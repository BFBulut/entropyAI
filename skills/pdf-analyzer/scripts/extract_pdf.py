#!/usr/bin/env python3
"""CLI utility to extract text and tables from PDF documents."""

import sys
import argparse
import json
from pathlib import Path
import pypdf

def extract_pdf(pdf_path: str) -> dict:
    p = Path(pdf_path)
    if not p.exists():
        return {"error": f"File not found: {pdf_path}"}

    reader = pypdf.PdfReader(str(p))
    pages = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        pages.append({"page": i + 1, "text": text})

    return {
        "filename": p.name,
        "total_pages": len(reader.pages),
        "pages": pages
    }

def main():
    parser = argparse.ArgumentParser(description="Extract text from PDF")
    parser.add_argument("--file", "-f", required=True, help="Path to PDF file")
    args = parser.parse_args()

    result = extract_pdf(args.file)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
