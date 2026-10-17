import io, json, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

board = r"D:\Windows\TaiwanElection\Video\boards\2014-newtpei-mayor"
share = r"D:\Windows\TaiwanElection\Video\Share"


def load_js(path, var):
    s = open(path, encoding="utf-8").read()
    i = s.index(var)
    i = s.index("=", i) + 1
    return json.loads(s[i:].rstrip().rstrip(";"))


new = load_js(board + r"\board.js", "window.BOARD")
old = load_js(share + r"\data\election-2014.js", "window.ELECTION_2014")

fails = []


def eq(label, a, b):
    if a != b:
        fails.append("%s: %r != %r" % (label, a, b))


# meta（id 是新欄位，不比）
for k in set(old["meta"]) | set(new["meta"]):
    if k == "id":
        continue
    eq("meta." + k, old["meta"].get(k), new["meta"].get(k))

# candidates
for c in new["candidates"]:
    o = old["candidates"][c["key"]]
    for f, nf in (("name", "name"), ("party", "party"), ("party_short", "partyShort"),
                  ("party_en", "partyEn"), ("number", "number"), ("votes", "votes"),
                  ("pct", "pct"), ("share", "share"), ("elected", "elected")):
        # 舊檔未宣告 elected 者視為 False
        eq("candidates.%s.%s" % (c["key"], f), bool(o.get(f)) if f == "elected"
           else o.get(f), c.get(nf))

# districts：順序、票數、百分比、勝負
eq("districts.len", len(old["districts"]), len(new["districts"]))
for o, n in zip(old["districts"], new["districts"]):
    t = n["name"]
    eq(t + ".name", o["town"], t)
    eq(t + ".short", o["short"], n["short"])
    eq(t + ".villages", o["villages"], n["villages"])
    eq(t + ".valid", o["valid"], n["valid"])
    eq(t + ".winner", o["winner"], n["winnerKey"])
    eq(t + ".margin", o["margin"], n["margin"])
    for k in ("zhu", "you"):
        eq("%s.votes.%s" % (t, k), o[k], n["votes"][k])
        eq("%s.pct.%s" % (t, k), o[k + "Pct"], n["pct"][k])

# geojson
og = sorted(f["properties"]["town"] for f in old["geojson"]["features"])
ng = sorted(f["properties"]["name"] for f in new["geojson"]["features"])
eq("geojson.towns", og, ng)
old_by = {f["properties"]["town"]: f["geometry"] for f in old["geojson"]["features"]}
new_by = {f["properties"]["name"]: f["geometry"] for f in new["geojson"]["features"]}
for t in og:
    eq("geojson.geometry." + t, old_by[t], new_by[t])

print("比對項目：meta %d 項、候選人 %d 位、行政區 %d 個（含票數/百分比/幾何）"
      % (len(new["meta"]), len(new["candidates"]), len(new["districts"])))
if fails:
    print("失敗 %d 項：" % len(fails))
    for f in fails[:40]:
        print("  " + f)
else:
    print("全部一致，0 差異。")