#!/usr/bin/env python3
"""Render actual RTL display events; the diagnostic emits four points."""
import csv,json
from pathlib import Path
rows=list(csv.DictReader(Path('build/display-events.csv').open()))
assert len(rows)==4
parts=['<svg xmlns="http://www.w3.org/2000/svg" width="640" height="700" viewBox="0 0 640 700">',
'<rect width="640" height="700" fill="#101911"/>',
'<text x="32" y="34" fill="#b8e9a9" font-family="sans-serif" font-size="18">TX-2 RTL — paper-booted display diagnostic</text>',
'<rect x="32" y="58" width="576" height="576" rx="16" stroke="#446a3b" fill="#071208"/>',
'<path d="M320 70V620M44 346H596" stroke="#18371c" stroke-width="1"/>']
events=[]
for i,row in enumerate(rows):
 def decode(value):return -(1023-value) if value&512 else value
 x,y=decode(int(row['x_ones_complement'])),decode(int(row['y_ones_complement']))
 px,py=320+x*0.52,346-y*0.52
 parts.extend([f'<circle cx="{px:.2f}" cy="{py:.2f}" r="9" fill="#88f46e" opacity=".12"/>',
 f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3" fill="#bcff91"/>',
 f'<text x="{px+12:.2f}" y="{py-8:.2f}" fill="#93b889" font-family="monospace" font-size="12">{i+1}: ({x}, {y})</text>'])
 events.append({'cycle':int(row['cycle']),'unit_octal':f"{int(row['unit']):02o}",'x':x,'y':y,'intensity':int(row['intensity'])})
parts.extend(['<text x="32" y="665" fill="#b8e9a9" font-family="sans-serif" font-size="14">4 display events · light-pen handler: RAM counter = 1</text>',
'<text x="32" y="687" fill="#819d79" font-family="sans-serif" font-size="12">Own diagnostic program; event positions are RTL outputs. Not Sketchpad.</text>','</svg>'])
Path('results/display-demo.svg').write_text('\n'.join(parts)+'\n')
Path('results/display-events.json').write_text(json.dumps(events,indent=2)+'\n')
print('Saved results/display-demo.svg from verified RTL events')
