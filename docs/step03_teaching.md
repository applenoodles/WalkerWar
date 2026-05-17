# Step 3 — OSRM 單次查詢 + 座標工具（Teaching Mode）

> 對應 Build Order 第 3 步：「OSRMService + coords helpers — single pairwise walking time query, cached.」

本步驟新增 / 修改的檔案：
- 新增 `utils/coords.py`
- 新增 `services/osrm_service.py`
- 修改 `app.py`（加入 `osrm_svc` 與 `/debug/osrm` 路由）

---

## 1. 各檔案的中文導讀（Plain-English Walkthrough）

### `utils/coords.py`

**這個檔案在做什麼？**
只有兩個迷你函式，專門處理「(緯度, 經度) 在不同 API 之間順序不一致」這件事。
- `to_osrm_coords(lat, lon)`：把 `(lat, lon)` 轉成 OSRM URL 路徑要的 `"lon,lat"` 字串。
- `from_osrm_geometry(geojson_coords)`：把 OSRM 回傳的 `[[lon, lat], ...]` 翻成 Folium 要的 `[[lat, lon], ...]`。

**這裡引入的關鍵概念**
- **純函式（Pure function）**：給相同輸入永遠得到相同輸出，不讀檔、不打網路、不修改外部狀態。
- **集中化（Centralization）**：CLAUDE.md 在「Critical Gotchas」明確警告，座標順序錯亂是這個專案最常見的 bug。把這兩個函式集中起來，等於規定全專案都只能呼叫它們，不能自己手刻字串拼接。

**為什麼這樣設計？**

| 來源 / 目標 | 用的順序 |
|---|---|
| Nominatim 回傳 | `(lat, lon)`（字串） |
| OSRM URL 路徑 | `"lon,lat;lon,lat"` |
| OSRM `geometry.coordinates` | `[[lon, lat], ...]` |
| Folium / Leaflet | `[lat, lon]` |

四個地方有兩種順序混在一起，遲早會出現「明明應該在新竹、結果地圖卻畫在台北外海」的詭異 bug。集中之後，未來若要改邏輯只需要動這一個檔案。

**遊戲流程中何時被呼叫？**
- `OSRMService` 組 URL 時 → 呼叫 `to_osrm_coords`。
- `OSRMService` 把路線存進 cache / 之後 Folium 畫線時 → 呼叫 `from_osrm_geometry`。

---

### `services/osrm_service.py`

**這個檔案在做什麼？**
`OSRMService` 是一個負責「問 OSRM 兩點之間怎麼走、要走多久」的服務類別：
1. 收到兩個 `(lat, lon)` tuple。
2. 先看磁碟有沒有 cache 過這條路線（symmetric key，A→B 和 B→A 共用）。
3. 沒有就打 OSRM `/route/v1/foot/{coords}` REST API，把回傳 JSON 裡有用的三個欄位（`duration_min`, `distance_m`, `geometry`）整理成乾淨 dict、存進 cache 後回傳。
4. 失敗（網路、SSL、解析錯誤）一律回傳 `None`，不會炸到呼叫者。

**這裡引入的關鍵概念**
- **GeoJSON**：OSRM `routes[0].geometry` 是 GeoJSON LineString；它的 `coordinates` 規定要 `(lon, lat)`，所以一定要經過 `from_osrm_geometry()` 翻過才能丟給 Folium。
- **對稱 cache key**：用 `tuple(sorted([a, b]))` 排好順序再 sha256 雜湊，A→B 跟 B→A 會 hash 到同一個檔名 → Step 4 的 N×N 矩陣 API 用量直接砍半（變 N·(N-1)/2）。
- **Session 重用**：`requests.Session()` 會保留 TCP 連線、預設 header，連續打多次 request 比每次 `requests.get()` 快很多。Step 4 一次要打 ~190 次 OSRM，這個差距會很明顯。
- **`verify=False` + `urllib3.disable_warnings`**：在學校 / 公司網路常會遇到 SSL 中間人攔截，跟 `poi_service.py` 解的是同一個問題。

**為什麼這樣設計？**
- 只把「最有用」的三個欄位寫進 cache，不存整包 OSRM 回應。cache 檔變小、未來換 API 也比較好相容。
- `get_walking_time` 故意做成 `get_walking_route` 的薄包裝（讀 cache 後取 `duration_min`），避免兩個方法各自打 API、各自存 cache 檔。
- 失敗時回傳 `None`，符合 `Optional[dict]` 型別宣告，呼叫端只需要 `if route is None:` 就能 graceful fallback。

**遊戲流程中何時被呼叫？**
- Step 3：暫時只在 `/debug/osrm` 路由，用第一、第二個 POI 驗證 API 通了。
- Step 4：建立 N×N 步行時間矩陣，每個 cell 都會呼叫一次。
- Step 5 ~ 10：所有「能不能走到」、「contest 比誰快」的判定都從矩陣讀，回合中不會再打 OSRM。

---

### `app.py`（新增的兩處）

**新增了什麼？**
1. `from services.osrm_service import OSRMService` + `osrm_svc = OSRMService()` —— 跟 `poi_svc` 一樣，啟動時就建好一個全域單例。
2. `@app.get("/debug/osrm")` 路由 —— 拿 `/debug/pois` 同樣的 POI 清單，取前兩個 POI 算一次步行路線、回傳整理好的結果。

**為什麼這樣設計？**
- 純粹是這一步的「驗證收據」。等 Step 5 開始接 `/game` 流程時，這個 route 連同 `/debug/pois` 會一起拆掉。
- 回傳故意 `round()` 過，且 geometry 只回 `len(geometry)` 加第一個點，避免回應太肥；要看完整 geometry 直接讀 cache 檔。

**驗證結果（本次實際跑出來）**

```json
{
  "from": {"name": "影咖啡 Inn Caffe將軍村門市", "lat": 24.7944552, "lon": 121.0027524},
  "to":   {"name": "清心福全", "lat": 24.7914207, "lon": 121.0042621},
  "duration_min": 1.4,
  "distance_m":   692.2,
  "geometry_points": 25,
  "first_geom_point": [24.794251, 121.002887]
}
```

`first_geom_point` 是 `[lat, lon]`（24.79, 121.00）—— 確認 `from_osrm_geometry` 確實有把 OSRM 的順序翻對了。

---

## 2. 概念卡（Concept Cards）

### 卡 1：純函式（Pure Function）

| 項目 | 內容 |
|---|---|
| 一句話 | 給相同輸入永遠得到相同輸出、且不會修改任何外部狀態的函式。 |
| 比喻 | 像自動販賣機投硬幣 → 出固定飲料：投同樣硬幣永遠出同款飲料，也不會偷偷改它自己的庫存表給別人看。 |
| 在我們程式裡 | `utils/coords.py` 兩個函式都是純函式：沒 I/O、沒亂數、沒修改外部變數。 |
| 為什麼用 | 最容易測試、最容易讓口試委員瞬間看懂、最不會在團隊合作時偷偷產生副作用。 |
| 可能被問 | Q：「為什麼這兩個函式不寫在 `osrm_service.py` 裡？」 A：「因為它們是純函式，跟 OSRM 本身沒邏輯關聯，未來 Folium 顯示、AI 計算都會用到，集中放在 utils 比較好重用。」 |

### 卡 2：GeoJSON

| 項目 | 內容 |
|---|---|
| 一句話 | 一種用 JSON 表達地理形狀（點、線、面）的開放標準。 |
| 比喻 | 像 `.docx` 之於文字、`.png` 之於圖片，是「地理形狀」這類資料的通用檔案格式。 |
| 在我們程式裡 | OSRM 回傳的 `routes[0].geometry` 就是 GeoJSON LineString；它的 `coordinates` 是 `[[lon, lat], ...]`。 |
| 為什麼用 | 是業界標準，OSRM、Folium、Leaflet、QGIS 都吃 GeoJSON。我們只要把座標順序翻對就能跨工具用。 |
| 可能被問 | Q：「為什麼 GeoJSON 用 (lon, lat) 而不是大家比較熟的 (lat, lon)？」 A：「GeoJSON 沿用了數學上 `(x, y)` 的習慣，把 longitude 當 x、latitude 當 y。所以才要在我們的 `utils/coords.py` 集中翻成 Folium 要的 (lat, lon)。」 |

### 卡 3：Tuple（元組）

| 項目 | 內容 |
|---|---|
| 一句話 | Python 的「不可變、有序」序列，用括號寫成 `(a, b, c)`。 |
| 比喻 | 跟 list 像兄弟，但 tuple 一旦建好就不能改 —— 比較像「身分證上的姓名、出生日期」，list 像「購物車」。 |
| 在我們程式裡 | `OSRMService` 用 `tuple[float, float]` 當 `(lat, lon)` 的型別；`_cache_path()` 用 `tuple(sorted([a, b]))` 當對稱 cache key。 |
| 為什麼用 | tuple 可以被 hash（list 不行），所以可以丟進 `set` 或當 dict 的 key、或丟給 sha256。 |
| 可能被問 | Q：「為什麼不直接用 list `[lat, lon]`？」 A：「list 在 Python 是 mutable、不能被 hash，所以無法被拿來組合成 cache key。」 |

### 卡 4：對稱 Cache Key（Symmetric Cache Key）

| 項目 | 內容 |
|---|---|
| 一句話 | 把「A→B」和「B→A」視為同一筆資料、共用同一個 cache 檔，省一半 API 呼叫。 |
| 比喻 | 像 LINE 群組裡兩個人聊天，無論誰先傳訊息，這條對話只會有一個聊天視窗，不會因為發起人不同就再開一個。 |
| 在我們程式裡 | `_cache_path()`：先把兩個座標各 `round(_, 5)`（~1 m 精度），再 `tuple(sorted([a, b]))`，最後 sha256 取前 16 字。 |
| 為什麼用 | 步行 A→B 和 B→A 在 foot routing 下時間相同；cache 合起來，Step 4 的 N×N 矩陣只要算一半。 |
| 可能被問 | Q：「如果是單行道，B→A 不就跟 A→B 不一樣？」 A：「對車輛確實會不一樣；但 OSRM 的 foot profile 假設行人兩個方向都能走，所以對 walking time 來說是對稱的。如果之後改用 driving，這個假設要重新評估。」 |

### 卡 5：HTTP 路徑參數 vs 查詢參數（Path Param vs Query Param）

| 項目 | 內容 |
|---|---|
| 一句話 | URL `/foo/123` 那個 `123` 是「路徑參數」，`?key=value` 那段是「查詢參數」，語意不同。 |
| 比喻 | 路徑參數像「房號 502」（指定資源本身）；查詢參數像門上掛的「請打掃」「請勿打擾」標牌（修飾資源的呈現）。 |
| 在我們程式裡 | OSRM URL：`https://router.project-osrm.org/route/v1/foot/{coords}?overview=full&geometries=geojson`。座標放在路徑（指定要算哪兩點），`overview` / `geometries` 放 query（控制回傳的細節）。 |
| 為什麼用 | REST 風格慣例：路徑表達「是哪個資源」，query string 表達「要怎麼看」。 |
| 可能被問 | Q：「為什麼座標不也用 query string？」 A：「OSRM 把座標當成識別這條 route 的主鍵、放在路徑符合 REST 慣例；overview 是次要選項才放 query。」 |

---

## 3. 模擬問答（Mock Q&A）

### Q1（概念）
**問：「對稱 cache key」是什麼？為什麼這樣設計？**

我把兩個座標各四捨五入到小數第 5 位（約 1 公尺精度），用 `tuple(sorted([a, b]))` 排序後再 sha256 取前 16 字當檔名。這樣 A→B 和 B→A 會算出一模一樣的檔名，cache 自動共用，到 Step 4 建距離矩陣時只要打 N·(N−1)/2 次 API、不用 N²。對行人來說兩方向時間相同，這個對稱假設是 OK 的。

### Q2（走讀）
**問：為什麼 `get_walking_time` 寫成 `get_walking_route` 的小包裝？**

避免重複呼叫 OSRM。如果兩個方法各自打一次 API、各自存自己的 cache 檔，當我已經有完整路線時、只想知道時間就會再多打一次。改成 `get_walking_time` 直接讀已經 cache 好的 route dict 裡的 `duration_min`，永遠只打一次 API，cache 也只占一個檔案。

### Q3（設計決策）
**問：為什麼座標轉換函式要寫在 `utils/coords.py`，不直接寫在 `osrm_service.py` 裡？**

三個理由：(1) 座標順序這件事在這個專案有四個地方（Nominatim、OSRM URL、OSRM geometry、Folium）會用到，未來 Folium 渲染、AI 計算都會 import 它；(2) 它是純函式，跟 OSRM 邏輯解耦，獨立測試最容易；(3) CLAUDE.md 警告「座標順序錯亂是這個專案最常見的 bug」，集中起來才能單點修正。

### Q4（修改情境）
**問：如果我想把試玩地點換成台北市區，需要改哪裡？**

基本上只要改 `app.py`（或之後 `/new_game` 表單）的 `"清華大學"` 字串就好，POIService 跟 OSRMService 都不用動。注意：(1) `config.POI_RADIUS_M`（1.5 km）在大都會可能會抓太多 POI，到時可以調小；(2) cache 是用座標 hash，所以新地點會自動建新檔，不會跟舊資料衝突。

### Q5（已知限制 —— 一定會被問）
**問：你印出來 692 m 走 1.4 分鐘合理嗎？**

嚴格說不合理 —— 1.4 分鐘走 692 公尺等於時速 30 km/h，這是車速不是步速。公開的 `router.project-osrm.org` 雖然接受 `/foot/` 路徑，但實際底下仍是車的速度模型。對 Step 3 我只是驗證 API 通了；到 **Step 4 建矩陣** 時我會加一層「用 OSRM 回傳的 `distance_m` 除以行人速度（約 5 km/h）」的轉換，讓 AP=15 分鐘真的代表 15 分鐘步行。這個決策會在 Step 4 一開始重新確認後再下手。

---

## 4. 學生自我檢查儀式（Self-Check Ritual）

在開始 Step 4 之前，請自己對自己回答這些題目（先合上 IDE，不可以邊看程式邊背）：

- [ ] 我能不看程式碼，畫出 `utils/coords.py` 兩個函式的「輸入 → 輸出」格式。
- [ ] 我能解釋為什麼 cache key 是「sorted + sha256」而不是直接用座標字串拼起來。
- [ ] 我能說出 OSRM 回傳的 `geometry.coordinates` 跟 Folium 要的 `[lat, lon]` 差在哪裡。
- [ ] 我能舉一個「如果 OSRM 失敗，程式會怎麼反應」的例子（提示：`@handle_api_errors` + `None`）。
- [ ] 我知道公開 OSRM 伺服器其實回的是車速，以及 Step 4 我打算怎麼補救。

任何一題卡住 → 回到對應「概念卡」或「Plain-English Walkthrough」段落重看一次，再開 Step 4。
