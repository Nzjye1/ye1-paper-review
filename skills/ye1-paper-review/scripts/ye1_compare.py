#!/usr/bin/env python3
"""Compare two Word files using Word on macOS, then audit the saved result."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import os
from lxml import etree as ET
import zipfile
from pathlib import Path
from ye1_revision_check import audit, load, marks

APPLESCRIPT=r'''
on run argv
  set seedPath to item 1 of argv
  set changedPath to item 2 of argv
  set authorName to item 3 of argv
  set waitSeconds to (item 4 of argv) as integer
  with timeout of waitSeconds seconds
    tell application "Microsoft Word"
      open POSIX file seedPath
      set workingDoc to active document
      compare workingDoc path changedPath author name authorName target compare target current detect format changes false ignore all comparison warnings true
      save workingDoc
      close workingDoc saving no
    end tell
  end timeout
end run
'''

def add_line_numbers(path):
    ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    part=path.with_suffix('.line-numbers.tmp')
    try:
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(part,'w') as target:
            for info in source.infolist():
                data=source.read(info.filename)
                if info.filename=='word/document.xml':
                    root=ET.fromstring(data)
                    for section in root.iter(ns+'sectPr'):
                        if section.find(ns+'lnNumType') is not None:continue
                        number=ET.Element(ns+'lnNumType',{ns+'countBy':'1',ns+'restart':'continuous'})
                        children=list(section); margin=section.find(ns+'pgMar')
                        section.insert(children.index(margin)+1 if margin is not None else 0,number)
                    data=ET.tostring(root,encoding='utf-8',xml_declaration=True)
                target.writestr(info,data)
        os.replace(part,path)
    finally:part.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('original','revised','out'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--author',default='Ye1');p.add_argument('--timeout',type=int,default=300);p.add_argument('--line-numbers',action='store_true',help='按需添加连续行号')
    a=p.parse_args()
    if sys.platform!='darwin':p.error('该工具需要 macOS 和 Microsoft Word；其他系统使用宿主的 Word 比较功能。')
    for f in (a.original,a.revised):
        if not f.is_file():p.error(f'输入不存在: {f}')
        if marks(load(f)[0])[0]:p.error('输入含未决修订；保留原有修订并使用适合的 Word 工具处理。')
    if a.out.exists() or a.out.suffix.lower()!='.docx' or not a.out.parent.is_dir():p.error('输出必须是已有目录中的新 DOCX 文件。')
    base=Path.home()/'Library/Containers/com.microsoft.Word/Data/Documents'
    if not base.is_dir():p.error('未找到 Word 容器；先启动 Word 并检查文件访问权限。')
    with tempfile.TemporaryDirectory(prefix='ye1-compare-',dir=base) as folder:
        temp=Path(folder);source=temp/(temp.name+'-base.docx');change=temp/(temp.name+'-changed.docx')
        shutil.copyfile(a.original,source);shutil.copyfile(a.revised,change)
        try:
            result=subprocess.run(['osascript','-',str(source),str(change),a.author,str(a.timeout)],input=APPLESCRIPT,text=True,capture_output=True,timeout=a.timeout+15)
        except subprocess.TimeoutExpired:
            raise SystemExit('Word 操作超时；请检查 Word 是否有权限或提示窗口。本工具未写入输出。')
        if result.returncode:raise SystemExit('Word 比较失败；本工具未写入输出：'+result.stderr.strip())
        if a.line_numbers:add_line_numbers(source)
        outcome=audit(source,a.original,a.revised,a.author)
        if outcome['issues']:
            print(json.dumps(outcome,ensure_ascii=False,indent=2))
            raise SystemExit('比较结果存在待核问题，未写入输出。')
        created=False
        try:
            with a.out.open('xb') as dst, source.open('rb') as src:
                created=True;shutil.copyfileobj(src,dst)
        except Exception:
            if created:a.out.unlink(missing_ok=True)
            raise
        print(json.dumps(outcome,ensure_ascii=False,indent=2))
        print('已生成:',a.out)

if __name__=='__main__':main()
