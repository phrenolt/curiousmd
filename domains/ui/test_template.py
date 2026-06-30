import json
import unittest
from domains.ui.template import json_for_script, render_index


class TestJsonForScript(unittest.TestCase):
    def test_spaces_not_replaced(self):
        out = json_for_script({"key": "hello world"})
        self.assertIn(" ", out)

    def test_line_separator_escaped(self):
        out = json_for_script({"k": "a b"})
        self.assertNotIn(" ", out)
        self.assertIn("\\u2028", out)

    def test_paragraph_separator_escaped(self):
        out = json_for_script({"k": "a b"})
        self.assertNotIn(" ", out)
        self.assertIn("\\u2029", out)

    def test_lt_escaped(self):
        out = json_for_script({"k": "<script>"})
        self.assertNotIn("<", out)
        self.assertIn("\\u003c", out)

    def test_gt_escaped(self):
        out = json_for_script({"k": "</script>"})
        self.assertNotIn(">", out)
        self.assertIn("\\u003e", out)

    def test_amp_escaped(self):
        out = json_for_script({"k": "a&b"})
        self.assertNotIn("&", out)
        self.assertIn("\\u0026", out)

    def test_output_is_valid_json(self):
        obj = {"docs": [], "active": None, "browse_root": "/tmp", "browse_path": "/tmp"}
        out = json_for_script(obj)
        parsed = json.loads(out)
        self.assertEqual(parsed["docs"], [])
        self.assertIsNone(parsed["active"])


class TestRenderIndex(unittest.TestCase):
    def _render(self):
        return render_index([], None, "/tmp", "/tmp")

    def test_returns_html_string(self):
        html, _ = self._render()
        self.assertIn("<!DOCTYPE html>", html)

    def test_nonce_in_style_tag(self):
        html, nonce = self._render()
        self.assertIn(f'<style nonce="{nonce}">', html)

    def test_nonce_in_script_tags(self):
        html, nonce = self._render()
        self.assertGreaterEqual(html.count(f'nonce="{nonce}"'), 2)

    def test_no_inline_style_attributes(self):
        html, _ = self._render()
        # style= in HTML attributes is blocked by nonce-based CSP
        # only <style nonce="..."> blocks are allowed
        import re
        inline_styles = re.findall(r'<(?!style)[^>]+\bstyle\s*=', html)
        self.assertEqual(inline_styles, [])

    def test_bootstrap_json_is_valid(self):
        html, _ = self._render()
        import re
        m = re.search(r'window\.__BOOTSTRAP__\s*=\s*(\{.*?\});', html)
        self.assertIsNotNone(m)
        parsed = json.loads(m.group(1))
        self.assertIn("docs", parsed)

    def test_bootstrap_spaces_intact(self):
        html, _ = self._render()
        # regression: spaces must not be replaced with
        self.assertNotIn("\\u2028", html.split("__BOOTSTRAP__")[1].split("</script>")[0])


if __name__ == "__main__":
    unittest.main()
