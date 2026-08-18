import html
import re
import urllib.parse
import uuid
from html.parser import HTMLParser

LINK_SCHEMES = {"", "http", "https", "mailto"}
IMAGE_SCHEMES = {"", "http", "https"}
MAX_LINE_LEN = 4096
HTML_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})
PASSTHROUGH_TAGS = frozenset({
    "table", "tbody", "thead", "tr", "td", "th", "sub", "sup",
})
PASSTHROUGH_ATTRS = {
    "td": frozenset({"class", "width", "valign"}),
    "th": frozenset({"class", "width", "valign"}),
}

INLINE_RE = re.compile(
    r"(?P<code>`(?P<code_inner>[^`\n]+)`)"
    r"|(?P<bi>\*\*\*(?P<bi_inner>[^*\n]+)\*\*\*)"
    r"|(?P<bold>\*\*(?P<bold_inner>[^*\n]+)\*\*|__(?P<bold_inner2>[^_\n]+)__)"
    r"|(?P<italic>\*(?P<italic_inner>[^*\n]+)\*|(?<![A-Za-z0-9_])_(?P<italic_inner2>[^_\n]+)_(?![A-Za-z0-9_]))"
    r"|(?P<strike>~~(?P<strike_inner>[^~\n]+)~~)"
    r"|(?P<image>!\[(?P<image_alt>[^\]]*)\]\((?P<image_src>[^)\s]+)(?:\s+\"(?P<image_title>[^\"]*)\")?\))"
    r"|(?P<link>\[(?P<link_text>!\[[^\]]*\]\([^)]+\)|[^\]]+)\]\((?P<link_href>[^)\s]+)(?:\s+\"(?P<link_title>[^\"]*)\")?\))"
    r"|(?P<autolink><(?P<autolink_url>(?:https?|mailto):[^>\s]+)>)|(?P<html></?(?:table|tbody|thead|tr|td|th|sub|sup)(?:\s+[^>]*)?>)"
)


# --- AST Nodes ---

class Node: pass
class Block(Node): pass
class Inline(Node): pass

class HtmlTag(Inline):
    def __init__(self, raw):
        self.raw = raw

class Document(Block):
    def __init__(self, children):
        self.children = children

class ThematicBreak(Block):
    def __init__(self, source_line=None):
        self.source_line = source_line

class Heading(Block):
    def __init__(self, level, text, center=False, source_line=None):
        self.level = level
        self.text = text
        self.center = center
        self.source_line = source_line

class CodeBlock(Block):
    def __init__(self, lang, code, source_line=None):
        self.lang = lang
        self.code = code
        self.source_line = source_line

class Paragraph(Block):
    def __init__(self, text, center=False, source_line=None):
        self.text = text
        self.center = center
        self.source_line = source_line

class BlockQuote(Block):
    def __init__(self, children, source_line=None):
        self.children = children
        self.source_line = source_line

class List(Block):
    def __init__(self, ordered, items, source_line=None):
        self.ordered = ordered
        self.items = items
        self.source_line = source_line

class ListItem(Node):
    def __init__(self, content, nested, source_line=None):
        self.content = content
        self.nested = nested
        self.source_line = source_line

class Table(Block):
    def __init__(self, header, aligns, rows, source_line=None):
        self.header = header
        self.aligns = aligns
        self.rows = rows
        self.source_line = source_line


# --- Inline Nodes ---

class Text(Inline):
    def __init__(self, content): self.content = content

class CodeSpan(Inline):
    def __init__(self, content): self.content = content

class Strong(Inline):
    def __init__(self, children): self.children = children

class Emph(Inline):
    def __init__(self, children): self.children = children

class Strike(Inline):
    def __init__(self, children): self.children = children

class Image(Inline):
    def __init__(self, alt, src, title, blocked=False):
        self.alt = alt
        self.src = src
        self.title = title
        self.blocked = blocked

class Link(Inline):
    def __init__(self, href, title, children, blocked=False, raw_label=None):
        self.href = href
        self.title = title
        self.children = children
        self.blocked = blocked
        self.raw_label = raw_label


# --- Parsing ---

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

def parse_inline(text):
    if len(text) > MAX_LINE_LEN:
        text = text[:MAX_LINE_LEN] + "…"
    nodes = []
    pos = 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            nodes.append(Text(text[pos:m.start()]))
        kind = m.lastgroup
        if kind == "code":
            nodes.append(CodeSpan(m.group("code_inner")))
        elif kind == "bi":
            nodes.append(Strong([Emph([Text(m.group("bi_inner"))])]))
        elif kind == "bold":
            nodes.append(Strong([Text(m.group("bold_inner") or m.group("bold_inner2"))]))
        elif kind == "italic":
            nodes.append(Emph([Text(m.group("italic_inner") or m.group("italic_inner2"))]))
        elif kind == "strike":
            nodes.append(Strike([Text(m.group("strike_inner"))]))
        elif kind == "image":
            alt = m.group("image_alt") or ""
            src = _clean_url(m.group("image_src"), IMAGE_SCHEMES)
            title = m.group("image_title")
            if src is None:
                nodes.append(Image(alt, m.group("image_src"), title, blocked=True))
            else:
                nodes.append(Image(alt, src, title, blocked=False))
        elif kind == "link":
            label_text = m.group("link_text")
            href = _clean_url(m.group("link_href"), LINK_SCHEMES)
            title = m.group("link_title")
            if href is None:
                nodes.append(Link(m.group("link_href"), title, [], blocked=True, raw_label=label_text))
            else:
                nodes.append(Link(href, title, parse_inline(label_text), blocked=False))
        elif kind == "html":
            nodes.append(HtmlTag(m.group("html")))
        elif kind == "autolink":
            raw_url = m.group("autolink_url")
            url = _clean_url(raw_url, LINK_SCHEMES)
            if url is None:
                nodes.append(Link(raw_url, None, [], blocked=True, raw_label=raw_url))
            else:
                nodes.append(Link(url, None, [Text(raw_url)], blocked=False))
        pos = m.end()
    if pos < len(text):
        nodes.append(Text(text[pos:]))
    return nodes

def _source_line(source_lines, index, line_offset=0):
    if source_lines is not None and index < len(source_lines):
        return source_lines[index]
    return line_offset + index + 1


def _parse_list(lines, i, base_indent, line_offset=0, source_lines=None):
    list_line = _source_line(source_lines, i, line_offset)
    first = lines[i]
    indent = len(first) - len(first.lstrip(" "))
    if indent < base_indent:
        return i, None
    ordered = bool(re.match(r"^\s*\d+\.\s+", first))
    item_re = (re.compile(r"^(\s*)(\d+)\.\s+(.*)$") if ordered
               else re.compile(r"^(\s*)([-*+])\s+(.*)$"))

    items = []
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
            i, nested_list = _parse_list(
                lines, i, base_indent=cur_indent, line_offset=line_offset,
                source_lines=source_lines,
            )
            if nested_list and items:
                items[-1].nested.append(nested_list)
            continue
            
        item_line = _source_line(source_lines, i, line_offset)
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
            i, nested_list = _parse_list(
                lines, i, base_indent=indent + 1, line_offset=line_offset,
                source_lines=source_lines,
            )
            if nested_list:
                nested.append(nested_list)
                
        items.append(ListItem(content, nested, source_line=item_line))
        
    if not items:
        return i, None
    return i, List(ordered, items, source_line=list_line)

def parse_blocks(md, line_offset=0, source_lines=None):
    lines = md.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        source_line = _source_line(source_lines, i, line_offset)

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
            blocks.append(CodeBlock(lang, "\n".join(buf), source_line=source_line))
            continue

        if not raw.strip():
            i += 1
            continue

        if re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", raw):
            blocks.append(ThematicBreak(source_line=source_line))
            i += 1
            continue

        h = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", raw)
        if h:
            text = h.group(2)
            center = text.endswith(' {center}')
            if center:
                text = text[:-len(' {center}')]
            blocks.append(Heading(
                len(h.group(1)), text, center=center, source_line=source_line,
            ))
            i += 1
            continue

        if i + 1 < len(lines) and raw.strip():
            nxt = lines[i + 1]
            if not re.match(r"^\s*([-*+]\s|\d+\.\s|>|#{1,6}\s|```)", raw):
                if re.match(r"^=+\s*$", nxt):
                    blocks.append(Heading(1, raw.strip(), source_line=source_line))
                    i += 2
                    continue
                if re.match(r"^-+\s*$", nxt):
                    blocks.append(Heading(2, raw.strip(), source_line=source_line))
                    i += 2
                    continue

        if re.match(r"^>\s?", raw):
            quote_start = i
            block = []
            while i < len(lines) and re.match(r"^>\s?", lines[i]):
                block.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            blocks.append(BlockQuote(
                parse_blocks(
                    "\n".join(block),
                    line_offset=line_offset + quote_start,
                    source_lines=(
                        source_lines[quote_start:i]
                        if source_lines is not None else None
                    ),
                ),
                source_line=source_line,
            ))
            continue

        if re.match(r"^\s*[-*+]\s+", raw) or re.match(r"^\s*\d+\.\s+", raw):
            i, list_node = _parse_list(
                lines, i, base_indent=0, line_offset=line_offset,
                source_lines=source_lines,
            )
            if list_node:
                blocks.append(list_node)
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
            blocks.append(Table(header, aligns, rows, source_line=source_line))
            continue

        para = [raw]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|>|\s*[-*+]\s+|\s*\d+\.\s+|```|---+\s*$|===+\s*$)",
            lines[i],
        ):
            para.append(lines[i])
            i += 1
        text = ' '.join(p.strip() for p in para)
        center = text.startswith('{center} ')
        if center:
            text = text[len('{center} '):]
        blocks.append(Paragraph(text, center=center, source_line=source_line))

    return blocks

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


# --- Rendering ---

def render_inline_nodes(nodes):
    out = []
    for node in nodes:
        if isinstance(node, Text):
            out.append(html.escape(node.content))
        elif isinstance(node, HtmlTag):
            out.append(node.raw)
        elif isinstance(node, CodeSpan):
            out.append(f"<code>{html.escape(node.content)}</code>")
        elif isinstance(node, Strong):
            out.append(f"<strong>{render_inline_nodes(node.children)}</strong>")
        elif isinstance(node, Emph):
            out.append(f"<em>{render_inline_nodes(node.children)}</em>")
        elif isinstance(node, Strike):
            out.append(f"<del>{html.escape(node.children[0].content)}</del>")
        elif isinstance(node, Image):
            alt = html.escape(node.alt)
            if node.blocked:
                out.append(f'<span class="blocked-image">[blocked image: {alt}]</span>')
            else:
                src_raw = node.src
                w_attr = ''
                w_match = re.search(r'#w(\d+)$', src_raw)
                if w_match:
                    w_attr = f' width="{w_match.group(1)}"'
                    src_raw = src_raw[:w_match.start()]
                src_attr = html.escape(src_raw, quote=True)
                title = node.title
                t_attr = f' title="{html.escape(title, quote=True)}"' if title else ""
                out.append(f'<img alt="{alt}" src="{src_attr}"{t_attr}{w_attr} loading="lazy" decoding="async">')
        elif isinstance(node, Link):
            if node.blocked:
                label = render_inline_nodes(parse_inline(node.raw_label)) if node.raw_label else ""
                out.append(f'<span class="blocked-link">{label}</span>')
            else:
                label = render_inline_nodes(node.children)
                href_attr = html.escape(node.href, quote=True)
                title = node.title
                t_attr = f' title="{html.escape(title, quote=True)}"' if title else ""
                out.append(f'<a href="{href_attr}"{t_attr} rel="noopener noreferrer">{label}</a>')
    return "".join(out)

def render_inline(text):
    return render_inline_nodes(parse_inline(text))

def slugify(text):
    s = re.sub(r"<[^>]+>", "", text).lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or "section"

def render_html(ast):
    seen_slugs = {}

    def source_attr(node):
        line = getattr(node, "source_line", None)
        return f' data-source-line="{line}"' if line is not None else ""

    def get_slug(text):
        base = slugify(text)
        n = seen_slugs.get(base, 0)
        seen_slugs[base] = n + 1
        return base if n == 0 else f"{base}-{n}"

    def render_block(block):
        if isinstance(block, ThematicBreak):
            return f"<hr{source_attr(block)}>"
        elif isinstance(block, Heading):
            rendered = render_inline(block.text)
            slug = get_slug(block.text)
            cls = ' class="text-center"' if block.center else ''
            return f'<h{block.level} id="{slug}"{cls}{source_attr(block)}>{rendered}</h{block.level}>'
        elif isinstance(block, CodeBlock):
            cls = f' class="lang-{html.escape(block.lang)}"' if block.lang else ""
            code = html.escape(block.code)
            return f"<pre{source_attr(block)}><code{cls}>{code}</code></pre>"
        elif isinstance(block, BlockQuote):
            inner = "\n".join(render_block(child) for child in block.children)
            return f"<blockquote{source_attr(block)}>{inner}</blockquote>"
        elif isinstance(block, Paragraph):
            cls = ' class="text-center"' if block.center else ''
            return f'<p{cls}{source_attr(block)}>{render_inline(block.text)}</p>'
        elif isinstance(block, List):
            tag = "ol" if block.ordered else "ul"
            res = [f"<{tag}{source_attr(block)}>"]
            for item in block.items:
                item_html = render_inline(item.content)
                if item.nested:
                    nested_html = "\n".join(render_block(n) for n in item.nested)
                    res.append(f"<li{source_attr(item)}>{item_html}\n{nested_html}</li>")
                else:
                    res.append(f"<li{source_attr(item)}>{item_html}</li>")
            res.append(f"</{tag}>")
            return "\n".join(res)
        elif isinstance(block, Table):
            parts = [f"<table{source_attr(block)}><thead><tr>"]
            for idx, cell in enumerate(block.header):
                a = block.aligns[idx] if idx < len(block.aligns) else None
                parts.append(f"<th{_align_attr(a)}>{render_inline(cell)}</th>")
            parts.append("</tr></thead><tbody>")
            width = len(block.header)
            for row in block.rows:
                parts.append("<tr>")
                for idx in range(width):
                    cell = row[idx] if idx < len(row) else ""
                    a = block.aligns[idx] if idx < len(block.aligns) else None
                    parts.append(f"<td{_align_attr(a)}>{render_inline(cell)}</td>")
                parts.append("</tr>")
            parts.append("</tbody></table>")
            return "".join(parts)
        elif isinstance(block, Document):
            out = []
            for child in block.children:
                out.append(render_block(child))
            return "\n".join(out)
        return ""

    return render_block(ast)

class SafeHtmlPreProcessor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.result = []
        self.segments = []
        self.link_hrefs = []
        self.stack = []
        self.centered = 0

    def _emit(self, text, follows_source_lines=False):
        self.result.append(text)
        self.segments.append((text, self.getpos()[0], follows_source_lines))

    @staticmethod
    def _passthrough_attrs(tag, attrs):
        allowed = PASSTHROUGH_ATTRS.get(tag, frozenset())
        safe_attrs = []
        seen = set()
        for name, value in attrs:
            if name in seen or name not in allowed or value is None:
                continue
            seen.add(name)
            if name == "class":
                classes = value.split()
                if not classes or any(
                    cls not in {"align-left", "align-center", "align-right"}
                    for cls in classes
                ):
                    continue
                value = " ".join(classes)
            elif name == "width" and not re.fullmatch(r"\d+%?", value):
                continue
            elif name == "valign" and value.lower() not in {
                "top", "middle", "bottom", "baseline",
            }:
                continue
            safe_attrs.append(f' {name}="{html.escape(value, quote=True)}"')
        return "".join(safe_attrs)
        
    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        is_centered = attr_dict.get("align") == "center"
        if tag not in HTML_VOID_TAGS:
            self.stack.append((tag, is_centered))
            if is_centered:
                self.centered += 1

        if tag == "img":
            src = attr_dict.get("src", "")
            alt = attr_dict.get("alt", "")
            width = attr_dict.get("width", "")
            
            if width:
                try:
                    w = int(width.replace("px", ""))
                    src += f"#w{w}"
                except: pass
                
            self._emit(f"![{alt}]({src})")
        elif tag == "a":
            href = attr_dict.get("href", "")
            self.link_hrefs.append(href)
            self._emit("[")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self._emit(f"\n{'#' * level} ")
            self._heading_centered = is_centered or self.centered > 0
        elif tag in ("b", "strong"):
            self._emit("**")
        elif tag in ("i", "em"):
            self._emit("*")
        elif tag == "del":
            self._emit("~~")
        elif tag in ("p", "div"):
            if is_centered:
                self._emit("\n\n{center} ")
            else:
                self._emit("\n\n")
        elif tag == "span":
            pass
        elif tag == "br":
            self._emit("  \n")
        elif tag in PASSTHROUGH_TAGS:
            attr_str = self._passthrough_attrs(tag, attrs)
            self._emit(f"<{tag}{attr_str}>")
        else:
            attr_str = "".join(f' {k}="{v}"' if v is not None else f' {k}' for k, v in attrs)
            self._emit(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag):
        if tag not in HTML_VOID_TAGS:
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index][0] == tag:
                    closed = self.stack[index:]
                    del self.stack[index:]
                    self.centered -= sum(is_centered for _, is_centered in closed)
                    break

        if tag == "a":
            if self.link_hrefs:
                href = self.link_hrefs.pop()
                self._emit(f"]({href})")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if getattr(self, '_heading_centered', False):
                self._emit(" {center}")
                self._heading_centered = False
            self._emit("\n\n")
        elif tag in ("p", "div"):
            self._emit("\n\n")
        elif tag in ("b", "strong"):
            self._emit("**")
        elif tag in ("i", "em"):
            self._emit("*")
        elif tag == "del":
            self._emit("~~")
        elif tag in ("span", "br", "img"):
            pass
        elif tag in PASSTHROUGH_TAGS:
            self._emit(f"</{tag}>")
        else:
            self._emit(f"</{tag}>")

    def handle_data(self, data):
        self._emit(data, follows_source_lines=True)
        
    def handle_entityref(self, name):
        self._emit(f"&{name};")
        
    def handle_charref(self, name):
        self._emit(f"&#{name};")

def _line_origins(segments):
    origins = []
    line_origin = None
    line_has_chars = False

    for text, source_line, follows_source_lines in segments:
        current_source_line = source_line
        for char in text:
            if char == "\n":
                origins.append(line_origin or current_source_line)
                line_origin = None
                line_has_chars = False
                if follows_source_lines:
                    current_source_line += 1
                continue
            if line_origin is None:
                line_origin = current_source_line
            line_has_chars = True

    if line_has_chars:
        origins.append(line_origin)
    return origins


def normalize_safe_html(md_text, with_source_map=False):
    protected = {}

    def protect(prefix, content):
        token = f"__MDVIEW_{prefix}_{uuid.uuid4().hex}__"
        placeholder = token + ("\n" * content.count("\n"))
        protected[placeholder] = content
        return placeholder
    
    def save_block(m):
        return protect("CODE_BLOCK", m.group(0))
    
    md_text = re.sub(r"(?m)^```[\w]*\n[\s\S]*?^```\s*$", save_block, md_text)
    
    def save_inline(m):
        return protect("INLINE_CODE", m.group(0))
        
    md_text = re.sub(r"`[^`\n]+`", save_inline, md_text)

    def save_autolink(m):
        return protect("AUTOLINK", m.group(0))

    md_text = re.sub(r"<(?:https?|mailto):[^>\s]+>", save_autolink, md_text)
    
    parser = SafeHtmlPreProcessor()
    parser.feed(md_text)
    segments = []
    for text, source_line, follows_source_lines in parser.segments:
        for placeholder, content in protected.items():
            text = text.replace(placeholder, content)
        segments.append((text, source_line, follows_source_lines))

    processed = "".join(text for text, _, _ in segments)
    if with_source_map:
        return processed, _line_origins(segments)
    return processed

def md_to_html(md):
    md, source_lines = normalize_safe_html(md, with_source_map=True)
    blocks = parse_blocks(md, source_lines=source_lines)
    ast = Document(blocks)
    return render_html(ast)
