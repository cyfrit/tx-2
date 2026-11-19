#!/usr/bin/env python3
"""Index IA OCR word boxes by PDF page for exactly matching scan files."""
import concurrent.futures
import hashlib
import json
import pathlib
import subprocess
import xml.etree.ElementTree as ET

import pymupdf
from collect_primary_sources import archive_metadata

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAIRS = [
    ('tx-2-users-handbook-nov-63', 'TX-2_UsersHandbook_Nov63'),
    ('tx-2-tech-man-vol-2-jun-61', 'TX-2_TechManVol2_Jun61'),
    ('tx-2-tech-man-vol-3-jul-61', 'TX-2_TechManVol3_Jul61'),
    ('bitsavers_mittx2TX2P_6403361', 'TX-2_Papers_WJCC_57'),
    ('bitsavers_mittx2TX2U_1831851', 'TX-2_UserHandbook_ch3'),
    ('bitsavers_mittx2TX2P_2073486', 'TX-2_ProgExamp'),
    ('bitsavers_mittx2TX2C_10802013', 'TX-2_Circuitry'),
    ('bitsavers_mittx2AComdAccessMagneticTapeSystemwithFixedAddres_586318',
     'A_Computer-Integrated_Rapid_Access_Magnetic_Tape_System_with_Fixed_Address'),
]


def process(pair):
    ident, stem = pair
    metadata = archive_metadata(ident)
    expected_pdf = next(f for f in metadata['files'] if f['name'] == stem + '.pdf')
    pdf_path = ROOT / ('references/pdfs/' + stem + '.pdf')
    actual_md5 = hashlib.md5(pdf_path.read_bytes()).hexdigest()
    if actual_md5 != expected_pdf['md5']:
        raise ValueError(f'{stem}: archive PDF checksum differs; OCR pairing rejected')
    relative_xml = 'references/catalog/' + stem + '_djvu.xml'
    path = ROOT / relative_xml
    if not path.exists():
        subprocess.run(['aria2c', '-q', '-x4', '-s4', '-k1M', '--continue=true',
                        '--auto-file-renaming=false', '--dir=' + str(path.parent),
                        '--out=' + path.name,
                        'https://archive.org/download/' + ident + '/' + stem + '_djvu.xml'],
                       check=True, timeout=300)
    tree = ET.parse(path)
    objects = tree.findall('.//OBJECT')
    with pymupdf.open(ROOT / ('references/pdfs/' + stem + '.pdf')) as pdf:
        if len(objects) != len(pdf):
            raise ValueError(f'{stem}: OCR has {len(objects)} pages, PDF has {len(pdf)}; mapping rejected')
    pages = []
    for i, obj in enumerate(objects):
        lines = [' '.join(''.join(w.itertext()) for w in line.findall('.//WORD'))
                 for line in obj.findall('.//LINE')]
        text = '\n'.join(lines)
        pages.append({'pdf_page': i + 1, 'pdf_index': i, 'characters': len(text.strip()),
                      'text': text, 'text_origin': 'Internet Archive DjVu XML OCR',
                      'ocr_source': relative_xml})
    out = ROOT / ('references/page-index/' + stem + '.archive-ocr.jsonl')
    out.write_text('\n'.join(json.dumps(p, ensure_ascii=False) for p in pages) + '\n')
    text_path = ROOT / ('references/text/' + stem + '.archive-page-ocr.txt')
    text_path.write_text('\n'.join(f'\n\f\n[PDF PAGE {p["pdf_page"]}]\n' + p['text'] for p in pages))
    print(stem, len(pages), 'OCR pages indexed', flush=True)
    return {'id': stem, 'archive_page_index_path': str(out.relative_to(ROOT)),
            'archive_page_text_path': str(text_path.relative_to(ROOT)),
            'ocr_pages': len(pages), 'mapping_check': 'Original PDF MD5 matches IA metadata; PDF page count equals OCR OBJECT count'}


if __name__ == '__main__':
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        pending = {executor.submit(process, pair): pair for pair in PAIRS}
        for future in concurrent.futures.as_completed(pending):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({'id': pending[future][1], 'status': 'failed', 'error': type(exc).__name__})
                print('FAILED', pending[future][1], str(exc), flush=True)
            (ROOT / 'references/catalog/archive-page-ocr.json').write_text(json.dumps(results, indent=2))
    if any(x.get('status') == 'failed' for x in results):
        raise SystemExit(1)
