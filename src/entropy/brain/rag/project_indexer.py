"""Project Codebase Indexer and Syntax-Aware Local RAG Search (Phase 4)."""

import ast
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

IGNORE_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", ".pytest_cache", ".venv", "venv",
    "node_modules", ".idea", ".vscode", "dist", "build", ".entropy", "skills"
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".exe", ".dll", ".so", ".bin", ".iso", ".zip",
    ".tar", ".gz", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
    ".db", ".sqlite", ".sqlite3", ".wal"
}

class ProjectIndexer:
    """Indexes and retrieves relevant code symbols and files using AST syntax-aware chunking."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = Path(root_dir) if root_dir else Path.cwd()
        # Cache: rel_path -> {"mtime": float, "chunks": List[Dict[str, Any]], "content": str}
        self._file_cache: Dict[str, Dict[str, Any]] = {}
        # Flat list of all active code chunks
        self.chunks: List[Dict[str, Any]] = []

    @property
    def indexed_files(self) -> Dict[str, str]:
        """Backward compatibility property returning rel_path -> content preview."""
        return {path: entry.get("content", "") for path, entry in self._file_cache.items()}

    def scan_and_index(self, max_files: int = 500) -> int:
        """
        T4.2: Scan project files with incremental mtime caching.
        Only re-parses files that have been created or modified since last index.
        """
        current_rel_paths: Set[str] = set()
        indexed_count = 0

        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                ext = Path(file).suffix.lower()
                if ext in IGNORE_EXTENSIONS:
                    continue

                full_path = Path(root) / file
                try:
                    rel_path = str(full_path.relative_to(self.root_dir)).replace("\\", "/")
                    current_rel_paths.add(rel_path)
                    mtime = full_path.stat().st_mtime

                    cached = self._file_cache.get(rel_path)
                    if cached and cached.get("mtime") == mtime:
                        # File is unchanged: keep cached chunks
                        indexed_count += 1
                        continue

                    # File changed or new: parse and chunk
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(100_000)

                    chunks = self._chunk_file(full_path, rel_path, content)
                    self._file_cache[rel_path] = {
                        "mtime": mtime,
                        "content": content[:8000],
                        "chunks": chunks
                    }
                    indexed_count += 1

                    if indexed_count >= max_files:
                        break
                except Exception:
                    continue

            if indexed_count >= max_files:
                break

        # Remove deleted files from cache
        deleted = set(self._file_cache.keys()) - current_rel_paths
        for d in deleted:
            self._file_cache.pop(d, None)

        # Rebuild flat chunks list
        self.chunks = []
        for entry in self._file_cache.values():
            self.chunks.extend(entry.get("chunks", []))

        return indexed_count

    def _chunk_file(self, full_path: Path, rel_path: str, content: str) -> List[Dict[str, Any]]:
        """T4.1: Dispatch syntax-aware chunking based on file extension."""
        ext = full_path.suffix.lower()
        if ext == ".py":
            return self._parse_python_ast(content, rel_path)
        elif ext in {".md", ".markdown"}:
            return self._parse_markdown_sections(content, rel_path)
        else:
            return self._chunk_generic(content, rel_path)

    def _parse_python_ast(self, source_code: str, rel_path: str) -> List[Dict[str, Any]]:
        """T4.1: Extract discrete functions, async functions, and classes using Python AST."""
        chunks = []
        lines = source_code.splitlines()

        try:
            tree = ast.parse(source_code)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = node.lineno
                    end = node.end_lineno or start
                    code_snippet = "\n".join(lines[start - 1:end])
                    doc = ast.get_docstring(node) or ""
                    chunks.append({
                        "symbol": f"def {node.name}()",
                        "type": "function",
                        "path": rel_path,
                        "start_line": start,
                        "end_line": end,
                        "docstring": doc,
                        "content": code_snippet[:2000]
                    })
                elif isinstance(node, ast.ClassDef):
                    start = node.lineno
                    end = node.end_lineno or start
                    code_snippet = "\n".join(lines[start - 1:end])
                    doc = ast.get_docstring(node) or ""
                    chunks.append({
                        "symbol": f"class {node.name}",
                        "type": "class",
                        "path": rel_path,
                        "start_line": start,
                        "end_line": end,
                        "docstring": doc,
                        "content": code_snippet[:2500]
                    })
        except Exception:
            pass

        if not chunks:
            chunks = self._chunk_generic(source_code, rel_path)

        return chunks

    def _parse_markdown_sections(self, content: str, rel_path: str) -> List[Dict[str, Any]]:
        """Chunk Markdown by markdown headers."""
        chunks = []
        sections = re.split(r"(?m)^(#{1,3}\s+.+)$", content)
        if len(sections) > 1:
            for i in range(1, len(sections), 2):
                sec_header = sections[i].strip()
                sec_body = sections[i + 1].strip() if i + 1 < len(sections) else ""
                combined = f"{sec_header}\n{sec_body}"[:2000]
                chunks.append({
                    "symbol": sec_header.lstrip("#").strip(),
                    "type": "section",
                    "path": rel_path,
                    "start_line": 1,
                    "end_line": 1,
                    "docstring": "",
                    "content": combined
                })
        else:
            chunks = self._chunk_generic(content, rel_path)
        return chunks

    def _chunk_generic(self, content: str, rel_path: str) -> List[Dict[str, Any]]:
        """Fallback chunker splitting content by 100-line blocks."""
        chunks = []
        lines = content.splitlines()
        block_size = 100
        step = 80

        if not lines:
            return [{
                "symbol": Path(rel_path).name,
                "type": "file",
                "path": rel_path,
                "start_line": 1,
                "end_line": 1,
                "docstring": "",
                "content": ""
            }]

        for i in range(0, len(lines), step):
            block = lines[i:i + block_size]
            snippet = "\n".join(block)
            chunks.append({
                "symbol": Path(rel_path).name,
                "type": "file_block",
                "path": rel_path,
                "start_line": i + 1,
                "end_line": min(len(lines), i + block_size),
                "docstring": "",
                "content": snippet[:2500]
            })
        return chunks

    def search_codebase(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Find the most relevant source code symbols and chunks.
        Ranks by symbol name match, docstring, filename, and content match.
        """
        terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 1]
        if not terms:
            return []

        scored = []

        for chunk in self.chunks:
            symbol_lower = chunk["symbol"].lower()
            path_lower = chunk["path"].lower()
            content_lower = chunk["content"].lower()
            doc_lower = chunk.get("docstring", "").lower()

            score = 0
            for term in terms:
                # Symbol match carries highest weight
                if term in symbol_lower:
                    score += 15
                if term in doc_lower:
                    score += 8
                if term in path_lower:
                    score += 6
                # Content frequency
                score += min(10, content_lower.count(term) * 2)

            if score > 0:
                snippet = chunk["content"][:300].replace("\n", " ").strip()
                scored.append({
                    "path": chunk["path"],
                    "symbol": chunk["symbol"],
                    "type": chunk["type"],
                    "lines": f"L{chunk['start_line']}-L{chunk['end_line']}",
                    "score": score,
                    "snippet": f"...{snippet}..."
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
