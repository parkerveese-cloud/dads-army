"""Shared set-up for the tests: a fresh, empty Dads Army for each test, and stand-ins for Home Assistant
and the public feeds, so nothing here touches the internet or a real Home Assistant.

Run everything from the repository folder with:  python3 -m unittest discover -s tests
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(os.path.dirname(HERE), "dadsarmy")
for _k in ("SUPERVISOR_TOKEN", "HASSIO_TOKEN", "DADSARMY_FEED_URLS"):
    os.environ.pop(_k, None)
os.environ["DADSARMY_DATA"] = tempfile.mkdtemp(prefix="dadsarmy-import-")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import server  # noqa: E402

REAL_FEED_URLS = dict(server.FEED_URLS)


class AppTest(unittest.TestCase):
    """Each test gets its own empty database and backup folder, with Home Assistant and warnings off."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="dadsarmy-test-")
        if server.DB is not None:
            try:
                server.DB.close()
            except Exception:
                pass
        server.DATA_DIR = self.dir
        server.DB_PATH = os.path.join(self.dir, "dadsarmy.db")
        server.BACKUP_DIR = os.path.join(self.dir, "backups")
        server.HA_TOKEN = ""
        server.HA_LAST.clear()
        server.RAN_OUT_PENDING.clear()
        server.HA_REBASE.clear()
        server.HA_HOME.update(lat=None, lon=None, at=0.0)
        server.ALERT_MEM.update(band={}, held={})   # 1.28.0: the level's memory of the last look
        # Every feed points nowhere (a closed port on this machine), so no test can reach the internet.
        # Tests that need a feed point it at FakeFeeds.
        server.FEED_URLS.clear()
        server.FEED_URLS.update(dict((k, "http://127.0.0.1:9/" + k) for k in REAL_FEED_URLS))
        server.LIVE_STATE.clear() if hasattr(server, "LIVE_STATE") else None
        with server.WARN_LOCK:
            server.WARN_STATE.clear()
            server.WARN_STATE.update({"items": [], "news": [], "sources": {}, "checked_at": None, "region": "",
                                      "seen": {}})
        self.real_http_get = server.http_get
        server.init_db()

    def tearDown(self):
        server.http_get = self.real_http_get
        server.HA_TOKEN = ""
        try:
            server.DB.close()
        finally:
            server.DB = None
            shutil.rmtree(self.dir, ignore_errors=True)

    # -- helpers ---------------------------------------------------------------------
    def add(self, name, qty=0, expiry=None, **fields):
        body = dict(fields, name=name, qty=qty)
        if expiry:
            body["expiry"] = expiry
        return server.api_item_create(body, {})["id"]

    def stock(self, item_id, qty, expiry=None, location=""):
        return server.api_stock_add({"qty": qty, "expiry": expiry, "location": location}, {}, str(item_id))

    def item(self, item_id):
        return [it for it in server.all_items() if it["id"] == item_id][0]

    def total(self, item_id):
        return sum(b["qty"] for b in self.item(item_id)["batches"])

    def assertApiError(self, status, fn, *args, **kw):
        with self.assertRaises(server.ApiError) as cm:
            fn(*args, **kw)
        self.assertEqual(cm.exception.status, status, cm.exception.message)
        return cm.exception


def days_from_today(n):
    import datetime as dt
    return (dt.date.today() + dt.timedelta(days=n)).isoformat()


# -- Running Dads Army's own web server, for tests of the HTTP side -----------------------
class AppServer(object):
    def __init__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.daemon_threads = True
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def call(self, method, path, body=None, ctype="application/json", raw=None):
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
        req = urllib.request.Request(self.base + path, method=method, data=data,
                                     headers={"Content-Type": ctype} if ctype else {})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                out = r.read()
                return r.status, out, dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def json(self, method, path, body=None, **kw):
        status, out, _ = self.call(method, path, body, **kw)
        return status, json.loads(out.decode("utf-8") or "{}")

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


# -- A stand-in for Home Assistant's REST API -------------------------------------------
class FakeHA(object):
    """Keeps states and events like Home Assistant. Set .down = True to answer 502, as the Supervisor
    does while Home Assistant restarts."""

    def __init__(self):
        self.states, self.events, self.deleted, self.down, self.requests = {}, [], [], False, []
        self.history = None   # what /api/history/period answers (None: 404, as with the recorder off)
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def reply(self, code, obj):
                body = json.dumps(obj).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def body(self):
                n = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(n) or b"{}") if n else {}

            def handle_any(self, method):
                fake.requests.append((method, self.path))
                if fake.down:
                    return self.reply(502, {"message": "Bad gateway"})
                if self.headers.get("Authorization") != "Bearer test-token":
                    return self.reply(401, {"message": "Unauthorized"})
                p = self.path
                if p.startswith("/api/states/"):
                    eid = p[len("/api/states/"):]
                    if method == "GET":
                        return self.reply(200, fake.states[eid]) if eid in fake.states else self.reply(404, {})
                    if method == "DELETE":
                        fake.deleted.append(eid)
                        fake.states.pop(eid, None)
                        return self.reply(200, {})
                    fake.states[eid] = self.body()
                    return self.reply(200, fake.states[eid])
                if p.startswith("/api/events/") and method == "POST":
                    fake.events.append((p[len("/api/events/"):], self.body()))
                    return self.reply(200, {"message": "ok"})
                if p.startswith("/api/history/period/"):
                    return self.reply(200, fake.history) if fake.history is not None else self.reply(404, {})
                if p == "/api/config":
                    return self.reply(200, {"latitude": 54.486, "longitude": -0.615})
                return self.reply(404, {})

            def do_GET(self):
                self.handle_any("GET")

            def do_POST(self):
                self.handle_any("POST")

            def do_DELETE(self):
                self.handle_any("DELETE")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.api = "http://127.0.0.1:%d/api" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def events_of(self, kind):
        return [e for k, e in self.events if k == kind]

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
