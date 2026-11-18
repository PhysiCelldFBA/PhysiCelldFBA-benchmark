---
title: "Supplementary Material: Numerical robustness, computational cost and scalability of PhysiCelldFBA"
subtitle: "Benchmark scenarios, metrics and results"
---

# Contents

- S1. Overview: questions and where they are answered
- S2. General methods: software, hardware, models, solver and measurements
- S3. Numerical robustness of the spatial coupling
- S4. Computational cost and scalability
- S5. Standard FBA versus parsimonious FBA in the cancer model
- S6. Practical guidance for choosing timesteps and problem sizes
- S7. Reproducibility, software availability and data archive
- S8. Scope of the benchmark

# S1. Overview: questions and where they are answered

PhysiCelldFBA couples an agent-based multicellular simulator (PhysiCell, with the BioFVM diffusion
solver) to a flux balance analysis (FBA) problem solved in every cell. Each cell takes up and secretes
metabolites through the voxel of the diffusion mesh that contains it. Its metabolic model is
re-solved every intracellular timestep, which may be a multiple k of the diffusion timestep. This
supplement reports a benchmark of that coupling. It asks two groups of questions.

**Numerical robustness.** Do the results depend on the order in which cells are updated, on the number of
CPU threads, on the number of cells that share a voxel, on the voxel size, or on the diffusion and
intracellular timesteps?

**Computational cost.** How do wall time and memory scale with the number of cells, the size of the
genome-scale model (GEM), the number of diffusing metabolite fields and the number of CPU threads? What
does metabolism add to a PhysiCell simulation? How many LPs per second can be solved, and which problem
sizes are feasible? What do the published applications cost?

| Question | Scenarios | Section | Tables and figures |
|---|---|---|---|
| Serial versus parallel execution; cell-update order | Shared voxel; mesh occupancy; unit tests | S3.1–S3.3 | Tables S3–S5, Figure S1 |
| Several cells exchanging with the same voxel | Shared voxel; mesh occupancy | S3.1–S3.2 | Tables S3–S4, Figure S1 |
| Voxel size | Mesh occupancy; unit tests (dx × dt); timestep scenarios A1–A4 | S3.2–S3.4 | Tables S4–S7, Figures S1–S3 |
| Diffusion and intracellular timesteps: accuracy | Timestep accuracy A1–A4 at two diffusion timesteps; growth controls | S3.4–S3.5 | Tables S6–S8, Figures S2, S3, S5 |
| Diffusion and intracellular timesteps: cost | Timestep cost, three models, 1 and 56 threads | S4.7 | Table S11, Figure S4 |
| Scaling with cell number, GEM size, fields and threads; memory | Performance and scaling | S4.2–S4.5 | Table S9, Figure S7 |
| PhysiCell baseline (overhead of the add-on) | Performance and scaling, three variants | S4.3 | Figure S7c–d |
| Solver-call rate and LP size | Performance and scaling | S2.2, S4.6 | Tables S1, S10 |
| Hardware, compiler, solver settings | All | S2 | Table S2 |
| Feasible problem sizes | Performance and scaling | S4.8 | Table S12 |
| Cost of the published applications | Six sample projects, as distributed | S4.9 | Table S13 |
| FBA versus parsimonious FBA (pFBA) | Cancer model, single cell and 240-cell application | S5 | Tables S14–S15, Figure S6 |
| Reproducibility | All | S7 | — |

In total the benchmark comprises 1,058 simulations (Table S0), all run on the same PhysiCelldFBA version and
the same hardware. Every attempted run is reported. Runs with diagnostic flags (for example a negative
concentration or a non-optimal LP) are retained and discussed.

**Table S0. Studies and number of simulations.**

| Study | Simulations | Section |
|---|---:|---|
| Shared voxel (eight cells in one voxel) | 60 | S3.1 |
| Mesh occupancy (eight cells on four meshes) | 240 | S3.2 |
| PhysiCelldFBA unit-test suite | 3 test programs | S3.3 |
| Timestep accuracy (A1–A4, two diffusion timesteps) | 58 | S3.4 |
| Growth-condition controls | 23 | S3.5 |
| Performance and scaling (three variants) | 405 | S4.2–S4.5 |
| Timestep cost (two diffusion timesteps) | 252 | S4.7 |
| Published applications, as distributed | 12 | S4.9 |
| Standard FBA versus pFBA | 8 | S5 |

# S2. General methods

## S2.1 Software

All simulations used **PhysiCelldFBA commit `c59daa81`** (based on PhysiCell 1.14.2). The performance
baseline is **PhysiCell 1.14.2, commit `49d7cc54`** (MathCancer/PhysiCell), built from its template
project. The exact build, run and analysis code is in the benchmark repository (Section S7).

Two kinds of builds were used:

- **Instrumented builds** for the controlled studies (S3.1, S3.2, S3.4, S3.5, S4.2–S4.7, S5). A compile-time
  instrumentation layer (`-DPHYSICELL_BENCHMARK`) records phase timings, solver calls and simplex
  iterations, LP sizes and statuses, per-step substrate amounts and an exchange ledger. It only reads the
  simulation state and does not alter the computation. A benchmark driver replaces each project's `main` so that cells can be placed at
  prescribed positions, and movement, division and death can be switched off when a study needs a fixed
  geometry. These controls are listed for each study below.
- **Stock builds**, exactly as distributed, for the unit tests (S3.3) and the published applications (S4.9).

## S2.2 Metabolic models

Three models span two orders of magnitude in size (Table S1). E. coli core and MCF7 core are the models of the
bacterial and cancer applications. iML1515 is a genome-scale E. coli model used here as the large-model case.

**Table S1. Metabolic models and the LP solved per cell.**

| Model | Source in the distribution | Reactions | Species in the SBML | LP rows (metabolites) | LP columns (reactions) | Nonzeros |
|---|---|---:|---:|---:|---:|---:|
| E. coli core | `bacterial_colony/config/Ecoli_core.xml` | 95 | 72 | 72 | 95 | 360 |
| MCF7 core | `cancer_core_metabolism/config/MCF7_Zielinski_2017_core_trimmed.sbml` | 374 | 360 | 360 | 374 | 1,566 |
| iML1515 | benchmark asset `iML1515.xml` | 2,712 | 1,877 | 1,877 | 2,712 | 10,575 |

## S2.3 Hardware and execution environment

**Table S2. Hardware, compiler and solver settings.**

| Item | Setting |
|---|---|
| Machine | MareNostrum 5, general-purpose partition (Barcelona Supercomputing Center) |
| Node | 2 × Intel Xeon Platinum 8480+ (Sapphire Rapids), 2 × 56 cores, 256 GB RAM; one node per job, used exclusively |
| Operating system | Red Hat Enterprise Linux 9.6 (kernel 5.14), glibc 2.34 |
| Compiler | GCC 11.5.0, `-O3 -march=native -fomit-frame-pointer -mfpmath=both -fopenmp -m64 -std=c++11` |
| Libraries | Clp 1.17.10, CoinUtils 2.11.12, libSBML 5.20.4 |
| Parallelism | OpenMP, one thread per physical core (`--hint=nomultithread`), `OMP_PROC_BIND=spread`, `OMP_PLACES=cores`, `OMP_DYNAMIC=FALSE`; BLAS single-threaded |
| LP solver | Clp dual simplex; the first solve of each cell from scratch, later solves warm-started from the cell's previous basis; primal and dual feasibility tolerances 10⁻⁷ |
| pFBA second stage | Clp primal simplex; growth fixed at 100% of the stage-one optimum; on failure the cell keeps its stage-one fluxes |
| Analysis | Python 3.12.1, NumPy, SciPy, Matplotlib (versions in the archive) |

## S2.4 Media

Each model was run in the medium of the application it comes from, with that application's supply at the domain
boundaries.
Where a study needed sustained growth, a "fed" variant kept the same composition and supplied it at the
boundaries:

- E. coli core: the bacterial-colony medium (glucose 4 mM, oxygen 5 mM; oxygen supplied at the x and y boundaries);
- MCF7 core: the 23-field medium of the cancer application (glucose 0.5 mM, 17 amino acids and other nutrients at 1 mM).
  In the native configuration it is supplied as a gradient from one face. In the fed variant it is uniform initially
  and at the boundaries, with oxygen at 2 mM;
- iML1515: glucose 8 mM and oxygen 5 mM, initially and at the boundaries.

Concentrations are in mM. Exchange fluxes follow PhysiCelldFBA's convention: uptake bounds are set from
Michaelis–Menten kinetics of the local concentration, and are capped so that one cell (or all cells in a
voxel) cannot take up more over one intracellular timestep than the voxel contains.

## S2.5 Measurements and metrics

- **Wall time** of the whole process (GNU `time`), and **simulation-loop time**, which excludes start-up (model loading)
  and initial output. Loop time is split into intracellular (LP), exchange, diffusion, mechanics, phenotype
  and output phases.
- **Peak memory**: maximum resident set size of the process.
- **Solver statistics**: LP solves, solver time, simplex iterations, and LP status per solve (optimal,
  infeasible, other).
- **Exchange ledger**: at every diffusion step, the change in each substrate's total domain amount is compared
  with the sum of the cells' exchanges. Residuals are reported in absolute and relative terms.
- **Minimum concentration** of every field over all voxels at every step. Values are reported signed, never clipped.
- **Intracellular updates** per cell, due and performed.
- **Biomass**: per-cell and total dry mass over time.
- **Speed-up** of a configuration relative to a reference (1 thread, or k = 1), and **parallel efficiency**
  (speed-up divided by threads).
- **Relative error** of a quantity against the k = 1 run of the same scenario, either at the end or as the maximum over
  the trajectory, sampled every simulated minute.

## S2.6 Execution protocol

- Every run had an exclusive node. A study's repeats of one configuration ran in the same Slurm job, on one node.
- Run order within a study was randomised with a recorded seed.
- Each run's inputs were materialised as an immutable bundle containing the configuration, the SBML, the cell
  positions and a copy of the executable. A SHA-256 manifest records each bundle.
- The simulation random seed was 50 in all controlled studies. Cell-update orders were set by separate seeds (S3.1).
- Hardware, loaded modules, CPU affinity and thread environment were recorded for every run. The requested thread
  count was verified from the telemetry.
- Timing studies used three repeats per configuration and report the median.

# S3. Numerical robustness of the spatial coupling

## S3.1 Several cells exchanging with one voxel: threads and update order

**Question.** When several cells take up the same substrate from one voxel, is the result independent of the number of
threads and of the order in which cells are processed?

**Scenario.** PhysiCelldFBA's voxel-sharing test: eight E. coli core cells placed at the same point, so that all of
them share one 1.6 µm voxel (domain 16 µm in each direction). Initial glucose is 0.165 mM, enough for about two
diffusion steps, so the cells compete for the voxel's content; oxygen is not limiting. The simulation covers 0.1
simulated minutes with diffusion and intracellular timesteps of 0.01 min (10 steps, 80 intracellular updates in
total). Positions and population are fixed; biomass growth is on.

**Design.** 1, 2, 4 and 8 OpenMP threads × 5 cell-order seeds (11, 23, 37, 51, 71) × 3 repeats = 60 runs. Each
order seed permutes the list of cells once, at initialisation. The permutation is recorded. Each parallel run
is compared with the serial run of the same seed and repeat. Repeats with the same seed measure the variability
caused by thread scheduling.

**Metrics.** Intracellular updates performed; minimum glucose over time; final dry mass of every cell; exchange
ledger; LP status.

**Results** (Table S3, Figure S1a).

- **All 60 runs are bitwise identical**: the same 80 updates, the same glucose trajectory and the same final dry
  mass of every cell, for every thread count, order seed and repeat.
- The voxel is emptied within the second diffusion step (Figure S1a). Every run reports the same minimum
  glucose, −3.78 × 10⁻⁶ mM. This is 2.3 × 10⁻⁵ of the initial concentration and comes from the operator
  splitting. The uptake limit is computed from each cell's dry mass at the start of the step, while the exchange
  is applied with the mass after the growth step. The difference is of order c·μ·Δt.
- The exchange ledger closes in every run, and all LPs are optimal.

**Table S3. Eight cells in one voxel (60 runs).**

| Threads | Runs | Updates per run | Final total dry mass (pg) | Minimum glucose (mM) | Difference from the matched serial run |
|---:|---:|---:|---:|---:|---|
| 1 | 15 | 80 | 2.704062 | −3.78 × 10⁻⁶ | reference |
| 2 | 15 | 80 | 2.704062 | −3.78 × 10⁻⁶ | 0 (bitwise) |
| 4 | 15 | 80 | 2.704062 | −3.78 × 10⁻⁶ | 0 (bitwise) |
| 8 | 15 | 80 | 2.704062 | −3.78 × 10⁻⁶ | 0 (bitwise) |

The eight cells here are identical, so the update order cannot change the outcome. The unit-test suite (S3.3)
repeats the order test with heterogeneous cells.

## S3.2 Voxel occupancy and voxel size

**Question.** Does it matter whether cells share a voxel or each have their own? Does voxel size matter at a fixed
cell geometry?

**Scenario.** The same eight cells, now at eight distinct fixed positions (x = −7 or −5 µm, y = −7 or −3 µm,
z = −7 or 1 µm) in the same 16 µm domain. Four meshes change only the voxel size, and with it the number of
cells per occupied voxel. Glucose diffusion is disabled, so each voxel's content is the only glucose its cells
can use. Everything else is as in S3.1.

**Design.** 4 meshes × 4 thread counts × 5 order seeds × 3 repeats = 240 runs.

**Results** (Table S4, Figure S1b).

- **On every mesh, all 60 runs are bitwise identical**, across threads, order seeds and repeats.
- The voxel size changes the result, as expected physically. A smaller voxel holds less glucose per cell: at 0.1 min
  the minimum glucose is 0.158 mM with 16 µm voxels and 0.058 mM with 4 µm voxels. With 2 µm voxels, each cell
  empties its own voxel by 0.05 min. Total final dry mass changes by at most 0.07% between meshes.
- On the 2 µm mesh the minimum reaches −1.19 × 10⁻⁶ mM, the same first-order splitting effect as in S3.1.
- Exchange-ledger residuals stay below 4 × 10⁻¹³ mM·µm³, at the level of floating-point rounding, and all LPs are
  optimal on every mesh.

**Table S4. Eight separated cells on four meshes (240 runs; values identical within each mesh).**

| Voxel edge (µm) | Voxels | Cells per occupied voxel | Runs | Minimum glucose at 0.1 min (mM) | Final total dry mass (pg) | Max ledger residual (mM·µm³) | Difference parallel − serial |
|---:|---:|---:|---:|---:|---:|---:|---|
| 16 | 1 | 8 | 60 | 0.158 | 2.706942 | 3.9 × 10⁻¹³ | 0 |
| 8 | 8 | 4 | 60 | 0.137 | 2.706919 | 5.6 × 10⁻¹⁴ | 0 |
| 4 | 64 | 2 | 60 | 0.0579 | 2.706759 | 1.7 × 10⁻¹³ | 0 |
| 2 | 512 | 1 | 60 | −1.19 × 10⁻⁶ | 2.704968 | 2.9 × 10⁻¹³ | 0 |

![**Figure S1. Glucose in shared and separate voxels.** (a) Minimum glucose concentration over time for eight E. coli
core cells sharing one 1.6 µm voxel: all 60 runs (1, 2, 4 and 8 threads; five update-order seeds; three repeats)
overlap exactly. (b) Eight separated cells on meshes with 16, 8, 4 and 2 µm voxels (8, 4, 2 and 1 cells per
occupied voxel). Thick solid lines: serial runs; thin dashed lines: 2, 4 and 8 threads. On each mesh all 60 runs
coincide.](figures/FigS1.png)

## S3.3 PhysiCelldFBA unit-test suite

**Question.** Do the engine's own correctness tests pass on the benchmarked version, including heterogeneous cells,
varied update orders, parallel execution, and a range of voxel sizes and timesteps?

**Scenario.** The `dfba_unit_test` project distributed with PhysiCelldFBA, stock build, run unchanged with its two
test scripts.

**Table S5. Unit tests on PhysiCelldFBA `c59daa81`.**

| Test | What it checks | Result |
|---|---|---|
| Voxel sharing (`run_voxel_sharing_test.sh`) | 1, 4 and 8 cells, and a mixed layout, in one voxel. Concentrations stay non-negative within 10⁻⁴ mM, and a cell type that cannot take up glucose does not dilute the others' uptake | 5/5 pass; minimum glucose −3.8 × 10⁻⁶ to −7.6 × 10⁻⁶ mM |
| Update order and threads (same script) | 12 cells of four different types in one voxel, created in 5 different orders and run on 1 and 4 threads; each run compared with the 1-thread run in the original order (tolerance 10⁻⁹) | 10/10 agree; largest difference 1.1 × 10⁻¹⁵ |
| Voxel size and timestep (`run_dxdt_test.sh`) | Voxel sizes 0.8, 1.6 and 3.2 µm × diffusion timesteps 0.005, 0.01 and 0.02 min, and intracellular timesteps of 2 and 10 diffusion steps. Checks: results independent of dx and dt while the uptake limit is inactive; exact voxel depletion when it acts; exchange ledger; carbon and elemental balances | 118/118 pass |

With heterogeneous cells the order of floating-point summation changes with the update order, so results agree to
rounding level (10⁻¹⁵) rather than bitwise. This is the expected behaviour of a correct shared-voxel exchange.

## S3.4 Diffusion and intracellular timesteps: accuracy

**Question.** How much accuracy is lost when the metabolic model is solved only every k diffusion steps
(intracellular timestep = k × diffusion timestep)? Does the answer depend on the diffusion timestep, the model and
the voxel size?

**Scenarios** (Table S6). Four scenarios cover both models of the published applications, in their applications'
voxel sizes, with one and with sixteen cells. All are serial, with fixed positions and population and biomass growth
on, for 240 simulated minutes. Because cells do not divide, their dry mass keeps growing (E. coli by 12–28-fold),
which makes the late E. coli conditions progressively more demanding.

**Table S6. Timestep-accuracy scenarios.**

| Scenario | Model | Cells | Voxel | Domain | Medium |
|---|---|---:|---|---|---|
| A1 | E. coli core | 1 | 2 µm | 16 × 16 × 16 µm | Closed: glucose 10 mM, not replenished; oxygen not limiting |
| A2 | E. coli core | 16, one per voxel | 2 µm | 8 × 8 × 2 µm | Glucose 4 mM, not replenished; oxygen 5 mM, supplied at the x and y boundaries |
| A3 | MCF7 core | 1 | 15 µm | 360 × 120 × 30 µm | Native application medium: 23 fields supplied as a gradient from one face |
| A4 | MCF7 core | 16, one per voxel | 15 µm | 60 × 30 × 30 µm | Fed: 23 fields, uniform initially and at the boundaries (glucose 0.5 mM, O₂ 2 mM) |

**Design.** k = 1, 2, 5, 10, 20, 50 and 100 at diffusion timesteps of 0.01 min (the PhysiCell default) and 0.001
min. The intracellular timestep therefore ranges from 0.01 to 1 min and from 0.001 to 0.1 min. Each scenario's k = 1
run is the reference. To check that the reference itself has converged, A3 was also run at k = 1 with half the
diffusion timestep. In total 4 × 7 × 2 + 2 = 58 runs.

**Metrics.** Final and maximum relative error of the total dry mass against k = 1; relative error of total glucose
(and oxygen) uptake; minimum concentration; exchange ledger at every step; LP status of every update.

**Results** (Table S7, Figures S2 and S3).

- **Mass balance holds at every k.** All 58 runs pass the exchange ledger at every step.
- **The error is governed by the length of the intracellular window, not by k.** Plotted against the window
  length, the errors at the two diffusion timesteps fall on nearly the same curve (Figure S3). The MCF7 scenarios
  give identical errors for equal windows: for example 2.05 × 10⁻⁵ for a 0.1-min window, whether it is k = 10 at
  0.01 min or k = 100 at 0.001 min. In the E. coli scenarios the errors for equal windows agree within about a factor
  of two.
- **Cancer cells in 15 µm voxels are insensitive to the window up to 0.2 min.** A4 stays below 2.3 × 10⁻⁴ for every
  window up to 1 min. A3 stays below 4.3 × 10⁻⁵ up to 0.2 min. At 0.5 min its biomass error is 2.4%, and at 1 min
  every LP is infeasible: the uptake allowed over the window cannot meet the model's maintenance requirement.
- **E. coli in 2 µm voxels needs short windows.** Windows of 0.01 min or less keep A2 within 5 × 10⁻⁹. A2 errors
  rise to 5.5–11.6% at 0.02 min and 58% at 0.1 min. In A1 the final biomass is within 10⁻⁴ for windows up to 0.01 min, while
  the trajectory deviates by up to 1.9% during depletion. In the closed pool of A1 a longer window delays uptake, but
  the cell eventually consumes the same glucose. The trajectory error therefore exceeds the final error.
- **Reference convergence.** Halving the diffusion timestep at k = 1 (A3) changes final biomass by 5 × 10⁻⁶ at 0.01 min
  and 5 × 10⁻⁷ at 0.001 min, and glucose uptake by 0.33% and 0.033%.
- **Minimum concentrations.** All MCF7 runs and A2 stay non-negative. In A1 at 0.001 min, k = 1, 2 and 5, glucose
  reaches −1.25 × 10⁻⁴, −5.2 × 10⁻⁵ and −1.9 × 10⁻⁵ mM at the moment of depletion. That is at most 1.3 × 10⁻⁵ of the
  initial 10 mM, within the first-order splitting bound $2\,\mu_{\max}\,\Delta t\,c_0 \approx 2.7 \times 10^{-4}$ mM.

**Table S7. Relative biomass error against k = 1: final value, with the maximum over the trajectory in brackets
where it differs.**

| k | A1, dt 0.01 | A2, dt 0.01 | A3, dt 0.01 | A4, dt 0.01 | A1, dt 0.001 | A2, dt 0.001 | A3, dt 0.001 | A4, dt 0.001 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | −0.50% (2.0%) | −11.6% | 4 × 10⁻¹⁰ (2.3 × 10⁻⁶) | 4 × 10⁻¹⁰ (2.3 × 10⁻⁶) | −5 × 10⁻⁶ (0.18%) | 5 × 10⁻¹⁰ | −6 × 10⁻⁹ | −6 × 10⁻⁹ |
| 5 | −3.6% (7.6%) | −37.9% | 2 × 10⁻⁹ (9.1 × 10⁻⁶) | 2 × 10⁻⁹ (9.1 × 10⁻⁶) | −2 × 10⁻⁵ (0.80%) | 2 × 10⁻⁹ | 6 × 10⁻⁹ | 6 × 10⁻⁹ |
| 10 | −10.0% (15.3%) | −58.1% | 4 × 10⁻⁹ (2.1 × 10⁻⁵) | 4 × 10⁻⁹ (2.1 × 10⁻⁵) | −1.0 × 10⁻⁴ (1.9%) | 5 × 10⁻⁹ | 6 × 10⁻⁹ | 6 × 10⁻⁹ |
| 20 | −21.4% (26.8%) | −73.9% | 9 × 10⁻⁹ (4.3 × 10⁻⁵) | 9 × 10⁻⁹ (4.3 × 10⁻⁵) | −0.18% (3.9%) | −5.5% | 6 × 10⁻⁹ (2.3 × 10⁻⁶) | 6 × 10⁻⁹ (2.3 × 10⁻⁶) |
| 50 | −42.3% (46.3%) | −87.0% | −2.4% | 2 × 10⁻⁸ (1.1 × 10⁻⁴) | −2.6% (9.5%) | −35.0% | 6 × 10⁻⁹ (9.1 × 10⁻⁶) | 6 × 10⁻⁹ (9.1 × 10⁻⁶) |
| 100 | −58.7% (61.4%) | −92.1% | −5.3%, all LPs infeasible | 4 × 10⁻⁸ (2.3 × 10⁻⁴) | −9.0% (17.3%) | −57.8% | 7 × 10⁻⁹ (2.1 × 10⁻⁵) | 7 × 10⁻⁹ (2.1 × 10⁻⁵) |

![**Figure S2. Accuracy of running the metabolism every k diffusion steps.** Maximum relative error of total dry mass
over 240 min (a, b) and relative error of total glucose uptake (c, d) against k, for scenarios A1–A4, at diffusion
timesteps of 0.01 min (a, c) and 0.001 min (b, d). A3 (open triangles, dashed) and A4 coincide wherever neither is
limited by its voxel content. Ringed point: every LP infeasible (A3, k = 100, 1-min window). Values below 10⁻¹² are
plotted at 10⁻¹².](figures/FigS2.png)

![**Figure S3. The error depends on the window length.** Data of Figure S2a–b plotted against the intracellular timestep
(window length) for each scenario. At equal windows, the two diffusion timesteps give the same error (MCF7, A3–A4)
or errors within a factor of two (E. coli, A1–A2).](figures/FigS3.png)

**Interpretation: the window-demand criterion.** Over one intracellular window the uptake bound of a cell is the
smaller of its kinetic uptake and the content of its voxel. The voxel content is not refilled by diffusion until
the next window. The kinetic demand over a window relative to the voxel content is

$$D = \frac{V_{\max}\, m_{\mathrm{cell}}\, \Delta t_{\mathrm{intra}}}{c\, V_{\mathrm{voxel}}},$$

with $V_{\max}$ the maximal specific uptake rate, $m_{\mathrm{cell}}$ the cell's dry mass, $\Delta t_{\mathrm{intra}}$ the
intracellular timestep, $c$ the local concentration and $V_{\mathrm{voxel}}$ the voxel volume. While D < 1 for every consumed substrate, a longer window changes only how often the fluxes are
recomputed, and the error stays small (A3, A4, and A1–A2 at short windows). When D exceeds 1, the uptake over the
window is limited by the voxel content instead of the kinetics, and growth falls behind the k = 1 reference. This
happens for E. coli in 2 µm voxels (small voxel, high specific uptake, cells growing without division) and for a
single cancer cell in a gradient at windows of 0.5–1 min. The criterion depends on the model, the cell mass, the
voxel size and the local concentration, so no single k is safe for all applications. Users can check
$\Delta t_{\mathrm{intra}} < c\, V_{\mathrm{voxel}} / (V_{\max}\, m_{\mathrm{cell}})$ for each consumed substrate before
choosing a window.

## S3.5 Growth-condition controls

**Question.** Does each model grow in its medium with all LPs optimal and mass balance satisfied, and how sensitive
is short-term growth to the intracellular timestep?

**Scenarios.** 23 short serial controls (10 simulated minutes, diffusion timestep 0.01 min): single cells and 16-cell
fixed-volume populations of the three models in their media (S2.4), at intracellular timesteps of 0.01, 0.1 and 1
min. Fixed-volume populations keep cell volume constant and test LP feasibility and positive growth rates of all
cells at every update. MCF7 core is also tested with pFBA and in two alternative supplies (oxygen at 2 mM as a
gradient, and the uniform fed medium).

**Metrics.** Biomass change; LP status of every update; growth rate of every cell; minimum concentrations; exchange
ledger.

**Results** (Table S8, Figure S5).

- 22 of 23 controls have all LPs optimal, positive growth, non-negative concentrations and a closed exchange ledger.
  The exception is the single MCF7 cell in the native gradient at a 1-min window: all 10 of its LPs are infeasible.
- At windows of 0.01 min every model grows at its expected rate: E. coli core 14.9% in 10 min, iML1515 12.3%, MCF7 core 0.23%.
  pFBA gives the same MCF7 growth as FBA.
- Longer windows reduce growth wherever D > 1 (S3.4): E. coli core to 5.3% at 1 min; iML1515 to 7.0% at 0.1 min and
  0.09% at 1 min. MCF7 growth is unchanged at 0.1 min, and at 1 min with oxygen at 2 mM.

**Table S8. Growth-condition controls (10 min).**

| Model, medium | Cells | Intracellular dt (min) | Dry-mass change | LPs not optimal | Ledger | All checks |
|---|---|---|---:|---:|---|---|
| E. coli core, colony medium | 1 | 0.01 / 0.1 / 1 | 14.86% / 14.86% / 5.32% | 0 | closed | yes |
| E. coli core, colony medium | 16, fixed volume | 0.01 / 1 | volume fixed | 0 | closed | yes |
| iML1515, fed | 1 | 0.01 / 0.1 / 1 | 12.27% / 7.01% / 0.09% | 0 | closed | yes |
| iML1515, batch | 1 | 0.01 | 12.27% | 0 | closed | yes |
| iML1515, fed | 16, fixed volume | 0.01 / 1 | volume fixed | 0 | closed | yes |
| MCF7 core, native gradient | 1 | 0.01 / 0.1 / 1 | 0.228% / 0.228% / 0 | 0 / 0 / 10 of 10 | closed | yes / yes / no |
| MCF7 core, native gradient, pFBA | 1 | 0.01 | 0.228% | 0 | closed | yes |
| MCF7 core, O₂ 2 mM gradient | 1 | 0.01 / 0.1 / 1 | 0.228% (all) | 0 | closed | yes |
| MCF7 core, uniform fed | 1 | 0.01 / 0.1 / 1 | 0.228% (all) | 0 | closed | yes |
| MCF7 core, uniform fed | 16, fixed volume | 0.01 / 1 | volume fixed | 0 | closed | yes |

![**Figure S5. Single-cell growth in each model's medium.** Dry-mass change over 10 simulated minutes at intracellular
timesteps of 0.01, 0.1 and 1 min (diffusion timestep 0.01 min). (a) E. coli core in the bacterial-colony medium.
(b) iML1515 in the fed medium, and in the batch medium at 0.01 min. (c) MCF7 core in the native gradient medium, with
FBA at three windows and pFBA at 0.01 min. At 1 min every MCF7 LP is infeasible and the cell does not grow. The
staircase in (a) at 1 min shows growth applied once per window.](figures/FigS5.png)

# S4. Computational cost and scalability

## S4.1 Workloads and variants

**Workload.** A controlled lattice workload per model: N cells (100, 1,000 or 10,000), one per voxel, at fixed
positions, with fixed volume and population, in the model's fed medium and with the voxel size of its template
(2 µm for E. coli core and 15 µm for MCF7 core, as in their applications; 1 µm for iML1515, whose configuration derives
from the acetate-switch project). The domain holds exactly one voxel per cell (for 1,000 cells: 25 × 40 × 1 voxels
for the bacterial models, 10 × 10 × 10 for MCF7 core). Diffusion timestep 0.01 min,
k = 1, 10 simulated minutes (1,000 steps), output limited to the final state. Unless stated otherwise, every model
carries 23 diffusing fields, the minimum of the MCF7 medium, so that the three models solve the same transport problem.

**Variants.** The same workload was run in three builds:

- **PhysiCelldFBA** with metabolism;
- **PhysiCelldFBA without metabolism**: the same executable, with the intracellular model removed from the input;
- **PhysiCell 1.14.2** (template project) with the core part of the same instrumentation layer.

**Design.** 100, 1,000 and 10,000 cells at 1 and 56 threads; 1, 2, 4, 8, 16, 28, 56 and 112 threads at 1,000 cells;
4/5, 8, 16, 23 and 32 fields at 1,000 cells and 56 threads. 135 configurations × 3 repeats = 405 runs, all
completed at the requested thread count. Repeat spread (maximum − minimum over the median) is at most 10% for loops of
10 s or more, and up to 25% for loops under 2 s. Times are the simulation loop (S2.5). Model loading adds
about 0.15 s per cell for iML1515 and is negligible for the core models.

## S4.2 Scaling with cell number and model size

**Results** (Table S9, Figure S7a).

- **Cost is close to linear in the number of cells.** It is dominated by one LP per cell and step. From 100 to 10,000 cells,
  the cost per cell and step rises by 12–17% for MCF7 core and iML1515, and by 58% for E. coli core, whose cheap
  LPs leave a larger share to the rest of the step.
- **Cost grows with the size of the model.** On one thread a cell-step costs 46 µs (E. coli core), 257 µs (MCF7 core)
  and 1,673 µs (iML1515) at 1,000 cells. Compared with the same simulation without metabolism, one step costs 25×,
  455× and 2,350× more.

**Table S9. Cost and scaling of the lattice workload (median of 3 repeats).**

| Model | µs per cell and step, 1 thread (100 / 1,000 / 10,000 cells) | Loop time, 1,000 cells, 1 thread | Speed-up at 1,000 cells: 8 / 28 / 56 / 112 threads | Speed-up at 10,000 cells, 56 threads | Peak memory at 10,000 cells |
|---|---|---:|---|---:|---:|
| E. coli core | 35 / 46 / 55 | 45.6 s | 8.2 / 20.2 / 21.3 / 19.9 | 23.8× | 1.2 GB |
| MCF7 core | 242 / 257 / 272 | 257 s | 7.8 / 23.8 / 40.6 / 59.3 | 31.4× | 4.0 GB |
| iML1515 | 1,578 / 1,673 / 1,849 | 1,675 s | 7.6 / 24.0 / 38.0 / 42.5 | 33.8× | 23.4 GB |

## S4.3 Scaling with threads, and the PhysiCell baseline

**Results** (Table S9, Figure S7b–d).

- **The LP work parallelises well.** For MCF7 core and iML1515 the speed-up is close to ideal up to 28 threads
  (efficiency 85–86%). It reaches 38–41× at 56 threads and 42–59× at 112 threads, where the two sockets are used.
- **With cheap LPs, the rest of the step limits the speed-up.** E. coli core levels off at about 20× from 28
  threads on. The non-LP part of the step (diffusion, mechanics, output bookkeeping) then dominates.
- **The add-on adds no measurable cost without metabolism.** PhysiCelldFBA without intracellular models runs within
  0.90–1.08× of PhysiCell 1.14.2 at every one of the 45 configurations per model (Figure S7d). The two baselines gain
  only 2–5× from threads, because their small workloads are dominated by threading overhead (Figure S7b–c).

## S4.4 Scaling with the number of metabolite fields

At 1,000 cells and 56 threads, the loop time does not change measurably with the number of diffusing fields
(Figure S7e): 1.7–2.1 s for E. coli core (5–32 fields), 6.3–6.4 s for MCF7 core (23 and 32 fields; its medium needs 23)
and 43.5–44.9 s for iML1515 (4–32 fields). In these workloads (one cell per voxel, 1,000 voxels) the per-field diffusion
cost is small compared with the LPs. Larger domains with many empty voxels would increase the diffusion share, as in
PhysiCell itself.

## S4.5 Memory

Peak memory grows linearly with the number of cells and with the model size (Figure S7f): about 0.12 GB (E. coli core),
0.4 GB (MCF7 core) and 2.3 GB (iML1515) per 1,000 cells. Each cell holds its own LP.

![**Figure S7. Performance and scaling.** Lattice workload, one cell per voxel, 23 fields, k = 1, 10 simulated
minutes, median of 3 repeats. (a) Simulation-loop time per cell and step against cell count, on 1 thread (filled,
solid) and 56 threads (open, dashed). (b) Speed-up against threads at 1,000 cells. Grey: the MCF7 workload without
metabolism and in PhysiCell 1.14.2. (c) Loop time against threads at 1,000 cells for PhysiCelldFBA (solid),
PhysiCelldFBA without metabolism (dashed) and PhysiCell 1.14.2 (dotted). The last two overlap. (d) Loop-time ratio of
PhysiCelldFBA without metabolism to PhysiCell 1.14.2, all 135 configurations. (e) Loop time against the number of
diffusing fields, 1,000 cells, 56 threads. (f) Peak memory against cell count.](figures/FigS7.png)

## S4.6 Solver cost and solver-call rate

**Table S10. LP cost per cell update** (1,000 cells, 1 thread, k = 1, 10 min: 10⁶ warm-started solves per run; median of 3 runs).

| Model | µs per warm-started solve | Simplex iterations per solve | ms per first (cold) solve | Solves per second, 1 thread |
|---|---:|---:|---:|---:|
| E. coli core | 35.7 | 0.004 | 0.56 | 28,000 |
| MCF7 core | 210.9 | 0.023 | 1.98 | 4,700 |
| iML1515 | 1,518 | 0.46 | 25.9 | 660 |

At k = 1 most warm-started solves need no pivot, because the bounds move little between consecutive steps. The cost
of a solve is then mostly updating the bounds and verifying the basis. On 56 threads, the 10⁶ solves of the 1,000-cell
workload, together with all other work of the loop, take 2.1 s (E. coli core), 6.3 s (MCF7 core) and 44 s (iML1515):
an overall rate of about 470,000, 160,000 and 23,000 cell updates per second.

## S4.7 Cost of the intracellular timestep

**Question.** How much time does a longer intracellular window save?

**Workload.** The lattice workload of S4.1 with 1,000 cells in each model's medium; k = 1, 2, 5, 10, 20, 50 and 100 at
diffusion timesteps of 0.01 and 0.001 min; 1 and 56 threads; 3 repeats; 10 simulated minutes. 252 runs, all
completed without flags. Repeat spread is at most 2.3% on 1 thread and 7% on 56 threads, except E. coli core on 56
threads (loops of 1–21 s), where it reaches 18%.

**Results** (Table S11, Figure S4).

- **The saving is capped by the share of time in the LPs** (Amdahl's law). On 1 thread, MCF7 core saves 9.5× at k = 10
  and 63× at k = 100 (dt 0.01). E. coli core on 56 threads spends 37–46% of its loop outside the LPs and cannot gain
  more than 2.2–2.7×.
- **The cost of a solve depends on the window length.** Each solve is warm-started from the cell's previous basis.
  The longer the window, the further the bounds move between solves and the more iterations a solve needs. On 1 thread,
  iML1515 spends the same intracellular time for the same window at either diffusion timestep: 218 s and 212 s for
  0.1-min windows (k = 10 at 0.01, k = 100 at 0.001), and 1,672 s and 1,686 s for 0.01-min windows. Genome-scale models
  therefore gain less than k from long windows.

**Table S11. Simulation-loop time at k = 1 and speed-up at k = 10 / k = 100** (1,000 cells, 10 min; Amdahl bound in
brackets where it limits).

| Model | Threads | dt 0.01: loop at k = 1 | dt 0.01: speed-up k = 10 / 100 | dt 0.001: loop at k = 1 | dt 0.001: speed-up k = 10 / 100 |
|---|---:|---:|---:|---:|---:|
| E. coli core | 1 | 45.8 s | 7.1× / 18.6× | 458 s | 7.2× / 18.8× |
| E. coli core | 56 | 1.86 s | 2.2× / 2.3× (2.2) | 20.9 s | 2.3× / 2.7× (2.7) |
| MCF7 core | 1 | 256 s | 9.5× / 62.9× | 2,567 s | 9.9× / 84.1× |
| MCF7 core | 56 | 6.38 s | 6.9× / 16.5× | 61.5 s | 7.9× / 26.3× |
| iML1515 | 1 | 1,674 s | 7.6× / 21.0× | 16,352 s | 9.7× / 75.8× |
| iML1515 | 56 | 43.2 s | 7.9× / 23.7× | 425 s | 9.4× / 66.5× |

![**Figure S4. Time saved by longer intracellular windows.** Simulation-loop speed-up relative to k = 1 for 1,000 cells,
on 1 thread (blue, circles) and 56 threads (orange, squares), at diffusion timesteps of 0.01 min (solid, filled) and
0.001 min (dashed, open). Dotted: speed-up equal to k.](figures/FigS4.png)

Combining Tables S7 and S11: for cancer cells in 15 µm voxels at a diffusion timestep of 0.001 min, a 0.1-min window
(k = 100) changes biomass by about 2 × 10⁻⁵ and runs the loop 84× faster on 1 thread and 26× faster on 56 threads. For
E. coli in 2 µm voxels, windows up to 0.01 min (k ≤ 10 at 0.001 min) keep the final biomass within 10⁻⁴ and run 7–10×
faster on 1 thread, but at most 2.3× faster on 56 threads.

## S4.8 Feasible problem sizes

Table S12 extrapolates the measured loop cost at 10,000 cells linearly to other cell counts, for a 24-hour simulation
at k = 1 and a diffusion timestep of 0.01 min. Cost is close to linear in the number of cells (S4.2). Model loading,
output and the extra mechanics and diffusion of a growing tissue are not included.

**Table S12. Estimated wall time of a 24-hour simulation (one node, k = 1, diffusion dt 0.01 min).**

| Model | Threads | 1,000 cells | 10,000 cells | 100,000 cells | Memory per 1,000 cells |
|---|---:|---:|---:|---:|---:|
| E. coli core | 1 | 2.2 h | 22 h | 9.2 days | 0.12 GB |
| E. coli core | 56 | 0.09 h | 0.9 h | 9.3 h | |
| MCF7 core | 1 | 11 h | 4.5 days | 45 days | 0.4 GB |
| MCF7 core | 56 | 0.35 h | 3.5 h | 35 h | |
| iML1515 | 1 | 74 h | 31 days | 308 days | 2.3 GB |
| iML1515 | 56 | 2.2 h | 22 h | 9.1 days | |

On one node, tens of thousands of cells with core models are tractable over days of simulated time, and
genome-scale models over hours to a day for about 10⁴ cells. A window of k diffusion steps divides the LP part of these
times by up to k, within the accuracy limits of S3.4. All measurements are on one shared-memory node; PhysiCell and
PhysiCelldFBA parallelise with OpenMP within a node.

## S4.9 The published applications, as distributed

**Question.** What do the simulations shown in the main text cost?

**Scenario.** The six dFBA sample projects distributed with PhysiCelldFBA, stock builds, each run with its distributed
configuration (thread count, timesteps, duration, seed, inputs) on one exclusive node. Those configured with fewer
threads than a node were also run at 56 threads, changing only the thread count. 12 runs.

**Table S13. Wall time and memory of the published applications.**

| Application (project) | Model | Threads | Diffusion / intracellular dt (min) | Simulated | Cells: start → end | Wall time | Peak memory |
|---|---|---:|---|---:|---|---:|---:|
| Unit test (`dfba_unit_test`) | E. coli core | 4 (distributed) / 56 | 0.001 / 0.001 | 4 h | 1 → 8 | 30 s / 66 s | 20 MB |
| Metabolism-driven motility (`metabolic_driven_motility`) | E. coli core | 6 / 56 | 0.001 / 0.001 | 10 h | 1 | 65 s / 93 s | 14 MB |
| Motility with proliferation (same project) | E. coli core | 6 / 56 | 0.001 / 0.001 | 10 h | 1 → 4 | 65 s / 95 s | 16 MB |
| Acetate switch (`ecoli_acetic_switch`) | E. coli core | 3 / 56 | 0.001 / 0.001 | 10 h | 200 → 1,600 | 4.08 h / 0.72 h | 0.28 GB |
| Cancer metabolism (`cancer_core_metabolism`) | MCF7 core | 6 / 56 | 0.01 / 0.01 | 72 h | 240 → 354 / 352 | 2.42 h / 0.55 h | 0.15 GB |
| Bacterial colony (`bacterial_colony`) | E. coli core | 112 | 0.001 / 0.001 | 10 h | 211 → 93,655 | 16.0 h | 11.0 GB |
| Cross-feeding (`crossfeeding`) | iCB925 and iMG746 (trimmed) | 112 | 0.001 / 0.001 | 42.5 of 50 h | 353 → 29,742 | 30.2 h | 14.2 GB |

- Applications with a handful of cells run in about a minute; start-up and output dominate, and 56 threads are slower
  than 4–6.
- With hundreds of cells, 56 threads are 4.4× (cancer metabolism) and 5.7× (acetate switch) faster than the distributed
  thread counts.
- Growing bacterial populations are the expensive case. At a diffusion and intracellular timestep of 0.001 min, the
  bacterial colony grows to about 94,000 cells in 10 simulated hours and needs 16 h on a full node, at 4.0 µs per cell
  and diffusion step. The cost per simulated hour grows with the population.
- The cross-feeding run terminated after 42.5 of its 50 simulated hours (30.2 h of wall time), when the colony had
  outgrown its 200 × 200 µm two-dimensional domain and cells were being pushed beyond its edges. Its timings are
  reported up to that point: 5.9 µs per cell and diffusion step.

# S5. Standard FBA versus parsimonious FBA in the cancer model

**Question.** Does parsimonious FBA (pFBA) change the growth, the exchanges or the tissue dynamics of the cancer
model, and what does it cost?

**Method.** pFBA solves the standard FBA problem (stage one) and then, with growth fixed at 100% of the stage-one
optimum, minimises the total absolute flux (stage two). It selects one flux distribution among the equally optimal
ones. FBA and pFBA differ only in this second stage.

**Scenarios.** MCF7 core at intracellular timesteps of 0.01 and 0.1 min (k = 1 and 10 at a diffusion timestep of 0.01 min):

- **Single cell**: one cell at a fixed position, fixed population, 240 simulated minutes, 1 thread, per-step telemetry.
- **Application**: the `cancer_core_metabolism` application (240 cells from its distributed initial positions, with
  growth, division and death) for its 72 simulated hours, on 56 threads, with hourly snapshots and no per-step telemetry.
  One run per condition.

**Metrics.** Biomass trajectories; exchange rates of glucose, oxygen and lactate; total internal flux; second-stage
status; live and dead cells; mean substrate concentrations; infeasible LPs; loop and wall time.

**Results: single cell** (Table S14, Figure S6a–b).

- pFBA reproduces FBA's growth exactly: the biomass trajectories differ by at most 2 × 10⁻¹³.
- It selects a flux distribution with 192× less total internal flux. That distribution takes up 21% less glucose and
  14% less oxygen and secretes 38% less lactate.
- All second-stage solves are optimal. pFBA takes 1.45× FBA's loop time at 0.01 min and 1.07× at 0.1 min.
- The 0.1-min window changes biomass by 2 × 10⁻⁵ relative to 0.01 min, with identical exchange rates.

**Table S14. Single MCF7 cell, 240 min.**

| | FBA, dt 0.01 | pFBA, dt 0.01 | FBA, dt 0.1 | pFBA, dt 0.1 |
|---|---:|---:|---:|---:|
| Biomass change | 5.611976% | 5.611976% | 5.611976% | 5.611976% |
| Median total internal \|flux\| | 3,020 | 15.7 | 3,020 | 15.7 |
| Mean glucose / O₂ / lactate net exchange (BioFVM units/min) | −1,204 / −4,927 / +1,536 | −946 / −4,254 / +959 | −1,204 / −4,927 / +1,536 | −946 / −4,254 / +959 |
| Second-stage solves (all optimal) | — | 24,000 | — | 2,400 |
| Simulation-loop time | 15.7 s | 22.9 s | 8.9 s | 9.5 s |

**Results: application** (Table S15, Figure S6c–f).

- **FBA and pFBA give the same tumour dynamics within the variation of a single stochastic run.** Live cells and biomass
  track each other for about 40 h and then differ by up to 13% (cells) and 8% (biomass). Division and death are
  stochastic, and with one run per condition this late difference cannot be separated from random variation.
- **pFBA's systematic signature is lactate.** Mean lactate in the domain ends 1.6× (dt 0.01) to 1.8× (dt 0.1) higher
  under pFBA, while mean glucose and oxygen are the same. In the single cell pFBA secretes less lactate than FBA.
  Which exchange pFBA selects among equally optimal solutions therefore depends on the local environment.
- **Cost.** pFBA takes 1.3× (dt 0.01) to 2.0× (dt 0.1) FBA's wall time. The second stage falls back to stage-one fluxes in
  8 × 10⁻⁶ (dt 0.01) and 1 × 10⁻⁶ (dt 0.1) of its solves.
- **The window matters in the crowded tissue.** At 0.1 min the early die-off is delayed by about 10 h, the final
  population is 9–13% larger, and twice as many stage-one LPs are infeasible, identically for FBA and pFBA. Cells in this
  application are crowded and oxygen is low (about 0.15 mM), which is where the window-demand criterion (S3.4)
  predicts a sensitivity that the single, well-supplied cell does not show. A 0.1-min window runs 8.7× (FBA) and 5.8×
  (pFBA) faster.
- **Infeasible LPs in the application.** About 12% of all stage-one LPs are infeasible at 0.01 min (34% in the first
  simulated hour). These are cells whose local supply cannot meet the model's maintenance requirement. The application
  flags them for metabolic death.

**Table S15. The cancer application at 72 h (240 initial cells, 56 threads).**

| | FBA, dt 0.01 | pFBA, dt 0.01 | FBA, dt 0.1 | pFBA, dt 0.1 |
|---|---:|---:|---:|---:|
| Live / dead cells | 180 / 169 | 188 / 170 | 204 / 145 | 204 / 143 |
| Live dry mass (10⁵ pg) | 1.51 | 1.52 | 1.69 | 1.71 |
| Mean lactate (mM) | 0.186 | 0.298 | 0.167 | 0.308 |
| Infeasible stage-one LPs (whole run) | 11.7% | 12.0% | 22.3% | 22.1% |
| Second-stage fallbacks | — | 602 of 74.7 M | — | 9 of 7.2 M |
| Wall time | 33.8 min | 44.1 min | 3.9 min | 7.6 min |

![**Figure S6. Standard FBA versus pFBA in the MCF7 cancer model.** (a) Mean exchange rates of a single cell over 240 min
(intracellular dt 0.01 min). (b) Median total internal flux of the same cell. (c–f) The 240-cell cancer application over
72 h: live cells (c), live dry mass (d), mean lactate (e) and mean oxygen (f), for FBA (blue) and pFBA (orange) at
intracellular timesteps of 0.01 min (solid) and 0.1 min (dashed). One run per condition.](figures/FigS6.png)

# S6. Practical guidance for choosing timesteps and problem sizes

1. **Parallel execution and cell ordering do not change results.** Serial and parallel runs are identical at every
   tested occupancy. With heterogeneous cells, the update order affects results only at rounding level (10⁻¹⁵).
2. **Mass balance holds for any ratio of intracellular to diffusion timestep.** The exchange ledger closes in every run.
3. **Choose the intracellular window from the window-demand criterion, not from a fixed k.** Keep
   $\Delta t_{\mathrm{intra}} < c\, V_{\mathrm{voxel}} / (V_{\max}\, m_{\mathrm{cell}})$ for every consumed substrate, using the local concentration in crowded
   regions. In these benchmarks, cancer cells in 15 µm voxels tolerate 0.1–0.2-min windows, while E. coli in 2 µm voxels
   needs windows of about 0.01 min or less.
4. **The time saved is bounded by the LP share of the run.** Windows save most for mid-size and large models on few
   threads, and least for small models on many threads.
5. **Use the threads of a node for populations of hundreds of cells or more.** LP work scales to 38–41× on 56 threads.
   For a handful of cells, a few threads are faster.
6. **Size the problem with Tables S9 and S12.** Cost is close to linear in the number of cells, and memory is about
   0.12, 0.4 and 2.3 GB per 1,000 cells for the three models.

# S7. Reproducibility, software availability and data archive

**Versions.**

- PhysiCelldFBA commit `c59daa81bc13c459b9421b3fb5dbb7b6200b3b8b`.
- PhysiCell baseline: commit `49d7cc54d9367431ae3f51814621258fdbbb736d` (version 1.14.2).
- Benchmark repository: github.com/PhysiCelldFBA/PhysiCelldFBA-benchmark, release `v1.0.0`, archived on Zenodo as
  [doi:10.5281/zenodo.24283791](https://doi.org/10.5281/zenodo.24283791). It contains PhysiCelldFBA at the benchmarked commit as a Git submodule.

**License.** The benchmark code is distributed under the BSD 3-Clause license, the license of PhysiCell (file
`LICENSE`). The results, tables, figures and documentation are distributed under CC-BY-4.0.

**What the archive contains.**

- **Code**: the instrumentation layer (applied as a patch at build time), the benchmark driver, and the build script that
  records compiler, flags, libraries, solver settings and binary checksums. It also has the preparation scripts that
  generate every scenario from the distributed configurations, the Slurm launcher, the analysis scripts, and the
  script that draws Figures S1–S7 from the result tables.
- **Inputs**: all configurations, SBML models (including the iML1515 asset), cell positions and seeds, as immutable
  bundles with SHA-256 manifests. Simulation seed 50. Update-order seeds 11, 23, 37, 51 and 71. Run-order seeds are
  recorded in each campaign.
- **Results**: per study, tables of every run, figures, compact per-run evidence (metrics, telemetry summaries, settings,
  hardware records, logs) and an `analysis.json` with the SHA-256 of the analysis script and of every evidence file.
- **Environment**: compiler and module versions, and `pip freeze` of the analysis environment.
- **Raw outputs** (about 140 GB: snapshots and per-step telemetry) are archived separately, with a guide to their layout
  (`benchmarks/DATA.md`).

**Commands.** Each study is prepared, run and analysed by a scripted workflow. The exact sequences used are in
`benchmarks/results/final-20261102/workflow/` and `workflow-studies/`. In outline:

```bash
# build (records build.json with compiler, flags, libraries, solver settings, binary SHA-256)
bash benchmarks/performance/build.sh PhysiCelldFBA <build-dir> <project> <jobs>
python benchmarks/performance/record_build.py <build-dir> <executable> --template <build-record>
# prepare a study (never runs simulations, refuses to overwrite)
python benchmarks/voxel_sharing/prepare.py ...            # S3.1, S3.2 (with --protocol mesh_protocol.json)
python benchmarks/performance/prepare_tradeoff.py --stage accuracy|cost --diffusion-dt 0.01|0.001 ...   # S3.4, S4.7
python benchmarks/performance/prepare_final_studies.py --stage pfba|scaling ...                         # S5, S4.1-S4.6
# run on a Slurm cluster (one exclusive node per job)
sbatch <campaign>/tools/run_mn5.sbatch <campaign> 1 <part> [<case list>]
# analyse
python benchmarks/voxel_sharing/analyze.py | summarize_mesh.py ...
python benchmarks/performance/analyze_tradeoff.py | analyze_cost.py | analyze_pfba.py | analyze_scaling.py | analyze_apps.py ...
python benchmarks/performance/report_tables.py ...        # Tables S1, S2, S10, S12
python supplementary/make_figures.py                      # Figures S1-S7
```

Unit tests (S3.3): `benchmarks/results/unit_tests/c59daa81/run.sh`. Applications (S4.9):
`benchmarks/results/applications/apps-20261109/workflow/`.

# S8. Scope of the benchmark

- **Controlled geometries.** The robustness, timestep and scaling studies fix cell positions and populations so that
  configurations can be compared exactly. Growing tissues are covered by the published applications (S4.9) and by the
  cancer application (S5).
- **One node.** All measurements are on one shared-memory node with up to 112 threads.
- **Replicates.** Timing studies use three repeats. The stochastic cancer application was run once per condition, so
  differences after about 40 h are not tested statistically.
- **Platform.** Timings are for the hardware of Table S2. Relative results (scaling, ratios, speed-ups) are expected to
  carry over to similar multicore CPUs; absolute times will differ.
