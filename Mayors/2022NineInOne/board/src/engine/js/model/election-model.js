/* ==========================================================================
   election-model.js — 選舉資料模型（泛化版）
   --------------------------------------------------------------------------
   把 build_board.py 產生的 canonical 資料（window.BOARD）包成有語意的物件：
   候選人、行政區、總計、勝負差距、地圖色階等。
   繪製層只跟這個模型要資料，不直接碰原始 JSON。

   ★ 泛化重點（原版寫死 2014 新北的 zhu / you / lee）：
     - 候選人不再寫死 key，改吃 canonical 的 candidates 陣列（任意人數、任意 key）
     - 分槽：candidates[].slot 宣告優先，否則依得票取前 N 名進主卡（左 = 票高）
     - 行政區 winnerKey / partyKey 由候選人資料推出，不再 === 'zhu' ? 'kmt' : 'dpp'
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};
  var U = NT.Utils;

  /**
   * Candidate —— 單一候選人
   * @param {object} raw  原始資料（canonical，camelCase；亦容忍 snake_case）
   * @param {string} slot 'left' | 'right' | 'minor' | null
   */
  function Candidate(raw, slot) {
    this.key = raw.key;
    this.slot = slot || null;
    this.name = raw.name;
    /* 資料檔欄位為 snake_case，這裡同時接受 camelCase，避免欄位改名時靜默失效 */
    this.nameEn = raw.nameEn || raw.name_en || '';
    this.party = raw.party;
    this.partyShort = raw.partyShort || raw.party_short || '';
    this.partyEn = raw.partyEn || raw.party_en || '';
    this.number = raw.number;
    this.votes = raw.votes || 0;
    this.pct = raw.pct || 0;          // 佔有效票 %
    this.share = raw.share || 0;      // 佔實際投票數 %
    this.elected = !!raw.elected;
    this.partyKey = Candidate.partyKeyOf(this.partyShort);
    /* 色票：meta.json 若為這位候選人宣告 color（十六進位），就以它為準。
       小黨 / 無黨籍沒有預設政黨色時，可用這個欄位指定一個主色，
       其餘亮暗階與地圖色階由 Theme.fromColor 推導。
       沒有宣告的人完全不受影響（走原本的政黨色表）。 */
    this.color = raw.color || raw.colorHex || null;
    /* 副手（總統／副總統選舉用）：vice = 副手姓名、viceParty = 副手政黨全稱。
       沒宣告（市長選舉）時為 null，繪製層就不畫副手行，既有輸出不變。 */
    this.vice = raw.vice || raw.viceName || null;
    this.viceParty = raw.viceParty || null;
    /* 當選席次（2026-10-29：全國「政黨版圖」看板用）——
       這一場的 candidates 是「政黨」而不是人，`seats` 就是該黨拿下的縣市長席次。
       有宣告時，主要候選人色卡與第 3 名起的小卡都會在色塊裡畫「N 席」
       （見 layers.js 的 seatBadge）；沒宣告（22 場縣市長看板）完全不畫，
       既有輸出逐位元組不變。 */
    this.seats = (raw.seats === undefined || raw.seats === null) ? null : raw.seats;
    /* 黨主席／負責人（2026-10-29：全國看板的 candidates 是政黨，主卡的大字
       姓名要印黨主席而不是黨名 —— 黨名已經在政黨標籤（chip）上）。
       沒宣告時主卡照舊印 name，22 場縣市長看板不受影響。 */
    this.leader = raw.leader || null;
    /* 小卡副行替代字（2026-10-29 同上）—— 政黨當候選人時 partyDisplay() 會與
       姓名重複（都是黨名），改由資料層指定一行次要資訊，例如「候選 23 人」。
       沒宣告時走原本的 partyDisplay()，市長／總統看板不受影響。 */
    /* ★ 2026-10-29：sub 允許是**空字串**（＝副行留白）。
       全國看板裡「無黨籍」「其他政黨」沒有黨主席 → sub = ''，
       卡片保留四行的高度節奏但不印字；用 `||` 會把空字串吃成 null，
       於是又退回 partyDisplay()（＝黨名），變成一行重複的黨名。 */
    this.sub = (raw.sub === undefined || raw.sub === null) ? null : raw.sub;
    /* 推薦政黨（2026-10-19 個案：無黨籍候選人由某政黨背書，如 1996 林洋港＝
       新黨推薦）。recommendedBy 存推薦政黨的 partyShort，引擎據此在主卡
       政黨標籤後追加「[推薦徽章] 推薦」一段。沒有宣告就維持原樣。 */
    this.recommendedBy = raw.recommendedBy || raw.recommend || '';
    this.recommendedByKey = this.recommendedBy
        ? Candidate.partyKeyOf(this.recommendedBy) : '';
    this.theme = this.color ? NT.Theme.fromColor(this.color, this.partyKey)
                            : NT.Theme.party(this.partyKey);
  }

  Candidate.partyKeyOf = function (short) {
    var s = (short || '').toUpperCase();
    if (s === 'KMT') return 'kmt';
    if (s === 'DPP') return 'dpp';
    if (s === 'TPP') return 'tpp';
    if (s === 'NSC') return 'nsc';
    if (s === 'PFP') return 'pfp';
    /* 時代力量（2022 基隆陳薇仲）：**沒有黨徽素材**，所以不要讓它落到 'ind'
       —— 否則主卡徽章會去抓「無黨籍」那枚圓標，等於畫錯黨。
       'npp' 不在 slide.js 的 PARTIES_WITH_MARK 裡 → 不會嘗試載圖；
       Theme.party('npp') 找不到時退回 ind 灰，但這位候選人有 color（#FFBE00），
       實際走 Theme.fromColor，不會真的變成灰。 */
    if (s === 'NPP') return 'npp';
    /* 「其他政黨」（2026-10-29 全國看板的合計列）：同樣沒有黨徽素材，
       也不能落到 'ind'（否則會誤掛無黨籍圓標）。'oth' 不在
       slide.js 的 PARTIES_WITH_MARK 裡 → 主卡位置退回抽象色塊；
       顏色由資料層的 color 宣告供給（Theme.fromColor）。 */
    if (s === 'OTH') return 'oth';
    return 'ind';
  };

  /** "95萬9302"（>1 萬票用「萬」制，不寫千分位逗號） */
  Candidate.prototype.votesText = function () {
    return U.voteWan(this.votes);
  };

  /** "95萬9302票" */
  Candidate.prototype.votesLabel = function () {
    return U.voteWan(this.votes) + '票';
  };

  /** "50.06" */
  Candidate.prototype.pctText = function () {
    return this.pct.toFixed(2);
  };

  /* ---------------- 低得票率候選人：圖片框用占位圖 ----------------
     ★ 2026-10-28（需求）：得票**排名 ≥ 3** 且**得票率 < 3%** 的候選人，
       圖片框一律改畫 assets/low_pct.png（灰階人形剪影占位圖）。
       門檻只寫在這裡，繪製層（layers.js 的 minorBlock）與載入層
       （slide.js）都只問 usesLowPctPhoto()，不各自比數字。
     rank 由 ElectionModel 依總得票數排出（1 起算，跨全部候選人）。 */
  var LOW_PCT_RANK = 3;      /* 第 3 名（含）以後 */
  var LOW_PCT_LIMIT = 3;     /* 得票率 < 3% */

  Candidate.prototype.usesLowPctPhoto = function () {
    return (this.rank || 0) >= LOW_PCT_RANK && (this.pct || 0) < LOW_PCT_LIMIT;
  };

  /** 政黨英文縮寫
   *
   * ★ 已不再畫在看板上（需求：標籤只留中文政黨名，KMT / DPP / INDEPENDENT
   *   這些英文一律不顯示）。函式保留是因為它同時是「這個 partyShort 是不是
   *   兩大黨」的判準，其他地方（如除錯輸出）還可能要用；
   *   繪製層請改用 partyDisplay()。
   */
  Candidate.prototype.partyAbbr = function () {
    var s = (this.partyShort || '').toUpperCase();
    if (s === 'KMT') return 'KMT';
    if (s === 'DPP') return 'DPP';
    if (s === 'TPP') return 'TPP';
    if (s === 'NSC') return 'NSC';
    if (s === 'PFP') return 'PFP';
    return 'INDEPENDENT';
  };

  /* 中選會官方全稱 -> 看板顯示用的短名。
     中選會把無黨籍一律寫成「無黨籍及未經政黨推薦」（11 個字），
     候選人標籤只有 452px 寬，塞不下；而且看板上寫「無黨籍」語意完全等價。
     2014 那種本來就寫「無黨籍」的資料不會被改到。 */
  var PARTY_DISPLAY = {
    '無黨籍及未經政黨推薦': '無黨籍',
    '無黨籍及未經政黨推薦者': '無黨籍'
  };

  /** 看板上實際印出來的政黨名 */
  Candidate.prototype.partyDisplay = function () {
    var p = this.party || '';
    if (PARTY_DISPLAY[p]) return PARTY_DISPLAY[p];
    /* 官方全稱偶有增補（例如「無黨籍及未經政黨推薦之候選人」），
       用規則兜住：開頭是「無黨籍」且提到「未經政黨推薦」就縮成「無黨籍」。 */
    if (/^無黨籍/.test(p) && p.indexOf('未經政黨推薦') >= 0) return '無黨籍';
    return p;
  };

  /** 把 canonical 的 candidates（陣列）或舊 ELECTION_2014 的物件，統一成陣列 */
  function normalizeCandidates(rawCandidates) {
    var list = [];
    if (Array.isArray(rawCandidates)) {
      rawCandidates.forEach(function (c) {
        list.push(Object.assign({}, c));
      });
    } else if (rawCandidates && typeof rawCandidates === 'object') {
      Object.keys(rawCandidates).forEach(function (k) {
        var cc = Object.assign({}, rawCandidates[k]);
        cc.key = k;
        list.push(cc);
      });
    }
    return list;
  }

  /**
   * ElectionModel —— 一整場選舉
   */
  function ElectionModel(raw) {
    if (!raw) throw new Error('缺少選舉資料（window.BOARD 未載入）');
    this.raw = raw;
    this.meta = raw.meta;

    var list = normalizeCandidates(raw.candidates).map(function (c) {
      return new Candidate(c, c.slot);
    });
    if (!list.length) throw new Error('candidates 為空，無法建立看板');

    /* 分槽：宣告 slot 優先，否則依得票取前 N 名進主卡 */
    var nMain = (raw.slots && raw.slots.main) || 2;
    var byVotes = function (a, b) { return (b.votes || 0) - (a.votes || 0); };
    var sorted = list.slice().sort(byVotes);
    /* 得票排名（1 起算）：低得票率候選人的「第 3 名以後」判準靠這個，
       與主卡／小卡帶怎麼分槽無關（見 Candidate#usesLowPctPhoto）。 */
    sorted.forEach(function (c, i) { c.rank = i + 1; });
    var declaredMain = list.filter(function (c) {
      return c.slot === 'left' || c.slot === 'right';
    });
    var main = (declaredMain.length ? declaredMain : sorted).slice(0, nMain);
    main.sort(byVotes);                       // 得票高者固定放左（沿用版面慣例）

    var minors = list.filter(function (c) { return main.indexOf(c) < 0; });
    minors.sort(byVotes);

    this.main = main;
    this.minors = minors;
    this.left = main[0] || minors[0];
    this.right = main[1] || this.left;
    this.minor = minors[0] || null;           // 舊 API：MinorCandidateLayer 目前只畫一位
    this.hiddenMinorCount = Math.max(0, minors.length - (this.minor ? 1 : 0));
    this.candidates = main.concat(minors);

    /* 勝負差距（以前二名） */
    this.marginVotes = Math.abs((this.left.votes || 0) - (this.right.votes || 0));
    this.marginPct = Math.abs((this.left.pct || 0) - (this.right.pct || 0));
    this.winner = this.left.votes >= this.right.votes ? this.left : this.right;
    this.loser = this.winner === this.left ? this.right : this.left;

    var candByKey = {};
    this.candidates.forEach(function (c) { candByKey[c.key] = c; });

    /* 行政區：winnerKey / partyKey 由候選人推出；votes / pct 直接吃 canonical 的物件 */
    this.districts = (raw.districts || []).map(function (d) {
      var winnerKey = d.winnerKey || d.winner;
      var winner = candByKey[winnerKey];
      var partyKey = winner ? winner.partyKey : 'ind';
      return {
        name: d.name || d.town,
        short: d.short,
        villages: d.villages,
        votes: d.votes || {},
        pct: d.pct || {},
        valid: d.valid,
        winnerKey: winnerKey,
        partyKey: partyKey,
        margin: d.margin,
        color: NT.Theme.mapShade(partyKey, d.margin)
      };
    });

    /* 各陣營拿下的行政區數（依實際出現的政黨 key 建立，不寫死 kmt / dpp） */
    var self = this;
    this.districtTally = {};
    this.candidates.forEach(function (c) {
      if (self.districtTally[c.partyKey] === undefined) {
        self.districtTally[c.partyKey] = self.districts.filter(function (d) {
          return d.partyKey === c.partyKey;
        }).length;
      }
    });

    /* 以行政區名索引，方便後續（例如地圖 tooltip） */
    this.districtByName = {};
    for (var i = 0; i < this.districts.length; i++) {
      this.districtByName[this.districts[i].name] = this.districts[i];
    }

    this.geojson = raw.geojson;
  }

  /** 依行政區名取得資料（地圖 GeoJSON 的 TOWNNAME 已是「板橋區」格式） */
  ElectionModel.prototype.districtOf = function (townName) {
    if (this.districtByName[townName]) return this.districtByName[townName];
    var self = this;
    var key = Object.keys(this.districtByName).filter(function (k) {
      return k.indexOf(townName) === 0 || townName.indexOf(k) === 0;
    })[0];
    return key ? self.districtByName[key] : null;
  };

  /** 底部票數帶的分段（依有效票佔比，與大字得票率同一個口徑） */
  ElectionModel.prototype.ribbonSegments = function () {
    return this.candidates
      .slice()
      .sort(function (a, b) { return b.votes - a.votes; })
      .map(function (c) {
        return {
          key: c.key,
          color: c.theme.main,
          ratio: c.pct / 100,
          label: c.name
        };
      });
  };

  /** 主要候選人（左、右） */
  ElectionModel.prototype.mains = function () {
    return this.main;
  };

  /** 行政區數的「A : B」字串，取主要候選人所屬陣營 */
  ElectionModel.prototype.tallyText = function () {
    var parts = [];
    for (var i = 0; i < this.main.length; i++) {
      parts.push(this.districtTally[this.main[i].partyKey] || 0);
    }
    return parts.join(' : ');
  };

  /** 一句話總結，用於狀態列 */
  ElectionModel.prototype.summary = function () {
    return this.meta.election + '：' + this.winner.name + '以 ' +
      U.voteWan(this.marginVotes) + ' 票之差當選（' +
      this.tallyText() + ' 個行政區）';
  };

  NT.Candidate = Candidate;
  NT.ElectionModel = ElectionModel;

})(window);
