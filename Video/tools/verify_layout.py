# -*- coding: utf-8 -*-
"""verify_layout.py —— 版面自动验证：图例（legend）不得压到任何东西。

为什么需要这支脚本
------------------
「图例有没有压到地图」以前只能靠眼睛看。2018／2022 换成台北市之后，
图例从原本「新北市地图中间那个台北盆地空洞」挪到了地图正中央偏右，
正好盖住内湖／南港／信义／文山的村里色块 —— 没人看出来，直到出图被肉眼抓到。
这里把这条规则写成可执行断言，改版面时跑一次就知道有没有复发。

数据从哪来
----------
`node tools/render_boards.mjs` 默认会把每场看板的实际矩形导出到
    out/layout/<board-id>.json
内容包括：
  map.frame      Layout.map 的框（设定值）
  map.drawn      地图图片实际落点（MapLayer 记下来的值）
  map.content    地图的**墨迹**外接框 —— 扫 alpha > 16 逐像素求得。
                 台北的直式地图像四周留白很多，只看 drawn 会误判，
                 所以「有没有压到地图」一律以 content 为准。
  legend.box     图例的 contain 框（Layout.legend，设定值）
  legend.image   图例图片实际矩形 —— 图例已无底板，实际上只有这块被画到，
                 所以「有没有压到东西」以 image 为准
  elements.*     页眉 / 底部票数带 / 小卡（各一颗矩形），以及
                 cards —— 左右主卡逐块拆开的子矩形（left/card、left/chip、
                 left/name、left/pct、left/votes…）。
                 主卡不給外接框：它是 274–1403 × 1967–2533 的一长条，
                 外接框会把「色卡右側的空白」也算成占用，图例一比就误判成相交。

判定规则（任一 FAIL 即退出码 1）
-------------------------------
  L1  图例图片不得与地图墨迹框相交
  L2  图例图片不得与地图框（设定值）相交 —— 比 L1 更严：
      图例整个落在框外，「压在地图上」在几何上就不可能发生
  L3  图例图片不得与页眉 / 票数带 / 小卡 / 主卡任一块相交
  L4  图例图片必须完整落在 contain 框内
  L5  contain 框必须完整落在画布内

另外会印一张「其他元素 × 地图」的对照表当参考（不判定），
方便顺手看出别的元素有没有贴到地图。

用法：
    python tools/verify_layout.py                    # 验 out/layout/ 下所有场次
    python tools/verify_layout.py out/layout/*.json  # 指定档案
"""

from __future__ import annotations

import json
import os
import sys

# 判定容差（看板座标像素）。相交面积在两个方向都超过这个值才算「压到」，
# 避免「刚好贴着边」被误判。
TOL = 1.0

# 图例必须避开的「整块式」元素，以及给人看的标签
OTHER_ELEMENTS = [
    ("header", "页眉"),
    ("ribbon", "底部票数带"),
    ("minor", "小卡"),
]


def _obstacles(els):
    """把「图例要避开的元素」摊平成一串 (标签, 矩形)。

    含整块元素（页眉／票数带／小卡）与主卡的每一个子块。
    """
    out = []
    for key, label in OTHER_ELEMENTS:
        r = els.get(key)
        if r:
            out.append((label, r))
    for item in els.get("cards") or []:
        name = item.get("name") or "card"
        rect = item.get("rect")
        if not rect:
            continue
        side, _, part = name.partition("/")
        out.append(("%s主卡·%s" % ("左" if side == "left" else "右", part), rect))
    return out


def _rect(r):
    """把报告里的矩形正规化成 (x0, y0, x1, y1)。"""
    return (float(r["x"]), float(r["y"]),
            float(r["x"]) + float(r["w"]), float(r["y"]) + float(r["h"]))


def _overlap(a, b):
    """相交矩形；不相交回 None。"""
    ax0, ay0, ax1, ay1 = _rect(a)
    bx0, by0, bx1, by1 = _rect(b)
    x0, y0 = max(ax0, bx0), max(ay0, by0)
    x1, y1 = min(ax1, bx1), min(ay1, by1)
    if x1 - x0 <= TOL or y1 - y0 <= TOL:
        return None
    return (x0, y0, x1, y1)


def _fmt(r):
    return "x %-6.0f y %-6.0f w %-6.0f h %-6.0f" % (
        float(r["x"]), float(r["y"]), float(r["w"]), float(r["h"]))


def _gap(label_a, rect_a, rect_b):
    """两个矩形在 x 方向的净空（正 = 分离，负 = 重叠）。"""
    ax0, _, ax1, _ = _rect(rect_a)
    bx0, _, bx1, _ = _rect(rect_b)
    if ax1 <= bx0:
        return bx0 - ax1
    if bx1 <= ax0:
        return ax0 - bx1
    return -min(ax1 - bx0, bx1 - ax0)


def check_one(path):
    """验一份报告，回传 (board, [(规则, 是否通过, 说明)])。"""
    with open(path, encoding="utf-8") as f:
        rep = json.load(f)

    board = rep.get("board") or os.path.splitext(os.path.basename(path))[0]
    cv = rep.get("canvas") or {}
    leg = rep.get("legend")
    mp = rep.get("map")
    els = rep.get("elements") or {}
    rows = []

    if not leg:
        rows.append(("L0", False, "报告里没有 legend（图例没画？LegendLayer 没记落点）"))
        return board, rows

    # 图例已经没有底板了：实际被画到的只有 image，
    # 所以「有没有压到东西」用 image 比（box 只是保留的 contain 框）。
    box, image = leg.get("box") or leg.get("panel"), leg.get("image")
    if not box or not image:
        rows.append(("L0", False, "报告里没有 legend（图例没画？LegendLayer 没记落点）"))
        return board, rows

    # L1 / L2：地图
    if mp and mp.get("content"):
        ov = _overlap(image, mp["content"])
        rows.append(("L1", ov is None,
                     "图例图片 × 地图墨迹框 → %s"
                     % ("不相交（净空 %.0f px）" % _gap("legend", image, mp["content"])
                        if ov is None else "相交 %s" % str(tuple(round(v) for v in ov)))))
    else:
        rows.append(("L1", True, "地图墨迹框不可得（无地图素材？），略过"))

    if mp and mp.get("frame"):
        ov = _overlap(image, mp["frame"])
        rows.append(("L2", ov is None,
                     "图例图片 × 地图框 → %s"
                     % ("不相交（净空 %.0f px）" % _gap("legend", image, mp["frame"])
                        if ov is None else "相交 %s" % str(tuple(round(v) for v in ov)))))
    else:
        rows.append(("L2", True, "地图框不可得，略过"))

    # L3：其他元素（页眉／票数带／小卡／主卡各子块）
    bad = []
    for label, r in _obstacles(els):
        ov = _overlap(image, r)
        if ov is not None:
            bad.append("%s（重叠 %d×%d）"
                       % (label, round(ov[2] - ov[0]), round(ov[3] - ov[1])))
    rows.append(("L3", not bad,
                 "图例图片 × 页眉／票数带／小卡／主卡各块 → "
                 + ("全部不相交" if not bad else "压到 " + "、".join(bad))))

    # L4：图片必须在 contain 框内
    inside = (_rect(image)[0] >= _rect(box)[0] - TOL
              and _rect(image)[1] >= _rect(box)[1] - TOL
              and _rect(image)[2] <= _rect(box)[2] + TOL
              and _rect(image)[3] <= _rect(box)[3] + TOL)
    rows.append(("L4", inside,
                 "图例图片落在 contain 框内 → %s（图片 %s）"
                 % ("是" if inside else "否", _fmt(image))))

    # L5：contain 框必须在画布内
    if cv:
        ok = (float(box["x"]) >= -TOL and float(box["y"]) >= -TOL
              and float(box["x"]) + float(box["w"]) <= float(cv["w"]) + TOL
              and float(box["y"]) + float(box["h"]) <= float(cv["h"]) + TOL)
        rows.append(("L5", ok, "图例 contain 框落在画布 %sx%s 内 → %s"
                     % (cv.get("w"), cv.get("h"), "是" if ok else "否")))

    return board, rows


def print_advisory(rep):
    """参考用：其他元素 × 地图墨迹框，不判定。"""
    mp = rep.get("map")
    els = rep.get("elements") or {}
    if not mp or not mp.get("content"):
        return
    hits = []
    for label, r in _obstacles(els):
        if _overlap(r, mp["content"]) is not None:
            hits.append(label)
    if hits:
        print("    参考：这些元素与地图墨迹框有交集（不判定）→ %s" % "、".join(hits))


def main(argv):
    if argv:
        paths = argv
    else:
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "out", "layout")
        if not os.path.isdir(root):
            print("[错误] 找不到 %s；先跑 node tools/render_boards.mjs" % root)
            return 2
        paths = sorted(os.path.join(root, n) for n in os.listdir(root)
                       if n.lower().endswith(".json"))
    if not paths:
        print("[错误] 没有可验证的版面报告")
        return 2

    failed = 0
    for p in paths:
        board, rows = check_one(p)
        ok = all(r[1] for r in rows)
        print("\n[%s] %s" % ("PASS" if ok else "FAIL", board))
        for rule, passed, msg in rows:
            print("   %-4s %-4s %s" % (rule, "·" if passed else "✗", msg))
        if not ok:
            failed += 1
        with open(p, encoding="utf-8") as f:
            try:
                print_advisory(json.load(f))
            except Exception:                                  # noqa: BLE001
                pass

    print("\n[结果] %d 份报告，%d 份未通过" % (len(paths), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
