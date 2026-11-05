#!/usr/bin/env python3
"""Run MedSci's table arithmetic detector on a normalized working copy.

Only ordinary top-level DOCX tables and Markdown pipe tables are considered.
No finding is proof that every table, cell, or scientific denominator was checked.
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from dataclasses import asdict
from pathlib import Path

from check_table_percentages import TOTAL_LABEL_RE, _cell_count_pct, _parse_tables, audit


def docx_tables(path: Path):
    from docx import Document
    from docx.oxml.ns import qn

    tables, skipped = [], []
    for number, table in enumerate(Document(path).tables, 1):
        complex_cells = any(
            cell._tc.find('.//' + qn('w:gridSpan')) is not None
            or cell._tc.find('.//' + qn('w:vMerge')) is not None
            for row in table.rows for cell in row.cells
        )
        if complex_cells or len(table.rows) < 2:
            skipped.append({"table": number, "reason": "merged cells or fewer than two rows"})
            continue
        rows = [[" ".join(cell.text.split()).replace('|', '/') for cell in row.cells]
                for row in table.rows]
        if not rows[0] or any(len(row) != len(rows[0]) for row in rows):
            skipped.append({"table": number, "reason": "irregular rows"})
            continue
        line = lambda row: '| ' + ' | '.join(row) + ' |'
        md = [line(rows[0]), line(['---'] * len(rows[0]))] + [line(row) for row in rows[1:]]
        tables.append((number, '\n'.join(md)))
    return tables, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='A DOCX, Markdown, or text working file')
    args = parser.parse_args()
    path = Path(args.input)
    if path.suffix.lower() == '.docx':
        texts, skipped = docx_tables(path)
    else:
        texts = [('markdown', path.read_text(encoding='utf-8'))]
        skipped = []
    findings, coverage = [], []
    for number, text in texts:
        # Normalize only the in-memory detector input; never rewrite the manuscript.
        normalized = unicodedata.normalize('NFKC', text)
        candidate_cells = sum(
            1 for _header, rows, _line in _parse_tables(normalized)
            for row in rows if row and not TOTAL_LABEL_RE.match(row[0])
            for cell in row[1:] if _cell_count_pct(cell)
        )
        coverage.append({'table': number, 'n_parenthesized_candidates': candidate_cells,
                         'note': 'Syntactic candidates only; this is not a count of verified cells.'})
        report = audit(normalized, source=str(path))
        findings.extend({'table': number, **asdict(item)} for item in report.findings)
    print(json.dumps({'input': str(path), 'tables_considered': [x[0] for x in texts],
                      'skipped': skipped, 'coverage': coverage, 'findings': findings,
                      'scope': 'Only recognized n (%) cells and inferred/declared denominators; '
                               'zero candidates means no n (%) cells were checked. Separate count and '
                               'percentage columns require independent calculation. Verify original '
                               'table and actual denominators.'},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
