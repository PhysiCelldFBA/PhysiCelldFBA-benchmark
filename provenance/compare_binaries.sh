#!/usr/bin/env bash
# Compare two executables after removing debug information: every remaining ELF section
# is compared, then the whole stripped file without the GNU build-id note (a hash the
# linker computes over the full output, debug sections included).
# usage: compare_binaries.sh NEW ORIGINAL
set -euo pipefail
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
objcopy --strip-debug "$1" "$tmp/new"; objcopy --strip-debug "$2" "$tmp/orig"
[ "$(readelf -SW "$tmp/new" | awk '{print $2,$6}')" = "$(readelf -SW "$tmp/orig" | awk '{print $2,$6}')" ] \
    && echo "section layout identical" || echo "section layout DIFFERS"
n=0; differing=""
for s in $(readelf -SW "$tmp/new" | awk '/^ *\[ *[0-9]+\]/{gsub(/\[ *[0-9]+\]/,""); print $1}' | grep -v '^NULL$'); do
    n=$((n+1))
    cmp -s <(objcopy -O binary --only-section="$s" "$tmp/new" /dev/stdout) \
           <(objcopy -O binary --only-section="$s" "$tmp/orig" /dev/stdout) || differing="$differing $s"
done
echo "$n sections compared; differing:${differing:- none}"
objcopy --remove-section=.note.gnu.build-id "$tmp/new" "$tmp/new.x"; objcopy --remove-section=.note.gnu.build-id "$tmp/orig" "$tmp/orig.x"
cmp -s "$tmp/new.x" "$tmp/orig.x" && echo "stripped files identical apart from the build-id note" || echo "stripped files DIFFER beyond the build-id note"
