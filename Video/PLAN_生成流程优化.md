# Video 生成流程优化计划

> 版本：v1（2026-10-28）
> 范围：`D:\Windows\TaiwanElection\Video` 全流程（素材 → 建置 → 渲染 → 合成）
> 状态：**P0/P1 大部分已实施**（见下「实施记录」）；P2-2/P2-3/P2-4 未动。
> 本文件同时充当执行记录，未实施项仍保留原始描述。

---

## 实施记录（2026-10-28）

**回归基线**：`dist/_baseline_board_sha.txt`（96 个 board.js/board.files.js/index.html）、
`dist/_baseline_png_sha.txt`（32 张 PNG）、`invaild/_baseline_png_20261028/`（141MB 全量副本）。
每步改动后都做了逐字节比对，**最终全量 32 场重渲 → 32/32 与基线逐字节相同**。

| 任务 | 状态 | 实际改动 | 验证结果 |
|---|---|---|---|
| P0-3 清理 | ✅ | 僵尸目录 `dist/boards/2014-newtpei-mayor`（已是空目录）删除；9 个 `.cache/` 清掉 | 场次数 33→32 |
| P0-2 归档 | ✅ | 46 张 中彰投/雲嘉南/高屏 原图 → `src/president/maps/_unused/<year>/{1,2}/` | 每年在用目录只剩 北北基宜＋桃竹苗（2+2）；`build_assets --check` 0 缺件 |
| P1-4 去时间戳 | ✅ | `utils.js` 增 `BUILD_TOKEN`/`Utils.stampUrl()`；`slide.js` 6 处改调用；渲染 URL 带 `&v=<runId>` | 32 场 PNG 逐字节不变 |
| P1-5 单导航多倍率 | ✅ | `render_boards.mjs` scale 循环移进 `Page.navigate` 之内 | 1× PNG 逐字节不变；2 倍率 3.27s → 1.85s |
| P0-1 WebP 能力 | ✅（默认仍 png） | `headless.js __saveBoard(scale,name,format,quality)`；`--format/--quality`；契约检查接受 `.png/.webp` | 见下「WebP 实测」——**q95 未达 42dB 验收线**，默认暂不改 |
| P1-3 geo 缓存 | ✅ | 新 `geo_cache_path()`：`dist/.cache/geo/<县市>__<图资>__s60__r5.json`；`load_geojson()` 三层优先（memo→磁盘→重建） | 9 份重复缓存 → 2 份；`board.js` 逐字节不变 |
| P2-1 编排器 | ✅ | 新 `src/tools/build_all.py`；`build_board.main()` 重构为 `build_one()`；总统线按年份调生成器 | 台北 8 场 1.57s/场 → **0.6s 全量**；8 场 `board.js` 全部未变 |
| P1-2 单入口 | ✅ | 新 `boardlib/entry.py`；入口落 `dist/boards/_entry/index.html`（与场次同深度）；32 份 index.html 删除 | 全量 32 场渲染成功、逐字节不变 |
| 颜色量化提速（计划漏项） | ✅ | `_quantize_to_allowed()` 改 uint32 打包 + `unique(return_inverse)` + LUT；`make_map` 去掉重复的内联实现 | 2022 地图 13.99s → **4.00s**；map/map2/legend **逐字节相同** |
| P1-1a 补 `region.mapVariant` | ⏭ 跳过 | **前提不成立**：8 个 `-map2` 场次从来不是 `build_board` 建的（`_gen_president_boards.py` 直写产物），补字段只会让「用 build_board 重建」这件事看起来可行、实际会改掉 `board.js` | — |
| P1-1b 取消 `-map2` 场次 | 🟡 机制已就绪，**未删场次** | `--variants map,map2` + `layout.js` 读 `?mapVariant=map2`；实测「1950 行目检等价」升级为**逐字节等价** | `2000-president-north` 主版＋map2 版重渲 → 与现有 PNG 逐字节相同，`layout.json` 也相同。**删 8 个目录需你点头**（触碰「北北基宜线不重跑」约定） |
| P2-2 背景烘焙 | ⬜ 未做 | — | — |
| P2-3 board-kit | ⬜ 未做 | — | — |
| P2-4 脚本合并 | ⬜ 未做 | — | — |

### WebP 实测（P0-1 的决策依据，全部 2022-taipei-mayor 实测）

| 方案 | 体积 | PSNR | 结论 |
|---|---|---|---|
| 原 PNG | 4.60 MB | — | 基线 |
| WebP q95 | 0.52 MB（11%） | **38.96 dB** | 未达计划自定的 42 dB；边缘有可见振铃（maxdiff 128） |
| WebP q99 | 0.70 MB（15%） | 39.30 dB | 同上，收效甚微 |
| **WebP q1.0** | **2.56 MB（56%）** | **∞（像素全等）** | q=1.0 时 Chrome 走无损，零画质损失，32 张约 -44MB |
| PNG optimize=True | 3.32 MB（72%） | ∞ | 需 PIL 后处理，与「渲染器零依赖」冲突 |

> 结论：**q95 的 -90% 体积是拿画质换的**，而你的交付档要进后期合成（`dist/final` → `make_video.py`），
> 二次损失不划算。建议 `--format webp --quality 1`（无损、-44%），或维持 png 不动。
> 默认值保持 `png` 就是为了不擅自改交付格式。

### 跟进记录（同日第二轮：处理「视频断链」与「--force 改画面」）

**① 视频链路已打通（草稿级）**

- `make_video.py` 新增 `--check`（只点家底）、`--draft`（用 `dist/dist_png` 顶替）、
  以及合成前的统一预检：缺图/缺配乐一次列清，并给出下一步命令，不再等 ffmpeg 跑到一半报错。
- TIMELINE 的旧编号（831/832…1112）已能反推年份（民国年 = 西元 − 1911，末位 1=区级图 / 2=村里图）。
- 补齐了视频缺的 8 张「区级图」帧：`node render_boards.mjs --boards <8 场> --variants map,map2`
  → `dist/dist_png/taipei-mayor/<年>-map2.png`（新增 8 张，dist_png 141MB → 176MB）。
- 实测出片：`invaild/_tmp/video/臺北市長選舉1994-2022_2560x1440_草稿.mp4`
  （6:35.46、2560×1440、24fps、无声，编码 57s）。**链路本身没问题，缺的只是你的后期图与配乐。**
- 还缺：`dist/final/<编号>.png` 16 张（后期合成版）、`dist/final/MP3/*.mp3` 6 首。

**修复过程中发现并修掉的两个真 bug**

- 变体机制对**市長场**此前是坏的：`board.files.js` 没有 `map2.png` 这一项，
  把 `Layout.map.src` 改成逻辑名 `assets/map2.png` 会解析失败 → 地图整片空白
  （2022 区级版渲染出来中间是空的）。改成在 `slide.js` 对**已解析的实际路径**做
  `map.png → map2.png` 替换，两条线都正常；总统线变体仍与基线逐字节相同。
- `_loadMap2` 增加「主图已是区级版就不再画右栏」的短路，避免同一张图叠两遍。

**② `--force` 会改画面：根因已定位，不是「成品过期」那么简单**

- 新增 `python src/mapgen/tool/build_assets.py --check-drift`：重算一遍（写临时文件）并与
  既有成品逐像素比对，**只报告不写档**。当前结果：`一致 47 / 漂移 17`。
- 漂移集中在台北线的 7 个年份（1994/1998/2002/2006/2010/2018/2022），总统线 0 漂移。
- 根因：`Converge_to_map_taipei.py` 的**民进党绿色阶**是 `#C9F2DE / #A8E8C9 / #7EDBB2`（青绿），
  而 `Precident/color.txt`（总统线读的那份、也是记忆里铁律 6 写的约定）是
  `#E8FFE0 / #C0FFB1 / #A4FF90 / #78FF4F`（黄绿）。
  **现存 dist/assets 成品的绿（#78FF4F、#68DE45）精确等于 color.txt 的档位**，
  说明台北脚本的 DPP 色阶曾偏离过 color.txt，而源图在 2026-10-09 被按偏离版重生成，
  成品没跟着更新 —— 于是「成品符合约定、源图不符合」。
- 另有第二层差异：1994/1998 源图留白比成品多 5.41%（2002/2006 多 0.71%），
  即新版把「图资有里、excel 无资料」的里留白（1998 有 24 个），旧版则上了色。
- **结论：不能简单 --force。** 要么先把台北脚本的 DPP 色阶改回 `color.txt` 再重生成 + 重做成品 +
  重渲 7 场看板；要么明确接受青绿新版。两条路都会改变交付画面，需要你定。

### 仍未处理

3. **北北基宜 16 场的 `board.files.js` 缺 `party_ind.png`**：2000 年宋楚瑜／许信良（无党籍）
   渲染时告警「读不到政党徽章」，退回抽象色块。要修得重跑那条线，按约定未动。
4. `assets/share/` 下今天新增了 `新竹.png`、`高雄.png` 两张街景（另有 `街景1.png` 闲置），
   看起来在铺新竹/高雄市长线 —— P0-2 归档的是总统分区图，不影响，但新线会用到新的街景素材。
5. WebP 与「删 8 个 `-map2` 场次」两件事仍待你决定（见上表）。

---

## 0. 一页结论

审计确认"生成逻辑存在浪费"，量化如下（基线为 2026-10-28 实测）：

| 维度 | 现状 | 可回收 | 主要手段 |
|---|---|---|---|
| 磁盘 | 291 MB（dist 167 / assets 80 / src 44） | **~148 MB** | PNG→WebP 127MB、未用地图归档 21MB |
| 素材 I/O | 每场 ~4–5MB × 64 次 ≈ 250–300MB | **-95%** | 去掉 headless 的时间戳、整批共享缓存 |
| 渲染单位 | 32 场（其中 8 场为镜像冗余） | **-25%** | 取消 `-map2` 场次，改用 variant 参数 |
| 建置耗时 | ~60–100s（逐场起进程） | **-80%** | 单进程编排 + geo 记忆化 |
| 代码 | 3 组近重复脚本 + 跨项目整套副本 | **减半** | 合并 video/gen 脚本；抽出 board-kit |

**红线（全程不可违反）**

1. `assets/candidate/`（109 张 / 43MB）**有用素材，不删、不移、不改、不转换**。任何清理脚本必须先排除该目录。
2. 除本计划列出的目标外，**其他地方的产物与行为保持不变**：32 张看板的画面内容必须逐像素等价（P0-1 除外，它改的是编码格式而非像素布局，需人工目检确认）。
3. 不修改 `src/boards/*/meta.json` 里与显示有关的字段（election/candidates/districts/header 等）。

---

## 1. 现状基线（实测，可复现）

### 1.1 目录体积

| 路径 | 体积 | 备注 |
|---|---|---|
| `dist/dist_png` | 141 MB | 32 张 PNG，manifest 记录合计 140.1 MB（4.4 MB/张） |
| `assets` | 80 MB | `candidate` 43M（**保留**）、`map` 22M、`share` 16M |
| `src` | 44 MB | `president/maps` 36M（每年 10 张只用 4 张） |
| `dist/assets` | 26 MB | 透明化成品，81 个文件 |
| `dist/boards` | 1.4 MB | 32 场 × (board.js / board.files.js / index.html / layout.json) |

### 1.2 关键实测值

| 项目 | 值 | 测法 |
|---|---|---|
| 单场 1× 渲染耗时 | 1.07 s | `node src/tools/render_boards.mjs --boards 2022-taipei-mayor --scale 1` |
| 2 场 × 1,2× 耗时 | 3.27 s | 同上，`--scales 1,2`（含 Edge 启动） |
| PNG → WebP q95 | 4.60 MB → **0.47 MB（10%）** | PIL `save('WEBP', quality=95, method=6)` |
| PNG → WebP q90 | 4.60 MB → 0.32 MB（7%） | 同上 |
| PNG `optimize=True` | 4.60 MB → 3.03 MB（66%） | 仅调 zlib 参数 |
| `geo.build()` | 0.32–0.54 s | 读全台 SHP + dissolve（不含 1.0s 的 geopandas import） |
| `index.html` 重复度 | 32 份 **sha256 全同** | `sha256sum dist/boards/*/index.html \| uniq -c` |
| `board.js` 重复度 | 8 对完全相同（32 份中 16 份两两成对） | `*-president-north{,-map2}` |
| geojson 缓存重复 | 8 个台北场各存 15243 B **相同内容** | `dist/boards/*/.cache/geojson.json` |
| 渲染器跨项目重复 | 438 行中 **437 行相同** | `Video/src/tools/render_boards.mjs` vs `Mayors/2022NineInOne/Video2022/…` |
| 引擎跨项目漂移 | 12 个文件 9 个字节相同；`layers.js` 差 461 行、`headless.js` 711 行、`layout.js` 125 行 | `diff` 逐文件 |

### 1.3 已确认的冗余点（逐条对应后文任务）

| 编号 | 现象 | 位置 | 归入任务 |
|---|---|---|---|
| R1 | PNG 出口 141MB，信息熵对 PNG 极不友好（街景照片 + 大面积渐变） | `headless.js:117`、`render_boards.mjs:95` | P0-1 |
| R2 | 总统原图每年 10 张只用到 4 张（北北基宜 + 桃竹苗） | `src/president/maps/<year>/{1,2}/` | P0-2 |
| R3 | 8 个 `-map2` 场次与主版 `board.js` 字节相同，仅 `board.files.js` 一行不同 | `src/boards/*-president-north-map2/` | P1-1 |
| R4 | 8 份相同 geojson 缓存，且放在**产物目录**（清 dist 即丢） | `build_board.py:372` | P1-3 |
| R5 | 素材 URL 带 `?t=Date.now()`，跨场/跨倍率缓存 100% 失效 | `slide.js` 6 处（108/178/217/297/346/386） | P1-4 |
| R6 | 每个倍率各 `Page.navigate` 一次，重载模型与素材 | `render_boards.mjs:435-500` | P1-5 |
| R7 | 逐场起 Python 进程，每场重复 import geopandas + 读全台 SHP | `build_board.py` CLI | P2-1 |
| R8 | 背景层每场重画 7 层（含 3.55MB 街景缩放），组合数仅 6–18 种 | `layers.js:186-284` | P2-2 |
| R9 | `render_boards.mjs` / `engine` 跨项目整套复制且已分叉 | `Video` vs `Mayors/2022NineInOne/Video2022` | P2-3 |
| R10 | 3 个 `make_*video.py` 共同 79 行；`_gen_president_boards{,_tzmm}.py` 83% 相同 | `src/tools/` | P2-4 |
| R11 | `verify_board.py` 硬编码已不存在的 `Video/boards/2014-newtpei-mayor` | `src/tools/verify_board.py:4` | P3-1 |
| R12 | `src/boards/<id>/source/` 7MB 素材副本，仅为 `check_sources()` 存在性检查 | 32 场 | P3-2 |

### 1.4 计划外的现状发现（仅记录，不在本次范围）

- `dist/final/` 与 `dist/videos/` **均为空目录**，`make_video.py` 依赖的 `dist/final/831.png` 等文件不存在 → 视频合成链路当前处于断链状态，需另行补齐素材。
- `src/boards/2014-newtpei-mayor/` 带 `.skip` 标记（不参与 `--all`），但 `dist/boards/` 仍留有它的产物目录与 77KB `.cache`（僵尸产物）。
- 根目录 `_tmp_seals.png`（644KB）全仓零引用，为临时文件。

---

## 2. P0 —— 无损回收（预期 -148MB，半天内完成并可回滚）

### P0-1 PNG 出口改 WebP（-127MB，最高优先级）

**问题**：`canvas.toBlob(cb, 'image/png')` 输出的是未经优化的 PNG。看板底色是大面积渐变、背景是街景照片，这类内容用无损逐像素编码约 90% 的体积是格式浪费。

**改动文件（2 个）**

1. `src/engine/js/headless.js`

```js
// 现状（第 89-123 行）
global.__saveBoard = function (scale, name) {
  return renderToCanvas(scale).then(function (cv) {
    ...
    cv.toBlob(function (blob) { ... }, 'image/png');
```

改为接受格式与质量参数，保持向后兼容（不传 = png）：

```js
global.__saveBoard = function (scale, name, format, quality) {
  var mime = 'image/' + (format || 'png');
  var q = (quality === undefined) ? 0.95 : quality;
  return renderToCanvas(scale).then(function (cv) {
    ...
    cv.toBlob(function (blob) { ... }, mime, mime === 'image/png' ? undefined : q);
```

2. `src/tools/render_boards.mjs`

- `pngNameOf()`（第 95-99 行）增加格式参数：`${stem}.${ext}`，ext 由 `opts.format` 决定（默认 `webp`）。
- `--saveBoard` 调用处（第 473 行）传 `opts.format, opts.quality`。
- `MIME` 表已含 `.webp`（第 321 行），`/__save` 的档名白名单 `[A-Za-z0-9._-]` 不影响 `.webp`。
- 新增参数：`--format webp|png`（默认 `webp`）、`--quality 0.95`。
- `manifest.json` 的 `file` 字段自然跟随新扩展名；`listNonPng()` 的契约检查需同步（现只允许 `.png`，改为允许 `.png/.webp`）。

**验收**

| 项 | 标准 |
|---|---|
| 体积 | `du -sh dist/dist_png` ≤ 20MB（基线 141MB） |
| 像素 | 同场 WebP 与旧 PNG 叠合，PSNR ≥ 42dB；文字边缘无可见色斑（人工目检 1 张台北 + 1 张总统） |
| 渲染 | 32 场全部成功，`manifest.json` 32 笔 ok |
| 版面 | `verify_layout.py` 32 份报告 0 未通过（该脚本不依赖图片格式） |

**风险与回退**

- 风险：WebP 有损 + 后续视频编码 = 二次损失。若最终要出 4K 视频母版，画质敏感。
- 缓解：保留 `--format png` 开关；或采用"双出口"（默认 WebP 交付 + `--master png` 生成母版到 `dist/dist_png/_master/`，母版不进交付）。
- 回退：`--format png` 重跑即可，无需改代码；旧 PNG 在切换前先备份到 `dist/_backup_png/`。

**建议的执行方式**：先只渲 1 场（`--boards 2022-taipei-mayor`）出对比样张，确认画质后再全量。

---

### P0-2 未使用地图原图归档（-21MB）

**问题**：`src/president/maps/<year>/` 每年有 5 个区域 × 2 个层级 = 10 张，实际只用到北北基宜与桃竹苗（对应 `map.png`/`map2.png`/`map_tzmm.png`/`map2_tzmm.png`）。中彰投、雲嘉南、高屏 3 个区域 × 8 年 ≈ 48 张从未被任何看板引用。

**做法（移动，不删除）**

```
src/president/maps/<year>/{1,2}/中彰投*.png   → src/president/maps/_unused/<year>/
src/president/maps/<year>/{1,2}/雲嘉南*.png   → 同上
src/president/maps/<year>/{1,2}/高屏*.png     → 同上
```

**验证**

```bash
# 1. 确认没有被引用（应为空）
grep -rn "中彰投\|雲嘉南\|高屏" src/mapgen src/tools src/president/*.py

# 2. 确认 4 张在用的图仍在原位
ls src/president/maps/1996/2/北北基宜*.png src/president/maps/1996/2/桃竹苗*.png

# 3. 重跑素材管线应仍为 0 缺件
python src/mapgen/tool/build_assets.py --check
```

**风险**：若未来要做「中彰投/雲嘉南/高屏」看板，需从 `_unused/` 取回。这是纯延迟决策，不损失信息。

---

### P0-3 临时文件与僵尸产物（-1MB，顺手）

| 对象 | 动作 | 说明 |
|---|---|---|
| `Video/_tmp_seals.png` | 移到 `invaild/` | 644KB，全仓零引用 |
| `dist/boards/2014-newtpei-mayor/` | 保留场次，清掉 `.cache/` | 该场带 `.skip`，产物目录里的 77KB 缓存无意义 |
| `src/boards/2014-newtpei-mayor/.cache`（若存在） | 删除 | 已被 .skip 的场次不应留缓存 |

> 注：`invaild/` 是既有的归档目录，本计划沿用，不新建目录。

---

## 3. P1 —— 结构性去重（预期 场次 -25%、I/O -95%、缓存可控）

### P1-1 `-map2` 镜像场次归一（渲染单位 32 → 24）

**问题**：`_gen_president_boards.py:222` 用循环一次产出两场：

```python
for suffix, map_target in (("", "map.png"), ("-map2", "map2.png")):
```

两场 `board.js` 字节相同、`index.html` 相同、`layout.json` 相同，**唯一差异**是 `board.files.js` 的 `map.png` 指向。

**同时存在一个隐患**：`build_board.py` 早已支持正规机制 `meta.region.mapVariant = "map2"`（`manifest.py:83-92`、`naming.py:183-206`），但 `-map2` 场次的 `meta.json` 里**没有 `region` 字段**。因此任何人跑一次 `build_board.py boards/1996-president-north-map2`，都会把地图指回 `map.png` —— 该场次是"手工产物"，不受建置链管控。

**分两步走（先安全，再彻底）**

**第一步（当天，零风险）**：给 8 个 `-map2` 场次的 `meta.json` 补上正规字段，让建置链能正确重建：

```json
"region": { "mapVariant": "map2" }
```

验证：重跑 `build_board.py boards/1996-president-north-map2` 后，`board.files.js` 仍指向 `map2.png`（当前若不补，会被改成 `map.png`）。

**第二步（结构归一，需改引擎与渲染器）**：取消独立场次，改为同一场次 + 渲染变体。

- `render_boards.mjs` 增加 `--variants map,map2`：对同一场次渲染两次，URL 加 `&mapVariant=map2`。
- `slide.js` 读取 `location.search` 的 `mapVariant`，覆盖 `Layout.map.src`（`assets/map.png` → `assets/map2.png`）。`Utils.resolveAsset` 已能按 `board.files.js` 的 key 解析，`map2.png` 本来就在 files 表里，无需后端改动。
- `pngNameOf()` 保持现有命名：`<year>-map2.webp`（交付文件名不变）。
- 删除 `src/boards/*-president-north-map2/`（8 个目录）与对应 `dist/boards/*-map2/`。

**验收**：`dist/dist_png/president-north/{year}-map2.webp` 与改造前的 `{year}-map2.png` 目检等价；场次数从 32 降到 24。

**风险**：`--map2` 变体的 `map2.png` 同时被 `Map2Layer` 用于右栏（总统场图例关闭时才画）。切主图为 map2 后需确认 `Map2Layer` 跳过（现有逻辑：`L.legend.disabled` 且 `assets.map2` 存在时画右栏 —— 会出现"主图和右栏是同一张图"的重复）。**必须处理**：variant=map2 时把 `Layout.map2.enabled` 置 false。

> 结论：第一步必做（修隐患）；第二步收益是"少 8 个目录"，改动面较大，建议放在 P1 末尾、单独一次提交，便于回退。

---

### P1-2 `index.html` 单入口（产物去重）

**现状**：`write_index_html()`（`build_board.py:198-209`）把模板复制到每场目录，32 份 sha256 全同。

**做法**：保留 `src/templates/index.html` 作为唯一模板，渲染 URL 改为

```
dist/boards/_entry.html?board=<id>&headless=1
```

`_entry.html` 内动态注入：

```html
<script>
  var b = new URLSearchParams(location.search).get('board') || '';
  document.write('<script src="../' + b + '/board.js"><\/script>');
  document.write('<script src="../' + b + '/board.files.js"><\/script>');
</script>
```

**连带改动**：`write_board_files_js()` 用 `os.path.relpath(path, board.out_dir)` 生成 `../../assets/...`（相对 `dist/boards/<id>/`）。入口上移一层后要改为相对 `dist/boards/`，即 `../assets/...`。**这是唯一容易踩的坑**，改完必须验证地图能正常加载（浏览器控制台无 404）。

**验收**：24（或 32）场渲染成功；`dist/boards/*/index.html` 全部消失；`board.files.js` 路径以 `../assets/` 开头。

**风险**：中断"直接双击 `dist/boards/<id>/index.html` 打开"的旧用法。若需保留，可让 `_entry.html` 在 `file://` 下同样工作（相对路径一致即可）。

---

### P1-3 geojson 缓存集中化（去 8 份重复，且不被 clean 误删）

**现状**：`build_board.py:372`

```python
cache_path = args.geo_cache or os.path.join(board.out_dir, ".cache", "geojson.json")
```

`board.out_dir` = `dist/boards/<id>/` —— 缓存放在**产物目录**里。8 个台北场次各存一份 15243 B 的相同文件；任何清理 dist 的操作都会连带丢缓存。

**做法**：按内容寻址，集中到 `dist/.cache/geo/`：

```python
def geo_cache_path(board, want):
    key = "%s__%s__s%g__r%d" % (
        want["county"], want["id"], want["simplify"], want["round"])
    return os.path.join(naming.VIDEO_ROOT, "dist", ".cache", "geo", key + ".json")
```

`provenance_matches()` 校验逻辑不变（key 已含 provenance 关键字段，仍保留比对作二次保护）。

**收益**：台北 1994–2018 共用一个文件；新建 P2-1 编排器后同进程内再记忆化一层。

**验收**：`dist/.cache/geo/` 下文件数 = 不同 (county, 图资, simplify) 组合数（当前应为 2–3 个）；重跑 `build_board.py` 打印"沿用"而非"重建"。

---

### P1-4 headless 关闭素材时间戳（I/O -95%）

**现状**：`slide.js` 6 处

```js
var url = src.indexOf('?') < 0 ? src + '?t=' + Date.now() : src;
```

设计意图是"换图后刷新页面能看到新版"，对交互式正确；但批量渲染时每场每次加载都换 URL，浏览器 HTTP 缓存必然 miss —— 每场都要重新下载并解码 `street_bg.png`（3.55MB）、地图（0.15–0.55MB）、徽章与图例。

**做法**：集中成一个工具函数，交互式与批处理分开：

```js
// utils.js 新增
var BUILD_TOKEN = (function () {
  var q = (global.location && global.location.search) || '';
  if (q.indexOf('headless=1') >= 0) {
    var m = /[?&]v=([\w.-]+)/.exec(q);
    return m ? m[1] : '0';          // 同批内固定 → 命中缓存
  }
  return String(Date.now());        // 交互式仍强刷
})();
Utils.stampUrl = function (src) {
  return src.indexOf('?') < 0 ? src + '?t=' + BUILD_TOKEN : src;
};
```

`slide.js` 6 处替换为 `U.stampUrl(src)`。`render_boards.mjs` 在页面 URL 末尾追加 `&v=${runId}`（`runId` 在一次批处理开始时生成一次）。

**验收**：渲染同一批 8 场，Edge 的 Network 面板（或服务端 `/__save` 之外的请求计数）显示 `street_bg.png` 只请求 1 次；全批耗时下降。

> 若不方便统计请求数，可直接在 `serveStatic()` 里对静态文件请求打点计数，跑完打印 top-10，作为"缓存命中"的客观证据（建议顺手加，成本几行）。

---

### P1-5 一次导航渲多倍率（同场成本减半）

**现状**：`render_boards.mjs:435-500`，`for (const board)` 内嵌 `for (const scale)`，每个倍率执行一次 `Page.navigate` + `__boardReady` + `__saveBoard`。

**做法**：把 scale 循环移到 `Page.navigate` 之内（`__saveBoard` 本来就接受 scale，`renderToCanvas` 每次新建 canvas，互不干扰）：

```js
await cdp.send('Page.navigate', { url });
await loaded;
await ready();
for (const scale of opts.scales) {
  const name = pngNameOf(boardId, scale, opts.format);
  const info = await cdp.evaluate(
    `window.__saveBoard(${scale}, ${JSON.stringify(name)}, ${JSON.stringify(opts.format)}, ${opts.quality})`,
    180000);
  ...
}
```

`--report` 仍只在首个倍率跑一次（逻辑不变）。

**验收**：2 场 × 1,2× 的耗时低于改造前的 3.27 s（预计 ~2.2 s）；PNG 逐字节与改造前一致（格式不变时）。

---

## 4. P2 —— 架构级（收益随场次规模放大）

### P2-1 编排器 `build_all.py`（建置耗时 -80%）

**问题**：`build_board.py` 是单场 CLI，批量要靠 shell 循环，每场付一次进程启动代价（`import geopandas` ≈ 1.0s + 读全台 SHP 0.2–0.5s + dissolve 0.3–0.5s）。32 场约 45–65s 是纯重复。

**做法**：新增 `src/tools/build_all.py`

- 一次进程内遍历 `src/boards/*/meta.json`（尊重 `.skip`）。
- 用 `dict` 记忆化 `geo.build()`：key = `(county, source_id, simplify, shp)`，同 county+图资只 dissolve 一次。
- 复用 `build_board.main()` 的逻辑需先重构成 `build_one(board, opts)` 函数（当前全部写在 `main()` 里，直接 import 无法复用）。
- 提供 `--only <id...>` / `--all` / `--skip-geo` / `--check`。

**验收**：全量建置 ≤ 15 s；`board.js` 逐字节与逐场跑一致（这是关键回归断言）。

---

### P2-2 背景层烘焙（每场省 7 层合成 + 3.55MB 大图缩放）

**现状**：`BackgroundLayer.draw()`（`layers.js:186-284`）每场每倍率依次画：街景 cover 缩放 → 渐层 → 2 个径向光晕 → 374 条格线 → 水印轮廓 → 光带 → 暗角。

**可烘焙性分析**：

| 层 | 依赖 | 是否确定 |
|---|---|---|
| 街景 + 渐层 + 格线 + 光带 + 暗角 | 常量 | 完全确定 |
| 两个光晕 | `T.party(glowLeft/Right).main` | 取决于左右两侧政党 → 组合数 ≤ 6–18 |
| 水印轮廓 | `assets.projectorBackdrop`（本场 geojson） | 3 种（台北 / 北北基宜 / 桃竹苗） |

**做法**：`dist/bake/bg-<colorPairHash>-<outlineId>-<scale>.webp`，命中则一次 `drawImage`，未命中现画并写盘。建议先用 `--bake` 开关灰度上线，比对像素差为 0 后再默认开启。

**验收**：烘焙前后同场 PNG **逐字节相同**（这是最强断言；若因抗锯齿差异不成立，退化为 PSNR ≥ 50dB）。

---

### P2-3 抽出 `Shared/board-kit`（跨项目复用，止住漂移）

**现状**：`Video/src/tools/render_boards.mjs` 与 `Mayors/2022NineInOne/Video2022/src/tools/render_boards.mjs` —— 438 行中 437 行相同。两套 `src/engine` 12 个文件中 9 个字节相同，`layers.js` 已分叉 461 行、`headless.js` 711 行、`layout.js` 125 行。分叉的恰恰是最需要统一维护的渲染逻辑。

**做法**：

```
Shared/board-kit/
  engine/            ← 单一真相（layers/headless/layout/slide/…）
  tools/render_boards.mjs
  tools/verify_layout.py
  tools/build_assets.py
  board.config.schema.json
```

各项目只保留 `board.config.json`（尺寸 2560×1440 / 3840×2160、输出命名规则、素材根、素材映射），用配置驱动差异。这是**大改**，建议在 P0/P1/P2-1~2 稳定后再做，且必须先建立"改造前 32 张图逐字节基线"作为回归依据。

**风险**：Video2022 已在 4K + 中文档名上跑通（见当日记录），合并时要以其已验证行为为基线之一，避免把 Video 的旧规则反向带回。

---

### P2-4 脚本合并（维护成本减半）

| 现状 | 合并为 | 差异如何表达 |
|---|---|---|
| `make_video.py` / `make_precident_video.py` / `make_precident_tzmm_video.py`（共同 79 行：时间轴、xfade、acrossfade、响度拉平） | `make_video.py --profile <name>` | 时间轴与曲目外置 `src/tools/video_profiles/*.json` |
| `_gen_president_boards.py` / `_gen_president_boards_tzmm.py`（190/229 行相同，83%） | `_gen_president_boards.py --region north\|tzmm` | 区域集合、layout 常量、board id 后缀外置 |

**验收**：合并后同一 profile 产出的 mp4，时长/音轨/画面与旧脚本一致（用 `verify_video.py` 比对，或比对 ffprobe 时长 + 逐段响度）。

---

## 5. P3 —— 可选净化（不影响主链路）

| 编号 | 对象 | 动作 | 说明 |
|---|---|---|---|
| P3-1 | `src/tools/verify_board.py` | 删除或改参数化 | 硬编码 `D:\...\Video\boards\2014-newtpei-mayor`，该目录已不存在，脚本必失败 |
| P3-2 | `src/boards/<id>/source/` 7MB 素材副本 | 改为声明式 | `check_sources()` 现在只验证"文件在不在"，实际建置读 `dist/assets/`。可改为校验 `dist/assets/` 中对应文件存在，`source/` 只留 `data.xlsx` + `meta.json` |
| P3-3 | `dist/boards/<id>/layout.json` | 移到 `dist/report/<id>.json` | 校验报告与看板产物混放；`verify_layout.py` 需同步路径 |
| P3-4 | `assets/share/街景1.png`、`街景3.png`（12MB） | 待确认 | 当前只用 `街景2.png` → `street_bg.png`。**这两张是否保留需你确认**，本计划不擅自处置 |

> P3-2 涉及 32 个目录的素材副本，改动面较大且收益仅 7MB，建议放到最后或不做。

---

## 6. 执行顺序与依赖

```
P0-1 (WebP)  ──┐
P0-2 (归档)  ──┤ 互相独立，可并行
P0-3 (清理)  ──┘
        │
        ▼
P1-1 第一步（补 region.mapVariant）  ← 独立，优先做（修隐患）
        │
        ▼
P1-4 (去时间戳) ─→ P1-5 (多倍率单导航)   ← 都改 render_boards.mjs，同一次提交更省
        │
        ▼
P1-3 (geo 缓存集中) ─→ P2-1 (build_all.py)
        │
        ▼
P1-2 (单入口 index.html)   ← 改产物结构，和 P2-1 一起验证
        │
        ▼
P1-1 第二步（取消 -map2 场次）  ← 改动面最大，单独提交
        │
        ▼
P2-2 (背景烘焙) → P2-3 (board-kit) → P2-4 (脚本合并)
```

**建议的提交切分**（每步一个 commit，便于回退）：P0-1 / P0-2+3 / P1-1a / P1-4+5 / P1-3 / P2-1 / P1-2 / P1-1b / P2-2 / P2-3 / P2-4。

---

## 7. 回归基线（每次改动前先拍）

在动手之前必须先固化"改造前"基线，否则无法证明"其他地方没变"：

```bash
# 1. 全量快照现有产物哈希
cd D:/Windows/TaiwanElection/Video
find dist/boards -type f \( -name "board.js" -o -name "board.files.js" \) \
  -exec sha256sum {} \; | sort -k2 > dist/_baseline_board_sha.txt

find dist/dist_png -type f -name "*.png" -exec sha256sum {} \; \
  | sort -k2 > dist/_baseline_png_sha.txt

# 2. 存档一份当天全量 PNG（供目检与像素比对；约 141MB）
#    若磁盘吃紧，至少留 3 张代表场：1994-taipei / 1996-president-north / 1996-president-tzmm

# 3. 记下建置与渲染耗时
time (for d in src/boards/*/; do python src/tools/build_board.py "$d"; done)
time node src/tools/render_boards.mjs --all --scale 1
```

**判定标准**

| 改动类型 | 允许的差异 |
|---|---|
| P0-1（改格式） | 像素允许 PSNR ≥ 42dB；`board.js` / `board.files.js` 必须逐字节不变 |
| P0-2、P0-3（移文件） | 全部产物逐字节不变 |
| P1-*、P2-*（改流程） | `board.js` 逐字节不变；PNG（格式不变时）逐字节不变 |

---

## 8. 收益汇总（预期）

| 指标 | 基线 | P0 完成 | P1 完成 | P2 完成 |
|---|---|---|---|---|
| 项目总体积 | 291 MB | **~143 MB** | ~100 MB | ~100 MB |
| `dist/dist_png` | 140.1 MB | **~14 MB** | ~12 MB | ~12 MB |
| 渲染单位（场次） | 32 | 32 | **24** | 24 |
| 素材 I/O / 全批 | ~250–300 MB | 同 | **~5 MB** | ~5 MB |
| 全量建置 | ~60–100 s | 同 | ~30 s | **~10 s** |
| 全量渲染（1×） | ~35 s | ~35 s | **~20 s** | ~18 s |
| 渲染器代码副本 | 2 套（已漂移） | 2 套 | 2 套 | **1 套** |
| 视频合成脚本 | 3 个近重复 | 3 个 | 3 个 | **1 个** |

> `assets/candidate` 43MB **全程保留**，不计入回收项。

---

## 9. 风险登记

| 风险 | 影响 | 概率 | 应对 |
|---|---|---|---|
| WebP 有损影响 4K 视频母版画质 | 中 | 中 | 保留 `--format png`；或双出口（母版 PNG 不入交付） |
| 单入口 `index.html` 的 `board.files.js` 相对路径错一层 | 高（地图 404） | 高 | 改完立刻渲 1 场，看控制台 404；`board.files.js` 必须 `../assets/` 开头 |
| variant=map2 时主图与右栏重复 | 中 | 中 | variant=map2 时置 `Layout.map2.enabled=false` |
| 取消 `-map2` 场次后交付文件名变化 | 中 | 低 | `pngNameOf()` 保持 `<year>-map2` 主干部不变 |
| `build_all.py` 重构 `main()` 引入回归 | 高 | 中 | 断言 `board.js` 逐字节不变 |
| 合并 board-kit 时把 Video 旧规则带回 Video2022 | 高 | 中 | 以 Video2022 已验证行为为基线之一，逐场对拍 |
| 缓存集中后被误删 | 低 | 低 | `dist/.cache/` 加 `.gitignore`，清理脚本显式排除 |

---

## 10. 需要你确认的三件事

1. **WebP 还是 PNG？** 默认 `--format webp --quality 0.95`（4.6MB→0.47MB），还是双出口（交付 WebP + 母版 PNG）？影响 P0-1 的实现方式。
2. **`assets/share/街景1.png`、`街景3.png`（12MB）是否保留？** 当前只用 `街景2.png`。你说了候选人的图有用，这两张同理我不敢擅动。
3. **`-map2` 是保留为独立交付，还是改成渲染变体？** 若两种图都必须作为独立文件交付，P1-1 第二步只做"补 `region.mapVariant`"（第一步）即可，收益从 -25% 降为"修复重跑隐患"。
