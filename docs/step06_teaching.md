# Step 6 — Folium 互動地圖（Teaching Mode）

> 對應 Build Order 第 6 步：「Game screen with Folium map — markers for all POIs, origin highlighted, no interactivity yet.」

**這一步把 Step 5 的「文字版進行中頁」換成真的互動地圖。** 玩家還不能點 POI（Step 7 才會接），但已經看得到：街道底圖、23 個 marker、起點是黑色旗子、滑鼠移過會出 tooltip、點下去會出 popup。

本步驟新增 / 修改的檔案：
- 新增 `services/map_service.py`（`MapService.render_game_map()`）
- 修改 `app.py`（import + `map_svc` singleton + `/game` route 多傳一個 `map_html`）
- 修改 `templates/game.html`（把 placeholder section 換成 `{{ map_html|safe }}`）
- 修改 `static/style.css`（新增 `.map-wrapper` 樣式）

**驗證結果（本次實際跑出來）**：
| 指標 | 結果 |
|---|---|
| `/new_game`（全 cache）| 0.27 秒 |
| `/game` render | 0.35 秒、38 KB HTML |
| Leaflet CSS / JS 載入 | ✓ |
| `L.marker(...)` 出現次數 | 23（= 22 POI + 1 起點，完全對齊） |
| 起點 lat (`24.79...`) / 「起點」popup / 「清華大學」 | 全部 ✓ |

---

## 1. 各檔案的中文導讀（Plain-English Walkthrough）

### `services/map_service.py`

**做什麼？**
`MapService.render_game_map(gs)` 接收一個 `GameState`，產出一段完整的互動式地圖 HTML 字串，丟回 Flask 用。內部流程：
1. 建一張 `folium.Map`，中心點 = 起點座標、zoom 15（街景級）、底圖 = OpenStreetMap。
2. 跑迴圈，把 `gs.pois`（含起點）每個都加成 `folium.Marker`：
   - 起點：黑色旗子（`Icon(color="black", icon="flag")`）、popup 寫「起點」、tooltip 帶旗子 emoji。
   - 普通 POI：灰色資訊圖示、popup 顯示「名稱 / 類別 / 分數」。
3. 回傳 `m.get_root().render()`：整個 `<!DOCTYPE html><html>...` 字串。

**為什麼這樣設計？**
- **服務類別模式**：和 `POIService` / `OSRMService` 一致 —— 一個檔案只負責一件事（這裡是「把 GameState 變成可看的地圖」），方便測試、方便替換。
- **`get_root().render()` 而非 `.save()`**：CLAUDE.md 在 Architecture 章節明確規定。`.save()` 會寫一個獨立 HTML 檔到磁碟，再讓瀏覽器另外開；我們要的是「inline 到 Flask 回應裡」，所以必須拿到 HTML 字串。
- **起點 vs POI 視覺差異**：旗子 + 黑色一眼看出「這是出發點」。Step 11 再進一步把 player-owned 染藍色、AI-owned 染紅色。

**遊戲流程中何時被呼叫？**
- 每次 `GET /game` 時呼叫一次。地圖每次都是現組現吐 —— Folium 操作很快（~50 ms 等級），不需要 cache 起來。

---

### `app.py`（三個小改動）

1. `from services.map_service import MapService`
2. `map_svc = MapService()` —— 跟 `poi_svc`、`osrm_svc` 一樣的 singleton 模式。
3. `/game` route 多一句 `map_html = map_svc.render_game_map(gs)`，把它跟 `gs`、`total_turns` 一起傳給 template。

**為什麼用 singleton？**
`MapService` 沒有任何 state（不持有 cache、不持有 session），其實 stateless 寫成 module function 也行。用 class 是為了跟其他 service 保持一致風格，未來如果要加 cache（例如同一場遊戲只要 marker 沒變就重用 HTML），改成 instance 就有地方放 cache state。

---

### `templates/game.html`

**改了哪裡？**
舊版的 placeholder section：
```html
<section>
  <h2>地圖（Step 6 才會接上 Folium）</h2>
  <p>起點：{{ gs.origin_display }}</p>
  ...
</section>
```
換成：
```html
<section class="map-wrapper">
  {{ map_html|safe }}
</section>
<p class="hint">起點 <b>{{ gs.origin_display }}</b> · ...</p>
```

**`|safe` filter 是什麼？**
Jinja2 預設**會把所有 `{{ ... }}` HTML-escape**（`<` → `&lt;`、`"` → `&quot;`），這是防止 XSS（cross-site scripting）的內建保護。但我們明確知道 `map_html` 就是合法的 HTML、不能被 escape，所以加 `|safe` 告訴 Jinja「我相信這段、原樣輸出」。

**安全提醒**：`|safe` 只能用在「來源可信」的 HTML。如果哪天 `map_html` 含使用者輸入（比方說 POI 名稱寫進 popup），就要先確保那個輸入已經被 escape 過，否則惡意 POI 名稱可以注入 JavaScript。我們的 popup 內文目前都是 Nominatim 回的 POI 名稱（外部資料、不可 100% 信任），Folium 的 `Popup` 物件其實已經對內容做 escape 了 —— 但如果之後手刻 popup，要留意。

---

### `static/style.css`

新增的 `.map-wrapper` 規則：
```css
.map-wrapper {
  margin: 1rem 0;
  border: 1px solid #bdc3c7;
  border-radius: 6px;
  overflow: hidden;
  min-height: 500px;
}
.map-wrapper .folium-map { height: 500px !important; width: 100% !important; }
```
**為什麼要 `!important`？**
Folium 渲染的 HTML 會把整張 `<html><body>` 塞進來、自帶 inline style。我們的外部 stylesheet 要強制把 `.folium-map` 高度鎖死在 500 px，不然在某些瀏覽器會塌成 0 px 高（看不到地圖、只看到底框）。`!important` 是這種「我必須贏 inline style」場景下不得不用的工具。

---

## 2. 概念卡（Concept Cards）

### 卡 1：Folium 與 Leaflet（地圖渲染的兩層）

| 項目 | 內容 |
|---|---|
| 一句話 | Folium 是 Python 套件，把你寫的 Python code 編成 Leaflet（瀏覽器端 JavaScript 地圖函式庫）能跑的 HTML。 |
| 比喻 | Folium 是「翻譯」，Leaflet 是「演員」。你說中文劇本（Python），Folium 翻成英文（JS），演員（瀏覽器）在台上演出（互動地圖）。 |
| 在我們程式裡 | 後端 Python `MapService.render_game_map()` 用 Folium 物件描述地圖；輸出的 HTML 內含 Leaflet 的 `<script>`、瀏覽器執行後才真正畫出地圖。 |
| 為什麼用 | 我們是 Flask 後端開發者、不想寫 JS。Folium 讓我們只用 Python 就能產出互動地圖；底層仍是業界標準 Leaflet。 |
| 可能被問 | Q：「沒有 JS 怎麼會互動？」 A：「Folium 把 Leaflet 的 JS 一起寫進回應的 HTML 裡，瀏覽器收到後執行 JS 就動起來。我們只是用 Python 在後端組裝這份 HTML。」 |

### 卡 2：伺服器端渲染 vs SPA（Server-Side Rendering vs Single-Page App）

| 項目 | 內容 |
|---|---|
| 一句話 | SSR = 伺服器先把整頁 HTML 組好再吐；SPA = 伺服器只給空殼 + 一坨 JS，由前端 JS 抓 API、自己組畫面。 |
| 比喻 | SSR 像麥當勞外送 —— 廚房做好整份套餐直接送到家。SPA 像 IKEA —— 寄一袋零件 + 說明書，到家自己組。 |
| 在我們程式裡 | 純 SSR：每次 request Flask 一次性吐完整 HTML（含 Folium 地圖），瀏覽器只負責執行 Leaflet 互動。 |
| 為什麼用 | 期末展示用：(1) 沒有 build step（npm 不用裝、webpack 不用學）；(2) 第一次打開就是完整畫面、不會有「白屏等載入」；(3) Demo 講解時程式碼路徑短、好說明。 |
| 可能被問 | Q：「為什麼不用 React？」 A：「SSR 對我們這個遊戲已經夠；引入 React 等於再背一整套生態系，CLAUDE.md 明確規定『no Bootstrap, no React』。」 |

### 卡 3：Jinja `|safe` 與 HTML 自動轉義（Auto-escape & XSS）

| 項目 | 內容 |
|---|---|
| 一句話 | Jinja2 預設把所有變數做 HTML escape，`\|safe` 告訴它「這個變數我擔保是合法 HTML、不要 escape」。 |
| 比喻 | 像郵局收件預設都拆開檢查危險物品；`\|safe` 是「我認證這包裹安全、放行」的章。亂蓋這個章就會出包。 |
| 在我們程式裡 | `{{ map_html\|safe }}`：因為 Folium 輸出本來就是 HTML，escape 掉會變一坨純文字、地圖不會出現。 |
| 為什麼用 | 必要、且唯一需要 `\|safe` 的地方在我們專案是 Folium 地圖。其他 `{{ gs.players.human.ap }}` 之類的純文字維持自動 escape，安全第一。 |
| 可能被問 | Q：「`\|safe` 有什麼風險？」 A：「如果『可信來源』的內容裡有使用者控制的部分（例如 POI 名稱被打成 `<script>alert()</script>`），`\|safe` 會直接讓那段 JS 在瀏覽器執行 —— 這就是 XSS 攻擊。所以使用前要確認 escape 已經在上游做過。」 |

### 卡 4：CDN（內容交付網路）

| 項目 | 內容 |
|---|---|
| 一句話 | 把靜態資源（JS/CSS/字型/圖片）放在全球分散的快取伺服器上，使用者下載時自動連到最近一台。 |
| 比喻 | 像便利商店連鎖體系：與其每樣商品都從台北總部寄貨，每縣市開一家分店、就近領貨。 |
| 在我們程式裡 | Folium 預設用 `cdn.jsdelivr.net` 載 Leaflet 的 JS / CSS、用 `unpkg.com` 載字型；我們的 Flask 伺服器自己不存這些檔。 |
| 為什麼用 | (1) 我們的 Flask 不需要 serve 幾 MB 的 Leaflet 靜態檔，省流量；(2) 全球使用者體感都快；(3) 多個網站共用 CDN，使用者瀏覽器很可能已經有 cache。 |
| 可能被問 | Q：「如果學校網路把 jsdelivr.net 擋掉怎麼辦？」 A：「地圖會顯示不出來。要 demo 安全的話可以下載 Leaflet 的 JS/CSS 放在 `static/leaflet/`，改用本地路徑載入。MVP 假設網路通暢。」 |

### 卡 5：座標順序再次提醒（Leaflet & Folium）

| 項目 | 內容 |
|---|---|
| 一句話 | Folium 與 Leaflet 內部都用 `[lat, lon]`（與 Google Maps、Apple Maps 一致），這跟 OSRM 的 `[lon, lat]` 是反的。 |
| 比喻 | 不同國家郵遞區號順序不同 —— 寄錯就送到隔壁城市。 |
| 在我們程式裡 | `folium.Map(location=[lat, lon])`、`folium.Marker(location=[lat, lon])` 全部 `[lat, lon]`。所以從 OSRM 拿到的 `[lon, lat]` 必須先經 `from_osrm_geometry()` 翻過再丟給 Folium。 |
| 為什麼用 | 這是專案最容易出 bug 的點（CLAUDE.md「Critical Gotchas」第一條），Step 6 又是 lat/lon 大量出現的地方，**重點再講一次**。 |
| 可能被問 | Q：「我如果不小心把 lon/lat 寫反會怎樣？」 A：「marker 會跑到地球的完全錯誤位置 —— 比方說起點清華大學（121, 24）寫反成 (24, 121) 會跑到南極附近的海面，地圖一片藍。」 |

---

## 3. 模擬問答（Mock Q&A）

### Q1（概念）
**問：為什麼用 `m.get_root().render()` 而不是 Folium 的 `m.save("map.html")`？**

`.save()` 會把地圖存成獨立 HTML 檔到磁碟，再讓瀏覽器另外開、跟 Flask 的回應沒關係。我們要的是「跟 HUD、POI 列表、回合資訊全部組在同一個 Flask 回應裡 inline 渲染」，所以必須拿到 HTML 字串、用 Jinja `{{ map_html|safe }}` 注入到 game.html。`get_root().render()` 就是把 Folium 內部組好的整棵 HTML tree 序列化成字串的方法。CLAUDE.md 在 Architecture 章節明確規定要用這個 pattern。

### Q2（走讀）
**問：你的 `render_game_map` 怎麼決定哪個 marker 是起點？**

`gs.pois` 是一個 list of `Place`，起點在 Step 5 被包成 `Place(poi_id="origin", ...)` 塞到 list 的最前面。所以 render 迴圈裡用 `is_origin = (p.poi_id == "origin")` 一行判斷，True 的給黑旗子 + 「起點」popup，False 的給灰資訊圖示 + 「名稱 / 類別 / 分數」popup。`"origin"` 這個字串就是這個專案裡的 magic value，從 Step 5 一路沿用。

### Q3（設計決策）
**問：為什麼把地圖放在 service class 裡，不直接寫在 route function 裡？**

三個理由：(1) **一致性** —— 跟 `POIService`、`OSRMService` 同一個風格，每個 service 一個檔，class 是工程上常用的「可重複使用、可注入」單元；(2) **可測試** —— 未來如果要驗 marker 數量、popup 內容，可以對 `MapService` 寫 unit test，不用啟 Flask；(3) **擴充空間** —— Step 7 要加 click handler、Step 11 要加 owner 染色，這些邏輯放 service 裡組裝，route function 永遠保持「一行呼叫 + render template」的乾淨。

### Q4（修改情境）
**問：如果我想把所有 cafe 顯示成棕色標記，怎麼改？**

`MapService.render_game_map()` 加 dict 對應：
```python
ICON_COLOR_BY_CATEGORY = {
    "cafe": "darkred", "park": "green", "station": "blue", ...
}
icon = folium.Icon(color=ICON_COLOR_BY_CATEGORY.get(p.category, "gray"))
```
但 `folium.Icon` 只支援固定色票（red, blue, green, orange...），無法用 hex 直接給色 —— 我們 `config.py` 的 `PLAYER_COLORS = "#2c7fb8"` 等 hex 不能直接套，要對應到最近的 folium 色名，或改用 `folium.DivIcon` 自己畫 HTML。Step 11 polish 會處理這個對應表。

### Q5（已知限制 / 風險）
**問：你的網頁有 XSS 風險嗎？**

理論上有兩個地方需要警覺：(1) POI popup 顯示 `p.name`，這是 Nominatim 回傳的字串、不是完全可信來源 —— 但 Folium 的 `Popup` 物件會自己做 escape，目前安全；(2) `game.html` 把 `gs.origin_display` 等變數用 `{{ }}` 包，Jinja 自動 escape，也安全。**唯一 `|safe` 的地方是 `map_html` 整段** —— 而那段是我們自己用 Folium 組出來的、沒摻外部輸入，所以可控。但未來如果有人在 popup 裡塞 `f"<script>..."`、又用 `|safe`，就會炸。原則：`|safe` 出現的地方必須回頭審查那個變數的來源鏈。

---

## 4. 學生自我檢查儀式（Self-Check Ritual）

在開始 Step 7 之前，請自己對自己回答這些題目（先合上 IDE）：

- [ ] 我能用一張紙畫出 `request → Flask → MapService → Folium → HTML → 瀏覽器 → Leaflet 渲染` 的完整流程。
- [ ] 我能解釋為什麼地圖必須用 `|safe`、以及這個 filter 在什麼情境下會出大事。
- [ ] 我能說出 Folium 與 Leaflet 的分工。
- [ ] 我能說出 Folium 的 `location` 用 `[lat, lon]`、OSRM 用 `[lon, lat]`，並且能舉例如果反了會發生什麼事。
- [ ] 我知道 Step 7 會在這張地圖上面加什麼（點 POI 移動的 click handler）。

任何一題卡住 → 回對應「概念卡」或「Plain-English Walkthrough」段落重看一次，再開 Step 7。
