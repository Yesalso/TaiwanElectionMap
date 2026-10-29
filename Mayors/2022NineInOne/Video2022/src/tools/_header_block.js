  /* =====================================================================
     HeaderLayer —— 頁眉：標題群 / 縣市徽章卡 / 數據列 / 當選人
     ---------------------------------------------------------------------
     ★ 2026-10-27（2022 九合一縣市長線）：整塊重排。
       舊版（Video/ 那條線）是
         [市徽白卡][選舉名稱][年份圓盤＋投票日][投票率·有效票][時任首長]
       這條線改成四塊，由左而右：
         ① 標題群：縣市·屆次（小字）／2022年九合一選舉（大字）／投票日（小字）
         ② 縣市徽章卡：白底圓角卡，放該縣市徽章（需求：2022 右側一張卡片）
         ③ 數據列：選舉人數／投票數／有效票／無效票／投票率，**一項一行**
         ④ 當選人：沿用舊版 incumbent 區塊，人物改吃 meta.header

       ★ 年份圓盤整組移除：年份已經在大字標題裡（2022年九合一選舉），
         圓盤再畫一次 2022 只是重複。投票日降成標題群第三行的小字。
       ★ 三行都靠左對齊同一個 x（Layout.header.title.x），
         徽章卡的 x 由「最寬那一行的右緣 + gap」推得 —— 換縣市、換屆次
         都不會讓卡片飄掉或壓到字。
     ===================================================================== */
  HeaderLayer.prototype.draw = function (ctx) {
    var H = L.header, meta = this.model.meta;
    var U_ = U;

    /* 頂部漸層帶（與舊版相同）：讓頁眉在街景背景上有一層暗底 */
    ctx.fillStyle = U_.gradient(ctx, 0, 0, 0, H.h, [
      [0, 'rgba(4,7,16,0.92)'],
      [0.72, 'rgba(4,7,16,0.62)'],
      [1, 'rgba(4,7,16,0)']
    ]);
    ctx.fillRect(0, 0, L.W, H.h);
    ctx.fillStyle = T.BG.line;
    ctx.fillRect(0, H.h - 1, L.W, 1);

    /* ---------------- ① 左：標題群（三行） ----------------
       小字（縣市 · 第 X 屆 Y 長選舉）→ 大字（2022年九合一選舉）→ 小字（投票日）。
       三行的字級與基線全部寫在 Layout.header.title，這裡只負責畫。 */
    var t = H.title;
    var subText = meta.subtitle || '';
    var mainText = meta.election || '';
    var dateText = String(meta.year) + '年' + (meta.date || '') + ' 投票';

    if (subText) {
      U_.text(ctx, subText, {
        x: t.x, y: t.subY, size: t.sub.size, weight: t.sub.weight,
        color: T.BG.textFaint, align: 'left', baseline: 'alphabetic',
        spacing: t.sub.spacing
      });
    }
    U_.text(ctx, mainText, {
      x: t.x, y: t.mainY, size: t.main.size, weight: t.main.weight,
      color: T.BG.text, align: 'left', baseline: 'alphabetic',
      spacing: t.main.spacing,
      shadow: { color: 'rgba(0,0,0,0.5)', blur: 18, y: 5 }
    });
    U_.text(ctx, dateText, {
      x: t.x, y: t.dateY, size: t.date.size, weight: t.date.weight,
      color: T.BG.textDim, align: 'left', baseline: 'alphabetic',
      spacing: t.date.spacing
    });

    /* 量三行實際寬度 → 取最寬者當「標題群右緣」，徽章卡接在它後面 */
    var widths = [0, 0, 0];
    ctx.save();
    ctx.font = U_.font(t.sub.size, t.sub.weight);
    widths[0] = subText ? U_.measureSpaced(ctx, subText, t.sub.spacing) : 0;
    ctx.font = U_.font(t.main.size, t.main.weight);
    widths[1] = U_.measureSpaced(ctx, mainText, t.main.spacing);
    ctx.font = U_.font(t.date.size, t.date.weight);
    widths[2] = U_.measureSpaced(ctx, dateText, t.date.spacing);
    ctx.restore();
    var titleRight = t.x + Math.max(widths[0], widths[1], widths[2]);

    /* ---------------- ② 縣市徽章卡 ----------------
       白底圓角卡 + 投影，徽章圖等比例 contain 進卡片內距裡。
       ★ 滿版旗幟類（宜蘭的縣旗整張都是畫面、沒有白底）由 meta.sealCover
         宣告改走 cover（裁切填滿卡片），否則 contain 後只剩一條細橫條。
       讀不到徽章時在卡片裡畫一個暗色圈勾記號，不開天窗。 */
    var sc = H.seal;
    var size = sc.size;
    var pad = sc.pad === undefined ? 14 : sc.pad;
    var rad = sc.radius === undefined ? 26 : sc.radius;
    var cardX = titleRight + (sc.gap || 0);
    var cardY = (H.h - size) / 2;
    var seal = this.assets.citySeal;

    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.45)';
    ctx.shadowBlur = 18;
    ctx.shadowOffsetY = 6;
    ctx.fillStyle = '#ffffff';
    U_.roundRectPath(ctx, cardX, cardY, size, size, rad);
    ctx.fill();
    ctx.restore();

    if (seal && seal.width) {
      ctx.save();
      ctx.imageSmoothingQuality = 'high';
      if (meta.sealCover) {
        /* 滿版：卡片當裁切框，圖以 cover 鋪滿（比例不符的部分裁掉） */
        U_.roundRectPath(ctx, cardX, cardY, size, size, rad);
        ctx.clip();
        var kc = Math.max(size / seal.width, size / seal.height);
        ctx.drawImage(seal, cardX + (size - seal.width * kc) / 2,
          cardY + (size - seal.height * kc) / 2,
          seal.width * kc, seal.height * kc);
      } else {
        /* 一般徽章：等比例 contain 進卡片內距，置中 */
        var box = size - pad * 2;
        var ks = Math.min(box / seal.width, box / seal.height);
        var iw = seal.width * ks, ih = seal.height * ks;
        ctx.drawImage(seal, cardX + (size - iw) / 2, cardY + (size - ih) / 2, iw, ih);
      }
      ctx.restore();
    } else {
      Marks.voteMark(ctx, cardX + size / 2, cardY + size / 2, size * 0.22,
        'rgba(0,0,0,0.34)', 6);
    }
    /* 記下落點，供自動化驗證量測（與舊版的 assets.sealRect 同一個欄位名） */
    this.assets.sealRect = { x: cardX, y: cardY, w: size, h: size };

    /* ---------------- ③ 數據列（一項一行） ----------------
       資料由 meta.statsRows 給：[{label:'選舉人數', value:'202萬6769 人'}, …]，
       引擎只排版，不決定要印哪幾項（gen_boards.py 產生，換項目不必改引擎）。
       標籤暗色、數值白色；標籤欄固定寬（labelW）讓數值左緣成一直線。 */
    var sr = H.stats;
    var rows = meta.statsRows || [];
    var rowH = sr.rowH;
    var rowsTop = (H.h - rows.length * rowH) / 2;
    var colX = cardX + size + (sr.gap || 0);
    var vw = 0;
    ctx.save();
    ctx.font = U_.font(sr.valueSize, sr.valueWeight);
    for (var i = 0; i < rows.length; i++) {
      var cy = rowsTop + rowH * (i + 0.5);
      U_.text(ctx, rows[i].label, {
        x: colX, y: cy, size: sr.labelSize, weight: sr.labelWeight,
        color: T.BG.textFaint, align: 'left', baseline: 'middle',
        spacing: sr.labelSpacing || 0
      });
      U_.text(ctx, rows[i].value, {
        x: colX + sr.labelW, y: cy, size: sr.valueSize, weight: sr.valueWeight,
        color: T.BG.text, align: 'left', baseline: 'middle'
      });
      var w = ctx.measureText(rows[i].value).width;
      if (w > vw) vw = w;
    }
    ctx.restore();
    this.assets.statsRect = {
      x: colX, y: rowsTop, w: sr.labelW + vw, h: rows.length * rowH
    };

    /* ---------------- ④ 右：當選人 ----------------
       沿用舊版的 incumbent 區塊（色塊框 + 三行字），人物與政黨改由
       meta.header 宣告（gen_boards.py 寫入：role/name/party/partyShort）。
       meta.header.role 宣告成 null 時整格不畫。 */
    var hdr = meta.header || null;
    var roleLabel = (hdr && hdr.role !== undefined) ? hdr.role
      : (meta.headerRole === undefined ? '當選人' : meta.headerRole);
    if (roleLabel) {
      var incTheme, incName, incParty;
      if (hdr && hdr.name) {
        var hdrPartyKey = NT.Candidate.partyKeyOf(hdr.partyShort);
        incTheme = hdr.color ? T.fromColor(hdr.color, hdrPartyKey)
                             : T.party(hdrPartyKey);
        incName = hdr.name;
        incParty = hdr.party || '';
      } else {
        incTheme = this.model.left.theme;
        incName = this.model.left.name;
        incParty = this.model.left.partyDisplay();
      }
      var inc = H.incumbent;
      var px = inc.card.right - inc.card.w;
      /* 頭像框：看板一律不畫候選人照片（照片由使用者後製），框裡只填
         政黨純色 + 一圈亮線，位置與尺寸維持舊版。 */
      ctx.save();
      ctx.shadowColor = 'rgba(0,0,0,0.5)';
      ctx.shadowBlur = 16;
      ctx.fillStyle = incTheme.main;
      U_.roundRectPath(ctx, px, inc.card.y, inc.card.w, inc.card.h, inc.card.radius);
      ctx.fill();
      ctx.restore();
      ctx.save();
      ctx.strokeStyle = U_.alpha(incTheme.light, 0.9);
      ctx.lineWidth = 2.5;
      U_.roundRectPath(ctx, px, inc.card.y, inc.card.w, inc.card.h, inc.card.radius);
      ctx.stroke();
      ctx.restore();

      U_.text(ctx, roleLabel, {
        x: inc.textRight, y: inc.line1Y, size: inc.line1Size, weight: 700,
        color: T.BG.textFaint, align: 'right', baseline: 'middle', spacing: 8
      });
      U_.text(ctx, incName, {
        x: inc.textRight, y: inc.line2Y, size: inc.line2Size, weight: 900,
        color: '#fff', align: 'right', baseline: 'middle'
      });
      U_.text(ctx, incParty, {
        x: inc.textRight, y: inc.line3Y, size: inc.line3Size, weight: 700,
        color: U_.alpha(incTheme.light, 0.95), align: 'right', baseline: 'middle'
      });
      this.assets.incumbentRect = {
        x: px, y: inc.card.y, w: inc.card.w, h: inc.card.h
      };
    }
  };

