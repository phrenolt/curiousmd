import threading
from collections import OrderedDict


class DocStore:
    def __init__(self):
        self._docs = OrderedDict()
        self._next_id = 1
        self._lock = threading.Lock()

    def add(self, name, content, dir=""):
        with self._lock:
            doc_id = str(self._next_id)
            self._next_id += 1
            self._docs[doc_id] = {"name": name, "content": content, "dir": dir}
        return doc_id

    def remove(self, doc_id):
        with self._lock:
            return self._docs.pop(doc_id, None) is not None

    def list(self):
        with self._lock:
            return [
                {"id": did, "name": d["name"], "dir": d.get("dir", "")}
                for did, d in self._docs.items()
            ]

    def get(self, doc_id):
        with self._lock:
            d = self._docs.get(doc_id)
            if d is None:
                return None
            return {
                "id": doc_id,
                "name": d["name"],
                "dir": d.get("dir", ""),
                "content": d["content"],
            }

    def update(self, doc_id, content):
        with self._lock:
            if doc_id not in self._docs:
                return False
            self._docs[doc_id]["content"] = content
            return True


# Module-level singleton used by the running server
store = DocStore()
