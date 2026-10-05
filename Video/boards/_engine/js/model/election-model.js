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
