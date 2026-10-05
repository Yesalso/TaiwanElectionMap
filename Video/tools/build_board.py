# -*- coding: utf-8 -*-
"""build_board.py —— 建置單一選舉看板。

流程：
  1. manifest.resolve()      讀 meta.json、驗欄位
  2. xlsx_read.read_units()  逐里得票 -> 聚合到行政區
  3. 對帳                   Σ 各區票 vs meta.candidates[].votes
  4. geo.build()             由 SHP dissolve 出行政區 GeoJSON
                             （圖資依 meta.year 挑：<2019 用歷史圖資 106，
                               >=2019 用現行圖資 111；快取會記來源，換版自動重建）
  5. resolve_assets()        找素材：一律優先吃 NewSolution/png/processed/
                             的透明化成品（舊場次沒搬過去的才回退 boards/<id>/assets/）
  6. 寫 board.js / board.files.js / board.assets.js

★ 本檔不再「做」素材（不去背、不透明化、不往 assets/ 複製檔案）。
  素材的產生只有一個入口：NewSolution/tool/build_assets.py，
  成品只有一個落點：NewSolution/png/processed/。

用法：
  python tools/build_board.py boards/2018-taipei-mayor
  python build_board.py boards/2014-newtpei-mayor --skip-geo
  python build_board.py boards/2014-newtpei-mayor --diff Share/data/election-2014.js
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from boardlib import assets as assets_mod
from boardlib import canonical, geo, manifest, naming, xlsx_read


# ------------------------------------------------------------------ 聚合
def aggregate(units, board):
    """把 {單位全名: {key: 票}} 依 unitLevel 聚合成行政區。

    回傳 (districts, villages_by_district, unmatched)。
    """
    level = board.unit_level
    town_full = board.region.get("townFull", {}) or {}
    agg = {}
    for label, votes in units.items():
        if level == "village":
            district, _unit = xlsx_read.split_district(label)
        else:
            district, _unit = label, ""
        district = town_full.get(xlsx_read.short_name(district), district)
        slot = agg.setdefault(district, {"votes": {}, "villages": 0,
                                         "valid": 0})
        for key, v in votes.items():
            if key == "__valid__":
                slot["valid"] += v
            else:
                slot["votes"][key] = slot["votes"].get(key, 0) + v
        slot["villages"] += 1

    districts = []
    for district, slot in agg.items():
        valid = slot["valid"] or sum(slot["votes"].values())
        d = canonical.build_district(
            name=district,
            short=xlsx_read.short_name(district),
            villages=slot["villages"],
            votes=slot["votes"],
            valid=valid,
        )
        # 只補算未列入 xlsx 的候選人（逐里檔缺票者以 0 參與，但不影響勝負）
        for key in board.candidate_keys:
            d["votes"].setdefault(key, 0)
        districts.append(d)
    return canonical.sort_districts(districts)


def reconcile(districts, board):
    """對帳：Σ 各區票 vs meta.json 宣告的官方總票。

    回傳 (rows, warnings)；rows 為 [{key, name, declared, summed, diff}]。
    """
    rows = []
    warns = []
    for cand in board.candidates:
        key = cand["key"]
        summed = sum(d["votes"].get(key, 0) for d in districts)
        declared = cand.get("votes")
        diff = None if declared is None else summed - declared
        rows.append({
            "key": key,
            "name": cand["name"],
            "declared": declared,
            "summed": summed,
            "diff": diff,
        })
        if diff:
            warns.append("%s：各區合計 %s，meta.json 官方票 %s，差 %+d"
                         % (cand["name"], f"{summed:,}", f"{declared:,}", diff))
    return rows, warns


def fill_candidate_pct(candidates, meta):
    """由官方總票補算 pct / share。"""
    valid = meta.get("validVotes") or 0
    cast = meta.get("castVotes") or 0
    out = []
    for c in candidates:
        votes = c.get("votes") or 0
        d = dict(c)
        d["pct"] = canonical.pct_of(votes, valid)
        d["share"] = canonical.share_of(votes, cast)
        out.append(d)
    return out


# ------------------------------------------------------------------ 輸出
def write_board_js(board, payload, out_dir):
    js = ("/* 自動產生，請勿手改。\n"
          "   來源：%s\n"
          "   建置：Video/tools/build_board.py %s\n"
          "*/\n"
          "window.BOARD = " % (os.path.basename(board.source_file("data.xlsx")),
                                 board.id))
    js += json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    js += ";\n"
    path = os.path.join(out_dir, "board.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(js)
    return path


def write_board_files_js(board, resolved, out_dir):
    """寫「邏輯素材名 -> 實際檔案 URL」的對照表（window.BOARD_FILES）。

    引擎內部一律用邏輯名（assets/map.png、candidate/ko.png…），實際檔案在
    NewSolution/png/processed/ 底下、依類別與年份分層（見 naming.processed_relpath）。
    這張表把兩邊接起來，順便讓素材位置可以整批換掉而不用改 JS。

    路徑寫成「相對 index.html」的形式，所以靜態伺服器的根必須是 Video/
    （tools/render_boards.mjs 已照此設定）。
    """
    files = {}
    for fname, path in sorted(resolved.items()):
        rel = os.path.relpath(path, board.board_dir).replace(os.sep, "/")
        files[fname.replace(os.sep, "/")] = rel
    js = ("/* 自動產生，請勿手改。\n"
          "   邏輯素材名 -> 實際檔案（透明化成品在 NewSolution/png/processed/）\n"
          "   建置：Video/tools/build_board.py %s\n"
          "*/\n"
          "window.BOARD_FILES = " % board.id)
    js += json.dumps({"files": files}, ensure_ascii=False, indent=2)
    js += ";\n"
    path = os.path.join(out_dir, "board.files.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(js)
    return path


def write_board_assets_js(board, resolved, out_dir):
    """寫內嵌備援（file:// 直接開啟 index.html 時用）。

    對外同時提供兩個進入點：
      window.BOARD_ASSETS  以檔名為 key（map.png、candidate/zhu.png…）
      window.NT_ASSETS     以引擎欄位名為 key（voteMap、legend…），
                           供 _engine/js/slide.js 使用；欄位名見 naming.ASSETS
    """
    asset_map = {name.replace(os.sep, "/"): assets_mod.embed(path)
                 for name, path in resolved.items()}

    engine = {}
    for fname, spec in naming.by_filename().items():
        if fname in asset_map:
            engine[spec.engine_field] = asset_map[fname]
    for c in board.candidates:
        fname = naming.party_filename(c["partyShort"])
        if fname in asset_map:
            engine[naming.party_engine_field(c["partyShort"])] = asset_map[fname]

    js = ("/* 自動產生，請勿手改。file:// 直接開啟時的內嵌備援。\n"
          "   建置：Video/tools/build_board.py %s\n"
          "*/\n"
          "window.BOARD_ASSETS = " % board.id)
    js += json.dumps(asset_map, ensure_ascii=False, separators=(",", ":"))
    js += ";\nwindow.NT_ASSETS = "
    js += json.dumps(engine, ensure_ascii=False, separators=(",", ":"))
    js += ";\n"
    path = os.path.join(out_dir, "board.assets.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(js)
    return path


def resolve_assets(board):
    """挑出這場看板要用的素材，回傳 ({邏輯檔名: 絕對路徑}, [缺少的檔名])。

    ★ 透明化成品不再進 boards/<id>/assets/ —— 全部集中在
      NewSolution/png/processed/（產生者是 NewSolution/tool/build_assets.py）。
      本函式只「找圖」，不「做圖」，也不往任何資料夾複製檔案。

    優先序：

      NewSolution/png/processed/…   透明化成品（正常路徑）
      boards/<id>/assets/…          舊場次的既有成品（2014 新北還沒搬過去時的後援）

    兩邊都沒有就列進 missing，由呼叫端決定要警告還是報錯。
    """
    filenames = naming.required_filenames(board.candidates)

    resolved, missing = {}, []
    for fname in filenames:
        dst = naming.processed_path(fname, board.year,
                                    map_variant=board.map_variant)
        if dst and os.path.isfile(dst):
            resolved[fname] = dst
            continue
        legacy = os.path.join(board.assets_dir, fname)
        if os.path.isfile(legacy):
            resolved[fname] = legacy
            continue
        missing.append(fname)
    return resolved, missing


# ------------------------------------------------------------------ diff
def diff_against(path, payload):
    """與既有 election-XXXX.js 逐欄比對，印出差異。"""
    src = open(path, encoding="utf-8").read()
    i = src.index("=")
    old = json.loads(src[i + 1:].rstrip().rstrip(";"))

    problems = []

    om, nm = old.get("meta", {}), payload.get("meta", {})
    for k in sorted(set(om) | set(nm)):
        if om.get(k) != nm.get(k):
            problems.append("meta.%s: 舊 %r -> 新 %r" % (k, om.get(k), nm.get(k)))

    oc, nc = old.get("candidates", {}), {c["key"]: c for c in payload["candidates"]}
    for key in sorted(set(oc) | set(nc)):
        o = oc.get(key) or {}
        n = nc.get(key) or {}
        for f in ("name", "party", "party_short", "party_en", "number",
                  "votes", "pct", "share"):
            ov = o.get(f)
            nv = n.get(f) if f in n else n.get(
                {"party_short": "partyShort", "party_en": "partyEn"}.get(f, f))
            if ov != nv:
                problems.append("candidates.%s.%s: 舊 %r -> 新 %r"
                                % (key, f, ov, nv))

    od = old.get("districts", [])
    nd = payload.get("districts", [])
    if len(od) != len(nd):
        problems.append("districts 數量: 舊 %d -> 新 %d" % (len(od), len(nd)))
    for o, n in zip(od, nd):
        if o.get("town") != n.get("name"):
            problems.append("districts 順序/名稱: 舊 %r -> 新 %r"
                            % (o.get("town"), n.get("name")))
            continue
        for f_old, f_new in (("villages", "villages"), ("valid", "valid"),
                             ("winner", "winnerKey"), ("margin", "margin")):
            if o.get(f_old) != n.get(f_new):
                problems.append("%s.%s: 舊 %r -> 新 %r"
                                % (n["name"], f_old, o.get(f_old), n.get(f_new)))
        for key in payload["candidates"][0]["key"] and [c["key"] for c in payload["candidates"]]:
            if o.get(key) != n["votes"].get(key):
                problems.append("%s.votes.%s: 舊 %r -> 新 %r"
                                % (n["name"], key, o.get(key), n["votes"].get(key)))

    og = old.get("geojson", {})
    ng = payload.get("geojson", {})
    ofn = [f["properties"].get("town") for f in og.get("features", [])]
    nfn = [f["properties"].get("name") for f in ng.get("features", [])]
    if sorted(ofn) != sorted(nfn):
        problems.append("geojson 行政區: 舊 %d 個 / 新 %d 個，集合不同"
                        % (len(ofn), len(nfn)))

    print("\n--- 與 %s 比對 ---" % path)
    if not problems:
        print("完全一致，0 差異。")
    else:
        print("差異 %d 項：" % len(problems))
        for p in problems[:80]:
            print("  " + p)
        if len(problems) > 80:
            print("  ... 另 %d 項" % (len(problems) - 80))
    return problems


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="建置單一選舉看板")
    ap.add_argument("board_dir")
    ap.add_argument("--skip-geo", action="store_true")
    ap.add_argument("--diff", metavar="OLD_JS",
                    help="與既有的 election-XXXX.js 比對")
    ap.add_argument("--geo-cache", metavar="FILE",
                    help="沿用既有的 geojson（不重跑 SHP）；"
                         "預設讀 <board>/.cache/geojson.json，"
                         "且來源與本次不符會自動重建，指定本參數則一律沿用")
    ap.add_argument("--refresh-geo", action="store_true",
                    help="忽略 .cache/geojson.json，強制重跑 SHP")
    ap.add_argument("--shp", metavar="FILE",
                    help="強制用這份村里界 SHP，覆寫「依選舉年挑圖資」的結果"
                         "（<2019 預設用歷史圖資 106 VILLAGE_MOI_1070205）")
    args = ap.parse_args()

    board = manifest.resolve(args.board_dir)
    print("board:", manifest.describe(board))

    missing = manifest.check_sources(board)
    if missing:
        raise SystemExit("source/ 缺少檔案：%s" % "、".join(missing))
    print("source/ 檔案齊備。")

    xlsx = board.source_file("data.xlsx")
    units, layout, sheet = xlsx_read.read_units(
        xlsx, board.candidates, board.region.get("sheet"))
    print("xlsx 版面 %s（sheet「%s」），讀到 %d 個單位"
          % (layout, sheet, len(units)))

    districts = aggregate(units, board)
    rows, warns = reconcile(districts, board)
    print("行政區 %d 個，村里合計 %d 筆"
          % (len(districts), sum(d["villages"] for d in districts)))
    print("對帳：")
    for r in rows:
        d = "  n/a" if r["diff"] is None else "%+d" % r["diff"]
        print("  %-8s 官方 %12s  各區合計 %12s  差 %s"
              % (r["name"], "-" if r["declared"] is None else "{:,}".format(r["declared"]),
                 "{:,}".format(r["summed"]), d))
    for w in warns:
        print("  [提示] " + w)

    cache_path = args.geo_cache or os.path.join(board.board_dir, ".cache", "geojson.json")
    if args.skip_geo:
        geojson = {"type": "FeatureCollection", "features": []}
        print("geojson: 略過")
    else:
        # 依「選舉年」挑村里界圖資：<2019 走歷史圖資 106，否則走現行圖資 111。
        # meta.region 可用 geoSource / shp 覆寫（見 boardlib.geo.SOURCES）。
        shp_override = args.shp or board.geo_shp
        simplify = board.region.get("simplify", geo.DEFAULT_SIMPLIFY)
        want = geo.expected_provenance(
            board.county, year=board.year, source_id=board.geo_source,
            shp=shp_override, simplify=simplify)
        print("geojson 圖資：%s（選舉年 %d）%s"
              % (want["label"], board.year,
                 "  ← --shp 覆寫" if args.shp else
                 "  ← region.shp 覆寫" if board.geo_shp else
                 "  ← region.geoSource 覆寫" if board.geo_source else ""))

        cached = None
        cached_prov = None
        if os.path.isfile(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                cached = json.load(f)
            cached_prov = geo.provenance_of(cached)

        if args.refresh_geo:
            reuse, why = False, "--refresh-geo 指定重跑"
        elif args.geo_cache:
            # 明確指定 --geo-cache 時以使用者為準，不因來源不同而自動重建
            reuse = cached is not None
            why = "--geo-cache 指定沿用" if reuse else ""
        elif cached is None:
            reuse, why = False, "尚無快取"
        elif geo.provenance_matches(cached_prov, want):
            reuse, why = True, "圖資 %s" % cached_prov.get("shp")
        elif not cached_prov:
            reuse, why = False, "快取沒有來源資訊（舊格式，無法確認是哪一版圖資）"
        else:
            reuse, why = False, ("快取來自 %s，本次應為 %s"
                                 % (cached_prov.get("shp"), want.get("shp")))

        if reuse:
            geojson = cached
            print("geojson: 沿用 %s（%d 個行政區，%s）"
                  % (os.path.relpath(cache_path), len(geojson["features"]), why))
        else:
            if cached is not None:
                print("geojson: 快取失效 → 重建（%s）" % why)
            geojson = geo.build(board.county,
                                year=board.year,
                                source_id=board.geo_source,
                                shp=shp_override,
                                simplify=simplify)
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(geojson, f, ensure_ascii=False)
            src = geo.provenance_of(geojson) or {}
            print("geojson: 由 %s dissolve %d 個行政區，快取至 %s"
                  % (src.get("shp", "SHP"), len(geojson["features"]),
                     os.path.relpath(cache_path)))



    meta = dict(board.meta)
    totals = xlsx_read.read_official_totals(xlsx)
    for k_src, k_dst in (("valid", "validVotes"), ("invalid", "invalidVotes"),
                         ("vote_cast", "castVotes"), ("electorate", "electorate")):
        if k_src in totals:
            meta.setdefault(k_dst, totals[k_src])
    if meta.get("castVotes") and meta.get("electorate"):
        meta["turnout"] = round(meta["castVotes"] / meta["electorate"] * 100, 2)

    candidates = fill_candidate_pct(board.candidates, meta)

    # ---- 素材：只找圖，不做圖（透明化是 NewSolution/tool/build_assets.py 的事）----
    resolved, missing_assets = resolve_assets(board)
    print("素材：找到 %d 張、缺 %d 張" % (len(resolved), len(missing_assets)))
    if missing_assets:
        print("  [警告] 缺：%s" % "、".join(missing_assets))
        print("         跑 python NewSolution/tool/build_assets.py 產生成品"
              "（原圖放 NewSolution/png/<類別>/<年份>/）")

    # 看板不畫候選人照片（卡面只填政黨純色），所以 board.js 不含 photo 欄位。
    # meta.json 就算還留著舊的 photo / cardSize，manifest 也不會帶進來
    # （見 boardlib/manifest.py 的 _normalise_candidates）。

    payload = {
        "meta": meta,
        "candidates": candidates,
        "districts": districts,
        "geojson": geojson,
    }

    tol = board.assets_cfg.get("voteMapAspectTolerance", 0.2)
    map_key = naming.by_role()["得票率地圖"].filename
    if map_key in resolved:
        warn = assets_mod.aspect_warning(resolved[map_key], tol)
        if warn:
            print("  [警告] " + warn)
    else:
        print("  [警告] 沒有地圖，看板會退回預設畫法")

    p1 = write_board_js(board, payload, board.out_dir)
    print("輸出:", os.path.relpath(p1), "(%.0f KB)" % (os.path.getsize(p1) / 1024))

    p2 = write_board_files_js(board, resolved, board.out_dir)
    print("輸出:", os.path.relpath(p2), "(%.0f KB)" % (os.path.getsize(p2) / 1024))

    p3 = write_board_assets_js(board, resolved, board.out_dir)
    print("輸出:", os.path.relpath(p3), "(%.0f KB)" % (os.path.getsize(p3) / 1024))

    if args.diff:
        diff_against(args.diff, payload)


if __name__ == "__main__":
    main()