# Separated-cell mesh diagnostic

This follow-up uses the existing eight-cell dFBA unit-test physiology and a new,
fixed geometry. It does not replace the original coincident-cell results.
The protocol is [mesh_protocol.json](mesh_protocol.json).

The [240-run analysis](../results/voxel_sharing/mesh-20261026/README.md) is complete.
One cell per voxel passed the measured glucose exchange-balance check, but parallel
update deficits persisted and the finest mesh produced negative glucose even in
serial controls. Smaller voxels alone are not a sufficient correctness criterion.
The report separates observations from hypotheses and identifies focused controls
to perform before interpreting parallel performance measurements.

Eight distinct centers form a rectangular array: x = -7/-5, y = -7/-3,
z = -7/1 microns. The domain stays [-8,8] in each direction. Positions, domain
volume, initial concentrations, timesteps and solver settings are identical across
meshes. Centers are at least one micron from every selected voxel boundary.
Cells stay fixed; population is fixed but metabolic biomass growth is enabled.
This is a controlled geometry, not a growing-tissue packing model.

| Cubic voxel edge (µm) | Total voxels | Occupied voxels | Cells per occupied voxel |
|---:|---:|---:|---:|
| 16 | 1 | 1 | 8 |
| 8 | 8 | 2 | 4 |
| 4 | 64 | 4 | 2 |
| 2 | 512 | 8 | 1 |

Each mesh has 1/2/4/8 threads × seeds 11/23/37/51/71 × three repeats: **240 runs**
in total. Duration is 0.1 simulated minutes; diffusion and intracellular dt remain
0.01 minutes as in the original test. The original loop end condition is retained.
Order is permuted once at initialization, never within a run.

Compare each parallel run with the serial run on **the same mesh, seed and
repetition**. Refinement also changes local nutrient amount; glucose diffusion is
disabled in this test, so unoccupied voxels cannot replenish the occupied ones.
Cross-mesh concentration differences alone cannot establish a race. Retain negative
concentrations, solver failures and missed updates. In the first campaign
(`mesh-20261026`, source `0e66312f`) the packed scheduler flags and shared-voxel
exchange code were unchanged, so separate occupancy did not promise race freedom;
later builds include the PR #19 fixes and are compared with `compare_builds.py`. Any comparison with proposed fixes must use separately identified
builds and reports.

Input generation checks predicted occupancy and rejects duplicate or boundary
centers. `benchmark_positions.csv` records actual coordinates and voxel indices;
`benchmark_population.csv` records observed maximum occupancy at each diagnostic
sample. Unexpected occupancy is flagged. Analysis produces separate figure folders
for each mesh, plus combined tables with mesh identifiers. `mesh_comparison` shows
missing updates and minimum-glucose differences against the matched serial run,
plotted versus observed maximum occupancy; colors identify thread counts.

Build a new unit-test binary with the explicit-position harness, following
[the common build instructions](../performance/README.md). Keep its build record.
In the documented Python environment, prepare a new campaign:

```bash
python benchmarks/voxel_sharing/prepare.py \
  --protocol benchmarks/voxel_sharing/mesh_protocol.json \
  --binary /absolute/new-build/dfba-unit-test \
  --build /absolute/new-build/build.json \
  --output benchmarks/workspaces/mesh-NEW
```

Validate representative runs at every mesh before the full matrix. Use the existing
`run_mn5.sbatch` launcher and `analyze.py` exporter with this new campaign. Reports,
tables and plots belong under `benchmarks/results/voxel_sharing/mesh-NEW/`.
