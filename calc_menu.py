# -*- coding: utf-8 -*-
"""
머리띠의 '계산기 ▾' 버튼 하나와 그 아래로 펼쳐지는 기관 목록.

계산기가 KOSHA·한전·가스공사 셋일 때는 버튼을 나란히 뒀는데, 늘어나니 머리띠가
난잡해졌다. 버튼은 하나만 두고 누르면 목록이 내려와서 고르게 한다.

이 모듈이 계산기 패널(details)의 열고 닫기를 전부 맡는다.
  - 목록에서 고른 패널만 열고 나머지는 닫는다(둘 이상 펼치면 공고 목록이 화면 밖으로 밀린다)
  - 브라우저는 details 의 열림 상태를 세션에 기억했다가 load 이후에 되살린다. 그래서
    사용자가 목록에서 하나를 고르기 전까지는 몇 번이고 닫는다
각 패널 모듈은 자기 점수를 목록 줄의 <b id=...> 에 써 넣기만 한다.
"""

import html

CSS = r"""
/* ---- 머리띠 계산기 메뉴 ---- */
.cmenu{position:relative;margin-left:12px}
.cbtn{font:inherit;font-size:12.5px;line-height:1;padding:7px 13px;cursor:pointer;
border:1px solid var(--pri3);border-radius:24px;background:#fff;color:var(--pri2);
white-space:nowrap;display:inline-flex;align-items:center;gap:6px}
.cbtn:hover{background:var(--tint)}
.cbtn:focus-visible{outline:2px solid var(--pri);outline-offset:2px}
.cbtn.on,.cbtn.act{background:var(--pri);border-color:var(--pri);color:#fff}
.cnow:not(:empty){font-weight:700}
.cnow:not(:empty)::before{content:"· ";font-weight:400}
.car{font-size:10px;transition:transform .15s}
.cbtn.on .car{transform:rotate(180deg)}
.cdrop{position:absolute;right:0;top:calc(100% + 8px);z-index:60;width:470px;
max-width:calc(100vw - 32px);background:#fff;border:1px solid var(--pri3);
border-radius:10px;box-shadow:0 10px 28px rgba(50,50,120,.16);overflow:hidden}
.cdh{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;background:var(--pri);
color:#fff;padding:10px 14px;font-size:13px;font-weight:700}
.cdh span{font-size:11.5px;font-weight:400;opacity:.88}
.crow{display:flex;align-items:center;gap:12px;width:100%;padding:10px 14px;margin:0;
border:0;border-top:1px solid var(--line2);background:#fff;font:inherit;text-align:left;
cursor:pointer;color:var(--ink)}
.cdh + .crow{border-top:0}
.crow:nth-of-type(even){background:var(--zebra)}
.crow:hover,.crow:focus-visible{background:var(--tint);outline:0}
.crow.on{box-shadow:inset 4px 0 0 var(--pri)}
.cn{flex:0 0 72px;font-size:13.5px;font-weight:700;color:var(--pri2)}
.cx{flex:1;min-width:0;display:flex;flex-direction:column;line-height:1.4}
.ct{font-size:13px;color:var(--ink)}
.cs{font-size:11.5px;color:var(--ink3)}
.cd{flex:0 0 58px;text-align:center;font-size:12px;color:var(--ink2);white-space:nowrap}
.cd.hot{color:var(--red);font-weight:700}
.cd.past{color:var(--ink3)}
.cv{flex:0 0 56px;text-align:right;font-size:12px;color:var(--ink3);white-space:nowrap}
.cv b{font-size:15px;color:var(--pri2);margin-right:1px}
.cdf{padding:8px 14px;font-size:11.5px;color:var(--ink3);background:var(--soft);
border-top:1px solid var(--line2)}
@media (max-width:520px){.cn{flex-basis:58px}.cd{flex-basis:46px}.cs{display:none}}
"""


def html_(entries, today):
    """entries: [{panel, val, short, name, desc, deadline}]
    접수 중인 것을 마감 가까운 순으로 위에, 마감된 것은 아래로 보낸다."""
    if not entries:
        return ""

    def key(e):
        dl = e.get("deadline") or ""
        return (not dl or dl < today, dl)

    rows = "".join(
        '<button class="crow" type="button" data-panel="%s" data-dl="%s">'
        '<span class="cn">%s</span>'
        '<span class="cx"><span class="ct">%s</span><span class="cs">%s</span></span>'
        '<span class="cd"></span>'
        '<span class="cv"><b id="%s">–</b>점</span></button>'
        % (html.escape(e["panel"]), html.escape(e.get("deadline") or ""),
           html.escape(e["short"]), html.escape(e["name"]), html.escape(e["desc"]),
           html.escape(e["val"]))
        for e in sorted(entries, key=key))
    return (
        '<div class="cmenu">'
        '<button class="cbtn" id="cbtn" type="button" aria-haspopup="true" '
        'aria-expanded="false" aria-controls="cdrop">계산기<span class="cnow" id="cnow"></span>'
        '<span class="car" aria-hidden="true">▾</span></button>'
        '<div class="cdrop" id="cdrop" hidden>'
        '<div class="cdh">서류전형 점수 계산기<span>기관을 누르면 아래에 펼쳐집니다</span></div>'
        + rows +
        '<div class="cdf">※ 입력한 성적·자격증은 이 브라우저에만 저장됩니다</div>'
        "</div></div>")


APP = r"""
/* ================= 머리띠 계산기 메뉴 ================= */
(function () {
  var btn = document.getElementById('cbtn'), drop = document.getElementById('cdrop');
  if (!btn || !drop) return;
  var rows = [].slice.call(drop.querySelectorAll('.crow'));
  var boxes = rows.map(function (r) { return document.getElementById(r.getAttribute('data-panel')); });
  var nowEl = document.getElementById('cnow');

  /* D-day 는 파일을 만든 날이 아니라 페이지를 연 날 기준으로 센다 */
  var today = new Date(); today.setHours(0, 0, 0, 0);
  rows.forEach(function (r) {
    var dl = r.getAttribute('data-dl'), cd = r.querySelector('.cd');
    if (!dl) return;
    var p = dl.split('-'), d = new Date(+p[0], +p[1] - 1, +p[2]);
    var n = Math.round((d - today) / 864e5);
    cd.textContent = n < 0 ? '접수마감' : n === 0 ? '오늘마감' : 'D-' + n;
    cd.classList.toggle('hot', n >= 0 && n <= 3);
    cd.classList.toggle('past', n < 0);
  });

  var touched = false;
  function closeAll(except) {
    boxes.forEach(function (b) { if (b && b !== except) b.open = false; });
  }
  function forceClosed() { if (!touched) closeAll(null); }
  forceClosed();
  setTimeout(forceClosed, 0);
  window.addEventListener('load', forceClosed);
  window.addEventListener('pageshow', forceClosed);

  function setDrop(open) {
    drop.hidden = !open;
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    btn.classList.toggle('on', open);
  }

  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    setDrop(drop.hidden);
    if (!drop.hidden) (drop.querySelector('.crow.on') || rows[0]).focus();
  });

  rows.forEach(function (r, i) {
    r.addEventListener('click', function () {
      var box = boxes[i];
      if (!box) return;
      touched = true;
      var open = !box.open;
      closeAll(box);
      box.open = open;
      setDrop(false);
      if (open) box.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
  });

  /* 패널 제목줄(접기 ▲)로 닫아도 메뉴 표시가 따라오게 */
  function sync() {
    var cur = null;
    boxes.forEach(function (b, i) {
      var on = !!(b && b.open);
      rows[i].classList.toggle('on', on);
      if (on) cur = rows[i];
    });
    nowEl.textContent = cur ? cur.querySelector('.cn').textContent : '';
    btn.classList.toggle('act', !!cur);
  }
  boxes.forEach(function (b) { if (b) b.addEventListener('toggle', sync); });

  document.addEventListener('click', function (e) {
    if (!drop.hidden && !drop.contains(e.target)) setDrop(false);
  });
  document.addEventListener('keydown', function (e) {
    if (drop.hidden) return;
    if (e.key === 'Escape') { setDrop(false); btn.focus(); return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      var i = rows.indexOf(document.activeElement);
      i = e.key === 'ArrowDown' ? (i + 1) % rows.length : (i <= 0 ? rows.length - 1 : i - 1);
      rows[i].focus();
    }
  });
  sync();
})();
"""
