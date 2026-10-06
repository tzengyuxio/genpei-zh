// Browser front end for the Chinese version of 源平合戦.
//
// The player picks their own DOS/V copy (a folder or a zip). Everything
// happens in this page: the files are checked against the SHA-256 sums in
// genpei-zh.kzp (written by tools/mkpatch.py), patched, zipped into a js-dos
// bundle and run in DOSBox-X compiled to WebAssembly. The original files
// are kept in IndexedDB so the player picks them only once; the patch is
// applied again on every start, so a new genpei-zh.kzp needs no re-pick.
// Nothing is uploaded anywhere.
//
// Ported from kami-zh web/app.js; everything specific to this game is in
// GAME below (see kami-zh docs/web-port.md).

import { unzipSync, zipSync } from "https://cdn.jsdelivr.net/npm/fflate@0.8.2/esm/browser.js";

const GAME = {
  id: "genpei-zh",              // IndexedDB name, prefix of the js-dos save key and localStorage
  patch: "genpei-zh.kzp",
  dir: "GENPEI",                // folder on the emulated C:
  marker: "MAIN.EXE",           // the picked folder is the one holding this file
  launcher: "GENPEI.COM",
  saveFile: "SAVEDATA.GP",      // the game's own save file, watched for changes
  stateFile: "genpeistate.sav", // DOSBox-X save state, copied to and from the snapshot slots
  // RLE-packed executables, unpacked before checking and patching (the
  // patch is made against the unpacked image, see tools/unpack_exe.py).
  unpack: ["MAIN.EXE"],
  // GENPEI.COM: turn the exec of OPEN.EXE into a jump to the exec of MAIN.EXE.
  skipOpening: { file: "GENPEI.COM", offset: 0x5a3, from: [0xba, 0x53, 0x05], to: [0xeb, 0x1a] },
  // Same set-up as tools/dosbox/genpei.conf and run.sh, minus getsysfont
  // (no host fonts in a browser; DOSBox-X falls back to its built-in one).
  conf: (state, dir, launcher) => `[sdl]
autolock = false

[dosbox]
machine = svga_s3
# Save states go to one file in the bundle root, where app.js can read it.
savefile = ${state}
usesavefile = true

[dosv]
dosv = jp

[dos]
country = 81
# EMS only: with XMS too, Main.exe hangs right after the leader is chosen.
xms = false
ems = emsboard

[cpu]
cputype = 386
cycles = 20000

[autoexec]
mount c .
c:
cd ${dir}
${launcher}
`,
};

const JSDOS = "https://cdn.jsdelivr.net/npm/js-dos@8.5.1/dist/";
const SAVE_KEY = `${GAME.id}.changes`;   // js-dos stores the game's disk changes under this key
const SAVE_PATH = `${GAME.dir}/${GAME.saveFile}`;
const STATE_FILE = GAME.stateFile;
const SLOTS = 8;
const POLL_MS = 3000;

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- storage

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(GAME.id, 1);
    req.onupgradeneeded = () => req.result.createObjectStore("files");
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function dbOp(mode, fn) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("files", mode);
    const req = fn(tx.objectStore("files"));
    tx.oncomplete = () => resolve(req && req.result);
    tx.onerror = () => reject(tx.error);
  });
}

const loadOriginal = () => dbOp("readonly", (s) => s.get("original"));
const storeOriginal = (files) => dbOp("readwrite", (s) => s.put(files, "original"));
const forgetOriginal = () => dbOp("readwrite", (s) => s.delete("original"));
const loadSlot = (n) => dbOp("readonly", (s) => s.get(`state-${n}`));
const storeSlot = (n, slot) => dbOp("readwrite", (s) => s.put(slot, `state-${n}`));

// ------------------------------------------------------------------ patch

function parsePatch(buf) {
  const v = new DataView(buf);
  const u8 = new Uint8Array(buf);
  if (String.fromCharCode(...u8.slice(0, 4)) !== "KZP1") throw new Error("修補資料損毀");
  let p = 4;
  const count = v.getUint16(p, true); p += 2;
  const files = [];
  for (let i = 0; i < count; i++) {
    const n = u8[p++];
    // DOS names are case-insensitive; the original files are mixed case (Main.exe).
    const name = String.fromCharCode(...u8.slice(p, p + n)).toUpperCase(); p += n;
    const f = { name };
    f.srcSize = v.getUint32(p, true); p += 4;
    f.srcSum = u8.slice(p, p + 32); p += 32;
    f.dstSize = v.getUint32(p, true); p += 4;
    f.dstSum = u8.slice(p, p + 32); p += 32;
    const ops = v.getUint32(p, true); p += 4;
    f.ops = [];
    for (let j = 0; j < ops; j++) {
      if (u8[p] === 0) {
        f.ops.push([0, v.getUint32(p + 1, true), v.getUint32(p + 5, true)]);
        p += 9;
      } else {
        const len = v.getUint32(p + 1, true);
        f.ops.push([1, u8.subarray(p + 5, p + 5 + len)]);
        p += 5 + len;
      }
    }
    files.push(f);
  }
  return files;
}

function applyOps(src, f) {
  const out = new Uint8Array(f.dstSize);
  let o = 0;
  for (const op of f.ops) {
    const part = op[0] === 0 ? src.subarray(op[1], op[1] + op[2]) : op[1];
    out.set(part, o);
    o += part.length;
  }
  return out;
}

async function sha256(data) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", data));
}

const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

// Throws with a message for the player when the copy is not the expected one.
async function checkOriginal(files, patch) {
  for (const f of patch) {
    const src = files[f.name];
    if (!src) throw new Error(`缺少 ${f.name}`);
    const sum = await sha256(src);
    if (same(sum, f.dstSum)) throw new Error(`${f.name} 已經是中文版，請選擇日文原版的檔案`);
    if (!same(sum, f.srcSum)) throw new Error(`${f.name} 與 DOS/V 原版不符（可能是其他版本或已修改過）`);
  }
  if (!files[GAME.launcher]) throw new Error(`缺少 ${GAME.launcher}`);
}

async function patched(files, patch, skipOpening) {
  const out = { ...files };
  for (const f of patch) {
    const dst = applyOps(files[f.name], f);
    if (!same(await sha256(dst), f.dstSum)) throw new Error(`${f.name} 修補結果不符`);
    out[f.name] = dst;
  }
  const skip = GAME.skipOpening;
  if (skipOpening && skip) {
    const com = out[skip.file].slice();
    if (same(com.subarray(skip.offset, skip.offset + skip.from.length), skip.from)) com.set(skip.to, skip.offset);
    out[skip.file] = com;
  }
  return out;
}

// --------------------------------------------------------------- unpacking

// Copy of files with the GAME.unpack executables unpacked. A file that is
// not packed the expected way is left as is, so checkOriginal() reports it.
function unpacked(files) {
  const out = { ...files };
  for (const name of GAME.unpack) {
    if (!out[name]) continue;
    try { out[name] = unpackExe(out[name]); } catch {}
  }
  return out;
}

// Port of tools/unpack_exe.py (see there for the packer's layout).
function unpackExe(exe) {
  const v = new DataView(exe.buffer, exe.byteOffset, exe.byteLength);
  const w = (o) => v.getUint16(o, true);
  const image = exe.subarray(w(8) * 16);
  const cs = w(22);
  const stub = image.subarray(cs * 16);
  const sw = (o) => stub[o] | (stub[o + 1] << 8);
  if (!same(stub.subarray(1, 7), [0x9c, 0x50, 0x8c, 0xda, 0x52, 0x52])) throw new Error("unknown packer stub");

  const top = cs * 16 + sw(0x10) * 16 - 16 + 0x10;
  const out = new Uint8Array(top);
  let ctl = 0x1977;
  let src = cs * 16 - 11;
  let dst = top - 1;
  for (let r = sw(0x2b); r > 0; r--) {
    const b0 = stub[ctl--];
    let lit = stub[ctl--];
    if (b0 & 1) lit = (lit << 8) | stub[ctl--];
    let fill = b0 >> 2;
    if (b0 & 2) fill = (fill << 8) | stub[ctl--];
    const value = stub[ctl--];
    for (; lit > 0; lit--) out[dst--] = image[src--];
    for (; fill > 0; fill--) out[dst--] = value;
  }
  if (dst !== -1) throw new Error("bad packed image");

  const relocs = [];
  let p = 0x1978, seg = 0, off = 0;
  for (let r = sw(0x8b); r > 0; r--) {
    const b = stub[p++];
    let delta = b;
    if (b <= 1) {
      if (b === 1) seg += stub[p++] << 8;
      delta = sw(p); p += 2;
    }
    off += delta;
    if (off > 0xffff) { off -= 0x10000; seg += 0x1000; }
    if (off === 0xffff) { off = 0xffef; seg += 1; }
    relocs.push([seg, off]);
  }

  // build_mz(): a plain MZ header, the relocation table, then the image.
  const ss = sw(0xb8), sp = sw(0xbd);
  const hdrSize = Math.ceil((0x1c + 4 * relocs.length) / 16) * 16;
  const total = hdrSize + out.length;
  const minAlloc = Math.max(0, Math.floor((ss * 16 + sp - out.length + 15) / 16));
  const res = new Uint8Array(total);
  const rv = new DataView(res.buffer);
  [0x5a4d, total % 512, Math.ceil(total / 512), relocs.length, hdrSize / 16, minAlloc, 0xffff,
    ss, sp, 0, sw(0xc0), sw(0xc2), 0x1c, 0].forEach((x, i) => rv.setUint16(i * 2, x, true));
  relocs.forEach(([s, o], i) => {
    rv.setUint16(0x1c + i * 4, o, true);
    rv.setUint16(0x1e + i * 4, s, true);
  });
  res.set(out, hdrSize);
  return res;
}

// ---------------------------------------------------------------- picking

// Keeps the files that sit next to GAME.marker, keyed by upper-case name.
function gameFiles(entries) {
  const main = entries.find((e) => baseName(e.path).toUpperCase() === GAME.marker);
  if (!main) throw new Error(`找不到 ${GAME.marker}，請選擇含有遊戲檔的 ${GAME.dir} 資料夾或其壓縮檔`);
  const dir = dirName(main.path);
  const files = {};
  for (const e of entries) {
    if (dirName(e.path) === dir && baseName(e.path)) files[baseName(e.path).toUpperCase()] = e.data;
  }
  return files;
}

const baseName = (p) => p.slice(p.lastIndexOf("/") + 1);
const dirName = (p) => p.slice(0, p.lastIndexOf("/") + 1);

async function fromFileList(list) {
  const entries = [];
  for (const file of list) {
    if (file.name.toLowerCase().endsWith(".zip")) {
      const unzipped = unzipSync(new Uint8Array(await file.arrayBuffer()));
      for (const [path, data] of Object.entries(unzipped)) {
        if (!path.includes("__MACOSX")) entries.push({ path, data });
      }
    } else {
      entries.push({ path: file.webkitRelativePath || file.name, data: new Uint8Array(await file.arrayBuffer()) });
    }
  }
  return gameFiles(entries);
}

// --------------------------------------------------------------------- ui

let patch;
let dosProps = null;

function status(text, isError = false) {
  const el = $("status");
  el.textContent = text;
  el.classList.toggle("error", isError);
}

async function showStart() {
  const original = await loadOriginal();
  $("setup").hidden = !!original;
  $("ready").hidden = !original;
}

async function pick(list) {
  if (!list.length) return;
  try {
    status("讀取中…");
    const files = await fromFileList(list);
    status("驗證中…");
    await checkOriginal(unpacked(files), patch);
    await storeOriginal(files);
    status("");
    await showStart();
  } catch (e) {
    status(e.message, true);
  }
}

async function start() {
  const skip = $("skip").checked;
  try { localStorage.setItem(`${GAME.id}-skip`, skip ? "1" : ""); } catch {}
  let files;
  try {
    const original = unpacked(await loadOriginal());
    await checkOriginal(original, patch);
    files = await patched(original, patch, skip);
  } catch (e) {
    $("ready-status").textContent = e.message;
    return;
  }
  const bundle = { ".jsdos/dosbox.conf": new TextEncoder().encode(GAME.conf(STATE_FILE, GAME.dir, GAME.launcher)) };
  for (const [name, data] of Object.entries(files)) bundle[`${GAME.dir}/${name}`] = data;
  const url = URL.createObjectURL(new Blob([zipSync(bundle, { level: 0 })]));

  document.body.classList.add("playing");
  dosProps = Dos($("dos"), {
    url,
    backend: "dosboxX",
    pathPrefix: JSDOS + "emulators/",
    autoStart: true,
    kiosk: true,
    noCloud: true,
    quickSave: false,   // F6/F7 are handled below, into our own quick slot
    autoSave: true,
    fsChanges: { urlToKey: () => SAVE_KEY },
    onEvent: (event, c) => {
      if (event === "ci-ready") {
        ci = c;
        watchSaves();
      }
    },
  });
}

// ------------------------------------------------- automatic disk saving

let ci = null;

// Size of a file in the bundle root, or null when it does not exist.
// (fsReadFile never settles for a missing file, so look it up first.)
async function fileSize(path) {
  const parts = path.split("/");
  let node = await ci.fsTree();
  for (const part of parts) {
    node = (node.nodes || []).find((n) => n.name === part);
    if (!node) return null;
  }
  return node.size ?? null;
}

async function readFile(path) {
  return (await fileSize(path)) === null ? null : ci.fsReadFile(path);
}

// The game writes GAME.saveFile when the player saves in game. Once it has
// stopped changing, hand the disk changes to js-dos to keep in the browser.
async function watchSaves() {
  let saved = await digest(await readFile(SAVE_PATH));
  let pending = null;
  for (;;) {
    await sleep(POLL_MS);
    let now;
    try {
      now = await digest(await readFile(SAVE_PATH));
    } catch {
      continue;
    }
    if (now === saved) { pending = null; continue; }
    if (now !== pending) { pending = now; continue; }   // still being written
    if (await persist()) saved = now;
    pending = null;
  }
}

async function digest(data) {
  if (!data) return "";
  return Array.from(await sha256(data)).join(",");
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function persist() {
  try {
    await (await dosProps).save();
    note(`已自動保存遊戲存檔（${clock()}）`);
    return true;
  } catch (e) {
    console.error(e);
    note("保存遊戲存檔失敗", true);
    return false;
  }
}

const clock = (d = new Date()) => d.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" });

function note(text, isError = false) {
  const el = $("note");
  el.textContent = text;
  el.classList.toggle("error", isError);
}

// ---------------------------------------------------------- snapshots

// A snapshot is a DOSBox-X save state: the whole machine, so it works in
// dungeons too. DOSBox-X writes it to STATE_FILE; each slot keeps a copy
// in IndexedDB together with a thumbnail. It does not include the disk, so
// the game's own saves are unaffected by loading one.

async function saveState(n) {
  // Remove the last state first: saving twice in the same spot can write
  // identical bytes, which could not be told apart from "not written yet".
  if ((await fileSize(STATE_FILE)) !== null) await ci.fsDeleteFile(STATE_FILE);
  const shot = await thumbnail();
  ci.sendBackendEvent({ type: "wc-trigger-event", event: "hand_savestate" });
  for (let i = 0; i < 40; i++) {
    await sleep(250);
    if (await fileSize(STATE_FILE)) {
      await sleep(500);   // let the write finish
      const final = await readFile(STATE_FILE);
      await storeSlot(n, { data: final, shot, time: Date.now() });
      return true;
    }
  }
  throw new Error("快照沒有寫出來");
}

async function loadState(n) {
  const slot = await loadSlot(n);
  if (!slot) return;
  await ci.fsWriteFile(STATE_FILE, slot.data);
  ci.sendBackendEvent({ type: "wc-trigger-event", event: "hand_loadstate" });
}

async function thumbnail() {
  try {
    const img = await ci.screenshot();
    const full = document.createElement("canvas");
    full.width = img.width;
    full.height = img.height;
    full.getContext("2d").putImageData(img, 0, 0);
    const small = document.createElement("canvas");
    small.width = 160;
    small.height = 120;
    small.getContext("2d").drawImage(full, 0, 0, 160, 120);
    return small.toDataURL("image/png");
  } catch {
    return null;
  }
}

// The quick slot is slot "quick": F6 / the toolbar saves into it without
// asking, F7 loads it back.
const slotName = (n) => (n === "quick" ? "快速快照" : `快照 ${n}`);

async function quickSave() {
  if (!ci || busy) return;
  busy = true;
  try {
    await saveState("quick");
    note(`已快速保存（${clock()}）`);
  } catch (e) {
    note(e.message, true);
  } finally {
    busy = false;
  }
  if (!$("slots").hidden) showSlots();
}

async function quickLoad() {
  if (!ci || busy) return;
  if (!(await loadSlot("quick"))) {
    note("還沒有快速快照，先按 F6 或「快速保存」", true);
    return;
  }
  await loadState("quick");
  note(`已快速載入（${clock()}）`);
}

let busy = false;

async function showSlots() {
  const list = $("slot-list");
  list.textContent = "";
  for (const n of ["quick", ...Array.from({ length: SLOTS }, (_, i) => i + 1)]) {
    const slot = await loadSlot(n);
    const li = document.createElement("li");
    const img = document.createElement("div");
    img.className = "thumb";
    if (slot && slot.shot) img.style.backgroundImage = `url(${slot.shot})`;
    const label = document.createElement("span");
    const tag = n === "quick" ? "快速" : `${n}.`;
    label.textContent = slot
      ? `${tag} ${new Date(slot.time).toLocaleString("zh-TW", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}`
      : `${tag} （空）`;
    const save = document.createElement("button");
    save.textContent = "存";
    save.addEventListener("click", async () => {
      if (slot && !confirm(`要覆蓋${slotName(n)}嗎？`)) return;
      save.disabled = true;
      try {
        await saveState(n);
        note(`已存入${slotName(n)}（${clock()}）`);
      } catch (e) {
        note(e.message, true);
      }
      showSlots();
    });
    const load = document.createElement("button");
    load.textContent = "讀";
    load.disabled = !slot;
    load.addEventListener("click", async () => {
      if (!confirm(`要讀取${slotName(n)}嗎？目前尚未存檔的進度會遺失。`)) return;
      await loadState(n);
      $("slots").hidden = true;
      note(`已讀取${slotName(n)}`);
    });
    li.append(img, label, save, load);
    list.append(li);
  }
}

function toggleSlots() {
  const panel = $("slots");
  panel.hidden = !panel.hidden;
  if (!panel.hidden) showSlots();
}

async function quit() {
  if (!confirm("確定要結束遊戲嗎？遊戲內的存檔已自動保存。")) return;
  await persist();
  location.reload();
}

async function forget() {
  if (!confirm("要刪除存在這個瀏覽器裡的原版遊戲檔嗎？存檔不會刪除，下次需要重新選擇原版檔。")) return;
  await forgetOriginal();
  await showStart();
}

async function main() {
  try { $("skip").checked = localStorage.getItem(`${GAME.id}-skip`) === "1"; } catch {}
  $("pick-dir").addEventListener("change", (e) => pick(e.target.files));
  $("pick-zip").addEventListener("change", (e) => pick(e.target.files));
  $("start").addEventListener("click", start);
  $("forget").addEventListener("click", forget);
  $("snap").addEventListener("click", toggleSlots);
  $("qsave").addEventListener("click", quickSave);
  $("qload").addEventListener("click", quickLoad);
  // Capture phase, so the keys never reach the emulator.
  window.addEventListener("keydown", (e) => {
    if (!document.body.classList.contains("playing") || (e.key !== "F6" && e.key !== "F7")) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (!e.repeat) (e.key === "F6" ? quickSave : quickLoad)();
  }, true);
  window.addEventListener("keyup", (e) => {
    if (document.body.classList.contains("playing") && (e.key === "F6" || e.key === "F7")) {
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  }, true);
  $("quit").addEventListener("click", quit);
  try {
    patch = parsePatch(await (await fetch(GAME.patch)).arrayBuffer());
  } catch (e) {
    status("載入修補資料失敗：" + e.message, true);
    return;
  }
  await showStart();
}

main();
