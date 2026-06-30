import os
import tempfile
import unittest
from domains.filesystem.browser import FilesystemBrowser


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

    def test_path_outside_root_clamped(self):
        escaped = os.path.join(self.tmp, "..", "..", "etc", "passwd")
        result = self.browser.resolve(escaped)
        self.assertTrue(result == self.tmp or result.startswith(self.tmp + os.sep))

    def test_absolute_path_outside_clamped(self):
        result = self.browser.resolve("/etc/passwd")
        self.assertTrue(result == self.tmp or result.startswith(self.tmp + os.sep))


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


if __name__ == "__main__":
    unittest.main()
