#!/usr/bin/env bash
# Launch the patched game in DOSBox-X.
#
#   tools/dosbox/run.sh            play (mouse works, click through menus)
#   tools/dosbox/run.sh 90         record 90s to build/captures/ and exit
#   GENPEI_START=End.exe tools/dosbox/run.sh   play only the ending
#
# This script copies game/GENPEI/ -> build/GENPEI/ on first run (if missing),
# so game/ stays untouched. Patched artefacts should land in build/GENPEI/.
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
limit=${1:-}
conf=$(mktemp -t genpei-conf)

# Mirror game/GENPEI into build/GENPEI if build is empty. Keep game/ pristine.
if [ ! -d "$root/build/GENPEI" ]; then
  mkdir -p "$root/build"
  cp -R "$root/game/GENPEI" "$root/build/GENPEI"
fi

{
  sed "s|@ROOT@|$root|" "$root/tools/dosbox/genpei.conf"
  echo "mount c $root/build"
  echo "c:"
  # build/FAKEMS.COM, if present, scripts the mouse (see tools/mousetsr.py)
  [ -f "$root/build/FAKEMS.COM" ] && echo 'c:\FAKEMS.COM'
  echo "cd GENPEI"
  [ -n "$limit" ] && echo "config -avistart"
  echo "${GENPEI_START:-Genpei.com}"
} > "$conf"

args=(-conf "$conf" -nopromptfolder -fastlaunch -nolog)
[ -n "$limit" ] && args+=(-time-limit "$limit" -exit)

if [ -z "$limit" ]; then
  exec dosbox-x "${args[@]}"
fi
# DOSBox-X on macOS sometimes hangs past -time-limit; kill it if it does.
dosbox-x "${args[@]}" &
pid=$!
( sleep $((limit + 30)); kill -9 "$pid" 2>/dev/null && echo "watchdog: killed hung dosbox-x" >&2 ) &
wait "$pid" || true
