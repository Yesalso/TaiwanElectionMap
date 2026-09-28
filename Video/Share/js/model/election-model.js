/* ==========================================================================
   election-model.js — 選舉資料模型
   --------------------------------------------------------------------------
   把 tools/build_data.py 產生的原始資料包成有語意的物件：
   候選人、行政區、總計、勝負差距、地圖色階等。
   繪製層只跟這個模型要資料，不直接碰原始 JSON。
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};
  var U = NT.Utils;

  /**
   * Candidate —— 單一候選人
   * @param {object} raw  原始資料
   * @param {string} slot 'left' | 'right' | 'minor'
   */
  function Candidate(raw, slot) {
    this.key = raw.key;
    this.slot = slot;
    this.name = raw.name;
    /* 資料檔欄位為 snake_case，這裡同時接受 camelCase，避免欄位改名時靜默失效 */
    this.nameEn = raw.nameEn || raw.name_en || '';
    this.party = raw.party;
    this.partyShort = raw.partyShort || raw.party_short || '';
    this.partyEn = raw.partyEn || raw.party_en || '';
    this.number = raw.number;
    this.votes = raw.votes;
    this.pct = raw.pct;          // 佔有效票 %
    this.share = raw.share;      // 佔實際投票數 %
    this.elected = !!raw.elected;
    this.photo = raw.photo || null;
    this.partyKey = Candidate.partyKeyOf(this.partyShort);
    this.theme = NT.Theme.party(this.partyKey);
  }

  Candidate.partyKeyOf = function (short) {
    if (short === 'KMT') return 'kmt';
    if (short === 'DPP') return 'dpp';
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

  /** 政黨英文縮寫（卡片下方標籤用，避免長名撐爆色塊） */
  Candidate.prototype.partyAbbr = function () {
    if (this.partyShort === 'KMT') return 'KMT';
    if (this.partyShort === 'DPP') return 'DPP';
    return 'INDEPENDENT';
  };

  /**
   * ElectionModel —— 一整場選舉
   */
  function ElectionModel(raw) {
    if (!raw) throw new Error('缺少選舉資料（data/election-2014.js 未載入）');
    this.raw = raw;
    this.meta = raw.meta;

    var photos = raw.photos || {};
    function build(key, slot) {
      var c = Object.assign({}, raw.candidates[key]);
      c.key = key;
      c.photo = photos[key] || null;
      return new Candidate(c, slot);
    }

    /* 依得票高低決定左右：得票高者放左（與看板慣例一致） */
    var zhu = build('zhu', 'left');
    var you = build('you', 'right');
    this.left = zhu;
    this.right = you;
    this.minor = build('lee', 'minor');
    this.candidates = [zhu, you, this.minor];

    /* 勝負差距 */
    this.marginVotes = Math.abs(zhu.votes - you.votes);
    this.marginPct = Math.abs(zhu.pct - you.pct);
    this.winner = zhu.votes >= you.votes ? zhu : you;
    this.loser = this.winner === zhu ? you : zhu;

    /* 行政區：附上色階 */
    this.districts = (raw.districts || []).map(function (d) {
      var winnerKey = d.winner;                 // 'zhu' | 'you'
      var partyKey = winnerKey === 'zhu' ? 'kmt' : 'dpp';
      return {
        name: d.town,
        short: d.short,
        villages: d.villages,
        votes: { zhu: d.zhu, you: d.you },
        pct: { zhu: d.zhuPct, you: d.youPct },
        valid: d.valid,
        winnerKey: winnerKey,
        partyKey: partyKey,
        margin: d.margin,
        color: NT.Theme.mapShade(partyKey, d.margin)
      };
    });

    /* 各陣營拿下的行政區數 */
    this.districtTally = {
      kmt: this.districts.filter(function (d) { return d.partyKey === 'kmt'; }).length,
      dpp: this.districts.filter(function (d) { return d.partyKey === 'dpp'; }).length
    };

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
    return [this.left, this.right];
  };

  /** 一句話總結，用於狀態列 */
  ElectionModel.prototype.summary = function () {
    return this.meta.election + '：' + this.winner.name + '以 ' +
      U.voteWan(this.marginVotes) + ' 票之差當選（' +
      this.districtTally.kmt + ' : ' + this.districtTally.dpp + ' 個行政區）';
  };

  NT.Candidate = Candidate;
  NT.ElectionModel = ElectionModel;

})(window);
