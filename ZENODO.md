# Zenodo deposit: what to upload and how

The benchmark is deposited manually. This checklist keeps the record consistent with the repository and the
manuscript.

## 1. Freeze the version

1. Make sure `main` contains the final reports and that the working tree is clean.
2. Tag it: `git tag -a v1.0.0 -m "PhysiCelldFBA benchmark, final results"` and `git push origin v1.0.0`.
3. Build the upload archive from the tag, including the pinned submodule's commit id but not its sources:
   ```bash
   git archive --format=tar.gz --prefix=PhysiCelldFBA-benchmark-v1.0.0/ -o PhysiCelldFBA-benchmark-v1.0.0.tar.gz v1.0.0
   sha256sum PhysiCelldFBA-benchmark-v1.0.0.tar.gz
   ```
   The archive holds the code, protocols, compact results (about 0.4 GB) and the iML1515 asset. PhysiCelldFBA
   itself is referenced by commit (below), not included.

## 2. Record metadata

| Field | Value |
|---|---|
| Upload type | Dataset (or Software, if the code is the focus) |
| Title | PhysiCelldFBA benchmarks: concurrency, timestep, pFBA and performance results |
| Version | v1.0.0 |
| License | CC-BY-4.0 for the record (results, tables, figures and documentation); BSD 3-Clause for the code (see `LICENSE`), as stated in `README.md` |
| Description | Start from the first paragraphs of `README.md` and `benchmarks/results/final-20261102/README.md` |
| Related identifiers | GitHub `PhysiCelldFBA/PhysiCelldFBA-benchmark` at tag v1.0.0 (is supplement to); `PhysiCelldFBA/PhysiCelldFBA` commit `c59daa81` (references); the manuscript DOI once available (is supplement to) |
| Authors | To be decided by the authors |

## 3. Raw data

The raw campaign outputs (the whole `benchmarks/workspaces/` folder, 163 GB; see
[benchmarks/DATA.md](benchmarks/DATA.md)) go in the same record, next to the repository archive. They are packaged by
[`benchmarks/package_raw_data.sh`](benchmarks/package_raw_data.sh): one byte-exact `tar.zst` per folder, verified against
the SHA-256 of every source file, with the duplicated simulator executables stored once (`executables.tar.zst`;
[`benchmarks/restore_executables.sh`](benchmarks/restore_executables.sh) puts them back). The result is 25 archives,
6.7 GB in total, uploaded with their `README.md` and `SHA256SUMS`.

## 4. After publication

Add the DOI to `README.md` and to the manuscript's data-availability statement. Note in `PROVENANCE.md` the
PhysiCelldFBA release commit once the exchange-fix PR is merged, and the outcome of comparing it with `c59daa81`.
