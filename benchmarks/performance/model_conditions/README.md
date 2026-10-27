# Model-specific growth conditions review

Reviewed against source revision `845d9c2e8e2746e954068363fa717dfad1643eed`.
This review covers 23 PhysiCell XML configurations under
`sample_projects_intracellular/fba`, their referenced SBML models, and nutrient
supply code in the sample mains/custom modules. One legacy configuration has no
intracellular cell definition. The extracted inventory is
[sample_conditions.json](sample_conditions.json); [media.csv](media.csv) is the
compact field-by-field table, including enabled boundary faces.

**Growth conditions must be selected per model and per experimental purpose.**
The existing examples provide starting conditions, not experimentally optimized
media. The static checks below establish initial LP feasibility under specified
local concentrations; they cannot establish sustained growth in a spatial run.
Existing simulations, sample inputs, benchmark defaults and engine code have
not been changed by this review.

## Conditions extracted from the use cases

Concentrations below use the engine's mM convention. Retain the source exchange
reaction mappings, Km/Vmax, model bounds, cell mass and geometry together.
Changing concentration alone does not reproduce a use case.

| Model/use case | Starting medium and supply | Consequence for the benchmark |
|---|---|---|
| E. coli core, mass conversion | Glucose 10 mM; oxygen **100,000,000 mM**; acetate/CO2 zero; closed boundaries. Dry mass 0.338 pg; voxel 4.096 µm³. | Deliberately oxygen-unlimited, finite-glucose conservation test. Keep it as a numerical control; do not call this a realistic culture medium. |
| E. coli core, shared voxel | Glucose 0.165 mM; the same artificial oxygen reservoir. | Deliberate competition/stress test. Preserve it when interpreting the completed shared-voxel and mesh experiments. |
| E. coli core, bacterial colony | Glucose 11 mM and oxygen 10 mM initially and at x/y boundaries; acetate, lactate and CO2 initially zero. Dry mass 0.338 pg; voxel 8 µm³. | Best-supported existing **fed growth** starting profile for this application model. It includes five coupled fields and different uptake kinetics from the unit test. |
| E. coli core, acetate switching | Glucose 8 mM and oxygen 5 mM initially; acetate/CO2 zero; boundaries disabled. Dry mass 0.338 pg; voxel 1 µm³. | A batch/switching experiment, not a continuously supplied growth medium. Its main performs a later oxygen reset. |
| iML1515, native large-scale example | Glucose 10 mM initially with closed glucose boundaries; oxygen 1 mM initially and at x/y boundaries. Dry mass **808.056 pg**; voxel 8000 µm³. | Do not copy this phenotype into a bacterial comparison without review: it uses volume 2494 µm³, fluid fraction 0.70 and density 1.08. Its objective mapping is valid. |
| iML1515, current benchmark template | Acetate-switching initial medium: glucose 8 mM, oxygen 5 mM, dry mass 0.338 pg, voxel 1 µm³; substitute iML1515 and its biomass objective. | A controlled model substitution, not the native large-scale application. Initial growth is supported by the static check; sustained supply remains to be validated. |
| MCF7 core, FBA and pFBA samples | All 23 fields initially zero. At xmin: glucose 0.5 mM, oxygen 0.5 mM and 17 other nutrients at 1 mM each. At xmax: all fields zero. Three minutes of pre-diffusion. Dry mass 778.128 pg; voxel 3375 µm³. | Preserve the complete supplied medium, gradient and preparation for the application comparison. A generic glucose/oxygen-only unit-test medium is insufficient. |
| Recon2.2 cancer sample | Oxygen 0.06 mM and glucose 5 mM initially and at x/y boundaries; lactate/CO2 zero. Dry mass 785.610 pg; voxel 8000 µm³. | Different network, maintenance and transport settings from MCF7. It is not currently one of the three selected performance networks. |
| Crossfeeding: C. beijerinckii and M. barkeri | Glucose 1, CO2 1, NH4/Pi/SO4 each 5; H2, acetate and methane zero initially, with the corresponding boundary values enabled. | Preserve both partners. M. barkeri needs access to partner products; its near-zero initial standalone growth is not evidence of a solver crash. |
| E. coli metabolic motility | Default: oxygen initially 4, zmax 8; glucose initially zero, xmin 0 and xmax 0.65. Multiple-source variant: glucose supplied at explicit source voxels toward 6 mM. | Includes position-dependent delivery and an additional motility ATP cost. XML alone cannot reproduce this application. Dry mass is 2.08 pg, not 0.338 pg. |

MCF7's 17 additional supplied nutrients are Choline, Glycine, L-Arginine,
L-Asparagine, L-Glutamate, L-Glutamine, L-Isoleucine, L-Leucine, L-Lysine,
L-Phenylalanine, L-Serine, L-Threonine, L-Tryptophan, L-Tyrosine, L-Valine,
Ornithine and Phosphate. Ammonium, CO2, L-Aspartate and L-Lactate start at zero
and have no positive xmin supply. Retain all 23 fields and exchange mappings.

The detailed inventory preserves the exact original unit labels. Some acetate
fields are labelled `mmol` and some gas fields `dimensionless`, despite being
used as concentrations by the dFBA exchange calculation. These metadata
inconsistencies need normalization in newly reviewed inputs; this review does
not silently convert their numerical values. Growth outputs below are h⁻¹, as
used by the engine, even where an XML growth/maintenance label says `1/min`.

## Supply behavior that copying XML would miss

- [Acetate-switching main](../../../sample_projects_intracellular/fba/ecoli_acetic_switch/main.cpp)
  actively calls `inject_density` once at `reinject_oxygen_time`: 210 minutes in
  the default example and **390 minutes even in `static_condition.xml`**. The
  target oxygen concentration is 5 mM across all voxels (the function replaces
  concentrations; it does not just add substrate at the edges). The older
  `reintroduce_nutrients_function()` call is commented out; its XML window
  parameters are not the active schedule. The native iML1515 XML lacks the newer
  pulse parameters read by this main. Do not assume that file is a runnable
  replacement without reconciling those parameters.
- [Crossfeeding main](../../../sample_projects_intracellular/fba/crossfeeding/main.cpp)
  has its scheduled refeeding call commented out. The custom module's initial
  refeed setup is conditional on `glucose_refeed_enabled`, which the reviewed
  XMLs do not set. `nutrient_reintroduction=True` alone does not enable a pulse.
- [Motility main](../../../sample_projects_intracellular/fba/metabolic_driven_motility/main.cpp)
  registers source voxels and invokes bulk source/sink integration. Sources are
  disabled in the default XML and enabled in the multiple-source variant.
  Source radius, location, target concentration and supply rate all matter.
- The benchmark driver retains cancer pre-diffusion, but does not implement
  these acetate-switching pulse or motility source hooks. Their application
  behavior must not be inferred from a benchmark using their initial medium.
- Explicit per-face Dirichlet settings must be inspected, including zero-value
  sinks. A single outer-boundary boolean or initial concentration is not a
  sufficient description of the medium.

## Model bounds are part of the medium specification

The unit-test and application files both named `Ecoli_core.xml` are different.
The unit-test model has no positive ATP-maintenance minimum; the colony/switching
model requires `R_ATPM >= 8.39`. MCF7 requires 1.07, iML1515 6.86 and Recon2.2
8.6 mmol/gDW/h. These minima explain why starvation can produce a feasible
zero-growth solution in one model and an infeasible LP in another. Preserve the
SBML hashes and maintenance settings; do not remove maintenance to make a
benchmark pass.

Unmapped SBML exchange bounds also remain active. The static screen counts
4 boundary reactions allowing unmapped uptake for E. coli and MCF7, 21 for
iML1515 and 36 for Recon2.2. These counts describe permitted bounds, not proof
that every such reaction carries flux. Such substrates are implicit reservoirs,
not explicit BioFVM fields. Therefore four simulated fields do not describe the
entire iML1515 nutritional environment.

## Static LP screening results

The [screening table](static_lp/summary.csv) contains 36 checks using the current
dFBA/CLP implementation: each native profile, both crossfeeding organisms,
three MCF7 oxygen candidates, and the iML1515 benchmark-template substitution,
at intracellular intervals 0.01, 0.1 and 1 minute. The source and binary hashes
are archived with the results.

For each field, the screen uses the maximum of the initial concentration and
enabled boundary concentrations as a **uniform local supply-level condition**.
It applies mapped Michaelis–Menten uptake limits, the current single-cell voxel
budget over the intracellular interval (including its 1e-18 mmol epsilon),
growth upper bounds and enabled metabolic-death lower bounds. Unmapped SBML
bounds are retained. It does not solve diffusion, gradients, shared demand,
growth over time, secretion caching, refeeding or pFBA.

| Profile | Growth at 0.01 min (h⁻¹) | Growth at 0.1 min (h⁻¹) | At 1 min |
|---|---:|---:|---:|
| E. coli mass conversion | 0.731854 | 0.731854 | 0.666495 |
| E. coli colony | 0.832174 | 0.832174 | 0.695280 |
| E. coli switching | 0.688763 | 0.456874 | Infeasible |
| iML1515 native physiology | 0.694995 | 0.343906 | 0.092738 |
| iML1515 benchmark-template physiology | 0.694636 | 0.442654 | 0.005952 |
| MCF7 original supplied medium, O2 0.5 mM | 0.013653 | 0.013653 | Infeasible |
| MCF7 candidate O2 0.75 mM | 0.013653 | 0.013653 | 0.001840 |
| MCF7 candidate O2 1 mM | 0.013653 | 0.013653 | 0.008586 |
| MCF7 candidate O2 2 mM | 0.013653 | 0.013653 | 0.013653 |
| Recon2.2 | 0.084444 | 0.084444 | Infeasible |
| C. beijerinckii | 0.166488 | 0.040351 | 0.004035 |
| M. barkeri before partner supply | 0.00000227 | 0.00000227 | 0.00000227 |

These checks use each template's own voxel and dry mass. They are neither a
matched growth-rate comparison across networks nor runtime measurements.
The iML1515 proxy now reads the exact template named in `study.json`; the input
materializer already replaces its core-model objective with the iML1515 one.

The completed cancer pilot **did preserve the native cancer medium**. Its first
failure was not caused by copying the E. coli unit-test medium. As shown in the
[pilot LP diagnosis](../../results/timestep/pilot-20261026/README.md), at dt = 1
minute the 0.5 mM local oxygen budget caps uptake at 0.13011998 mmol/gDW/h,
which cannot support the mandatory ATP maintenance. The new static checks show
that oxygen enrichment can restore feasibility. They do not establish that the
native medium was biologically wrong or that enrichment fixes timestep handling.

## Recommended profiles and next validation

1. **Conservation and shared-voxel controls:** retain their original finite
   glucose budgets, unit-test SBML and intentional oxygen reservoir. Keep these
   results separate from normally fed growth/performance cases.
2. **E. coli core growth/performance:** use the colony's fed 11 mM glucose /
   10 mM oxygen profile as the source-backed starting candidate, with its
   application SBML, five fields and native uptake kinetics. This is a separate
   profile from the existing mass-conversion benchmark. Boundary feeding still
   needs to be checked at interior cell positions as the domain grows.
3. **iML1515 performance:** retain the small-cell benchmark physiology and
   8 mM glucose / 5 mM oxygen starting concentrations, with the iML1515 objective
   and unchanged maintenance/implicit nutrient bounds. Explicitly validate or
   add sustained nutrient delivery before a long growth benchmark; the current
   closed starting medium is not a feeding protocol. Do not adopt the older
   808 pg phenotype merely because it accompanies the larger SBML.
4. **MCF7 application/FBA versus pFBA:** retain the native 23-field medium and
   gradient as the biological comparison. For a separate growth-positive
   control spanning dt up to 1 minute, **2 mM local oxygen** with the remaining
   native supply-level concentrations is the strongest of the three screened
   candidates: it retains the small-step static growth optimum. This is a
   numerical control candidate, not a physiological oxygen recommendation.
   A 2 mM boundary value alone does not guarantee 2 mM at interior cells.
5. **Other applications:** preserve Recon2.2's own medium; validate its native
   6-minute intracellular interval separately (not covered by this screen).
   Validate crossfeeding as a coupled culture and motility with its source and
   ATP-cost hooks. Do not substitute these application dynamics into the
   current three-network performance study without a separate protocol.

Before freezing new benchmark inputs, run short serial positive controls at
the actual cell positions, followed by the selected population/geometry. Check
local concentrations, optimal solver statuses, nontrivial growth, uptake versus
available amounts and substrate trajectories throughout the intended duration.
For fed systems, include delivered/removed substrate in mass accounting. Freeze
one medium and feeding schedule across a timestep comparison and use the same
conditions for FBA/pFBA; do not tune nutrients independently for each timestep.
Record supply cost in runtime measurements and match it in PhysiCell controls.

Boundary-only feeding may become limiting as a performance domain grows. A
uniform reservoir control would need explicit implementation and disclosure;
it is not currently supplied by multiplying initial values. In particular,
the materializer's generic nutrient multiplier leaves zero initial cancer
fields at zero and does not change their boundary supply.

The serial dynamic follow-up is documented in the
[growth-validation results](../../results/growth_conditions/growth-20261026/README.md).
In particular, 2 mM oxygen restored initial static feasibility but did not
eliminate all dynamic failures at a one-minute intracellular interval. The separate
unequal-timestep exchange-caching concern and concurrency issues remain open;
nutrient enrichment cannot validate or repair them. Long-duration and target-size
validation remains outstanding. No timestep equality rule was introduced.

## Reproduce the review

From the repository root, first obtain the usual analysis allocation and activate
the environment (run manually; these tools never submit jobs):

```bash
salloc -A bsc08 -q gp_debug -t 00:20:00 -n 1 -c 32 -J dfba-media-review
srun --pty bash
module load hdf5 python/3.12.1
source venv/bin/activate
```

Choose fresh output paths; both scripts refuse to overwrite an existing folder.

```bash
mkdir -p benchmarks/workspaces/media-review-new
g++ -O2 -std=c++11 \
  -Iaddons/dFBA/src -Iaddons/dFBA/ext/coin-or/include \
  -Iaddons/dFBA/ext/libsbml/include \
  benchmarks/performance/diagnostics/screen_medium.cpp \
  addons/dFBA/src/dfba_Model.cpp addons/dFBA/src/dfba_Reaction.cpp \
  addons/dFBA/src/dfba_Metabolite.cpp addons/dFBA/src/dfba_Solution.cpp \
  addons/dFBA/ext/coin-or/lib/libClp.a \
  addons/dFBA/ext/coin-or/lib/libCoinUtils.a \
  addons/dFBA/ext/libsbml/lib/libsbml-static.a \
  -llapack -lxml2 -lbz2 -lz \
  -o benchmarks/workspaces/media-review-new/screen_medium
python benchmarks/performance/review_conditions.py \
  --output benchmarks/workspaces/media-review-new/inventory
python benchmarks/performance/screen_conditions.py \
  --inventory benchmarks/workspaces/media-review-new/inventory/sample_conditions.json \
  --binary benchmarks/workspaces/media-review-new/screen_medium \
  --output benchmarks/workspaces/media-review-new/static-lp
```

The archived [details](static_lp/details.json) contain concentrations and kinetic /
capped bounds for each check. The generated per-check TSV files and solver logs
are retained in the ignored workspace; compact summaries and provenance are
kept here for publication. The inventory extractor records XML settings; the
C++ supply-hook review above is manual and must be revisited if sample mains
or custom modules change.
