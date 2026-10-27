# First failed cancer LP

This diagnostic replays the original ratio-100 configuration with an isolated
copy of the cancer build. Observation-only hooks export the first failed LP,
its column mapping/bounds, and the local exchange inputs. Independent LP copies
are used for counterfactual solves. The campaign binary, settings and results
remain untouched.

- `failed_problem.lp`: first failed LP, coefficients exported with 17 decimals.
- `failed_bounds.csv`: original reaction IDs, column indices and bounds.
- `first_update_exchange.csv`: cell-local concentrations, kinetic and actual bounds.
- `lp_probe.csv`: fresh primal solve and relaxation of required positive fluxes.
- `oxygen_counterfactual.txt`: replay with only oxygen's lower bound changed.
- `provenance.json`, `diagnostic_checks.json`: source identities and verification.
- `probe.patch`: observation hooks applied to the isolated source snapshot.

The original LP is infeasible (Clp status 1). Relaxing the ATP-maintenance minimum
to zero and maximizing ATP maintenance gives 0.83241808311966425, below the required
1.07. Restoring only the oxygen exchange lower bound from -0.13011998026031704
to -0.5 makes the original objective feasible (status 0).

To reproduce the oxygen counterfactual from this exported LP, compile
`benchmarks/performance/diagnostics/replay_lp.cpp` against the recorded Clp/CoinUtils
libraries, then run in the project's compute environment:

```bash
/path/to/replay_lp /path/to/failed_problem.lp x17 -0.5
```

`x17` is the **exported variable name** for `R_EX_o2_e`, verified in
`failed_bounds.csv`. LP import can reorder columns; do not use an imported numeric
column index. The exported LP minimizes negative biomass, so its feasible objective
is -0.013653092327316667 (positive growth magnitude 0.013653092327316667 per hour).

The general in-memory probe is in `benchmarks/performance/diagnostics/lp_probe.h`.
It is not included by production code. The isolated patch includes it after
`dfba_Model.h` and calls it immediately after a primary solve, passing the LP and
reaction-to-column map. Its scans do not assume a model-specific reaction ID.
