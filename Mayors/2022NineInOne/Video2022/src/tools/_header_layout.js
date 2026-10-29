  /* ------------------------------ 頁眉 ------------------------------
     ★ 2026-10-27（2022 九合一縣市長線）整塊重排，見 render/layers.js 的
       HeaderLayer。舊版是「市徽白卡／選舉名稱／年份圓盤＋投票日／投票率·有效票／
       時任首長」；這條線改成四塊：
         ① 標題群（縣市·屆次 → 2022年九合一選舉 → 投票日，全部靠左）
         ② 縣市徽章卡（白底圓角卡，接在標題右側）
         ③ 數據列（一項一行，標籤 + 數值兩欄）
         ④ 當選人（incumbent 區塊原樣保留）
       年份圓盤整組移除（年份已在大字標題裡）；要復原時把舊版 layers.js 的
       dateBlock 段落貼回來，並在下面補回 dateBlock 設定即可。 */
  Layout.header = {
    h: 236,
    /* ① 標題群：三行的字級／基線。subY / mainY / dateY 是
       「alphabetic 基線」的 y（不是行框上緣），改字級時一起看。 */
    title: {
      x: 72,
      sub: { size: 30, weight: 700, spacing: 10 },     /* 臺北市 · 第四屆市長選舉 */
      main: { size: 82, weight: 900, spacing: 6 },     /* 2022年九合一選舉 */
      date: { size: 27, weight: 600, spacing: 3 },     /* 2022年11月26日 投票 */
      subY: 72, mainY: 156, dateY: 208
    },
    /* ② 徽章卡：正方形白卡 + 投影，徽章等比例 contain 進內距。
       gap = 標題群右緣 → 卡片左緣；size 是卡片邊長（正方形）。
       滿版旗幟類（宜蘭）由 meta.sealCover 改走 cover（裁切填滿）。 */
    seal: {
      src: 'assets/city_seal.png',
      gap: 56, size: 172, pad: 15, radius: 26
    },
    /* ③ 數據列：一項一行，垂直置中於頁眉。
       labelW = 標籤欄寬（數值的左緣 = 標籤左緣 + labelW），
       數值欄左緣成一直線，五行看起來是一張表。 */
    stats: {
      gap: 56, rowH: 38,
      labelSize: 26, labelWeight: 700, labelSpacing: 4, labelW: 132,
      valueSize: 30, valueWeight: 900
    },
    /* ④ 右：當選人（與舊版 incumbent 完全相同的幾何） */
    incumbent: {
      card: { w: 112, h: 132, radius: 20, right: 2488, y: 34 },
      textRight: 2348, line1Y: 76, line2Y: 126, line3Y: 164,
      line1Size: 28, line2Size: 52, line3Size: 30
    }
  };

