import base64
import json
import os

_UI_DIR = os.path.dirname(os.path.abspath(__file__))

_CSS = None
_JS = None
_PAGE = None


def _assets():
    global _CSS, _JS, _PAGE
    if _CSS is None:
        with open(os.path.join(_UI_DIR, "styles.css"), "r", encoding="utf-8") as f:
            _CSS = f.read()
        with open(os.path.join(_UI_DIR, "app.js"), "r", encoding="utf-8") as f:
            _JS = f.read()
        with open(os.path.join(_UI_DIR, "template.html"), "r", encoding="utf-8") as f:
            _PAGE = f.read()
    return _CSS, _JS, _PAGE


def json_for_script(obj):
    return (json.dumps(obj)
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))


def render_index(docs, active, browse_root, browse_path):
    css, js, page = _assets()
    bootstrap = {
        "docs": docs,
        "active": active,
        "browse_root": browse_root,
        "browse_path": browse_path,
    }
    nonce = base64.b64encode(os.urandom(16)).decode("ascii")
    body = page.format(
        css=css,
        js=js,
        bootstrap=json_for_script(bootstrap),
        nonce=nonce,
    )
    return body, nonce
