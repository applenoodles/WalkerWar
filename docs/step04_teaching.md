# Step 4 — N×N 步行時間矩陣（Teaching Mode）

> 對應 Build Order 第 4 步：「Walking time matrix — given N POIs, build N×N matrix (with progress logging); cache to disk.」

本步驟新增 / 修改的檔案：
- 修改 `config.py`：新增 `WALKING_SPEED_KMH = 5.0`
- 修改 `services/osrm_service.py`：新增 `_walking_minutes()` 私有助手、`build_matrix()` 方法，重構 `get_walking_route()` 改為「儲存距離，每次重算時間」
- 修改 `app.py`：新增 `/debug/matrix` 路由

**驗證結果（本次實際跑出來）**：22 個 POI → 22×22 矩陣，首次建構 62.4 s（231 次 OSRM 呼叫，平均 270 ms / 次），二次 0.4 s（全 cache hit）；對角線全 0、首 5 個 POI 兩兩對稱檢查全通過；OSRM 步速修正後 692.2 m → 8.31 min（合理步速）。

---

## 1. 各檔案的中文導讀（Plain-English Walkthrough）

### `config.py`（新增一個常數）

**這個改動在做什麼？**
新增 `WALKING_SPEED_KMH = 5.0`，把行人速度從魔術數字升等成有名字、有註解、可調整的常數。

**為什麼這樣設計？**
- Step 3 末發現公開 OSRM demo 的 `/foot/` 其實仍回車速，這個常數就是我們補救方案的核心：用 OSRM 給的距離 ÷ 這個速度 = 真正的步行分鐘。
- 5 km/h 是城市規劃文獻常用的「平均步行速度」。如果之後想模擬「年長者場景」可以調 3.5，「年輕人短程衝刺」可以調 6 ——一個地方改、全專案生效。

---

### `services/osrm_service.py`（重構 + 新增）

這檔有三個重要的改動，分別解決一個問題。

#### 1) `_walking_minutes(distance_m)` —— 新的私有助手

把「距離 → 時間」的公式集中在一個地方：
```python
def _walking_minutes(self, distance_m: float) -> float:
    return (distance_m / 1000.0) / WALKING_SPEED_KMH * 60.0
```
唯一的計算入口，避免到處散落 `/1000 * 60 / 5.0` 的算式。

#### 2) `get_walking_route()` —— 改為「儲存距離、每次重算時間」

**舊版**：把 OSRM 回的 duration 直接寫進 cache。如果之後改 `WALKING_SPEED_KMH`，所有 cache 就過期。
**新版**：cache 仍記著 `duration_min`，**但讀出來時會覆蓋**：
```python
cached = json.loads(...)
cached["duration_min"] = self._walking_minutes(cached["distance_m"])  # self-heal
return cached
```
這叫「自我修復的 cache（self-healing cache）」：cache 裡只有原料（距離）永遠是真的，最後端上桌的數字（時間）每次重算。Step 3 那唯一一個 cache 檔不用清掉，自動會變對。

#### 3) `build_matrix(places)` —— 本步主角

```python
matrix[poi_id_a][poi_id_b] = walking_minutes_from_a_to_b
```
這個 N×N 字典就是整個遊戲的「靈魂資料結構」。後面所有「能不能走到」、「contest 比誰先到」、「AI 該走哪」、「Voronoi 領土屬於誰」的判定，**全部都是查這張表**。

**設計重點**

| 設計 | 為什麼 |
|---|---|
| 只跑「上三角」（C(N,2) 對） | 步行對稱：A→B == B→A，下三角直接 mirror，API 用量砍半（22 個 POI 從 484 次降到 231 次）。 |
| 用 `dict[str, dict[str, float]]` 而不是 `list[list[float]]` | 用 `poi_id` 字串當 key、未來 POI 順序變動或新增也不會「索引錯位」；JSON 序列化也直觀。 |
| 對角線 `matrix[x][x] = 0` | 把「同一點」當作合法的特殊查詢，呼叫端不用先判斷 `if a == b`。 |
| 每 20 對 log 一次進度 | 第一次跑要 60+ 秒，學生如果看不到進度會以為當機 → 退出 → 又要重跑。 |
| 任一對失敗就 `raise RuntimeError` | 殘缺的矩陣比沒矩陣還危險（後面 lookup 會回 KeyError 或更慘的錯誤），寧可一次全失敗。 |

**遊戲流程中何時被呼叫？**
- Step 5：玩家提交起點 → 生 POI → `build_matrix(pois)` → 存進 `data/games/{game_id}.json`。
- Step 5 之後：所有回合中讀矩陣，不再打 OSRM。

---

### `app.py`（`/debug/matrix` 路由）

跟 `/debug/osrm` 同樣 pattern 的 debug route，回傳：
- `n_pois`、`matrix_size` —— 維度
- `diagonal_zero_ok` —— 對角線是否全為 0
- `sample_top3x3_min` —— 左上 3×3 角的實際數字
- `symmetry_check_first5` —— 前 5 個 POI 兩兩對稱檢查

純粹是 Step 4 的「驗證收據」。Step 5 接 `/game` 之後一起拆掉。

---

## 2. 概念卡（Concept Cards）

### 卡 1：距離矩陣（Distance Matrix）

| 項目 | 內容 |
|---|---|
| 一句話 | 一張 N×N 的表，每個格子記「從第 i 個點到第 j 個點的距離（或時間）」。 |
| 比喻 | 像台鐵的「站對站票價對照表」：你查台北→新竹要多少錢，就翻到「台北」這列、找「新竹」這欄。 |
| 在我們程式裡 | `OSRMService.build_matrix()` 回傳的 `dict[poi_id_a][poi_id_b] = 分鐘`。 |
| 為什麼用 | 整個遊戲的判斷（reachable / contest / AI 評分 / 領土）都需要「兩點間時間」，先算好查表 → 每次 O(1)；如果回合中現算 → 每回合 ~190 次 API call，根本玩不下去。 |
| 可能被問 | Q：「為什麼不每次需要時直接查 OSRM？」 A：「OSRM 是 hot path：22 個 POI 配 6 回合，現算的話一場遊戲要打上千次 API、累積延遲幾分鐘；預先建表 + cache 是把所有外部延遲移到遊戲開始前。」 |

### 卡 2：對稱矩陣與上三角（Symmetric Matrix & Upper Triangle）

| 項目 | 內容 |
|---|---|
| 一句話 | 一個矩陣若 `M[i][j] == M[j][i]`，就叫「對稱」；只算上三角就能填完整張表，省一半計算。 |
| 比喻 | 國中段考座位表，若「甲到乙幾步」=「乙到甲幾步」，你只要量人與人組合（不是排列），就能補完整張表。 |
| 在我們程式裡 | `build_matrix()` 的 `for j in range(i+1, n)` 只跑上三角；每次填值後 `matrix[b][a] = t` mirror 到下三角。 |
| 為什麼用 | 22 個 POI：N²=484 vs N(N-1)/2=231 —— OSRM 呼叫直接砍一半（62 s vs 約 124 s）。 |
| 可能被問 | Q：「如果是車輛單行道，對稱還成立嗎？」 A：「不一定。OSRM 的 foot profile 假設行人雙向可走，所以這裡對稱；如果以後換 driving，可能要拆成完整 N² 矩陣。」 |

### 卡 3：時間 / 空間複雜度（Time & Space Complexity, Big-O）

| 項目 | 內容 |
|---|---|
| 一句話 | 用 O(...) 描述「資料量變大時，程式跑多久 / 用多少記憶體」的成長速度。 |
| 比喻 | 一條捷運線 N 站：所有兩站之間都得通車 → 班次數量是 O(N²)，新增一站，工程量「按平方」變多。 |
| 在我們程式裡 | 矩陣建構：上三角 → 時間 O(N²/2) 次 API；空間 O(N²) 個 cell；查表：O(1)（dict 雜湊）。 |
| 為什麼用 | 它幫我們選資料結構：22 個 POI O(N²)=484 還能接受；如果未來放大到 100 個 POI、O(N²)=10000 就會卡，那時要考慮 OSRM 的 `/table` 端點（一次回傳整片矩陣）。 |
| 可能被問 | Q：「為什麼說 dict 查表是 O(1)？」 A：「Python dict 底下用 hash table，平均一次雜湊就能定位，跟資料量無關（除非 hash 衝突大量發生，那種情況實務上很少見）。」 |

### 卡 4：自我修復的 Cache（Self-Healing Cache）

| 項目 | 內容 |
|---|---|
| 一句話 | Cache 只存「原料」，每次讀的時候用最新公式重算「結果」，這樣公式變動不會讓 cache 失效。 |
| 比喻 | 冰箱裡只存蛋（原料），不存炒蛋（成品）。今天想吃水煮、明天想吃太陽蛋，蛋本身永遠是對的，做法可以隨時換。 |
| 在我們程式裡 | OSRM cache 存 `distance_m`（從 OSRM 來，恆真），每次回傳時用 `_walking_minutes()` 重算 `duration_min`；若改 `WALKING_SPEED_KMH = 4.0`，下次讀 cache 自動就是新速度，不用清檔。 |
| 為什麼用 | (1) 速度參數調整時，所有 cache 無痛升級；(2) 避免把「衍生計算」凝固在磁碟上，未來 bug 修不掉。 |
| 可能被問 | Q：「Step 3 cache 那個檔的 duration 是錯的，要不要先刪？」 A：「不用，因為 distance 是對的，新版讀的時候會用新公式重算 duration。我跑 `/debug/osrm` 直接看到從 1.4 變成 8.31，cache 沒動。」 |

### 卡 5：起點處理（Origin Handling，預告 Step 5）

| 項目 | 內容 |
|---|---|
| 一句話 | 兩名玩家都從同一個起點（清華大學）出發，這個「起點」也需要進矩陣，否則第 1 回合不知道誰能走到哪。 |
| 比喻 | 班遊抽出發地點，若行程表只記「景點 A 到景點 B 多遠」、沒記「車站到 A 多遠」，你連第一步都不能算。 |
| 在我們程式裡 | Step 4 的 `build_matrix` 純粹只算傳入的 places 兩兩之間。Step 5 在呼叫之前，會把 `origin` 包成一個 `Place(poi_id="origin", value=0, ...)` 加到 list 最前面，所以矩陣自然會包含「起點 ↔ 每個 POI」的時間。 |
| 為什麼用 | 把起點當「普通 POI」處理，可以重用全部現成 lookup 邏輯（reachable、contest 都不用為起點寫特例）；缺點是 origin 也算進「玩家擁有 POI」時要記得跳過 —— 這在 Step 5 GameState 裡會明確處理。 |
| 可能被問 | Q：「為什麼起點不另存一張 1×N 的小表？」 A：「會多一條 code path 要維護；把起點當普通節點，矩陣是統一的 (N+1)×(N+1)，所有查 reachable / contest 的程式碼都只是 lookup，不用為起點寫 if。」 |

---

## 3. 模擬問答（Mock Q&A）

### Q1（概念）
**問：為什麼遊戲一開始就花 60 秒先把矩陣建完，而不是回合中用到再算？**

OSRM 是 hot path。22 個 POI、6 回合，回合中現算的話 AI 評分一次要對所有候選 POI 計算 walking time，加上 contest 又要查更多次，一場遊戲可能打上千次 API，累積延遲幾分鐘、玩家會以為當機。預先建表把所有「外部世界的延遲」集中在「開始遊戲」這個玩家心理已經準備好等的時刻。建完之後配上 cache，第二次以後幾乎瞬間。

### Q2（走讀）
**問：你的 cache key 是怎麼讓 A→B 和 B→A 共用一個檔的？**

`_cache_path()` 裡先把兩個 `(lat, lon)` 各 `round(_, 5)`（約 1 公尺精度），再 `tuple(sorted([a, b]))` 排序，最後 sha256 取前 16 字。因為 sorted 永遠把較小的座標排前面，無論呼叫順序是 A→B 還是 B→A，產出的 key 都一樣，所以兩個方向共用一個 cache 檔。22 個 POI 從 484 次降到 231 次，整整少打一半。

### Q3（設計決策）
**問：為什麼矩陣用 `dict[str, dict[str, float]]`，不用 `list[list[float]]`？**

三個理由：(1) 用 `poi_id` 當 key，未來 POI 順序變動或刪一個再加新的，都不會出現「索引位置錯位」的災難；(2) JSON 序列化天然支援字串 key，存進 `data/games/{game_id}.json` 不用再另存索引對照表；(3) 在 Python 裡 dict lookup 平均也是 O(1)，跟 list 索引差距小到對遊戲體感無影響。代價是記憶體稍大、JSON 檔稍胖，但 22 個 POI 我們承擔得起。

### Q4（修改情境）
**問：如果想模擬「長輩走得比較慢」的場景，需要改哪裡？**

只改 `config.py` 的 `WALKING_SPEED_KMH = 5.0` → `3.0`，**整個專案會自動跟著變**。OSRM cache 不用清，因為 `get_walking_route()` 每次讀 cache 時都會用最新的 `WALKING_SPEED_KMH` 重算 duration（self-healing cache）。下次 `/debug/matrix` 重跑就是新速度的矩陣。

### Q5（已知限制 / 未來工作）
**問：22 個 POI 已經要 60 秒，如果要支援 100 個 POI 怎麼辦？**

C(100, 2) = 4950 對，照現在做法要 ~22 分鐘，玩家鐵定關掉。可以改用 OSRM 的 `/table/v1/foot/` 端點，**一次 request 就回傳整片 N×N**，不用逐對打 —— 缺點是 demo server 對 table 有 source/destination 數量上限（公開的好像是 100），剛好夠用、但要另外處理 cache key（變成「整組座標」的 hash）。MVP 因為只跑 22 個沒做這層優化，spec 也說「Keep the algorithm story small and explainable」，所以保留現在的逐對版本當作講解主線。

---

## 4. 學生自我檢查儀式（Self-Check Ritual）

在開始 Step 5 之前，請自己對自己回答這些題目（先合上 IDE）：

- [ ] 我能在白紙上畫出 3×3 矩陣的結構，並指出對角線為什麼是 0、為什麼對稱。
- [ ] 我能說出「為什麼要先把整張矩陣建完才開始玩」，至少給出兩個理由。
- [ ] 我能解釋「self-healing cache」是什麼，以及為什麼 Step 3 那個 cache 檔不用清。
- [ ] 我能算 22 個 POI 的「上三角」是幾對：`22*21/2 = 231`，而完整 N² 是 484。
- [ ] 我知道 Step 5 會把起點當作「普通 POI」插到 list 最前面、跟著一起進矩陣。

任何一題卡住 → 回對應「概念卡」或「Plain-English Walkthrough」段落重看一次，再開 Step 5。
