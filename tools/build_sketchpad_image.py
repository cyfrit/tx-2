#!/usr/bin/env python3
"""Decode assembler paper blocks into an absolute RTL memory image.
Addresses come from binary block headers, never abbreviated listing columns.
"""
import argparse,hashlib,json,subprocess,shutil
import tx2tape
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MASK=(1<<18)-1

def decode_tape(path):
 raw=path.read_bytes();assert len(raw)%6==0
 words=[]
 for pos in range(0,len(raw),6):
  value=0
  for col,line in enumerate(raw[pos:pos+6]):
   for bit in range(6):value|=((line>>bit)&1)<<(6*bit+5-col)
  words.append(value)
 pos=20;image={};blocks=[]
 while pos<len(words):
  count_field=words[pos]>>18
  count=1-(count_field if count_field<1<<17 else -((~count_field)&MASK))
  end=words[pos]&MASK;start=end-count+1
  assert count>0 and pos+count+1<len(words),(path,pos,count)
  body=words[pos+1:pos+count+1]
  blocks.append({'start':f'{start:06o}','count':count})
  if start!=0o27:
   for addr,value in enumerate(body,start):
    assert 0<=addr<1<<17
    if addr in image:assert image[addr]==value,(path,addr)
    image[addr]=value
  pos+=count+2
 return image,blocks

def main():
 p=argparse.ArgumentParser();p.add_argument('--modules',nargs='+',default=['main']);p.add_argument('--assemble',action='store_true');args=p.parse_args()
 merged={};owners={};reports=[];conflicts=[];rc=0o210000
 for name in args.modules:
  if args.assemble:
   subprocess.run(['python3','tools/prepare_sketchpad.py','--module',name,'--rc-origin',f'{rc:o}'],cwd=ROOT,check=True)
   with (ROOT/'results'/f'sketchpad-{name}-assembly.log').open('w') as out:
    subprocess.run([str(ROOT/'work/tx2-sketchpad-tools/target/debug/tx2m4as'),'--list','--output',f'build/sketchpad-{name}.tape',f'work/sketchpad/{name}-expanded.tx2as'],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,check=True)
  image,blocks=decode_tape(ROOT/'build'/f'sketchpad-{name}.tape')
  helpers=[a for a in image if a>=0o210000]
  assert not helpers or max(helpers)<=0o217777,(name,'private RC exceeds U',max(helpers))
  if helpers:rc=(max(helpers)+8)&~7
  reports.append({'module':name,'words':len(image),'blocks':blocks,'private_rc_next':f'{rc:06o}',
    'source_sha256':hashlib.sha256((ROOT/'work/sketchpad'/f'{name}-expanded.tx2as').read_bytes()).hexdigest()})
  for addr,value in image.items():
   if addr in merged and merged[addr]!=value:
    conflicts.append({'address':f'{addr:06o}','earlier':owners[addr],'later':name,'old':f'{merged[addr]:012o}','new':f'{value:012o}'})
   merged[addr]=value;owners[addr]=name
 # Build one physical paper stream with the original reader leader and
 # independently balanced one's-complement checksums. No RTL loader shortcuts.
 raw=(ROOT/'build/sketchpad-main.tape').read_bytes();leader=[]
 for pos in range(0,120,6):
  leader.append(sum(((raw[pos+c]>>bit)&1)<<(6*bit+5-c) for c in range(6) for bit in range(6)))
 paper_words=list(leader);paper_blocks=[]
 ranges=[]
 for address,value in sorted(merged.items()):
  if ranges and address==ranges[-1][0]+len(ranges[-1][1]):ranges[-1][1].append(value)
  else:ranges.append((address,[value]))
 start_code=[0o010452020000,0o140500200000]
 ranges=[(0o27,start_code)]+ranges
 for n,(start,body) in enumerate(ranges):
  next_address=0o27 if n==len(ranges)-1 else 3
  length=(1-len(body))%MASK;header=(length<<18)|(start+len(body)-1)
  checksum=(-sum((word>>18)+(word&MASK) for word in [header,*body])-next_address)%MASK
  assert (sum((word>>18)+(word&MASK) for word in [header,*body])+checksum+next_address)%MASK==0
  paper_words.extend([header,*body,(checksum<<18)|next_address])
  paper_blocks.append({'start':f'{start:06o}','words':len(body),'checksum':f'{checksum:06o}','next':f'{next_address:06o}'})
 tape=bytes(tx2tape.FEED|line for word in paper_words for line in tx2tape.splay(word))
 (ROOT/'build/sketchpad.tape').write_bytes(tape)
 (ROOT/'results/sketchpad-paper.json').write_text(json.dumps({'leader_words':20,'lines':len(tape),'blocks':paper_blocks},indent=2)+'\n')
 # The constraint module extends the model and intentionally updates its
 # total length. Every other differing overlap is an integration failure.
 for conflict in conflicts:
  assert conflict['address']=='022000' and conflict['earlier']=='calculate' and conflict['later']=='constraints',conflict
 assert merged[0o22053]==0o006004000015 and merged[0o22054]==0o000046000062 and merged[0o22055]==0o775000000000, 'PDF part2 p23 printed model witnesses differ'
 (ROOT/'build/sketchpad-combined.hex').write_text(''.join(f'{a:05x} {w:09x}\n' for a,w in sorted(merged.items())))
 (ROOT/'results/sketchpad-image.json').write_text(json.dumps({'modules':reports,'words':len(merged),'conflicts':conflicts,'load':'Absolute image plus checksummed paper; paper boot executes the original reader leader','rc_relocation':'private compiler RC words relocated into existing U RAM; common NLIST=22000'},indent=2)+'\n')
 if args.modules==['main','calculate','constraints','math','display','io','build']:
  package=ROOT/'programs/sketchpad';package.mkdir(exist_ok=True)
  for src,dest in [('sketchpad-combined.hex','sketchpad.hex'),('sketchpad.tape','sketchpad.tape')]:
   shutil.copyfile(ROOT/'build'/src,package/dest)
  changes=[]
  for name in args.modules:
   changes.extend({'module':name,**change} for change in json.loads((ROOT/'work/sketchpad'/f'{name}-expanded.json').read_text())['changes'])
  inputs=['upstream/Sketchpad/sk.tx2as','upstream/Sketchpad/sk2.tx2as','tools/sketchpad-assembler.patch','tools/prepare_sketchpad.py']
  manifest={'tool_revision':'7480ac70bfece86c58b28a9f085ab4fe63880aae',
   'listing_revision':'3d134b23d207f169d0fb65ac5768177867689ed2',
   'description':'Sketchpad listing reconstruction; private RC in U RAM; model normalized to 22000 octal',
   'image':json.loads((ROOT/'results/sketchpad-image.json').read_text()),
   'paper':json.loads((ROOT/'results/sketchpad-paper.json').read_text()),'source_changes':changes,
   'files_sha256':{name:hashlib.sha256((package/name).read_bytes()).hexdigest() for name in ['sketchpad.hex','sketchpad.tape']},
   'inputs_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in inputs}}
  (package/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 print(f'{len(merged)} memory words; {len(conflicts)} conflicting overlaps; next U address {rc:o}')
 for c in conflicts[:12]:print(c)
if __name__=='__main__':main()
