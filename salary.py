# -*- coding: utf-8 -*-
"""
알리오 경영공시에서 기관별 보수 정보를 받아 온다.

채용 API(잡알리오)에는 급여 항목이 아예 없다. 대신 알리오 본체의
'통계분석 > 단일항목 통계'가 인증키 없이 열려 있어 그쪽을 쓴다.

  엔드포인트 https://www.alio.go.kr/statisticsSearch/findSingleItemSearchList.json
  파라미터   reportFormNo=20601 (직원 평균보수 현황), itemNo, pageNo, countPerPage
  응답       기관 355곳 × yy0~yy5 (yy0 이 최신 연도 = 페이지의 alioYear)
  단위       천원 (평균근속연수만 월)

countPerPage 는 100 이 상한이라 항목당 4페이지씩 돈다. 총 12회.
연 1회 갱신되는 공시라 salary.json 에 캐시하고 30일이 지나야 다시 받는다.
"""

import io
import json
import os
import re
import time
import datetime as dt
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "salary.json")

BASE = "https://www.alio.go.kr/statisticsSearch/findSingleItemSearchList.json"
PAGE = "https://www.alio.go.kr/statisticsSearch/singleStatisticsSearch.do"
FORM = "20601"

# 20601 보고서 안의 항목 번호. 트리(findItemTreeList.json)에서 확인한 값.
ITEMS = {
    "pay": "GI0208",   # 신입사원 초임 - 합계
    "avg": "GI0101",   # 정규직(일반정규직) 1인당 평균 보수액
    "mon": "GI0110",   # 정규직(일반정규직) 평균근속연수 (단위: 월)
}

MAX_AGE_DAYS = 30
HEADERS = {"Referer": PAGE, "User-Agent": "gonggi-scanner/1.0"}


def norm(name):
    """기관명 대조용 키. (주)·(재) 같은 접두와 공백·기호를 털어낸다."""
    s = re.sub(r"\((주|재|사|사단법인|재단법인|학교법인)\)", "", str(name or ""))
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s)


def _get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _year():
    """공시 기준연도. 페이지에 alioYear 로 박혀 있어 그대로 읽는다."""
    try:
        m = re.search(r'alioYear\s*=\s*"(\d{4})"', _get(PAGE))
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return dt.date.today().year


def _fetch_item(item_no):
    out = {}
    for page in range(1, 8):
        q = urllib.parse.urlencode({
            "pageNo": page, "countPerPage": 100,
            "reportFormNo": FORM, "itemNo": item_no,
        })
        doc = json.loads(_get(BASE + "?" + q))
        rows = (doc.get("data") or {}).get("result") or []
        for r in rows:
            out[r.get("apbaNa", "")] = r.get("yy0")
        if len(rows) < 100:
            break
        time.sleep(0.15)
    return out


def fetch():
    """{정규화기관명: {name, pay, avg, mon}} 를 만든다. 보수는 천원, 근속은 월."""
    year = _year()
    cols = {k: _fetch_item(v) for k, v in ITEMS.items()}

    def num(v):
        try:
            return int(float(str(v).replace(",", "")))
        except (TypeError, ValueError):
            return None

    data = {}
    for name in cols["pay"]:
        rec = {"name": name,
               "pay": num(cols["pay"].get(name)),
               "avg": num(cols["avg"].get(name))}
        rec["mon"] = num(cols["mon"].get(name))
        if rec["pay"] or rec["avg"]:
            data[norm(name)] = rec
    return {"fetched": dt.date.today().isoformat(), "year": year, "data": data}


def load(force=False, quiet=False):
    """캐시가 신선하면 그대로, 아니면 새로 받는다. 실패하면 빈 dict."""
    doc = None
    if os.path.exists(CACHE) and not force:
        try:
            with io.open(CACHE, encoding="utf-8") as f:
                doc = json.load(f)
            age = (dt.date.today() - dt.date(*map(int, doc["fetched"].split("-")))).days
            if age <= MAX_AGE_DAYS and doc.get("data"):
                if not quiet:
                    print("  보수 정보 캐시 사용 (%s, 기관 %d곳)"
                          % (doc["fetched"], len(doc["data"])))
                return doc
        except Exception:
            doc = None

    try:
        if not quiet:
            print("알리오 경영공시에서 보수 정보 받는 중…")
        fresh = fetch()
        with io.open(CACHE, "w", encoding="utf-8") as f:
            f.write(json.dumps(fresh, ensure_ascii=False))
        if not quiet:
            print("  %d년 공시 기준 기관 %d곳" % (fresh["year"], len(fresh["data"])))
        return fresh
    except Exception as e:
        # 보수는 부가 정보다. 못 받아도 채용 목록은 그대로 나와야 한다.
        if not quiet:
            print("  ! 보수 정보를 받지 못했습니다 (%s). 연봉 칸은 비워 둡니다."
                  % type(e).__name__)
        return doc or {"fetched": "", "year": 0, "data": {}}


def attach(inst_name, doc):
    """기관명으로 찾아 {pay, avg, mon} 을 돌려준다. 없으면 None."""
    return (doc.get("data") or {}).get(norm(inst_name))


if __name__ == "__main__":
    d = load(force=True)
    print("기준연도", d["year"], "· 기관", len(d["data"]))
    for k in ("한국환경공단", "한국전력공사", "한국동서발전(주)"):
        print(" ", k, attach(k, d))
