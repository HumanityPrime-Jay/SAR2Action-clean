# TW-03｜雲林 NISAR 雙時相

2026-11-14 建置。沿用 TW-01 的 5 × 5 km WGS84 AOI 並保留原始資料。分析只採指定兩景 Provisional P05023、降軌 061／frame 076、左視。取得方式為本機 Earthdata OAuth 與 ASF 原始 HDF5。正式提交重用範圍以 Local Lead 判定為準。

從 SAR2Action 執行 `.\.venv\Scripts\python.exe -B tw03/build_demo.py`。兩景 HDF5 置於 `tw03/inputs`。程式先驗證場景、格網、mask 與頻段，再呼叫既有 Change Engine，並於發布前驗證資產。原始檔與輸出 SHA-256、資料 URL、場景時間及限制列在 manifest。原始 HDF5 留在資料包外。

UI 讀 `nisar-demo-v1/manifest.json` 的 `layers[].overlay.href` 與 `coordinates_lon_lat`，四角順序為左上、右上、右下、左下。PNG 為 Web Mercator 取樣，原生分析在 GeoTIFF。Agent 用 `evidence_href` 取得原始 EvidenceRecord，以 `statistics_href` 取得 HH/HV 統計。所有資產相對於 manifest。

兩期都在薔琵颱風前。結果描述 NISAR L-band 背向散射變化，農損原因與損失金額需獨立證據。與 TW-01 Sentinel-1D 觀測分開引用。

實測 Evidence ID 為 `E-TW03-B82BA14BAC9F8501`，兩期格網均為 EPSG:32651、20 m。AOI 多邊形依引擎的 all-touched 規則包含 63,080 個像元，兩期 mask 均為 class 1 且雙極化功率均有效。EvidenceRecord 的覆蓋率以引擎所用的外接格網視窗 64,770 為分母，得 97.3908%。多邊形內有效比例為 100%，兩個分母的差異來自多邊形外像元。

22 項現行引擎與 Evidence schema 回歸測試通過，1 項無關的既有大型場景測試排除。TW-03 另從本次原始視窗獨立驗算兩個 GeoTIFF 的 mask 與 T1/T0 dB 差值，並通過 EvidenceRecord schema、檔案雜湊、PNG 及 MapLibre 四角順序檢查。前端與 Agent 的接線由後續整合驗收。
