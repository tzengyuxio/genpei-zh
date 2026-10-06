#!/usr/bin/env bash
# Assemble the browser version (web/) into web/dist/.
#
#   tools/web.sh          # build web/dist/
#   tools/web.sh serve    # build, then serve it at http://localhost:8000/
#
# Needs game/GENPEI (the original). The translation is built from scratch in
# a temporary directory (build/ is left alone). The patch is made against a
# copy of the original whose Main.exe is unpacked, as the build patches the
# unpacked image; web/app.js unpacks the player's Main.exe the same way.
# web/dist/ holds only the page, the script and genpei-zh.kzp -- no game
# data -- so it can be published as is.
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d -t genpei-web)
trap 'command rm -rf "$work"' EXIT
game=$root/game/GENPEI
orig=$work/orig
out=$work/build

mkdir -p "$orig" "$out"
cp "$game"/* "$orig/"
python3 "$root/tools/unpack_exe.py" "$game/Main.exe" "$orig/Main.exe" >/dev/null
cp "$orig"/* "$out/"
{
  python3 "$root/tools/patch.py" --apply "$root/translation/main.tsv" "$root/translation/main_data.tsv" --target "$out/Main.exe"
  python3 "$root/tools/patch.py" --apply "$root/translation/sndata.tsv" --target "$out/Sndata.gp"
  python3 "$root/tools/patch.py" --apply "$root/translation/open.tsv" --target "$out/Open.exe"
  python3 "$root/tools/patch.py" --apply "$root/translation/end.tsv" --target "$out/End.exe"
  python3 "$root/tools/message.py" apply "$game/Message.gp" "$root/translation/message.tsv" "$out/Message.gp"
  python3 "$root/tools/textimg.py" "$out"
} >/dev/null

dist=$root/web/dist
command rm -rf "$dist"
mkdir -p "$dist"
python3 "$root/tools/mkpatch.py" "$orig" "$out" "$dist/genpei-zh.kzp"
cp "$root/web/index.html" "$root/web/app.js" "$dist/"
echo "$dist 已就緒"

if [ "${1:-}" = serve ]; then
  cd "$dist" && python3 -m http.server 8000
fi
