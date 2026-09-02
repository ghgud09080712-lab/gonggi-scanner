# -*- coding: utf-8 -*-
"""
마감된 공고에서 기관별·직렬별 경쟁률을 모은다.

진행 중인 공고는 지원인원이 전부 비어 있지만, 마감된 공고에는 들어온다.
`/detail` 의 steps 구조를 알아야 제대로 읽을 수 있다.

  steps 는 sortNo 가 '직렬', 그 안의 행들이 '전형 단계'다.
  한 직렬 그룹에서
    - 첫 단계 행의 aplyNope  = 총 지원자 수
    - cmpttRt 가 채워진 행     = 마지막 단계. recrutNope 가 최종 선발인원
    - 그 행의 cmpttRt          = 공식 경쟁률 (지원자수 ÷ 최종선발인원)

  예) 한국장학재단 5급-일반행정 : 지원 2,338 ÷ 최종 18 = 129.89 = cmpttRt
  그래서 직접 계산하지 않고 cmpttRt 를 그대로 쓴다.

전체를 훑으면 요청이 수천 건이라 하루 한도(1,000회)를 넘긴다. 그래서
  - 한 번 실행에 BUDGET 회만 쓰고 중단한 지점을 compete.json 에 저장한다
    (저장소에 들어 있는 compete.json 은 씨앗이다. 깃허브 액션은 캐시가 있으면
     그쪽을 쓰고, 없으면 이 씨앗에서 이어서 모은다)
  - 관심기관을 먼저 처리해 쓸모 있는 값이 빨리 쌓이게 한다
  - 이미 본 공고 번호는 다시 조회하지 않는다
여러 번 실행하며 조금씩 채워 나가는 구조다.
"""

import io
import json
import re
import os
import time
import datetime as dt
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "compete.json")
BASE = "https://apis.data.go.kr/1051000/recruitment/"

# 알리오 개방데이터 포털(청년일자리)이 자기 '오픈API 조회' 화면을 그리려고 쓰는
# 주소다. 원본이 같아서 파라미터 이름도 응답 필드도 data.go.kr 것과 똑같은데
# 인증키가 필요 없고 하루 한도에도 안 걸린다. 목록은 numOfRows=1000 이 먹혀서
# 한 달치가 요청 한 번에 끝난다(data.go.kr 은 100건씩 6번).
#
# 다만 공식 개방 API 가 아니라 사이트 내부 주소라 예고 없이 바뀔 수 있다.
# 그래서 이걸 먼저 쓰되, 실패하면 조용히 data.go.kr 경로로 되돌아간다.
ALIO = "https://opendata.alio.go.kr/new/odaApiMng/recrutInquiryAjax%s.do"
ALIO_REF = "https://opendata.alio.go.kr/new/odaApiMng/recrutInquiryList.do"
ALIO_ROWS = 1000      # 목록 한 번에 받을 건수
ALIO_PAUSE = 0.35     # 남의 웹서버다. 호출 사이에 간격을 둔다
ALIO_GIVEUP = 3       # 연속 이만큼 실패하면 이번 실행에서는 안 쓴다

BUDGET = 400          # 한 번 실행에서 쓸 API 호출 수 (일 한도 1,000회)
MONTHS = 36           # 몇 달 전까지 훑을지
                      # 18개월로는 모자랐다. cmpttRt 공시가 아주 늦어서
                      # 최근 1년치는 대부분 비어 있다 — 표본 0건이던 대형기관
                      # 31곳을 202304~202409 로 밀어서 보니 10/10 다 나왔다.
                      # (한전·환경공단·가스공사·인국공·심평원 …)
SKIP_RECENT = 5       # 최근 몇 달은 건너뛸지 — 전형이 끝나야 지원인원이 공시된다
MAX_PER_INST = 40     # 기관당 보관할 표본 수
PER_INST_MONTH = 5    # 한 기관에서 한 달에 상세 조회할 공고 수 상한
                      # 한도 없는 경로로 바뀐 뒤 2 -> 5. 2 일 때는 그 달에
                      # 경쟁률이 실린 공고를 못 집고 지나치는 일이 잦았다
ENOUGH_PER_INST = 6   # 이만큼 모인 기관은 더 캐지 않는다
MAX_AGE_DAYS = 0      # 날짜가 바뀌면 이어서 더 모은다 (하루 한 번)


def _key(name):
    """기관명 대조용. (주)·(재) 와 공백·기호를 턴다."""
    import re
    s = re.sub(r"\((주|재|사|사단법인|재단법인|학교법인)\)", "", str(name or ""))
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s)


def _empty():
    return {"updated": "", "done_months": [], "pending": {}, "seen": [], "inst": {}}


def load_cache():
    if os.path.exists(CACHE):
        try:
            with io.open(CACHE, encoding="utf-8") as f:
                d = json.load(f)
            for k, v in _empty().items():
                d.setdefault(k, v)
            return d
        except Exception:
            pass
    return _empty()


def save_cache(d):
    try:
        with io.open(CACHE, "w", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False))
    except OSError:
        pass


class Quota(Exception):
    """일일 한도 초과. 오늘은 더 못 부른다."""


class Budget(object):
    """남은 호출 수를 세는 것뿐이다. 다 쓰면 Stop 을 던진다."""

    class Stop(Exception):
        pass

    def __init__(self, n):
        self.left = n

    def spend(self):
        if self.left <= 0:
            raise Budget.Stop()
        self.left -= 1


_alio_fail = [0]
_alio_why = [None]


def _alio_note(e):
    """알리오 경로가 왜 죽었는지 한 번만 알려 준다.
    조용히 data.go.kr 로 넘어가면 러너에서 무슨 일이 났는지 알 길이 없다."""
    _alio_fail[0] += 1
    if _alio_why[0] is None:
        _alio_why[0] = "%s: %s" % (type(e).__name__, e)
        print("  알리오 경로 실패 → data.go.kr 로 갑니다 (%s)" % _alio_why[0][:120])


def _alio(ep, kw):
    """알리오 내부 엔드포인트로 같은 데이터를 받아 data.go.kr 모양으로 맞춘다."""
    body = urllib.parse.urlencode(kw).encode("utf-8")
    req = urllib.request.Request(
        ALIO % ("Detail" if ep == "detail" else "List"), data=body,
        headers={"User-Agent": "Mozilla/5.0", "Referer": ALIO_REF,
                 "X-Requested-With": "XMLHttpRequest",
                 "Content-Type": "application/x-www-form-urlencoded"})
    time.sleep(ALIO_PAUSE)
    with urllib.request.urlopen(req, timeout=45) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    d = d.get("data") or {}
    res = d.get("result")
    if res is None:
        raise ValueError("빈 응답")
    return {"result": res, "totalCount": d.get("totalCount")}


def _api(key, ep, budget, **kw):
    # 한도를 안 쓰는 경로부터 시도한다. 여기서 받아지면 budget 은 건드리지 않는다.
    if _alio_fail[0] < ALIO_GIVEUP:
        try:
            out = _alio(ep, dict(kw, ongoingYn="A"))
            _alio_fail[0] = 0
            return out
        except Exception as e:
            _alio_note(e)

    budget.spend()
    kw.update({"serviceKey": key, "resultType": "json"})
    url = BASE + ep + "?" + urllib.parse.urlencode(kw)
    req = urllib.request.Request(url, headers={"User-Agent": "gonggi-scanner/1.0"})
    # 응답이 늦는 일이 잦다. 재시도는 호출 한도를 더 쓰지 않는다.
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                body = r.read().decode("utf-8", "replace")
            if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in body:
                raise Quota()
            return json.loads(body)
        except urllib.error.HTTPError as e:
            # 429 는 재시도해도 소용없다. 오늘 치를 다 쓴 것이다.
            if e.code == 429:
                raise Quota()
            last = e
            time.sleep(2 * (attempt + 1))
        except Quota:
            raise
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def rates(detail):
    """한 공고에서 직렬별 경쟁률을 뽑는다."""
    groups = {}
    for s in detail.get("steps") or []:
        groups.setdefault(s.get("sortNo"), []).append(s)

    out = []
    for rows in groups.values():
        final = None
        for r in rows:
            if r.get("cmpttRt") not in (None, ""):
                final = r                      # 마지막 단계 행
        if final is None:
            continue
        try:
            rt = round(float(final["cmpttRt"]), 1)
        except (TypeError, ValueError):
            continue
        if rt <= 0:
            continue                            # 선발 0명이면 경쟁률이 의미 없다
        aply = max([r.get("aplyNope") or 0 for r in rows] or [0])
        out.append({
            "t": (final.get("recrutPbancTtl") or "")[:40],
            "r": rt,
            "n": final.get("recrutNope") or 0,
            "a": aply,
        })
    return out


def _months(n, skip=0):
    """이번 달에서 skip 개월 전부터 n개월 거슬러 올라가는 (시작일, 종료일, 키) 목록.

    막 마감된 공고는 지원인원이 비어 있다. 전형이 다 끝나고 공시돼야
    값이 들어오므로 최근 몇 달은 훑어도 소득이 없다."""
    today = dt.date.today()
    y, m = today.year, today.month
    out = []
    for _ in range(skip + n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        first = dt.date(y, m, 1)
        last = dt.date(y + (m == 12), (m % 12) + 1, 1) - dt.timedelta(days=1)
        out.append((first.strftime("%Y%m%d"), last.strftime("%Y%m%d"), "%04d%02d" % (y, m)))
    return out[skip:]


def collect(key, gate, interest, targets, quiet=False):
    """예산이 허락하는 만큼 모으고 캐시에 이어 붙인다.

    gate 는 목록 필터보다 느슨하게 준다. 기관의 경쟁률 감을 잡는 게 목적이라
    그 기관의 과거 공고면 신입이든 경력이든 표본으로 쓸모가 있다."""
    import scan                                   # gate/norm 재사용

    doc = load_cache()
    seen = set(doc["seen"])
    budget = Budget(BUDGET)
    added = 0

    # 상세 조회는 비싸다. 관심기관과 지금 목록에 뜨는 기관만 본다.
    tset = {_key(t) for t in targets}

    def is_target(inst):
        k = _key(inst)
        if k in tset:
            return True
        return any(_key(i) and _key(i) in k for i in interest)

    def enough(inst):
        # 이미 충분히 모인 기관은 더 볼 필요가 없다. 뒤로 갈수록
        # 상세 조회가 거의 안 생겨 남은 달을 훨씬 싸게 넘길 수 있다.
        return len(doc["inst"].get(inst) or []) >= ENOUGH_PER_INST

    def want(r):
        return (r["inst"] and is_target(r["inst"])
                and not enough(r["inst"]) and gate(r))

    try:
        for bgn, end, key_m in _months(MONTHS, SKIP_RECENT):
            if key_m in doc["done_months"]:
                continue

            pend = doc["pending"].get(key_m)
            if pend is None:
                # 이 달 목록을 모아 후보를 만든다.
                cand = []
                rows = ALIO_ROWS if _alio_fail[0] < ALIO_GIVEUP else 100
                for page in range(1, 40):
                    d = _api(key, "list", budget, numOfRows=rows, pageNo=page,
                             pbancBgngYmd=bgn, pbancEndYmd=end)
                    rs = d.get("result") or []
                    for x in rs:
                        r = scan.norm(x)
                        if r["sn"] not in seen and want(r):
                            cand.append([r["sn"], r["inst"]])
                    if len(rs) < rows:
                        break
                # 한전KPS 처럼 한 달에 공고를 100건씩 내는 기관이 있다.
                # 그런 기관이 예산을 통째로 먹지 않도록 기관별로 잘라
                # 번갈아 담는다. 관심기관은 각 바퀴에서 앞에 세운다.
                by = {}
                for row in cand:
                    by.setdefault(row[1], []).append(row)
                for rows in by.values():
                    del rows[PER_INST_MONTH:]

                def _first(row):
                    k = _key(row[1])
                    return 0 if any(_key(i) and _key(i) in k for i in interest) else 1

                pend, turn = [], 0
                while True:
                    wave = [rows[turn] for rows in by.values() if turn < len(rows)]
                    if not wave:
                        break
                    wave.sort(key=_first)
                    pend.extend(wave)
                    turn += 1
                doc["pending"][key_m] = pend

            while pend:
                sn, inst = pend[0]
                if enough(inst):
                    pend.pop(0)
                    continue
                try:
                    det = _api(key, "detail", budget, sn=sn)["result"]
                except (Budget.Stop, Quota):
                    raise
                except Exception:
                    # 못 읽은 건 seen 에 넣지 않는다. 넣어 버리면 영영
                    # 다시 안 보게 되어 그 달이 빈 채로 닫힌다.
                    pend.pop(0)
                    continue
                pend.pop(0)
                seen.add(sn)
                rs = rates(det)
                if rs:
                    year = str(det.get("pbancEndYmd") or "")[:4]
                    se = str(det.get("recrutSeNm") or "")
                    bucket = doc["inst"].setdefault(inst, [])
                    # 같은 표본이 두 번 들어가지 않게 한다. 그래야 이미 훑은
                    # 달을 다시 훑어도 숫자가 부풀지 않는다.
                    have = {(b.get("t"), b.get("r"), b.get("a")) for b in bucket}
                    for one in rs:
                        if (one["t"], one["r"], one["a"]) in have:
                            continue
                        one["y"] = year
                        one["se"] = se
                        bucket.append(one)
                    del bucket[:-MAX_PER_INST]
                    added += len(rs)

            doc["pending"].pop(key_m, None)
            doc["done_months"].append(key_m)
            # 한 달 끝날 때마다 저장한다. 중간에 멈춰도(타임아웃·강제종료)
            # 그때까지 쓴 API 호출이 헛돌지 않는다.
            doc["seen"] = sorted(seen)[-20000:]
            doc["updated"] = dt.date.today().isoformat()
            save_cache(doc)
            if not quiet:
                print("  %s 완료 (남은 호출 %d, 표본 %d건)"
                      % (key_m, budget.left,
                         sum(len(v) for v in doc["inst"].values())))
    except Quota:
        if not quiet:
            print("  ! 오늘 API 한도(1,000회)를 다 썼습니다. 내일 이어서 모읍니다")
    except Budget.Stop:
        if not quiet:
            print("  이번 실행 호출 한도(%d회) 소진 - 다음 실행에 이어서 모읍니다" % BUDGET)
    except Exception as e:
        if not quiet:
            print("  ! 경쟁률 수집 중단 (%s)" % type(e).__name__)

    doc["seen"] = sorted(seen)[-20000:]
    doc["updated"] = dt.date.today().isoformat()
    save_cache(doc)
    if not quiet:
        print("  기관 %d곳 / 표본 %d건 (이번에 %d건 추가)"
              % (len(doc["inst"]), sum(len(v) for v in doc["inst"].values()), added))
    return doc


def load(key, gate, interest, targets, force=False, quiet=False):
    doc = load_cache()
    if not force and doc["updated"]:
        try:
            age = (dt.date.today()
                   - dt.date(*map(int, doc["updated"].split("-")))).days
            if age <= MAX_AGE_DAYS:
                if not quiet:
                    print("  경쟁률 캐시 사용 (기관 %d곳, 표본 %d건)"
                          % (len(doc["inst"]), sum(len(v) for v in doc["inst"].values())))
                return doc
        except Exception:
            pass
    if not quiet:
        print("과거 공고에서 경쟁률 모으는 중…")
    return collect(key, gate, interest, targets, quiet=quiet)


def _flat(s):
    """직렬명 대조용. 대괄호·기호·공백을 털어 붙인다."""
    s = re.sub(r"[\[\](){}<>·,/\-_]", " ", str(s or ""))
    return re.sub(r"\s+", "", s)


def _same_series(sample_title, series):
    """표본의 직렬명이 이 공고의 직렬 중 하나와 같은 것인지."""
    a = _flat(sample_title)
    if len(a) < 2:
        return False
    for s in series or []:
        b = _flat(s)
        if len(b) >= 2 and (a in b or b in a):
            return True
    return False


def summary(inst_name, doc, prefer_new=True, series=None):
    """기관 하나의 요약. 중앙값과 표본을 돌려준다.

    신입 표본이 3건 이상이면 그것만 쓴다. 경력·인턴 공고는 경쟁률이
    성격이 달라 섞으면 왜곡된다."""
    rows = (doc.get("inst") or {}).get(inst_name)
    if not rows:
        return None
    kind = "표본"

    # 같은 기관도 직렬마다 경쟁률이 몇 배씩 차이 난다.
    # 이 공고의 직렬과 같은 표본이 있으면 그것만 쓴다.
    if series:
        same = [r for r in rows if _same_series(r.get("t"), series)]
        if same:
            vals = sorted(r["r"] for r in same)
            n = len(vals)
            med = vals[n // 2] if n % 2 else round((vals[n // 2 - 1] + vals[n // 2]) / 2, 1)
            return {"med": med, "n": n, "kind": "직렬",
                    "lo": vals[0], "hi": vals[-1],
                    "top": sorted(same, key=lambda r: -(r.get("a") or 0))[:6]}

    if prefer_new:
        fresh = [r for r in rows if "신입" in str(r.get("se") or "")]
        if len(fresh) >= 3:
            rows, kind = fresh, "신입"
    vals = sorted(r["r"] for r in rows)
    n = len(vals)
    med = vals[n // 2] if n % 2 else round((vals[n // 2 - 1] + vals[n // 2]) / 2, 1)
    top = sorted(rows, key=lambda r: -(r.get("a") or 0))[:6]
    return {"med": med, "n": n, "kind": kind,
            "lo": vals[0], "hi": vals[-1], "top": top}
