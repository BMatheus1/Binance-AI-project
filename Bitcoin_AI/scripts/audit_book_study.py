"""Audita derivados e preservação; não confunde extração com compreensão.

As páginas de revisão abaixo são um registro editorial explícito de passagens
analisadas. Não são inferidas de OCR, tamanho de texto ou solicitações de leitura.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'knowledge/study'


def pages(spec):
    result = set()
    for part in spec.split(','):
        if not part.strip():
            continue
        limits = [int(x) for x in part.split('-')]
        result.update(range(limits[0], limits[-1] + 1))
    return sorted(result)


REVIEW = {
    'grimes': {
        'passages': '3-4,7-15,20-23,30-32,56-61,65-69,81-84,111-120,134-140,159-172,175-193,196-202,205-208,226-229,247-250,279-282,300-309,356-359,363-365,382-384,391-392,406-413,425,431-436',
        'visual': '',
        'limitation': 'Leitura temática aprofundada de passagens dos 12 capítulos; diversos exemplos, trechos e apêndices ainda não revisados integralmente.',
    },
    'brooks': {
        'passages': '1-5,7-9,202-209',
        'visual': '16,69,82,93,136,141,152,200',
        'limitation': 'Suplemento do audiobook; exposição textual integral e áudio ausentes. Varredura de legendas não equivale à inspeção de cada gráfico.',
    },
    'aronson': {
        'passages': '1-15,17-18,25-26,30-36,51-52,72-73,103-104,129-133,164-165,186-187,214-216,218-220,222-224,234-240,247,252-254,285-290,295-300',
        'visual': '',
        'limitation': 'Tradução automática; arquivo termina no meio do capítulo 6, PDF300/página impressa302. Capítulos7-9 e final do livro ausentes.',
    },
    'nison': {
        'passages': '1,8-10,12-23,35-37,40-43,51-53,56-58,61-62,67-68,72,77-78,90-92,96-97,130-131,146-148,160-162,183,188,195-196,203,211,219,225,236-238,249-250,256,261,265-266,272-273,279-280,284,289-304,307-309,315-316',
        'visual': '1,8-10,14-15,35-37,42,91,161',
        'limitation': 'OCR pt-BR de original inglês: erros possíveis. Edição e sequência editorial não certificadas. Leitura de passagens selecionadas e glossário; numerosos exemplos ainda sem revisão detalhada.',
    },
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    books = []
    for slug, review in REVIEW.items():
        folder = ROOT / 'tmp/book_study' / slug
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        source = ROOT / manifest['source']
        total = len(manifest['pages'])
        selected = set(pages(review['passages']))
        visual = set(pages(review['visual']))
        assert all(1 <= n <= total for n in selected | visual)
        current_hash = digest(source)
        assert current_hash == manifest['sha256'], f'Original alterado: {source}'
        records = []
        for n in range(1, total + 1):
            native = folder / f'{n:04d}.txt'
            ocr = folder / f'{n:04d}.ocr.txt'
            ocr_meta = folder / f'{n:04d}.ocr.json'
            assert native.exists(), (slug, n)
            if slug in ('brooks', 'nison'):
                assert ocr.exists() and ocr_meta.exists(), (slug, n)
                meta = json.loads(ocr_meta.read_text(encoding='utf-8-sig'))
                assert meta['pdf_page'] == n
            records.append({
                'pdf_page': n,
                'native_extracted': True,
                'ocr_completed': ocr.exists() and ocr_meta.exists(),
                'selected_passages_reviewed': n in selected,
                'visual_review_recorded': n in visual,
                'partial_caption_scan': slug == 'brooks' and 11 <= n <= 201,
            })
        books.append({
            'id': slug, 'source': str(source.resolve()),
            'sha256': current_hash, 'source_unchanged': True,
            'pdf_pages': total, 'integral_semantic_reading_completed': False,
            'selected_passage_pages': sorted(selected),
            'visual_pages': sorted(visual),
            'pages_without_recorded_passage_or_visual_review': [
                n for n in range(1, total + 1) if n not in selected | visual
            ],
            'limitation': review['limitation'], 'page_records': records,
        })
    output = {
        'study_date': '2026-10-17',
        'definitions': {
            'native_extracted': 'O extrator processou a página; o resultado pode ser vazio ou conter apenas rodapé.',
            'ocr_completed': 'Derivado local de OCR gerado, sem garantia de acurácia ou compreensão.',
            'selected_passages_reviewed': 'Há passagens analisadas nessa página; não certifica revisão integral de todo o texto, notas ou gráfico da página.',
            'visual_review_recorded': 'Página exibida para inspeção visual dirigida; não implica validação empírica do exemplo.',
            'partial_caption_scan': 'Varredura da última legenda reconhecida por página; pode omitir outras legendas e não interpreta todos os gráficos.',
        },
        'books': books,
        'totals': {
            'pdf_pages_processed': sum(b['pdf_pages'] for b in books),
            'ocr_pages_completed': sum(r['ocr_completed'] for b in books for r in b['page_records']),
            'pages_with_selected_passages_reviewed': sum(len(b['selected_passage_pages']) for b in books),
            'pages_with_visual_review_recorded': sum(len(b['visual_pages']) for b in books),
        },
        'warning': 'Extração e OCR completos não são leitura integral. Páginas com revisão registrada também podem conter partes ainda não estudadas.',
    }
    (DEST / 'coverage.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    original = json.loads((ROOT / 'reports/originals_preserved.json').read_text(encoding='utf-8'))
    preservation = []
    for entry in original['files']:
        actual = digest(ROOT / entry['file'])
        preservation.append({'file': entry['file'], 'sha256': actual, 'unchanged': actual == entry['sha256']})
    assert all(x['unchanged'] for x in preservation), 'Um original divergiu do registro anterior'
    (DEST / 'preservation.json').write_text(json.dumps({
        'study_date': '2026-10-17', 'checked': len(preservation),
        'all_unchanged': True, 'files': preservation,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(output['totals'], ensure_ascii=False))
    print('Originais preservados:', len(preservation))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
