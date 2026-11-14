# Repository cleanup report

The original D:\SAR2Action was preserved. Work was performed in D:\SAR2Action-github-safe, created without overwriting an existing directory. Existing import paths and backend/frontend layout remain unchanged. The copy excludes virtual environments, node_modules, Hermes runtime state, B-team JSON cache, raw/processed satellite data, generated reports/screenshots, archives, and build output. README, deployment/data instructions, sample environment, and strengthened Git ignore rules were added. No license was assigned because team rights are unconfirmed.

Original B-team SHA-256 values before cleanup:
- evidence_store.json: 79E5784482FF14544F8AC8920D5DA6F197570509B772838F8381761AA682345C
- fingerprint_store.json: F67369998D6A8782A7512317A3F2B7509571F28A7B62514DC18243B1CAB29795
- analysis_store.json: BDF8280D9B62CE55231C802DC0B046732FCAD40176A1D574666D55DECDF519A9
- layer_store.json: AF370157CD91B792A63531CA8FCFAA9E5DF5834ABF1DF48199BFE672F19B6C20

Baseline original frontend: 9/9 unit tests passed and Vite build passed. Original backend pytest could not start because the local venv points to a missing Python installation. Safe copy frontend: 9/9 unit tests passed; TypeScript check and Vite build passed. Safe copy backend pytest/health and integration checks are BLOCKED: only Python 3.11 is installed, no usable project environment exists, and available packages lack pytest/rasterio. npm dependency audit is BLOCKED by DNS/network access. Windows Defender scan is BLOCKED because its feature is disabled. These failures prevent a READY release.
