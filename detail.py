# -*- coding: utf-8 -*-
"""
공고 상세(`/detail`)에서 목록 API 에 없는 것들을 가져온다.

목록 API 는 메타정보만 준다. 상세에는 세 가지가 더 있고 셋 다 쓸모가 크다.

  acbgCondNmLst  학력조건. 석·박사만 뽑는 공고를 걸러낼 수 있다
  files[]        공고문 첨부. 자격증 가점표가 이 안에 있다 (URL 은 갈아끼운다)
  steps[]        전형단계. sortNo 가 직렬이라 '직렬명'을 뽑아낼 수 있다

특히 직렬명이 중요하다. 통합공채는 NCS 대분류가 5~6개씩 붙어서 그것만으로는
그 공고에 내 직렬이 있는지 알 수 없는데, 직렬명을 보면 바로 안다.

공고당 1회 호출이라 sn 별로 캐시한다. 공고 내용은 잘 바뀌지 않으므로
CACHE_DAYS 동안은 다시 받지 않는다.
"""

import io
import json
import os
import time
import datetime as dt
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "detail.json")
BASE = "https://apis.data.go.kr/1051000/recruitment/detail"

ALIO_FILE = "https://www.alio.go.kr/download/download.json?fileNo=%s"

CACHE_DAYS = 7
SCHEMA = 2            # 캐시 형식. 올리면 예전 캐시를 통째로 버린다
MAX_FILES = 4
MAX_SERIES = 40
HEADERS = {"User-Agent": "gonggi-scanner/1.0"}


class Quota(Exception):
    """일일 한도 초과. 오늘은 더 못 부른다."""


def _load():
    if os.path.exists(CACHE):
        try:
            with io.open(CACHE, encoding="utf-8") as f:
                d = json.load(f)
            if (isinstance(d, dict) and isinstance(d.get("items"), dict)
                    and d.get("v") == SCHEMA):
                return d
        except Exception:
            pass
    return {"items": {}}


def _save(doc):
    doc["v"] = SCHEMA
    try:
        with io.open(CACHE, "w", encoding="utf-8") as f:
            f.write(json.dumps(doc, ensure_ascii=False))
    except OSError:
        pass


def _fetch(key, sn):
    q = urllib.parse.urlencode({"serviceKey": key, "resultType": "json", "sn": sn})
    req = urllib.request.Request(BASE + "?" + q, headers=HEADERS)
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                body = r.read().decode("utf-8", "replace")
            if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in body:
                raise Quota()
            return json.loads(body).get("result") or {}
        except urllib.error.HTTPError as e:
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


def extract(det):
    """상세 응답에서 쓸 것만 남긴다."""
    # 직렬명. 같은 직렬이 전형 단계마다 반복되므로 중복을 없앤다.
    series, seen = [], set()
    for s in det.get("steps") or []:
        t = (s.get("recrutPbancTtl") or "").strip()
        if t and t not in seen:
            seen.add(t)
            series.append(t[:60])
        if len(series) >= MAX_SERIES:
            break

    files = []
    for f in det.get("files") or []:
        name = (f.get("atchFileNm") or "").strip()
        no = f.get("recrutAtchFileNo")
        # API 가 주는 url(opendata.alio.go.kr/recruit/downloadAtchFile)은 죽었다.
        # 포털이 /new 로 개편되면서 파일 대신 API 안내 페이지(/new/main.do)로
        # 302 로 튕긴다. 알리오 본체의 다운로드는 살아 있고 같은 파일번호를 쓴다.
        url = (ALIO_FILE % no) if no else f.get("url")
        if url and name:
            files.append({"n": name[:70], "u": url})
        if len(files) >= MAX_FILES:
            break

    return {
        "acbg": (det.get("acbgCondNmLst") or "").strip(),
        "series": series,
        "files": files,
        "step": (det.get("scrnprcdrMthdExpln") or "").strip()[:400],
    }


def load(key, sns, budget=120, quiet=False):
    """필요한 공고만 받아 캐시에 채우고 {sn: 정보} 를 돌려준다."""
    doc = _load()
    items = doc["items"]
    today = dt.date.today().isoformat()
    fresh = 0

    need = []
    for sn in sns:
        cur = items.get(str(sn))
        if not cur:
            need.append(sn)
            continue
        try:
            age = (dt.date.today()
                   - dt.date(*map(int, cur.get("d", "2000-01-01").split("-")))).days
        except Exception:
            age = 999
        if age > CACHE_DAYS:
            need.append(sn)

    if need and not quiet:
        print("공고 상세 %d건 받는 중… (캐시 %d건)" % (min(len(need), budget), len(items)))

    try:
        for sn in need[:budget]:
            one = extract(_fetch(key, sn))
            one["d"] = today
            items[str(sn)] = one
            fresh += 1
            time.sleep(0.05)
    except Quota:
        if not quiet:
            print("  ! 오늘 API 한도를 다 썼습니다. 받은 것까지만 씁니다")
    except Exception as e:
        if not quiet:
            print("  ! 상세 조회 중단 (%s). 받은 것까지만 씁니다" % type(e).__name__)

    # 오래된 공고는 캐시에서 덜어낸다. 안 그러면 파일이 계속 커진다.
    if len(items) > 1200:
        keep = sorted(items.items(), key=lambda kv: kv[1].get("d", ""), reverse=True)
        doc["items"] = dict(keep[:800])

    _save(doc)
    if fresh and not quiet:
        print("  상세 %d건 새로 받음 (캐시 %d건)" % (fresh, len(doc["items"])))
    return doc["items"]


# ---------------------------------------------------------------- 학력

# 목록에 남길 학력조건. 하나라도 걸치면 통과다.
# 값이 비어 있는 공고는 알 수 없으니 통과시킨다.
def acbg_ok(info, want):
    if not want or not info:
        return True
    v = info.get("acbg") or ""
    if not v:
        return True
    toks = {t.strip() for t in v.split(",") if t.strip()}
    return bool(toks & set(want))
