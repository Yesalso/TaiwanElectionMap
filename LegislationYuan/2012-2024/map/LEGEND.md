# 图例（Legend）生成说明

> 范围：`board/` 看板管道（`Video2022/` 为同构旧副本，逻辑一致）。
> 关联文档：`README.md`（整体管道）、`NATIONAL_BOARD_EXPERIENCE.md`（全国看板经验）。

## 0. 结论速览

1. **图例不是引擎画的**。色阶条是一张**离线预生成的透明 PNG**，引擎只负责 `contain` 贴图。
2. **生成端**：`src/tools/build_national_assets.py` 的 `build_legend()` / `build_legend2()`，配置与常量在 `src/tools/national_map.py`，色阶直接读 `Precident/color.txt`——与地图实际填色同一份数据，保证「图例上是什么色，地图上就是什么色」。
3. **渲染端**：`src/engine/js/render/layers.js` 的 `LegendLayer`，把图片 contain 进 `Layout.legend` 框，**不加底板**（透明底 + 白字，直接贴深色看板底）。

## 1. 链路总览

```mermaid
flowchart LR
  A["Precident/color.txt<br/>RATE_COLOR_STOPS"] --> B["national_map.load_ramps()<br/>按 RAMP_GROUP 取 4 组"]
  B --> C["build_legend()<br/>Pillow 2× 现画 960×236"]
  C --> D["dist/assets/national/legend.png<br/>+ maps.json 记 box"]
  D --> E["board.files.js<br/>逻辑名 legend.png"]
  E --> F["slide.js _loadLegend()<br/>http 读实体 / file 读内嵌"]
  F --> G["layers.js LegendLayer.draw()<br/>contain → drawImage"]
  G --> H["看板 480×118<br/>（页眉右侧 / 地图右栏）"]
  H --> I["verify_layout.py<br/>L1–L5 不压任何元素"]
```

## 2. 文件索引

| 文件 | 角色 |
|---|---|
| `src/tools/national_map.py` | 配置单一来源：路径、色阶分组、图例尺寸、刻度步长、字体 |
| `src/tools/build_national_assets.py` | 生成器：`build_legend()`（四家）、`build_legend2()`（两党） |
| `D:/Windows/TaiwanElection/Precident/color.txt` | 色阶数据（35% 起、5% 一阶），地图与图例共用 |
| `dist/assets/national/legend.png` | 成品图例（透明底 RGBA） |
| `dist/assets/national/maps.json` | 成品尺寸与 `box`，供建看板读取 |
| `dist/boards/<id>/board.files.js` | 逻辑素材名 → 实体路径 |
| `src/engine/js/slide.js` | `_loadLegend()` 载入策略 |
| `src/engine/js/render/layers.js` | `LegendLayer.draw()` 绘制 |
| `src/engine/js/core/layout.js` | `Layout.legend` 默认版面 + `meta.layout` 逐场覆盖 |
| `src/tools/_gen_national.py` | 把 `box` 写进 `meta.layout.legend` |
| `src/tools/_gen_boards.py` | 22 场县市长看板一律 `legend.disabled = true` |
| `src/tools/verify_layout.py` | 版面断言 L0–L5 |

## 3. 生成端

### 3.1 色阶数据源

`color.txt` 是一份 Python 串列字面，每组注释标明政党：

```python
RATE_COLOR_STOPS = [
    # 无党籍
    [
        (35, "#D9D9D9"), (40, "#C9C9C9"), (45, "#B6B6B6"), (50, "#A0A0A0"),
        (55, "#898989"), (60, "#727272"), (65, "#5B5B5B"), (70, "#464646"),
        (75, "#333333"), (80, "#232323"), (85, "#151515"),
    ],

    # 中国国民党
    [
        (35, "#A6E9FF"), (40, "#73D9FF"), (45, "#40C8FF"), (50, "#00C0F4"),
        (55, "#00A2E8"), (60, "#0080B8"), (65, "#006591"), (70, "#004B6B"),
        (75, "#003247"), (80, "#00283A"), (85, "#001F2E"), (100, "#010D29"),
    ],
    # …民主进步党 / 新党 / 宋楚瑜 / 民众党
]
```

`national_map.py` 用组索引把它映射成「政党 → 色阶」：

```python
COLOR_TXT = r"D:\Windows\TaiwanElection\Precident\color.txt"
# color.txt 的組別索引（由上而下）：0 無黨籍／1 國民黨／2 民進黨／3 新黨／4 宋楚瑜／5 民眾黨
RAMP_GROUP = {"中國國民黨": 1, "民主進步黨": 2, "台灣民眾黨": 5, "無黨籍": 0}
# 圖例顯示順序（使用者指定：國民黨 → 民進黨 → 民眾黨 → 無黨籍）
LEGEND_PARTIES = ["中國國民黨", "民主進步黨", "台灣民眾黨", "無黨籍"]


def load_ramps():
    """讀 color.txt（Python 串列字面）→ {政黨: [(上限%, "#RRGGBB"), …]}。"""
    with open(COLOR_TXT, encoding="utf-8") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    stops = ast.literal_eval("\n".join(lines).split("=", 1)[1])
    return {p: stops[RAMP_GROUP[p]] for p in LEGEND_PARTIES}
```

> 注意：`load_ramps()` 会过滤掉以 `#` 开头的注释行，所以 `color.txt` 里可以自由加注释。

### 3.2 版面常量

```python
# 圖例：放在頁眉右側（四行數據右邊、席次說明左邊），與地圖框不重疊。
LEGEND_BOX = {"x": 1600, "y": 62, "w": 480, "h": 118}
LEGEND_SCALE = 2            # 圖例 PNG 以 2× 繪製（960×236），contain 後仍清楚
# 圖例最上方那條「比例尺」：每 2 階標一次 = 每 10 個百分點（35／45／55／65…）。
LEGEND_TICK_STEP = 2

# 兩黨獨立圖例（不進看板版面）
LEGEND2_PARTIES = ["中國國民黨", "民主進步黨"]
LEGEND2_START = 40          # 只畫 >= 40 的階（KMT／DPP 各 11 格）
LEGEND2_SCALE = 2
LEGEND2_NAME_W = 250        # 黨名欄寬
LEGEND2_CELL = 86           # 每格寬（11 格 = 946）
LEGEND2_PITCH = 56
LEGEND2_CELL_GAP = 10
LEGEND2_RULER_H = 44
LEGEND2_FONT = {"name": 38, "tick": 26, "unit": 22}
LEGEND2_TICK_MAJOR = 10     # 只標 % 為 10 倍數且在 LEGEND2_TICK_MAX 以下的格
LEGEND2_TICK_MAX = 80
```

### 3.3 `build_legend()` —— 四家图例（进看板）

```python
def build_legend():
    """透明底圖例：四家政黨各自的得票率色階（直接讀 color.txt）。"""
    W, H = int(NM.LEGEND_BOX["w"] * NM.LEGEND_SCALE), \
           int(NM.LEGEND_BOX["h"] * NM.LEGEND_SCALE)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))     # 透明底
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    ramps = NM.load_ramps()

    rows = len(NM.LEGEND_PARTIES)                     # 4 列
    f_name = _font(34)
    name_w = 178                                      # 色條起點（黨名最寬 5 字 × 34 ≈ 170）
    cell = 65                                         # 每階 65px（12 階 = 780）

    # ---- 頂部比例尺：每 2 階（＝10 個百分點）標一次，刻度線對齊色階格線 ----
    SCALE_H = 40                                      # 2× 繪製 → 看板 20px
    widest = max((ramps[p] for p in NM.LEGEND_PARTIES), key=len)
    f_tick = _font(26)
    f_unit = _font(22)
    for j in range(0, len(widest), NM.LEGEND_TICK_STEP):
        pct = widest[j][0]
        x0 = name_w + j * cell
        d.line([x0, SCALE_H - 12, x0, SCALE_H - 3],
               fill=(255, 255, 255, 120), width=2)
        d.text((x0 + 4, SCALE_H - 40), "%d%%" % pct,
               font=f_tick, fill=(255, 255, 255, 205))
    # 尺規最右端補一個「以上」（最後一格是 85+，右對齊貼齊畫布邊）
    _t = "以上"
    d.text((W - 4 - d.textlength(_t, font=f_unit), SCALE_H - 36), _t,
           font=f_unit, fill=(255, 255, 255, 140))

    # ---- 四列色階 ----
    pitch = (H - SCALE_H) / rows                      # (236 − 40) / 4 = 49
    for i, party in enumerate(NM.LEGEND_PARTIES):
        top = SCALE_H + i * pitch
        d.text((2, top + 4), party, font=f_name, fill=white)
        ry = round(top + 4)
        rh = round(pitch - 9)                         # 色块高 40px（看板 20px）
        for j, (_, hexv) in enumerate(ramps[party]):
            col = tuple(int(hexv[k:k + 2], 16) for k in (1, 3, 5))
            x0 = round(name_w + j * cell)
            d.rectangle([x0, ry, x0 + cell - 1, ry + rh], fill=col + (255,))

    img.save(NM.OUT_LEGEND, "PNG", optimize=True)
```

几何账（2× 坐标）：

| 量 | 值 | 说明 |
|---|---|---|
| 画布 | 960 × 236 | `LEGEND_BOX` 480×118 × `LEGEND_SCALE` 2 |
| 党名列 | 178 px | 5 字 × 34px ≈ 170，留 8px 呼吸 |
| 每阶宽 | 65 px | 12 阶 = 780 → 178 + 780 = 958，右侧余 2px |
| 阶数 | 12 / 12 / 12 / 11 | 国民党、民进党、民众党有 100% 那阶；无党籍到 85% |
| 比例尺高 | 40 px | 看板 20px |
| 列高 | 49 px | 色块 40 + 间距 9 |
| 刻度 | 每 2 阶 | = 每 10 个百分点；只标在「最长那组」的格线上 |

**为什么 2× 绘制**：看板框 480×118，图 960×236 正好 2:1，`contain` 缩小一半即为 1:1 落地，避免非整数缩放导致的色块糊边与文字锯齿。

**为什么透明底 + 白字**：看板底色 `#0d1738`。旧版是「透明底 + 深色字 + 浅色圆角底板」，底板与白字反而糊成一片，现已整块移除——图例和地图一样，直接贴在看板底上。

### 3.4 `build_legend2()` —— 两党独立图例（不进看板）

```python
def build_legend2(start=None, parties=None, scale=None, ruler=True,
                  out=None, ink=(255, 255, 255)):
    S = scale or NM.LEGEND2_SCALE
    start = NM.LEGEND2_START if start is None else start
    parties = list(parties or NM.LEGEND2_PARTIES)
    dst = out or NM.OUT_LEGEND2
    ramps = NM.load_ramps()

    def px(v):                       # 邏輯單位 → 實際像素
        return int(round(v * S))

    cells = {p: [(pct, hx) for pct, hx in ramps[p] if pct >= start] for p in parties}
    n = max(len(v) for v in cells.values())
    ticks_src = cells[max(parties, key=lambda p: len(cells[p]))]

    name_w, cell = px(NM.LEGEND2_NAME_W), px(NM.LEGEND2_CELL)
    pitch, gap = px(NM.LEGEND2_PITCH), px(NM.LEGEND2_CELL_GAP)
    rh = pitch - gap
    ruler_h = px(NM.LEGEND2_RULER_H) if ruler else 0
    W = name_w + n * cell
    H = ruler_h + pitch * len(parties)

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f_name = _font(px(NM.LEGEND2_FONT["name"]))
    f_tick = _font(px(NM.LEGEND2_FONT["tick"]))
    f_unit = _font(px(NM.LEGEND2_FONT["unit"]))
    white = tuple(ink) + (255,)

    # ---- 頂部比例尺：每 10 個百分點標一次，刻度線對齊色階格線 ----
    if ruler:
        base_y = ruler_h - px(14)
        for j, (pct, _) in enumerate(ticks_src):
            if pct % NM.LEGEND2_TICK_MAJOR or pct > NM.LEGEND2_TICK_MAX:
                continue
            x0 = name_w + j * cell
            d.line([x0, base_y + px(4), x0, ruler_h - px(1)],
                   fill=tuple(ink) + (110,), width=max(2, px(0.75)))
            d.text((x0 + px(4), base_y), "%d%%" % pct, font=f_tick,
                   fill=tuple(ink) + (210,), anchor="ls")
        _t = "以上"                   # 最後兩格是 85／100（100＝85 以上），不標 100%
        d.text((W - px(6) - d.textlength(_t, font=f_unit), base_y), _t,
               font=f_unit, fill=tuple(ink) + (130,), anchor="ls")

    # ---- 两列色阶 ----
    for i, party in enumerate(parties):
        top = ruler_h + i * pitch
        cy = top + rh // 2
        d.text((px(4), cy), party, font=f_name, fill=white, anchor="lm")
        for j, (_, hexv) in enumerate(cells[party]):
            col = tuple(int(hexv[k:k + 2], 16) for k in (1, 3, 5))
            x0 = name_w + j * cell
            d.rectangle([x0, top, x0 + cell - 2, top + rh - 1], fill=col + (255,))

    img.save(dst, "PNG", optimize=True)
```

与 `build_legend()` 的差别只有三点：只列两党、色阶从 `LEGEND2_START`(40%) 起、尺寸自成一套（逻辑宽 1200，2× 绘制）；其余视觉语言（左党名 / 右色阶 / 顶部刻度尺）刻意保持一致。`ink` 参数可改文字与刻度颜色（白底场景要换成深色）。

### 3.5 运行入口

```python
if __name__ == "__main__":
    main()

# main() 里的开关：
#   --legend   只重画四家图例（跳过地图去底与 legend2）
#   --legend2  只重画两党图例
#   --no-ruler 两党图例不画比例尺
```

## 4. 渲染端

### 4.1 逻辑名 → 实体文件

引擎永远用逻辑名 `assets/legend.png`；建看板时写映射表：

```js
// dist/boards/2022-national/board.files.js（自动生成，勿手改）
window.BOARD_FILES = {
  "files": {
    "legend.png": "../../assets/national/legend.png",
    "map.png": "../../assets/national/county.png",
    "map2.png": "../../assets/national/town.png"
  }
};
```

来源：`_gen_national.py`

```python
legend_box = dict(asset_meta["legend"]["box"])      # 来自 maps.json
layout = {
    # 圖例擺在頁眉右側 → allowInHeader 讓 verify_layout 的 L3 不對整塊頁眉判定
    "legend": dict(legend_box, disabled=False, inner=0, title="",
                   allowInHeader=True),
    ...
}
```

### 4.2 载入

```js
// src/engine/js/slide.js
Slide.prototype._loadLegend = function () {
  var self = this;
  var A = global.NT_ASSETS || {};
  var src = U.resolveAsset((L.legend && L.legend.src) || '');

  function giveUp(reason) {
    if (src) console.warn('[Slide] 讀不到圖例（' + reason + '），看板不畫圖例區。');
    self.assets.legendSource = 'none';
    return null;
  }

  if (useEmbeddedUnderFile()) {               // file:// 下必须用内嵌副本，否则污染 canvas
    if (!A.legend) return Promise.resolve(giveUp('data/local-assets.js 沒有內嵌圖例'));
    return U.loadImage(A.legend).then(function (img) {
      self.assets.legendSource = 'embedded';
      return img;
    }).catch(function () { return giveUp('內嵌圖例解碼失敗'); });
  }

  if (!src) return Promise.resolve(giveUp('未設定 Layout.legend.src'));
  var url = src.indexOf('?') < 0 ? src + '?t=' + Date.now() : src;   // 防缓存
  return U.loadImage(url).then(function (img) {
    self.assets.legendSource = 'file';
    return img;
  }).catch(function () { return giveUp('讀不到 ' + src); });
};
```

失败一律返回 `null`，由 `LegendLayer` 静默跳过——宁可少一块图例，也不留空底板或开天窗。

### 4.3 绘制

```js
// src/engine/js/render/layers.js
LegendLayer.prototype.draw = function (ctx) {
  var img = this.assets.legend;
  if (!img) return;                            /* 沒有圖例就什麼都不畫 */
  if (L.legend && L.legend.disabled) return;   /* 逐場關閉 */

  var g = L.legend;
  var x = g.x, y = g.y, w = g.w, h = g.h;
  var inner = g.inner === undefined ? 16 : g.inner;

  ctx.save();
  ctx.globalAlpha = g.opacity === undefined ? 1 : g.opacity;

  var contentX = x + inner, contentY = y + inner;
  var contentW = w - inner * 2, contentH = h - inner * 2;
  if (g.title) {                               /* 可选小标题，默认不画 */
    var tSize = g.titleSize || 24;
    U.text(ctx, g.title, {
      x: contentX, y: contentY + tSize * 0.82,
      size: tSize, weight: g.titleWeight || 900,
      color: g.titleColor || '#ffffff',
      align: 'left', baseline: 'alphabetic', spacing: 2
    });
    contentY += tSize * 1.18 + (g.titleGap === undefined ? 12 : g.titleGap);
    contentH = y + h - inner - contentY;
  }
  if (contentH <= 8 || contentW <= 8) { ctx.restore(); return; }

  /* 圖例圖片：contain 進剩餘區域（保持原圖比例），水平／垂直置中 */
  var k = Math.min(contentW / img.width, contentH / img.height);
  var iw = img.width * k;
  var ih = img.height * k;
  var ix = contentX + (contentW - iw) / 2;
  var iy = contentY + (contentH - ih) / 2;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, ix, iy, iw, ih);
  ctx.restore();

  /* 記下落點，供自動化驗證量測 */
  this.assets.legendRect = {
    box: { x: x, y: y, w: w, h: h },
    image: { x: ix, y: iy, w: iw, h: ih },
    source: this.assets.legendSource
  };
};
```

关键点：

- **不画底板**。历史上曾铺 `Layout.legend.bg` 浅色圆角板撑对比，白字上线后反而糊成一片，已删除。
- **只做 contain**，不拉伸、不裁切；框比图大就居中留白。
- `legendRect` 是 `render_boards.mjs` 汇出 `layout.json` 的数据源，也是 `verify_layout.py` 的输入。

### 4.4 版面默认值

```js
// src/engine/js/core/layout.js
Layout.legend = {
  src: 'assets/legend.png',
  disabled: false,
  /* 右欄 1580–2024 置中：1580 + (444 − 352) / 2 = 1626 */
  x: 1626, y: 493, w: 352, h: 440,
  title: '',
  titleSize: 24, titleWeight: 900, titleColor: '#ffffff',
  titleGap: 12,
  inner: 18,
  opacity: 1,
  allowInHeader: false
};
```

逐场覆盖走 `LAYOUT_OVERRIDABLE`（浅层合并）：

```js
var LAYOUT_OVERRIDABLE = ['legend', 'map2', 'map', 'ribbon', 'minors'];
```

## 5. 逐场配置

### 5.1 全国看板（有图例）

`meta.layout.legend` 等于「页眉右侧 + 无内距 + 允许落在页眉带内」：

```json
"legend": {
  "x": 1600, "y": 62, "w": 480, "h": 118,
  "disabled": false, "inner": 0, "title": "", "allowInHeader": true
}
```

因为图例不占右侧空栏，`map2`（乡镇级图）才能同时存在：

```json
"map2": { "x": 1300, "y": 248, "w": 640, "h": 854,
          "enabled": true, "allowWithLegend": true }
```

### 5.2 22 场县市长看板（无图例）

```python
# src/tools/_gen_boards.py
layout = {"legend": {"disabled": True},
          "map": map_box,
          "map2": dict(map2_box, enabled=True)}
```

对应 `meta.json`：

```json
"layout": {
  "legend": {"disabled": true},
  "map":  {"x": 645.0, "y": 197.0, "w": 788.3, "h": 1032},
  "map2": {"x": 1469.3, "y": 363.0, "w": 534.7, "h": 700.1, "enabled": true}
}
```

原因有两层：

1. 右栏让给乡镇级地图（`map2`），一村里图 + 一乡镇图并排对照，信息密度更高。
2. 地图 PNG 本身不含图例——`script/Draw_CountyMayor_2022.py` 开头写明「**不画标题、不画图例**，只输出纯地图」。

因此 `dist/boards/2022-taipei/layout.json` 里图例落点是 `"legend": null`，`verify_layout.py` 走 L0 提前返回。

## 6. 版面校验

`render_boards.mjs --report` 把实际矩形写进 `layout.json`，`verify_layout.py` 逐条断言：

| 规则 | 内容 |
|---|---|
| L0 | 图例关闭 → 打印说明并跳过 L1–L5；图例没画却报了框 → 失败 |
| L1 | 图例图片 **不得与地图墨迹框**相交 |
| L2 | 图例图片 **不得与地图框**（设定值）相交——比 L1 更严，几何上杜绝压图 |
| L3 | 不得与页眉／票数带／小卡／主卡各块相交（`allowInHeader` 时只跳过页眉那一项） |
| L4 | 图片必须完整落在 contain 框内 |
| L5 | contain 框必须落在画布内 |

判定用 **image** 而非 **box**：图例已无底板，实际被画到的只有图片那一块；用外接框会把「色卡右侧空白」也算成占用，导致误判相交。

```python
# src/tools/verify_layout.py
# L3：圖例若宣告 inHeader（全國看板把它放在頁眉右側）就不對「整塊頁眉」判定 ——
#     頁眉是一個 0..W × 0..h 的大矩形，任何嵌在裡面的元素都必然「相交」，
#     那不是壓到，是設計。其餘元素（票數帶／小卡／主卡各塊）照驗。
for label, r in _obstacles(els):
    if label == "页眉" and leg.get("inHeader"):
        skipped.append(label)
        continue
    ov = _overlap(image, r)
    if ov is not None:
        bad.append("%s（重叠 %d×%d）" % (label, round(ov[2] - ov[0]), round(ov[3] - ov[1])))
```

## 7. 复现命令

```bash
PY="C:/Users/Windows/AppData/Local/Programs/Python/Python313/python.exe"
NODE="C:/Users/Windows/.workbuddy/binaries/node/versions/22.22.2-6/node.exe"
cd Mayors/2022NineInOne/board

# ① 只重画图例（不动地图去底）
PYTHONIOENCODING=utf-8 $PY src/tools/build_national_assets.py --legend
# ①' 两党独立图例（不画刻度尺加 --no-ruler）
PYTHONIOENCODING=utf-8 $PY src/tools/build_national_assets.py --legend2

# ② 重建看板数据（把新的 box 写进 meta.layout.legend）
PYTHONIOENCODING=utf-8 $PY src/tools/_gen_national.py

# ③ 渲染
$NODE src/tools/render_boards.mjs --boards 2022-national --scales 1.5

# ④ 版面验证（期望 23 份报告 0 未通过）
PYTHONIOENCODING=utf-8 $PY src/tools/verify_layout.py
```

> `--scale 1.5` 会被 `parseInt` 截成 1，多倍率要用 `--scales 1.5`。

## 8. 参数速查

| 参数 | 位置 | 作用 |
|---|---|---|
| `LEGEND_BOX` | `national_map.py` | 看板上的 contain 框（1600,62,480,118） |
| `LEGEND_SCALE` | `national_map.py` | PNG 相对看板框的倍数（2 → 960×236） |
| `LEGEND_TICK_STEP` | `national_map.py` | 每隔几阶标一次刻度（2 阶 = 10%） |
| `LEGEND_PARTIES` | `national_map.py` | 显示哪几家、按什么顺序 |
| `RAMP_GROUP` | `national_map.py` | 政党名 → `color.txt` 组索引 |
| `LEGEND2_*` | `national_map.py` | 两党图例的起始百分比、格宽、字体、刻度上限 |
| `disabled` | `Layout.legend` / `meta.layout` | 整块不画 |
| `inner` | `Layout.legend` | 图片内距（全国场 0，默认 18） |
| `title` | `Layout.legend` | 可选小标题，空串即不画 |
| `opacity` | `Layout.legend` | 图片整体透明度 |
| `allowInHeader` | `Layout.legend` | 声明图例位于页眉带内，L3 跳过页眉判定 |

## 9. 历史坑位

| # | 现象 | 结论 |
|---|---|---|
| 1 | 图例摆在地图框内（1540,700），2014 新北靠「台北盆地空洞」蒙混过关 | 换台北市后正好压在內湖／南港／信义／文山色块上 → 地图框收窄到 560–1580，图例独占右栏 |
| 2 | 深色文字贴在 `#0d1738` 上看不清 | 曾加浅色圆角底板；改白字后底板反而糊住文字 → 底板整个删除 |
| 3 | 白字图例过「白底转透明」会整片消失 | `build_assets.py` 对这张图走 `how=copy`，不做任何去背 |
| 4 | 别处的地图底色 `#323232` 与无党籍 75% 的 `#333333` 只差 1 | 去底前先用 `all_ramp_colors()` 保护「数据填色」，否则会被挖成透明（苗栗县事故） |
| 5 | 图例进页眉触发 L3「压到页眉（480×88）」 | 新增 `allowInHeader`，L3 只跳过页眉这一项，其余照验 |
| 6 | 四家图例沿用「拿国民党当范例」的单列写法，看不出其他三家阶数不同 | 读 `color.txt` 画四列，12/12/12/11 阶各自成条，起点对齐、阶宽固定 65px |
| 7 | 图例开着的场次右栏被占用，`map2` 无处可放 | `layout.map2.allowWithLegend` 显式放行（全国场图例已在页眉，不与地图框重叠） |

## 10. 附：2012 立委脚本的独立图例

`script/2012LegislatorParty.py` 与 board 管道无关，自带一套「按候选人分列、色块 + 文字竖排」的图例，直接合进成品 PNG。若维护的是那张图，改这里：

```python
def draw_legend_on(final_img, x0, y0, cand_names, stops_list, max_label_w, start_tier=0):
    """圖例：色塊用 ImageDraw 繪製；文字以 render_text_image 貼上（同 Converge_to_map.py）。"""
    draw_obj = ImageDraw.Draw(final_img)
    col_width = BLOCK_WIDTH + 4 + max_label_w
    col_positions = [x0 + i * (col_width + H_SPACING) for i in range(len(cand_names))]
    name_h = max((render_cand_name_img(nm).height for nm in cand_names), default=0)
    for col_idx, stops in enumerate(stops_list):
        x_start = col_positions[col_idx]
        if col_idx < len(cand_names):
            nm_img = render_cand_name_img(cand_names[col_idx])
            blit_rgba(final_img, nm_img, (x_start + (col_width - nm_img.width) / 2, y0))
        for i, (upper, color_hex) in enumerate(stops):
            y = y0 + name_h + COLUMN_TITLE_GAP + i * (BLOCK_HEIGHT + V_SPACING)
            draw_obj.rectangle(
                [x_start, y, x_start + BLOCK_WIDTH, y + BLOCK_HEIGHT],
                fill=color_hex, outline="#000000", width=1)
            prev = stops[i - 1][0] if i > 0 else start_tier
            limg = render_text_image_cached(
                [get_label_text(upper, prev, is_first=(i == 0), is_last=(i == len(stops) - 1))],
                LEGEND_LABEL_FONT_SIZE)
            blit_rgba(final_img, limg, (x_start + BLOCK_WIDTH + 4,
                                        y + (BLOCK_HEIGHT - limg.height) / 2))
```

差异对照：

| — | board 管道（全国看板） | 2012 脚本 |
|---|---|---|
| 形式 | 独立透明 PNG，引擎 contain 贴图 | 直接画进成品图 |
| 分列单位 | 政党（四家 / 两家） | 候选人 |
| 色块朝向 | 横向铺开，顶部一条比例尺 | 纵向堆叠，每格右侧标区间 |
| 文字 | 纯白、无描边 | 文字渲染成图片再贴，带黑框区分 |

---

## 11. 本项目的历届图例（`map/legend/<年份>.png`）

上面 §3 讲的是 board 看板用的图例；**本项目（`LegislationYuan/2012-2024`）另有一套独立图例**，供 `map/` 下那批白底得票率地图使用。

- **生成器**：`script/build_legends.py`（Pillow 现画，不依赖 board 管道）
- **输出**：`map/legend/2008.png`、`2012.png`、`2016.png`、`2020.png`、`2024.png`（透明背景 RGBA，文件名即选举年份）
- **色阶**：直接读 `LegislationYuan/color.txt`（7 组：无党籍／国民党／民进党／新党／宋楚瑜／民众党／无党团结联盟），与地图填色同一份数据

```bash
PYTHONIOENCODING=utf-8 $PY script/build_legends.py        # 全部年份
PYTHONIOENCODING=utf-8 $PY script/build_legends.py 2024   # 只做指定年份
```

### 11.1 和 board 版的差异

**沿用**：色阶数据（`color.txt`）、字型（`national_map.FONT_CANDIDATES`：源石黑體 TW Heavy → 微软正黑粗体，逐字同源）、左党名／右色阶的排版、顶部每 2 阶一条刻度、最右端「以上」。

| — | board 版（§3.3） | 本项目版 |
|---|---|---|
| 文字颜色 | 纯白（贴深色看板） | **深灰 `#1C1E22`**（地图是白底，白字看不见） |
| 背景 | 透明 | 透明（可直接叠在地图留白处） |
| 列哪些政党 | 固定四家 | **只列该届地图上真的出现过的色阶组** |
| 尺寸 | 960×236（2× 绘，落地 480×118） | 2402×440～752（1× 绘，直接叠在 9077×12500 的地图上） |

> 字型只认 `FONT_CANDIDATES` 的顺序，本机取到的是 `%LOCALAPPDATA%\Microsoft\Windows\Fonts\gensekigothictw-heavy.ttf`；换机器若没装源石黑体，会自动退回 `C:\Windows\Fonts\msjhbd.ttc`（字形略窄，空格位置不变，无需改常数）。

### 11.2 每年列哪些政党（由地图实际用色决定）

判定方法（两道交叉核对）：

1. 把该届成品 PNG 的像素与 `color.txt` 的 7 组色阶逐一比对 —— 地图填色只用色阶色，命中即代表该组出现过；
2. 对照生成日志 `map/_run_2016_2020_2024.log`、`_run_village.log` 里的 **「領先村里」** 统计（村里级，即主图口径）。

| 年份 | 图例列 | 领先村里统计 | 说明 |
|---|---|---|---|
| 2008 | 国民党、民进党 | —（2008 图来自 2008 项目） | 全图仅第 1／2 组色阶 |
| 2012 | 国民党、民进党、**绿党** | 国民党 5,025／民进党 2,966／**绿党 2** | 绿党用 `CUSTOM_RAMPS` 补自订色（见 §11.3） |
| 2016 | 国民党、民进党、无党团结联盟 | 民进党 6,589／国民党 1,361／无党团结联盟 22 | 第 6 组粉红；**无灰阶** |
| 2020 | 国民党、民进党、民众党、**时代力量** | 民进党 4,412／国民党 3,497／**民众党 1**／**时代力量 1** | 民众党第 5 组青绿；时代力量第 8 组金黄 |
| 2024 | 国民党、民进党、民众党、**时代力量** | 民进党 4,539／国民党 3,319／**民众党 40**／**时代力量 1** | 同上 |

> **时代力量自成一色（2026-11-12 起）**：`color.txt` 新增第 8 组，最终定版为金黄 5 阶 —— 40 `#FFE300`／45 `#E8B70D`／50 `#CFA30C`／55 `#997909`／60 `#695207`。地图脚本 `PARTY_COLOR_GROUP` 已加 `時代力量: 7`；图例只填 40–60 这 5 格，35 与 65 以后留白。
> **2012 与 2008 的图例已不同**（多了绿党一行）。

### 11.3 自订色与口径差

- **2012 的绿党（自订色，已画进图例）**：村里统计有 2 个台东村里由绿党领先，原图把它们画成自订绿 `#25BF52`（40% 以上）、`#27CC58`（45% 以上）—— 两个色都不在 `color.txt` 内。图例用 `CUSTOM_RAMPS = {"綠黨": [(40, "#25BF52"), (45, "#27CC58")]}` 补上，**只填 40% 与 45% 两格，其余留白**（不加任何说明文字）。
- **灰阶的署名**：第 0 组灰阶是「没有专色的政党」共用。哪一届只被一个党用，就直接写党名；若同届有多个小党吃灰阶，才写「無黨籍／其他政党」。**2026-11-12 时代力量改用自己的金黄之后，这 5 届图例已没有灰阶行**（原先 2020／2024 那 2 个里改吃第 8 组）。
- **阶数**：国民党／民进党／民众党 12 阶（35–85 各一阶＋100）；无党团结联盟 11 阶（到 85）；时代力量 5 阶（40–60）；绿党 2 阶（40、45）。每格 150px、**按百分刻度对齐**，所以短的行两端留白 —— 与 §3.3 的四家图例一致。
- **平票斜线纹不单列**：村里第 1、2 名同票时地图叠 45° 斜线纹（2012 有 20 处、2024 有 18 处），那不是第三种颜色，图例不表示。
