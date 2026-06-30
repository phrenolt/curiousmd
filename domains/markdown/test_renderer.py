import unittest
from domains.markdown.renderer import md_to_html, render_inline, slugify


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


if __name__ == "__main__":
    unittest.main()
