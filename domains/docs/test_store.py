import threading
import unittest
from domains.docs.store import DocStore


class TestDocStore(unittest.TestCase):
    def setUp(self):
        self.store = DocStore()

    def test_add_and_get(self):
        doc_id = self.store.add("README.md", "# Hello", dir="/home/user")
        doc = self.store.get(doc_id)
        self.assertEqual(doc["name"], "README.md")
        self.assertEqual(doc["content"], "# Hello")
        self.assertEqual(doc["dir"], "/home/user")
        self.assertEqual(doc["id"], doc_id)

    def test_add_increments_id(self):
        id1 = self.store.add("a.md", "")
        id2 = self.store.add("b.md", "")
        self.assertNotEqual(id1, id2)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get("nonexistent"))

    def test_remove_existing(self):
        doc_id = self.store.add("f.md", "content")
        self.assertTrue(self.store.remove(doc_id))
        self.assertIsNone(self.store.get(doc_id))

    def test_remove_missing_returns_false(self):
        self.assertFalse(self.store.remove("ghost"))

    def test_list_empty(self):
        self.assertEqual(self.store.list(), [])

    def test_list_returns_all(self):
        self.store.add("a.md", "")
        self.store.add("b.md", "")
        names = [d["name"] for d in self.store.list()]
        self.assertIn("a.md", names)
        self.assertIn("b.md", names)

    def test_list_preserves_insertion_order(self):
        self.store.add("first.md", "")
        self.store.add("second.md", "")
        names = [d["name"] for d in self.store.list()]
        self.assertEqual(names, ["first.md", "second.md"])

    def test_update_content(self):
        doc_id = self.store.add("f.md", "old")
        self.assertTrue(self.store.update(doc_id, "new"))
        self.assertEqual(self.store.get(doc_id)["content"], "new")

    def test_update_missing_returns_false(self):
        self.assertFalse(self.store.update("ghost", "data"))

    def test_list_excludes_content(self):
        self.store.add("f.md", "content")
        listing = self.store.list()
        self.assertNotIn("content", listing[0])

    def test_concurrent_adds(self):
        results = []
        def add_one():
            results.append(self.store.add("x.md", ""))
        threads = [threading.Thread(target=add_one) for _ in range(20)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(len(results), 20)
        self.assertEqual(len(set(results)), 20)  # all unique IDs


if __name__ == "__main__":
    unittest.main()
