import html
import re
import urllib.parse
import uuid
from html.parser import HTMLParser

LINK_SCHEMES = {"", "http", "https", "mailto"}
IMAGE_SCHEMES = {"", "http", "https"}
MAX_LINE_LEN = 4096

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

class ThematicBreak(Block): pass

class Heading(Block):
    def __init__(self, level, text, center=False):
        self.level = level
        self.text = text
        self.center = center

class CodeBlock(Block):
    def __init__(self, lang, code):
        self.lang = lang
        self.code = code

class Paragraph(Block):
    def __init__(self, text, center=False):
        self.text = text
        self.center = center

class BlockQuote(Block):
    def __init__(self, children):
        self.children = children

class List(Block):
    def __init__(self, ordered, items):
        self.ordered = ordered
        self.items = items

class ListItem(Node):
    def __init__(self, content, nested):
        self.content = content
        self.nested = nested

class Table(Block):
    def __init__(self, header, aligns, rows):
        self.header = header
        self.aligns = aligns
        self.rows = rows


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

def _parse_list(lines, i, base_indent):
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
            i, nested_list = _parse_list(lines, i, base_indent=cur_indent)
            if nested_list and items:
                items[-1].nested.append(nested_list)
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
            i, nested_list = _parse_list(lines, i, base_indent=indent + 1)
            if nested_list:
                nested.append(nested_list)
                
        items.append(ListItem(content, nested))
        
    if not items:
        return i, None
    return i, List(ordered, items)

def parse_blocks(md):
    lines = md.splitlines()
    blocks = []
    i = 0
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
            blocks.append(CodeBlock(lang, "\n".join(buf)))
            continue

        if not raw.strip():
            i += 1
            continue

        if re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", raw):
            blocks.append(ThematicBreak())
            i += 1
            continue

        h = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", raw)
        if h:
            text = h.group(2)
            center = text.endswith(' {center}')
            if center:
                text = text[:-len(' {center}')]
            blocks.append(Heading(len(h.group(1)), text, center=center))
            i += 1
            continue

        if i + 1 < len(lines) and raw.strip():
            nxt = lines[i + 1]
            if not re.match(r"^\s*([-*+]\s|\d+\.\s|>|#{1,6}\s|```)", raw):
                if re.match(r"^=+\s*$", nxt):
                    blocks.append(Heading(1, raw.strip()))
                    i += 2
                    continue
                if re.match(r"^-+\s*$", nxt):
                    blocks.append(Heading(2, raw.strip()))
                    i += 2
                    continue

        if re.match(r"^>\s?", raw):
            block = []
            while i < len(lines) and re.match(r"^>\s?", lines[i]):
                block.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            blocks.append(BlockQuote(parse_blocks("\n".join(block))))
            continue

        if re.match(r"^\s*[-*+]\s+", raw) or re.match(r"^\s*\d+\.\s+", raw):
            i, list_node = _parse_list(lines, i, base_indent=0)
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
            blocks.append(Table(header, aligns, rows))
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
        blocks.append(Paragraph(text, center=center))

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

    def get_slug(text):
        base = slugify(text)
        n = seen_slugs.get(base, 0)
        seen_slugs[base] = n + 1
        return base if n == 0 else f"{base}-{n}"

    def render_block(block):
        if isinstance(block, ThematicBreak):
            return "<hr>"
        elif isinstance(block, Heading):
            rendered = render_inline(block.text)
            slug = get_slug(block.text)
            cls = ' class="text-center"' if block.center else ''
            return f'<h{block.level} id="{slug}"{cls}>{rendered}</h{block.level}>'
        elif isinstance(block, CodeBlock):
            cls = f' class="lang-{html.escape(block.lang)}"' if block.lang else ""
            code = html.escape(block.code)
            return f"<pre><code{cls}>{code}</code></pre>"
        elif isinstance(block, BlockQuote):
            inner = "\n".join(render_block(child) for child in block.children)
            return f"<blockquote>{inner}</blockquote>"
        elif isinstance(block, Paragraph):
            cls = ' class="text-center"' if block.center else ''
            return f'<p{cls}>{render_inline(block.text)}</p>'
        elif isinstance(block, List):
            tag = "ol" if block.ordered else "ul"
            res = [f"<{tag}>"]
            for item in block.items:
                item_html = render_inline(item.content)
                if item.nested:
                    nested_html = "\n".join(render_block(n) for n in item.nested)
                    res.append(f"<li>{item_html}\n{nested_html}</li>")
                else:
                    res.append(f"<li>{item_html}</li>")
            res.append(f"</{tag}>")
            return "\n".join(res)
        elif isinstance(block, Table):
            parts = ["<table><thead><tr>"]
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
        self.link_hrefs = []
        self.stack = []
        self.centered = 0
        
    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        is_centered = attr_dict.get("align") == "center"
        self.stack.append(is_centered)
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
                
            self.result.append(f"![{alt}]({src})")
        elif tag == "a":
            href = attr_dict.get("href", "")
            self.link_hrefs.append(href)
            self.result.append("[")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self.result.append(f"\n{'#' * level} ")
            self._heading_centered = is_centered or self.centered > 0
        elif tag in ("b", "strong"):
            self.result.append("**")
        elif tag in ("i", "em"):
            self.result.append("*")
        elif tag == "del":
            self.result.append("~~")
        elif tag in ("p", "div"):
            if is_centered:
                self.result.append("\n\n{center} ")
            else:
                self.result.append("\n\n")
        elif tag == "span":
            pass
        elif tag == "br":
            self.result.append("  \n")
        elif tag in ("table", "tbody", "thead", "tr", "td", "th", "sub", "sup"):
            attr_str = "".join(f' {k}="{v}"' if v is not None else f' {k}' for k, v in attrs)
            self.result.append(f"<{tag}{attr_str}>")
        else:
            attr_str = "".join(f' {k}="{v}"' if v is not None else f' {k}' for k, v in attrs)
            self.result.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag):
        if self.stack:
            if self.stack.pop():
                self.centered -= 1

        if tag == "a":
            if self.link_hrefs:
                href = self.link_hrefs.pop()
                self.result.append(f"]({href})")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if getattr(self, '_heading_centered', False):
                self.result.append(" {center}")
                self._heading_centered = False
            self.result.append("\n\n")
        elif tag in ("p", "div"):
            self.result.append("\n\n")
        elif tag in ("b", "strong"):
            self.result.append("**")
        elif tag in ("i", "em"):
            self.result.append("*")
        elif tag == "del":
            self.result.append("~~")
        elif tag in ("span", "br", "img"):
            pass
        elif tag in ("table", "tbody", "thead", "tr", "td", "th", "sub", "sup"):
            self.result.append(f"</{tag}>")
        else:
            self.result.append(f"</{tag}>")

    def handle_data(self, data):
        self.result.append(data)
        
    def handle_entityref(self, name):
        self.result.append(f"&{name};")
        
    def handle_charref(self, name):
        self.result.append(f"&#{name};")

def normalize_safe_html(md_text):
    code_blocks = {}
    
    def save_block(m):
        token = f"__MDVIEW_CODE_BLOCK_{uuid.uuid4().hex}__"
        code_blocks[token] = m.group(0)
        return token
    
    md_text = re.sub(r"(?m)^```[\w]*\n[\s\S]*?^```\s*$", save_block, md_text)
    
    def save_inline(m):
        token = f"__MDVIEW_INLINE_CODE_{uuid.uuid4().hex}__"
        code_blocks[token] = m.group(0)
        return token
        
    md_text = re.sub(r"`[^`\n]+`", save_inline, md_text)
    
    parser = SafeHtmlPreProcessor()
    parser.feed(md_text)
    processed = "".join(parser.result)
    
    for token, content in code_blocks.items():
        processed = processed.replace(token, content)
        
    return processed

def md_to_html(md):
    md = normalize_safe_html(md)
    blocks = parse_blocks(md)
    ast = Document(blocks)
    return render_html(ast)
