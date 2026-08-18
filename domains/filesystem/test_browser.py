import os
import tempfile
import unittest
from domains.filesystem.browser import FilesystemBrowser, MAX_FILE_SIZE


class TestResolve(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.browser = FilesystemBrowser(root=self.tmp)

    def test_empty_path_returns_root(self):
        self.assertEqual(self.browser.resolve(""), self.tmp)

    def test_path_inside_root(self):
        sub = os.path.join(self.tmp, "sub")
        os.makedirs(sub)
        self.assertEqual(self.browser.resolve(sub), sub)

    def test_path_outside_root_rejected(self):
        escaped = os.path.join(self.tmp, "..", "..", "etc", "passwd")
        self.assertIsNone(self.browser.resolve(escaped))

    def test_absolute_path_outside_rejected(self):
        self.assertIsNone(self.browser.resolve("/etc/passwd"))

    def test_hidden_path_is_rejected(self):
        hidden = os.path.join(self.tmp, ".private", "notes.md")
        os.makedirs(os.path.dirname(hidden))
        open(hidden, "w").close()
        self.assertIsNone(self.browser.resolve(hidden))


class TestListDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.browser = FilesystemBrowser(root=self.tmp)

    def _touch(self, *parts):
        path = os.path.join(self.tmp, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
        return path

    def test_lists_md_files(self):
        self._touch("README.md")
        result = self.browser.list_dir()
        names = [e["name"] for e in result["entries"]]
        self.assertIn("README.md", names)

    def test_excludes_non_md_files(self):
        self._touch("script.py")
        result = self.browser.list_dir()
        names = [e["name"] for e in result["entries"]]
        self.assertNotIn("script.py", names)

    def test_excludes_hidden_files(self):
        self._touch(".hidden.md")
        result = self.browser.list_dir()
        names = [e["name"] for e in result["entries"]]
        self.assertNotIn(".hidden.md", names)

    def test_excludes_hidden_dirs(self):
        os.makedirs(os.path.join(self.tmp, ".git"))
        result = self.browser.list_dir()
        names = [e["name"] for e in result["entries"]]
        self.assertNotIn(".git", names)

    def test_includes_subdirs(self):
        os.makedirs(os.path.join(self.tmp, "docs"))
        result = self.browser.list_dir()
        names = [e["name"] for e in result["entries"]]
        self.assertIn("docs", names)

    def test_dirs_come_before_files(self):
        self._touch("z.md")
        os.makedirs(os.path.join(self.tmp, "aaa"))
        result = self.browser.list_dir()
        types = [e["type"] for e in result["entries"]]
        # dirs should appear before files
        first_file = next((i for i, t in enumerate(types) if t == "file"), len(types))
        first_dir = next((i for i, t in enumerate(types) if t == "dir"), len(types))
        self.assertLess(first_dir, first_file)

    def test_invalid_path_returns_none(self):
        result = self.browser.list_dir(os.path.join(self.tmp, "nonexistent"))
        self.assertIsNone(result)

    def test_returns_dir_key(self):
        result = self.browser.list_dir()
        self.assertIn("dir", result)

    def test_excludes_symlinked_directory_outside_root(self):
        outside = tempfile.mkdtemp()
        link = os.path.join(self.tmp, "outside")
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"symlinks unavailable: {error}")
        names = [entry["name"] for entry in self.browser.list_dir()["entries"]]
        self.assertNotIn("outside", names)

    def test_excludes_symlinked_markdown_outside_root(self):
        outside = tempfile.NamedTemporaryFile(suffix=".md", delete=False)
        outside.close()
        link = os.path.join(self.tmp, "outside.md")
        try:
            os.symlink(outside.name, link)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"symlinks unavailable: {error}")
        names = [entry["name"] for entry in self.browser.list_dir()["entries"]]
        self.assertNotIn("outside.md", names)


class TestOpenAndWrite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.browser = FilesystemBrowser(root=self.tmp)
        self.docs = []

    def _add(self, name, content, dir=""):
        self.docs.append({"name": name, "content": content, "dir": dir})
        return str(len(self.docs))

    def _write(self, name, content="content"):
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            file.write(content)
        return path

    def test_opens_markdown_inside_root(self):
        path = self._write("notes.md", "allowed")
        doc, error = self.browser.open_file(path, self._add)
        self.assertIsNone(error)
        self.assertEqual(doc["name"], "notes.md")
        self.assertEqual(self.docs[0]["content"], "allowed")

    def test_rejects_non_markdown_file(self):
        path = self._write("secret.txt")
        doc, error = self.browser.open_file(path, self._add)
        self.assertIsNone(doc)
        self.assertEqual(error, "not a markdown file")

    def test_rejects_hidden_markdown_file(self):
        path = self._write(".secret.md")
        doc, error = self.browser.open_file(path, self._add)
        self.assertIsNone(doc)
        self.assertEqual(error, "not found")

    def test_rejects_markdown_symlink_outside_root(self):
        outside = tempfile.NamedTemporaryFile(suffix=".md", delete=False)
        outside.write(b"sensitive")
        outside.close()
        link = os.path.join(self.tmp, "notes.md")
        try:
            os.symlink(outside.name, link)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"symlinks unavailable: {error}")
        doc, error = self.browser.open_file(link, self._add)
        self.assertIsNone(doc)
        self.assertEqual(error, "not found")

    def test_rejects_oversized_markdown_file(self):
        path = self._write("large.md", "x" * (MAX_FILE_SIZE + 1))
        doc, error = self.browser.open_file(path, self._add)
        self.assertIsNone(doc)
        self.assertEqual(error, "file is too large")

    def test_write_revalidates_root_boundary(self):
        outside = tempfile.NamedTemporaryFile(suffix=".md", delete=False)
        outside.write(b"sensitive")
        outside.close()
        link = os.path.join(self.tmp, "notes.md")
        try:
            os.symlink(outside.name, link)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"symlinks unavailable: {error}")
        self.assertEqual(self.browser.write_file(link, "changed"), "not found")
        with open(outside.name, "r", encoding="utf-8") as file:
            self.assertEqual(file.read(), "sensitive")


if __name__ == "__main__":
    unittest.main()
