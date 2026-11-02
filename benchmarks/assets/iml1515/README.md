# iML1515 benchmark assets

PhysiCelldFBA removed the iML1515 genome-scale model from `ecoli_acetic_switch` after
`a2519f06` (the sample now uses E. coli core). The benchmark keeps it as a genome-scale
workload, so the two files it used are stored here unchanged, taken from PhysiCelldFBA
`a2519f06:sample_projects_intracellular/fba/ecoli_acetic_switch/config/`:

| File | SHA-256 |
|---|---|
| `PhysiCell_settings.xml` (template of the `iml_batch` / `iml_fed` medium profiles) | `85e3b256a099b027f6b30f0114b15f40f0a1a55cca99bdf02b0626844868774a` |
| `iML1515.xml` (SBML) | `9c772d44ca43350e40dc7ee86c7aa148796856be1eea45e5406c6df8f7dcde28` |

These are the inputs with which the `iml_fed` profile passed the
[growth-condition checks](../../results/growth_conditions/growth-20261026/README.md) and ran in
the trade-off [check stage](../../results/timestep/tradeoff-checks-20261027/README.md). Paths starting
with `benchmarks/` in `study.json` and `growth_profiles.json` resolve inside this repository
(`common.source_path`); all others resolve in the PhysiCelldFBA submodule.
