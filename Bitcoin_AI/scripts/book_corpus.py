"""Extrai corpus local por página para estudo, sem alterar/publicar os PDFs."""
import hashlib
import json
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp/book_study"
OUT.mkdir(parents=True, exist_ok=True)
for path in sorted((ROOT / "data/knowledge/books").glob("*.pdf")):
    name = path.name.lower()
    slug = "grimes" if "grimes" in name else "brooks" if "brooks" in name else "aronson" if "aronson" in name else "nison"
    folder = OUT / slug
    folder.mkdir(exist_ok=True)
    reader = PdfReader(path)
    pages = []
    for number, page in enumerate(reader.pages, 1):
        dest = folder / f"{number:04d}.txt"
        if not dest.exists():
            dest.write_text(page.extract_text() or "", encoding="utf-8")
        pages.append({"pdf_page": number, "native_chars": len(dest.read_text(encoding="utf-8")), "method": "native_text", "semantic_review": False})
    record = {"source": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "pages": pages,
              "notice": "Extração/indexação não equivalem a leitura ou compreensão. Corpus privado, ignorado pelo Git."}
    (folder / "manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(slug, len(pages), sum(p["native_chars"] for p in pages), flush=True)
