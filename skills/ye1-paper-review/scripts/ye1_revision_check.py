#!/usr/bin/env python3
"""Inspect Word tracked changes and compare their accepted/rejected main text."""
import argparse
from collections import Counter
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
REV={'ins','del','moveTo','moveFrom'}

def load(path):
    with ZipFile(path) as z:
        root=ET.fromstring(z.read('word/document.xml'))
        comments=ET.fromstring(z.read('word/comments.xml')) if 'word/comments.xml' in z.namelist() else None
    return root,comments

def marks(root):
    values=Counter();authors=set()
    for node in root.iter():
        name=node.tag.removeprefix(W)
        if node.tag.startswith(W) and name in REV:
            values[name]+=1
            authors.add(node.get(W+'author',''))
    return dict(values), sorted(authors)

def text(root,mode):
    parts=[]
    def walk(node,show=True):
        tag=node.tag.removeprefix(W)
        if node.tag.startswith(W):
            if tag in ('ins','moveTo') and mode=='reject':show=False
            if tag in ('del','moveFrom') and mode=='accept':show=False
            if show and tag in ('t','delText','instrText','delInstrText'):
                # Field instructions are not visible document text.
                if tag in ('t','delText'):parts.append(node.text or '')
            elif show and tag in ('tab','br','cr'):parts.append(' ')
        for child in node:walk(child,show)
    walk(root)
    return re.sub(r'\s+',' ',''.join(parts)).strip()

def comments(doc,xml):
    if xml is None:return Counter(),Counter()
    all_comments=Counter();anchored=Counter()
    begins={x.get(W+'id') for x in doc.iter(W+'commentRangeStart')}
    ends={x.get(W+'id') for x in doc.iter(W+'commentRangeEnd')}
    refs={x.get(W+'id') for x in doc.iter(W+'commentReference')}
    for c in xml.iter(W+'comment'):
        signature=(c.get(W+'author',''),''.join(x.text or '' for x in c.iter(W+'t')))
        all_comments[signature]+=1
        if c.get(W+'id') in begins & ends & refs:anchored[signature]+=1
    return all_comments,anchored

def audit(marked,original,revised,author=None):
    m,mc=load(marked); o,oc=load(original); r,rc=load(revised)
    mm,ma=marks(m);om,_=marks(o);rm,_=marks(r)
    issues=[]; warnings=[]
    if om or rm:issues.append('BASE_HAS_REVISIONS: 基准或修改稿包含未决修订，无法用全部接受／拒绝核对；不得自动删除。')
    if not mm:issues.append('NO_REVISIONS: 未发现正文修订标记。')
    accept_ok=text(m,'accept')==text(r,'accept');reject_ok=text(m,'reject')==text(o,'accept')
    if not accept_ok:issues.append('ACCEPT_MISMATCH: 接受修订后的正文与修改稿不同。')
    if not reject_ok:issues.append('REJECT_MISMATCH: 拒绝修订后的正文与基准稿不同。')
    if author and ma and set(ma)!={author}:issues.append('AUTHOR_MISMATCH: 修订作者不一致或缺失。')
    tables={k:len(list(v.iter(W+'tbl'))) for k,v in [('marked',m),('original',o),('revised',r)]}
    if tables['marked']!=tables['revised']:issues.append('TABLE_COUNT_MISMATCH: 带修订稿和修改稿的表格数量不同。')
    old,old_anchors=comments(o,oc)
    for label,doc,comment_xml in [('marked',m,mc),('revised',r,rc)]:
        now,anchors=comments(doc,comment_xml)
        if old-now or old_anchors-anchors:issues.append(f'COMMENT_LOSS: {label} 缺少原有普通批注或其基本锚点。')
        if now-old:warnings.append(f'COMMENT_ADDED_OR_DUPLICATED: {label} 有新增或重复批注，需核对。')
    return {'scope':'仅核对主文档可见文字、表格数量、普通批注及基本锚点；不验证批注具体位置、页眉页脚、图片、复杂域及页面布局。',
            'revision_counts':mm,'authors':ma,'table_counts':tables,'accept_matches':accept_ok,'reject_matches':reject_ok,'issues':issues,'warnings':warnings}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for x in ('marked','original','revised'):p.add_argument('--'+x,required=True,type=Path)
    p.add_argument('--author');p.add_argument('--out',type=Path);p.add_argument('--strict',action='store_true')
    args=p.parse_args();report=audit(args.marked,args.original,args.revised,args.author)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with args.out.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return int(args.strict and bool(report['issues']))

if __name__=='__main__':raise SystemExit(main())
