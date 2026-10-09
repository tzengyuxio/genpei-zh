#!/usr/bin/env bash
# Build the release patcher zips into patcher/dist/.
#
#   tools/release.sh v1.0.0
#
# Needs game/GENPEI (the original) and Go. The patch is the one tools/web.sh
# builds from scratch in a temporary directory (build/ is left alone).
# Ported from kami-zh tools/release.sh.
set -euo pipefail

version=${1:?usage: tools/release.sh VERSION}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d -t genpei-release)
trap 'command rm -rf "$work"' EXIT

"$root/tools/web.sh" >/dev/null 2>&1
cp "$root/web/dist/genpei-zh.kzp" "$root/patcher/"

dist=$root/patcher/dist
command rm -rf "$dist"
mkdir -p "$dist"

package() {   # package NAME BINARY
  local dir=$work/$1
  mkdir -p "$dir"
  cp "$2" "$dir/"
  # CRLF + BOM so Notepad on old Windows reads the UTF-8 text
  { printf '\xef\xbb\xbf'; sed "s/@VERSION@/$version/; s/\$/\r/" "$root/patcher/README.txt"; } > "$dir/README.txt"
  sed 's/$/\r/' "$root/patcher/genpei-zh.conf" > "$dir/genpei-zh.conf"
  (cd "$work" && zip -qrX "$dist/$1.zip" "$1")
}

cd "$root/patcher"
GOOS=windows GOARCH=amd64 go build -trimpath -ldflags=-s -o "$work/win/genpei-zh-patch.exe" .
package "genpei-zh-patch-$version-windows" "$work/win/genpei-zh-patch.exe"

GOOS=darwin GOARCH=arm64 go build -trimpath -ldflags=-s -o "$work/arm64" .
GOOS=darwin GOARCH=amd64 go build -trimpath -ldflags=-s -o "$work/amd64" .
mkdir -p "$work/mac"
lipo -create -output "$work/mac/genpei-zh-patch" "$work/arm64" "$work/amd64"
package "genpei-zh-patch-$version-macos" "$work/mac/genpei-zh-patch"

ls -l "$dist"
