from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from pypdf import PdfReader

from .common import ROOT, config, digest, save_json, versions, write_text

PATTERN = re.compile(r"^BTCUSDT-1m-(\d{4}-\d{2})(?:-\d{2})?\.zip$")


def classify(path: Path) -> str:
    if PATTERN.fullmatch(path.name):
        return "candidato_binance_spot_klines_1m_verificar_schema"
    return {".pdf": "conhecimento_pdf", ".md": "documentação", ".json": "configuração", ".py": "código"}.get(path.suffix.lower(), "revisão_manual")


def audit(root: Path = ROOT) -> dict:
    c = config(root)
    excluded = {".git", "__pycache__", ".venv", ".pytest_cache"}
    files = [p for p in root.rglob("*") if p.is_file() and not excluded.intersection(p.parts)
             and not {"reports", "models", "processed", "features", "targets"}.intersection(p.relative_to(root).parts)]
    items = []
    for p in sorted(files):
        item = {"path": str(p.relative_to(root)), "bytes": p.stat().st_size, "category": classify(p)}
        if p.suffix.lower() in {".zip", ".pdf"}:
            item["sha256"] = digest(p)
        if p.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(p) as z:
                    item["crc_ok"] = z.testzip() is None
                    item["members"] = z.namelist()
                match = PATTERN.fullmatch(p.name)
                item["nominal_month"] = match[1] if match else None
            except (zipfile.BadZipFile, OSError) as e:
                item["error"] = str(e)
        if p.suffix.lower() == ".pdf":
            try:
                r = PdfReader(p)
                item.update(pages=len(r.pages), encrypted=r.is_encrypted)
                if not r.is_encrypted:
                    item["metadata"] = dict(r.metadata or {})
                    item["sample_text_chars"] = sum(len(r.pages[i].extract_text() or "") for i in range(min(8, len(r.pages))))
            except Exception as e:
                item["error"] = str(e)
        items.append(item)
    report = {"files": items, "count": len(items), "bytes": sum(i["bytes"] for i in items), "dependencies": versions(),
              "original_layout": {"raw": c["raw"], "books": c["books"]},
              "initial_received_files": 42, "initial_received_bytes": 195985098,
              "notes": ["Livros preservados em data/knowledge/books; conhecimentos derivados em knowledge/.",
                        "Nomes de arquivos não comprovam origem; esquema, datas, CRC e checksums são verificados na ingestão."]}
    save_json(root / "reports/A_audit.json", report)
    rows = [f"| `{i['path']}` | {i['bytes']} | {i['category']} |" for i in items]
    write_text(root / "reports/A_audit.md", "# A — Auditoria inicial\n\nRecebidos: 42 arquivos, 195.985.098 bytes: 36 ZIPs, 4 PDFs, README e .gitignore.\n\n"
               "Cobertura nominal: 2023-10 a 2026-09. Cobertura efetiva e falhas: relatório B. Nenhum original movido ou alterado.\n\n"
               "Livros em `data/knowledge/books`, preservados. Nison sem texto na amostra; Brooks é suplemento de audiobook; Aronson é tradução automática.\n\n"
               "Python e dependências estão disponíveis; versões exatas no JSON e requirements-lock.txt.\n\n"
               "| Arquivo | Bytes | Classificação |\n|---|---:|---|\n" + "\n".join(rows))
    return report
