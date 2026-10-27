#!/usr/bin/env bash
# Build an isolated source snapshot. Does not run the executable or submit jobs.
# Usage: build.sh SOURCE NEW_BUILD_DIR dfba_unit_test|cancer_core_metabolism|template [JOBS]
# SOURCE is normally the PhysiCelldFBA submodule. DFBA_EXT optionally names an
# installed addons/dFBA/ext (libSBML, Clp) to link instead of SOURCE's own.
# EXTRA_PATCHES optionally lists source patches (e.g. proposed-fixes/*.patch) applied
# after the hooks; they are listed with their digests in applied-patches.txt.
set -euo pipefail
source_repo=$(realpath "${1:?source checkout}")
destination=$(realpath -m "${2:?new build directory}")
project=${3:?project name}
jobs=${4:-4}
case "$project" in dfba_unit_test|cancer_core_metabolism|template) ;; *) exit 2;; esac
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || exit 2
mkdir "$destination"
echo "EXTRA_PATCHES='${EXTRA_PATCHES:-}' DFBA_EXT='${DFBA_EXT:-}' bash $0 $*" > "$destination/build-command.txt"
# Tracked source only; include staged edits for local verification, preserving
# their exact patch in the evidence. Publication builds must use clean commits.
git -C "$source_repo" ls-files -z | tar -C "$source_repo" --null -T - -cf - | tar -C "$destination" -xf -
git -C "$source_repo" diff HEAD --binary > "$destination/source.patch"
git -C "$source_repo" rev-parse HEAD > "$destination/source_commit.txt"
here=$(cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$destination/benchmarks/performance"
cp "$here/telemetry.h" "$here/runtime.h" "$destination/benchmarks/performance/"
# Unhooked PhysiCelldFBA receives the core and dFBA-engine hooks; pristine
# upstream receives only the shared core hooks, not dFBA code.
if ! grep -q PHYSICELL_BENCHMARK "$destination/core/PhysiCell_cell_container.cpp"; then
    if [[ -d "$destination/addons/dFBA/src" ]]; then
        patch -d "$destination" -p1 < "$here/physicelldfba-hooks.patch"
    else
        patch -l -d "$destination" -p1 < "$here/upstream-hooks.patch"
    fi
fi
: > "$destination/applied-patches.txt"
for extra in ${EXTRA_PATCHES:-}; do
    patch -d "$destination" -p1 < "$extra"
    sha256sum "$(realpath "$extra")" >> "$destination/applied-patches.txt"
done
if [[ "$project" == template ]]; then
    make -C "$destination" template > "$destination/staging.log" 2>&1
else
    mkdir -p "$destination/addons/dFBA"
    # Tracked ext/.gitkeep creates a real directory in the snapshot. Preserve
    # that placeholder so ln does not silently create the nested ext/ext link.
    if [[ -e "$destination/addons/dFBA/ext" ]]; then
        mv "$destination/addons/dFBA/ext" "$destination/benchmark-dependency-placeholder"
    fi
    ln -s "$(realpath "${DFBA_EXT:-$source_repo/addons/dFBA/ext}")" "$destination/addons/dFBA/ext"
    target=$project
    if [[ "$project" == cancer_core_metabolism ]]; then target=cancer-core-metabolism; fi
    make -C "$destination" "$target" > "$destination/staging.log" 2>&1
fi
cp "$here/driver.cpp" "$destination/main.cpp"
cat >> "$destination/Makefile" <<'EOF'

# Benchmark-only build: shared hooks compile out in ordinary builds.
override COMPILE_COMMAND += -DPHYSICELL_BENCHMARK
EOF
make -C "$destination" -j"$jobs" > "$destination/build.log" 2>&1
{
    "${PHYSICELL_CPP:-g++}" --version
    sha256sum "$destination/source.patch" "$here/driver.cpp" "$here/runtime.h" "$here/telemetry.h" "$here/upstream-hooks.patch" "$here/physicelldfba-hooks.patch"
    git -C "$source_repo" status --short
    echo "extra patches:"; cat "$destination/applied-patches.txt"
    echo "benchmark repository $(git -C "$here" rev-parse HEAD) $(git -C "$here" status --porcelain | wc -l) uncommitted"
} > "$destination/build-evidence.txt"
printf 'Built in %s; source.patch records local deviations. No simulation launched.\n' "$destination"
