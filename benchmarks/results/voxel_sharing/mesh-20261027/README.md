# Separated-cell mesh results after the PR #19 race fixes

Repeat of the [240-run mesh campaign](../mesh-20261026/README.md) with the unchanged
protocol on source `23f456b0`, which includes PR #19. All 240 runs completed and passed
`summarize_mesh.py` validation: 240 runs and 180 matched pairs, with geometry, occupancy,
orders, thread counts and timesteps as specified. At every occupancy (8/4/2/1 cells per
voxel) and thread count, parallel runs perform all 80 updates, pass the glucose
exchange-balance check, and match their serial run exactly in minimum glucose and
biomass. Only the 2 µm mesh is flagged (`negative_concentration`, −1.19×10⁻⁶ mM, serial
and parallel alike); the comparison report explains this.

Analysis, figures and interpretation:
[before/after comparison](../before-after-20261027/README.md). This directory holds the
`analyze.py` export and the `summarize_mesh.py` tables
([mesh_thread_summary](tables/mesh_thread_summary.csv),
[per-run diagnostics](tables/mesh_run_diagnostics.csv),
[same-seed repeats](tables/same_seed_repeats.csv)), plus [mesh_validation.json](mesh_validation.json).
Simulation job 48112701; export job 48113002.
