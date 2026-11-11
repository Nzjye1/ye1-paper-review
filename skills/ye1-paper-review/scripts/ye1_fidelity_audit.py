#!/usr/bin/env python3
"""Local, advisory comparison of protected tokens in a manuscript rewrite."""
import argparse
import collections
import json
import re
import unicodedata
from pathlib import Path

NUMBER = re.compile(r'(?<![\w])(?:[<>≤≥=]\s*)?[+−–-]?\s*\d+(?:[.,]\d+)*(?:\s*(?:%|％))?',re.I)
CITATION = re.compile(r'\[(?:\s*\d+(?:\s*[-–,，;；]\s*\d+)*\s*|@[^\]]+)\]|\b[A-Z][A-Za-zÀ-ÿ\'-]+(?:\s+et\s+al\.)?\s*\(\d{4}[a-z]?\)',re.I)
FIGURE = re.compile(r'\b(?:fig(?:ure)?|table)\.?\s*\d+[a-z]?|(?:图|表)\s*\d+[a-z]?',re.I)
MEASURE = re.compile(r'(?<!\w)[+−–-]?\d+(?:\.\d+)?\s*(?:mg|mcg|μg|µg|kg|g|mmol/L|mmHg|mL|ml|cm|mm|years?|days?|weeks?|个月|天|岁|小时)(?!\w)',re.I)
ASSIGN = re.compile(r'\b([A-Za-z][A-Za-z -]{2,30}?)\s+(?:was|were|is|of|为|是)\s*([+−–-]?\d+(?:\.\d+)?\s*%?)',re.I)
IDENT = re.compile(r'\b(?:NCT\d{8}|ISRCTN\d+|PMID\s*:?\s*\d+|10\.\d{4,9}/[-._;()/:a-z0-9]+)',re.I)


def counts(pattern,text):
    return collections.Counter(re.sub(r'\s+','',unicodedata.normalize('NFKC',x.group()).casefold()) for x in pattern.finditer(text))


def compare(a,b):
    return {'removed': dict(a-b), 'added':dict(b-a)}


def main():
    ap=argparse.ArgumentParser(description='辅助核对修改前后数字、单位、引用、图表编号及指定术语；不评估语义。')
    ap.add_argument('before',type=Path);ap.add_argument('after',type=Path)
    ap.add_argument('--term',action='append',default=[],help='可重复：应保留的术语')
    ap.add_argument('--out',type=Path,help='可选：只写入新 JSON 文件')
    args=ap.parse_args()
    original=args.before.read_text(encoding='utf-8-sig'); revised=args.after.read_text(encoding='utf-8-sig')
    result={'scope':'本地文本标记计数；不证明语义、事实、引用绑定或因果强度正确。', 'checks':{}}
    for label,pattern in [('citations',CITATION),('figures_tables',FIGURE),('measurements',MEASURE),('identifiers',IDENT)]:
        result['checks'][label]=compare(counts(pattern,original),counts(pattern,revised))
    before_no_cite=CITATION.sub(' ',original);after_no_cite=CITATION.sub(' ',revised)
    result['checks']['numbers']=compare(counts(NUMBER,before_no_cite),counts(NUMBER,after_no_cite))
    result['checks']['simple_label_values']=compare(counts(ASSIGN,original),counts(ASSIGN,revised))
    result['protected_terms']={t:{'before':original.count(t),'after':revised.count(t)} for t in args.term if t}
    changed=any(v['added'] or v['removed'] for v in result['checks'].values()) or any(v['before']!=v['after'] for v in result['protected_terms'].values())
    result['status']='REVIEW_CHANGES' if changed else 'NO_TOKEN_CHANGE_DETECTED'
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with args.out.open('x',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
