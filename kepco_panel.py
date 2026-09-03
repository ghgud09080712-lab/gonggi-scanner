# -*- coding: utf-8 -*-
"""
한국전력공사 4직급 대졸수준 신입 1차(서류)전형 계산기 패널.

배점표는 공고문 붙임2(외국어성적 환산기준)·붙임5(자격증 보유 가점표)를 그대로 뜯어
`kepco_calc.json` 에 넣어 뒀다. 이 파일은 그 데이터로 화면(폼)과 계산 스크립트를 만든다.

계산 규칙(2026년도 하반기 공고문):
  1) 1차전형 = 외국어 성적(100) + 자격증 가점(사무 20 / 기술 40)
  2) 외국어 = (TOEIC 환산점수 ÷ 상한점수) × 100.  상한은 사무 850, 기술 800
  3) 공통 가점은 한국사·국어능력·IT·외국어구사능력 네 분야 각 5점.
     ICT 지원자는 IT 분야에서 제외되어 공통 상한이 15점이다
  4) 계열별 자격가점은 최대 2개, 동일종류는 상위등급 1개만 인정 → 상한 20점
  5) 커트라인(사무 120 / 배전·송변전 130 / ICT·토목 120) 이상이면 전원 합격

KOSHA 패널과 이름이 겹치지 않도록 이 패널의 CSS 클래스·DOM id 는 전부 x 로 시작한다.
(특히 칩에 class="c" 를 쓰면 목록 쪽 paintChips() 가 innerHTML 을 덮어써서 사라진다)
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "kepco_calc.json")


def load():
    """데이터가 없으면 None. 패널을 통째로 빼고 나머지는 그대로 돌아간다."""
    try:
        with open(DATA, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


CSS = """
/* ---- 한전 1차전형 계산기 ---- */
.xc{font:inherit;font-size:13px;border:0;background:none;padding:1px 0;
color:var(--ink2);cursor:pointer;white-space:nowrap;line-height:1.9}
.xc::before{content:"□";color:var(--line);margin-right:5px}
.xc:hover{color:var(--pri2)}
.xc:focus-visible{outline:2px solid var(--pri);outline-offset:2px}
.xc.have{color:var(--pri2);font-weight:700}
.xc.have::before{content:"■";color:var(--pri)}
.xc.dim{color:var(--ink3);opacity:.5;cursor:default}
.xc.cut{color:var(--ink3);font-weight:400;text-decoration:line-through}
.xc.cut::before{content:"■";color:var(--line)}
/* 닫혀 있을 때는 막대조차 남기지 않는다. 상단 버튼이 유일한 입구다. */
#xpanel:not([open]){display:none}

.xtot{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--ink2)}
.xbar{flex:1;min-width:90px;max-width:200px;height:6px;background:var(--line2);
border-radius:3px;overflow:hidden}
.xbar i{display:block;height:100%;background:var(--pri);width:0}
.form td.xcell{padding:9px 14px}
.xline{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:5px}
.xline .xv{font-size:13px;font-weight:700;color:var(--pri2);white-space:nowrap}
.xline .xn{font-size:12px;color:var(--ink3)}
.xgrade{font-size:12px;color:var(--ink3);white-space:nowrap;flex:0 0 92px}
.xrow{display:flex;gap:8px;align-items:baseline;margin:2px 0}
/* 칩이 줄을 넘길 때 라벨 칸 아래로 흘러내리지 않게 따로 감싼다 */
.xchips{flex:1;min-width:0;display:flex;flex-wrap:wrap;gap:0 14px}
.xrow.plain{flex-wrap:wrap}
.xf{font:inherit;font-size:13px;padding:4px 8px;border:1px solid var(--line);
border-radius:4px;background:#fff;color:var(--ink)}
.xf:focus-visible{outline:2px solid var(--pri);outline-offset:1px}
#xlang{width:96px}
.xwarn{color:var(--orange);font-weight:700}
.xbad{color:var(--red);font-weight:700}
.xok{color:var(--green);font-weight:700}
.xnote{font-size:12px;color:var(--ink3);margin:7px 0 0}
.xres{display:flex;flex-wrap:wrap;gap:10px 20px;align-items:center;
padding:13px 16px;background:var(--tint);border-top:1px solid var(--line2)}
.xres .big{font-size:22px;font-weight:900;color:var(--pri2);letter-spacing:-.02em}
.xres .big small{font-size:13px;font-weight:400;color:var(--ink3);margin-left:2px}
.xres .seg{font-size:13px;color:var(--ink2)}
.xres .seg b{color:var(--pri2)}
.xcut{font-size:13px;font-weight:700}
"""


def panel(x):
    """검색조건 표와 같은 형태의 폼. 왼쪽 라벨 + 오른쪽 입력."""
    fopts = "".join(
        '<option value="%s"%s>%s</option>'
        % (f["name"], " selected" if f["name"] == "사무" else "", f["name"])
        for f in x["fields"])
    tests = ["TOEIC", "TEPS", "TEPS-S", "TOEIC-S", "OPIc"]
    topts = "".join('<option value="%s">%s</option>' % (t, t) for t in tests)
    adv = " · ".join(x["advanced"])
    return "".join([
        '<table class="form"><tbody>',

        '<tr><th scope="row">지원분야</th><td class="xcell">',
        '<div class="xrow plain"><select class="xf" id="xfield">', fopts, "</select>",
        '<span class="xn" id="xfinfo"></span></div>',
        "</td></tr>",

        '<tr><th scope="row">외국어 성적</th><td class="xcell">',
        '<div class="xline"><span class="xv" id="xlangv">0 / 100</span>',
        '<span class="xn">(TOEIC 환산 ÷ 상한) × 100 · 상한 사무 850 · 기술 800</span></div>',
        '<div class="xrow plain"><select class="xf" id="xtest">', topts, "</select>",
        '<input class="xf" id="xlang" type="text" inputmode="numeric" placeholder="점수/등급">',
        '<span class="xn" id="xconv">성적이 없으면 비워 두세요</span></div>',
        '<p class="xnote">지원자격은 <b>TOEIC 환산 700점 이상</b>입니다. ',
        "고급자격증 보유자는 외국어 성적도 1차전형도 면제됩니다 — ", adv, ".</p>",
        "</td></tr>",

        '<tr><th scope="row">공통 가점</th><td class="xcell">',
        '<div class="xline"><span class="xv" id="xcomv">0 / 20</span>',
        '<span class="xn">분야마다 5점 · 한 분야에서 여러 개를 가져도 5점입니다</span></div>',
        '<div id="xcommon"></div>',
        "</td></tr>",

        '<tr><th scope="row">계열 가점</th><td class="xcell">',
        '<div class="xline"><span class="xv" id="xserv">0 / 20</span>',
        '<span class="xn">최대 2개 · 동일종류는 상위등급 1개만</span></div>',
        '<div id="xseries"></div>',
        '<p class="xnote">위 <b>내 자격증</b>에서 ■ 로 표시한 종목은 자동으로 켜집니다. ',
        "인정되지 않는 항목에는 <s>취소선</s>이 표시됩니다.</p>",
        "</td></tr>",

        "</tbody></table>",

        '<div class="xres">',
        '<span class="big" id="xtotal">0<small> / 120점</small></span>',
        '<span class="seg" id="xseg"></span>',
        '<span class="xcut" id="xcutmsg"></span>',
        '<span class="spacer"></span>',
        '<button class="xf" id="xreset" type="button">전체해제</button>',
        "</div>",
    ])


APP = """
/* ================= 한전 1차(서류)전형 계산기 ================= */
(function () {
  if (typeof KEPCO === 'undefined' || !KEPCO) return;
  var comHost = document.getElementById('xcommon');
  var serHost = document.getElementById('xseries');
  if (!comHost || !serHost) return;

  var X = { field: '사무', test: 'TOEIC', score: '', com: {}, ser: {} };
  try {
    var raw = JSON.parse(localStorage.getItem('kepco') || 'null');
    if (raw) { X = Object.assign(X, raw); X.com = X.com || {}; X.ser = X.ser || {}; }
  } catch (e) {}

  var fieldEl = document.getElementById('xfield');
  var testEl = document.getElementById('xtest');
  var langEl = document.getElementById('xlang');
  if (X.field) fieldEl.value = X.field;
  if (X.test) testEl.value = X.test;
  langEl.value = X.score || '';

  function saveX() {
    X.field = fieldEl.value; X.test = testEl.value; X.score = langEl.value;
    try { localStorage.setItem('kepco', JSON.stringify(X)); } catch (e) {}
  }

  function field() {
    var n = fieldEl.value, out = KEPCO.fields[0];
    KEPCO.fields.forEach(function (f) { if (f.name === n) out = f; });
    return out;
  }

  /* 위 '내 자격증' 패널에서 보유(1)로 켠 종목을 알아본다.
     공고문이 등급을 행으로 나누고 종목명만 적어서 '종목명+등급' 이 곧 자격증 이름이다.
     (예: [기사] 전기 = 전기기사).  전문자격(ADP 등)은 이름 그 자체다. */
  function held(name, grade) {
    if (typeof S === 'undefined') return false;
    if (grade === '전문자격') return S[name] === 1;
    return S[name + grade] === 1;
  }

  /* 동일종류 판정용 묶음. 국가기술자격은 종목명이 곧 종류이고,
     ICT 전문자격만 상·하위가 이름부터 달라 따로 묶어 준다. */
  var FAM = { 'ADP': 'ADP', 'ADsP': 'ADP', 'DAP': 'DAP', 'DAsP': 'DAP',
              'SQLP': 'SQL', 'SQLD': 'SQL',
              'COS Pro 1급': 'COS', 'COS Pro 2급': 'COS',
              'PCCP Lv3~5': 'PCCP', 'PCCP Lv2': 'PCCP' };
  function fam(name) { return FAM[name] || name; }

  /* ---------------- 공통 가점 ---------------- */
  function comRows() {
    var f = field();
    return KEPCO.common.map(function (g) {
      var items = g.items.slice();
      if (g.key === 'lang2') {
        items = (KEPCO.lang2[f.kind] || []).concat(KEPCO.lang2_extra);
      }
      return { key: g.key, label: g.label, score: g.score, items: items,
               off: (g.key === 'it' && f.name === 'ICT') };
    });
  }

  /* 공통 가점 중 '내 자격증'에 그대로 있는 것들. 이름이 서로 달라 손으로 이어 준다.
     (한국사는 '3급 이상'이라 1급을 갖고 있으면 당연히 충족) */
  var COMSEED = { '한국사능력검정시험 3급 이상': '한국사능력검정 1급',
                  '정보처리기사': '정보처리기사',
                  '컴퓨터활용능력 1급': '컴퓨터활용능력 1급' };

  function drawCom() {
    comHost.innerHTML = comRows().map(function (g) {
      var chips = g.items.map(function (n) {
        var id = g.key + '|' + n;
        var seed = COMSEED[n] && typeof S !== 'undefined' && S[COMSEED[n]] === 1;
        var on = X.com[id] !== undefined ? X.com[id] : (seed ? 1 : 0);
        X.com[id] = on ? 1 : 0;
        on = !g.off && !!on;
        return '<button class="xc xcom' + (on ? ' have' : '') + (g.off ? ' dim' : '') +
               '" data-id="' + esc(id) + '" data-k="' + g.key + '"' +
               (g.off ? ' disabled' : '') + '>' + esc(n) + '</button>';
      }).join('');
      return '<div class="xrow"><span class="xgrade">' + esc(g.label) + ' ' +
             g.score + '점' + (g.off ? ' (제외)' : '') + '</span>' +
             '<span class="xchips">' + chips + '</span></div>';
    }).join('');
  }

  function comScore() {
    var sum = 0;
    comRows().forEach(function (g) {
      if (g.off) return;
      var any = g.items.some(function (n) { return X.com[g.key + '|' + n] === 1; });
      if (any) sum += g.score;
    });
    return sum;
  }

  function comCap() { return field().name === 'ICT' ? 15 : 20; }

  /* ---------------- 계열 가점 ---------------- */
  function serGroups() { return KEPCO.series[fieldEl.value] || []; }

  function drawSer() {
    var gs = serGroups();
    if (!gs.length) {
      serHost.innerHTML = '<p class="xnote">사무 분야는 계열별 자격가점이 없습니다. ' +
                          '자격증 가점은 위 공통 가점 20점이 전부입니다.</p>';
      return;
    }
    serHost.innerHTML = gs.map(function (g) {
      return g.rows.map(function (r) {
        var grade = r[0];
        var chips = r[1].map(function (n) {
          var id = fieldEl.value + '|' + grade + '|' + n;
          var on = X.ser[id] !== undefined ? X.ser[id] : (held(n, grade) ? 1 : 0);
          X.ser[id] = on ? 1 : 0;
          var label = grade === '전문자격' ? n : n + grade;
          return '<button class="xc xser' + (on ? ' have' : '') +
                 '" data-id="' + esc(id) + '" data-s="' + g.score +
                 '" data-f="' + esc(fam(n)) + '">' + esc(label) + '</button>';
        }).join('');
        return '<div class="xrow"><span class="xgrade">' + esc(grade) + ' ' +
               g.score + '점</span><span class="xchips">' + chips + '</span></div>';
      }).join('');
    }).join('');
  }

  /* 켠 것 중 동일종류는 상위등급 1개만 남기고, 남은 것 중 점수 높은 2개만 인정 */
  function serPick() {
    var best = {};
    serGroups().forEach(function (g) {
      g.rows.forEach(function (r) {
        r[1].forEach(function (n) {
          var id = fieldEl.value + '|' + r[0] + '|' + n;
          if (!X.ser[id]) return;
          var k = fam(n);
          if (!best[k] || g.score > best[k].s) best[k] = { s: g.score, id: id };
        });
      });
    });
    var arr = Object.keys(best).map(function (k) { return best[k]; });
    arr.sort(function (a, b) { return b.s - a.s; });
    var keep = {}, sum = 0;
    arr.slice(0, 2).forEach(function (o) { keep[o.id] = 1; sum += o.s; });
    return { keep: keep, sum: Math.min(sum, 20) };
  }

  /* ---------------- 외국어 ---------------- */
  function convert() {
    var v = String(langEl.value || '').trim();
    var t = testEl.value;
    if (!v) return null;
    if (t === 'TOEIC-S' || t === 'OPIc') {
      var m = KEPCO.conv[t === 'TOEIC-S' ? 'toeics' : 'opic'][v.toUpperCase()];
      return m === undefined ? null : m;
    }
    var n = parseInt(v.replace(/[^0-9]/g, ''), 10);
    if (isNaN(n)) return null;
    if (t === 'TOEIC') return n;
    var map = KEPCO.conv[t === 'TEPS' ? 'teps' : 'tepss'];
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
    if (toeic !== null) lang = Math.min(100, Math.round(toeic / f.cap * 100 * 100) / 100);
    var com = Math.min(comScore(), comCap());
    var p = serPick();
    return { f: f, toeic: toeic, lang: lang, com: com, ser: p.sum, keep: p.keep,
             max: 100 + comCap() + f.series_cap,
             total: Math.round((lang + com + p.sum) * 100) / 100 };
  }

  function fmt(v) { return (Math.round(v * 100) / 100).toString(); }

  function paintX() {
    var r = calc();
    document.getElementById('xlangv').textContent = fmt(r.lang) + ' / 100';
    document.getElementById('xcomv').textContent = fmt(r.com) + ' / ' + comCap();
    document.getElementById('xserv').textContent = fmt(r.ser) + ' / ' + r.f.series_cap;
    document.getElementById('xtotal').innerHTML =
      fmt(r.total) + '<small> / ' + r.max + '점</small>';
    document.getElementById('xseg').innerHTML =
      '외국어 <b>' + fmt(r.lang) + '</b> · 공통 <b>' + fmt(r.com) +
      '</b> · 계열 <b>' + fmt(r.ser) + '</b>';
    document.getElementById('xfinfo').textContent =
      r.f.kind + ' · 외국어 상한 ' + r.f.cap + '점 · 서류 ' + r.f.ratio +
      ' · 전원합격선 ' + r.f.cut + '점';

    /* 인정되지 않는 계열 자격증에 취소선 */
    document.querySelectorAll('.xser').forEach(function (b) {
      var id = b.getAttribute('data-id');
      b.classList.toggle('cut', !!X.ser[id] && !r.keep[id]);
    });

    var conv = document.getElementById('xconv');
    if (r.toeic === null) {
      conv.textContent = '성적이 없으면 비워 두세요';
      conv.className = 'xn';
    } else if (r.toeic < KEPCO.min_toeic) {
      conv.textContent = 'TOEIC ' + fmt(r.toeic) + ' 환산 — 지원자격(700) 미달입니다';
      conv.className = 'xn xbad';
    } else if (r.toeic >= r.f.cap) {
      conv.textContent = 'TOEIC ' + fmt(r.toeic) + ' 환산 — 만점입니다. 더 올려도 100점입니다';
      conv.className = 'xn xok';
    } else {
      conv.textContent = 'TOEIC ' + fmt(r.toeic) + ' 환산 — ' + r.f.cap +
                         '이면 만점(+' + fmt(100 - r.lang) + '점 남음)';
      conv.className = 'xn xwarn';
    }

    var cm = document.getElementById('xcutmsg');
    var gap = Math.round((r.f.cut - r.total) * 100) / 100;
    if (gap <= 0) {
      cm.textContent = '전원합격선 ' + r.f.cut + '점 통과';
      cm.className = 'xcut xok';
    } else {
      cm.textContent = '전원합격선 ' + r.f.cut + '점까지 ' + fmt(gap) + '점';
      cm.className = 'xcut xwarn';
    }

    var sum = document.getElementById('xsum');
    if (sum) sum.innerHTML = '<b>' + fmt(r.total) + '점</b> / ' + r.max +
                             ' · ' + esc(r.f.name);
    var bv = document.getElementById('xbtnv');
    if (bv) bv.textContent = fmt(r.total);
    var bar = document.getElementById('xbari');
    if (bar) bar.style.width = Math.min(100, r.total / r.max * 100) + '%';
    saveX();
  }

  comHost.addEventListener('click', function (e) {
    var b = e.target.closest('.xcom');
    if (!b || b.disabled) return;
    var id = b.getAttribute('data-id');
    X.com[id] = X.com[id] ? 0 : 1;
    b.classList.toggle('have', !!X.com[id]);
    paintX();
  });

  serHost.addEventListener('click', function (e) {
    var b = e.target.closest('.xser');
    if (!b) return;
    var id = b.getAttribute('data-id');
    X.ser[id] = X.ser[id] ? 0 : 1;
    b.classList.toggle('have', !!X.ser[id]);
    paintX();
  });

  fieldEl.addEventListener('change', function () { drawCom(); drawSer(); paintX(); });
  testEl.addEventListener('change', paintX);
  langEl.addEventListener('input', paintX);
  document.getElementById('xreset').addEventListener('click', function () {
    X = { field: fieldEl.value, test: testEl.value, score: '', com: {}, ser: {} };
    langEl.value = '';
    drawCom(); drawSer(); paintX();
  });

  /* 계산기는 접어 두고, 상단 머리띠의 작은 '한전' 버튼으로 연다.
     브라우저가 details 의 열림 상태를 세션에 기억했다가 load 이후에 되살리기 때문에
     사용자가 직접 누르기 전까지는 몇 번이고 닫는다. */
  var box = document.getElementById('xpanel');
  var btn = document.getElementById('xbtn');
  var kbox = document.getElementById('kpanel');
  var kbtn = document.getElementById('kbtn');
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
        if (kbox) kbox.open = false;
        box.scrollIntoView({ block: 'start', behavior: 'smooth' });
      }
    });
    box.addEventListener('toggle', function () {
      btn.setAttribute('aria-expanded', box.open ? 'true' : 'false');
      btn.classList.toggle('on', box.open);
    });
    /* 두 계산기를 동시에 펼치면 목록이 화면 밖으로 밀린다. 한 번에 하나만. */
    if (kbtn) kbtn.addEventListener('click', function () { touched = true; box.open = false; });
  }

  drawCom();
  drawSer();
  paintX();
})();
"""
