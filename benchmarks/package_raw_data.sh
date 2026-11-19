#!/usr/bin/env bash
# Package the raw benchmark outputs (benchmarks/workspaces) for archiving: one byte-exact tar.zst per
# top-level folder. The simulator executables (thousands of identical copies of a few binaries) are left out
# of those archives and stored once per distinct SHA-256 in executables.tar.zst; manifests/*.executables.sha256
# maps every original path to its binary, and restore_executables.sh puts them back.
#
# Every archive is verified: it is extracted again and the SHA-256 of every file is compared with the source.
#
# Usage: package_raw_data.sh [folder ...]     (default: every folder in $SRC). Finished folders are skipped.
set -euo pipefail
export LC_ALL=C
SRC=${SRC:-/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark/benchmarks/workspaces}
OUT=${OUT:-/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark-rawdata-v1.0.0}
THREADS=${THREADS:-$(nproc)}
LEVEL=${LEVEL:-19}
M="$OUT/manifests"; T="$OUT/tmp"
mkdir -p "$M" "$T"
cd "$SRC"
if [ $# -gt 0 ]; then dirs=("$@"); else mapfile -t dirs < <(find . -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort); fi

hash_files() { xargs -0 -r -P "$THREADS" -n 32 sha256sum -- | sort -k2; }

for d in "${dirs[@]}"; do
  [ -d "$SRC/$d" ] || { echo "no such folder: $d" >&2; exit 1; }
  if [ -e "$M/$d.ok" ]; then echo "[$(date +%T)] $d: already done, skipped"; continue; fi
  t0=$SECONDS
  # 1. simulator executables: regular files named 'simulation' that start with the ELF magic number
  find "$d" -type f -name simulation -print0 | while IFS= read -r -d '' f; do
    if [ "$(head -c 4 -- "$f" | od -An -tx1 | tr -d ' \n')" = 7f454c46 ]; then printf '%s\0' "$f"; fi
  done | sort -z > "$T/$d.exe0"
  hash_files < "$T/$d.exe0" > "$M/$d.executables.sha256"
  # 2. archive members: everything else (folders, files, symlinks), and the SHA-256 of every regular file
  find "$d" -print0 | sort -z | comm -z -23 - "$T/$d.exe0" > "$T/$d.members0"
  find "$d" -type f -print0 | sort -z | comm -z -23 - "$T/$d.exe0" | hash_files > "$M/$d.sha256"
  # 3. archive
  tar --null --no-recursion -T "$T/$d.members0" --owner=0 --group=0 --numeric-owner -cf - \
    | zstd -q -"$LEVEL" --long=27 -T"$THREADS" -f -o "$OUT/$d.tar.zst"
  # 4. verify: extract, hash again, compare
  v="$T/verify-$d"; rm -rf -- "$v"; mkdir -p "$v"
  zstd -dc --long=27 "$OUT/$d.tar.zst" | tar -xf - -C "$v"
  ( cd "$v" && find "$d" -type f -print0 | sort -z | hash_files ) > "$T/$d.verify.sha256"
  cmp "$M/$d.sha256" "$T/$d.verify.sha256"
  n_src=$(tr -cd '\0' < "$T/$d.members0" | wc -c); n_dst=$(find "$v/$d" | wc -l)
  [ "$n_src" = "$n_dst" ] || { echo "$d: entry count differs ($n_src vs $n_dst)" >&2; exit 1; }
  rm -rf -- "$v" "$T/$d.verify.sha256" "$T/$d.exe0" "$T/$d.members0"
  touch "$M/$d.ok"
  printf '[%s] %s: %s files, %s executables left out, %s -> %s, verified, %ss\n' "$(date +%T)" "$d" \
    "$(wc -l < "$M/$d.sha256")" "$(wc -l < "$M/$d.executables.sha256")" \
    "$(du -sh --apparent-size "$d" | cut -f1)" "$(du -h --apparent-size "$OUT/$d.tar.zst" | cut -f1)" "$((SECONDS - t0))"
done

# 5. one copy of each distinct executable
e="$T/executables"; rm -rf -- "$e"; mkdir -p "$e/executables"
cat "$M"/*.executables.sha256 | sort -u -k1,1 | while read -r sha path; do
  mkdir -p "$e/executables/$sha"; cp -p -- "$SRC/$path" "$e/executables/$sha/simulation"
  echo "$sha  executables/$sha/simulation"
done > "$M/executables.sha256"
( cd "$e" && sha256sum -c --quiet "$M/executables.sha256" )
tar -C "$e" --owner=0 --group=0 --numeric-owner -cf - executables | zstd -q -"$LEVEL" --long=27 -T"$THREADS" -f -o "$OUT/executables.tar.zst"
rm -rf -- "$e"
cp -p "$SRC/README.md" "$OUT/workspaces-README.md" 2>/dev/null || true

# 6. checksums of the archives
cd "$OUT"
tar -cf - manifests | zstd -q -19 -f -o manifests.tar.zst
sha256sum -- *.tar.zst > SHA256SUMS
echo "[$(date +%T)] done: $(ls *.tar.zst | wc -l) archives, $(du -ch --apparent-size *.tar.zst | tail -1 | cut -f1) in total, $(wc -l < "$M/executables.sha256") distinct executables"
