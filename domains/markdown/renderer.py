import html
import re
import urllib.parse

LINK_SCHEMES = {"", "http", "https", "mailto"}
IMAGE_SCHEMES = {"", "http", "https"}
MAX_LINE_LEN = 4096

INLINE_RE = re.compile(
    r"(?P<code>`([^`\n]+)`)"
    r"|(?P<bi>\*\*\*([^*\n]+)\*\*\*)"
    r"|(?P<bold>\*\*([^*\n]+)\*\*|__([^_\n]+)__)"
    r"|(?P<italic>\*([^*\n]+)\*|(?<![A-Za-z0-9_])_([^_\n]+)_(?![A-Za-z0-9_]))"
    r"|(?P<strike>~~([^~\n]+)~~)"
    r"|(?P<image>!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\))"
    r"|(?P<link>\[([^\]]+)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\))"
    r"|(?P<autolink><(https?://[^>\s]+)>)"
)


def _clean_url(url, allowed_schemes):
    if not url:
        return None
    cleaned = "".join(ch for ch in url.strip() if ch >= " " and ch != "\x7f")
    if not cleaned:
        return None
    try:
        parts = urllib.parse.urlsplit(cleaned)
    except ValueError:
        return None
    if parts.scheme.lower() not in allowed_schemes:
        return None
    return cleaned


def render_inline(text):
    if len(text) > MAX_LINE_LEN:
        text = text[:MAX_LINE_LEN] + "…"
    out = []
    pos = 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            out.append(html.escape(text[pos:m.start()]))
        kind = m.lastgroup
        if kind == "code":
            out.append(f"<code>{html.escape(m.group(2))}</code>")
        elif kind == "bi":
            out.append(f"<strong><em>{html.escape(m.group(4))}</em></strong>")
        elif kind == "bold":
            out.append(f"<strong>{html.escape(m.group(6) or m.group(7))}</strong>")
        elif kind == "italic":
            out.append(f"<em>{html.escape(m.group(9) or m.group(10))}</em>")
        elif kind == "strike":
            out.append(f"<del>{html.escape(m.group(12))}</del>")
        elif kind == "image":
            alt = html.escape(m.group(14) or "")
            src = _clean_url(m.group(15), IMAGE_SCHEMES)
            if src is None:
                out.append(f'<span class="blocked-image">[blocked image: {alt}]</span>')
            else:
                src_attr = html.escape(src, quote=True)
                title = m.group(16)
                t_attr = f' title="{html.escape(title, quote=True)}"' if title else ""
                out.append(f'<img alt="{alt}" src="{src_attr}"{t_attr} loading="lazy" decoding="async">')
        elif kind == "link":
            label = render_inline(m.group(18))
            href = _clean_url(m.group(19), LINK_SCHEMES)
            if href is None:
                out.append(f'<span class="blocked-link">{label}</span>')
            else:
                href_attr = html.escape(href, quote=True)
                title = m.group(20)
                t_attr = f' title="{html.escape(title, quote=True)}"' if title else ""
                out.append(f'<a href="{href_attr}"{t_attr} rel="noopener noreferrer">{label}</a>')
        elif kind == "autolink":
            raw_url = m.group(22)
            url = _clean_url(raw_url, LINK_SCHEMES)
            label = html.escape(raw_url)
            if url is None:
                out.append(f'<span class="blocked-link">{label}</span>')
            else:
                href = html.escape(url, quote=True)
                out.append(f'<a href="{href}" rel="noopener noreferrer">{label}</a>')
        pos = m.end()
    if pos < len(text):
        out.append(html.escape(text[pos:]))
    return "".join(out)


def slugify(text):
    s = re.sub(r"<[^>]+>", "", text).lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or "section"


def md_to_html(md):
    lines = md.splitlines()
    out = []
    i = 0
    seen_slugs = {}

    def heading(level, text):
        rendered = render_inline(text)
        base = slugify(text)
        n = seen_slugs.get(base, 0)
        seen_slugs[base] = n + 1
        slug = base if n == 0 else f"{base}-{n}"
        return f'<h{level} id="{slug}">{rendered}</h{level}>'

    while i < len(lines):
        raw = lines[i]

        m = re.match(r"^```(\w*)\s*$", raw)
        if m:
            lang = m.group(1)
            i += 1
            buf = []
            while i < len(lines) and not re.match(r"^```\s*$", lines[i]):
                buf.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            cls = f' class="lang-{html.escape(lang)}"' if lang else ""
            code = html.escape("\n".join(buf))
            out.append(f"<pre><code{cls}>{code}</code></pre>")
            continue

        if not raw.strip():
            i += 1
            continue

        if re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", raw):
            out.append("<hr>")
            i += 1
            continue

        h = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", raw)
        if h:
            out.append(heading(len(h.group(1)), h.group(2)))
            i += 1
            continue

        if i + 1 < len(lines) and raw.strip():
            nxt = lines[i + 1]
            if not re.match(r"^\s*([-*+]\s|\d+\.\s|>|#{1,6}\s|```)", raw):
                if re.match(r"^=+\s*$", nxt):
                    out.append(heading(1, raw.strip()))
                    i += 2
                    continue
                if re.match(r"^-+\s*$", nxt):
                    out.append(heading(2, raw.strip()))
                    i += 2
                    continue

        if re.match(r"^>\s?", raw):
            block = []
            while i < len(lines) and re.match(r"^>\s?", lines[i]):
                block.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            inner = md_to_html("\n".join(block))
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        if re.match(r"^\s*[-*+]\s+", raw) or re.match(r"^\s*\d+\.\s+", raw):
            i = _render_list(lines, i, out, base_indent=0)
            continue

        if (raw.lstrip().startswith("|") and i + 1 < len(lines)
                and _is_table_sep(lines[i + 1])):
            header = _split_row(raw)
            aligns = [_cell_align(c) for c in _split_row(lines[i + 1])]
            rows = []
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(_split_row(lines[i]))
                i += 1
            out.append(_render_table(header, aligns, rows))
            continue

        para = [raw]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|>|\s*[-*+]\s+|\s*\d+\.\s+|```|---+\s*$|===+\s*$)",
            lines[i],
        ):
            para.append(lines[i])
            i += 1
        out.append(f"<p>{render_inline(' '.join(p.strip() for p in para))}</p>")

    return "\n".join(out)


def _render_list(lines, i, out, base_indent):
    first = lines[i]
    indent = len(first) - len(first.lstrip(" "))
    if indent < base_indent:
        return i
    ordered = bool(re.match(r"^\s*\d+\.\s+", first))
    tag = "ol" if ordered else "ul"
    item_re = (re.compile(r"^(\s*)(\d+)\.\s+(.*)$") if ordered
               else re.compile(r"^(\s*)([-*+])\s+(.*)$"))

    out.append(f"<{tag}>")
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        m = item_re.match(ln)
        if not m:
            break
        cur_indent = len(m.group(1))
        if cur_indent < indent:
            break
        if cur_indent > indent:
            i = _render_list(lines, i, out, base_indent=cur_indent)
            continue
        content = m.group(3)
        i += 1
        cont = []
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(\s*[-*+]\s+|\s*\d+\.\s+|#{1,6}\s|>|```)", lines[i]
        ):
            cont.append(lines[i].strip())
            i += 1
        if cont:
            content = content + " " + " ".join(cont)
        nested = []
        if (i < len(lines) and re.match(r"^\s+([-*+]|\d+\.)\s+", lines[i])
                and (len(lines[i]) - len(lines[i].lstrip(" "))) > indent):
            sub = []
            i = _render_list(lines, i, sub, base_indent=indent + 1)
            nested = sub
        item_html = render_inline(content)
        if nested:
            out.append(f"<li>{item_html}\n" + "\n".join(nested) + "</li>")
        else:
            out.append(f"<li>{item_html}</li>")
    out.append(f"</{tag}>")
    return i


_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def _is_table_sep(line):
    return bool(_TABLE_SEP_RE.match(line)) and "|" in line


def _split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells = []
    cur = []
    j = 0
    while j < len(s):
        ch = s[j]
        if ch == "\\" and j + 1 < len(s) and s[j + 1] == "|":
            cur.append("|")
            j += 2
            continue
        if ch == "|":
            cells.append("".join(cur).strip())
            cur = []
            j += 1
            continue
        cur.append(ch)
        j += 1
    cells.append("".join(cur).strip())
    return cells


def _cell_align(cell):
    c = cell.strip()
    left = c.startswith(":")
    right = c.endswith(":")
    if left and right:
        return "center"
    if right:
        return "right"
    if left:
        return "left"
    return None


def _align_attr(a):
    return f' class="align-{a}"' if a else ""


def _render_table(header, aligns, rows):
    parts = ["<table><thead><tr>"]
    for i, cell in enumerate(header):
        a = aligns[i] if i < len(aligns) else None
        parts.append(f"<th{_align_attr(a)}>{render_inline(cell)}</th>")
    parts.append("</tr></thead><tbody>")
    width = len(header)
    for row in rows:
        parts.append("<tr>")
        for i in range(width):
            cell = row[i] if i < len(row) else ""
            a = aligns[i] if i < len(aligns) else None
            parts.append(f"<td{_align_attr(a)}>{render_inline(cell)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)
