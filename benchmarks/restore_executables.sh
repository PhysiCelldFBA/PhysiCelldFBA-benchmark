#!/usr/bin/env bash
# Put the simulator executables back where they were in every extracted campaign folder.
# Usage: restore_executables.sh [directory]   (the directory where the archives were extracted; default: here)
set -euo pipefail
cd "${1:-.}"
[ -d executables ] && [ -d manifests ] || { echo "extract executables.tar.zst and manifests.tar.zst here first" >&2; exit 1; }
n=0
for m in manifests/*.executables.sha256; do
  while read -r sha path; do
    [ -d "$(dirname -- "$path")" ] || continue   # this campaign was not extracted
    cp -p -- "executables/$sha/simulation" "$path"; chmod +x -- "$path"; n=$((n + 1))
  done < "$m"
done
echo "restored $n executables"
