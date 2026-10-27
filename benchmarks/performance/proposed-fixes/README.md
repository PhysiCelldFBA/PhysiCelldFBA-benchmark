# Proposed fixes (not part of PhysiCelldFBA)

Source patches applied to benchmark builds with `EXTRA_PATCHES` to measure the effect
of a candidate fix before it is merged upstream. A build that uses one records it in
`build.json` (`source_patches`, `benchmark_harness`) and in `applied-patches.txt`.
Results from such builds describe the patched code, not any PhysiCelldFBA release;
re-run on the merged commit once a fix is accepted.

## `intracellular-dt-exchange.patch`

After each FBA solve, `dFBAIntracellular::update_dfba_outputs` called
`set_internal_uptake_constants(dfba_time_step)`. BioFVM precomputes
`net_export_rate × dt` there and adds it to the voxel at **every diffusion step**
until the next update. With intracellular dt = k × diffusion dt, each dFBA window
therefore exchanged k times the FBA flux. The call also clears BioFVM's
`volume_is_changed` flag, so growth does not trigger a recomputation with the
diffusion step. The patch builds the constants for `PhysiCell::diffusion_dt`.

- No effect when intracellular dt equals diffusion dt (k = 1).
- Evidence: serial E. coli pilots (`results/timestep/pilot-20261026`) consumed 1.17%,
  2.33% and 11.56% of the glucose at k = 1, 2, 10, with the same biomass growth.
- The uptake cap (`update_dfba_inputs`) already budgets a whole window, so it is
  consistent with the patched exchange.
