# -*- coding: utf-8 -*-
"""
공공기관 채용 스캐너
잡알리오 오픈API(공공데이터포털 15125273)에서 채용공고를 받아
관심 기관·직무만 걸러 오프라인 HTML로 만든다.

사용법:  python scan.py            평소 실행
         python scan.py --dump     원본 JSON 첫 건을 뜯어보기(필드명 확인용)
         python scan.py --all      필터 없이 전부 출력
         python scan.py --salary   보수 정보(알리오 경영공시)를 강제로 다시 받기
         python scan.py --compete  과거 경쟁률 표본을 더 모으기

서버(클라우드타입)에서는 app.py 가 build_html() 을 불러 쓴다.
인증키는 config.json 보다 SERVICE_KEY 환경변수가 우선한다.
"""

import json
import os
import sys
import re
import time
import datetime as dt
import urllib.parse
import urllib.request

import certs
import salary
import compete
import detail
import kosha_panel
import kepco_panel
import kogas_panel

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "https://apis.data.go.kr/1051000/recruitment/list"
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
SAMPLE = os.path.join(HERE, "config.sample.json")
SEEN = os.path.join(HERE, "seen.json")
OUT = os.path.join(HERE, "채용공고.html")

# 서버(클라우드타입)에서는 물어보지도, 브라우저를 띄우지도 않는다.
SERVER = os.environ.get("GONGGI_SERVER") == "1"

# 컨테이너 시계는 UTC 라 그냥 today() 를 쓰면 D-day 가 하루 밀린다.
KST = dt.timezone(dt.timedelta(hours=9))


def now_kst():
    return dt.datetime.now(KST)


TODAY = now_kst().date()


# ---------------------------------------------------------------- config

def service_key():
    """인증키는 환경변수가 먼저다. 그래야 깃허브에 키를 안 올리고 배포할 수 있다."""
    key = (os.environ.get("SERVICE_KEY") or "").strip()
    if key:
        return key
    path = CONFIG if os.path.exists(CONFIG) else SAMPLE
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                key = (json.load(f).get("serviceKey") or "").strip()
        except Exception:
            key = ""
    return "" if key.startswith("여기에") else key


def load_config():
    # 배포본에는 config.json 대신 config.sample.json 만 들어간다(키 제외).
    path = CONFIG if os.path.exists(CONFIG) else SAMPLE
    if not os.path.exists(path):
        die("config.json 이 없습니다. 같은 폴더에 두세요.")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["serviceKey"] = service_key()
    if not cfg["serviceKey"]:
        die(
            "인증키가 없습니다.\n"
            "  로컬  : config.json 의 serviceKey 에 넣으세요.\n"
            "  서버  : SERVICE_KEY 환경변수에 넣으세요.\n"
            "  키 받기: data.go.kr → '재정경제부_공공기관 채용정보 조회서비스' 활용신청(자동승인)\n"
            "          → 마이페이지 → 개발계정 → 일반 인증키(Decoding)"
        )
    return cfg


def die(msg):
    print("\n[중단] " + msg + "\n")
    if SERVER:
        raise RuntimeError(msg.splitlines()[0])
    input("엔터를 누르면 닫힙니다...")
    sys.exit(1)


# ---------------------------------------------------------------- fetch

def call(key, page, rows=100, ongoing=True):
    # data.go.kr 은 깃허브 러너에서 자주 타임아웃나고, 그러면 빌드가 통째로
    # 실패해 그날 페이지가 갱신되지 않는다. 같은 데이터를 주는 알리오 경로를
    # 먼저 쓰고 거기서 실패할 때만 원래 경로로 되돌아간다.
    if compete._alio_fail[0] < compete.ALIO_GIVEUP:
        try:
            d = compete._alio("list", {"pageNo": page, "numOfRows": rows,
                                       "ongoingYn": "Y" if ongoing else "A"})
            compete._alio_fail[0] = 0
            return d
        except Exception as e:
            compete._alio_note(e)

    p = {"serviceKey": key, "resultType": "json", "numOfRows": rows, "pageNo": page}
    if ongoing:
        # 문서에 없는 파라미터지만 실제로 동작한다.
        # 없이 부르면 마감된 공고까지 11만건이 잡혀 일일 한도(1,000회)를 태운다.
        p["ongoingYn"] = "Y"
    q = urllib.parse.urlencode(p, safe="")
    req = urllib.request.Request(BASE + "?" + q, headers={"User-Agent": "gonggi-scanner/1.0"})
    # 이 API 는 가끔 응답이 늦다. 특히 해외(깃허브 러너)에서 부를 때 그렇다.
    # 한 번 실패했다고 포기하면 그날 목록이 통째로 날아가므로 몇 번 다시 건다.
    raw = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                raw = r.read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as e:
            # 인증키 오류는 403으로 오는데 본문에 진짜 사유가 들어 있다.
            raw = e.read().decode("utf-8", "replace") if e.fp else ""
            if not raw.lstrip().startswith(("{", "[")):
                die("HTTP %s %s\n     %s" % (e.code, e.reason, raw[:300] or "(응답 본문 없음)"))
            break
        except urllib.error.URLError as e:
            if attempt == 3:
                die("네트워크에 연결할 수 없습니다: %s" % e.reason)
            print("  응답이 없어 다시 시도합니다 (%d/3)" % (attempt + 1))
            time.sleep(3 * (attempt + 1))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        die("API가 JSON이 아닌 응답을 보냈습니다. 앞부분:\n" + raw[:400])


def check_error(doc):
    """공공데이터포털 공통 오류 봉투를 사람이 읽을 수 있게 바꾼다."""
    env = doc.get("OpenAPI_ServiceResponse") if isinstance(doc, dict) else None
    if not env:
        return
    h = env.get("cmmMsgHeader", {})
    code = h.get("errMsg", "")
    hint = {
        "SERVICE_KEY_IS_NOT_REGISTERED_ERROR":
            "인증키가 등록되지 않았습니다. 활용신청 직후에는 반영에 몇 분~1시간 걸립니다.\n"
            "     Encoding 키가 아니라 Decoding 키를 넣었는지도 확인하세요.",
        "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR":
            "일일 호출 한도(개발계정 1,000건)를 넘었습니다. 내일 다시 실행하세요.",
        "SERVICE_ACCESS_DENIED_ERROR":
            "이 서비스에 대한 활용신청이 승인되지 않았습니다.",
    }.get(code, h.get("returnAuthMsg", code))
    die("API 오류: " + str(code) + "\n     " + str(hint))


def extract_items(doc):
    """응답 구조가 바뀌어도 레코드 배열을 찾아낸다."""
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for k in ("result", "items", "item", "data", "list"):
        v = doc.get(k)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
        if isinstance(v, dict):
            found = extract_items(v)
            if found:
                return found
    for v in doc.values():
        if isinstance(v, (dict, list)):
            found = extract_items(v)
            if found:
                return found
    return []


def total_count(doc):
    if isinstance(doc, dict):
        for k in ("totalCount", "totalcount", "total"):
            if k in doc:
                try:
                    return int(doc[k])
                except (TypeError, ValueError):
                    pass
        for v in doc.values():
            if isinstance(v, dict):
                n = total_count(v)
                if n:
                    return n
    return 0


def fetch_all(key, max_pages=40, ongoing=True):
    rows, page = [], 1
    total = None
    while page <= max_pages:
        doc = call(key, page, ongoing=ongoing)
        check_error(doc)
        if total is None:
            total = total_count(doc)
            print("  진행 중 공고 %s건" % (total or "?"))
            if total and total > max_pages * 100:
                print("  ! %d페이지까지만 받습니다(일일 호출 한도 보호)." % max_pages)
        items = extract_items(doc)
        if not items:
            break
        rows.extend(items)
        print("  %d페이지 … 누적 %d건" % (page, len(rows)))
        if len(items) < 100 or (total and len(rows) >= total):
            break
        page += 1
        time.sleep(0.2)
    return rows


# ---------------------------------------------------------------- fields

def pick(rec, *names):
    # 이 API는 빈 값을 ""가 아니라 "." 으로 내려준다.
    for n in names:
        v = rec.get(n)
        if v in (None, "", [], ".", "-"):
            continue
        if isinstance(v, str) and v.strip() in (".", "-", ""):
            continue
        return v
    return ""


def as_date(v):
    s = re.sub(r"[^0-9]", "", str(v or ""))
    if len(s) < 8:
        return None
    try:
        return dt.date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def norm(rec):
    end = as_date(pick(rec, "pbancEndYmd", "endYmd", "rceptEndYmd"))
    beg = as_date(pick(rec, "pbancBgngYmd", "bgngYmd", "rceptBgngYmd"))
    return {
        "sn": str(pick(rec, "recrutPblntSn", "pblntSn", "sn")),
        "inst": str(pick(rec, "instNm", "pblntInstNm", "insttNm")),
        "title": str(pick(rec, "recrutPbancTtl", "pbancTtl", "title")),
        "ncs": str(pick(rec, "ncsCdNmLst", "ncsCdLst", "ncsNm")),
        "hire": str(pick(rec, "hireTypeNmLst", "hireTypeLst")),
        "se": str(pick(rec, "recrutSeNm", "recrutSe")),
        "rgn": str(pick(rec, "workRgnNmLst", "workRgnLst")),
        "nope": str(pick(rec, "recrutNope", "nope")),
        "pref": str(pick(rec, "prefCondCn", "prefCn", "prefCond")),
        "qual": str(pick(rec, "aplyQlfcCn", "aplyQlfc")),
        "url": str(pick(rec, "srcUrl", "url", "pbancUrl")),
        "beg": beg,
        "end": end,
    }


# ---------------------------------------------------------------- filter

def gate(r, cfg):
    """자격증과 무관한 1차 관문. 통과한 공고만 HTML에 실어 보낸다.
    자격증 매칭은 브라우저에서 하므로 여기서 걸러내지 않는다."""
    # 고용형태 — "정규직"이 "비정규직"의 부분문자열이라 포함검사를 쓰면 안 된다.
    # 콤마로 쪼개 토큰 단위로 정확히 맞춘다.
    want = [x for x in cfg.get("고용형태", []) if x]
    if want:
        toks = {t.strip() for t in re.split(r"[,/]", r["hire"]) if t.strip()}
        if not toks & set(want):
            return False

    # 채용구분은 "신입"이 "신입+경력"에 들어가야 하므로 부분검사가 맞다.
    se = [x for x in cfg.get("채용구분", []) if x]
    if se and not any(s in r["se"] for s in se):
        return False

    # 제외어는 제목뿐 아니라 기관명도 본다. "부산대학교병원"처럼
    # 기관명에만 병원이 들어가는 경우를 잡기 위해서다.
    for bad in cfg.get("제외키워드", []):
        if bad and (bad in r["title"] or bad in r["inst"]):
            return False

    rgns = [x for x in cfg.get("근무지역", []) if x]
    if rgns and not any(x in r["rgn"] for x in rgns):
        return False

    return True


def interest(r, cfg):
    for inst in cfg.get("관심기관", []):
        if inst and inst.replace(" ", "") in r["inst"].replace(" ", ""):
            return inst
    return ""


# ---------------------------------------------------------------- render

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def dday(r):
    if not r["end"]:
        return None
    return (r["end"] - TODAY).days


CSS = """
:root{
--pri:#6162d4;--pri2:#5051c4;--pri3:#8b8de9;--tint:#dfe0f6;--zebra:#f4f5ff;
--ink:#333;--ink2:#505050;--ink3:#737373;--line:#d9d9d9;--line2:#dadade;
--soft:#f4f4f4;--red:#d42b2b;--orange:#c2650a;--green:#1a7f4b}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);word-break:keep-all;
font:14px/1.62 "Noto Sans KR","Malgun Gothic","맑은 고딕",sans-serif}
a{color:inherit}

/* ---- 상단 띠 + 로고 ---- */
.gov{background:var(--pri);color:#fff;font-size:12px;line-height:30px;height:30px}
.gov .in{max-width:1180px;margin:0 auto;padding:0 20px;text-align:right;opacity:.92}
.hd{border-bottom:1px solid var(--line)}
.hd .in{max-width:1180px;margin:0 auto;padding:16px 20px;display:flex;
align-items:center;gap:14px;flex-wrap:wrap}
.logo{font-size:23px;font-weight:900;color:var(--pri);letter-spacing:-.03em}
.logo span{display:inline-block;margin-left:12px;padding-left:13px;
border-left:1px solid var(--line);font-size:12.5px;font-weight:400;
color:var(--ink3);letter-spacing:0;vertical-align:3px}
.hd .when{margin-left:auto;font-size:12.5px;color:var(--ink3)}

.wrap{max-width:1180px;margin:0 auto;padding:0 20px 70px}
h1{text-align:center;font-size:31px;font-weight:800;letter-spacing:-.035em;
margin:38px 0 8px;color:#222}
.lead{text-align:center;font-size:13.5px;color:var(--ink3);margin:0 0 26px}
.lead b{color:var(--pri2);font-weight:700}

/* ---- 검색조건 박스 ---- */
.srch{border:1px solid var(--pri3);border-radius:10px;overflow:hidden;
margin-bottom:26px}
.srch-hd{display:flex;align-items:center;gap:12px;flex-wrap:wrap;
background:var(--zebra);padding:11px 16px;border-bottom:1px solid var(--pri3);
cursor:pointer;list-style:none}
.srch-hd::-webkit-details-marker{display:none}
.srch-hd .st{font-size:14.5px;font-weight:700;color:var(--pri2);white-space:nowrap}
.psum{flex:1;min-width:190px;font-size:13px;color:var(--ink2)}
.psum b{color:var(--pri2)}
.psum i{font-style:normal;color:var(--orange)}
.pmore{font-size:12.5px;color:#fff;background:var(--pri);border-radius:14px;
padding:3px 14px;white-space:nowrap}
.srch[open] .srch-hd{border-bottom-color:var(--line2)}
.form{width:100%;border-collapse:collapse;table-layout:fixed}
.form th{width:112px;background:var(--soft);border:1px solid var(--line2);
border-left:0;padding:10px 8px;font-size:13px;font-weight:500;color:var(--ink2);
text-align:center;vertical-align:middle}
.form td{border:1px solid var(--line2);border-right:0;padding:9px 14px;
vertical-align:middle}
.form tr:first-child th,.form tr:first-child td{border-top:0}
.chips{display:flex;flex-wrap:wrap;gap:4px 16px}
.c{font:inherit;font-size:13px;border:0;background:none;padding:1px 0;
color:var(--ink2);cursor:pointer;white-space:nowrap;line-height:1.9}
.c:hover{color:var(--pri2)}
.c:focus-visible{outline:2px solid var(--pri);outline-offset:2px}
.c b{font-weight:400;margin-right:5px;color:var(--line)}
.c.have{color:var(--pri2);font-weight:700}
.c.have b{color:var(--pri)}
.c.plan{color:var(--orange);font-weight:700}
.c.plan b{color:var(--orange)}
.srch-ft{display:flex;flex-wrap:wrap;gap:9px 14px;align-items:center;
padding:13px 16px;background:var(--soft);border-top:1px solid var(--line2);
font-size:13px;color:var(--ink2)}
.tally b{color:var(--pri2);font-weight:700}
.spacer{flex:1}
.srch-ft button{font:inherit;font-size:12.5px;padding:5px 14px;cursor:pointer;
border:1px solid var(--line);background:#fff;color:var(--ink2);border-radius:4px}
.srch-ft button:hover{border-color:var(--pri3);color:var(--pri2)}

/* ---- 탭 ---- */
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:18px}
.tabs button{font:inherit;font-size:13.5px;padding:8px 17px;cursor:pointer;
border:1px solid var(--line);background:#fff;color:var(--ink2);border-radius:24px}
.tabs button:hover{border-color:var(--pri3);color:var(--pri2)}
.tabs button span{color:var(--ink3);margin-left:6px;font-size:12.5px}
.tabs button.on{background:var(--pri);border-color:var(--pri);color:#fff;font-weight:700}
.tabs button.on span{color:#fff;opacity:.85}

/* ---- 결과 머리 ---- */
.rhd{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:9px}
.rhd h2{font-size:16.5px;font-weight:700;margin:0;color:#222}
.rhd h2 b{color:var(--pri)}
.rhd .r{margin-left:auto;display:flex;gap:6px}
.rhd select{font:inherit;font-size:12.5px;padding:5px 8px;border:1px solid var(--line);
border-radius:4px;background:#fff;color:var(--ink2);cursor:pointer}

/* ---- 목록 표 ---- */
.list{width:100%;border-collapse:collapse;border-top:2px solid var(--pri);
table-layout:fixed}
.list thead th{background:var(--pri);color:#fff;font-size:13.5px;font-weight:700;
padding:11px 5px;text-align:center;border-left:1px solid rgba(255,255,255,.28)}
.list thead th:first-child{border-left:0}
.list tbody td{border-left:1px solid var(--line2);border-bottom:1px solid var(--line2);
padding:11px 9px;font-size:13px;color:var(--ink2);text-align:center;
vertical-align:middle;background:#fff}
.list tbody td:first-child{border-left:0}
.list tbody tr:nth-child(odd) td{background:var(--zebra)}
.list tbody tr:hover td{background:var(--tint)}
.list td.t{text-align:left}
/* 기관명은 띄어쓰기가 없어 저절로 줄바꿈이 안 된다. 칸을 넘겨 옆 칸을
   침범하지 않도록 글자 단위로 줄을 바꾸게 한다. */
.list td.inst{overflow-wrap:anywhere;word-break:break-word;line-height:1.45}
.tl{font-size:14px;font-weight:500;color:#2b2b2b;line-height:1.5;
text-decoration:none;display:inline-block}
.tl:hover{color:var(--pri2);text-decoration:underline}
.sub2{display:block;margin-top:4px;font-size:12px;color:var(--ink3);line-height:1.6}
.sub2 u{text-decoration:none;border-bottom:1px dotted var(--ink3);cursor:help}
.badges{margin-top:6px;display:flex;flex-wrap:wrap;gap:4px}
.bg{font-size:11.5px;line-height:1.7;padding:0 7px;border-radius:3px;
background:var(--tint);color:var(--pri2);white-space:nowrap}
.bg.named{background:var(--pri);color:#fff;font-weight:700}
.bg.plan{background:#fdeddb;color:var(--orange)}
.bg.rest{background:none;border:1px solid var(--line);color:var(--ink3)}
.ymd{font-size:12.5px;color:var(--ink3);display:block}
.dd{font-size:13.5px;font-weight:700;color:var(--pri2)}
.dd.u{color:var(--red)}
.dd.s{color:var(--orange)}
.pin{display:inline-block;font-size:11px;line-height:1.6;padding:0 6px;
border:1px solid var(--pri3);color:var(--pri2);border-radius:3px;margin-right:5px}
.isnew{display:inline-block;font-size:11px;line-height:1.6;padding:0 6px;
background:var(--red);color:#fff;border-radius:3px;margin-right:5px;font-weight:700}
.none{padding:64px 20px;text-align:center;color:var(--ink3);font-size:13.5px;
line-height:2;border-bottom:1px solid var(--line2)}
.none b{color:var(--ink2)}

/* ---- 페이지 ---- */
.pager{display:flex;justify-content:center;gap:4px;margin-top:22px}
.pager button{font:inherit;font-size:13px;min-width:30px;height:30px;padding:0 8px;
border:1px solid var(--line);background:#fff;color:var(--ink2);cursor:pointer;
border-radius:3px}
.pager button:hover{border-color:var(--pri3);color:var(--pri2)}
.pager button.on{background:var(--pri);border-color:var(--pri);color:#fff;font-weight:700}
.pager button:disabled{color:#c4c4c4;cursor:default;border-color:#e8e8e8}

.notice{margin-top:30px;background:var(--soft);border:1px solid var(--line);
border-radius:6px;padding:16px 18px;font-size:12.5px;color:var(--ink3);line-height:1.95}
.notice p{margin:0 0 6px;text-indent:-13px;padding-left:13px}
.notice p:last-child{margin:0}
.notice b{color:var(--ink2)}

.pay-n{font-size:13.5px;font-weight:700;color:var(--pri2);display:block}
.pay-s{font-size:11.5px;color:var(--ink3);display:block;margin-top:1px}
.pay-x{color:#bdbdbd}
td.pay{cursor:help}

td.rt{cursor:help}
.rt-n{display:block;font-size:13.5px;font-weight:700;color:var(--pri2)}
.rt-n.hot{color:var(--red)}
.rt-n.easy{color:var(--green)}
.rt-s{display:block;font-size:11.5px;color:var(--ink3);margin-top:1px}

.srs{display:block;margin-top:5px;font-size:11.5px;color:var(--ink3);line-height:1.6}
.srs b{color:var(--pri2);font-weight:600}
.atc{margin-top:6px;display:flex;flex-wrap:wrap;gap:4px 10px;font-size:11.5px}
.atc[hidden]{display:none}
.atc-b{font:inherit;font-size:11.5px;margin-top:6px;padding:1px 8px;border-radius:3px;
cursor:pointer;border:1px solid var(--line);background:none;color:var(--ink3)}
.atc-b:hover{border-color:var(--pri3);color:var(--pri2)}
.atc-b.on{border-color:var(--pri3);background:var(--tint);color:var(--pri2)}
.atc a{color:var(--pri2);text-decoration:none;border-bottom:1px solid transparent}
.atc a:hover{border-bottom-color:var(--pri2)}
.atc a::before,.atc-b::before{content:"\\1F4CE";margin-right:3px;opacity:.7}
.acb{display:inline-block;font-size:11px;line-height:1.6;padding:0 6px;border-radius:3px;
background:var(--sf2,#eef0eb);border:1px solid var(--line);color:var(--ink3);margin-right:5px}

.ap-b{font:inherit;font-size:12px;padding:3px 10px;border-radius:12px;cursor:pointer;
border:1px dashed var(--line);background:none;color:#b8b8b8;white-space:nowrap;line-height:1.5}
.ap-b:hover{border-color:var(--pri3);color:var(--pri2)}
.ap-b.s1{border:1px solid var(--pri3);background:var(--tint);color:var(--pri2);font-weight:700}
.ap-b.s2{border:1px solid var(--pri);background:var(--pri);color:#fff;font-weight:700}
.ap-b.s3{border:1px solid var(--green);background:#e4f1e9;color:var(--green);font-weight:700}
.ap-b.s4{border:1px solid var(--line);background:var(--soft);color:var(--ink3);
text-decoration:line-through}

@media(max-width:900px){
.list col.hide,.list th.hide,.list td.hide{display:none}
h1{font-size:24px}
.form th{width:82px;font-size:12px}
}
"""

APP = """
var S = {};
try { S = JSON.parse(localStorage.getItem('certs') || 'null') || DEFAULTS; }
catch (e) { S = DEFAULTS; }

var FILTER = 'all', SORT = 'fit', PER = 20, PAGE = 1;

// 공고별 지원 상태. 0 미표시 -> 1 관심 -> 2 지원함 -> 3 서류합격 -> 4 탈락
var MARKS = ['-', '관심', '지원함', '서류합격', '탈락'];
var A = {};
try { A = JSON.parse(localStorage.getItem('applied') || '{}') || {}; }
catch (e) { A = {}; }

function saveA() {
  try { localStorage.setItem('applied', JSON.stringify(A)); } catch (e) {}
}
var PANEL = document.getElementById('panel');

function save() {
  try { localStorage.setItem('certs', JSON.stringify(S)); } catch (e) {}
}

function cycle(name) {
  var v = S[name] || 0;
  S[name] = (v + 1) % 3;      // 0 미보유 -> 1 보유 -> 2 취득예정
  save(); paintChips(); PAGE = 1; run();
}

function paintChips() {
  document.querySelectorAll('.c').forEach(function (b) {
    var v = S[b.dataset.n] || 0;
    b.className = 'c' + (v === 1 ? ' have' : v === 2 ? ' plan' : '');
    var box = v === 1 ? '■' : v === 2 ? '▣' : '□';
    b.innerHTML = '<b>' + box + '</b>' + b.dataset.n;
    b.setAttribute('aria-pressed', v ? 'true' : 'false');
  });
}

function scoreOne(rec, name, state) {
  var c = CERTS[name];
  if (!c) return null;

  // 정식 명칭이 본문에 그대로 있으면 가장 강한 신호.
  var named = c.alias.some(function (a) { return rec.body.indexOf(a) > -1; });

  // 통합공채는 여러 직렬을 한 공고로 내서 NCS 대분류가 5~6개씩 붙는다.
  // 그 자체가 '아무나'라는 뜻은 아니지만 근거로는 약하다.
  // 그래서 NCS 개수로 점수를 희석하고, 좁은 공고이거나 관심 기관일 때만
  // NCS 하나만으로도 후보에 올린다.
  var n = rec.ncs ? rec.ncs.split(',').length : 0;
  var specific = n > 0 && n <= 3;
  var ncsHit = c.ncs.some(function (x) { return rec.ncs.indexOf(x) > -1; });

  var kwHit = c.kw.filter(function (k) { return rec.title.indexOf(k) > -1; });

  // 상세에서 받은 '직렬명'이 있으면 NCS 대분류보다 훨씬 정확하다.
  // 통합공채는 NCS 가 5~6개씩 붙어 그것만으론 내 직렬이 있는지 알 수 없다.
  var srs = rec.series || [];
  var sHit = srs.length ? c.kw.filter(function (k) {
    return srs.some(function (t) { return t.indexOf(k) > -1; });
  }) : [];

  // 직렬을 다 아는 공고인데 하나도 안 맞으면 NCS 만으로는 후보에 올리지 않는다.
  var known = srs.length >= 2;
  if (!named && !kwHit.length && !sHit.length &&
      !(ncsHit && !known && (specific || rec.interest))) return null;

  var w = named ? 100
        : sHit.length * 20 + kwHit.length * 8 +
          (ncsHit ? 12 / Math.sqrt(Math.max(1, n)) : 0);
  return { name: name, state: state, named: named, ncs: ncsHit,
           kw: kwHit, srs: sHit, w: w };
}

function evaluate(rec) {
  var hits = [], score = 0;
  Object.keys(S).forEach(function (name) {
    var st = S[name];
    if (!st) return;
    var h = scoreOne(rec, name, st);
    if (!h) return;
    hits.push(h);
    score += st === 1 ? h.w : h.w * 0.4;   // 취득예정은 가중치를 낮춘다
  });
  // 관심 기관 가산은 공고당 한 번만.
  if (hits.length && rec.interest) score += 15;
  hits.sort(function (a, b) { return b.w - a.w; });
  return { hits: hits, score: score };
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// 한 칸에 다 못 넣는 콤마 목록을 줄인다. 원문은 마우스를 올리면 나온다.
function shorten(v, keep, unit) {
  var a = String(v || '').split(',').map(function (s) { return s.trim(); })
          .filter(function (s) { return s; });
  if (!a.length) return null;
  if (a.length <= keep) return { txt: a.join(', '), cut: false, n: a.length };
  return { txt: a.slice(0, keep).join(', ') + ' 외 ' + (a.length - keep) + unit,
           cut: true, n: a.length };
}

function hover(txt, full) {
  return full ? '<u title="' + esc(full) + '">' + esc(txt) + '</u>' : esc(txt);
}

function rgnCell(rec) {
  var rg = shorten(rec.rgn, 1, '');
  if (!rg) return '-';
  if (rg.n >= 13) return hover('전국', rec.rgn);
  return hover(rg.n > 1 ? rg.txt.split(' 외 ')[0] + ' 외 ' + (rg.n - 1) : rg.txt,
               rg.n > 1 ? rec.rgn : '');
}

// 만원 단위로 끊어 읽기 좋게. 알리오 원자료는 천원이다.
function man(thousand) {
  return Math.round(thousand / 10).toLocaleString('ko-KR') + '만';
}

function payCell(rec) {
  var p = rec.pay;
  if (!p || !p.p) return '<td class="pay"><span class="pay-x">-</span></td>';
  var tip = PAYYEAR + '년 공시 · 신입사원 초임 ' + p.p.toLocaleString('ko-KR') + '천원';
  if (p.a) tip += ' / 일반정규직 1인당 평균보수 ' + p.a.toLocaleString('ko-KR') + '천원';
  if (p.m) tip += ' / 평균근속 ' + (p.m / 12).toFixed(1) + '년';
  return '<td class="pay" title="' + esc(tip) + '">' +
    '<span class="pay-n">' + man(p.p) + '</span>' +
    (p.a ? '<span class="pay-s">평균 ' + man(p.a) + '</span>' : '') +
    '</td>';
}

function markCell(rec) {
  var v = A[rec.sn] || 0;
  return '<td><button class="ap-b s' + v + '" data-sn="' + esc(rec.sn) +
         '" title="누를 때마다 관심 → 지원함 → 서류합격 → 탈락 → 해제">' +
         MARKS[v] + '</button></td>';
}

function rateCell(rec) {
  var c = rec.cmp;
  if (!c) return '<td class="rt"><span class="pay-x">-</span></td>';
  var cls = c.r >= 30 ? 'rt-n hot' : (c.r <= 8 ? 'rt-n easy' : 'rt-n');
  var tip = '과거 ' + c.k + ' 공고 ' + c.n + '건의 경쟁률 중앙값 (' +
            c.lo + ':1 ~ ' + c.hi + ':1)';
  c.top.forEach(function (t) {
    tip += '\\n· ' + t.y + ' ' + t.t + ' — ' + t.r + ':1 (지원 ' +
           t.a.toLocaleString('ko-KR') + '명 → ' + t.n + '명)';
  });
  return '<td class="rt" title="' + esc(tip) + '">' +
    '<span class="' + cls + '">' + c.r + ':1</span>' +
    '<span class="rt-s">' + c.k + ' ' + c.n + '건</span></td>';
}

function row(rec, ev, no) {
  var d = rec.dday, cls = 'a', dd = '상시', when = '-';
  if (d !== null) {
    dd = d > 0 ? 'D-' + d : (d === 0 ? 'D-DAY' : '마감');
    when = rec.endTxt;
    cls = d <= 3 ? 'u' : (d <= 10 ? 's' : 'n');
  }

  var head = '';
  if (rec.isNew) head += '<span class="isnew">NEW</span>';
  if (rec.interest) head += '<span class="pin">관심기관</span>';

  var t = esc(rec.title) || '(제목 없음)';
  t = rec.url
    ? '<a class="tl" href="' + esc(rec.url) + '" target="_blank" rel="noopener">' + t + '</a>'
    : '<span class="tl">' + t + '</span>';

  var sub = [];
  if (rec.se) sub.push(esc(rec.se));
  if (rec.nope) sub.push(esc(/^[0-9]+$/.test(rec.nope) ? rec.nope + '명' : rec.nope));
  var nc = shorten(rec.ncs, 2, '개 분야');
  if (nc) sub.push(hover(nc.txt, nc.cut ? rec.ncs : ''));

  var bg = ev.hits.slice(0, 4).map(function (h) {
    var cl = h.named ? 'bg named' : (h.state === 2 ? 'bg plan' : 'bg');
    var why = h.named ? ' 명시'
            : (h.srs && h.srs.length ? ' 직렬'
            : (h.state === 2 ? ' 예정' : ''));
    return '<span class="' + cl + '">' + esc(h.name) + why + '</span>';
  });
  if (ev.hits.length > 4) {
    bg.push('<span class="bg rest">외 ' + (ev.hits.length - 4) + '</span>');
  }

  // 직렬은 통합공채에서 특히 쓸모 있다. 몇 개만 보이고 나머지는 툴팁으로.
  var srsLine = '';
  if (rec.series && rec.series.length) {
    // 바깥의 head(배지 줄)와 이름이 겹치면 var 호이스팅으로 덮어써진다.
    var sHead = rec.series.slice(0, 3).map(esc).join(' · ');
    var more = rec.series.length > 3 ? ' 외 ' + (rec.series.length - 3) : '';
    srsLine = '<span class="srs" title="' + esc(rec.series.join('\\n')) + '">' +
              '<b>직렬</b> ' + sHead + more + '</span>';
  }

  // 첨부는 공고당 서너 개씩이라 다 펼쳐 두면 제목이 묻힌다. 버튼만 세우고
  // 누를 때 펼친다.
  var atc = '';
  if (rec.files && rec.files.length) {
    atc = '<button type="button" class="atc-b">첨부 ' + rec.files.length + '</button>' +
          '<div class="atc" hidden>' + rec.files.map(function (f) {
      return '<a href="' + esc(f.u) + '" target="_blank" rel="noopener">' +
             esc(f.n) + '</a>';
    }).join('') + '</div>';
  }

  var acb = rec.acbg ? '<span class="acb">' + esc(rec.acbg) + '</span>' : '';

  var hi = shorten(rec.hire, 1, '');

  return '<tr>' +
    '<td>' + no + '</td>' +
    '<td class="t">' + head + acb + t +
      (sub.length ? '<span class="sub2">' + sub.join(' · ') + '</span>' : '') +
      srsLine + atc +
      (bg.length ? '<div class="badges">' + bg.join('') + '</div>' : '') +
    '</td>' +
    '<td class="inst">' + esc(rec.inst) + '</td>' +
    payCell(rec) +
    rateCell(rec) +
    '<td class="hide">' + rgnCell(rec) + '</td>' +
    '<td class="hide">' + (hi ? hover(hi.n > 1 ? hi.txt.split(' 외 ')[0] + ' 외 ' + (hi.n - 1)
                                              : hi.txt, hi.n > 1 ? rec.hire : '') : '-') + '</td>' +
    '<td><span class="ymd">' + esc(when) + '</span>' +
        '<span class="dd ' + cls + '">' + dd + '</span></td>' +
    markCell(rec) +
    '</tr>';
}

function match(x, f) {
  if (f === 'all') return true;
  if (f === 'named') return x.e.hits.some(function (h) { return h.named; });
  if (f === 'urgent') return x.r.dday !== null && x.r.dday <= 10;
  if (f === 'new') return x.r.isNew;
  if (f === 'inst') return !!x.r.interest;
  if (f === 'mine') return !!A[x.r.sn];
  return x.e.score > 0;                       // 'fit'
}

function dnum(r) { return r.dday === null ? 9999 : r.dday; }

function sorter(a, b) {
  if (SORT === 'dday') return dnum(a.r) - dnum(b.r);
  if (SORT === 'inst') return a.r.inst.localeCompare(b.r.inst, 'ko');
  if (SORT === 'rate') {
    // 경쟁률은 낮을수록 좋다. 표본이 없는 기관은 뒤로 보낸다.
    var ra = a.r.cmp ? a.r.cmp.r : 1e9, rb = b.r.cmp ? b.r.cmp.r : 1e9;
    if (ra !== rb) return ra - rb;
    return dnum(a.r) - dnum(b.r);
  }
  if (SORT === 'pay') {
    var pa = a.r.pay ? a.r.pay.p : -1, pb = b.r.pay ? b.r.pay.p : -1;
    if (pa !== pb) return pb - pa;              // 초임 높은 순, 없으면 뒤로
    return dnum(a.r) - dnum(b.r);
  }
  if (b.e.score !== a.e.score) return b.e.score - a.e.score;   // 'fit'
  return dnum(a.r) - dnum(b.r);
}

// 고른 자격증을 검색조건이 접힌 상태에서도 한 줄로 보여준다.
function summarize() {
  var have = [], plan = [];
  Object.keys(S).forEach(function (k) {
    if (S[k] === 1) have.push(k); else if (S[k] === 2) plan.push(k);
  });
  function cut(a) {
    return a.length > 3 ? a.slice(0, 3).join(', ') + ' 외 ' + (a.length - 3) : a.join(', ');
  }
  var out = [];
  if (have.length) out.push('<b>보유</b> ' + esc(cut(have)));
  if (plan.length) out.push('<i>취득예정</i> ' + esc(cut(plan)));
  document.getElementById('psum').innerHTML =
    out.length ? out.join(' / ') : '선택된 자격증이 없습니다';
}

function pager(total) {
  var pages = PER === 0 ? 1 : Math.ceil(total / PER);
  var el = document.getElementById('pager');
  if (pages <= 1) { el.innerHTML = ''; return; }
  var h = '<button data-p="1"' + (PAGE === 1 ? ' disabled' : '') + '>&laquo;</button>' +
          '<button data-p="' + (PAGE - 1) + '"' + (PAGE === 1 ? ' disabled' : '') + '>&lsaquo;</button>';
  for (var i = 1; i <= pages; i++) {
    h += '<button data-p="' + i + '"' + (i === PAGE ? ' class="on"' : '') + '>' + i + '</button>';
  }
  h += '<button data-p="' + (PAGE + 1) + '"' + (PAGE === pages ? ' disabled' : '') + '>&rsaquo;</button>' +
       '<button data-p="' + pages + '"' + (PAGE === pages ? ' disabled' : '') + '>&raquo;</button>';
  el.innerHTML = h;
  el.querySelectorAll('button').forEach(function (b) {
    b.onclick = function () {
      if (b.disabled) return;
      PAGE = parseInt(b.dataset.p, 10); run();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };
  });
}

function run() {
  var scored = DATA.map(function (r) { return { r: r, e: evaluate(r) }; });

  document.querySelectorAll('.tabs button').forEach(function (b) {
    var f = b.dataset.f;
    b.querySelector('span').textContent =
      scored.filter(function (x) { return match(x, f); }).length;
  });

  var rows = scored.filter(function (x) { return match(x, FILTER); });
  rows.sort(sorter);

  var picked = Object.keys(S).filter(function (k) { return S[k]; }).length;
  var fitCount = scored.filter(function (x) { return x.e.score > 0; }).length;
  document.getElementById('tally').innerHTML =
    '선택 <b>' + picked + '개</b> · 전체 ' + DATA.length + '건 중 <b>' + fitCount + '건</b> 적합';
  document.getElementById('rcount').textContent = rows.length;
  summarize();

  var pages = PER === 0 ? 1 : Math.max(1, Math.ceil(rows.length / PER));
  if (PAGE > pages) PAGE = pages;
  var from = PER === 0 ? 0 : (PAGE - 1) * PER;
  var page = PER === 0 ? rows : rows.slice(from, from + PER);

  var tb = document.getElementById('tbody');
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="9" class="none">조회된 채용공고가 없습니다.<br>' +
      (picked ? '자격증을 더 고르거나 <b>전체</b> 탭을 눌러보세요.'
              : '위 <b>내 자격증</b>을 펼쳐 보유 자격증을 먼저 선택해 주세요.') + '</td></tr>';
  } else {
    tb.innerHTML = page.map(function (x, i) {
      return row(x.r, x.e, from + i + 1);      // 1번부터 차례대로
    }).join('');
  }
  pager(rows.length);
}

document.querySelectorAll('.c').forEach(function (b) {
  b.onclick = function () { cycle(b.dataset.n); };
});
document.querySelectorAll('.tabs button').forEach(function (b) {
  b.onclick = function () {
    document.querySelectorAll('.tabs button').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on'); FILTER = b.dataset.f; PAGE = 1; run();
  };
});
// 표를 다시 그릴 때마다 핸들러를 달면 중복되므로 tbody 한 곳에만 건다.
document.getElementById('tbody').addEventListener('click', function (e) {
  var f = e.target.closest ? e.target.closest('.atc-b') : null;
  if (f) {
    var box = f.nextElementSibling;
    box.hidden = !box.hidden;
    f.classList.toggle('on');
    return;
  }
  var b = e.target.closest ? e.target.closest('.ap-b') : null;
  if (!b) return;
  var sn = b.dataset.sn;
  A[sn] = ((A[sn] || 0) + 1) % MARKS.length;
  if (!A[sn]) delete A[sn];
  saveA();
  run();
});

document.getElementById('sort').onchange = function () {
  SORT = this.value; PAGE = 1; run();
};
document.getElementById('per').onchange = function () {
  PER = parseInt(this.value, 10); PAGE = 1; run();
};
document.getElementById('reset').onclick = function () {
  S = {}; save(); paintChips(); PAGE = 1; run();
};
document.getElementById('restore').onclick = function () {
  S = JSON.parse(JSON.stringify(DEFAULTS)); save(); paintChips(); PAGE = 1; run();
};

// 검색조건은 접힌 채로 시작한다. 목록이 먼저 보이는 편이 낫다.
function paintPanel() {
  PANEL.querySelector('.pmore').textContent = PANEL.open ? '접기 ▲' : '펼치기 ▼';
}
try { PANEL.open = localStorage.getItem('panelOpen') === '1'; } catch (e) {}
PANEL.addEventListener('toggle', function () {
  try { localStorage.setItem('panelOpen', PANEL.open ? '1' : '0'); } catch (e) {}
  paintPanel();
});
paintPanel();

paintChips();
run();
"""


def build_picker():
    """검색조건 표. 왼쪽 라벨 칸 + 오른쪽 자격증 목록 — 정부 포털 폼 형태."""
    out = ["<table class=\"form\"><tbody>"]
    for gname, items in certs.GROUPS:
        chips = "".join(
            '<button class="c" data-n="%s" aria-pressed="false">%s</button>' % (esc(n), esc(n))
            for n, _ncs, _kw, _al in items
        )
        out.append('<tr><th scope="row">%s</th><td><div class="chips">%s</div></td></tr>'
                   % (esc(gname), chips))
    out.append("</tbody></table>")
    return "".join(out)

def render(rows, cfg, defaults, pay, comp, dets):
    data = []
    for r, is_new in rows:
        d = dday(r)
        data.append({
            "sn": r["sn"],
            "inst": r["inst"], "title": r["title"], "ncs": r["ncs"], "rgn": r["rgn"],
            "nope": r["nope"], "se": r["se"], "hire": r["hire"], "url": r["url"],
            "interest": interest(r, cfg), "isNew": bool(is_new),
            "dday": d, "endTxt": r["end"].strftime("%y.%m.%d") if r["end"] else "",
            # 자격증 이름을 찾을 본문. 길면 잘라 파일 크기를 잡는다.
            "body": (r["qual"] + " " + r["pref"] + " " + r["title"])[:900],
        })
        # 알리오 경영공시의 기관별 보수. 이름이 안 맞으면 그냥 비운다.
        sal = salary.attach(r["inst"], pay)
        data[-1]["pay"] = ({"p": sal["pay"], "a": sal["avg"], "m": sal["mon"]}
                           if sal else None)
        # 상세에서 받은 학력·직렬·첨부.
        info = dets.get(str(r["sn"])) or {}
        data[-1]["acbg"] = info.get("acbg") or ""
        data[-1]["series"] = info.get("series") or []
        data[-1]["files"] = info.get("files") or []

        # 과거 공고에서 모은 그 기관의 경쟁률. 같은 직렬 표본이 있으면 그걸 쓴다.
        cs = compete.summary(r["inst"], comp, series=info.get("series"))
        data[-1]["cmp"] = ({"r": cs["med"], "n": cs["n"], "k": cs["kind"],
                            "lo": cs["lo"], "hi": cs["hi"], "top": cs["top"]}
                           if cs else None)
    now = now_kst().strftime("%Y-%m-%d %H:%M")
    payload = (
        "var DATA=%s;\nvar CERTS=%s;\nvar DEFAULTS=%s;\n"
        % (json.dumps(data, ensure_ascii=False),
           json.dumps(certs.flat(), ensure_ascii=False),
           json.dumps(defaults, ensure_ascii=False))
    )
    payload += "var PAYYEAR=%d;\n" % (pay.get("year") or 0)
    kcalc = kosha_panel.load()
    payload += "var KOSHA=%s;\n" % json.dumps(kcalc, ensure_ascii=False)
    xcalc = kepco_panel.load()
    payload += "var KEPCO=%s;\n" % json.dumps(xcalc, ensure_ascii=False)
    gcalc = kogas_panel.load()
    payload += "var KOGAS=%s;\n" % json.dumps(gcalc, ensure_ascii=False)

    # '전체'가 첫 탭이자 기본 화면이다. 자격증으로 좁힌 화면만 먼저 보이면
    # 경쟁률·초임처럼 다른 공고에 붙은 정보가 통째로 안 보인다.
    # 정렬은 그대로 '자격증 적합순'이라 맞는 공고는 어차피 위로 올라온다.
    tabs = [
        ("all", "전체"), ("mine", "내 표시"), ("fit", "내 자격증 적합"),
        ("named", "공고 명시"), ("urgent", "마감 임박"), ("new", "신규 공고"),
        ("inst", "관심 기관"),
    ]
    tab_html = "".join(
        '<button%s data-f="%s">%s<span>0</span></button>'
        % (' class="on"' if i == 0 else "", f, esc(label))
        for i, (f, label) in enumerate(tabs)
    )

    cols = [("번호", "48", ""), ("채용제목", "", ""), ("기관명", "182", ""),
            ("신입 초임", "98", ""), ("경쟁률", "88", ""), ("근무지", "88", "hide"),
            ("고용형태", "98", "hide"), ("마감일", "88", ""), ("내 상태", "92", "")]
    colgroup = "".join(
        '<col%s%s>' % (' style="width:%spx"' % w if w else "",
                       ' class="hide"' if c else "")
        for _t, w, c in cols
    )
    thead = "".join(
        '<th scope="col"%s>%s</th>' % (' class="hide"' if c else "", esc(t))
        for t, _w, c in cols
    )

    # CSS·JS 에 % 가 들어 있어 문자열 포매팅 대신 이어붙인다.
    return "".join([
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<title>공공기관 채용정보 ", now, "</title>",
        "<style>", CSS, kosha_panel.CSS, kepco_panel.CSS, kogas_panel.CSS,
        "</style></head><body>",

        '<div class="gov"><div class="in">',
        "잡알리오 오픈API로 만든 개인용 채용공고 목록입니다",
        "</div></div>",
        '<div class="hd"><div class="in">',
        '<span class="logo">채용공고<span>공공기관 채용정보 스캐너</span></span>',
        '<span class="when">', now, " 기준</span>",
        ('<button class="kbtn" id="kbtn" type="button" aria-expanded="false">'
         'KOSHA <b id="kbtnv"></b></button>') if kcalc else "",
        ('<button class="kbtn" id="xbtn" type="button" aria-expanded="false">'
         '한전 <b id="xbtnv"></b></button>') if xcalc else "",
        ('<button class="kbtn" id="gbtn" type="button" aria-expanded="false">'
         '가스공사 <b id="gbtnv"></b></button>') if gcalc else "",
        "</div></div>",

        '<div class="wrap">',
        "<h1>공공기관 채용정보</h1>",
        '<p class="lead">진행 중인 공고를 고용형태·채용구분으로 1차 추린 ',
        "<b>", str(len(data)), "건</b>입니다. 보유 자격증을 선택하면 맞는 공고가 위로 올라옵니다.</p>",

        '<details class="srch" id="panel"><summary class="srch-hd">',
        '<span class="st">내 자격증</span>',
        '<span class="psum" id="psum"></span>',
        '<span class="pmore">펼치기 ▼</span></summary>',
        build_picker(),
        '<div class="srch-ft"><span class="tally" id="tally"></span>',
        '<span class="spacer"></span>',
        "<span>□ 미보유 · ■ 보유 · ▣ 취득예정 (누를 때마다 바뀝니다)</span>",
        '<button id="restore">기본값</button>',
        '<button id="reset">전체해제</button></div></details>',

        # ---- KOSHA 서류 정량평가 계산기. 배점표 데이터가 없으면 통째로 생략한다 ----
        ('<details class="srch" id="kpanel"><summary class="srch-hd">'
         '<span class="st">KOSHA 정량평가</span>'
         '<span class="psum" id="ksum"></span>'
         '<span class="kbar"><i id="kbari"></i></span>'
         '<span class="pmore">접기 ▲</span></summary>'
         + kosha_panel.panel(kcalc) + "</details>") if kcalc else "",

        # ---- 한전 1차(서류)전형 계산기. 같은 방식으로 데이터가 없으면 생략한다 ----
        ('<details class="srch" id="xpanel"><summary class="srch-hd">'
         '<span class="st">한전 1차전형</span>'
         '<span class="psum" id="xsum"></span>'
         '<span class="xbar"><i id="xbari"></i></span>'
         '<span class="pmore">접기 ▲</span></summary>'
         + kepco_panel.panel(xcalc) + "</details>") if xcalc else "",

        # ---- 가스공사 서류전형 계산기 ----
        ('<details class="srch" id="gpanel"><summary class="srch-hd">'
         '<span class="st">가스공사 서류전형</span>'
         '<span class="psum" id="gsum"></span>'
         '<span class="gbar"><i id="gbari"></i></span>'
         '<span class="pmore">접기 ▲</span></summary>'
         + kogas_panel.panel(gcalc) + "</details>") if gcalc else "",

        '<div class="tabs">', tab_html, "</div>",

        '<div class="rhd"><h2>채용정보 <b id="rcount">0</b>건</h2><div class="r">',
        '<select id="sort">',
        '<option value="fit">자격증 적합순</option>',
        '<option value="dday">마감 임박순</option>',
        '<option value="rate">경쟁률 낮은순</option>',
        '<option value="pay">초임 높은순</option>',
        '<option value="inst">기관명순</option></select>',
        '<select id="per">',
        '<option value="20">20개씩</option>',
        '<option value="50">50개씩</option>',
        '<option value="0">전체보기</option></select>',
        "</div></div>",

        '<table class="list"><colgroup>', colgroup, "</colgroup>",
        "<thead><tr>", thead, "</tr></thead>",
        '<tbody id="tbody"></tbody></table>',
        '<div class="pager" id="pager"></div>',

        '<div class="notice">',
        "<p>※ <b>명시</b> 표시가 붙은 자격증은 공고 본문에 이름이 실제로 적혀 있는 경우입니다. ",
        "표시가 없으면 NCS 직무·공고 제목으로 추정한 것이니 원문을 반드시 확인하세요.</p>",
        "<p>※ 대부분의 공고는 자격 요건을 첨부파일로 넘기기 때문에 API 본문만으로는 ",
        "명시 여부를 모두 확인할 수 없습니다.</p>",
        "<p>※ <b>내 상태</b> 칸을 누르면 관심 → 지원함 → 서류합격 → 탈락 → 해제 순으로 ",
        "바뀝니다. 이 브라우저에만 저장되며 <b>내 표시</b> 탭에서 모아 볼 수 있습니다.</p>",
        "<p>※ <b>경쟁률</b>은 그 기관의 <b>지난 공고</b>에서 확인된 값(지원자수 ÷ 최종선발인원)의 ",
        "중앙값이며, 이번 공고의 경쟁률이 아닙니다. 직렬마다 크게 다르니 마우스를 올려 ",
        "표본을 확인하세요. 표본이 아직 없는 기관은 빈칸입니다.</p>",
        "<p>※ <b>신입 초임</b>은 해당 기관이 알리오에 공시한 ",
        str(pay.get("year") or ""), "년 <b>일반정규직 신입사원 초임(합계)</b>이며 ",
        "이번 공고의 급여가 아닙니다. 기관 전체 평균이라 직군·직급에 따라 달라집니다. ",
        "칸에 마우스를 올리면 1인당 평균보수와 평균근속연수가 함께 표시됩니다.</p>",
        "<p>※ 점선이 있는 <b>외 N</b> 항목에 마우스를 올리면 전체 목록이 표시됩니다.</p>",
        "<p>※ 출처 : 채용정보는 잡알리오 오픈API(공공데이터포털 15125273), ",
        "보수는 알리오 경영공시 통계(www.alio.go.kr). ",
        "지방공기업은 클린아이 잡플러스 소관으로 이 목록에 포함되지 않습니다.</p>",
        "</div>",

        "</div><script>", payload, APP, kosha_panel.APP, kepco_panel.APP,
        kogas_panel.APP, "</script></body></html>",
    ])

# ---------------------------------------------------------------- main

def loose_gate(cfg):
    """경쟁률 표본용 필터. 목록 필터보다 느슨하다.
    기관의 경쟁률 감을 잡는 게 목적이라 신입·경력을 가리지 않는다."""
    bad = [b for b in cfg.get("제외키워드", []) if b]

    def ok(r):
        return not any(b in r["title"] or b in r["inst"] for b in bad)
    return ok


def compete_load(cfg, rows, args):
    targets = sorted({r["inst"] for r, _n in rows})
    return compete.load(cfg["serviceKey"], loose_gate(cfg),
                        cfg.get("관심기관", []), targets,
                        force="--compete" in args)


def collect(args=()):
    """API 호출부터 정렬까지. HTML 을 만들 재료를 돌려준다."""
    cfg = load_config()
    print("잡알리오 API 호출 중…")
    raw = fetch_all(cfg["serviceKey"])
    if not raw:
        die("공고를 하나도 받지 못했습니다. --dump 로 응답을 확인해 보세요.")

    recs = [norm(x) for x in raw]
    recs = [r for r in recs if (r["end"] is None or r["end"] >= TODAY)]

    seen = set()
    if os.path.exists(SEEN):
        try:
            with open(SEEN, encoding="utf-8") as f:
                seen = set(json.load(f))
        except Exception:
            seen = set()
    first_run = not seen

    keep = [r for r in recs if "--all" in args or gate(r, cfg)]

    # 상세를 받아 학력조건으로 한 번 더 거른다. 석·박사만 뽑는 공고는
    # 목록에 있어 봐야 소음이다. 상세를 못 받았으면 그냥 통과시킨다.
    dets = detail.load(cfg["serviceKey"], [r["sn"] for r in keep])
    want = [x for x in cfg.get("학력조건", []) if x]
    if want:
        before = len(keep)
        keep = [r for r in keep if detail.acbg_ok(dets.get(str(r["sn"])), want)]
        if before != len(keep):
            print("  학력조건으로 %d건 제외" % (before - len(keep)))

    rows = [(r, (not first_run) and r["sn"] not in seen) for r in keep]
    rows.sort(key=lambda t: (dday(t[0]) if dday(t[0]) is not None else 9999, t[0]["inst"]))

    defaults = {n: 1 for n in cfg.get("보유자격증", []) if n in certs.flat()}
    defaults.update({n: 2 for n in cfg.get("취득예정자격증", []) if n in certs.flat()})

    return cfg, recs, rows, defaults, first_run, dets


def save_seen(recs):
    try:
        with open(SEEN, "w", encoding="utf-8") as f:
            json.dump(sorted({r["sn"] for r in recs}), f)
    except OSError:
        pass          # 읽기 전용 파일시스템이면 NEW 표시만 포기한다


def build_html(args=()):
    """app.py 가 부르는 진입점. (HTML 문자열, 공고 수) 를 돌려준다."""
    cfg, recs, rows, defaults, _first, dets = collect(args)
    pay = salary.load(force="--salary" in args)
    comp = compete_load(cfg, rows, args)
    html = render(rows, cfg, defaults, pay, comp, dets)
    save_seen(recs)
    return html, len(rows)


def main():
    args = sys.argv[1:]

    print("\n공공기관 채용 스캐너")
    print("-" * 46)

    if "--dump" in args:
        cfg = load_config()
        raw = fetch_all(cfg["serviceKey"])
        print("\n[첫 레코드 원본]")
        print(json.dumps(raw[0], ensure_ascii=False, indent=2))
        print("\n[필드명 목록]")
        print(", ".join(sorted(raw[0].keys())))
        input("\n엔터를 누르면 닫힙니다...")
        return

    cfg, recs, rows, defaults, first_run, dets = collect(args)
    pay = salary.load(force="--salary" in args)
    comp = compete_load(cfg, rows, args)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(rows, cfg, defaults, pay, comp, dets))
    save_seen(recs)

    n_new = sum(1 for _r, is_new in rows if is_new)
    print("-" * 46)
    print("진행 중 %d건 → 1차 통과 %d건" % (len(recs), len(rows)))
    print("보유 %d개 / 취득예정 %d개를 기본 선택으로 넣었습니다."
          % (sum(1 for v in defaults.values() if v == 1),
             sum(1 for v in defaults.values() if v == 2)))
    if first_run:
        print("첫 실행이라 NEW 표시는 없습니다. 다음 실행부터 새 공고를 표시합니다.")
    elif n_new:
        print("\n새로 올라온 공고 %d건:" % n_new)
        for r, is_new in rows:
            if is_new:
                d = dday(r)
                print("  %-6s %s — %s" % ("D-%d" % d if d is not None else "상시",
                                          r["inst"], r["title"][:44]))
    else:
        print("새 공고 없음.")

    urgent = [r for r, _n in rows if dday(r) is not None and 0 <= dday(r) <= 7]
    if urgent:
        print("\n이번 주 마감 %d건:" % len(urgent))
        for r in urgent:
            print("  D-%-3d %s — %s" % (dday(r), r["inst"], r["title"][:44]))

    print("\n결과: %s" % OUT)
    print("HTML에서 자격증을 고르면 맞는 공고가 위로 올라옵니다.")
    if not SERVER:
        try:
            os.startfile(OUT)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단했습니다.")
    except Exception as e:
        print("\n[오류] %s: %s" % (type(e).__name__, e))
        if SERVER:
            sys.exit(1)          # 서버·CI 에서는 입력을 기다리면 안 된다
        input("엔터를 누르면 닫힙니다...")
