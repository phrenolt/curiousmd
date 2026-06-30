# CuriousMD

A local Markdown viewer and editor for the desktop. Spins up a loopback HTTP server, opens your browser, and lets you browse, open, read, and edit `.md` files — no cloud, no account, no external dependencies.

---

## Install / Uninstall

```sh
# Install (adds 'md' alias to ~/.bashrc + desktop entry)
bash install.sh
source ~/.bashrc

# Uninstall
bash uninstall.sh
```

The installer hard-codes the absolute path to `mdview.py` in the alias. If you move the project directory, re-run `install.sh`.

### Quick run (no install)

```sh
python3 mdview.py                # browse from current directory
python3 mdview.py README.md      # preload one file
python3 mdview.py docs/          # preload every .md file under docs/
```

---

## What it is

| Item | Detail |
|------|--------|
| Language | Python 3 (stdlib only — no pip installs) |
| Entry point | `mdview.py` |
| Server | `http.server.BaseHTTPRequestHandler` |
| Renderer | Custom Markdown-to-HTML parser (no third-party lib) |
| Install | `install.sh` / `uninstall.sh` (bash alias + `.desktop` entry) |

### Features

- Sidebar of open files — full paths shown, close (×) per file
- Filesystem browser (chrooted to launch directory, hidden files/dirs suppressed)
- Side-by-side edit mode: raw Markdown textarea + live-updating preview, save to disk (Ctrl+S / Escape to exit)
- In-page search with highlight, next/prev (Ctrl+F, `/`, F3)
- Browser tab shows reversed full path (`README.md › docs › home › …`)
- Rendered: headings, bold/italic/strike, code, fenced code blocks, blockquotes, ordered/unordered lists, tables, images, autolinks, horizontal rules
- Responsive layout (collapses to single column ≤ 820 px)

---

## Architecture

```
mdview.py                  HTTP routing + main() only
domains/
  markdown/renderer.py     md_to_html(), render_inline(), helpers
  docs/store.py            DocStore — thread-safe in-memory document store
  filesystem/browser.py    FilesystemBrowser — chrooted FS listing + file open
  auth/session.py          AuthSession — URL token + session cookie
  ui/template.py           Page builder (loads styles.css, app.js, template.html)
  ui/styles.css            All styles
  ui/app.js                All frontend logic
  ui/template.html         HTML shell
```

### API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Full page (URL-token-gated, sets session cookie) |
| GET | `/api/docs` | List open documents |
| GET | `/api/docs/<id>/html` | Render document to HTML |
| GET | `/api/docs/<id>/raw` | Return raw Markdown text |
| PUT | `/api/docs/<id>/content` | Write edited content to disk + update store |
| DELETE | `/api/docs/<id>` | Close a document |
| GET | `/api/fs` | Directory listing (chrooted) |
| GET | `/api/open` | Open a file from disk into the store |
| POST | `/api/preview` | Render arbitrary Markdown to HTML (live preview) |

CSS and JavaScript are inlined into the single HTML page returned at `/`. No assets are fetched from the network.

---

## Tests

```sh
bash run_tests.sh
```

85 tests across `domains/markdown/`, `domains/docs/`, `domains/filesystem/`, `domains/auth/`, and `domains/ui/`.

---

## Security Profile

### Authentication model

Two-token design:

1. **URL bootstrap token** — `secrets.token_urlsafe(32)`, generated at startup. Required only for `GET /`. Printed to the terminal and opened in the browser automatically.
2. **Session cookie** — `secrets.token_urlsafe(32)`, generated at startup. Issued as `Set-Cookie: session=…; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400` on the first successful page load. All API requests validate this cookie via `secrets.compare_digest()` (timing-safe). The URL token never appears in subsequent API calls.

This means the sensitive credential does not persist in browser history beyond the initial page open.

### Content Security Policy

A new `os.urandom(16)` nonce is generated per page render. CSP header sent with every HTML response:

```
default-src   'none'
script-src    'nonce-<per-render>'
style-src     'nonce-<per-render>'
img-src       'self' http: https:
connect-src   'self'
base-uri      'none'
form-action   'none'
frame-ancestors 'none'
object-src    'none'
```

Inline scripts and styles without the nonce are blocked, including anything injected via Markdown content.

### XSS prevention

**Server side**
- `html.escape()` on all Markdown-derived text before it enters HTML.
- URL scheme allowlisting via `_clean_url()`: rejects anything outside `{http, https, mailto, ""}` for links and `{http, https, ""}` for images. `javascript:`, `data:`, `vbscript:` etc. become `[blocked …]` spans.
- `json_for_script()` escapes `<`, `>`, `&`, and Unicode line/paragraph separators in bootstrap data.

**Client side (defence in depth)**
- `sanitizeMarkdownHTML()` re-validates server-rendered HTML against a strict tag and attribute allowlist before inserting into the DOM via `replaceChildren()`.
- `href`/`src` re-validated in-browser with `new URL()`.
- `class` restricted per tag to known-safe values (`lang-*`, `align-*`, `blocked-*`).
- `rel` forced to `noopener noreferrer`.

### Filesystem access

- Browser is **chrooted** to the launch directory — paths resolving outside `browse_root` are silently clamped back to root.
- Hidden files and directories (names starting with `.`) are suppressed in all listings.
- Only `.md .markdown .mdown .mkd .mdx` files can be opened or browsed.
- Files over 5 MB are rejected.
- `PUT /api/docs/<id>/content` writes only to files already tracked in the in-memory store — no arbitrary path writes.
- Asset serving uses `os.path.realpath()` + root prefix check — path traversal blocked.

### Other hardening

- `X-Content-Type-Options: nosniff` on every response.
- `Referrer-Policy: no-referrer`.
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`.
- `Cache-Control: no-store`.
- SVG assets served with `sandbox; default-src 'none'` CSP.
- `MAX_LINE_LEN = 4096` truncates long lines before regex to prevent catastrophic backtracking.
- Thread-safe document store (`threading.Lock`).
- Concurrent request handling via `ThreadingMixIn`.
- Default bind: `127.0.0.1` only.

---

### Residual risks

| Issue | Severity | Notes |
|-------|----------|-------|
| **No rate limiting** | Informational | stdlib server has no request rate limiter. Not a practical concern on localhost. |
| **No raw-HTML passthrough** | Feature gap / security benefit | Raw HTML in Markdown is escaped and shown as text. Secure by design, but deviates from CommonMark. |
| **Edit writes to disk as process owner** | Informational | `PUT /api/docs/<id>/content` writes with the permissions of the Python process. Any `.md` file opened into the store can be overwritten. This is intentional; only tracked files are writable. |
| **No TLS** | Informational | Localhost-only; acceptable trade-off. |

---

### Overall rating

**Low risk** for its intended use case (single-user, localhost, developer tool).

Layered defences — session cookie auth, per-render CSP nonces, server-side HTML escaping, client-side DOM sanitisation, filesystem chroot, and hidden-file suppression — go well above the bar for this class of application.
