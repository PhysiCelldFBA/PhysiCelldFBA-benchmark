# Software environment of the final runs

Captured on MareNostrum 5 (GPP partition) for the analyses and tests of the final runs.

| File | Contents |
|---|---|
| [python.txt](python.txt), [modules.txt](modules.txt) | Python 3.12.1 from `module load hdf5 python/3.12.1`, and the loaded modules |
| [requirements-analysis.txt](requirements-analysis.txt) | `pip freeze` of the analysis environment. It includes the MN5 system site packages the venv sees; the analyses need only `numpy`, `scipy`, `matplotlib` (and `pctk` for snapshot work). |
| [requirements-unit-tests.txt](requirements-unit-tests.txt) | Packages added for PhysiCelldFBA's `dfba_unit_test` checks (`cobra`), installed on top of the system site packages |
| [compiler.txt](compiler.txt) | GCC 11.5.0, glibc 2.34, RHEL 9.6 |

Simulation builds record compiler, flags, linked libraries (Clp 1.17.10, CoinUtils 2.11.12, libSBML 5.20.4) and
solver settings in their build records: [`results/final-20261102/builds/`](../results/final-20261102/builds/).
