#!/usr/bin/env python3
"""CuriousMD — local Markdown viewer and editor, stdlib only.

Usage:
    python3 mdview.py                # browse Markdown files from current dir
    python3 mdview.py README.md      # preloads a file
    python3 mdview.py docs/          # preloads every .md file under docs/
"""

import argparse
import json
import os
import re
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

from domains.auth.session import auth
from domains.docs.store import store
from domains.filesystem.browser import browser, MD_EXTS, MAX_FILE_SIZE
from domains.markdown.renderer import md_to_html
from domains.ui.template import render_index

_asset_root = None  # set at startup; used only to serve bundled static files


# ---------- HTTP handler ----------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _check_session(self):
        ok = auth.check_session(self.headers.get("Cookie", ""))
        if not ok:
            self._send_json({"error": "forbidden"}, status=403)
        return ok

    # ---------- response helpers ----------

    def _send(self, status, ctype, data, extra_headers=None):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, body, status=200, nonce=None, set_session=False):
        headers = {}
        if nonce:
            headers["Content-Security-Policy"] = (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; "
                f"style-src 'nonce-{nonce}'; "
                "img-src 'self' http: https:; "
                "connect-src 'self'; "
                "base-uri 'none'; "
                "form-action 'none'; "
                "frame-ancestors 'none'; "
                "object-src 'none'"
            )
        if set_session:
            headers["Set-Cookie"] = auth.make_set_cookie()
        self._send(status, "text/html; charset=utf-8", body, headers)

    def _send_json(self, obj, status=200):
        self._send(status, "application/json; charset=utf-8", json.dumps(obj))

    def _send_file(self, path):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            self.send_error(404)
            return
        ext = os.path.splitext(path)[1].lower()
        ctype = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".svg": "image/svg+xml",
            ".webp": "image/webp", ".ico": "image/x-icon",
        }.get(ext, "application/octet-stream")
        headers = {}
        if ext == ".svg":
            headers["Content-Security-Policy"] = (
                "sandbox; default-src 'none'; img-src 'self' data:; "
                "style-src 'unsafe-inline'"
            )
        self._send(200, ctype, data, headers)

    # ---------- routing ----------

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        if path in ("/", ""):
            params = urllib.parse.parse_qs(parsed.query)
            token = params.get("token", [""])[0]
            if not auth.check_url_token(token):
                self._send(403, "text/plain; charset=utf-8",
                           "403 Forbidden — invalid or missing token")
                return
            body, nonce = self._render_index()
            return self._send_html(body, nonce=nonce, set_session=True)

        if path == "/api/docs":
            if not self._check_session():
                return
            return self._send_json({"docs": store.list()})

        if path == "/api/fs":
            if not self._check_session():
                return
            browse_path = urllib.parse.parse_qs(parsed.query).get("path", [""])[0]
            listing = browser.list_dir(browse_path)
            if listing is None:
                return self._send_json({"error": "not found"}, status=404)
            return self._send_json(listing)

        if path == "/api/open":
            if not self._check_session():
                return
            file_path = urllib.parse.parse_qs(parsed.query).get("path", [""])[0]
            doc, err = browser.open_file(file_path, store.add)
            if not doc:
                return self._send_json({"error": err or "unable to open"}, status=400)
            return self._send_json(doc, status=201)

        m = re.match(r"^/api/docs/([^/]+)/html$", path)
        if m:
            if not self._check_session():
                return
            doc = store.get(m.group(1))
            if not doc:
                return self.send_error(404)
            return self._send_json({
                "id": doc["id"], "name": doc["name"],
                "dir": doc.get("dir", ""), "html": md_to_html(doc["content"]),
            })

        m = re.match(r"^/api/docs/([^/]+)/raw$", path)
        if m:
            if not self._check_session():
                return
            doc = store.get(m.group(1))
            if not doc:
                return self.send_error(404)
            return self._send_json({
                "id": doc["id"], "name": doc["name"],
                "dir": doc.get("dir", ""), "raw": doc["content"],
            })

        if _asset_root and path != "/":
            rel = path.lstrip("/")
            full = self._resolve_asset(rel)
            if full and os.path.isfile(full):
                return self._send_file(full)

        self.send_error(404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        m = re.match(r"^/api/docs/([^/]+)$", path)
        if m:
            if not self._check_session():
                return
            ok = store.remove(m.group(1))
            return self._send_json({"ok": ok}, status=200 if ok else 404)

        self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        if path == "/api/preview":
            if not self._check_session():
                return
            length = int(self.headers.get("Content-Length", 0))
            md = self.rfile.read(min(length, MAX_FILE_SIZE)).decode("utf-8", errors="replace")
            return self._send_json({"html": md_to_html(md)})

        self.send_error(404)

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        m = re.match(r"^/api/docs/([^/]+)/content$", path)
        if m:
            if not self._check_session():
                return
            doc = store.get(m.group(1))
            if not doc:
                return self._send_json({"error": "not found"}, status=404)
            if not doc.get("dir"):
                return self._send_json({"error": "file path unknown"}, status=400)
            length = int(self.headers.get("Content-Length", 0))
            new_content = self.rfile.read(min(length, MAX_FILE_SIZE)).decode("utf-8", errors="replace")
            full_path = os.path.join(doc["dir"], doc["name"])
            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
            except OSError as e:
                return self._send_json({"error": str(e)}, status=500)
            store.update(m.group(1), new_content)
            return self._send_json({"ok": True})

        self.send_error(404)

    # ---------- helpers ----------

    def _resolve_asset(self, rel):
        rel = rel.replace("\\", "/").lstrip("/")
        full = os.path.realpath(os.path.join(_asset_root, rel))
        root = os.path.realpath(_asset_root)
        if not (full == root or full.startswith(root + os.sep)):
            return None
        return full

    def _render_index(self):
        docs = store.list()
        active = docs[0]["id"] if docs else None
        root = browser.root or os.path.realpath(os.getcwd())
        return render_index(docs, active, root, root)


# ---------- startup ----------

def preload_path(path):
    global _asset_root
    if os.path.isfile(path):
        abs_path = os.path.abspath(path)
        _asset_root = os.path.dirname(abs_path) or os.getcwd()
        browser.root = os.path.realpath(_asset_root)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            store.add(os.path.basename(path), f.read(), dir=_asset_root)
        return
    if os.path.isdir(path):
        _asset_root = os.path.abspath(path)
        browser.root = os.path.realpath(_asset_root)
        found = []
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fn in filenames:
                if fn.lower().endswith(MD_EXTS):
                    found.append(os.path.join(dirpath, fn))
        found.sort(key=str.lower)
        for full in found:
            abs_full = os.path.abspath(full)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    store.add(os.path.basename(full), f.read(),
                              dir=os.path.dirname(abs_full))
            except OSError:
                pass


def main():
    global _asset_root
    try:
        with open("/proc/self/comm", "w") as _f:
            _f.write("CuriousMD")
    except OSError:
        pass

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("path", nargs="?", help="Optional file or directory to preload")
    p.add_argument("-p", "--port", type=int, default=0,
                   help="Port (default: auto-pick free port)")
    p.add_argument("--host", default="127.0.0.1", help="Bind host")
    p.add_argument("--no-browser", action="store_true",
                   help="Don't open a browser window")
    args = p.parse_args()

    if args.path:
        target = os.path.abspath(args.path)
        if not os.path.exists(target):
            print(f"error: not found: {target}", file=sys.stderr)
            sys.exit(1)
        preload_path(target)
    else:
        _asset_root = os.getcwd()
        browser.root = os.path.realpath(_asset_root)

    auth.init_tokens()

    try:
        server = ThreadedHTTPServer((args.host, args.port), Handler)
    except OSError as e:
        print(f"error: failed to bind to {args.host}:{args.port}: {e}", file=sys.stderr)
        sys.exit(1)
    port = server.server_address[1]
    url = f"http://{args.host}:{port}/?token={auth.token}"
    n = len(store.list())
    print(f"Serving {n} preloaded doc(s) from {_asset_root}\n  → {url}\n"
          f"Press Ctrl+C to stop.")

    if not args.no_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye.")
        server.shutdown()


if __name__ == "__main__":
    main()
