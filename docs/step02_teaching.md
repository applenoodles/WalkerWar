# Step 2 — Place Dataclass + POI Generation：Teaching Mode

---

## B. Plain-English Walkthrough

### `utils/decorators.py`

**這個檔案在做什麼：**
提供兩個「功能增強器」給其他函式使用。第一個是 `@log_execution`：幫任何函式自動記錄「它跑了多少毫秒」，不需要在每個函式裡手動寫計時程式碼。第二個是 `@handle_api_errors`：幫呼叫外部 API 的函式加上「安全網」，如果網路斷了、API 回傳錯誤格式，就靜靜地回傳一個預設值（`None` 或空 list），而不是讓整個程式崩潰。

**引入的關鍵概念：**
- Decorator（裝飾器）：用 `@` 符號掛在函式上，在不改變函式本身的情況下為它增加新行為。
- `functools.wraps`：保留原函式的名稱和 docstring，讓 log 訊息顯示正確名字。
- `default_factory`（工廠函式）：是一個「能生產預設值的函式」。用函式而不是直接用值，是因為像 `list()` 每次都要建新 list，不能共享同一個物件。

**為什麼這樣設計：**
把重複的「計時」和「錯誤處理」提取出來放在 `decorators.py`，是「DRY 原則（Don't Repeat Yourself）」的實踐。`poi_service.py`、`osrm_service.py` 都要用，只需 import 這兩個裝飾器，不用各自重複寫同樣的 try/except。

**何時執行：**
每次被裝飾的函式被呼叫時自動執行。例如 `poi_svc.geocode("清華大學")` → handle_api_errors wrapper 啟動 → log_execution wrapper 啟動 → 真正的 `geocode()` 執行 → 計時結束，log 輸出 → 回到 handle_api_errors wrapper → 如果沒錯誤就正常回傳。

---

### `models/place.py`

**這個檔案在做什麼：**
定義「遊戲節點」的資料結構。一個 `Place` 就是地圖上一個可被玩家走到並佔領的地點（咖啡廳、公園、車站……）。它存著地點的座標、類別、分值、OSM 的唯一 ID。它知道如何把自己轉成 JSON（`to_dict`）、從 JSON 還原（`from_dict`）、或從 Nominatim 的原始回傳直接建立（`from_nominatim`）。

**引入的關鍵概念：**
- Dataclass：用 `@dataclass` 裝飾器自動產生 `__init__`、`__repr__` 等樣板程式碼，讓我們只需宣告「有哪些欄位」即可。
- Type hint（型別提示）：如 `lat: float` 告訴讀者和 IDE 這個欄位應該是浮點數。
- `Optional[Place]`：意思是「回傳 Place 物件，或 None」。對應 Nominatim 搜尋可能找不到有效地點的情況。

**為什麼這樣設計：**
用 dataclass 而不是 dict，是因為：(1) 有欄位名稱提示（`place.lat` 比 `d["lat"]` 更清楚）；(2) 有 `from_nominatim` 這樣的 classmethod 封裝複雜的解析邏輯；(3) `GameEngine` 和 `AIService` 之後能用型別提示確認傳的是 `Place` 而非隨機 dict。

**何時執行：**
`poi_service.py` 的 `generate_pois` 每找到一個 Nominatim 地點時，呼叫 `Place.from_nominatim(raw, category)` 建立 `Place` 物件；存檔時呼叫 `place.to_dict()`；讀取快取時呼叫 `Place.from_dict(d)` 還原。

---

### `services/poi_service.py`

**這個檔案在做什麼：**
這個服務的工作是「把地圖變成遊戲棋盤」。`geocode()` 把玩家輸入的地名（`"清華大學"`）轉成經緯度；`generate_pois()` 再以那個座標為中心，向 Nominatim 詢問周圍的咖啡廳、公園、車站……，整理成 `Place` 物件的列表。結果都存在 `data/cache/poi/` 資料夾，下次遇到同樣查詢直接讀檔案。

**引入的關鍵概念：**
- Geocoding：把「地名字串」轉換成「經緯度座標」的過程。
- Bounding box（包圍框）：以中心點和半徑計算出矩形範圍，告訴 Nominatim「只要這個方框內的地點」。
- `requests.Session`：HTTP 連線的設定集合，把固定的 header（User-Agent）和 `verify=False`（跳過 SSL 憑證驗證，解決校園網路問題）設定一次，之後每次請求都自動帶上。
- `NOMINATIM_RATE_LIMIT_SEC = 1.05`：每次請求之間至少等 1.05 秒，是 Nominatim ToS 要求，防止因為速率過快被封鎖。

**設計決策說明：**
- **Multi-keyword fallback（多關鍵字備援）**：每個類別試多個關鍵字是因為 Nominatim 在台灣校園附近的英文標籤不足，`"cafe"` 可能找不到，但 `"咖啡"` 可以找到。
- **`countrycodes=tw`**：限制搜尋台灣，避免 `"清華大學"` 誤抓北京清華大學（同名不同地！）。
- **只快取成功的結果**：只有 ≥ `POI_FLOOR`（15個）的結果才存快取，失敗的結果不存，下次還是會重試。

**何時執行：**
玩家按下 Start Game → `/new` 路由 → `poi_svc.geocode()` → `poi_svc.generate_pois()` → 回傳 `Place` 列表給 `GameEngine` → 建立遊戲狀態。整個過程只在遊戲「開始時」發生一次。

---

### `app.py`（修改部分）

**修改了什麼：**
加入了 `from services.poi_service import ...` 和 `poi_svc = POIService()`，以及臨時的 `/debug/pois` 路由，讓我們可以用瀏覽器或 curl 直接測試 POI 生成。Step 5 完成後這個路由會被移除。

---

## C. Concept Cards

### Class（類別）

**是什麼：** 把相關的資料（屬性）和操作（方法）綁在一起的藍圖。用這個藍圖可以製造出很多具有相同結構的物件（實例）。

**比喻：** 「咖啡廳類別」是藍圖；你家附近三家咖啡廳是三個實例，每個都有自己的名字和座標，但都符合同一個藍圖的結構。

**在程式中的位置：** `Place`、`POIService`、`OSRMService`、`GameEngine`、`AIService`、`MapService` 都是 class。

**為什麼用：** 把 `POIService` 的 session、快取目錄、headers 等細節封裝進一個物件，外部只需要呼叫 `poi_svc.geocode("清華大學")`，不需要知道裡面怎麼發 HTTP request。

**教授可能問：**「為什麼 `geocode` 是 `POIService` 的方法，而不是一個獨立函式？」
**好答案：**「因為 `geocode` 和 `generate_pois` 共用同一個 session（HTTP 連線設定）和快取目錄。把它們放進同一個 class，讓這些共用狀態集中在一個地方管理，不用到處傳 headers 或 cache_dir 參數。」

---

### Dataclass（資料類別）

**是什麼：** 用 `@dataclass` 裝飾器裝飾的 class。Python 會自動為它生成 `__init__`（建構子）、`__repr__`（印出來長什麼樣）等方法，讓我們只需要用 `field_name: type` 聲明欄位即可。

**比喻：** 一般的 class 是自己蓋房子；dataclass 是買系統廚具組 — 你宣告「要有水槽、爐台、冰箱」，剩下的組裝交給 Python。

**在程式中的位置：** `Place`、`Player`、`GameState` 都是 dataclass。

**為什麼用：** 省去寫 `__init__(self, poi_id, name, lat, lon, ...)` 的樣板程式碼；新增欄位只需加一行宣告；自帶 `__repr__` 讓 debug 時可以直接 print 物件。

**教授可能問：**「`Place` 是 dataclass，`POIService` 是普通 class，差別在哪？」
**好答案：**「`Place` 是純粹的資料容器（持有一個地點的資訊），適合用 dataclass；`POIService` 有複雜的初始化邏輯（建 session、建目錄），也有很多行為（geocode、generate_pois、_search），這種有邏輯的物件用普通 class 更清楚。」

---

### Decorator（裝飾器）

**是什麼：** 放在函式定義前面（`@xxx`），在不修改函式原始碼的情況下，為它增加額外行為的語法。本質上是「以原函式為輸入、回傳新函式」的高階函式。

**比喻：** 就像給手機套保護殼 — 手機本身不變，但現在有了防摔功能。`@handle_api_errors` 是保護殼，`geocode` 是手機。

**在程式中的位置：**
- `@log_execution`：幫函式加計時日誌
- `@handle_api_errors(default_factory=lambda: None)`：幫 API 函式加安全網

**為什麼用：** 如果不用 decorator，每個 API 函式都要自己寫 try/except 和計時邏輯，造成很多重複程式碼。Decorator 讓這些「橫切關注點」集中在一個地方。

**教授可能問：**「`@handle_api_errors` 在 `@log_execution` 外面，為什麼這個順序？」
**好答案：**「Python 的 decorator 由內而外應用。`@log_execution` 先把 `geocode` 包成 `logged_geocode`；`@handle_api_errors` 再把 `logged_geocode` 包成 `safe_geocode`。呼叫時：`safe_geocode()` → `logged_geocode()` → `geocode()`。如果 `geocode` 丟出 `SSLError`，它穿透 log wrapper，最終被 `handle_api_errors` 捕捉並回傳 `None`。這個順序確保錯誤總是被最外層的 `handle_api_errors` 捕捉。」

---

### Type hint（型別提示）

**是什麼：** 在 Python 函式或變數旁邊標注「預期的型別」。Python 不強制執行，但 IDE 和靜態分析工具可以用它抓出錯誤。

**比喻：** 像樂高積木上的「建議年齡 8+」標示 — 不阻止 6 歲小孩玩，但告訴讀者這個積木適合誰用。

**在程式中的位置：**
- `def geocode(self, query: str) -> Optional[dict]:` → query 應該是字串；回傳值是 dict 或 None
- `list[Place]` → 一個存放 Place 物件的 list

**為什麼用：** (1) 文件作用：看函式簽名就知道傳什麼、得到什麼；(2) IDE 補全：VS Code 看到型別後才能提供正確的屬性建議。

**教授可能問：**「`Optional[dict]` 是什麼意思？」
**好答案：**「`Optional[X]` 等同於 `Union[X, None]`，意思是函式可能回傳 X 型別的值，也可能回傳 `None`。我們用它標記 `geocode`：查得到就回傳 dict，查不到就回傳 None，呼叫端需要先 `if loc is not None` 再使用。」

---

### HTTP request / REST API

**是什麼：** HTTP request 是我們的程式透過網路向另一台伺服器「發出請求」的動作。REST API 是一種設計規範：用 GET 取資料、用 POST 新增/修改，URL 代表資源，回應通常是 JSON。

**比喻：** 像是打電話去圖書館查書：你說出書名（URL + 參數）→ 館員找書（伺服器處理）→ 告訴你在哪一排（JSON 回應）。

**在程式中的位置：** `poi_service.py` 用 `self._session.get()` 呼叫 Nominatim 的 REST API；`osrm_service.py`（Step 3）也用同樣方式呼叫 OSRM。

**為什麼用：** Nominatim 和 OSRM 是公開的地圖服務，提供 REST API 讓任何人查詢，不需要自己建資料庫或下載地圖。

**教授可能問：**「如果 Nominatim API 掛了怎麼辦？」
**好答案：**「兩層防護：(1) `@handle_api_errors` 捕捉 `requests.Timeout` 等錯誤，回傳 `None` 而不是崩潰；(2) 快取機制讓已查過的結果存在磁碟，即使 demo 當天 API 斷線，只要快取有資料就能繼續運作。」

---

### Cache（快取）

**是什麼：** 把「一個問題的答案」存起來，下次遇到同樣問題就直接拿存的，不用重新計算或重新查詢。

**比喻：** 像你把某道數學題的解題過程抄在便條紙上 — 下次遇到一樣的題目，直接看便條紙，不用再算一遍。

**在程式中的位置：**
- `data/cache/poi/geocode_{hash}.json`：把地名查詢的結果存起來
- `data/cache/poi/pois_{lat}_{lon}_{radius}.json`：把 POI 列表存起來
- `data/cache/osrm/…`（Step 3）：把 OSRM 步行時間存起來

**為什麼用：** Nominatim 限制每秒最多 1 次請求，20 個 POI 的矩陣需要 190 次 OSRM 呼叫。沒有快取，每次啟動遊戲都要等好幾分鐘。有了快取，第二次之後直接讀磁碟（0.13 秒），demo 流暢無比。

**教授可能問：**「快取存在磁碟而不是記憶體，有什麼好處？」
**好答案：**「記憶體快取在程式重啟後就消失。磁碟快取重啟之後還在，特別適合我們 demo 的場景 — 昨天預熱的快取今天還能用。」

---

### Bounding box（包圍框）

**是什麼：** 以一個中心點和半徑，算出的四邊形「框框」，用來告訴地圖 API「只要這個區域內的資料」。

**比喻：** 在地圖上用手指框出一個範圍，然後說「只要框裡面的地點」。

**在程式中的位置：** `poi_service.py` 的 `_viewbox()` 方法：
```
delta_lat = radius_m / 111_111
delta_lon = radius_m / (111_111 * cos(lat))
→ left, top, right, bottom = lon-δ, lat+δ, lon+δ, lat-δ
格式：lon_min, lat_max, lon_max, lat_min（Nominatim 規定這個順序）
```

**為什麼用：** 讓 Nominatim 只回傳清大附近 1.5 公里內的地點，不然「cafe」可能找到台北的咖啡廳。

**教授可能問：**「為什麼 `delta_lon` 要乘以 `cos(lat)`？」
**好答案：**「地球是球形的。在赤道（lat=0），東西方向 1 度 ≈ 111 公里；越往高緯度，同樣 1 度的東西距離越短（因為緯度圓越小）。乘以 `cos(lat)` 是把球面幾何校正成平面近似，在 24 度（新竹緯度）約是 `cos(24°) ≈ 0.91`，影響約 9%。」

---

### Geocoding（地理編碼）

**是什麼：** 把一個地名或地址字串（`"清華大學"`）轉換成精確的經緯度座標（lat=24.7917, lon=120.9924）的過程。反過來（座標→地名）叫 reverse geocoding。

**比喻：** 像是查電話簿：你知道一個人的名字，查到他的電話號碼（座標）。

**在程式中的位置：** `POIService.geocode(query)` → Nominatim `/search` API → 返回 `{'lat': 24.7917, 'lon': 120.9924, 'display_name': '...'}`

**重要注意：** 我們加了 `countrycodes=tw` 限制搜尋台灣，避免 `"清華大學"` 找到北京清華大學（同樣的名字，不同的地方！）

**教授可能問：**「如果使用者輸入一個找不到的地方怎麼辦？」
**好答案：**「`geocode` 回傳 `None`，`app.py` 的 `/new` 路由檢查到 `None` 就 flash 錯誤訊息 '找不到地點，試試別的起點' 然後 redirect `'/'` 讓使用者重新輸入。」

---

## D. Mock Q&A

**Q1 [Concept]**：什麼是 Decorator（裝飾器）？你在哪裡用到它？

**A1：** Decorator 是一種語法，用 `@` 掛在函式前面，在不改變函式本身的情況下為它增加行為。它的本質是「接受一個函式、回傳一個新函式」。我們有兩個 decorator：`@log_execution` 幫任何函式記錄「跑了多少毫秒」；`@handle_api_errors(default_factory=...)` 幫 API 函式加 try/except 安全網，失敗時回傳 `default_factory()` 而不是讓程式崩潰。

**必提要點：** `@` 語法、高階函式、`functools.wraps` 保留函式名稱、`@handle_api_errors` 在外 / `@log_execution` 在內的裝飾順序、`default_factory` 為什麼是函式。

---

**Q2 [Walkthrough]**：帶我走過 `from_nominatim` 這個 classmethod，解釋每個步驟。

**A2：**
1. 嘗試從 `namedetails.get("name")` 取名字；如果沒有，就用 `display_name` 的第一個逗號前面那段（通常是地名）。如果兩個都空，就 `return None`（這個地點沒有名字，不值得加入遊戲）。
2. 把 `raw["lat"]` 和 `raw["lon"]` 轉成 `float`（Nominatim 回傳字串）；如果解析失敗就 `return None`。
3. 用 `"{osm_type}_{osm_id}"` 建立穩定的 `poi_id`（跨執行都不變）。
4. 從 `config.POI_CATEGORIES` 查這個類別的分值。
5. 回傳一個新的 `Place` 物件。

**必提要點：** `.get()` everywhere（不假設 Nominatim 回傳特定欄位）、`float()` 轉型（Nominatim 給字串）、`poi_id` 的穩定性。

---

**Q3 [Design Decision]**：`generate_pois` 為什麼要試多個關鍵字，而不是一個？

**A3：** 台灣（尤其校園附近）的 OSM 資料英文標籤不完整。用 `"cafe"` 在清大附近可能只找到 1–2 家，但 `"咖啡"` 能找到更多。每個類別設定 `keywords` 列表（`["cafe", "coffee", "咖啡"]`），依序試，直到有 ≥ 3 個地點為止，再換下一個類別。如果所有類別試完還不到 `POI_FLOOR`（15個），就用 generic fallback 再撈 `"amenity"` 標籤的地點補足。如果還是不夠，就 `raise NotEnoughPOIsError`，`/new` 路由捕捉並提示使用者換個起點。

**必提要點：** 台灣 OSM 中英文標籤不完整的現實、`POI_FLOOR` 的作用、`NotEnoughPOIsError` → 友好的錯誤訊息。

---

**Q4 [Concept]**：為什麼快取只存成功的結果，失敗的不存？

**A4：** 如果我們把「找不到 POI」的結果也快取起來，下次查同一個起點就永遠顯示錯誤，即使那個地點後來有更多 OSM 資料了。只快取「有效、足夠的結果（≥ `POI_FLOOR`）」，可以讓失敗的查詢在下次嘗試時重新試一次。對於成功的結果，快取確保 demo 當天不需要再打 Nominatim。

**必提要點：** 防止永久快取錯誤狀態、成功才寫 `cache_path.write_text(...)`。

---

**Q5 [Modification]**：如果要把 POI 搜尋半徑從 1500m 改成 2000m，怎麼做？

**A5：** 改 `config.py`：`POI_RADIUS_M = 2000`。然後刪除舊的 POI 快取（`data/cache/poi/pois_*.json`），因為快取 key 含半徑（`pois_{lat}_{lon}_{radius_m}.json`），舊快取對新半徑無效。重啟 Flask 後第一次查詢會重新生成更大範圍的 POI。

**必提要點：** 只改 `config.py`（single source of truth）、快取 key 含 radius、刪快取讓它重新生成。

---

## 學生自我檢驗儀式（Step 2 結束後做）

1. 打開 `data/cache/poi/pois_*.json`（用文字編輯器）。看一個條目，找出哪個 JSON 欄位變成了 `place.name`。
2. 在 `MY_NOTES.md` 裡寫：「`Place` 是什麼？為什麼用 dataclass 而不是普通 dict？」用自己的話，不要複製這份文件。
3. 試著口頭回答：「玩家填好起點按送出之後，`POIService` 做了哪些事，step by step？」
4. 試著口頭回答上面 5 個 Mock Q&A。答得出來就繼續 Step 3；答不出來就再讀一遍 Walkthrough。
