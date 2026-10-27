# PhysiCelldFBA manuscript benchmarks

This directory contains reproducible experiments intended for the supplementary
material. Scripts, protocols and documentation are versioned here. Generated
campaigns and large simulation outputs belong in ignored `workspaces/` folders;
reviewed compact evidence, tables and figures can be committed under `results/`.

| Study | Purpose | Protocol/code | Status |
|---|---|---|---|
| Shared voxel | Eight cells in one voxel, serial/parallel execution and per-run update-order seeds | [voxel_sharing/README.md](voxel_sharing/README.md) | [Pre-fix: 60 runs](results/voxel_sharing/voxel-20261026/README.md); [after PR #19: 60 runs](results/voxel_sharing/voxel-20261027/README.md), parallel identical to serial ([comparison](results/voxel_sharing/before-after-20261027/README.md)) |
| Mesh occupancy | Eight distinct fixed centers; 8/4/2/1 cells per occupied voxel | [voxel_sharing/MESH_STUDY.md](voxel_sharing/MESH_STUDY.md) | [Pre-fix: 240 runs](results/voxel_sharing/mesh-20261026/README.md), update deficits at every occupancy; [after PR #19: 240 runs](results/voxel_sharing/mesh-20261027/README.md), none ([comparison](results/voxel_sharing/before-after-20261027/README.md)) |
| Intracellular timestep | Ratios 1, 2, 10, 100; E. coli and cancer; reference refinement | [performance/TIMESTEP_PILOTS.md](performance/TIMESTEP_PILOTS.md) | [Eleven pilots analyzed](results/timestep/pilot-20261026/README.md). Ratios > 1 were dominated by an exchange-scaling defect; [re-run with a proposed fix](results/timestep/exchange-fix-20261027/README.md). Trade-off protocol in preparation |
| Model-specific growth conditions | Native and supplied media, single cells and fixed-volume populations | [performance/model_conditions/README.md](performance/model_conditions/README.md) | [23 dynamic controls analyzed](results/growth_conditions/growth-20261026/README.md); 10 pass full checks |
| Cancer FBA/pFBA | Outcomes and runtime after selecting the timestep | [performance/README.md](performance/README.md) | Pending timestep study |
| Performance/scaling | Cells, fields, networks and threads; upstream/disabled baselines | [performance/README.md](performance/README.md) | Pilot/workload validation pending |

`performance/` supplies shared build, input, telemetry and collection utilities.
The shared-voxel protocol uses the existing sample project's eight-cell test,
with disclosed benchmark controls and observations; it does not change production
solver algorithms or repair races. It also does not establish an architectural
guarantee of one cell per voxel. A smaller voxel reduces sharing risk for a given
cell distribution; measured occupancy and concurrency controls still matter.

Preparing the shared-voxel campaign creates all four study folders, each with
`inputs/`, `bundles/`, `runs/`, `tables/`, `plots/` and `logs/`. Only the shared-voxel
part is populated/submitted by that workflow. Git preserves the publication
table/plot directories through `.gitkeep` files in `results/<study>/`.

## Reproduction and publication

1. Check out the published source commit and read the study-specific README.
2. Build in an isolated directory using `performance/build.sh`; retain compiler,
   dependency, solver, source and executable provenance. Native compiler flags
   require a compatible execution CPU; record the resolved architecture.
3. Prepare a **new** campaign directory. Finalized input bundles carry checksums;
   do not edit them after staging. Regenerate bundles when moving to another host.
4. Submit only the selected study. Attempts are separate, including failed and
   diagnostically flagged runs. No preparation script submits jobs.
5. Run analysis manually in the documented Python environment. Verify coverage,
   order identity, actual thread counts, update counts and failed attempts before
   interpreting plots. Do not silently remove inconvenient outcomes.
6. Publish a report under `results/<study>/<campaign>/`, including the protocol,
   build/source identities, compact raw evidence, tables and figures. Keep bulky
   binaries, duplicated SBML bundles and MultiCellDS snapshots out of Git; provide
   an archival data link if full snapshots accompany the paper.

The report exporter is the study's analysis script. It copies compact per-run
telemetry, settings, manifests, hardware/resource metadata and logs alongside
its tables/plots, with checksums in `analysis.json`. These are collected results,
not fabricated examples. Before jobs finish, result and plot folders are empty.

Python preparation/collection uses the standard library. Plotting requires
Matplotlib. Additional snapshot analysis should prefer `pctk`; `pcdl` is not
required. On MN5 use the project's HDF5/Python 3.12.1 environment; analysis must
run in the allocation/environment described in the study README.
