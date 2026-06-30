import os

MD_EXTS = (".md", ".markdown", ".mdown", ".mkd", ".mdx")
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


class FilesystemBrowser:
    def __init__(self, root=None):
        self.root = os.path.realpath(root) if root else None

    def _root(self):
        return self.root or os.path.realpath(os.getcwd())

    def resolve(self, path):
        root = self._root()
        path = (path or "").replace("\\", "/")
        if not path:
            return root
        if os.path.isabs(path):
            resolved = os.path.realpath(path)
        else:
            resolved = os.path.realpath(os.path.join(root, path))
        if not (resolved == root or resolved.startswith(root + os.sep)):
            return root
        return resolved

    def list_dir(self, path=None):
        full = self.resolve(path or "")
        if not full or not os.path.isdir(full):
            return None
        entries = []
        try:
            with os.scandir(full) as it:
                for entry in it:
                    if entry.name.startswith("."):
                        continue
                    try:
                        entry_path = os.path.realpath(entry.path)
                        is_dir = entry.is_dir(follow_symlinks=True)
                        is_file = entry.is_file(follow_symlinks=True)
                    except OSError:
                        continue
                    if is_dir:
                        entries.append({"type": "dir", "name": entry.name, "path": entry_path})
                    elif is_file and entry.name.lower().endswith(MD_EXTS):
                        entries.append({"type": "file", "name": entry.name, "path": entry_path})
        except OSError as e:
            return {"dir": full, "entries": [], "error": str(e)}
        entries.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))
        return {"dir": full, "entries": entries}

    def open_file(self, path, add_doc_fn):
        full = self.resolve(path)
        if not full or not os.path.isfile(full):
            return None, "not found"
        if not full.lower().endswith(MD_EXTS):
            return None, "not a markdown file"
        try:
            if os.path.getsize(full) > MAX_FILE_SIZE:
                return None, "file is too large"
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as e:
            return None, str(e)
        dir_part = os.path.dirname(full)
        doc_id = add_doc_fn(os.path.basename(full), content, dir=dir_part)
        return {"id": doc_id, "name": os.path.basename(full), "dir": dir_part}, None


# Module-level singleton; root is set at startup via browser.root = ...
browser = FilesystemBrowser()
