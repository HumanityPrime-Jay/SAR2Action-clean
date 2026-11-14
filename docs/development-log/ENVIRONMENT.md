# Phase 1 R&D Environment Log (`ENVIRONMENT.md`)

- **Date:** 2026-10-23
- **Mode:** `PROJECT_MODE = PRE_COMPETITION_RND`
- **Virtual Environment Path:** `D:\NASA\SAR2Action\.venv`
- **Strategy:** `python -m venv .venv --system-site-packages` (Pragmatic R&D choice inheriting pre-validated Windows C-extension wheels from the system Python 3.13 installation without modifying the global Python environment; a clean isolated build recipe is maintained in `pyproject.toml` for final competition reproducibility).

---

## 1. Runtime & Disk Summary

| Attribute | Value |
| :--- | :--- |
| **OS** | Windows 64-bit (`AMD64`) |
| **Python Version** | `3.13.9 (tags/v3.13.9:8183fa5, Oct 14 2025, 14:09:13) [MSC v.1944 64 bit (AMD64)]` |
| **Virtualenv Executable** | `D:\NASA\SAR2Action\.venv\Scripts\python.exe` |
| **Workspace Drive (`D:\`) Total** | `953.87 GB` |
| **Workspace Drive (`D:\`) Free** | `89.47 GB` |

---

## 2. Verified Package Versions in `.venv`

| Package | Version | Source Location | Import Verification |
| :--- | :--- | :--- | :--- |
| `numpy` | `2.4.4` | Inherited (`--system-site-packages`) | PASS |
| `scipy` | `1.17.1` | Inherited (`--system-site-packages`) | PASS |
| `rasterio` | `1.4.3` | Inherited (`--system-site-packages`, includes bundled GDAL) | PASS |
| `geopandas` | `1.1.3` | Inherited (`--system-site-packages`) | PASS |
| `shapely` | `2.1.2` | Inherited (`--system-site-packages`) | PASS |
| `pyproj` | `3.7.2` | Inherited (`--system-site-packages`) | PASS |
| `xarray` | `2025.1.1` | Inherited (`--system-site-packages`) | PASS |
| `fastapi` | `0.133.1` | Inherited (`--system-site-packages`) | PASS |
| `pydantic` | `2.12.5` | Inherited (`--system-site-packages`) | PASS |
| `pytest` | `9.0.3` | Inherited (`--system-site-packages`) | PASS |
| `httpx` | `0.28.1` | Inherited (`--system-site-packages`) | PASS |
| `asf_search` | `14.1.0` | Installed in `.venv` (pure Python wheel) | PASS |
| `pyfive` | `0.5.0` | Installed in `.venv` (100% pure-Python HDF5 v1/v2 reader using stdlib `zlib`) | PASS |
| `h5py` | `3.16.0` | Installed in `.venv` (`D:\`) — **Windows Application Control Note below** | Blocked on `D:\` by OS policy; fallback active |

---

## 3. Windows Application Control / DLL Policy Finding

During import verification in `D:\NASA\SAR2Action\.venv`, Windows Application Control (`應用程式控制原則已封鎖此檔案` / Smart App Control / WDAC) blocked newly downloaded C-extension `.pyd` binaries located on the secondary drive `D:\` (`h5py.h5ds`), whereas all C-extension wheels already installed on `C:\Users\user\AppData\Local\Programs\Python\Python313\Lib\site-packages` (`numpy`, `scipy`, `rasterio`, `shapely`, `pyproj`, `pyogrio`) are trusted by the OS and import cleanly.

### Mitigation & HDF5 Strategy
1. **Pure-Python HDF5 Reader (`pyfive 0.5.0`)**: Installed in `.venv` (`D:\`) with zero `.pyd`/`.dll` files; imports cleanly and reads HDF5 superblocks, groups, attributes, and `zlib`/deflate-compressed datasets using standard-library `zlib` and `numpy`.
2. **If `h5py` C-extension performance is desired in Phase 2/3**: Either create the virtualenv directory on `C:\Users\user\.venvs\sar2action` (trusted `C:\` path) or run an HDF5-to-COG converter via `rasterio`.
3. Phase 1 Gate A is strictly **Metadata-First Discovery** via `asf_search` and `httpx` against official NASA Earthdata CMR / ASF APIs, which operate at 100% capability in `D:\NASA\SAR2Action\.venv`.
