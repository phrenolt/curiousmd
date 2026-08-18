import os
import tempfile
import unittest
import urllib.parse

import mdview
from domains.auth.session import auth
from domains.docs.store import store
from domains.filesystem.browser import browser


class TestFilesystemHttpBoundary(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = self.tempdir.name
        mdview._asset_root = self.root
        browser.root = self.root
        auth.init_tokens()
        self.cookie = auth.make_set_cookie().split(";", 1)[0]

    def tearDown(self):
        self.tempdir.cleanup()

    def _write(self, relative, content=b"content"):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as file:
            file.write(content)
        return path

    def _request(self, path, authenticated=False):
        handler = mdview.Handler.__new__(mdview.Handler)
        handler.path = path
        handler.headers = {"Cookie": self.cookie} if authenticated else {}
        result = {"status": None, "body": b""}

        def send_json(obj, status=200):
            result["status"] = status
            result["body"] = str(obj).encode("utf-8")

        def send_file(path):
            result["status"] = 200
            with open(path, "rb") as file:
                result["body"] = file.read()

        handler._send_json = send_json
        handler._send_file = send_file
        handler.send_error = lambda status: result.update(status=status)
        handler.do_GET()
        return result

    def test_static_fallback_does_not_serve_sensitive_files(self):
        self._write("secret.txt", b"do not expose")
        response = self._request("/secret.txt", authenticated=True)
        self.assertEqual(response["status"], 404)
        self.assertNotIn(b"do not expose", response["body"])

    def test_static_images_require_session(self):
        self._write("image.png", b"png bytes")
        response = self._request("/image.png")
        self.assertEqual(response["status"], 403)
        response = self._request("/image.png", authenticated=True)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], b"png bytes")

    def test_static_fallback_rejects_hidden_images(self):
        self._write(".private/secret.png", b"hidden")
        response = self._request("/.private/secret.png", authenticated=True)
        self.assertEqual(response["status"], 404)
        self.assertNotIn(b"hidden", response["body"])

    def test_static_fallback_rejects_encoded_traversal(self):
        outside = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        outside.write(b"outside")
        outside.close()
        path = "/" + urllib.parse.quote("../" + os.path.basename(outside.name))
        response = self._request(path, authenticated=True)
        self.assertEqual(response["status"], 404)
        self.assertNotIn(b"outside", response["body"])

    def test_open_api_rejects_non_markdown_and_hidden_markdown(self):
        plain = self._write("secret.txt")
        hidden = self._write(".secret.md")
        for path in (plain, hidden):
            query = urllib.parse.urlencode({"path": path})
            response = self._request("/api/open?" + query, authenticated=True)
            self.assertEqual(response["status"], 400)


class TestPreloadBoundary(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = self.tempdir.name
        with store._lock:
            store._docs.clear()
            store._next_id = 1

    def tearDown(self):
        self.tempdir.cleanup()

    def _write(self, relative, content="content"):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            file.write(content)
        return path

    def test_direct_preload_rejects_non_markdown(self):
        error = mdview.preload_path(self._write("secret.txt", "sensitive"))
        self.assertEqual(error, "not a markdown file")
        self.assertEqual(store.list(), [])

    def test_directory_preload_skips_hidden_and_external_symlinks(self):
        self._write("allowed.md", "allowed")
        self._write(".hidden.md", "hidden")
        outside = tempfile.NamedTemporaryFile(suffix=".md", delete=False)
        outside.write(b"outside")
        outside.close()
        try:
            os.symlink(outside.name, os.path.join(self.root, "outside.md"))
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"symlinks unavailable: {error}")

        self.assertIsNone(mdview.preload_path(self.root))
        self.assertEqual([doc["name"] for doc in store.list()], ["allowed.md"])


if __name__ == "__main__":
    unittest.main()
