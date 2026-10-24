# 选举看板生成指南

> 适用：本仓库的 32 场开票看板（台北市长 8 届 × 村里/区级 + 总统「北北基宜」8 届 × 村里/区级）。
> 撰写时间：2026-10-15，基于当前的程式码与目录实况（含「届次文案」「小卡去底色」「宋楚瑜 2000 灰」「分两文件夹输出」四轮定案）。
> 本文取代 `README_批量做看板.md`（那份是 2026-10-04 的历史快照，部分参数已过时，留作沿革参考）。

---

## 0. 一分钟上手

全部命令都在 `Video/` 目录下执行。先把两个可执行档存成变数：

```bash
PY="C:/Users/Windows/AppData/Local/Microsoft/WindowsApps/python.exe"          # 3.14.7，装了 geopandas / PIL / matplotlib / cv2
NODE="C:/Users/Windows/.workbuddy/binaries/node/versions/22.22.2-6/node.exe"  # 22.22.2
```

**改版面时（日常迭代，只出两场样本）**

```bash
$NODE tools/render_boards.mjs --boards 2000-president-north 2022-taipei-mayor \
      --scale 1 --out ./NewSolution/out/_sample
$PY tools/verify_layout.py NewSolution/out/_sample/layout/*.json
```

**定案后全量出图**（分两文件夹输出，2026-10-15 定案）

> 建置（`build_board.py` / `_gen_president_boards.py`）只有在**资料 / 几何 / 素材表**变了才需要跑；纯改版面直接跳到渲染即可。
> 全量只出**主版 16 场**（不含 `-map2` 变体），市长与总统分别输出到两个文件夹。

```bash
# ① 建置（改素材 / 几何 / 文案后才需要，会补 roc_flag / street_bg 等新素材）
for id in 1994-taipei-mayor 1998-taipei-mayor 2002-taipei-mayor 2006-taipei-mayor \
          2010-taipei-mayor 2014-taipei-mayor 2018-taipei-mayor 2022-taipei-mayor; do
  $PY tools/build_board.py "boards/$id"
done
$PY tools/_gen_president_boards.py                     # 8 个总统年一次重建

# ② 渲染：台北市长 8 场 → taipei/，总统 8 场 → president/
$NODE tools/render_boards.mjs --boards 1994-taipei-mayor 1998-taipei-mayor 2002-taipei-mayor \
    2006-taipei-mayor 2010-taipei-mayor 2014-taipei-mayor 2018-taipei-mayor 2022-taipei-mayor \
    --scale 1 --out ./NewSolution/out/taipei
$NODE tools/render_boards.mjs --boards 1996-president-north 2000-president-north \
    2004-president-north 2008-president-north 2012-president-north 2016-president-north \
    2020-president-north 2024-president-north \
    --scale 1 --out ./NewSolution/out/president

# ③ 验证
$PY tools/verify_layout.py NewSolution/out/taipei/layout/*.json
$PY tools/verify_layout.py NewSolution/out/president/layout/*.json
```

> 为什么只渲两场：这两场刚好覆盖**总统场**（图例关闭、有副手行、有区级图）与**市长场**（有图例、无副手）两种情境。引擎是全场共用的，两场过就等于全场过；一次 `--all` 要跑 32 场，迭代时没必要。

---

## 1. 环境

| 用途 | 路径 | 版本 |
|---|---|---|
| Python（地图生成、透明化、建置、验证） | `C:\Users\Windows\AppData\Local\Microsoft\WindowsApps\python.exe` | 3.14.7 |
| Node（无头渲染） | `C:\Users\Windows\.workbuddy\binaries\node\versions\22.22.2-6\node.exe` | 22.22.2 |
| 静态服务器根 | **必须** `Video/`，不是 `boards/` | — |

渲染走 Chrome DevTools Protocol，**零 npm 依赖**，会起一次 Edge/Chrome 后逐场截图。

---

## 2. 目录地图

```
Video/
├── NewSolution/
│   ├── Converge_to_map_taipei.py      ← 台北市长地图（读 xlsx + 村里界 SHP → 上色）
│   ├── data/                          ← 逐里得票 xlsx（市长链路的资料源）
│   ├── png/
│   │   ├── map/<year>/                ← 原始地图（map.png / map2.png / legend.png）
│   │   ├── party/                     ← 政党徽章原图
│   │   ├── share/                     ← 市徽 / 国徽 / 当选标志 / 国旗 / 街景
│   │   ├── candidate/                 ← 候选人照片原图（管线不消费，只留素材）
│   │   └── processed/                 ← ★ 全专案唯一成品落点（map/ party/ share/）
│   └── tool/
│       ├── build_assets.py            ← 素材透明化唯一入口
│       ├── assets.map.json            ← 配方表：原图 → 成品
│       ├── make_transparent.py        ← 白→透明（逐通道判准）
│       └── legend_president.py        ← 总统场图例（透明底白字）
├── Precident/maps/                    ← 总统「北北基宜」地图（脚本 + 各年成品）
│   ├── <year>/{1,2}/                  ← 1＝区级版（白底）、2＝村里版（已透明）
│   ├── Draw_Region_Maps_AllYears.py   ← 总统地图生成（1996–2024 × 五大分区）
│   └── Verify_Maps_AllYears.py
├── boards/
│   ├── _engine/js/                    ← ★ 共用引擎（改这里 = 改全部 32 场）
│   ├── _template/                     ← 新场次的骨架（index.html / meta.json / source/）
│   ├── <id>/                          ← 一场看板一个目录
│   └── 2014-newtpei-mayor/.skip       ← 冻结回归参照，--all 自动跳过
└── tools/
    ├── build_board.py                 ← 市长场建置
    ├── _gen_president_boards.py       ← 总统场建置（也生成配置）
    ├── _gen_taipei_boards.py          ← 市长场配置生成（一次性）
    ├── render_boards.mjs              ← 批量渲染
    └── verify_layout.py               ← 版面验证 L1–L12
```

---

## 3. 四段管线

### A. 素材准备

**A1 生成地图**（白底 RGB，之后才透明化）

**台北市长链路**

```bash
# 全部年份，或给年份关键字只做一年
$PY NewSolution/Converge_to_map_taipei.py
$PY NewSolution/Converge_to_map_taipei.py 2022
```

产物落在 `NewSolution/png/map/<year>/`：

| 档名 | 内容 |
|---|---|
| `map.png` | **村里级**：每一里按「领先候选人」上色（看板主图） |
| `map2.png` | **区级**：只画区不画里，**画布与 map.png 完全同尺寸同范围，可叠合** |
| `legend.png` | 图例（matplotlib 白底黑字；那步只为取遮罩，后面重新上白色） |

**总统「北北基宜」链路**（另一套脚本与资料来源）

```bash
# 脚本在 Video/Precident/maps/；但资料（xlsx、color.txt）在專案外的 D:/Windows/TaiwanElection/Precident/
$PY Precident/maps/Draw_Region_Maps_AllYears.py            # 全部年份 × 五大分区
$PY Precident/maps/Draw_Region_Maps_AllYears.py 2000       # 只做 2000
$PY Precident/maps/Draw_Region_Maps_AllYears.py 2000 北北基宜   # 只做某分区
```

脚本产出到 `Precident/maps/<year>/{1,2}/北北基宜<year>年總統副總統選舉_得票率地圖.png`。接着要**人工搬到看板消费的位置**（这步目前没有脚本）：

| 来源 | 搬到 | 内容 |
|---|---|---|
| `<year>/2/北北基宜…png` | `NewSolution/png/map/<year>/map.png` | **村里级**（有里界细线），已是 RGBA |
| `<year>/1/北北基宜…png` | `NewSolution/png/map/<year>/map2.png` | **区级**（只有乡镇市区界），白底 RGB，待透明化 |
| —（现生成） | `NewSolution/png/map/<year>/legend.png` | 跑 `$PY NewSolution/tool/legend_president.py <year>`，透明底白字 |

> 两个链路的差别：市长场由 `Converge_to_map_taipei.py` 从 xlsx + 村里界 SHP 现场绘出三张图；总统场则是先由 `Draw_Region_Maps_AllYears.py` 绘出五大分区各自的图，其中「北北基宜」那张再搬进 `NewSolution/png/map/<year>/`。
> `--all` 不涉及以上任何一步 —— 它只渲染已经备好素材的看板。

> 年份 = 一场选举 = 一个看板。市长链路的主程式会挡掉 `city != 臺北市` 的资料集。
> 1990 旧行政区图另有 `Converge_to_map_taipei_1990.py`，不在本管线内。

**A2 透明化**（唯一入口）

```bash
$PY NewSolution/tool/build_assets.py                      # 全部三类、全部年份
$PY NewSolution/tool/build_assets.py --kind share --force # 只做 share 并强制重做
$PY NewSolution/tool/build_assets.py --year 2022 --kind map
$PY NewSolution/tool/build_assets.py --dry-run            # 只列出会做什么
$PY NewSolution/tool/build_assets.py --check              # 只查齐备，缺件退出码 1
```

`--kind` 取值：`map` / `party` / `share`（三类，对应 `NewSolution/png/<kind>/`）。

配方表 `NewSolution/tool/assets.map.json`，成品**一律**写进 `NewSolution/png/processed/`，不回写原图、不写 `boards/<id>/assets/`。

**透明化的两条路线**

| 路线 | 判准 | 用在 |
|---|---|---|
| `white`（预设） | `alpha = (255 - min(R,G,B)) / soft`，`soft=30` | 精确纯白底 + 纯色平涂的素材（市徽、徽章） |
| `CopyRecipe`（`how: copy`） | 原样复制，**不碰透明度** | `legend.png`（本身透明底白字）、`roc_flag.png`（白日/白边过白会被吃掉）、`street_bg.png`（街景照整张都是内容） |
| 地图专用 | `make_transparent.py`，容差 `threshold=12`，**逐通道**判准（三通道都 ≥243 才算白） | `map.png` / `map2.png` |

> **铁律**：顺序不能反——**绝不能「先透明再缩图」**。先缩图会把浅色推向白、边缘被吃掉，而且 PNG 会暴涨。
> 要省体积就降**产图解析度**（`METERS_PER_PIXEL`），不要缩素材。

### B. 看板建置

原则：**只找图，不做图**。把「逻辑素材名 → 实际路径」写成对照表。

**市长场**

```bash
$PY tools/build_board.py boards/2022-taipei-mayor
```

| 参数 | 用途 |
|---|---|
| `--refresh-geo` | 丢掉缓存、重跑 SHP |
| `--shp <file>` | 指定村里界图资 |
| `--skip-geo` | 不碰地理处理（只改文案时快很多） |
| `--geo-cache <file>` | 指定其他缓存档 |
| `--diff <old.js>` | 跟旧版对照 |

读 `meta.json` + `source/data.xlsx` + 村里界 SHP → dissolve 聚合成行政区 → 产出：

- `board.js`（选票数据 + 行政区几何）
- `board.files.js`（`window.BOARD_FILES.files`，逻辑素材名 → 实际路径）
- `board.assets.js`（内嵌素材，**默认不产**；只有 `file://` 直开才需要，加 `--embed`）
- `index.html`（薄壳，复制模板）
- `.cache/geojson.json`（缓存，自带 `_source` 记录来源，不符会自动重建）

**总统场**

```bash
$PY tools/_gen_president_boards.py          # YEAR_META 全部年份
$PY tools/_gen_president_boards.py 2000     # 只做 2000
```

- 直接读 `D:/Windows/TaiwanElection/Precident/<year>Precident/data/*縣市鄉鎮村里*.xlsx` 的「乡镇市区级别」工作表算北北基宜合计（★ 资料在**專案外**的兄弟目录），**不建 `source/` 目录**，直接写 `board.files.js` 指向 `processed/`。
- 同时生成 `<year>-president-north` 与 `<year>-president-north-map2` 两个变体（差别只在主图用 `map.png` 还是 `map2.png`）。
- ★ **`index.html` 是从 `boards/2022-taipei-mayor/index.html` 复制过来的** —— 改了引擎壳层要记得重跑这个生成器。

### C. 渲染

```bash
$NODE tools/render_boards.mjs --boards 2000-president-north 2022-taipei-mayor --scale 1 --out ./NewSolution/out/_sample
$NODE tools/render_boards.mjs --all --scale 1 --out ./NewSolution/out
$NODE tools/render_boards.mjs --all --scales 1,2 --out ./NewSolution/out     # 1×=2560×1440, 2×=5120×2880
```

| 参数 | 说明 |
|---|---|
| `--boards <name...>` | 指定场次目录名（可多个，相对 `boards/`） |
| `--all` | 渲染 `boards/` 下所有含 `meta.json` 的场次 |
| `--scale <n>` / `--scales <1,2>` | 单倍率 / 多倍率 |
| `--out <dir>` | 输出目录，预设 `Video/out` |
| `--boards-root <dir>` | 覆盖 `boards/` 根目录 |
| `--root <dir>` | 静态服务器根，预设 `Video/` |

产物：

- `<out>/<id>_2560x1440.png` —— 看板成品
- `<out>/manifest.json` —— 场次清单 + SHA256 / bytes / 尺寸（可回归比对）
- `<out>/layout/<id>.json` —— 版面报告（验证用，见 §3-D）

> ★ **`--boards`（指定场次）会把 `manifest.json` 覆写成只有那几场。** 要恢复完整清单就重跑一次 `--all`。

### D. 验证

```bash
$PY tools/verify_layout.py                            # 验 out/layout/ 下所有场次
$PY tools/verify_layout.py NewSolution/out/layout/*.json
```

任一规则 FAIL → 退出码 1。规则清单见 §8。

---

## 4. 版面结构（2560 × 1440）

坐标取自真实渲染报告（`out/layout/*.json`），不是示意图。

| 区块 | 位置 / 尺寸 | 说明 |
|---|---|---|
| 页眉 | `y 0–236` 全宽 | 白底圆角徽章卡（市长=市徽、总统=国旗）＋选举名称＋「投票率／有效票」 |
| 左主卡 | `84, 274`，`452×620` | 第 1 名。政党胶囊 `chip` 在 `y910`，`452×84`，徽章边长 45.4px |
| 右主卡 | `2024, 274`，`452×620` | 第 2 名 |
| 主地图（框） | `560, 196`，`1020×1034` | `Layout.map`。**置中的直式图**，实际墨迹四周留白很多 |
| 右栏 | 二选一 | **市长场**＝图例 `1626, 493`，`352×440`；**总统场**＝区级图 `1451, 264`，`542×812` |
| 小卡带 | `x 560–1990`，`y 1102–1390` | 第 3 名**高卡靠右**（`h288`），其余**从它左缘往左排**，空位留在最左边 |
| 底部跑马灯 | `y 1396`，`h 44` | — |

**右栏为什么二选一**：市长场图例正占着那一栏；总统场图例是关闭的（`meta.layout.legend.disabled = true`），引擎才把区级图摆进去（`Map2Layer` 只在 `legend.disabled === true` 时绘制）。

**小卡为什么可以「往上长」**：地图是置中的直式图，下半部墨迹很窄（2022 在 `y1100` 以下只剩 `x≈1009–1280`），所以高卡与清单格落在**地图下方的空白处**，由 L9 把关。

---

## 5. 铁律（踩过雷，别改）

1. **只做臺北市**。`Converge_to_map_taipei.py` 会挡住 `city != 臺北市`；不要新增新北看板/地图。
2. **成品只写 `NewSolution/png/processed/`**，不回写原图、不写 `boards/<id>/assets/`。
3. **静态服务器根必须是 `Video/`**（`board.files.js` 用 `../../NewSolution/...` 指素材）。
4. **看板不画候选人照片**。卡面只填政党纯色 + 亮框，照片由使用者后制合成。
5. **村里界图资按选举年切换**：`<2019` 用历史图资 106（`cp950` 编码）；`≥2019` 用现行 111（`UTF-8`）。落点 `tools/boardlib/geo.py` 与 `Converge_to_map_taipei.py`。
6. **图例色阶固定绑政党**（不依栏位序循环）。1994–2010 的得票栏位只有人名、没有政党，两大党候选人姓名也列进了 `PARTY_COLOR_GROUPS`，否则整场变灰。
7. **政党标签不画英文缩写**；无党籍只印「无党籍」。统一走 `partyDisplay()`。
8. **顺序不可逆**：不能「先透明再缩图」。
9. **载入器必须做路径换算**：新增素材载入时 `U.resolveAsset(src)` 不能忘，忘了会静默 log「读不到 assets/xxx.png」，画面缺一块但不会报错。
10. **`2014-newtpei-mayor` 是 `.skip` 冻结回归参照，别重渲染它。**
11. **验证规则要排在 `legendDisabled` 提前返回之前** —— 总统场图例是关的，而「小卡压主卡叠字」这类乱码恰恰发生在总统场。
12. **单场 `--boards` 渲染会覆写 `manifest.json`**，全量后要重跑 `--all`。
13. **总统选举名称用「届」不用「任」**：第九届（1996）～第十六届（2024），改 `_gen_president_boards.py` `YEAR_META` 的 `ordinal`。
14. **第 3 名以后的小卡不加背景色**：`layers.js` 已删 `minorCardBg()`，高卡／窄卡／清单格的白字直接落在街景暗化背景上，只保留政党色块 `minorBlock`。
15. **宋楚瑜 2000 是「无党籍」→ 灰，不是亲民党橘**（2012/2016/2020 才是橘）。三层要一起改：区级图 `Precident/maps/Draw_Region_Maps_AllYears.py`（组别 4→0）、图例 `NewSolution/tool/legend_president.py`（同 4→0）、看板政党色块 `_gen_president_boards.py`（`color` 覆写删掉走 `ind` 灰）。
16. **全量输出分两文件夹**：主版 16 场，市长 → `out/taipei/`、总统 → `out/president/`；`-map2` 变体只按需单独出。

---

## 6. 常见任务

### 6.1 改版面（最常做）

改 `boards/_engine/js/core/layout.js`（版面配置）或 `boards/_engine/js/render/layers.js`（绘制逻辑），然后：

```bash
$NODE tools/render_boards.mjs --boards 2000-president-north 2022-taipei-mayor --scale 1 --out ./NewSolution/out/_sample
$PY tools/verify_layout.py NewSolution/out/_sample/layout/*.json
```

两场 PASS 后再全量。

### 6.2 新增一场看板

1. 复制 `boards/_template/` 成 `boards/<id>/`
2. 改 `meta.json`：选举名称、年份、候选人（`key`/`name`/`party`/`partyShort`/`number`/`votes`/`pct`/`elected`，总统场另加 `vice`/`viceParty`）
3. 放 `source/data.xlsx` + 素材（`map.png`/`legend.png`/`city_seal.png`/`emblem.png`/`mark_elected.png`/`party_<key>.png`）
4. `$PY tools/build_board.py boards/<id>` → `$NODE tools/render_boards.mjs --all ...`

`--all` 会自动捡到新目录，**JS / Python 零改动**。

> 总统场不走这条：它没有 `source/`，由 `_gen_president_boards.py` 从项目外的 xlsx 直接建置（见 §3-B），一跑就出 `村里版 + 区级版` 两个变体。

### 6.3 新增一项素材

1. 原图丢进 `NewSolution/png/<kind>/`
2. 在 `NewSolution/tool/assets.map.json` 补一行配方
3. 若是新的**逻辑角色**，在 `tools/boardlib/naming.py` 的 `ASSETS` 加一条 `AssetSpec`（含 `engine_field`）
4. `$PY NewSolution/tool/build_assets.py --kind <kind> --force`
5. 引擎端用 `slide.js` 的 `_loadNamedImage(engineKey, src, sourceField, label)` 载入

**全域共享素材**（如国旗、街景：全专案只有一份、各场 `source/` 不放）要设 `AssetSpec.shared = True`，建置时缺了只警告不挡。

### 6.4 只改文案（不改几何）

```bash
$PY tools/build_board.py boards/<id> --skip-geo    # 省掉 SHP 处理，快很多
```

### 6.5 换村里界图资

改 `Converge_to_map_taipei.py` 的 `DATASETS`（市长链路）或 `_gen_president_boards.py` 的 `YEAR_META`（总统链路），再跑 `--refresh-geo` 重建该场缓存。

---

## 7. 故障排查

| 症状 | 原因 | 解法 |
|---|---|---|
| 渲染时素材 404 | 静态根设成 `boards/` | `--root Video/`（预设已是） |
| 地图边缘一圈白边 | 地图没做白→透明，或容差变了 | 跑 `build_assets.py`；地图容差固定 12 |
| 图例整片不见 | 把 `legend.png` 也做了白→透明 | 它 `how=copy`，原样搬 |
| 国旗的白色被吃掉 | 对 `roc_flag.png` 走了白→透明 | 它是 `CopyRecipe` |
| 看板整场变灰 | 早年资料栏位只有人名、无政党 | 查 `PARTY_COLOR_STOPS` / `PARTY_COLOR_GROUPS` |
| 宋楚瑜颜色不对（2000 该灰却变橘） | 只改了一处，三层没同步 | 区级图 / 图例 / 看板政党色块三处一起改（见铁律 15） |
| 2024 柯文哲徽章读不到 | `party_tpp.png` 还没做 | 见 §9「待办」——补「台灣民眾黨.png」源图 + 配方 |
| 村里对不到、留白 | 早年里界与图资不符 | 图资按年份切（`<2019` 用 106、`≥2019` 用 111） |
| 票数变双重曝光乱码 | 第 3 名/小卡压到主卡的 `pct`/`votes` | 头号地雷：卡片**不可**对齐主卡右缘（2476），L6 把关 |
| 单场渲染后其他场消失 | `--boards` 覆写了 `manifest.json` | 重跑 `--all` |
| 全量偶发 `/__save` HTTP 500 | 文件写入抖动 | 已加自动重试（3 次 / 400ms）；仍失败就单场补渲 |
| `verify_layout` 报 PermissionError | 参数传了**目录**不是 json | 用 glob：`.../layout/*.json` |

---

## 8. 验证规则速查（`tools/verify_layout.py`）

数据来自渲染时导出的 `out/layout/<id>.json`。任一 FAIL → 退出码 1。

| 规则 | 内容 |
|---|---|
| **L1** | 图例图片不得与**地图墨迹**相交 |
| **L2** | 图例图片不得与地图框相交（比 L1 更严） |
| **L3** | 图例图片不得与页眉 / 票数带 / 小卡 / 主卡任一块相交 |
| **L4** | 图例图片必须完整落在 contain 框内 |
| **L5** | contain 框必须完整落在画布内 |
| **L6** | 小卡带不得与主卡的 `pct` / `votes` 块相交 ★ 总统场（图例关闭）也照验 |
| **L7** | 小卡彼此不得相交 |
| **L8** | 每张小卡都要落在带的范围（`x0..x1`）内 |
| **L9** | 小卡不得压到地图墨迹（用**分段 `map.profile`** 比，不能用外接框） |
| **L10** | 区级图不得压到主地图墨迹（同样用分段 profile） |
| **L11** | 区级图不得与图例／页眉／票数带／小卡／主卡各块相交 |
| **L12** | 区级图必须完整落在画布内 |

**为什么 L9 不能用外接框**：地图外接框是 `x675–1465`，而「其他候选人」清单格在 `x676–900` —— 它明明在地图下方的空白处，用外接框比会误判成交。所以 `headless.js` 的 `alphaScan()` 扫 48 带、每带记左右墨迹边界（`map.profile`）。旧报告没有 `profile` 时自动退回旧逻辑。

**报告里有什么**：`map{frame,drawn,content,profile}`、`map2{...}`、`legend{box,image}`、`elements{header,ribbon,minor,minorCards[],cards[]}`、`legendDisabled`。

---

## 9. 现况与待办

**已完成（2026-10-15）**

- 32 场看板配置齐备（台北市长 8 届 ×2 + 总统北北基宜 8 届 ×2）
- 引擎定案：页眉徽章白卡 + 街景背景、小卡带（第 3 名高卡 + 左群）、总统场双图同板、副手行
- 验证扩到 L1–L12：两场新样本 2/2 PASS；全量 32 份报告（含 30 份旧引擎产出的历史报告）32/32 PASS
- 总统选举名称「第 X 届」（不再用「任」）；第 3 名以后小卡去底色
- 宋楚瑜 2000 配色改无党籍灰（三层同步）；全量主版 16 场已分 `out/taipei/` + `out/president/` 两文件夹输出

**尚未做**

- **`party_tpp.png`（台灣民眾黨徽章）缺失**：`party` 源图只有 kmt/dpp/nsc/pfp 四个，2024 总统场柯文哲渲染会退回抽象色块。补法：加「台灣民眾黨.png」源图 + `assets.map.json` `party` 段补 `party_tpp.png`，重跑 `build_assets.py --kind party`。
- **未 commit**
- 颜色量化等优化（`Converge` 的 5.69s → 0.27s）已验证 bit 相同但**尚未落地**

**效能基准（单场 2022）**

| 步骤 | 耗时 |
|---|---|
| `Converge` | 7.0 s（其中颜色量化 4.33 s = 最大块） |
| `build_board` | 2.5 s |
| 素材透明化 | 3.0 s |
| `render` | 0.7 s |
| `verify` | 1.26 s |

瓶颈在颜色量化 → Python 进程开销 → 人手串指令。批次化的下一步就是补一层编排（`build_all.py`）。

---

## 10. 一句话总结

> **素材（地图 + 透明化）→ 建置（只找图不做图）→ 渲染（CDP 无头）→ 验证（L1–L12）**。
> 改版面只渲 2000 总统与 2022 市长两场，过验证再全量；
> 全量主版 16 场分两文件夹（市长 → `out/taipei/`、总统 → `out/president/`）；
> 「新增一场」永远只是加一个 `meta.json` + `source/`，程式零改动。
