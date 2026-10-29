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
`node src/tools/render_boards.mjs` 默认会把每场看板的实际矩形导出到
    dist/boards/<board-id>/layout.json
（PNG 走另一个出口 dist/dist_png/<id>.png；报告不是图片，跟看板产物放一起）
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
  L6  小卡（第 3 名起，elements.minor）不得与主卡的得票率／得票数块相交。
      2024／2020／1996 的「第 3 名卡压住第 2 名主卡、票数叠成乱码」就是这个。
      ★ 这条在 legendDisabled（总统看板）的场次也照验，不受 L0 提前返回影响。
  L7  小卡彼此不得相交（elements.minorCards：第 3 名高卡／第 4、5 名小卡／
      「其他候选人」格）。卡片宽 = 内容自然宽，所以任何相交都是排布算错。
  L8  每张小卡都要落在带的范围（elements.minor，x0..x1）内 —— 越界就会
      撞到主卡区，而这一点用「整条带」比会看不出来。
  L9  小卡（第 3 名高卡 /「其他候选人」清单格）不得压到地图墨迹。
      这两张卡会往上长（比左群高），而地图是置中的直式图、下半部墨迹很窄
      （y1230 的框内已无墨迹），所以它们本来就该落在地图下方的空白处。
      比对用 map.profile（分段墨迹，见 headless.js 的 alphaScan）——
      拿整张地图的外接框比会把「清单格明明在空白处」误判成压到。
      旧报告没有 profile 时退回「只看第 3 名高卡 × 外接框」。
  L10 區級圖（第二張圖，report 的 map2）不得压到主地图墨迹 —— 一样用分段 profile 比。
  L11 區級圖不得与图例／页眉／票数带／小卡／主卡各块相交。
  L12 區級圖必须完整落在画布内。
      ★ L10–L12 只有「图例关掉」的场次（总统北北基宜看板）才有 map2：
      那一栏本来是空的，引擎把區級版地图摆进去（Layout.map2 / Map2Layer）。
      与 L6／L9 同理，这几条排在 legendDisabled 的提前返回「之前」。

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

    # L6：小卡（第 3 名起）不得压到主卡的得票率／得票数块。
    # ★ 必须在 legendDisabled 的提前返回「之前」判定 —— 总统北北基宜看板
    #   图例是关掉的，而 2024／2020／1996 的「第 3 名卡压主卡」正是发生在
    #   那些场次（小卡叠上去，票数就变成双重曝光的乱码）。
    band = els.get("minor")
    if band:
        bad = []
        for item in els.get("cards") or []:
            name = item.get("name") or ""
            if not (name.endswith("/pct") or name.endswith("/votes")):
                continue
            rect = item.get("rect")
            if not rect:
                continue
            ov = _overlap(band, rect)
            if ov is not None:
                bad.append("%s（重叠 %d×%d）"
                           % (name, round(ov[2] - ov[0]), round(ov[3] - ov[1])))
        rows.append(("L6", not bad,
                     "小卡带 × 主卡得票率／票数块 → "
                     + ("全部不相交" if not bad else "压到 " + "、".join(bad))))
    else:
        rows.append(("L6", True, "本场无第 3 名以后候选人（无小卡带），略过"))

    # L7 / L8：逐张小卡（MinorCandidateLayer 记在 elements.minorCards）。
    # 卡宽 = 内容自然宽 → 只要位置算对，卡与卡之间就只剩 gap，绝不相交；
    # 反过来，卡片越界到主卡区在「整条带」的粒度上也看不出来，所以逐张挡。
    mcards = els.get("minorCards") or []
    if mcards:
        bad = []
        for i in range(len(mcards)):
            for j in range(i + 1, len(mcards)):
                ov = _overlap(mcards[i]["rect"], mcards[j]["rect"])
                if ov is not None:
                    bad.append("%s × %s（重叠 %d×%d）"
                               % (mcards[i].get("name"), mcards[j].get("name"),
                                  round(ov[2] - ov[0]), round(ov[3] - ov[1])))
        names = "、".join(str(c.get("name")) for c in mcards)
        rows.append(("L7", not bad,
                     "小卡彼此不相交（%d 张：%s）→ %s"
                     % (len(mcards), names,
                        "全部不相交" if not bad else "相撞 " + "、".join(bad))))

        out_of = []
        if band:
            bx0, by0, bx1, by1 = _rect(band)
            for item in mcards:
                r = item.get("rect")
                if not r:
                    continue
                x0, y0, x1, y1 = _rect(r)
                if (x0 < bx0 - TOL or x1 > bx1 + TOL
                        or y0 < by0 - TOL or y1 > by1 + TOL):
                    out_of.append("%s（x %.0f..%.0f）" % (item.get("name"), x0, x1))
            rows.append(("L8", not out_of,
                         "每张小卡都落在带 x %.0f..%.0f 内 → %s"
                         % (bx0, bx1, "是" if not out_of else "越界 " + "、".join(out_of))))

        # L9：小卡（第 3 名高卡 / 「其他候选人」清单格）不得压到地图墨迹。
        # 这两张卡都往「上」长（比左群高），左缘虽然落在 x0..x1 内，
        # 但地图是「置中的直式图」——下半部墨迹很窄（2022 在 y1100 以下
        # 只剩 x≈1009–1280，y1230 框内已无墨迹），所以它们本来就该落在
        # 地图下方的空白处。这条把「往上长」钉住：把 x1 往左挪、或把卡加宽
        # 到压到地图，立刻 FAIL。
        # ★ 比对用 map.profile（分段墨迹）而不是 map.content（整张外接框）：
        #   外接框是 x 675–1465，「其他候选人」清单在 x 675–900 就会被误判。
        #   旧报告没有 profile → 退回只看第 3 名高卡 × content（旧行为）。
        bigcard = None
        for item in mcards:
            if str(item.get("name") or "").startswith("big:"):
                bigcard = item
                break
        if mp and mp.get("profile"):
            bad, gaps = [], []
            for item in mcards:
                r = item.get("rect")
                if not r:
                    continue
                y0, y1 = _rect(r)[1], _rect(r)[3]
                near = [b for b in mp["profile"]
                        if min(_rect(b)[3], y1) - max(_rect(b)[1], y0) > TOL]
                if not near:
                    continue
                hits = [b for b in near if _overlap(r, b) is not None]
                if hits:
                    bad.append("%s（与 %d 段墨迹相交）"
                               % (item.get("name"), len(hits)))
                else:
                    gaps.append(min(_gap("", r, b) for b in near))
            rows.append(("L9", not bad,
                         "小卡 × 地图墨迹（分段，%d 带）→ %s"
                         % (len(mp["profile"]),
                            "全部落在空白处（最小净空 %.0f px）" % min(gaps)
                            if (not bad and gaps)
                            else ("全部落在空白处" if not bad
                                  else "压到 " + "、".join(bad)))))
        elif bigcard and mp and mp.get("content"):
            ov = _overlap(bigcard["rect"], mp["content"])
            rows.append(("L9", ov is None,
                         "第 3 名高卡 × 地图墨迹外接框 → %s"
                         % ("不相交（净空 %.0f px）"
                            % _gap("bigcard", bigcard["rect"], mp["content"])
                            if ov is None else "相交 %s" % str(tuple(round(v) for v in ov)))))
        else:
            rows.append(("L9", True, "本场无第 3 名高卡或地图墨迹框不可得，略过"))
    else:
        rows.append(("L7", True, "本场无逐张小卡报告（无第 3 名以后候选人），略过"))

    # L10 / L11 / L12：區級圖（第二張圖）。
    # 總統「北北基宜」場把圖例關掉了（meta.layout.legend.disabled），地圖右側
    # 那一欄本來整片空著 —— 引擎會把**區級版地圖**（assets/map2.png，
    # 只畫區、不畫里，與村里版同畫布同範圍）擺進去，讓同一張看板同時有
    # 「村里的圖」與「區級的圖」（見 layout.js 的 Layout.map2、layers.js 的
    # Map2Layer）。這裡把「它只能待在那一欄」寫成斷言：
    #   L10 不得壓到主地圖墨跡（一樣用分段 profile 比，不是整張外接框）
    #   L11 不得與圖例／主卡各塊／小卡／頁眉／票數帶相交
    #   L12 必須完整落在畫布內
    # ★ 與 L6／L9 同理，這幾條要排在 legendDisabled 的提前返回「之前」——
    #   區級圖正好只在 legendDisabled 的場次出現。
    m2 = rep.get("map2")
    if m2:
        r2 = m2.get("content") or m2.get("drawn")
        prof = mp.get("profile") if mp else None
        if r2 and prof:
            hits = [b for b in prof if _overlap(r2, b) is not None]
            gap = min(_gap("", r2, b) for b in prof)
            rows.append(("L10", not hits,
                         "區級圖 × 主地圖墨跡（分段，%d 帶）→ %s，最小淨空 %.0f px"
                         % (len(prof),
                            "不相交" if not hits else "壓到 %d 段墨跡" % len(hits),
                            gap)))
        elif r2 and mp and mp.get("content"):
            ov = _overlap(r2, mp["content"])
            rows.append(("L10", ov is None,
                         "區級圖 × 主地圖墨跡外接框 → %s"
                         % ("不相交（淨空 %.0f px）" % _gap("m2", r2, mp["content"])
                            if ov is None else "相交")))
        else:
            rows.append(("L10", True, "主地圖墨跡框不可得，略過"))

        if r2:
            bad = []
            for label, r in _obstacles(els):
                ov = _overlap(r2, r)
                if ov is not None:
                    bad.append("%s（重疊 %d×%d）"
                               % (label, round(ov[2] - ov[0]), round(ov[3] - ov[1])))
            if leg:
                for label, key in (("圖例圖片", "image"), ("圖例框", "box")):
                    r = leg.get(key)
                    if r and _overlap(r2, r) is not None:
                        bad.append(label)
            rows.append(("L11", not bad,
                         "區級圖 × 圖例／頁眉／票數帶／小卡／主卡各塊 → "
                         + ("全部不相交" if not bad else "壓到 " + "、".join(bad))))

            if cv:
                ok = (float(r2["x"]) >= -TOL and float(r2["y"]) >= -TOL
                      and float(r2["x"]) + float(r2["w"]) <= float(cv["w"]) + TOL
                      and float(r2["y"]) + float(r2["h"]) <= float(cv["h"]) + TOL)
                rows.append(("L12", ok,
                             "區級圖落在畫布 %sx%s 內 → %s（%s）"
                             % (cv.get("w"), cv.get("h"),
                                "是" if ok else "否", _fmt(r2))))
        else:
            rows.append(("L11", False, "報告有 map2 卻沒有任何矩形"))
    else:
        rows.append(("L10", True,
                     "本場沒有區級圖（圖例開著，或素材不存在），略過"))

    if rep.get("legendDisabled"):
        rows.append(("L0", True, "图例已按场次关闭（Layout.legend.disabled），L1–L5 略过"))
        return board, rows

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
        # 默认扫 dist/boards/<id>/layout.json（產物歸口後的路徑；本檔在 src/tools/）
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "dist", "boards")
        paths = []
        if os.path.isdir(root):
            for d in sorted(os.listdir(root)):
                lp = os.path.join(root, d, "layout.json")
                if os.path.isfile(lp):
                    paths.append(lp)
        if not paths:
            print("[错误] 找不到 %s 下的 layout.json；先跑 node tools/render_boards.mjs"
                  % root)
            return 2
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
