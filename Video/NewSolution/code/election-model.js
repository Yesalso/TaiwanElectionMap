/* ==========================================================================
   election-model.js — 選舉資料模型（泛化版，支援任意候選人數）
   ========================================================================== */
(function (global) {
  'use strict';

  var NT = global.NT = global.NT || {};
  var U = NT.Utils;

  function Candidate(raw, slot) {
    this.key = raw.key;
    this.slot = slot;
    this.name = raw.name;
    this.nameEn = raw.nameEn || '';
    this.party = raw.party;
    this.partyShort = raw.partyShort || '';
    this.partyEn = raw.partyEn || '';
    this.number = raw.number;
    this.votes = raw.votes;
    this.pct = raw.pct;
    this.share = raw.share;
    this.elected = !!raw.elected;
    this.photo = raw.photo || null;
    this.partyKey = Candidate.partyKeyOf(this.partyShort);
    this.theme = NT.Theme.party(this.partyKey);
  }

  Candidate.partyKeyOf = function (short) {
    if (short === 'KMT') return 'kmt';
    if (short === 'DPP') return 'dpp';
    if (short === 'TPP') return 'tpp';
    if (short === 'NSC') return 'nsc';
    return 'ind';
  };

  Candidate.prototype.votesText = function () { return U.voteWan(this.votes); };
  Candidate.prototype.votesLabel = function () { return this.votesText() + '票'; };
  Candidate.prototype.pctText = function () { return this.pct.toFixed(2); };
  Candidate.prototype.partyAbbr = function () {
    if (this.partyShort === 'KMT') return 'KMT';
    if (this.partyShort === 'DPP') return 'DPP';
    if (this.partyShort === 'TPP') return 'TPP';
    if (this.partyShort === 'NSC') return 'NSC';
    return 'IND';
  };

  function ElectionModel(raw) {
    if (!raw) throw new Error('缺少選舉資料');
    this.raw = raw;
    this.meta = raw.meta;

    var photos = raw.photos || {};
    var candidates = (raw.candidates || []).map(function (c, i) {
      var cc = Object.assign({}, c);
      cc.photo = photos[c.key] || null;
      return new Candidate(cc, c.slot || (i < 2 ? (i === 0 ? 'left' : 'right') : 'minor'));
    });

    /* 依得票高低決定主卡左右：得票高者放左 */
    var mainCandidates = candidates.filter(function (c) { return c.slot !== 'minor'; });
    mainCandidates.sort(function (a, b) { return b.votes - a.votes; });
    this.main = mainCandidates.slice(0, 2);
    this.minors = candidates.filter(function (c) { return this.main.indexOf(c) < 0; }, this);

    this.left = this.main[0] || this.minors[0];
    this.right = this.main[1] || this.left;
    this.candidates = this.main.concat(this.minors);

    /* 勝負差距（以前二名） */
    this.marginVotes = Math.abs(this.left.votes - this.right.votes);
    this.marginPct = Math.abs(this.left.pct - this.right.pct);
    this.winner = this.left.votes >= this.right.votes ? this.left : this.right;
    this.loser = this.winner === this.left ? this.right : this.left;

    /* 行政區：附上色階 */
    this.districts = (raw.districts || []).map(function (d) {
      var winnerKey = d.winnerKey;
      var winner = this.candidates.find(function (c) { return c.key === winnerKey; });
      var partyKey = winner ? winner.partyKey : 'ind';
      return {
        name: d.name, short: d.short, villages: d.villages,
        votes: d.votes, pct: d.pct, valid: d.valid,
        winnerKey: winnerKey, partyKey: partyKey,
        margin: d.margin,
        color: NT.Theme.mapShade(partyKey, d.margin)
      };
    }, this);

    this.districtTally = {};
    this.candidates.forEach(function (c) {
      this.districtTally[c.partyKey] = this.districts.filter(function (d) { return d.partyKey === c.partyKey; }).length;
    }, this);

    this.districtByName = {};
    this.districts.forEach(function (d) { this.districtByName[d.name] = d; }, this);

    this.geojson = raw.geojson;
  }

  ElectionModel.prototype.districtOf = function (townName) {
    if (this.districtByName[townName]) return this.districtByName[townName];
    var key = Object.keys(this.districtByName).find(function (k) {
      return k.indexOf(townName) === 0 || townName.indexOf(k) === 0;
    });
    return key ? this.districtByName[key] : null;
  };

  ElectionModel.prototype.ribbonSegments = function () {
    return this.candidates.slice().sort(function (a, b) { return b.votes - a.votes; })
      .map(function (c) { return { key: c.key, color: c.theme.main, ratio: c.pct / 100, label: c.name }; });
  };

  ElectionModel.prototype.mains = function () { return this.main; };

  ElectionModel.prototype.summary = function () {
    return this.meta.election + '：' + this.winner.name + '以 ' +
      U.voteWan(this.marginVotes) + ' 票之差當選';
  };

  NT.Candidate = Candidate;
  NT.ElectionModel = ElectionModel;

})(window);