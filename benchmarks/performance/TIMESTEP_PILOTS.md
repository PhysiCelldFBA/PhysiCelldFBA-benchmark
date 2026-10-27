# First serial timestep pilots

The first 11 runs are complete. See the [results, figures and cancer LP diagnosis](../results/timestep/pilot-20261026/README.md).

The subsequent [model-specific nutrient review](model_conditions/README.md)
separates native application media, deliberate starvation controls and candidate
growth-positive media. Read it before changing or extending these pilots; the
original results and inputs remain unchanged.

The [23 dynamic medium controls](../results/growth_conditions/growth-20261026/README.md)
show that enrichment does not resolve all unequal-timestep failures. Include
the exchange ledger in acceptance checks even for runs with positive growth
and no negative concentrations. The performance candidate profiles use the
tested 0.01-minute setting; the agreed timestep sweep is unchanged.

These pilots select the duration and numerical comparison criteria for the final
supplementary study. They are not final accuracy or performance measurements.

- E. coli mass conversion and single-cell cancer: intracellular/diffusion ratios
  1, 2, 10 and 100, with diffusion dt fixed at 0.01 minutes (eight cases).
- Cancer reference refinement: both timesteps equal at 0.01, 0.005 and 0.0025
  minutes (three cases). The coarsest reference repeats the ratio-one setup as a
  consistency check; it is not an independent model or accuracy ground truth.
- One thread, fixed position/population, metabolic biomass growth enabled,
  standard FBA, simulation seed 50. Cancer retains its physical pre-equilibration
  duration. Output snapshots follow intracellular dt; compact diagnostic data are
  also collected each diffusion step.
- Start with **10 simulated minutes** per case, giving ten intervals even at
  intracellular dt = 1 minute. Inspect depletion, biomass, exchanges, update counts
  and solver statuses before extending durations. Do not infer absence of timestep
  sensitivity when this pilot has not reached meaningful dynamics.

In the documented Python environment, use `prepare_pilots.py --help` and supply
the unit/cancer binaries and their build provenance. It creates fresh inputs,
immutable bundles, randomized launch order, run/table/plot folders and checksums.
The source must be committed. The full timestep study, cancer FBA/pFBA comparison,
and performance sweeps remain separate later stages.

Submit the prepared pilot campaign with the common launcher, selecting its part:

```bash
sbatch --job-name=dfba-dt-pilot --time=02:00:00 \
  --output=/absolute/campaign/timestep/logs/slurm-%j.out \
  /absolute/campaign/tools/run_mn5.sbatch /absolute/campaign 1 timestep
```

This reserves one node and executes the eleven cases sequentially. It preserves
comparable resources and continues after diagnostic flags. Use measured times to
size subsequent requests. Analyze compact trajectories with `analyze_outcomes.py`
and retain failed/flagged attempts. This preparation script does not submit jobs.
