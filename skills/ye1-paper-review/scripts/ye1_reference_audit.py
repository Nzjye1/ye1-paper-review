#!/usr/bin/env python3
"""Check explicit public reference identifiers against Crossref and PubMed."""
import argparse
import csv
import datetime as dt
import difflib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DOI_RE = re.compile(r'10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+', re.I)
PMID_RE = re.compile(r'\bPMID\s*[:：]?\s*(\d{4,9})\b|pubmed\.ncbi\.nlm\.nih\.gov/(\d{4,9})', re.I)


def clean_doi(value):
    m = DOI_RE.search(value or '')
    return m.group(0).rstrip('.,;:)]}').lower() if m else ''


def parse_bib(text):
    """Extract balanced BibTeX entries without assuming a single-line entry."""
    entries = []
    pos = 0
    while True:
        m = re.search(r'@([A-Za-z]+)\s*\{', text[pos:])
        if not m:
            break
        start = pos + m.start(); brace = pos + m.end() - 1
        depth = 0; end = None; escaped = False
        for i in range(brace, len(text)):
            c = text[i]
            if escaped:
                escaped = False; continue
            if c == '\\':
                escaped = True; continue
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0: end = i + 1; break
        if end is None:
            raise ValueError('BibTeX 括号未闭合，未继续解析；请先检查原文献列表。')
        entry = text[start:end]; pos = end
        if m.group(1).lower() in ('comment', 'preamble', 'string'): continue
        key = re.match(r'@\w+\s*\{\s*([^,]+)', entry)
        title = re.search(r'\btitle\s*=\s*(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|"([^"]*)")', entry, re.I | re.S)
        year = re.search(r'\byear\s*=\s*[{\"]?(\d{4})', entry, re.I)
        doi = re.search(r'\bdoi\s*=\s*[{\"]([^}\"]+)', entry, re.I)
        pmid = re.search(r'\bpmid\s*=\s*[{\"]?(\d{4,9})', entry, re.I)
        entries.append({'label': key.group(1).strip() if key else str(len(entries)+1),
                        'title': re.sub(r'[{}]', '', (title.group(1) or title.group(2))) if title else '',
                        'year': year.group(1) if year else '', 'doi': clean_doi(doi.group(1)) if doi else '',
                        'pmid': pmid.group(1) if pmid else '', 'raw': entry})
    return entries


def reference_section_docx(path):
    try:
        from docx import Document
    except ImportError as exc:
        raise ValueError('读取 Word 参考文献需要 python-docx；也可导出纯参考文献列表。') from exc
    doc = Document(path)
    lines=[]; found=False
    for para in doc.paragraphs:
        value=para.text.strip()
        if not found:
            if re.fullmatch(r'(?:references|bibliography|参考文献|引用文献)\s*[:：]?',value,re.I): found=True
            continue
        if value and (para.style.name.lower().startswith('heading') or re.fullmatch(r'(?:appendix|supplement|附录|补充材料)\b.*',value,re.I)):
            break
        if value: lines.append(value)
    if not found or not lines:
        raise ValueError('未找到可识别的 Word 参考文献标题或条目；请另存公开参考文献列表。')
    return '\n'.join(lines)


def parse_input(path):
    text = reference_section_docx(path) if path.suffix.lower() == '.docx' else path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() == '.bib': return parse_bib(text)
    if path.suffix.lower() in ('.csv', '.tsv'):
        dialect = '\t' if path.suffix.lower() == '.tsv' else ','
        result = []
        for i, row in enumerate(csv.DictReader(text.splitlines(), delimiter=dialect), 1):
            d = {str(k).strip().lower(): (v or '').strip() for k,v in row.items() if k is not None}
            result.append({'label': d.get('id') or d.get('key') or str(i), 'title': d.get('title',''),
                           'year': d.get('year',''), 'doi': clean_doi(d.get('doi','')),
                           'pmid': d.get('pmid',''), 'raw': ''})
        return result
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'): continue
        pm = PMID_RE.search(line)
        rows.append({'label': str(len(rows)+1), 'title':'', 'year':'', 'doi': clean_doi(line),
                     'pmid': (pm.group(1) or pm.group(2)) if pm else '', 'raw': line})
    return rows


def request_json(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Ye1-reference-audit/1.0 (bibliographic verification)', 'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def crossref(doi):
    url = 'https://api.crossref.org/works/' + urllib.parse.quote(doi, safe='/')
    data = request_json(url)['message']
    dates = data.get('published',{}).get('date-parts',[]) or data.get('created',{}).get('date-parts',[])
    return {'source':'Crossref', 'url':url, 'doi':data.get('DOI',''),
            'title':(data.get('title') or [''])[0], 'year':str(dates[0][0]) if dates and dates[0] else '',
            'publisher':data.get('publisher',''), 'type':data.get('type','')}


def title_candidates(title):
    params = urllib.parse.urlencode({'query.title': title, 'rows': 3, 'select': 'DOI,title,published'})
    url = 'https://api.crossref.org/works?' + params
    items = request_json(url)['message'].get('items', [])
    return [{'source':'Crossref title search', 'doi':i.get('DOI',''),
             'title':(i.get('title') or [''])[0], 'url':'https://doi.org/'+i.get('DOI','')}
            for i in items]


def pubmed(pmid):
    params = urllib.parse.urlencode({'db':'pubmed','id':pmid,'retmode':'json','tool':'ye1-reference-audit'})
    url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?' + params
    result = request_json(url).get('result', {})
    item = result.get(pmid)
    if not isinstance(item, dict) or item.get('error'): raise ValueError('PubMed 未返回对应题录')
    dois = [a.get('value','') for a in item.get('articleids',[]) if a.get('idtype') == 'doi']
    return {'source':'PubMed','url':'https://pubmed.ncbi.nlm.nih.gov/'+pmid+'/', 'pmid':pmid,
            'doi':dois[0] if dois else '', 'title':item.get('title',''), 'year':item.get('pubdate','')[:4],
            'publication_types':item.get('pubtype',[])}


def normalized(s):
    return ' '.join(re.findall(r'\w+', s.casefold(), flags=re.UNICODE))


def compare(entry, evidence):
    warnings = []
    if entry['doi'] and evidence.get('doi') and clean_doi(evidence['doi']) != entry['doi']:
        warnings.append('DOI 不一致')
    if entry['title'] and evidence.get('title'):
        a,b = normalized(entry['title']),normalized(evidence['title'])
        if a and b and difflib.SequenceMatcher(None,a,b).ratio() < 0.9:
            warnings.append('题名差异，请人工核对')
    if entry['year'] and evidence.get('year') and entry['year'] != evidence['year']:
        warnings.append('年份不同，请检查在线发表、正式出版及原始记录')
    return warnings


def main():
    ap = argparse.ArgumentParser(description='按已提供 DOI/PMID 核对公开参考文献，不自动搜索题名。')
    ap.add_argument('input', type=Path, help='仅包含参考文献的 BibTeX、CSV、TSV 或逐行文本')
    ap.add_argument('--out', type=Path, required=True, help='新的 JSON 文件路径，不覆盖现有文件')
    ap.add_argument('--offline', action='store_true', help='不联网，保留未核实状态')
    ap.add_argument('--allow-title-lookup', action='store_true', help='只对无 DOI/PMID 且有 title 的条目发送标题到 Crossref；须事先确认是公开文献标题')
    args = ap.parse_args()
    if args.input.suffix.lower() not in ('.bib','.csv','.tsv','.txt','.md','.docx'):
        ap.error('仅支持 bib/csv/tsv/txt/md/docx；Word 只从可识别的参考文献节提取')
    if args.out.exists(): ap.error('输出文件已存在，请指定新路径')
    try: records = parse_input(args.input)
    except (OSError, UnicodeError, ValueError) as e: ap.error(str(e))
    if not records: ap.error('没有解析到文献条目；请检查格式')
    output = {'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(), 'input':str(args.input),
              'offline':args.offline,'scope':'仅核对明确提供的 DOI/PMID；结果不证明文献支持正文，撤稿状态另核。','entries':[]}
    for rec in records:
        item = {k:v for k,v in rec.items() if k != 'raw'}
        item.update({'status':'UNVERIFIED','evidence':[], 'warnings':[], 'errors':[]})
        if rec['pmid'] and not re.fullmatch(r'\d{4,9}', rec['pmid']):
            item['errors'].append('PMID 格式无效'); rec['pmid']=''
        if not args.offline:
            for ident, fn in ((rec['doi'],crossref),(rec['pmid'],pubmed)):
                if not ident: continue
                try:
                    ev=fn(ident); item['evidence'].append(ev); item['warnings'].extend(compare(rec,ev)); time.sleep(0.4)
                except (OSError,ValueError,KeyError,urllib.error.URLError) as e:
                    item['errors'].append(f'{fn.__name__}: {type(e).__name__}: {e}')
        if not args.offline and args.allow_title_lookup and not rec['doi'] and not rec['pmid'] and rec['title']:
            try:
                item['title_candidates'] = title_candidates(rec['title']); time.sleep(0.4)
            except (OSError,ValueError,KeyError,urllib.error.URLError) as e:
                item['errors'].append(f'title_search: {type(e).__name__}: {e}')
        if item['evidence']:
            item['status'] = 'NEEDS_REVIEW' if item['warnings'] else 'IDENTIFIER_FOUND'
        output['entries'].append(item)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    try:
        with args.out.open('x',encoding='utf-8') as f: json.dump(output,f,ensure_ascii=False,indent=2)
    except OSError as e: ap.error(str(e))
    print(f"已记录 {len(records)} 条；识别成功不等于与正文论述一致。输出：{args.out}")

if __name__ == '__main__': main()
