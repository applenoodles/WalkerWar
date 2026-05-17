# Step 1 — Project Scaffolding：Teaching Mode

---

## B. Plain-English Walkthrough

### `config.py`

**這個檔案在做什麼：**
這是遊戲的「設定面板」。所有魔法數字都集中在這裡：API 的網址、遊戲規則的參數（幾回合、每回合幾分鐘）、每種 POI 的關鍵字和分值、combo 獎勵的門檻、玩家的顏色、以及快取存在哪個資料夾。其他檔案只要 `import config` 就能拿到這些常數，不用自己寫數字進去，改參數的時候也只要改這一個檔案。

**引入的關鍵概念：**
- 常數 (constant)：整個程式生命週期都不會變的值，全大寫命名（如 `TURNS = 6`）以示與變數區別。
- `Path`：Python 的 `pathlib.Path` 物件，代表資料夾或檔案路徑，比字串更安全，跨 OS 不會出錯。
- Dict（字典）：用 key 存取 value 的資料結構。`POI_CATEGORIES` 以類別名稱為 key、細節為 value。

**為什麼這樣設計：**
把所有常數集中一處叫做「single source of truth（唯一真相來源）」。如果老師問「把 AP 從 15 分鐘改成 20 分鐘怎麼辦？」答案就是「改 `config.py` 裡的 `AP_PER_TURN = 20.0`，其他不用動」。

**何時執行：**
Python 第一次 import 任何模組時，`config.py` 就被執行一次，它的變數存在記憶體裡直到程式結束。

---

### `requirements.txt`

**這個檔案在做什麼：**
列出這個專案「必須安裝哪些外部套件」的清單。`pip install -r requirements.txt` 會讀這份清單，自動下載安裝 Flask、folium、requests、python-dotenv 四個套件。沒有這個檔案，別人拿到你的程式碼就不知道要裝什麼。

**關鍵概念：**
- 套件 (package)：別人已經寫好、可以直接拿來用的程式碼集合。
- 版本限制（`>=`）：「這個版本以上都可以」。

**何時執行：**
不在程式執行時用，而是在「設定開發環境」時用（`pip install -r`）。

---

### `.gitignore`

**這個檔案在做什麼：**
告訴 Git「哪些檔案不要追蹤、不要上傳」。`.env`（含密碼）、`.venv/`（虛擬環境，每台電腦裝的位置不同）、`data/` 下的 JSON（快取跟遊戲紀錄）都列在這裡。沒有這個檔案，可能不小心把密碼或幾百 MB 的快取推到 GitHub。

**何時執行：**
每次 `git add` / `git commit` 時，Git 讀這個檔案過濾不要追蹤的檔案。

---

### `.env.example`

**這個檔案在做什麼：**
這是 `.env` 的「模板」。真正的 `.env` 有真實密碼，不能上 Git。`.env.example` 只有示範格式，沒有真實密碼，可以放心上 Git。新人 clone 這個 repo 之後，把 `.env.example` 複製成 `.env` 並填入真實值即可。

**何時執行：**
`python-dotenv` 的 `load_dotenv()` 會在程式啟動時讀真正的 `.env`，不是這個 example 檔案。

---

### `app.py`

**這個檔案在做什麼：**
整個 Web 應用程式的「入口」。做三件事：(1) 載入 `.env` 的環境變數；(2) 建立 Flask app 物件，設定 `secret_key`（用來簽 cookie）；(3) 定義 `/health` 路由 — `GET /health` 回傳 `{"status":"ok"}`，讓我們確認伺服器在跑。現在這個版本很小，後面的 step 會陸續加入更多路由（`/new`、`/game`、`/move` 等）。

**關鍵概念：**
- Flask app 物件：整個 Web 程式的核心，負責接收 HTTP 請求並分派給對應的函式。
- 路由 (route)：把「某個 URL 路徑」對應到「一個 Python 函式」的規則。
- `secret_key`：Flask 用來加密 session cookie 的密鑰，不能讓別人知道。
- `load_dotenv()`：從 `.env` 讀取變數，讓 `os.environ.get` 可以拿到。
- 日誌 (logging)：讓程式把執行訊息印出來，方便除錯。

**為什麼這樣設計：**
「app.py 要保持薄（thin）」是整個專案的設計原則：app.py 只做「接收請求 → 呼叫 service → 回應」，所有遊戲邏輯放在 `services/` 裡。

**何時執行：**
執行 `flask --app app run` 或 `python app.py` 時，這個檔案最先被載入。

---

### `models/__init__.py`、`services/__init__.py`、`utils/__init__.py`

**這些檔案在做什麼：**
空白的 `__init__.py` 讓 Python 把這些資料夾視為「套件 (package)」，才能用 `from models.place import Place` 這樣的語法 import 裡面的模組。沒有它，import 會找不到路徑。

---

### `data/cache/poi/.gitkeep`、`data/cache/osrm/.gitkeep`、`data/games/.gitkeep`

**這些檔案在做什麼：**
Git 不追蹤空資料夾。放一個空的 `.gitkeep` 讓 Git 追蹤到這個資料夾的存在，這樣別人 clone repo 時，`data/` 的目錄結構就已經在了，不用手動建。

---

## C. Concept Cards

### Virtual Environment（虛擬環境）

**是什麼：** 一個隔離的 Python 環境，讓這個專案用自己的套件版本，不影響電腦上其他的 Python 專案。

**比喻：** 像一個沙盒遊樂場 — 在裡面你可以隨便裝沙、改地形，出了沙盒就是正常的公園，兩邊互不干擾。

**在程式中的位置：** `python -m venv .venv` 建立；`.venv\Scripts\activate` 啟動；`pip install -r requirements.txt` 安裝套件進去。

**為什麼用：** 避免套件版本衝突，讓 `requirements.txt` 精準描述依賴。

**教授可能問：**「如果不用虛擬環境，這個專案在別人電腦上會怎樣？」
**好答案：**「可能因為套件版本不同而出錯，或者污染對方電腦上其他專案的環境。虛擬環境讓每個專案有自己乾淨的套件集，這樣 requirements.txt 就能精準描述依賴。」

---

### `requirements.txt`

**是什麼：** 一份文字清單，列出這個專案需要的外部套件及版本要求。用 `pip install -r requirements.txt` 一次安裝所有套件。

**比喻：** 像食譜的「材料清單」— 不寫食譜本身，只列出需要哪些材料、大概的量。

**為什麼用：** 別人拿到 repo 只需要一行指令就能裝好所有依賴，不用猜。

**教授可能問：**「為什麼 `.venv/` 不上傳到 Git？」
**好答案：**「虛擬環境裡有幾千個自動生成的檔案，幾百 MB，而且路徑是平台相關的。只要有 `requirements.txt`，任何人都能在自己電腦上重新建一個一模一樣的環境。」

---

### Flask app（Flask 應用物件）

**是什麼：** Flask 應用程式的核心物件，負責接收 HTTP 請求、把請求分派給對應的 Python 函式、然後把函式的回傳值變成 HTTP 回應。

**比喻：** 像一個交換機台的接線員 — 電話（HTTP 請求）進來，接線員（Flask app）看你撥哪個分機（URL 路由），幫你轉接到對應的人（Python 函式）。

**在程式中的位置：** `app.py` 第 16 行：`app = Flask(__name__)`

**為什麼用：** Flask 是 Python 界最輕量的 Web 框架，不強制任何資料庫或目錄結構，適合這種小型 demo 專案。

**教授可能問：**「Flask 跟 Django 差在哪裡？為什麼選 Flask？」
**好答案：**「Django 是大型框架，內建 ORM、admin 後台、驗證系統；Flask 是微框架，只給你路由和模板，其他自己決定。我們的遊戲沒有資料庫、沒有使用者系統，Flask 的簡單剛好符合需求。」

---

### Route（路由）

**是什麼：** 把一個 URL 路徑（如 `/health`）對應到一個 Python 函式的規則。

**比喻：** 像餐廳的菜單對應廚房的工作站 — 點了 A 菜（`/game`）就去找炒鍋師傅（`game_route` 函式），點了 B 菜（`/health`）就去找冷盤師傅（`health` 函式）。

**在程式中的位置：** 目前 `app.py` 只有一個路由：`@app.get("/health") def health()`

**為什麼用：** 路由讓一個程式可以根據不同的 URL 做完全不同的事，這就是「Web 應用程式」的核心概念。

**教授可能問：**「`@app.get` 跟 `@app.route(methods=['GET'])` 差在哪？」
**好答案：**「功能一樣，`@app.get` 是 Flask 2.0 以後的簡寫。`@app.post`, `@app.get` 讓程式碼更直觀 — 一眼看出這個路由接受什麼 HTTP method。」

---

### JSON

**是什麼：** JavaScript Object Notation，一種輕量的文字格式，用來在程式之間交換資料。長得像 Python dict，但 key 一定要雙引號，值只能是特定類型。

**比喻：** 像一種國際通用的表格格式 — 不管你是 Python、JavaScript、Java，都能讀懂 `{"status": "ok"}`。

**在程式中的位置：** `/health` 路由用 `jsonify({"status": "ok"})` 回傳 JSON；快取檔案（`data/cache/`、`data/games/`）也全部存成 JSON。

**為什麼用：** 瀏覽器和 API 都認識 JSON；Python 的 `json` 模組和 Flask 的 `jsonify` 讓轉換非常簡單。

**教授可能問：**「為什麼不用 pickle 來存遊戲狀態？」
**好答案：**「pickle 是 Python 專用格式，人眼看不懂，也有安全風險（可以執行任意程式碼）。JSON 是純文字，可以用文字編輯器打開檢查，debug 方便，也不限語言。」

---

## D. Mock Q&A

**Q1 [Concept]**：Virtual environment 是什麼？你為什麼要用它？

**A1：** 虛擬環境（`.venv`）是這個專案專屬的 Python 環境，裡面安裝的套件版本（Flask 3.x、folium 等）和電腦上其他專案完全隔離。用 `python -m venv .venv` 建立，用 `.venv\Scripts\activate` 啟動。好處是不同專案用不同版本的同一個套件時不會互相衝突，而且 `requirements.txt` 精準描述依賴，別人 clone 就能重現完全相同的環境。

**必提要點：** 隔離（isolation）、`requirements.txt` 作為依賴清單、`.venv/` 不上 Git 因為太大且平台相關。

---

**Q2 [Walkthrough]**：帶我走過 `app.py`，解釋每個部分在做什麼。

**A2：** 開頭 `import os、logging、load_dotenv、Flask、jsonify`，先 `load_dotenv()` 把 `.env` 裡的環境變數（`WALKWARS_SECRET`）讀進來；`logging.basicConfig` 設定日誌格式，讓執行訊息有時間戳、等級、名稱；`Flask(__name__)` 建立 Web 應用物件，`secret_key` 從環境變數讀，沒有的話 fallback 到 `'dev-secret'`；`@app.get("/health")` 裝飾器把 `health()` 函式綁定到 `GET /health` 路由，回傳 `{"status":"ok"}`；最後 `if __name__=="__main__"` 讓 `python app.py` 可以直接跑。

**必提要點：** `load_dotenv` 的作用、`secret_key` 從環境變數讀（安全考量）、路由裝飾器原理。

---

**Q3 [Design Decision]**：為什麼 `config.py` 要用 `pathlib.Path` 而不是直接寫字串 `"data/cache"`？

**A3：** `Path` 物件在 Windows/Mac/Linux 上自動處理路徑分隔符（Windows 用 `\`，Linux 用 `/`），用字串就要自己處理跨平台問題。更重要的是，`Path` 物件有方便的方法：`Path("data/cache") / "poi"` 可以串接子路徑，`Path.mkdir(exist_ok=True)` 可以直接建立資料夾，比字串拼接更安全、更直觀。

**必提要點：** 跨平台路徑問題、`Path` 物件的方法比字串方便。

---

**Q4 [Modification]**：老師說把 POI 半徑從 1500 公尺改成 2000 公尺，你怎麼做？

**A4：** 只改 `config.py` 一行：`POI_RADIUS_M = 2000`。因為所有用到這個數值的地方（`POIService.generate_pois` 等）都是 `import config` 拿值，不會有硬編碼的數字散落各處。改完重啟 Flask 即生效。這就是「single source of truth」設計的好處。

**必提要點：** 只改 `config.py`、不需要找其他地方的 magic number、重啟生效。

---

**Q5 [Concept]**：`.gitignore` 裡的 `data/cache/*/*.json` 在做什麼？

**A5：** 這條規則符合 `data/cache/poi/abc.json` 或 `data/cache/osrm/xyz.json` 這樣的路徑，也就是快取資料夾裡的所有 JSON 檔案，都不會被 Git 追蹤。原因是快取可能有幾百個檔案，是程式自動生成的，不屬於「原始碼」，不需要版本控制，而且會讓 repo 變得又大又難管理。`.gitkeep` 檔案不受影響，因為它不是 `.json` 結尾。

**必提要點：** glob 萬用字元 `*` 的意思、快取不應進入版本控制的理由、`.gitkeep` 的作用。

---

## 學生自我檢驗儀式（Step 1 結束後做）

1. 打開 `MY_NOTES.md`（沒有就建立）。用自己的話，每個檔案寫 2–3 句：`config.py` 是做什麼的、`app.py` 今天能做什麼、虛擬環境是什麼。**不要複製這份文件的內容，用自己的理解寫。**
2. 闔上電腦，對牆壁大聲說：「我打 `python app.py` 之後，發生了什麼事？」
3. 試著口頭回答上面 5 個 Mock Q&A。答得出來就繼續 Step 2；答不出來就再讀一遍 Walkthrough。
