# Step 5 — GameState + Player + 開始新遊戲（Teaching Mode）

> 對應 Build Order 第 5 步：「GameState + Player models + new game route — entering origin geocodes, generates POIs, builds matrix, redirects to `/game`.」

**這一步是整個專案第一次出現網頁。** 之前四步全是 JSON 後端 API，從這一步開始有：
- 起點輸入頁（`/`）
- 遊戲進行中頁（`/game`，內容暫時是文字，Step 6 接 Folium 地圖）

本步驟新增 / 修改的檔案：
- 新增 `models/game_state.py`（`Player`、`GameState` 兩個 dataclass）
- 新增 `services/game_engine.py`（`start_new_game()`、`save_game_state()`、`load_game_state()`）
- 新增 `templates/base.html`、`templates/index.html`、`templates/game.html`
- 新增 `static/style.css`
- 改寫 `app.py`：新增 `/`、`/new_game`、`/game` 三個路由

**驗證結果（本次實際跑出來）**：
| 步驟 | 結果 |
|---|---|
| `GET /` | 200，畫面有起點輸入表單 |
| `POST /new_game?origin=清華大學` | 302 → `/game`，耗時 9.7 秒（22 個新 OSRM 呼叫 + 231 cache hit） |
| `GET /game` | 200，HUD 顯示「回合 1/6、玩家 AP 15、AI AP 15」 |
| 持久化 | `data/games/383ebe1ce4e5.json`（21 KB） |

**怎麼看到畫面**：
```bash
.venv\Scripts\activate
python app.py
```
瀏覽器開 `http://localhost:5000/` → 按「開始遊戲」 → 等 ~10 秒 → 看到 HUD。

---

## 1. 各檔案的中文導讀（Plain-English Walkthrough）

### `models/game_state.py`

**做什麼？**
定義兩個 dataclass：
- `Player`：一邊玩家（human 或 ai）的 `ap`、`owned_pois`、`position`。
- `GameState`：一整場遊戲的所有狀態 —— 包含兩個 Player、POI 清單（含起點）、整張步行時間矩陣、原始起點查詢字串等。

兩個都帶 `to_dict()` / `from_dict()`，讓整個物件能進 JSON、又能讀回來。

**為什麼這樣設計？**
- `Player.position = "origin"`：兩名玩家開局都「站在起點」。把起點當作一個合法的 `poi_id`，可以重用所有 reachability lookup（不用為「玩家還沒走第一步」寫特例）。
- `Player.owned_pois` 是 list of poi_id 字串、不是 list of Place 物件：避免 JSON 同樣的 Place 被序列化兩次（一次在 `pois`，一次在 owned），保持資料的「正規化」。
- `GameState.history` 預留空 list，給 Step 9 的 contest log、Step 10 的 score breakdown 用。

**遊戲流程中何時被呼叫？**
- 玩家按「開始遊戲」 → `start_new_game()` 建一個 `GameState` 物件 → `save_game_state()` 序列化進磁碟。
- 之後每次 `/game` 載入頁面、`/move` 提交（Step 7+），都從磁碟 `load_game_state()` 回來。

---

### `services/game_engine.py`

**做什麼？**
三個 module-level 函式 + 兩個自訂例外：
1. `start_new_game(origin_query, poi_svc, osrm_svc)`：把 Step 2 ~ 4 的所有零件串成一個 `GameState`。
2. `save_game_state(game_id, gs)`：寫 `data/games/{game_id}.json`。
3. `load_game_state(game_id)`：讀回來。

**關鍵設計 1：起點插進 POI 清單最前面**
```python
origin_place = Place(poi_id="origin", value=0, category="generic", ...)
all_places = [origin_place] + pois
matrix = osrm_svc.build_matrix(all_places)
```
這就是 Step 4 教學文件最後一張卡預告的事 —— 把起點當作普通 Place，矩陣自然會包含「起點 ↔ 每個 POI」的時間，第 1 回合的 reachability 就能直接查表。`value=0` 確保起點即使被「擁有」也不會加分。

**關鍵設計 2：dependency injection（依賴注入）**
`start_new_game` 不自己 `POIService()` 一個出來，而是接收呼叫端傳進來的 `poi_svc` / `osrm_svc`。好處是：
- `app.py` 只在啟動時建一次 service singleton，所有 request 共用同一個 `requests.Session`（連線重用）。
- 未來測試時可以丟 mock service 進來，不用真的打網路。

**關鍵設計 3：UUID 當 game_id**
`uuid.uuid4().hex[:12]` 給每場遊戲一個近乎不會撞名的 12 字 ID（如 `383ebe1ce4e5`），同時當作 cookie 值、檔名、log 識別。

**遊戲流程中何時被呼叫？**
- `POST /new_game` → 一次 `start_new_game` + `save_game_state`。
- `GET /game`、`POST /move`（Step 7+）→ 每次都 `load_game_state(session['game_id'])`。

---

### `templates/base.html`

**做什麼？**
所有頁面共用的「殼」—— `<head>`、頂端 banner、CSS 連結。其他模板 `{% extends "base.html" %}` 並覆寫 `{% block title %}` 與 `{% block content %}` 兩個區塊。

**為什麼這樣設計？**
模板繼承（template inheritance）是 Jinja2 的核心模式，避免每個頁面複製貼上整段 `<html>` 骨架；未來改 header、加 nav bar、加 footer 全都改這一個檔案。

---

### `templates/index.html`

**做什麼？**
一個 `<form method="post" action="/new_game">`，預填 `清華大學`，按下按鈕就 POST 起點到後端。額外有 `{% if error %}` 區塊顯示 geocode 失敗或 POI 不足等錯誤。

**為什麼用 POST 不是 GET？**
- 「新建一個遊戲」是會在磁碟產生新檔案的副作用操作 → REST 慣例用 POST，避免被瀏覽器/搜尋引擎重複觸發。
- 表單欄位（origin）放在 request body，URL 保持乾淨。

---

### `templates/game.html`

**做什麼？**
顯示遊戲狀態的 HUD（回合、當前行動方、雙方 AP），加一段佔位文字「Step 6 才會接上 Folium」，加一個可展開的 `<details>` 列出所有 POI 名稱 —— 方便 Step 5 階段的人工驗證。

**設計重點**
- 用 Jinja2 表達式 `{{ '%.1f' | format(gs.players.human.ap) }}` 把 AP 格式化成一位小數。
- 起點旁邊放 🚩 emoji 區別於普通 POI 的 📍，視覺上一眼分清楚。

---

### `static/style.css`

**做什麼？**
最小化 CSS：版面寬 900 px 置中、HUD 用淡灰色 panel、按鈕用主題藍。

**為什麼這麼簡單？**
Step 11「UI styling」會做正式的色彩與互動樣式。這一步只求「不要醜到讓人看不下去」就好，避免提前花時間。

---

### `app.py`（大改造）

**新增的三個路由**

| 路由 | 方法 | 做什麼 |
|---|---|---|
| `/` | GET | 渲染 `index.html` 起點輸入頁 |
| `/new_game` | POST | 跑 `start_new_game` → `save_game_state` → 把 `game_id` 寫進 session → `redirect("/game")` |
| `/game` | GET | 從 session 拿 `game_id` → `load_game_state` → 渲染 `game.html` |

**關鍵設計：兩階段 state**
```python
session.clear()
session["game_id"]        = gs.game_id        # ~12 字
session["turn"]           = gs.turn           # int
session["current_player"] = gs.current_player # "human" or "ai"
session.modified = True
```
完整 `GameState`（含矩陣，~21 KB）寫到 `data/games/{game_id}.json`；session cookie 只放 ~30 bytes 的指標。**為什麼**：Flask 的 signed cookie 上限約 4 KB，整個矩陣放不進去；CLAUDE.md「Flask session size limit」明確規定 session 只放 `game_id`、`turn`、`current_player` 三個。

**Post/Redirect/Get（PRG）pattern**
`/new_game` 處理完不直接 render `game.html`，而是 302 redirect 到 `/game`。如果使用者按重新整理：直接 render 會跳出「您要重送表單嗎？」並把新遊戲再開一次；redirect 之後 URL 變成 `/game`，重新整理只會重讀 `GameState`，不會重建遊戲。

**Debug 路由保留**
`/health`、`/debug/pois`、`/debug/osrm`、`/debug/matrix` 暫時都還在 —— Step 6 之後遊戲頁能展示完整資料，那時再刪。

---

## 2. 概念卡（Concept Cards）

### 卡 1：Flask Session（簽章餅乾）

| 項目 | 內容 |
|---|---|
| 一句話 | Flask 內建的 per-user 字典，預設用「簽章 cookie」儲存在使用者瀏覽器上。 |
| 比喻 | 像遊樂園的手環 —— 上面寫著你買了什麼票券、印上樂園的官方戳章防偽造；下次進場閘門看一眼就知道你的身分。 |
| 在我們程式裡 | `session["game_id"] = gs.game_id` 把 12 字 game_id 簽章後塞進 cookie；下次 `/game` 直接 `session.get("game_id")` 讀回來。 |
| 為什麼用 | 不用建資料庫的 user table 也能維持「同一個人連續多個 request 之間的狀態」；簽章機制讓你即使把 cookie 拷給別人也能用，但別人改不了內容（會驗證失敗）。 |
| 可能被問 | Q：「為什麼不把整個 GameState 都塞進 session？」 A：「signed cookie 限 4 KB，矩陣本身就 18 KB 以上；所以只把 game_id 放 session、其餘存磁碟，這是 CLAUDE.md 規定的 pattern。」 |

### 卡 2：Jinja2 模板（伺服器端 HTML 拼裝）

| 項目 | 內容 |
|---|---|
| 一句話 | Flask 預設的模板引擎，讓我們在 HTML 裡寫 `{{ variable }}` 與 `{% for %}` `{% if %}` 等控制語法，由伺服器先填好再吐給瀏覽器。 |
| 比喻 | 像填字遊戲的母版：HTML 是有挖空的試卷、Python dict 是答案卡、render_template 是老師把答案填上去。 |
| 在我們程式裡 | `render_template("game.html", gs=gs, total_turns=TURNS)`：`gs` 與 `total_turns` 變數在 game.html 內可以直接用 `{{ gs.turn }}`、`{{ total_turns }}`。 |
| 為什麼用 | 比前端 SPA 簡單一萬倍 —— 沒有 build step、沒有 JS framework、第一次 request 就是完整 HTML，最適合期末展示。 |
| 可能被問 | Q：「`{% extends "base.html" %}` 跟 `{% include %}` 差在哪？」 A：「extends 是『繼承並覆寫某幾塊』，include 是『把另一個檔案整個塞進來』；header 全站共用、用 extends 比較乾淨。」 |

### 卡 3：HTTP POST 表單 vs GET 查詢

| 項目 | 內容 |
|---|---|
| 一句話 | GET 把參數放 URL（給「讀取資源」用），POST 把參數放 body（給「會改變伺服器狀態」用）。 |
| 比喻 | GET 像打電話查餘額（只看，不動帳本）；POST 像填轉帳單投進銀行（會動帳本，要存底）。 |
| 在我們程式裡 | `/` 是 GET（只渲染表單頁）；`/new_game` 是 POST（會建新遊戲檔案）。 |
| 為什麼用 | (1) REST 慣例 —— 副作用操作走 POST；(2) GET 會被瀏覽器、爬蟲、瀏覽記錄保留，POST 不會 —— 避免重整一次就多開一場遊戲。 |
| 可能被問 | Q：「為什麼 POST 之後 redirect 到 GET /game，不直接 render game.html？」 A：「這是 Post/Redirect/Get pattern —— 避免使用者按重整時瀏覽器重送 POST、又建一場新遊戲。」 |

### 卡 4：UUID（通用唯一識別碼）

| 項目 | 內容 |
|---|---|
| 一句話 | 128 bit 的隨機字串，全宇宙撞名機率近乎 0，常用作分散式系統的主鍵。 |
| 比喻 | 像台灣身分證字號 —— 不會用人名當主鍵（會撞名、會改），用一組獨立的代號比較安全。 |
| 在我們程式裡 | `uuid.uuid4().hex[:12]` 取前 12 字（如 `383ebe1ce4e5`）當 game_id，當作磁碟檔名 + cookie 值 + log 識別。 |
| 為什麼用 | 在沒有資料庫 auto-increment 的情況下，UUID 是「在客戶端就能本地產出、不會跟別人撞」的最簡解法。 |
| 可能被問 | Q：「為什麼只取前 12 字？整個 32 字會更安全？」 A：「16^12 ≈ 2.8×10^14，期末專案撞名機率可忽略；短一點，cookie 和檔名都比較好讀，log 也比較不雜。」 |

### 卡 5：兩階段狀態（Session-vs-Disk State）

| 項目 | 內容 |
|---|---|
| 一句話 | 把「指標」放 session cookie、「資料本體」放磁碟，cookie 永遠維持小而瀏覽器端讀得到。 |
| 比喻 | 像圖書館 —— 你的「借書證號碼」永遠帶在身上（session），借的書本身放在書架（磁碟），刷證就能找到對應的書。 |
| 在我們程式裡 | session 只存 `{"game_id", "turn", "current_player"}` ≈ 30 bytes；完整 `GameState`（含矩陣）約 21 KB，存 `data/games/{game_id}.json`。 |
| 為什麼用 | (1) Flask signed cookie 上限約 4 KB，矩陣絕對放不下；(2) cookie 越小、HTTP 每次傳輸越快；(3) 磁碟檔可以人工 inspect，bug 重現很方便。 |
| 可能被問 | Q：「如果我把伺服器重開機，遊戲還能繼續嗎？」 A：「能。session cookie 還在瀏覽器、game JSON 還在磁碟，下個 request 一進來照樣 `load_game_state(game_id)`、繼續玩。session 因為是 signed cookie，server 也不存 cookie 本體，所以重開機沒影響。」 |

---

## 3. 模擬問答（Mock Q&A）

### Q1（概念）
**問：為什麼 session 只放 game_id 不放整個 GameState？**

Flask 預設的 session 是「簽章 cookie」—— 把整個字典序列化後簽章存進使用者瀏覽器。cookie 有約 4 KB 的硬上限，但我們一場遊戲的矩陣本身就 18 KB 以上（23×23 浮點數加 POI metadata），絕對塞不下。所以採兩階段：session 只放 game_id（指標），完整 GameState 用 `data/games/{game_id}.json` 存在伺服器磁碟。每次 request 進來看 cookie 拿 ID、讀對應 JSON 還原物件。

### Q2（走讀）
**問：你的 `start_new_game` 為什麼要把 origin 包成一個 `Place` 塞進 list 最前面？**

為了讓「起點到每個 POI 的時間」也自動進矩陣。在 Step 4 我們的 `build_matrix(places)` 是兩兩跑迴圈、產 N×N dict；如果沒把 origin 包成 Place，第 1 回合玩家從起點出發要走到哪、AP 夠不夠，就沒得查表，要寫特例。包成 `Place(poi_id="origin", value=0)` 之後，矩陣是 (N+1)×(N+1)，所有 reachability lookup 不分 origin / POI 統一用 `matrix[position][target]` 一行解決。`value=0` 確保即使誰「擁有」起點也不會加分。

### Q3（設計決策）
**問：為什麼 `/new_game` 處理完要 redirect 到 `/game`，不直接 render `game.html`？**

這叫 Post/Redirect/Get pattern。如果直接 render，使用者按 F5 重整時瀏覽器會跳「您要重送表單嗎？」、按確定就又建一場新遊戲、又跑一次 60 秒的矩陣 build —— 體驗很糟。改 redirect 之後，網址列變成 `/game`，重整只會重做 GET、重讀同一個 game JSON，不會重建。

### Q4（修改情境）
**問：如果使用者把瀏覽器 cookie 清掉，他的遊戲檔還在嗎？**

檔還在 `data/games/{game_id}.json`，但**找不回去了** —— 因為唯一指向那個檔的 game_id 就在 cookie 裡，cookie 清掉就遺失。對 MVP 來說可以接受（一場遊戲 6 回合幾分鐘玩完）；要做長期保存可以加個「遊戲列表」頁，讓使用者用 ID 手動找回，或加 sign-in 把 game_id 綁在帳號上。

### Q5（已知限制）
**問：開遊戲花 10 秒會不會太久？**

對「同一個起點第二次」其實只要 ~1 秒（POI、地理編碼、22 個 origin↔POI OSRM 全部 cache hit）。第一次 10 秒主要是 22 個新的 OSRM 呼叫（起點到每個 POI 的步行路線）。Step 12 會寫 `scripts/warm_cache.py` 在 demo 前先跑一遍把所有東西預熱，demo 當天按下「開始遊戲」就秒開。如果想再快可以用 OSRM `/table/` 端點一次取整片矩陣，但會增加程式複雜度，MVP 不需要。

---

## 4. 學生自我檢查儀式（Self-Check Ritual）

在開始 Step 6 之前，請自己對自己回答這些題目（先合上 IDE）：

- [ ] 我能畫出 request 從瀏覽器到伺服器、到磁碟、再回瀏覽器的完整流程圖。
- [ ] 我能解釋為什麼 session 只放 game_id、其他都放磁碟。
- [ ] 我能說出 Post/Redirect/Get 是什麼、以及為什麼要這樣設計。
- [ ] 我能解釋起點怎麼被當作普通 POI 塞進矩陣，以及為什麼 `value=0`。
- [ ] 我知道下一步（Step 6）會把 `game.html` 裡的「Step 6 才會接上 Folium」那段，換成真正的 Leaflet 互動地圖。

任何一題卡住 → 回對應「概念卡」或「Plain-English Walkthrough」段落重看一次，再開 Step 6。
