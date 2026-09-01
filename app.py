# -*- coding: utf-8 -*-
"""
클라우드타입(CloudType) 배포용 웹서버.

로컬에서는 scan.py 가 HTML 을 만들고 브라우저를 띄우지만, 서버에서는
그럴 수 없다. 그래서 이 파일이
  1) 뜨자마자 한 번 목록을 만들고
  2) REFRESH_HOURS 마다 백그라운드로 다시 만들고
  3) 만들어진 HTML 을 그냥 서빙한다.

외부 라이브러리를 쓰지 않는다. 표준 라이브러리만 있으면 돌아간다.

환경변수
  SERVICE_KEY    (필수) data.go.kr 일반 인증키(Decoding)
  PORT           서버 포트. 클라우드타입이 넣어 준다. 기본 8080
  REFRESH_HOURS  목록 갱신 주기(시간). 기본 6
  REBUILD_TOKEN  설정하면 /rebuild?token=... 로 수동 갱신 가능
"""

import os
import sys
import threading
import traceback
import datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# scan.py 안의 대화형 처리(input, 브라우저 띄우기)를 끈다.
os.environ["GONGGI_SERVER"] = "1"

import scan  # noqa: E402

PORT = int(os.environ.get("PORT") or 8080)
REFRESH_HOURS = float(os.environ.get("REFRESH_HOURS") or 6)
REBUILD_TOKEN = os.environ.get("REBUILD_TOKEN") or ""
KST = dt.timezone(dt.timedelta(hours=9))

STATE = {"html": None, "built": None, "error": None, "count": 0}
LOCK = threading.Lock()


def log(msg):
    print("[%s] %s" % (dt.datetime.now(KST).strftime("%m-%d %H:%M:%S"), msg),
          flush=True)


ERROR_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>공공기관 채용정보 — 준비 중</title>
<style>body{font:15px/1.8 "Noto Sans KR",sans-serif;color:#333;
max-width:640px;margin:80px auto;padding:0 24px}
h1{font-size:22px;color:#6162d4}pre{background:#f4f4f4;padding:14px;
border-radius:6px;font-size:12px;overflow:auto;color:#666}</style></head>
<body><h1>목록을 아직 만들지 못했습니다</h1>
<p>%s</p><pre>%s</pre>
<p>인증키(<code>SERVICE_KEY</code>) 환경변수가 들어갔는지 확인해 주세요.
잠시 뒤 새로고침하면 다시 시도한 결과가 보입니다.</p></body></html>"""


def build():
    """목록을 새로 만들어 메모리에 올린다. 실패해도 서버는 죽지 않는다."""
    try:
        log("목록 생성 시작")
        html, count = scan.build_html()
        with LOCK:
            STATE["html"] = html
            STATE["built"] = dt.datetime.now(KST)
            STATE["count"] = count
            STATE["error"] = None
        log("목록 생성 완료 — %d건" % count)
    except Exception as e:
        detail = traceback.format_exc(limit=3)
        with LOCK:
            STATE["error"] = "%s: %s" % (type(e).__name__, e)
        log("목록 생성 실패 — %s" % STATE["error"])
        log(detail)


def loop():
    """첫 생성 뒤 주기적으로 다시 만든다."""
    build()
    while True:
        # 실패했으면 5분 뒤 다시, 성공했으면 정해진 주기로.
        wait = 300 if STATE["error"] else REFRESH_HOURS * 3600
        if threading.Event().wait(wait):
            return
        build()


class Handler(BaseHTTPRequestHandler):
    server_version = "gonggi-scanner"

    def log_message(self, fmt, *args):
        pass                                    # 접속 로그는 남기지 않는다

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path.rstrip("/") or "/"

        if path == "/health":
            ok = STATE["html"] is not None
            self._send(200 if ok else 503,
                       "ok %d건" % STATE["count"] if ok else "building",
                       "text/plain; charset=utf-8")
            return

        if path == "/rebuild":
            token = (parse_qs(u.query).get("token") or [""])[0]
            if not REBUILD_TOKEN or token != REBUILD_TOKEN:
                self._send(403, "forbidden", "text/plain; charset=utf-8")
                return
            threading.Thread(target=build, daemon=True).start()
            self._send(202, "rebuilding", "text/plain; charset=utf-8")
            return

        if path != "/":
            self._send(404, "not found", "text/plain; charset=utf-8")
            return

        with LOCK:
            html, err = STATE["html"], STATE["error"]
        if html:
            self._send(200, html)
        else:
            msg = "첫 목록을 만드는 중입니다. 20초쯤 뒤에 새로고침해 주세요." \
                if not err else "목록을 만들다 오류가 났습니다."
            self._send(503, ERROR_PAGE % (msg, err or ""))


def main():
    if not scan.service_key():
        log("! SERVICE_KEY 환경변수가 비어 있습니다. 그래도 서버는 띄웁니다.")
    threading.Thread(target=loop, daemon=True).start()
    log("포트 %d 에서 대기 (갱신 주기 %g시간)" % (PORT, REFRESH_HOURS))
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
