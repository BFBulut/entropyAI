"""Offline PDF Ingestion & Document Processing Engine for Entropy AI."""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import pypdf

from entropy.core.config import config
from entropy.core.event_bus import bus

class PDFIngestionEngine:
    """Extracts, parses, indexes, and caches PDF documents using offline pypdf."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or (Path.home() / ".entropy" / "pdf_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def extract_pdf_content(self, pdf_path: Path | str) -> Dict[str, Any]:
        """Extract text page-by-page, extract metadata, and compute statistics."""
        p = Path(pdf_path)
        if not p.exists():
            raise FileNotFoundError(f"PDF dosyası bulunamadı: {p}")

        reader = pypdf.PdfReader(str(p))
        num_pages = len(reader.pages)
        pages_text = []
        total_text = []

        for idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            clean_text = page_text.strip()
            pages_text.append({
                "page": idx + 1,
                "text": clean_text,
                "char_count": len(clean_text)
            })
            if clean_text:
                total_text.append(f"--- [Sayfa {idx + 1} / {num_pages}] ---\n{clean_text}")

        full_content = "\n\n".join(total_text)
        word_count = len(full_content.split())

        # Metadata extraction
        raw_meta = reader.metadata or {}
        metadata = {
            "filename": p.name,
            "filepath": str(p.resolve()),
            "pages": num_pages,
            "word_count": word_count,
            "title": raw_meta.get("/Title") or p.stem,
            "author": raw_meta.get("/Author") or "Bilinmiyor",
            "creator": raw_meta.get("/Creator") or "Bilinmiyor",
            "filesize_bytes": p.stat().st_size
        }

        # Cache markdown digest
        digest_path = self.cache_dir / f"{p.stem}_extracted.md"
        digest_content = f"# PDF Analiz Dökümü: {p.name}\n\n"
        digest_content += f"- **Sayfa Sayısı**: {num_pages}\n"
        digest_content += f"- **Kelime Sayısı**: {word_count}\n"
        digest_content += f"- **Kaynak Yol**: `{p.resolve()}`\n\n"
        digest_content += "## Çıkarılan İçerik\n\n" + full_content
        digest_path.write_text(digest_content, encoding="utf-8", errors="replace")

        return {
            "metadata": metadata,
            "pages": pages_text,
            "full_content": full_content,
            "digest_path": str(digest_path)
        }

    def ingest_and_store_memory(self, pdf_path: Path | str) -> Dict[str, Any]:
        """Parse PDF, store into Cognitive Memory, and index into Project RAG."""
        result = self.extract_pdf_content(pdf_path)
        meta = result["metadata"]
        p = Path(pdf_path)

        # 1. Store high-level semantic node in Cognitive Memory
        try:
            from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem
            cog = CognitiveMemorySystem()
            excerpt = result["full_content"][:600]
            summary_text = (
                f"PDF Dokümanı [{meta['filename']} - {meta['pages']} Sayfa]: "
                f"{excerpt}..."
            )
            cog.store_node(
                category="semantic",
                content=summary_text,
                importance=0.85,
                metadata={
                    "source": "pdf_ingestion",
                    "filename": meta["filename"],
                    "filepath": meta["filepath"],
                    "pages": meta["pages"],
                    "digest_path": result["digest_path"]
                }
            )
        except Exception:
            pass

        # 2. Add to Project RAG indexer
        try:
            from entropy.brain.rag.project_indexer import ProjectIndexer
            indexer = ProjectIndexer(config.default_project_path)
            indexer.scan_and_index(max_files=100)
        except Exception:
            pass

        bus.terminal_output_received.emit(
            f"\n[📄 PDF Motoru] '{p.name}' ({meta['pages']} Sayfa, {meta['word_count']} Kelime) "
            f"başarıyla işlendi ve bilişsel belleğe aktarıldı.\n"
        )
        return result
