# -*- coding: utf-8 -*-
"""entry.py —— 產出「全場共用」的看板入口頁 dist/boards/_entry/index.html。

為什麼要有這支
--------------
以前 build_board.py / 兩個總統生成器都往 `dist/boards/<id>/index.html`
複製一份模板 —— 32 場就是 32 份 sha256 完全相同的複製品。模板一改，
得把 32 場全部重建一次才會同步。

現在只有一份入口，用查詢參數指定場次：

    dist/boards/_entry/index.html?board=2022-taipei-mayor&headless=1

★ 入口刻意放在 `dist/boards/_entry/`（與 `dist/boards/<id>/` **同深度**），
  所以模板裡的 `../../../src/engine/...` 與 board.files.js 的
  `../../assets/...` 一條都不用改。若把入口上移到 `dist/boards/_entry.html`
  （少一層），這兩組相對路徑全部要重寫，是這個方案唯一的雷。

放在 boardlib 而不是 build_board.py：兩個總統生成器也要用，
但它們不該為了寫一個 HTML 而去 import geopandas。
"""

from __future__ import annotations

import os

from . import naming

BOARD_JS_TAG = '<script src="./board.js"></script>'
FILES_JS_TAG = '<script src="./board.files.js"></script>'

LOADER = """<script>
  /* 共用入口（dist/boards/_entry/index.html）—— 全場共用一份，不逐場複製。
     從 ?board=<場次 id> 動態掛上該場的資料層：
       ../<id>/board.js        window.BOARD
       ../<id>/board.files.js  window.BOARD_FILES（素材邏輯名 -> 實際檔）
     ★ 本檔與 dist/boards/<id>/ 同深度，所以模板裡的 ../../../src/engine
       與 board.files.js 的 ../../assets/ 都不必改。 */
  (function () {
    var id = (new URLSearchParams(location.search)).get('board') || '';
    if (!/^[A-Za-z0-9._-]+$/.test(id)) {
      document.write('<p style="padding:24px;font:16px sans-serif">'
        + '共用入口需要 ?board=&lt;場次 id&gt;（例：?board=2022-taipei-mayor）</p>');
      return;
    }
    document.write('<script src="../' + id + '/board.js"><\\/script>');
    document.write('<script src="../' + id + '/board.files.js"><\\/script>');
  })();
</script>"""


def entry_html() -> str:
    """由模板算出共用入口的 HTML（純函式，方便測試）。"""
    tpl = os.path.join(naming.VIDEO_ROOT, naming.TEMPLATE_DIR, "index.html")
    with open(tpl, encoding="utf-8") as f:
        html = f.read()
    if BOARD_JS_TAG not in html or FILES_JS_TAG not in html:
        raise SystemExit(
            "模板 %s 少了 %s 或 %s，無法產生共用入口"
            % (tpl, BOARD_JS_TAG, FILES_JS_TAG))
    # 先拿掉 board.files.js 那行，再把 board.js 那行換成載入器
    # （載入器會依序 document.write 這兩支，順序與原本一致）
    return html.replace(FILES_JS_TAG, "").replace(BOARD_JS_TAG, LOADER)


def write_entry_html() -> str:
    """寫出 dist/boards/_entry/index.html，回傳路徑（內容沒變就不重寫）。"""
    html = entry_html()
    dst_dir = os.path.join(naming.VIDEO_ROOT, "dist", "boards", "_entry")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "index.html")

    old = None
    if os.path.isfile(dst):
        with open(dst, encoding="utf-8") as f:
            old = f.read()
    if old != html:
        with open(dst, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
    return dst
