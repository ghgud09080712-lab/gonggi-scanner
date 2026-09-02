# -*- coding: utf-8 -*-
"""
KOSHA 신입직 5급·6급 서류 정량평가(100점) 계산기 패널.

배점표 자체는 공고문 [참고자료 6-1·6-2] 를 그대로 뜯어 `kosha_calc.json` 에
넣어 뒀다. 이 파일은 그 데이터로 화면(폼)과 계산 스크립트를 만든다.

계산 규칙(공고문 p.62):
  1) 직무기술자격·사무자동화는 해당사항을 모두 인정, 공인어학·한국사는 최상위 1개만
  2) 그럼에도 항목별 점수는 배점을 넘지 못한다 (기사 4개=52 → 50)
  3) 유효기간이 있는 서류는 접수 마감일 기준 유효해야 한다
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "kosha_calc.json")

CAPS = {"job": 50, "lang": 25, "office": 20, "hist": 5}


def load():
    """데이터가 없으면 None. 패널을 통째로 빼고 나머지는 그대로 돌아간다."""
    try:
        with open(DATA, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


CSS = """
/* ---- KOSHA 정량평가 계산기 ---- */
.kwrap{padding:0}
.kc{font:inherit;font-size:13px;border:0;background:none;padding:1px 0;
color:var(--ink2);cursor:pointer;white-space:nowrap;line-height:1.9}
.kc::before{content:"□";color:var(--line);margin-right:5px}
.kc:hover{color:var(--pri2)}
.kc:focus-visible{outline:2px solid var(--pri);outline-offset:2px}
.kc.have{color:var(--pri2);font-weight:700}
.kc.have::before{content:"■";color:var(--pri)}
/* 닫혀 있을 때는 막대조차 남기지 않는다. 상단 버튼이 유일한 입구다. */
#kpanel:not([open]){display:none}

/* 상단 머리띠의 작은 여는 버튼 */
.kbtn{font:inherit;font-size:12px;line-height:1;padding:6px 11px;cursor:pointer;
margin-left:12px;border:1px solid var(--pri3);border-radius:24px;
background:#fff;color:var(--pri2);white-space:nowrap}
.kbtn:hover{background:var(--tint)}
.kbtn:focus-visible{outline:2px solid var(--pri);outline-offset:2px}
.kbtn.on{background:var(--pri);border-color:var(--pri);color:#fff}
.kbtn b{font-weight:700;margin-left:5px}
.kbtn.on b{color:#fff}
.ktot{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--ink2)}
.ktot b{font-size:15px;color:var(--pri2)}
.kbar{flex:1;min-width:90px;max-width:200px;height:6px;background:var(--line2);
border-radius:3px;overflow:hidden}
.kbar i{display:block;height:100%;background:var(--pri);width:0}
.form td.kcell{padding:9px 14px}
.kline{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:5px}
.kline .kv{font-size:13px;font-weight:700;color:var(--pri2);white-space:nowrap}
.kline .kn{font-size:12px;color:var(--ink3)}
.kgrade{font-size:12px;color:var(--ink3);margin-right:4px;white-space:nowrap}
.krow{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;margin:2px 0}
.kf{font:inherit;font-size:13px;padding:4px 8px;border:1px solid var(--line);
border-radius:4px;background:#fff;color:var(--ink)}
.kf:focus-visible{outline:2px solid var(--pri);outline-offset:1px}
#klang{width:96px}
.kwarn{color:var(--orange);font-weight:700}
.kok{color:var(--green);font-weight:700}
.knote{font-size:12px;color:var(--ink3);margin:7px 0 0}
.kres{display:flex;flex-wrap:wrap;gap:10px 20px;align-items:center;
padding:13px 16px;background:var(--tint);border-top:1px solid var(--line2)}
.kres .big{font-size:22px;font-weight:900;color:var(--pri2);letter-spacing:-.02em}
.kres .big small{font-size:13px;font-weight:400;color:var(--ink3);margin-left:2px}
.kres .seg{font-size:13px;color:var(--ink2)}
.kres .seg b{color:var(--pri2)}
"""


def panel(k):
    """검색조건 표와 같은 형태의 폼. 왼쪽 라벨 + 오른쪽 입력."""
    fields = list(k["jobs"].keys())
    opts = "".join('<option value="%s"%s>%s</option>'
                   % (f, " selected" if f == "산업보건(위생)" else "", f)
                   for f in fields)
    office = "".join(
        '<div class="krow"><span class="kgrade">%d점</span>%s</div>'
        % (g["score"], "".join('<button class="kc ko" data-k="office" data-n="%s" '
                               'data-s="%d">%s</button>' % (n, g["score"], n)
                               for n in g["items"]))
        for g in k["office"])
    hist = "".join('<button class="kc ko" data-k="hist" data-n="%s" data-s="%d">%s '
                   '<span class="kn">%d점</span></button>'
                   % (h["name"], h["score"], h["name"], h["score"])
                   for h in k["hist"])
    tests = ["TOEIC", "G-TELP(Level2)", "New TEPS", "TOEFL(iBT)", "FLEX(듣기/읽기)", "TOEIC-S"]
    topts = "".join('<option value="%s">%s</option>' % (t, t) for t in tests)
    return "".join([
        '<table class="form"><tbody>',

        '<tr><th scope="row">채용분야</th><td class="kcell">',
        '<div class="krow"><select class="kf" id="kfield">', opts, "</select>",
        '<span class="kn">분야마다 인정 종목이 다릅니다. 고르면 아래 목록이 바뀝니다.</span>',
        "</div></td></tr>",

        '<tr><th scope="row">직무기술자격</th><td class="kcell">',
        '<div class="kline"><span class="kv" id="kjobv">0 / 50</span>',
        '<span class="kn">모두 인정 · 배점 초과분은 잘립니다</span></div>',
        '<div id="kjob"></div>',
        '<p class="knote">위 <b>내 자격증</b>에서 ■ 로 표시한 종목은 자동으로 켜집니다.</p>',
        "</td></tr>",

        '<tr><th scope="row">공인어학</th><td class="kcell">',
        '<div class="kline"><span class="kv" id="klangv">0 / 25</span>',
        '<span class="kn">최상위 1개만 · (TOEIC 환산 ÷ 800) × 25 · 800 이상 만점</span></div>',
        '<div class="krow"><select class="kf" id="ktest">', topts, "</select>",
        '<input class="kf" id="klang" type="text" inputmode="numeric" placeholder="점수">',
        '<span class="kn" id="kconv">성적이 없으면 비워 두세요</span></div>',
        "</td></tr>",

        '<tr><th scope="row">사무자동화</th><td class="kcell">',
        '<div class="kline"><span class="kv" id="kofficev">0 / 20</span>',
        '<span class="kn">모두 인정 · 합산 후 20점에서 잘립니다</span></div>',
        office,
        "</td></tr>",

        '<tr><th scope="row">한국사능력</th><td class="kcell">',
        '<div class="kline"><span class="kv" id="khistv">0 / 5</span>',
        '<span class="kn">최상위 1개만</span></div>',
        '<div class="krow">', hist, "</div>",
        "</td></tr>",

        "</tbody></table>",

        '<div class="kres">',
        '<span class="big" id="ktotal">0<small> / 100점</small></span>',
        '<span class="seg" id="kseg"></span>',
        '<span class="spacer"></span>',
        '<button class="kf" id="kreset" type="button">전체해제</button>',
        "</div>",
    ])


APP = """
/* ================= KOSHA 정량평가 계산기 ================= */
(function () {
  if (typeof KOSHA === 'undefined' || !KOSHA) return;
  var host = document.getElementById('kjob');
  if (!host) return;

  var K = { office: {}, hist: null, test: 'TOEIC', score: '', field: '산업보건(위생)' };
  try {
    var raw = JSON.parse(localStorage.getItem('kosha') || 'null');
    if (raw) { K = Object.assign(K, raw); K.office = K.office || {}; }
  } catch (e) {}

  var fieldEl = document.getElementById('kfield');
  var testEl = document.getElementById('ktest');
  var langEl = document.getElementById('klang');
  if (K.field) fieldEl.value = K.field;
  if (K.test) testEl.value = K.test;
  langEl.value = K.score || '';

  function saveK() {
    K.field = fieldEl.value; K.test = testEl.value; K.score = langEl.value;
    try { localStorage.setItem('kosha', JSON.stringify(K)); } catch (e) {}
  }

  /* 위 '내 자격증' 패널에서 보유(1)로 켠 종목을 알아본다.
     공고문은 등급을 행으로 나누고 종목명만 적어서, '종목명+등급' 이 곧 자격증 이름이 된다.
     (예: 기사 행의 '산업안전' = 산업안전기사) */
  function held(name, grade) {
    if (typeof S === 'undefined') return false;
    return S[name + grade] === 1;
  }

  function jobRows() { return KOSHA.jobs[fieldEl.value] || []; }

  function drawJob() {
    var html = jobRows().map(function (g) {
      var chips = g.items.map(function (n) {
        var id = fieldEl.value + '|' + g.grade + '|' + n;
        var on = K.job && K.job[id] !== undefined ? K.job[id] : held(n, g.grade);
        if (!K.job) K.job = {};
        K.job[id] = on ? 1 : 0;
        return '<button class="kc kj' + (on ? ' have' : '') + '" data-id="' + esc(id) +
               '" data-s="' + g.score + '">' + esc(n) + '</button>';
      }).join('');
      return '<div class="krow"><span class="kgrade">' + esc(g.grade) + ' ' +
             g.score + '점</span>' + chips + '</div>';
    }).join('');
    host.innerHTML = html;
  }

  function convert() {
    var v = String(langEl.value || '').trim();
    var t = testEl.value;
    if (!v) return null;
    if (t === 'TOEIC-S') {
      var m = KOSHA.conv.toeics[v.toUpperCase()];
      return m === undefined ? null : m;
    }
    var n = parseInt(v.replace(/[^0-9]/g, ''), 10);
    if (isNaN(n)) return null;
    if (t === 'TOEIC') return n;
    var tbl = { 'G-TELP(Level2)': 'gtelp', 'New TEPS': 'teps',
                'TOEFL(iBT)': 'toefl', 'FLEX(듣기/읽기)': 'flex' }[t];
    var map = KOSHA.conv[tbl] || {};
    /* 표에 없는 값은 그 아래에서 가장 가까운 칸으로 내려 읽는다(보수적으로) */
    var best = null;
    Object.keys(map).forEach(function (kk) {
      var key = parseInt(kk, 10);
      if (key <= n && (best === null || key > best)) best = key;
    });
    return best === null ? null : map[best];
  }

  function calc() {
    var job = 0;
    jobRows().forEach(function (g) {
      g.items.forEach(function (n) {
        if (K.job[fieldEl.value + '|' + g.grade + '|' + n]) job += g.score;
      });
    });
    job = Math.min(job, 50);

    var toeic = convert(), lang = 0;
    if (toeic !== null) lang = Math.min(25, Math.round(toeic / 800 * 25 * 100) / 100);

    var office = 0;
    Object.keys(K.office).forEach(function (n) { office += K.office[n] || 0; });
    office = Math.min(office, 20);

    var hist = 0;
    if (K.hist) {
      KOSHA.hist.forEach(function (h) { if (h.name === K.hist) hist = h.score; });
    }
    return { job: job, lang: lang, office: office, hist: hist, toeic: toeic,
             total: Math.round((job + lang + office + hist) * 100) / 100 };
  }

  function fmt(x) { return (Math.round(x * 100) / 100).toString(); }

  function paintK() {
    var r = calc();
    document.getElementById('kjobv').textContent = fmt(r.job) + ' / 50';
    document.getElementById('klangv').textContent = fmt(r.lang) + ' / 25';
    document.getElementById('kofficev').textContent = fmt(r.office) + ' / 20';
    document.getElementById('khistv').textContent = fmt(r.hist) + ' / 5';
    document.getElementById('ktotal').innerHTML = fmt(r.total) + '<small> / 100점</small>';
    document.getElementById('kseg').innerHTML =
      '직무 <b>' + fmt(r.job) + '</b> · 어학 <b>' + fmt(r.lang) + '</b> · 사무 <b>' +
      fmt(r.office) + '</b> · 한국사 <b>' + fmt(r.hist) + '</b>';
    var conv = document.getElementById('kconv');
    if (r.toeic === null) {
      conv.textContent = '성적이 없으면 비워 두세요';
      conv.className = 'kn';
    } else if (r.toeic >= 800) {
      conv.textContent = 'TOEIC ' + r.toeic + ' 환산 — 만점입니다. 더 올려도 25점입니다';
      conv.className = 'kn kok';
    } else {
      conv.textContent = 'TOEIC ' + r.toeic + ' 환산 — 800이면 만점(+' +
                         fmt(25 - r.lang) + '점 남음)';
      conv.className = 'kn kwarn';
    }
    var sum = document.getElementById('ksum');
    if (sum) sum.innerHTML = '<b>' + fmt(r.total) + '점</b> / 100 · ' + esc(fieldEl.value);
    var bv = document.getElementById('kbtnv');
    if (bv) bv.textContent = fmt(r.total);
    var bar = document.getElementById('kbari');
    if (bar) bar.style.width = Math.min(100, r.total) + '%';
    saveK();
  }

  host.addEventListener('click', function (e) {
    var b = e.target.closest('.kj');
    if (!b) return;
    var id = b.getAttribute('data-id');
    K.job[id] = K.job[id] ? 0 : 1;
    b.classList.toggle('have', !!K.job[id]);
    paintK();
  });

  document.querySelectorAll('.ko').forEach(function (b) {
    var kind = b.getAttribute('data-k'), n = b.getAttribute('data-n');
    var s = parseInt(b.getAttribute('data-s'), 10);
    if (kind === 'office' && K.office[n]) b.classList.add('have');
    if (kind === 'hist' && K.hist === n) b.classList.add('have');
    b.addEventListener('click', function () {
      if (kind === 'office') {
        if (K.office[n]) delete K.office[n]; else K.office[n] = s;
        b.classList.toggle('have', !!K.office[n]);
      } else {
        K.hist = (K.hist === n) ? null : n;
        document.querySelectorAll('.ko[data-k="hist"]').forEach(function (x) {
          x.classList.toggle('have', x.getAttribute('data-n') === K.hist);
        });
      }
      paintK();
    });
  });

  fieldEl.addEventListener('change', function () { drawJob(); paintK(); });
  testEl.addEventListener('change', paintK);
  langEl.addEventListener('input', paintK);
  document.getElementById('kreset').addEventListener('click', function () {
    K = { office: {}, hist: null, test: testEl.value, score: '',
          field: fieldEl.value, job: {} };
    langEl.value = '';
    document.querySelectorAll('.ko').forEach(function (x) { x.classList.remove('have'); });
    drawJob(); paintK();
  });

  /* 계산기는 접어 두고, 상단 머리띠의 작은 '계산기' 버튼으로 연다.
     매일 보는 건 공고 목록이지 계산기가 아니라서 자리를 차지하면 안 된다. */
  var box = document.getElementById('kpanel');
  var btn = document.getElementById('kbtn');
  if (btn && box) {
    /* 브라우저는 details 의 열림 상태를 세션에 기억했다가 되살린다. 그 복원이
       이 스크립트보다 늦게(load 이후) 돌아서, 한 번만 닫아 놓으면 도로 열린다.
       그래서 사용자가 직접 누르기 전까지는 몇 번이고 닫는다. */
    var touched = false;
    function forceClosed() { if (!touched) box.open = false; }
    forceClosed();
    setTimeout(forceClosed, 0);
    window.addEventListener('load', forceClosed);
    window.addEventListener('pageshow', forceClosed);

    btn.addEventListener('click', function () {
      touched = true;
      box.open = !box.open;
      if (box.open) box.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
    box.addEventListener('toggle', function () {
      btn.setAttribute('aria-expanded', box.open ? 'true' : 'false');
      btn.classList.toggle('on', box.open);
    });
  }

  drawJob();
  paintK();
})();
"""
