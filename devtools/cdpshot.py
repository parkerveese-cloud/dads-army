#!/usr/bin/env python3
"""Tiny CDP screenshotter (stdlib only).
usage: cdpshot.py OUTDIR W:MODE[,W:MODE...] view[,view...] [maxheight] [js]
Starts headless Chrome once, emulates width + colour scheme, full-page screenshot.
"""
import base64, json, os, socket, struct, subprocess, sys, tempfile, time, urllib.request

PORT = int(os.environ.get("CDP_PORT", "9339"))  # give each parallel user its own port
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class WS:
    def __init__(self, url):
        assert url.startswith("ws://")
        hostport, path = url[5:].split("/", 1)
        host, port = hostport.split(":")
        self.s = socket.create_connection((host, int(port)))
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.s.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(4096)
        self.rest = buf.split(b"\r\n\r\n", 1)[1]
        self.id = 0

    def _recv(self, n):
        while len(self.rest) < n:
            d = self.s.recv(1 << 20)
            if not d:
                raise EOFError
            self.rest += d
        out, self.rest = self.rest[:n], self.rest[n:]
        return out

    def recv(self):
        data = b""
        while True:
            h = self._recv(2)
            fin, op, ln = h[0] & 0x80, h[0] & 0xF, h[1] & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._recv(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._recv(8))[0]
            data += self._recv(ln)
            if fin:
                return json.loads(data)

    def send(self, method, params=None):
        self.id += 1
        msg = json.dumps({"id": self.id, "method": method, "params": params or {}}).encode()
        mask = os.urandom(4)
        hdr = bytes([0x81])
        n = len(msg)
        if n < 126:
            hdr += bytes([0x80 | n])
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
        self.s.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(msg)))
        while True:
            r = self.recv()
            if r.get("id") == self.id:
                if "error" in r:
                    raise RuntimeError(r["error"])
                return r.get("result", {})


def main():
    outdir, combos, views = sys.argv[1], sys.argv[2].split(","), sys.argv[3].split(",")
    maxh = int(sys.argv[4]) if len(sys.argv) > 4 else 4000
    js = sys.argv[5] if len(sys.argv) > 5 else ""
    base = os.environ.get("BASE", "http://127.0.0.1:18101/")
    os.makedirs(outdir, exist_ok=True)
    prof = tempfile.mkdtemp()
    p = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={PORT}",
                          f"--user-data-dir={prof}", "--no-first-run", "about:blank"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                break
            except Exception:
                time.sleep(0.2)
        page = [t for t in tabs if t["type"] == "page"][0]
        ws = WS(page["webSocketDebuggerUrl"])
        ws.send("Page.enable")
        ws.send("Runtime.enable")
        for combo in combos:
            w, mode = combo.split(":")
            w = int(w)
            for v in views:
                ws.send("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": w < 700})
                ws.send("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": mode}]})
                ws.send("Page.navigate", {"url": base + "#" + v})
                time.sleep(2.2)
                ws.send("Runtime.evaluate", {"expression": "location.hash='" + v + "'"})
                time.sleep(0.6)
                if js:
                    ws.send("Runtime.evaluate", {"expression": js})
                    time.sleep(0.6)
                r = ws.send("Runtime.evaluate", {"expression": "JSON.stringify([document.documentElement.scrollHeight, document.documentElement.scrollWidth, innerWidth])", "returnByValue": True})
                sh, sw, iw = json.loads(r["result"]["value"])
                h = min(sh, maxh) if not js.startswith("DA.open") else 900
                ws.send("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": w < 700})
                time.sleep(0.5)
                shot = ws.send("Page.captureScreenshot", {"format": "png"})
                fn = os.path.join(outdir, f"{v.split('?')[0]}-{w}-{mode}.png")
                open(fn, "wb").write(base64.b64decode(shot["data"]))
                print(fn, "scrollH", sh, "scrollW", sw, "innerW", iw, "OVERFLOW" if sw > iw else "")
    finally:
        p.terminate()


main()
