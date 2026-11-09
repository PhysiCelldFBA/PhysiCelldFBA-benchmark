# PhysiCelldFBA unit tests on the benchmarked commit

PhysiCelldFBA's own `sample_projects_intracellular/fba/dfba_unit_test` suite, run on commit `c59daa81` (stock build,
no benchmark hooks; job script [run.sh](run.sh), provenance in [provenance.txt](provenance.txt)). Both scripts exit 0.

| Test | What it checks | Result |
|---|---|---|
| Voxel sharing (`run_voxel_sharing_test.sh`) | 1, 4 and 8 cells, and a mixed layout, in one voxel: concentrations stay non-negative (tolerance 10⁻⁴ mM); a cell type that cannot take glucose does not dilute the others | 5/5 PASS (minimum glucose −3.8×10⁻⁶ to −7.6×10⁻⁶ mM) |
| Update order and threads (same script) | 12 cells of four types in one voxel, created in 5 orders, at 1 and 4 threads; every run against the 1-thread identity order (tolerance 10⁻⁹) | 10/10 within 1.1×10⁻¹⁵ |
| Voxel size and time step (`run_dxdt_test.sh`) | dx 0.8/1.6/3.2 µm × dt 0.005/0.01/0.02 min; invariance while the uptake cap is inactive, exact voxel draining when it acts, ledger residual, carbon and elemental balance; intracellular dt = 2 and 10 × dt | 118/118 PASS |

Logs: [voxel_sharing_and_update_order.log](voxel_sharing_and_update_order.log), [dxdt.log](dxdt.log), [summary.txt](summary.txt).
