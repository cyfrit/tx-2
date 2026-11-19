#!/usr/bin/env python3
"""Collect public TX-2 scans with provenance, hashes and page-level text.

Run from the project root. Resume by rerunning; existing complete PDFs are reused.
Mirrors preserve the original scanned documents. Catalog dates are metadata only.
"""
import concurrent.futures
import hashlib
import json
import pathlib
import re
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import pymupdf as fitz
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[1]
REF = ROOT / 'references'
MIRROR = 'https://ftpmirror.your.org/pub/misc/bitsavers/pdf/'
for directory in ['catalog', 'pdfs', 'text', 'page-index', 'figures']:
    (REF / directory).mkdir(exist_ok=True, parents=True)


def fetch(url, timeout=60):
    request = urllib.request.Request(url, headers={'User-Agent': 'TX2-documentation-research/1.0'})
    return urllib.request.urlopen(request, timeout=timeout)


def catalog_html(url, filename):
    dest = REF / 'catalog' / filename
    if not dest.exists():
        dest.write_bytes(fetch(url).read())
    return BeautifulSoup(dest.read_text(), 'html.parser')


def archive_metadata(identifier):
    path = REF / 'catalog' / (identifier + '.json')
    if path.exists():
        return json.loads(path.read_text())
    data = json.load(fetch('https://archive.org/metadata/' + identifier))
    path.write_text(json.dumps(data, indent=2))
    return data


def archive_job(identifier, group):
    try:
        data = archive_metadata(identifier)
        pdfs = [f for f in data.get('files', []) if f['name'].lower().endswith('.pdf')]
        if not pdfs:
            return {'id': identifier, 'group': group, 'status': 'no_public_pdf',
                    'source_url': 'https://archive.org/details/' + identifier}
        pdfs.sort(key=lambda f: (f.get('source') != 'original', int(f.get('size', '0'))))
        chosen = pdfs[0]
        meta = data.get('metadata', {})
        return {
            'id': identifier, 'group': group, 'title': meta.get('title', identifier),
            'catalog_date': meta.get('date'), 'creator': meta.get('creator'),
            'source_url': 'https://archive.org/details/' + identifier,
            'download_url': 'https://archive.org/download/' + identifier + '/' + urllib.parse.quote(chosen['name']),
            'filename': identifier + '.pdf', 'archive_identifier': identifier,
            'archive_pdf_name': chosen['name'],
        }
    except Exception as exc:
        print(f'FAILED {identifier} metadata: {exc}', flush=True)
        return {'id': identifier, 'group': group, 'status': 'metadata_failed', 'error': type(exc).__name__}


def build_jobs():
    jobs = []
    locations = [('mit/tx-2/', 'mirror-2.html', 'core'),
                 ('mit/tx-2/rcsri.org_library_tx2/', 'rcsri.org_library_tx2.html', 'user-memos')]
    for sub, saved, group in locations:
        soup = catalog_html(MIRROR + sub, saved)
        for a in soup.select('a[href]'):
            name = a['href']
            if name.lower().endswith('.pdf'):
                jobs.append({'id': name[:-4], 'group': group, 'title': name[:-4],
                             'source_url': 'http://bitsavers.org/pdf/' + sub + name,
                             'download_url': urllib.parse.urljoin(MIRROR + sub, name), 'filename': name})
    # Additional hardware and architecture precursors; these are categorized
    # separately from documentation of the operating TX-2.
    division = catalog_html(MIRROR + 'mit/lincolnLaboratory/division_6/', 'division_6.html')
    prefixes = ['6D-2631_', '6M-3144_', '6M-3284_', '6M-3417_', '6M-3536_', '6M-5649_']
    for a in division.select('a[href]'):
        name = a['href']
        if any(name.startswith(p) for p in prefixes):
            jobs.append({'id': name[:-4], 'group': 'hardware-and-precursors', 'title': name[:-4],
                         'source_url': 'http://bitsavers.org/pdf/mit/lincolnLaboratory/division_6/' + name,
                         'download_url': MIRROR + 'mit/lincolnLaboratory/division_6/' + name, 'filename': name})
    name = '6D-108-2_SLIDES_VIEWGRAPHS_19571231.pdf'
    jobs.append({'id': name[:-4], 'group': 'drawing-index', 'title': 'Division 6 slides and viewgraphs index',
                 'source_url': 'http://bitsavers.org/pdf/mit/lincolnLaboratory/MC665/' + name,
                 'download_url': MIRROR + 'mit/lincolnLaboratory/MC665/' + name, 'filename': name})

    soup = catalog_html('https://tx-2.github.io/documentation/ll-progress-reports', 'progress-reports.html')
    inventory = []
    archive_ids = {}
    section = ''
    for node in soup.find_all(['h2', 'h3', 'tr']):
        if node.name in ('h2', 'h3'):
            section = node.get_text(' ', strip=True)
            continue
        row = node.get_text(' ', strip=True)
        for a in node.select('a[href]'):
            url = a['href']
            inventory.append({'section': section, 'row': row, 'url': url})
            match = re.search(r'archive.org/details/([^/]+)', url)
            # All early construction/commissioning reports and all dedicated
            # Graphics reports; later broad research reports remain cataloged.
            if match and ('Graphics' == section or re.match(r'19(?:5[6-9]|6[0-3])-', row)):
                archive_ids[match.group(1)] = 'graphics-reports' if section == 'Graphics' else 'early-progress-reports'
    (REF / 'catalog' / 'progress-report-inventory.json').write_text(json.dumps(inventory, indent=2))
    archive_ids.update({'ad-0235247': 'peripherals', 'DTIC_AD0727768': 'later-memory',
                        'DTIC_AD0406608': 'graphics-hardware'})
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(archive_job, ident, group) for ident, group in archive_ids.items()]
        for future in concurrent.futures.as_completed(futures):
            jobs.append(future.result())
    # The RCS library also preserves quick-reference posters, separate from PDFs.
    rcs = catalog_html('https://www.rcsri.org/library/tx2/index.shtml', 'mirror-1.html')
    for a in rcs.select('a[href]'):
        name = a['href']
        if name.startswith('tx2-poster-') and name.endswith('.jpg'):
            jobs.append({'id': name[:-4], 'group': 'reference-posters', 'title': name,
                         'source_url': urllib.parse.urljoin('https://www.rcsri.org/library/tx2/', name),
                         'download_url': urllib.parse.urljoin('https://www.rcsri.org/library/tx2/', name),
                         'filename': name})
    chm = REF / 'catalog' / 'chm-github-contents.json'
    if not chm.exists():
        chm.write_bytes(fetch('https://api.github.com/repos/computerhistory/Historical-Highlights-Documents-Repository/contents/').read())
    for item in json.loads(chm.read_text()):
        if item['name'].startswith('Sketchpad Pt'):
            name = 'Sketchpad_listing_part' + ('1' if 'Pt 1' in item['name'] else '2')
            jobs.append({'id': name, 'group': 'historical-source-listings', 'title': item['name'],
                         'source_url': 'https://www.computerhistory.org/collections/catalog/102726903',
                         'download_url': item['download_url'], 'filename': name + '.pdf',
                         'github_blob_sha': item['sha']})
    return jobs


def collect(job):
    job = dict(job)
    if 'download_url' not in job:
        return job
    dest = REF / ('figures' if job['filename'].endswith('.jpg') else 'pdfs') / job['filename']
    try:
        if not dest.exists():
            partial = dest.with_suffix(dest.suffix + '.part')
            subprocess.run([
                'aria2c', '--continue=true', '--auto-file-renaming=false',
                '--allow-overwrite=true', '--file-allocation=none',
                '--max-connection-per-server=4', '--split=4', '--min-split-size=4M',
                '--max-tries=2', '--retry-wait=1', '--timeout=60',
                '--connect-timeout=20', '--summary-interval=0',
                '--console-log-level=error', '--download-result=hide',
                '--dir=' + str(partial.parent), '--out=' + partial.name,
                job['download_url'],
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1200)
            partial.replace(dest)
        digest = hashlib.sha256()
        with dest.open('rb') as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        job.update({'path': str(dest.relative_to(ROOT)), 'bytes': dest.stat().st_size,
                    'sha256': digest.hexdigest(), 'retrieved_at': datetime.now(timezone.utc).isoformat()})
        if dest.suffix == '.pdf':
            with fitz.open(dest) as doc:
                if not doc.is_pdf:
                    raise ValueError('Response is not a PDF')
                pages = []
                chunks = []
                for index, page in enumerate(doc):
                    text = page.get_text(sort=True)
                    pages.append({'pdf_page': index + 1, 'pdf_index': index,
                                  'characters': len(text.strip()), 'text': text})
                    chunks.append(f'\n\f\n[PDF PAGE {index + 1}; ZERO-BASED INDEX {index}]\n' + text)
                stem = dest.stem
                text_path = REF / 'text' / (stem + '.txt')
                pages_path = REF / 'page-index' / (stem + '.jsonl')
                text_path.write_text(''.join(chunks))
                pages_path.write_text('\n'.join(json.dumps(p, ensure_ascii=False) for p in pages) + '\n')
                job.update({'pages': len(pages), 'text_characters': sum(p['characters'] for p in pages),
                            'pages_with_text': sum(p['characters'] >= 80 for p in pages),
                            'text_path': str(text_path.relative_to(ROOT)),
                            'page_index_path': str(pages_path.relative_to(ROOT))})
                if 'archive_identifier' in job:
                    meta = archive_metadata(job['archive_identifier'])
                    for f in meta.get('files', []):
                        if f['name'].endswith('_djvu.txt'):
                            ocr_path = REF / 'text' / (stem + '.archive-ocr.txt')
                            if not ocr_path.exists():
                                ocr_path.write_bytes(fetch('https://archive.org/download/' + job['archive_identifier'] + '/' + urllib.parse.quote(f['name'])).read())
                            job['archive_ocr_path'] = str(ocr_path.relative_to(ROOT))
                            break
        job['status'] = 'downloaded'
        print(f"OK {job['id']} {job.get('pages', 'image')} pages {job['bytes'] / 1e6:.1f} MB", flush=True)
    except Exception as exc:
        job.update({'status': 'failed', 'error': type(exc).__name__})
        print(f"FAILED {job['id']} {exc}", flush=True)
    return job


def main():
    jobs = build_jobs()
    (REF / 'catalog' / 'download-jobs.json').write_text(json.dumps(jobs, ensure_ascii=False, indent=2))
    print(f'Collecting {len(jobs)} documents/images', flush=True)
    manifest = []
    manifest_path = REF / 'catalog' / 'manifest.json'
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(collect, job) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            manifest.append(record)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print('COMPLETE', len(manifest), 'records', sum(m['status'] == 'downloaded' for m in manifest), 'downloaded', flush=True)


if __name__ == '__main__':
    main()
