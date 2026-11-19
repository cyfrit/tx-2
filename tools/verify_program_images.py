#!/usr/bin/env python3
"""Reject stale saved assembler outputs and invalid paper block checksums."""
import hashlib,json
from pathlib import Path
import tx2tape
summary=[]
for name in ['hello','display-demo']:
 source=Path('programs',name+'.tx2as');digest=hashlib.sha256(source.read_bytes()).hexdigest()
 image=source.with_suffix('.hex').read_text();meta=json.loads(source.with_suffix('.tape.json').read_text())
 assert f'# source_sha256 {digest}' in image and meta['source_sha256']==digest, f'{name}: stale assembler outputs'
 tape=tx2tape.read(source.with_suffix('.tape'))
 assert all(b&tx2tape.FEED for b in tape) and len(tape)%6==0 and len(tape)==meta['paper_lines'] and meta['reader_leader_words']==20
 blocks=tx2tape.blocks(tape)
 assert blocks and all(b.get('checksum_ok') for b in blocks), f'{name}: bad block or checksum'
 assert all(b['next']==3 for b in blocks[:-1]), f'{name}: nonfinal block does not return to loader'
 summary.append({'name':name,'source_sha256':digest,'tape_sha256':hashlib.sha256(tape).hexdigest(),'paper_lines':len(tape),'blocks':len(blocks)})
Path('build/fixture-validation.json').write_text(json.dumps(summary,indent=2)+'\n')
print('PASS: saved source/image provenance and paper block checksums')
