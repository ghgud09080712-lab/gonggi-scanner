# -*- coding: utf-8 -*-
"""
공통 틀로 돌리는 서류전형 계산기들 (가스안전공사 · 남부발전 · 한국전력기술 …).

KOSHA·한전·가스공사는 규칙이 제각각이라 모듈을 하나씩 두었지만, 그 뒤로 본 공고문들은
거의 같은 모양이었다:
    서류 = 외국어(환산표 구간 점수, 또는 TOEIC ÷ 기준점)
         + 공통 자격(분야별 최고 1개)
         + 직무 자격(묶음별 최고 1개, 상위 N개)
그래서 배점표는 `extra_calc.json` 에만 두고 화면과 계산은 이 모듈 하나가 맡는다.
새 기관은 JSON 에 항목을 추가하면 끝이다.

직무 자격의 '묶음(g)' 규칙 하나로 세 공고를 다 표현한다.
    가스안전 : 능력구분(안전관리·화학공학 …)이 묶음 — 묶음마다 1개, 최대 2묶음
    남부발전 : 종목(산업안전·화공 …)이 묶음     — 기사·산업기사 중 상위 1개, 최대 3개
    한전기술 : 자격증 하나하나가 묶음           — 개당 10점, 최대 2개

CSS 클래스·DOM id 는 전부 q 접두어다. (.c 는 목록의 paintChips() 가, k·x·g 는 다른 계산기가 쓴다)
CSS·APP 는 raw 문자열이라 JS 정규식의 백슬래시를 그대로 적으면 된다.
"""

import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "extra_calc.json")


def load():
    """계산기 목록. 파일이 없거나 깨졌으면 빈 목록 — 나머지 화면은 그대로 돈다."""
    try:
        with open(DATA, encoding="utf-8") as f:
            return json.load(f).get("calcs") or []
    except Exception:
        return []


def panels(calcs):
    """접힌 details 껍데기만 만든다. 안쪽 폼은 스크립트가 QCALC 로 그린다."""
    out = []
    for c in calcs:
        i = html.escape(c["id"])
        out.append(
            '<details class="srch qpanel" id="qp-%s"><summary class="srch-hd">'
            '<span class="st">%s</span>'
            '<span class="psum" id="qs-%s"></span>'
            '<span class="qbar"><i id="qb-%s"></i></span>'
            '<span class="pmore">접기 ▲</span></summary>'
            '<div class="qbody" data-q="%s"></div></details>'
            % (i, html.escape(c["panel_title"]), i, i, i))
    return "".join(out)


CSS = r"""
/* ---- 공통 틀 서류전형 계산기 ---- */
/* 닫혀 있을 때는 막대조차 남기지 않는다. 머리띠의 계산기 메뉴가 유일한 입구다. */
.qpanel:not([open]){display:none}
.qbar{flex:1;min-width:90px;max-width:200px;height:6px;background:var(--line2);
border-radius:3px;overflow:hidden}
.qbar i{display:block;height:100%;background:var(--pri);width:0}
.form td.qcell{padding:9px 14px}
.qline{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:5px}
.qv{font-size:13px;font-weight:700;color:var(--pri2);white-space:nowrap}
.qn{font-size:12px;color:var(--ink3)}
a.qn{color:var(--pri2)}
.qrow{display:flex;gap:8px;align-items:baseline;margin:2px 0}
.qrow.plain{flex-wrap:wrap;align-items:center}
.qgrade{font-size:12px;color:var(--ink3);white-space:nowrap;flex:0 0 124px}
/* 칩이 줄을 넘길 때 라벨 칸 아래로 흘러내리지 않게 따로 감싼다 */
.qchips{flex:1;min-width:0;display:flex;flex-wrap:wrap;gap:0 14px}
.qc{font:inherit;font-size:13px;border:0;background:none;padding:1px 0;
color:var(--ink2);cursor:pointer;white-space:nowrap;line-height:1.9}
.qc::before{content:"□";color:var(--line);margin-right:5px}
.qc small{font-size:11px;color:var(--ink3);font-weight:400;margin-left:3px}
.qc:hover{color:var(--pri2)}
.qc:focus-visible{outline:2px solid var(--pri);outline-offset:2px}
.qc.have{color:var(--pri2);font-weight:700}
.qc.have::before{content:"■";color:var(--pri)}
.qc.dim{color:var(--ink3);opacity:.5;cursor:default}
.qc.cut{color:var(--ink3);font-weight:400;text-decoration:line-through}
.qc.cut::before{content:"■";color:var(--line)}
.qf{font:inherit;font-size:13px;padding:4px 8px;border:1px solid var(--line);
border-radius:4px;background:#fff;color:var(--ink)}
.qf:focus-visible{outline:2px solid var(--pri);outline-offset:1px}
button.qf{cursor:pointer}
.qlang{width:110px}
.qbad{color:var(--red);font-weight:700}
.qwarn{color:var(--orange);font-weight:700}
.qok{color:var(--green);font-weight:700}
.qnote{font-size:12px;color:var(--ink3);margin:7px 0 0}
.qres{display:flex;flex-wrap:wrap;gap:10px 20px;align-items:center;
padding:13px 16px;background:var(--tint);border-top:1px solid var(--line2)}
.qres .big{font-size:22px;font-weight:900;color:var(--pri2);letter-spacing:-.02em}
.qres .big small{font-size:13px;font-weight:400;color:var(--ink3);margin-left:2px}
.qres .seg{font-size:13px;color:var(--ink2)}
.qres .seg b{color:var(--pri2)}
.qnotes{padding:9px 16px 12px;background:var(--soft);border-top:1px solid var(--line2)}
.qnotes p{font-size:12px;color:var(--ink3);margin:3px 0}
@media (max-width:640px){.qgrade{flex-basis:78px;white-space:normal}}
"""


APP = r"""
/* ================= 공통 틀 서류전형 계산기 ================= */
(function () {
  if (typeof QCALC === 'undefined' || !QCALC || !QCALC.length) return;

  function r2(v) { return Math.round(v * 100) / 100; }
  function fmt(v) { return String(r2(v)); }

  /* 「내 자격증」에서 보유(1)로 켠 이름이 하나라도 있으면 true */
  function held(names) {
    if (typeof S === 'undefined' || !names) return false;
    for (var i = 0; i < names.length; i++) if (S[names[i]] === 1) return true;
    return false;
  }
  function flat(rows) {
    var out = [];
    (rows || []).forEach(function (r) { out = out.concat(r.chips); });
    return out;
  }

  /* 성적 한 칸을 읽는다.
     map   : 등급 → 값 (OPIc 'IH' 등)
     alias : 등급 → 숫자로 바꾼 뒤 표를 탄다 (TOEIC-S 'AL' → 160)
     table : [하한, 값] 을 높은 순으로. 첫 번째로 넘는 칸의 값. 다 못 넘으면 0
     표가 없으면 입력 숫자 그대로(TOEIC) */
  function langVal(T, raw) {
    raw = String(raw || '').trim();
    if (!raw) return null;
    var up = raw.toUpperCase().replace(/\s+/g, '');
    if (T.map && T.map[up] !== undefined) return T.map[up];
    var n = (T.alias && T.alias[up] !== undefined) ? T.alias[up]
                                                   : parseFloat(raw.replace(/[^0-9.]/g, ''));
    if (isNaN(n)) return null;
    if (!T.table) return n;
    for (var i = 0; i < T.table.length; i++) if (n >= T.table[i][0]) return T.table[i][1];
    return 0;
  }

  function opt(v) { return '<option value="' + esc(v) + '">' + esc(v) + '</option>'; }

  function skeleton(C) {
    var notes = (C.notes || []).map(function (n) { return '<p>※ ' + esc(n) + '</p>'; }).join('');
    return '<table class="form"><tbody>' +
      '<tr><th scope="row">공고</th><td class="qcell"><div class="qline">' +
        '<span class="qv">' + esc(C.name) + '</span>' +
        '<span class="qn">' + esc(C.title) + ' · 접수마감 ' + esc(C.deadline) + '</span>' +
        (C.sn ? '<a class="qn" href="https://job.alio.go.kr/recruitview.do?idx=' + C.sn +
                '" target="_blank" rel="noopener">공고 원문 ↗</a>' : '') +
      '</div></td></tr>' +
      '<tr><th scope="row">모집분야</th><td class="qcell"><div class="qrow plain">' +
        '<select class="qf" data-k="field">' + C.fields.map(function (f) { return opt(f.name); }).join('') +
        '</select><span class="qn" data-k="finfo"></span></div></td></tr>' +
      '<tr><th scope="row">외국어</th><td class="qcell">' +
        '<div class="qline"><span class="qv" data-k="langv"></span>' +
        '<span class="qn">' + esc(C.lang.formula) + '</span></div>' +
        '<div class="qrow plain"><select class="qf" data-k="test">' +
        C.lang.tests.map(function (t) { return opt(t.name); }).join('') + '</select>' +
        '<input class="qf qlang" data-k="score" type="text" autocomplete="off">' +
        '<span class="qn" data-k="conv"></span></div>' +
        (C.lang.note ? '<p class="qnote">' + esc(C.lang.note) + '</p>' : '') +
      '</td></tr>' +
      '<tr><th scope="row">' + esc(C.labels.com) + '</th><td class="qcell">' +
        '<div class="qline"><span class="qv" data-k="comv"></span>' +
        '<span class="qn">' + esc(C.common.rule) + '</span></div><div data-k="com"></div></td></tr>' +
      '<tr><th scope="row">' + esc(C.labels.job) + '</th><td class="qcell">' +
        '<div class="qline"><span class="qv" data-k="jobv"></span>' +
        '<span class="qn">' + esc(C.job_rule) + '</span></div><div data-k="job"></div>' +
        '<p class="qnote">위 <b>내 자격증</b>에서 ■ 로 표시한 종목은 자동으로 켜집니다. ' +
        '인정되지 않는 항목에는 <s>취소선</s>이 표시됩니다.</p></td></tr>' +
      '<tr data-k="sprow"><th scope="row">서류 면제</th><td class="qcell">' +
        '<div data-k="sp"></div></td></tr>' +
      '</tbody></table>' +
      '<div class="qres"><span class="big" data-k="total"></span>' +
        '<span class="seg" data-k="seg"></span><span class="qn qbad" data-k="floor"></span>' +
        '<span class="spacer"></span>' +
        '<button class="qf" type="button" data-k="reset">전체해제</button></div>' +
      (notes ? '<div class="qnotes">' + notes + '</div>' : '');
  }

  QCALC.forEach(mount);

  function mount(C) {
    var host = document.querySelector('.qbody[data-q="' + C.id + '"]');
    if (!host) return;
    var KEY = 'qcalc-' + C.id;
    var st = { field: C['default'], test: C.lang.tests[0].name, score: '', on: {} };
    try {
      var raw = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (raw) { st = Object.assign(st, raw); st.on = st.on || {}; }
    } catch (e) {}
    if (!C.fields.some(function (f) { return f.name === st.field; })) st.field = C['default'];
    if (!C.lang.tests.some(function (t) { return t.name === st.test; })) st.test = C.lang.tests[0].name;

    host.innerHTML = skeleton(C);
    function q(k) { return host.querySelector('[data-k="' + k + '"]'); }
    var fieldEl = q('field'), testEl = q('test'), langEl = q('score');
    fieldEl.value = st.field;
    testEl.value = st.test;
    langEl.value = st.score || '';

    function field() {
      var out = C.fields[0];
      C.fields.forEach(function (f) { if (f.name === fieldEl.value) out = f; });
      return out;
    }
    function test() {
      var out = C.lang.tests[0];
      C.lang.tests.forEach(function (t) { if (t.name === testEl.value) out = t; });
      return out;
    }
    function jobTable(f) { return f.jt ? C.jobs[f.jt] : null; }

    /* 처음 보는 칩은 「내 자격증」 보유 여부로 한 번만 켠다. 이후엔 손으로 켠 값 유지 */
    function isOn(c) {
      if (st.on[c.id] === undefined) st.on[c.id] = held(c.seed) ? 1 : 0;
      return !!st.on[c.id];
    }
    function allowed(c, f) {
      if (c.only && c.only.indexOf(f.name) < 0) return false;
      if (f.off && f.off.indexOf(c.g) >= 0) return false;
      return true;
    }
    /* 묶음마다 켜진 것 중 가장 높은 점수 하나 */
    function bestOf(chips, f) {
      var b = {};
      chips.forEach(function (c) {
        if (!isOn(c) || !allowed(c, f)) return;
        if (!b[c.g] || c.s > b[c.g].s) b[c.g] = { s: c.s, id: c.id };
      });
      return Object.keys(b).map(function (k) { return b[k]; });
    }

    function chipHTML(c, f, tag) {
      var ok = allowed(c, f);
      return '<button type="button" class="qc' + (ok && isOn(c) ? ' have' : '') +
             (ok ? '' : ' dim') + '" data-id="' + esc(c.id) + '"' + (ok ? '' : ' disabled') + '>' +
             esc(c.n) + (tag ? '<small>' + c.s + '</small>' : '') + '</button>';
    }
    function rowsHTML(rows, f) {
      return rows.map(function (r) {
        return '<div class="qrow"><span class="qgrade">' + esc(r.label) + '</span>' +
               '<span class="qchips">' + r.chips.map(function (c) { return chipHTML(c, f, r.tag); }).join('') +
               '</span></div>';
      }).join('');
    }

    function draw() {
      var f = field(), jt = jobTable(f);
      q('com').innerHTML = rowsHTML(C.common.rows, f);
      q('job').innerHTML = jt ? rowsHTML(jt.rows, f)
        : '<p class="qnote">' + esc(C.no_job || '이 분야는 직무 자격 점수가 없습니다.') + '</p>';
      var sp = jt && jt.special;
      q('sprow').hidden = !(sp && sp.length);
      q('sp').innerHTML = (sp || []).map(function (s) {
        return '<div class="qrow"><span class="qgrade">' + esc(s[0]) + '</span>' +
               '<span class="qchips qn">' + esc(s[1]) + '</span></div>';
      }).join('');
    }

    function calc() {
      var f = field(), jt = jobTable(f), T = test();
      var v = langVal(T, langEl.value), lang = 0;
      if (v !== null) {
        lang = C.lang.mode === 'linear' ? Math.min(v, C.lang.full) / C.lang.full * f.lang_max
                                        : Math.min(v, f.lang_max);
      }
      lang = r2(lang);

      var comKeep = {}, com = 0;
      bestOf(flat(C.common.rows), f).forEach(function (o) { comKeep[o.id] = 1; com += o.s; });
      com = Math.min(com, f.com_cap);

      var jobKeep = {}, job = 0;
      if (jt) {
        var arr = bestOf(flat(jt.rows), f).sort(function (a, b) { return b.s - a.s; });
        arr.slice(0, C.job_max).forEach(function (o) { jobKeep[o.id] = 1; job += o.s; });
        job = Math.min(job, f.job_cap);
      }
      var qual = com + job;
      if (f.qual_cap) qual = Math.min(qual, f.qual_cap);
      var max = f.lang_max + Math.min(f.qual_cap || 1e9, f.com_cap + (jt ? f.job_cap : 0));
      return { f: f, jt: jt, T: T, v: v, lang: lang, com: com, job: job, qual: qual,
               comKeep: comKeep, jobKeep: jobKeep, max: max, total: r2(lang + qual) };
    }

    function paint() {
      var r = calc(), f = r.f, L = C.lang;
      q('langv').textContent = fmt(r.lang) + ' / ' + f.lang_max;
      q('comv').textContent = fmt(r.com) + ' / ' + f.com_cap;
      q('jobv').textContent = r.jt ? fmt(r.job) + ' / ' + f.job_cap : '해당 없음';
      q('total').innerHTML = fmt(r.total) + '<small> / ' + r.max + '점</small>';
      q('seg').innerHTML = '외국어 <b>' + fmt(r.lang) + '</b> · 공통 <b>' + fmt(r.com) +
        '</b> · 직무 <b>' + fmt(r.job) + '</b>' +
        (f.qual_cap && r.com + r.job > f.qual_cap
          ? ' <span class="qn">(자격 합계 ' + f.qual_cap + '점 상한 적용)</span>' : '');
      q('finfo').textContent = [f.kind, f.ratio ? '서류 ' + f.ratio : '', f.note, '만점 ' + r.max + '점']
        .filter(Boolean).join(' · ');

      host.querySelectorAll('.qc').forEach(function (b) {
        var id = b.getAttribute('data-id');
        b.classList.toggle('cut', !b.disabled && !!st.on[id] && !r.comKeep[id] && !r.jobKeep[id]);
      });

      var conv = q('conv'), typed = String(langEl.value || '').trim();
      if (r.v === null) {
        conv.textContent = typed ? '인정되지 않는 값입니다' : '성적이 없으면 비워 두세요';
        conv.className = 'qn' + (typed ? ' qbad' : '');
      } else if (L.mode === 'linear') {
        var head = r.T.name === 'TOEIC' ? 'TOEIC ' + fmt(r.v) : 'TOEIC ' + fmt(r.v) + ' 환산';
        if (L.min && r.v < L.min) {
          conv.textContent = head + ' — 지원자격(' + L.min + ') 미달';
          conv.className = 'qn qbad';
        } else if (r.v >= L.full) {
          conv.textContent = head + ' — 만점';
          conv.className = 'qn qok';
        } else {
          conv.textContent = head + ' — ' + L.full + '이면 만점(+' + fmt(f.lang_max - r.lang) + '점 남음)';
          conv.className = 'qn qwarn';
        }
      } else if (r.v <= 0) {
        conv.textContent = '최저 구간 미만 — 0점';
        conv.className = 'qn qbad';
      } else {
        conv.textContent = fmt(r.lang) + '점 구간' +
          (r.lang >= f.lang_max ? ' — 만점' : ' — 만점까지 +' + fmt(f.lang_max - r.lang));
        conv.className = 'qn ' + (r.lang >= f.lang_max ? 'qok' : 'qwarn');
      }

      q('floor').textContent = C.floor && r.total < r.max * C.floor / 100
        ? '만점의 ' + C.floor + '% 미만 — 선발 제외 구간' : '';

      var sum = document.getElementById('qs-' + C.id);
      if (sum) sum.innerHTML = '<b>' + fmt(r.total) + '점</b> / ' + r.max + ' · ' + esc(f.name);
      var mv = document.getElementById('qv-' + C.id);
      if (mv) mv.textContent = fmt(r.total);
      var bar = document.getElementById('qb-' + C.id);
      if (bar) bar.style.width = Math.min(100, r.total / r.max * 100) + '%';

      st.field = fieldEl.value; st.test = testEl.value; st.score = langEl.value;
      try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {}
    }

    function hint() { langEl.placeholder = test().hint || '점수'; }

    host.addEventListener('click', function (e) {
      var b = e.target.closest('.qc');
      if (b && !b.disabled) {
        var id = b.getAttribute('data-id');
        st.on[id] = st.on[id] ? 0 : 1;
        b.classList.toggle('have', !!st.on[id]);
        paint();
        return;
      }
      if (e.target.closest('[data-k="reset"]')) {
        /* 0 으로 박아 둬야 다시 그릴 때 「내 자격증」 시딩이 되살아나지 않는다 */
        var all = flat(C.common.rows);
        Object.keys(C.jobs).forEach(function (k) { all = all.concat(flat(C.jobs[k].rows)); });
        all.forEach(function (c) { st.on[c.id] = 0; });
        langEl.value = '';
        draw(); paint();
      }
    });
    fieldEl.addEventListener('change', function () { draw(); paint(); });
    testEl.addEventListener('change', function () { hint(); paint(); });
    langEl.addEventListener('input', paint);

    hint();
    draw();
    paint();
  }
})();
"""
