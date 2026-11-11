# The manuscript's own simulations, as shipped: wall time and memory

The six dFBA sample projects of PhysiCelldFBA `c59daa81`, built without benchmark hooks or patches
([workflow/build.sh](workflow/build.sh), [workflow/builds.tsv](workflow/builds.tsv)) and run with their
shipped configuration. Each run had one exclusive MareNostrum 5 GPP node (2 × 56 cores; launcher
[workflow/run.sbatch](workflow/run.sbatch)). The simulations with fewer threads than a node were
repeated at 56 threads, changing only `omp_num_threads`. Submitted 2026-11-09 (12 Slurm jobs,
[workflow/submitted-jobs.tsv](workflow/submitted-jobs.tsv)). Analysis:
[`analyze_apps.py`](../../../performance/analyze_apps.py); per-run table [tables/apps.csv](tables/apps.csv).

| Simulation (project) | Threads | Diffusion / intracellular dt (min) | Simulated | Cells: start → end | Wall time | Peak memory |
|---|---:|---|---:|---|---:|---:|
| Unit test (`dfba_unit_test`) | 4 (shipped) | 0.001 / 0.001 | 4 h | 1 → 8 | 30 s | 20 MB |
| | 56 | | | | 66 s | 20 MB |
| Motility (`metabolic_driven_motility`, `_motility.xml`) | 6 (shipped) | 0.001 / 0.001 | 10 h | 1 | 65 s | 14 MB |
| | 56 | | | | 93 s | 14 MB |
| Motility and proliferation (same project, `_motility_proliferation.xml`) | 6 (shipped) | 0.001 / 0.001 | 10 h | 1 → 4 | 65 s | 14 MB |
| | 56 | | | | 95 s | 16 MB |
| Acetate switch (`ecoli_acetic_switch`) | 3 (shipped) | 0.001 / 0.001 | 10 h | 200 → 1600 | 4.08 h | 0.28 GB |
| | 56 | | | | 0.72 h | 0.28 GB |
| Cancer metabolism (`cancer_core_metabolism`) | 6 (shipped) | 0.01 / 0.01 | 72 h | 240 → 354 | 2.42 h | 0.15 GB |
| | 56 | | | 240 → 352 | 0.55 h | 0.14 GB |
| Bacterial colony (`bacterial_colony`) | 112 (shipped) | 0.001 / 0.001 | 10 h | 211 → 93 655 | 16.0 h | 11.0 GB |
| Cross-feeding (`crossfeeding`) | 112 (shipped) | 0.001 / 0.001 | **42.5 of 50 h, crashed** | 353 → 29 742 | 30.2 h | 14.2 GB |

Peak memory is the maximum resident set size reported by GNU time. Wall time includes start-up and output.

## Findings

- **Small simulations take about a minute.** With 1–8 cells, start-up, output and thread management dominate,
  and 56 threads are slower than the shipped 4–6 (0.45–0.70×).
- **With hundreds of cells, more threads pay off.** At 56 threads the acetate switch runs 5.7× faster
  than with the shipped 3 threads, and the cancer application 4.4× faster than with the shipped 6. The
  configurations as shipped use a small part of a modern node.
- **Growing bacterial populations dominate the cost.** At the shipped diffusion and intracellular dt of
  0.001 min, the bacterial colony grows from 211 to about 94 000 cells in 10 simulated hours and needs 16 h on a
  full node. Cross-feeding needs 30 h on a full node to reach 42.5 simulated hours. The wall time per simulated hour grows with the
  population. Cost per cell and diffusion step is 3.6 µs (acetate switch, 56 threads) and 4.0 µs (bacterial
  colony, 112 threads) with E. coli core, and 5.9 µs for cross-feeding (112 threads; trimmed
  C. beijerinckii iCB925 and M. barkeri iMG746, about 99% C. beijerinckii cells at the end).
- **The timestep is the main lever for these runs.** Running the metabolism every 10 diffusion
  steps instead of every step saves 7–10× on one thread but at most about 2.3× on 56 threads for E. coli core,
  whose LPs are cheap ([final report](../../final-20261102/README.md), section 3). The window rule of section 2 applies.

## The cross-feeding run crashed

The job ended with a segmentation fault (exit 139, signal 11) after 30.2 h of its 48 h limit. The last
progress report was at 2550 of 3000 simulated minutes. There was no error message, and memory use
was 14.2 GB of 256 GB. The snapshots up to 2550 min are complete and are used above.

**What the snapshots show** ([diagnostics/edge.txt](diagnostics/edge.txt), script
[diagnostics/edge.py](diagnostics/edge.py)). The domain is 200 × 200 µm (2D, 1.25 µm voxels), small
for a population that grows by a third every three simulated hours. The colony reaches the domain edge
between 2100 and 2400 min:

| Simulated time | Cells | Cells outside the domain | Cells within 2 µm of the edge | Max cells per voxel |
|---:|---:|---:|---:|---:|
| 2100 min | 15 177 | 0 | 0 | 5 |
| 2400 min | 24 039 | 42 | 132 | 6 |
| 2550 min | 29 742 | 261 | 506 | 9 |

The bacterial colony (domain 1000 × 1000 µm, colony 430 µm across at the end) and the acetate switch never reached
their domain edges, and they did not crash. Cells pushed out of the domain are flagged `is_out_of_domain`
and kept, with no BioFVM voxel (index −1). The dFBA demand table and the intracellular update skip them.

**What is not known.** The cause of the crash was not identified. Cells leaving the domain are the
most visible difference from the runs that completed, but this was not reproduced or traced. The
benchmark does not change the engine, so this run was not repeated with a debug build. A reproduction
needs a build with debug symbols and core dumps enabled. It could be made cheaper with a smaller
domain or a larger initial population, so that the edge is reached sooner.

**For the developers:** in this run (one run, seed 50, 112 threads), the shipped `crossfeeding`
configuration did not reach its 3000-minute end on `c59daa81`. Either the domain should be enlarged so the colony stays inside it, or the
behaviour of out-of-domain cells should be checked in the code paths that index voxels.

## Files

| Path | Contents |
|---|---|
| [tables/apps.csv](tables/apps.csv) | One row per run: Slurm state, exit code, completed, simulated and reached time, timesteps, cell counts, wall time and its source, peak memory, cost per simulated hour and per cell-step, binary and config SHA-256 |
| [analysis.json](analysis.json) | Analysis script SHA-256 and the SHA-256 of every copied evidence file |
| `data/<run>/` | `run-info.txt` (binary and config SHA-256, host, start, end, exit), `time.txt` (GNU time), `lscpu.txt`, `stderr.log`, last 60 lines of stdout |
| [workflow/](workflow/) | Build script and log, compiler version, binary table, launcher, job list |
| [diagnostics/](diagnostics/) | Domain-edge check of the cross-feeding, bacterial-colony and acetate-switch snapshots |

Notes:
- `config_sha256` equals `shipped_config_sha256` for the shipped runs. The 56-thread runs differ only in `omp_num_threads`.
- Cell-steps integrate the snapshot cell counts over time (trapezoid rule) and divide by the diffusion dt.
- For the crashed run, wall time and cost per simulated hour include the roughly 56 min after the last snapshot.
- Raw outputs (snapshots, SVG) stay in `benchmarks/workspaces/apps-20261109/runs/` on MareNostrum 5 ([DATA.md](../../../DATA.md)).
