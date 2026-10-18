"""Índice local de assuntos; não publica nem armazena cópias integrais de livros."""
from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader

from .common import ROOT, config, digest, save_json

TERMS = {
    "candles": ["candlestick", "pavio", "doji", "hammer"],
    "tendencia": ["trend", "tendência", "tendencia"],
    "suporte_resistencia": ["support", "resistance", "suporte", "resistência"],
    "rompimentos": ["breakout", "rompimento"],
    "pullback": ["pullback", "retração"],
    "reversao": ["reversal", "reversão"],
    "volume": ["volume"],
    "volatilidade": ["volatility", "volatilidade"],
    "validacao": ["hypothesis", "bootstrap", "data mining", "hipóteses", "mineração de dados"],
}


def index_books(root: Path = ROOT) -> dict:
    books = []
    for path in sorted((root / config(root)["books"]).glob("*.pdf")):
        logging.info("Indexando PDF %s", path.name)
        item = {"file": str(path.relative_to(root)), "sha256": digest(path), "references": []}
        try:
            r = PdfReader(path)
            item.update(pages=len(r.pages), metadata=dict(r.metadata or {}))
            if r.is_encrypted:
                item["status"] = "protegido; não acessado"
            else:
                readable = 0
                for number, page in enumerate(r.pages, 1):
                    text = (page.extract_text() or "").lower()
                    if len(text.strip()) >= 80:
                        readable += 1
                    categories = [k for k, words in TERMS.items() if any(w in text for w in words)]
                    if categories:
                        item["references"].append({"pdf_page": number, "topics": categories, "status": "localização por palavras; requer leitura contextual"})
                item.update(readable_pages=readable, status="texto acessível" if readable else "digitalizado; OCR não executado")
        except Exception as e:
            item.update(status="inacessível", error=str(e))
        books.append(item)
    report = {"books": books, "method": "Índice determinístico, páginas PDF físicas (1-based), sem reproduzir texto integral.",
              "limits": ["Ocorrência de termo não equivale a conceito validado.", "Gráficos requerem leitura visual; OCR completo pendente quando necessário.",
                         "Referências verificadas e formalizações próprias ficam em knowledge/concepts/verified.md."]}
    save_json(root / "knowledge/references/books.json", report)
    save_json(root / "reports/C_knowledge.json", report)
    return report
