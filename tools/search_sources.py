#!/usr/bin/env python3
"""Search extracted TX-2 document text and retain physical PDF page numbers."""
import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('pattern', help='Case-insensitive regular expression')
parser.add_argument('--source', default='', help='Document ID substring')
parser.add_argument('--limit', type=int, default=20)
args = parser.parse_args()
regex = re.compile(args.pattern, re.I)
manifest = json.loads((ROOT / 'references/catalog/manifest.json').read_text())
ocr = {x['id']: x for x in json.loads((ROOT / 'references/catalog/archive-page-ocr.json').read_text())
       if x.get('status') != 'failed'}
count = 0
for doc in manifest:
    if args.source not in doc['id'] or doc.get('status') != 'downloaded' or not doc.get('pages'):
        continue
    preferred = ocr.get(doc['id'], {}).get('archive_page_index_path', doc['page_index_path'])
    for line in (ROOT / preferred).open():
        page = json.loads(line)
        match = regex.search(page['text'])
        if match:
            excerpt = page['text'][max(0, match.start() - 70):match.end() + 240]
            print(f"{doc['id']} | PDF page {page['pdf_page']} | {page.get('text_origin', 'PDF text layer')}")
            print(' '.join(excerpt.split()))
            print(f"{doc['path']}#page={page['pdf_page']}\n")
            count += 1
            if count >= args.limit:
                raise SystemExit(0)
