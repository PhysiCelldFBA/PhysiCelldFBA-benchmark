# Provenance of the published results

The benchmarks were developed and first run on a private branch of PhysiCelldFBA
(`integration/manuscript-benchmarks`) and moved to this repository at its commit
`adb38285`. The `build.json`, `campaign.json` and report files under
`benchmarks/results/` record that branch's commit IDs, which are not public. This
file maps each one to public PhysiCelldFBA source and records how the mapping was checked.

## Mapping

On that branch, everything outside `benchmarks/` differed from public PhysiCelldFBA
only by the benchmark hooks (5 files, all inside `#ifdef PHYSICELL_BENCHMARK`) and a
documentation-only `README.md` in `sample_projects_intracellular/fba/dfba_unit_test/`.
The hooks are [`benchmarks/performance/physicelldfba-hooks.patch`](benchmarks/performance/physicelldfba-hooks.patch).

| Results | Recorded source commit | Public equivalent | Binary (SHA-256 prefix) |
|---|---|---|---|
| [`voxel_sharing/voxel-20261026`](benchmarks/results/voxel_sharing/voxel-20261026) (pre-fix) | `8ae6a1d7` | `development` @ `b0d810b4` + hooks patch; harness `runtime.h` as of that commit (SHA-256 `2a6aa1d775fd…`) | `2990326295d1` |
| [`voxel_sharing/mesh-20261026`](benchmarks/results/voxel_sharing/mesh-20261026), [`growth_conditions/growth-20261026`](benchmarks/results/growth_conditions), [`timestep/pilot-20261026`](benchmarks/results/timestep) (pre-fix) | `0e66312f` | `development` @ `b0d810b4` + hooks patch | unit test `29bc0c4af380`; cancer model `e2034f57e36e` |
| [`voxel_sharing/voxel-20261027`](benchmarks/results/voxel_sharing/voxel-20261027), [`voxel_sharing/mesh-20261027`](benchmarks/results/voxel_sharing/mesh-20261027) (after PR #19) | `23f456b0` | `development` @ `a2519f06` + hooks patch (the submodule commit) | `c74353427dee` |

`b0d810b4` is the merge of PhysiCelldFBA PR #16; `a2519f06` is the merge of PR #19
(parallel race fixes). All other harness files (`driver.cpp`, `telemetry.h`,
`upstream-hooks.patch`, and `runtime.h` for the later builds) are unchanged in this
repository; their digests are in each report's `build.json`.

## Verification

Performed on MN5 (Sapphire Rapids, GCC 11.5.0) on 2026-10-27, from this repository at
commit `b0e30cb`. Script and log: [`provenance/verify_builds.sh`](provenance/verify_builds.sh),
[`provenance/verify_builds.log`](provenance/verify_builds.log).

1. **Source identity.** Applying the hooks patch to `b0d810b4` reproduces the `core/`
   and `addons/dFBA/src/` trees of `8ae6a1d7` and `0e66312f` byte for byte. Applying
   it to `a2519f06` reproduces those of `23f456b0`.
2. **Builds.** Each binary was rebuilt with `benchmarks/performance/build.sh` from the
   public commit and compared with the original executable
   ([`provenance/binary_comparison.txt`](provenance/binary_comparison.txt),
   [`provenance/compare_binaries.sh`](provenance/compare_binaries.sh)):
   - all 33 object files are byte-identical to the original build's;
   - after removing debug information, all ELF sections and their layout are
     identical except `.note.gnu.build-id`, and the stripped files are identical
     once that note is removed.

   The full-file SHA-256 differs because the project Makefile links with `-ggdb`,
   which embeds the absolute build directory in the debug information; the build-id
   note is a hash over the whole file and changes with it. The executable code and
   data are the same.
3. **Inputs.** Campaigns prepared from this repository (configs and SBML read from the
   submodule) have the same input-file digests, case lists and per-bundle comparison
   keys as the original post-fix campaigns (60 and 240 bundles).
4. **Tests.** `test_workflow.py` (9 tests) and `test_campaign.py` (4 tests) pass
   ([`provenance/unit_tests.log`](provenance/unit_tests.log)).

The recorded binary hashes of the original executables were re-checked on the same day
and still match the reports.
