# -*- coding: utf-8 -*-
"""
한국가스공사 일반직(신입) 6급 서류전형 계산기 패널.

배점표는 공고문 첨부4(분야별 자격증 배점기준)·첨부5(외국어성적 환산기준)를 그대로
뜯어 `kogas_calc.json` 에 넣어 뒀다. 이 파일은 그 데이터로 화면(폼)과 계산 스크립트를 만든다.

계산 규칙(2026년 하반기 공고문 p.5, 첨부4):
  1) 서류 100점 = 외국어(영어) + 공통 자격증 + 직무 자격증
       사무 : 외국어 80 + 공통 20                (직무 자격증 없음)
       기술 : 외국어 60 + 공통 20 + 직무 20
  2) 외국어 = (TOEIC 환산점수 ÷ 990) × 80 또는 60
  3) 공통 자격증은 한국사·IT·국어능력·외국어구사능력 네 분야.
     동일분야 내 상위 등급 1개만 인정하고, AI·정보기술(전산) 지원자는 IT 분야 제외
  4) 직무 자격증은 기사 10점 / 산업기사 5점.
     동일종류는 상위등급 1개만, 인당 최대 2개까지
  5) 고급자격증 보유자는 서류전형 면제 + 배수외 선발 + 외국어 성적 면제

KOSHA(k)·한전(x) 패널과 겹치지 않게 이 패널의 CSS 클래스·DOM id 는 전부 g 로 시작한다.
(칩에 class="c" 를 쓰면 목록 쪽 paintChips() 가 innerHTML 을 덮어써서 사라진다)
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "kogas_calc.json")


def load():
    """데이터가 없으면 None. 패널을 통째로 빼고 나머지는 그대로 돌아간다."""
    try:
        with open(DATA, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


CSS = """
/* ---- 가스공사 서류전형 계산기 ---- */
.gc{font:inherit;font-size:13px;border:0;background:none;padding:1px 0;
color:var(--ink2);cursor:pointer;white-space:nowrap;line-height:1.9}
.gc::before{content:"□";color:var(--line);margin-right:5px}
.gc:hover{color:var(--pri2)}
.gc:focus-visible{outline:2px solid var(--pri);outline-offset:2px}
.gc.have{color:var(--pri2);font-weight:700}
.gc.have::before{content:"■";color:var(--pri)}
.gc.dim{color:var(--ink3);opacity:.5;cursor:default}
.gc.cut{color:var(--ink3);font-weight:400;text-decoration:line-through}
.gc.cut::before{content:"■";color:var(--line)}
/* 닫혀 있을 때는 막대조차 남기지 않는다. 상단 버튼이 유일한 입구다. */
#gpanel:not([open]){display:none}

.gbar{flex:1;min-width:90px;max-width:200px;height:6px;background:var(--line2);
border-radius:3px;overflow:hidden}
.gbar i{display:block;height:100%;background:var(--pri);width:0}
.form td.gcell{padding:9px 14px}
.gline{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:5px}
.gline .gv{font-size:13px;font-weight:700;color:var(--pri2);white-space:nowrap}
.gline .gn{font-size:12px;color:var(--ink3)}
.ggrade{font-size:12px;color:var(--ink3);white-space:nowrap;flex:0 0 104px}
.grow{display:flex;gap:8px;align-items:baseline;margin:2px 0}
/* 칩이 줄을 넘길 때 라벨 칸 아래로 흘러내리지 않게 따로 감싼다 */
.gchips{flex:1;min-width:0;display:flex;flex-wrap:wrap;gap:0 14px}
.grow.plain{flex-wrap:wrap}
.gf{font:inherit;font-size:13px;padding:4px 8px;border:1px solid var(--line);
border-radius:4px;background:#fff;color:var(--ink)}
.gf:focus-visible{outline:2px solid var(--pri);outline-offset:1px}
#glang{width:96px}
.gwarn{color:var(--orange);font-weight:700}
.gbad{color:var(--red);font-weight:700}
.gok{color:var(--green);font-weight:700}
.gnote{font-size:12px;color:var(--ink3);margin:7px 0 0}
.gres{display:flex;flex-wrap:wrap;gap:10px 20px;align-items:center;
padding:13px 16px;background:var(--tint);border-top:1px solid var(--line2)}
.gres .big{font-size:22px;font-weight:900;color:var(--pri2);letter-spacing:-.02em}
.gres .big small{font-size:13px;font-weight:400;color:var(--ink3);margin-left:2px}
.gres .seg{font-size:13px;color:var(--ink2)}
.gres .seg b{color:var(--pri2)}
"""


def panel(g):
    fopts = "".join(
        '<option value="%s"%s>%s</option>'
        % (f["name"], " selected" if f["name"] == "화공" else "", f["name"])
        for f in g["fields"])
    tests = ["TOEIC", "TEPS", "TEPS-S", "TOEIC-S", "OPIc"]
    topts = "".join('<option value="%s">%s</option>' % (t, t) for t in tests)
    adv = "".join(
        '<div class="grow"><span class="ggrade">%s</span>'
        '<span class="gchips gn">%s</span></div>'
        % (k, " · ".join(v)) for k, v in g["advanced"].items())
    return "".join([
        '<table class="form"><tbody>',

        '<tr><th scope="row">모집분야</th><td class="gcell">',
        '<div class="grow plain"><select class="gf" id="gfield">', fopts, "</select>",
        '<span class="gn" id="gfinfo"></span></div>',
        "</td></tr>",

        '<tr><th scope="row">외국어(영어)</th><td class="gcell">',
        '<div class="gline"><span class="gv" id="glangv">0 / 80</span>',
        '<span class="gn">(TOEIC 환산 ÷ 990) × 배점 · 사무 80점 · 기술 60점</span></div>',
        '<div class="grow plain"><select class="gf" id="gtest">', topts, "</select>",
        '<input class="gf" id="glang" type="text" inputmode="numeric" placeholder="점수/등급">',
        '<span class="gn" id="gconv">성적이 없으면 비워 두세요</span></div>',
        '<p class="gnote">지원자격은 <b>TOEIC 750점 이상</b>',
        "(사회형평(장애·보훈)은 500점 이상)입니다. ",
        "만점을 받으려면 990점이 필요해 사실상 상한이 없습니다.</p>",
        "</td></tr>",

        '<tr><th scope="row">공통 자격증</th><td class="gcell">',
        '<div class="gline"><span class="gv" id="gcomv">0 / 20</span>',
        '<span class="gn">동일분야 내 상위 등급 1개만 인정</span></div>',
        '<div id="gcommon"></div>',
        "</td></tr>",

        '<tr><th scope="row">직무 자격증</th><td class="gcell">',
        '<div class="gline"><span class="gv" id="gjobv">0 / 20</span>',
        '<span class="gn">기사 10점 · 산업기사 5점 · 동일종류는 상위등급 1개 · 최대 2개</span></div>',
        '<div id="gjob"></div>',
        '<p class="gnote">위 <b>내 자격증</b>에서 ■ 로 표시한 종목은 자동으로 켜집니다. ',
        "인정되지 않는 항목에는 <s>취소선</s>이 표시됩니다.</p>",
        "</td></tr>",

        '<tr><th scope="row">고급자격증</th><td class="gcell">',
        '<div class="gline"><span class="gn">아래를 보유하면 ',
        "<b>서류전형 면제 + 배수외 선발 + 외국어 성적 면제</b>, ",
        "필기 직무수행능력 만점의 10% 가점까지 붙습니다.</span></div>",
        adv,
        "</td></tr>",

        "</tbody></table>",

        '<div class="gres">',
        '<span class="big" id="gtotal">0<small> / 100점</small></span>',
        '<span class="seg" id="gseg"></span>',
        '<span class="spacer"></span>',
        '<button class="gf" id="greset" type="button">전체해제</button>',
        "</div>",
    ])


APP = """
/* ================= 가스공사 서류전형 계산기 ================= */
(function () {
  if (typeof KOGAS === 'undefined' || !KOGAS) return;
  var comHost = document.getElementById('gcommon');
  var jobHost = document.getElementById('gjob');
  if (!comHost || !jobHost) return;

  var G = { field: '화공', test: 'TOEIC', score: '', com: {}, job: {} };
  try {
    var raw = JSON.parse(localStorage.getItem('kogas') || 'null');
    if (raw) { G = Object.assign(G, raw); G.com = G.com || {}; G.job = G.job || {}; }
  } catch (e) {}

  var fieldEl = document.getElementById('gfield');
  var testEl = document.getElementById('gtest');
  var langEl = document.getElementById('glang');
  if (G.field) fieldEl.value = G.field;
  if (G.test) testEl.value = G.test;
  langEl.value = G.score || '';

  function saveG() {
    G.field = fieldEl.value; G.test = testEl.value; G.score = langEl.value;
    try { localStorage.setItem('kogas', JSON.stringify(G)); } catch (e) {}
  }

  function field() {
    var n = fieldEl.value, out = KOGAS.fields[0];
    KOGAS.fields.forEach(function (f) { if (f.name === n) out = f; });
    return out;
  }

  /* '내 자격증'에서 보유(1)로 켠 종목. 공고문이 등급을 행으로 나누고 종목명만 적어서
     '종목명+등급' 이 곧 자격증 이름이다(예: 기사 행의 '가스' = 가스기사).
     공고문에는 '측량 및 지형공간정보'처럼 띄어쓰기가 있어 공백은 지우고 맞춰본다. */
  function held(name) {
    if (typeof S === 'undefined') return false;
    return S[String(name).replace(/\\s/g, '')] === 1;
  }

  /* ---------------- 공통 자격증 ---------------- */
  function comRows() {
    var f = field();
    return KOGAS.common.map(function (g) {
      return { key: g.key, label: g.label, tiers: g.tiers,
               off: (g.key === 'it' && f.name === '전산') };
    });
  }

  /* 이름이 서로 달라 손으로 이어 주는 것들 */
  var COMSEED = { '한국사능력검정시험 1급': '한국사능력검정 1급',
                  '컴퓨터활용능력 1급': '컴퓨터활용능력 1급',
                  '정보처리기사': '정보처리기사' };

  function drawCom() {
    comHost.innerHTML = comRows().map(function (g) {
      return g.tiers.map(function (t) {
        var chips = t.items.map(function (n) {
          var id = g.key + '|' + t.score + '|' + n;
          var seed = COMSEED[n] && typeof S !== 'undefined' && S[COMSEED[n]] === 1;
          var on = G.com[id] !== undefined ? G.com[id] : (seed ? 1 : 0);
          G.com[id] = on ? 1 : 0;
          on = !g.off && !!on;
          return '<button class="gc gcom' + (on ? ' have' : '') + (g.off ? ' dim' : '') +
                 '" data-id="' + esc(id) + '" data-k="' + g.key + '" data-s="' + t.score +
                 '"' + (g.off ? ' disabled' : '') + '>' + esc(n) + '</button>';
        }).join('');
        return '<div class="grow"><span class="ggrade">' + esc(g.label) + ' ' +
               t.score + '점' + (g.off ? ' (제외)' : '') + '</span>' +
               '<span class="gchips">' + chips + '</span></div>';
      }).join('');
    }).join('');
  }

  /* 분야마다 켠 것 중 가장 높은 등급 하나만 */
  function comPick() {
    var keep = {}, sum = 0;
    comRows().forEach(function (g) {
      if (g.off) return;
      var best = null;
      g.tiers.forEach(function (t) {
        t.items.forEach(function (n) {
          var id = g.key + '|' + t.score + '|' + n;
          if (G.com[id] && (!best || t.score > best.s)) best = { s: t.score, id: id };
        });
      });
      if (best) { keep[best.id] = 1; sum += best.s; }
    });
    return { keep: keep, sum: Math.min(sum, field().com_cap) };
  }

  /* ---------------- 직무 자격증 ---------------- */
  function jobItems() { return KOGAS.job[fieldEl.value] || []; }

  function drawJob() {
    var items = jobItems();
    if (!items.length) {
      jobHost.innerHTML = '<p class="gnote">사무 분야는 직무 자격증 점수가 없습니다. ' +
                          '외국어 80점 + 공통 자격증 20점이 전부입니다.</p>';
      return;
    }
    jobHost.innerHTML = KOGAS.grades.map(function (gr) {
      var chips = items.map(function (n) {
        var id = fieldEl.value + '|' + gr.grade + '|' + n;
        var on = G.job[id] !== undefined ? G.job[id] : (held(n + gr.grade) ? 1 : 0);
        G.job[id] = on ? 1 : 0;
        return '<button class="gc gjob' + (on ? ' have' : '') +
               '" data-id="' + esc(id) + '" data-s="' + gr.score +
               '" data-n="' + esc(n) + '">' + esc(n + gr.grade) + '</button>';
      }).join('');
      return '<div class="grow"><span class="ggrade">' + esc(gr.grade) + ' ' +
             gr.score + '점</span><span class="gchips">' + chips + '</span></div>';
    }).join('');
  }

  /* 동일종류는 상위등급 1개, 남은 것 중 높은 2개만 */
  function jobPick() {
    var best = {};
    KOGAS.grades.forEach(function (gr) {
      jobItems().forEach(function (n) {
        var id = fieldEl.value + '|' + gr.grade + '|' + n;
        if (!G.job[id]) return;
        if (!best[n] || gr.score > best[n].s) best[n] = { s: gr.score, id: id };
      });
    });
    var arr = Object.keys(best).map(function (k) { return best[k]; });
    arr.sort(function (a, b) { return b.s - a.s; });
    var keep = {}, sum = 0;
    arr.slice(0, 2).forEach(function (o) { keep[o.id] = 1; sum += o.s; });
    return { keep: keep, sum: Math.min(sum, field().job_cap) };
  }

  /* ---------------- 외국어 ---------------- */
  function convert() {
    var v = String(langEl.value || '').trim();
    var t = testEl.value;
    if (!v) return null;
    if (t === 'TOEIC-S' || t === 'OPIc') {
      var m = KOGAS.conv[t === 'TOEIC-S' ? 'toeics' : 'opic'][v.toUpperCase()];
      return m === undefined ? null : m;
    }
    var n = parseInt(v.replace(/[^0-9]/g, ''), 10);
    if (isNaN(n)) return null;
    if (t === 'TOEIC') return n;
    var map = KOGAS.conv[t === 'TEPS' ? 'teps' : 'tepss'];
    /* 표에 없는 값은 그 아래에서 가장 가까운 칸으로 내려 읽는다(보수적으로) */
    var best = null;
    Object.keys(map).forEach(function (kk) {
      var key = parseInt(kk, 10);
      if (key <= n && (best === null || key > best)) best = key;
    });
    return best === null ? null : map[best];
  }

  /* ---------------- 합산 ---------------- */
  function calc() {
    var f = field();
    var toeic = convert(), lang = 0;
    if (toeic !== null) {
      lang = Math.min(f.lang_max,
                      Math.round(Math.min(toeic, 990) / 990 * f.lang_max * 100) / 100);
    }
    var cp = comPick(), jp = jobPick();
    return { f: f, toeic: toeic, lang: lang, com: cp.sum, job: jp.sum,
             comKeep: cp.keep, jobKeep: jp.keep,
             max: f.lang_max + f.com_cap + f.job_cap,
             total: Math.round((lang + cp.sum + jp.sum) * 100) / 100 };
  }

  function fmt(v) { return (Math.round(v * 100) / 100).toString(); }

  function paintG() {
    var r = calc();
    document.getElementById('glangv').textContent = fmt(r.lang) + ' / ' + r.f.lang_max;
    document.getElementById('gcomv').textContent = fmt(r.com) + ' / ' + r.f.com_cap;
    document.getElementById('gjobv').textContent = fmt(r.job) + ' / ' + r.f.job_cap;
    document.getElementById('gtotal').innerHTML =
      fmt(r.total) + '<small> / ' + r.max + '점</small>';
    document.getElementById('gseg').innerHTML =
      '외국어 <b>' + fmt(r.lang) + '</b> · 공통 <b>' + fmt(r.com) +
      '</b> · 직무 <b>' + fmt(r.job) + '</b>';
    document.getElementById('gfinfo').textContent =
      r.f.kind + ' · 서류 ' + r.f.ratio + ' 선발 · 만점 ' + r.max + '점' +
      (r.f.note ? ' · ' + r.f.note : '');

    document.querySelectorAll('.gcom').forEach(function (b) {
      var id = b.getAttribute('data-id');
      b.classList.toggle('cut', !!G.com[id] && !r.comKeep[id] && !b.disabled);
    });
    document.querySelectorAll('.gjob').forEach(function (b) {
      var id = b.getAttribute('data-id');
      b.classList.toggle('cut', !!G.job[id] && !r.jobKeep[id]);
    });

    var conv = document.getElementById('gconv');
    if (r.toeic === null) {
      conv.textContent = '성적이 없으면 비워 두세요';
      conv.className = 'gn';
    } else if (r.toeic < KOGAS.min_toeic) {
      conv.textContent = 'TOEIC ' + fmt(r.toeic) + ' 환산 — 지원자격(750) 미달' +
        (r.toeic >= KOGAS.min_toeic_equal ? ', 사회형평(장애·보훈)은 지원 가능' : '');
      conv.className = 'gn gbad';
    } else {
      conv.textContent = 'TOEIC ' + fmt(r.toeic) + ' 환산 — 990이면 만점(+' +
                         fmt(r.f.lang_max - r.lang) + '점 남음)';
      conv.className = 'gn ' + (r.toeic >= 990 ? 'gok' : 'gwarn');
    }

    var sum = document.getElementById('gsum');
    if (sum) sum.innerHTML = '<b>' + fmt(r.total) + '점</b> / ' + r.max +
                             ' · ' + esc(r.f.name);
    var bv = document.getElementById('gbtnv');
    if (bv) bv.textContent = fmt(r.total);
    var bar = document.getElementById('gbari');
    if (bar) bar.style.width = Math.min(100, r.total / r.max * 100) + '%';
    saveG();
  }

  comHost.addEventListener('click', function (e) {
    var b = e.target.closest('.gcom');
    if (!b || b.disabled) return;
    var id = b.getAttribute('data-id');
    G.com[id] = G.com[id] ? 0 : 1;
    b.classList.toggle('have', !!G.com[id]);
    paintG();
  });

  jobHost.addEventListener('click', function (e) {
    var b = e.target.closest('.gjob');
    if (!b) return;
    var id = b.getAttribute('data-id');
    G.job[id] = G.job[id] ? 0 : 1;
    b.classList.toggle('have', !!G.job[id]);
    paintG();
  });

  fieldEl.addEventListener('change', function () { drawCom(); drawJob(); paintG(); });
  testEl.addEventListener('change', paintG);
  langEl.addEventListener('input', paintG);
  document.getElementById('greset').addEventListener('click', function () {
    G = { field: fieldEl.value, test: testEl.value, score: '', com: {}, job: {} };
    langEl.value = '';
    drawCom(); drawJob(); paintG();
  });

  /* 계산기는 접어 두고 상단 머리띠의 '가스공사' 버튼으로 연다.
     브라우저가 details 의 열림 상태를 세션에 기억했다가 load 이후에 되살리기 때문에
     사용자가 직접 누르기 전까지는 몇 번이고 닫는다. */
  var box = document.getElementById('gpanel');
  var btn = document.getElementById('gbtn');
  var others = ['kpanel', 'xpanel'].map(function (id) { return document.getElementById(id); });
  if (btn && box) {
    var touched = false;
    function forceClosed() { if (!touched) box.open = false; }
    forceClosed();
    setTimeout(forceClosed, 0);
    window.addEventListener('load', forceClosed);
    window.addEventListener('pageshow', forceClosed);

    btn.addEventListener('click', function () {
      touched = true;
      box.open = !box.open;
      if (box.open) {
        others.forEach(function (o) { if (o) o.open = false; });
        box.scrollIntoView({ block: 'start', behavior: 'smooth' });
      }
    });
    box.addEventListener('toggle', function () {
      btn.setAttribute('aria-expanded', box.open ? 'true' : 'false');
      btn.classList.toggle('on', box.open);
    });
    /* 계산기를 동시에 펼치면 목록이 화면 밖으로 밀린다. 한 번에 하나만. */
    ['kbtn', 'xbtn'].forEach(function (id) {
      var b = document.getElementById(id);
      if (b) b.addEventListener('click', function () { touched = true; box.open = false; });
    });
  }

  drawCom();
  drawJob();
  paintG();
})();
"""
