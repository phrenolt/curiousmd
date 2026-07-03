import unittest
from domains.markdown.renderer import md_to_html, render_inline, slugify, normalize_safe_html


class TestRenderInline(unittest.TestCase):
    def test_bold_asterisk(self):
        self.assertEqual(render_inline("**bold**"), "<strong>bold</strong>")

    def test_bold_underscore(self):
        self.assertEqual(render_inline("__bold__"), "<strong>bold</strong>")

    def test_italic_asterisk(self):
        self.assertEqual(render_inline("*italic*"), "<em>italic</em>")

    def test_italic_underscore(self):
        self.assertEqual(render_inline("_italic_"), "<em>italic</em>")

    def test_bold_italic(self):
        self.assertEqual(render_inline("***bi***"), "<strong><em>bi</em></strong>")

    def test_strikethrough(self):
        self.assertEqual(render_inline("~~del~~"), "<del>del</del>")

    def test_inline_code(self):
        self.assertEqual(render_inline("`code`"), "<code>code</code>")

    def test_inline_code_escapes_html(self):
        self.assertIn("&lt;tag&gt;", render_inline("`<tag>`"))

    def test_safe_link(self):
        out = render_inline("[Go](https://example.com)")
        self.assertIn('href="https://example.com"', out)
        self.assertIn("rel=", out)

    def test_mailto_link(self):
        out = render_inline("[Mail](mailto:a@b.com)")
        self.assertIn('href="mailto:a@b.com"', out)

    def test_javascript_link_blocked(self):
        out = render_inline("[evil](javascript:evil())")
        self.assertIn("blocked-link", out)
        self.assertNotIn("javascript", out)

    def test_data_uri_link_blocked(self):
        out = render_inline("[x](data:text/html,<h1>)")
        self.assertIn("blocked-link", out)

    def test_safe_image(self):
        out = render_inline("![alt](https://example.com/img.png)")
        self.assertIn('<img', out)
        self.assertIn('alt="alt"', out)

    def test_nested_image_in_link(self):
        out = render_inline("[![alt](img.png)](https://example.com)")
        self.assertIn('<a href="https://example.com"', out)
        self.assertIn('<img alt="alt" src="img.png"', out)
        
    def test_nested_image_in_link_blocked(self):
        out = render_inline("[![alt](javascript:evil)](https://example.com)")
        self.assertIn('<a href="https://example.com"', out)
        self.assertIn('blocked-image', out)

    def test_javascript_image_blocked(self):
        out = render_inline("![alt](javascript:evil)")
        self.assertIn("blocked-image", out)
        self.assertNotIn("<img", out)

    def test_autolink(self):
        out = render_inline("<https://example.com>")
        self.assertIn('href="https://example.com"', out)

    def test_html_escaped_in_text(self):
        self.assertIn("&lt;", render_inline("<script>"))

    def test_long_line_truncated(self):
        long = "a" * 5000
        out = render_inline(long)
        self.assertIn("…", out)


class TestSluggify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_strips_html(self):
        self.assertEqual(slugify("<em>Title</em>"), "title")

    def test_empty(self):
        self.assertEqual(slugify(""), "section")

class TestSafeHtmlPreProcessor(unittest.TestCase):
    def test_safe_tags_converted_to_markdown(self):
        html = '<a href="https://example.com"><img src="img.png" alt="alt"></a>'
        out = normalize_safe_html(html)
        self.assertEqual(out, '[![alt](img.png)](https://example.com)')

        html2 = '<h1>Title</h1>'
        out2 = normalize_safe_html(html2)
        self.assertEqual(out2, '\n# Title\n\n')

    def test_unsafe_tags_escaped(self):
        html = '<script>alert(1)</script>'
        out = normalize_safe_html(html)
        self.assertEqual(out, '<script>alert(1)</script>')
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', md_to_html(html))

        html2 = '<iframe src="evil.com"></iframe>'
        out2 = normalize_safe_html(html2)
        self.assertEqual(out2, '<iframe src="evil.com"></iframe>')
        self.assertIn('&lt;iframe src=&quot;evil.com&quot;&gt;&lt;/iframe&gt;', md_to_html(html2))

    def test_styling_attributes_stripped(self):
        html = '<p align="center">text</p>'
        out = normalize_safe_html(html)
        self.assertIn('{center}', out)
        self.assertIn('text', out)

    def test_image_width_and_align_converted(self):
        html = '<p align="center"><img src="img.png" alt="alt" width="140"></p>'
        out = normalize_safe_html(html)
        self.assertIn('{center}', out)
        self.assertIn('![alt](img.png#w140)', out)

    def test_image_width_preserved_exactly(self):
        html = '<img src="img.png" alt="alt" width="820">'
        out = md_to_html(html)
        self.assertIn('width="820"', out)
        self.assertIn('src="img.png"', out)

    def test_code_blocks_protected(self):
        md = '```html\n<script>alert(1)</script>\n```'
        out = normalize_safe_html(md)
        self.assertEqual(out, md)

    def test_inline_code_protected(self):
        md = 'use `<script>` tag'
        out = normalize_safe_html(md)
        self.assertEqual(out, md)

    def test_centered_heading_emits_marker(self):
        html = '<h1 align="center">aceman</h1>'
        out = normalize_safe_html(html)
        self.assertIn('# aceman {center}', out)

    def test_centered_heading_renders_with_class(self):
        html = '<h1 align="center">aceman</h1>'
        out = md_to_html(html)
        self.assertIn('class="text-center"', out)
        self.assertIn('aceman', out)

    def test_non_centered_heading_has_no_class(self):
        html = '<h1>plain</h1>'
        out = md_to_html(html)
        self.assertNotIn('text-center', out)
        self.assertIn('plain', out)

    def test_centered_button_in_paragraph(self):
        html = '<p align="center"><a href="https://example.com"><img src="btn.png" alt="Button" width="240"></a></p>'
        out = md_to_html(html)
        self.assertIn('class="text-center"', out)
        self.assertIn('width="240"', out)
        self.assertIn('src="btn.png"', out)
        self.assertIn('href="https://example.com"', out)

    def test_centered_paragraph_keeps_images_inline(self):
        html = '<p align="center"><a href="#1"><img src="a.svg" alt="a"></a> <a href="#2"><img src="b.svg" alt="b"></a></p>'
        out = md_to_html(html)
        self.assertIn('class="text-center"', out)
        # Both images should be in the same <p>, not separate blocks
        self.assertEqual(out.count('<p'), 1)


class TestMdToHtml(unittest.TestCase):
    def test_heading_h1(self):
        out = md_to_html("# Hello")
        self.assertIn('<h1 id="hello">Hello</h1>', out)

    def test_heading_h2(self):
        out = md_to_html("## Sub")
        self.assertIn('<h2 id="sub">Sub</h2>', out)

    def test_duplicate_heading_slugs(self):
        out = md_to_html("# A\n# A\n# A")
        self.assertIn('id="a"', out)
        self.assertIn('id="a-1"', out)
        self.assertIn('id="a-2"', out)

    def test_setext_h1(self):
        out = md_to_html("Title\n=====")
        self.assertIn("<h1", out)

    def test_setext_h2(self):
        out = md_to_html("Sub\n---")
        self.assertIn("<h2", out)

    def test_paragraph(self):
        out = md_to_html("Hello world")
        self.assertIn("<p>Hello world</p>", out)

    def test_fenced_code_block(self):
        out = md_to_html("```py\nfoo\n```")
        self.assertIn('<pre><code class="lang-py">foo</code></pre>', out)

    def test_fenced_code_escapes_html(self):
        out = md_to_html("```\n<script>\n```")
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("<script>", out)

    def test_horizontal_rule(self):
        self.assertIn("<hr>", md_to_html("---"))

    def test_blockquote(self):
        out = md_to_html("> quote")
        self.assertIn("<blockquote>", out)

    def test_unordered_list(self):
        out = md_to_html("- a\n- b")
        self.assertIn("<ul>", out)
        self.assertIn("<li>", out)

    def test_ordered_list(self):
        out = md_to_html("1. first\n2. second")
        self.assertIn("<ol>", out)

    def test_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        out = md_to_html(md)
        self.assertIn("<table>", out)
        self.assertIn("<th>", out)
        self.assertIn("<td>", out)

    def test_table_alignment(self):
        md = "| L | C | R |\n|:--|:--:|--:|\n| a | b | c |"
        out = md_to_html(md)
        self.assertIn('class="align-left"', out)
        self.assertIn('class="align-center"', out)
        self.assertIn('class="align-right"', out)

    def test_empty_string(self):
        self.assertEqual(md_to_html(""), "")

    def test_blank_lines_ignored(self):
        out = md_to_html("\n\n# H\n\n")
        self.assertIn("<h1", out)


class TestSecurityAudit(unittest.TestCase):
    """Tests derived from a manual security audit of the rendering pipeline.

    Each test targets a specific attack vector that was identified during
    the audit and verified to be defended against.
    """

    # -- 1. ReDoS: pathological regex input should not hang --

    def test_redos_nested_emphasis_markers(self):
        """Deeply nested emphasis markers must not cause catastrophic backtracking."""
        evil = "*" * 500 + "a" + "*" * 500
        import time
        t0 = time.monotonic()
        render_inline(evil)
        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 2.0, "render_inline took too long — possible ReDoS")

    def test_redos_nested_brackets(self):
        """Deeply nested brackets must not cause catastrophic backtracking."""
        evil = "[" * 500 + "a" + "](" + "x" * 500 + ")"
        import time
        t0 = time.monotonic()
        render_inline(evil)
        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 2.0, "render_inline took too long — possible ReDoS")

    # -- 2. URL scheme smuggling with control characters --

    def test_javascript_with_null_byte(self):
        """Null bytes in scheme must not bypass the scheme check."""
        out = render_inline("![x](java\x00script:alert(1))")
        self.assertNotIn("<img", out)

    def test_javascript_with_tab_chars(self):
        """Tab characters in scheme must not bypass the scheme check."""
        out = render_inline("![x](java\tscript:alert(1))")
        self.assertNotIn("javascript", out.lower())

    def test_javascript_with_newline(self):
        """Newline in URL must not bypass the scheme check."""
        out = render_inline("[x](java\nscript:alert(1))")
        self.assertNotIn("javascript", out.lower())

    # -- 3. Case-mixed scheme evasion --

    def test_javascript_mixed_case_link(self):
        """Mixed-case 'JaVaScRiPt:' must be blocked."""
        out = render_inline("[x](JaVaScRiPt:alert(1))")
        self.assertIn("blocked-link", out)
        self.assertNotIn("href", out)

    def test_javascript_mixed_case_image(self):
        """Mixed-case 'JavaScript:' on images must be blocked."""
        out = render_inline("![x](JavaScript:alert(1))")
        self.assertIn("blocked-image", out)
        self.assertNotIn("<img", out)

    # -- 4. vbscript scheme --

    def test_vbscript_link_blocked(self):
        """vbscript: scheme must be blocked."""
        out = render_inline("[x](vbscript:MsgBox)")
        self.assertIn("blocked-link", out)
        self.assertNotIn("href", out)

    def test_vbscript_image_blocked(self):
        """vbscript: scheme on images must be blocked."""
        out = render_inline("![x](vbscript:MsgBox)")
        self.assertIn("blocked-image", out)
        self.assertNotIn("<img", out)

    # -- 5. HTML onerror / onload attribute injection --

    def test_img_onerror_stripped_by_preprocessor(self):
        """<img onerror=...> must not survive into the final HTML."""
        html = '<img src="x" onerror="alert(1)" alt="xss">'
        out = md_to_html(html)
        self.assertNotIn("onerror", out)
        self.assertNotIn("alert(1)", out)

    def test_img_onload_stripped_by_preprocessor(self):
        """<img onload=...> must not survive into the final HTML."""
        html = '<img src="img.png" onload="alert(1)">'
        out = md_to_html(html)
        self.assertNotIn("onload", out)
        self.assertNotIn("alert(1)", out)

    def test_svg_onload_escaped(self):
        """<svg onload=...> must be escaped to harmless text."""
        html = '<svg onload="alert(1)"></svg>'
        out = md_to_html(html)
        self.assertNotIn("<svg", out)
        self.assertIn("&lt;svg", out)

    # -- 6. Alt-text attribute injection --

    def test_alt_text_quote_injection(self):
        """Quotes in alt text must be escaped so they can't break out of the attribute."""
        out = render_inline('![" onload="alert(1)](img.png)')
        # The quote must be escaped — the browser must not see an unescaped "
        # that could terminate the alt attribute and start an onload handler.
        self.assertIn('&quot;', out)
        # Verify the onload never appears as an actual HTML attribute
        self.assertNotIn('onload="alert', out)

    def test_alt_text_angle_bracket_injection(self):
        """Angle brackets in alt text must be escaped."""
        out = render_inline('![<script>alert(1)</script>](img.png)')
        self.assertNotIn('<script>', out)

    # -- 7. Full pipeline end-to-end XSS attempts --

    def test_e2e_script_in_markdown_paragraph(self):
        """A raw <script> tag in a paragraph must be fully escaped."""
        out = md_to_html("Hello <script>alert(1)</script> world")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_e2e_img_onerror_in_markdown(self):
        """An <img onerror> in raw markdown must have the handler stripped."""
        out = md_to_html('<img src=x onerror=alert(1)>')
        self.assertNotIn("onerror", out)

    def test_e2e_nested_html_in_link(self):
        """HTML inside a markdown link label must be escaped."""
        out = md_to_html('[<img src=x onerror=alert(1)>](https://example.com)')
        self.assertNotIn("onerror", out)


if __name__ == "__main__":
    unittest.main()
