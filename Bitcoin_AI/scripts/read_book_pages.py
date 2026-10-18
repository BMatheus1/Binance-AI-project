"""Mostra páginas completas limpas e registra somente a solicitação de leitura.

O registro não atesta compreensão: a revisão semântica é documentada nos dossiês.
"""
import argparse,json,re,sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
p=argparse.ArgumentParser()
p.add_argument("book")
p.add_argument("pages",help="1-3,8,10-12")
p.add_argument("--ocr",action="store_true")
p.add_argument("--layout",action="store_true")
args=p.parse_args()
root=Path(__file__).resolve().parents[1]
folder=root/"tmp/book_study"/args.book
numbers=[]
for part in args.pages.split(','):
    ends=[int(x) for x in part.split('-')]
    numbers.extend(range(ends[0],ends[-1]+1))
for n in numbers:
    suffix='layout.txt' if args.layout else 'ocr.txt' if args.ocr else 'txt'
    path=folder/f"{n:04d}.{suffix}"
    text=path.read_text(encoding="utf-8")
    lines=[]
    for line in text.splitlines():
        if re.match(r"P1:|JWBT634-|Machine Translated by Google",line):continue
        if args.book=='brooks' and any(s in line for s in ['This PDF file','reproduced, copied, circulated','Point Books & Media']):continue
        lines.append(re.sub(r'\s+',' ',line).strip())
    print(f"\n=== {args.book.upper()} | PDF {n} ===\n"+'\n'.join(lines))
log=folder/'read_requests.jsonl'
with log.open('a',encoding='utf-8') as f:f.write(json.dumps({'pages':numbers,'method':'layout' if args.layout else 'ocr' if args.ocr else 'native','output_truncation_must_be_checked':True})+'\n')
