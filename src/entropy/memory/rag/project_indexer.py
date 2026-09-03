"""Project Codebase Indexer and Local RAG Search."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Set

IGNORE_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", ".pytest_cache", ".venv", "venv",
    "node_modules", ".idea", ".vscode", "dist", "build"
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".exe", ".dll", ".so", ".bin", ".iso", ".zip",
    ".tar", ".gz", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2"
}

class ProjectIndexer:
    """Indexes and retrieves relevant code files from the selected project directory."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = Path(root_dir) if root_dir else Path.cwd()
        self.indexed_files: Dict[str, str] = {}  # rel_path -> snippet/content

    def scan_and_index(self, max_files: int = 500) -> int:
        """Scan project files and cache them for instant retrieval."""
        self.indexed_files.clear()
        count = 0

        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                ext = Path(file).suffix.lower()
                if ext in IGNORE_EXTENSIONS:
                    continue

                full_path = Path(root) / file
                try:
                    rel_path = str(full_path.relative_to(self.root_dir))
                    # Read first 8000 characters for indexing
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(8000)
                    self.indexed_files[rel_path] = content
                    count += 1
                    if count >= max_files:
                        return count
                except Exception:
                    continue

        return count

    def search_codebase(self, query: str, top_k: int = 5) -> List[Dict[str, str]]:
        """Find the most relevant source files matching query keywords."""
        terms = [t.lower() for t in query.split() if len(t) > 2]
        scored = []

        for rel_path, content in self.indexed_files.items():
            content_lower = content.lower()
            path_lower = rel_path.lower()
            score = 0

            for term in terms:
                if term in path_lower:
                    score += 5  # filename match weight
                score += min(10, content_lower.count(term))

            if score > 0:
                # Find matching snippet preview
                first_match_idx = -1
                for term in terms:
                    idx = content_lower.find(term)
                    if idx != -1:
                        first_match_idx = idx
                        break

                snippet_start = max(0, first_match_idx - 100) if first_match_idx != -1 else 0
                snippet_end = min(len(content), snippet_start + 300)
                preview = content[snippet_start:snippet_end].replace("\n", " ").strip()

                scored.append({
                    "path": rel_path,
                    "score": score,
                    "snippet": f"...{preview}..."
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
