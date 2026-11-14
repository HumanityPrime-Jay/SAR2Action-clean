# Local scientific data

`cache/` holds team-provided `evidence_store.json`, `fingerprint_store.json`, and `analysis_store.json` (and optional `layer_store.json`). Obtain them from an authorized team source and copy them locally without changing values. They are ignored by Git. `raw/` holds authorized NISAR HDF5 products; `processed/` and `scenes/` are local outputs. None are included in this release. Synthetic fixtures in tests are examples, not real NISAR observations.

## Data-dependent test conditions

Run pytest after installing the dev extra. Tests that require private scene manifests, B-team cache records, or NISAR sidecars now state those prerequisites and skip when files are absent. Synthetic and deterministic tests continue to run. A skip does not validate the missing scientific data. To perform the complete data-backed checks, use only authorized local inputs in a separate private testing environment; never commit them.
