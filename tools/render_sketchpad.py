#!/usr/bin/env python3
"""Render the CRT events emitted by the running reconstructed Sketchpad."""
import csv,hashlib,json,re
from collections import Counter
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((ROOT/'results/sketchpad-points.csv').open()))
assert rows,'Sketchpad produced no CRT events'
def decode(value):
 value=int(value);return value if value<512 else -(1023-value)
points=Counter((decode(r['x']),decode(r['y'])) for r in rows)
fig,ax=plt.subplots(figsize=(8,8),facecolor='#061009')
ax.set_facecolor('#061009')
x,y=zip(*points)
ax.scatter(x,y,s=2.1,c='#a4ff78',linewidths=0)
ax.set_xlim(-511,511);ax.set_ylim(-511,511);ax.set_aspect('equal');ax.set_axis_off()
ax.set_title('Sketchpad listing reconstruction — TX-2 RTL',color='#d3ebcb',fontsize=12,pad=15)
fig.text(.5,.07,'Actual CRT events after paper boot',ha='center',color='#7c9979',fontsize=9)
for ext in ['png','svg']:
 fig.savefig(ROOT/'results'/f'sketchpad-screen.{ext}',dpi=180,bbox_inches='tight',facecolor=fig.get_facecolor())
plt.close(fig)
lines=(ROOT/'results/sketchpad-run.txt').read_text().splitlines()
stats={}
for line in lines[:2]:
 for key,value in re.findall(r'(\w+)=([^ ]+)',line):stats[key]=value
assert stats['fault']=='0',stats
assert stats.get('paper_boot')=='1' and stats['paper_position']==stats['paper_count'] and stats['rewinds']=='1',stats
assert int(stats['application_retirements'])>100000 and len(points)>500,stats
seq={m[1]:int(m[2]) for line in lines if (m:=re.match(r'sequence=([0-7]+) retirements=(\d+)',line))}
assert seq.get('60',0)>1000 and seq.get('76',0)>1000,seq
application_clocks=int(stats['cycles'])-int(stats['application_cycle_start'])
assert int(rows[-1]['cycle'])-int(stats['application_cycle_start'])>0.9*application_clocks,'display stopped refreshing'
changes=[]
for name in ['main','calculate','constraints','math','display','io','build']:
 data=json.loads((ROOT/'work/sketchpad'/f'{name}-expanded.json').read_text())
 changes.extend({'module':name,**c} for c in data['changes'])
report={'scope':'Recovered historical listing, assembled with recorded fixes; headless RTL execution',
 'run':stats,'sequence_retirements':seq,'display_events':len(rows),'first_display_cycle':int(rows[0]['cycle']),'last_display_cycle':int(rows[-1]['cycle']),'unique_display_positions':len(points),
 'x_range':[min(x),max(x)],'y_range':[min(y),max(y)],
 'image':json.loads((ROOT/'results/sketchpad-image.json').read_text()),
 'paper':json.loads((ROOT/'results/sketchpad-paper.json').read_text()),
 'source_changes':changes,'source_change_counts':dict(Counter(c['class'] for c in changes)),
 'rtl_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'rtl').glob('*.v'))},
 'run_log_sha256':hashlib.sha256((ROOT/'results/sketchpad-run.log').read_bytes()).hexdigest(),
 'limitations':['Transcription contains inferred repairs; this is not a verified original binary',
 'Private compiler RC helpers relocated into existing U RAM; module model base normalized to 22000 octal',
 'IOSAL suppressed during UNITS OFF for unimplemented offline devices; alarm 080 remains latched',
 'This headless run verifies startup and refresh; browser drawing evidence is recorded separately in browser-integration.json',
 'Constraint workflows, general editing and historical peripherals still require separate validation',
 'CRT image accumulates emitted coordinates; analog phosphor and real light pen not modeled']}
(ROOT/'results/sketchpad-run.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(f"PASS: physical paper boot, {stats['paper_count']} lines, {stats['retired']} retirements, {len(rows)} CRT events, {len(points)} positions, fault=0")
print('Saved results/sketchpad-screen.png and results/sketchpad-run.json')
