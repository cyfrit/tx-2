#!/usr/bin/env python3
"""ALU vectors: fraction mathematics plus handbook cases; not a CPU emulator.
MUL C is checked against the documented carry-save pulses as a separate invariant.
27+9 low-quarter cases use the documented shared ASK pulse count.
"""
import json, random
from pathlib import Path
R=random.Random(0x545832)
MASK=(1<<36)-1
ops=[0o60,0o61,0o62,0o64,0o65,0o66,0o67,0o70,0o71,0o72,0o74,0o75,0o76,0o77]
def ring(a,b,w):
 m=(1<<w)-1;s=a+b
 return ((s&m)+(s>>w))&m
def groups(f): return [[(0,36)],[(0,18),(18,18)],[(0,9),(9,27)],[(0,9),(9,9),(18,9),(27,9)]][f]
def signed(x,w): return -((~x)&((1<<w)-1)) if x>>(w-1) else x
def encode(x,w,negative=False): return (~abs(x))&((1<<w)-1) if x<0 or negative else x
def micro_mul(a,d,w,n):
 m=(1<<w)-1;neg=(a^d)>>(w-1);b=abs(signed(a,w));d=abs(signed(d,w));a=c=0
 for _ in range(n):
  if b&1:c|=a&d;a^=d
  a,c,b=(a>>1)^c,(a>>1)&c,(b>>1)|((a&1)<<(w-1))
 if b&1:c|=a&d;a^=d
 a=ring(a,(c<<1)&m,w)
 if neg:a^=m;b^=m
 return a,b,c
def micro_div(a,b,d,w,n):
 m=(1<<w)-1;sg=1<<(w-1);na=bool(a&sg);nd=bool(d&sg)
 if not na:a^=m;b^=m
 if nd:d^=m
 a=(a+d)&m
 for i in range(n):
  if bool(a&sg)==bool(d&sg):d^=m
  bn=((b<<1)|bool(a&sg))&m
  if i<n-1:a=((a<<1)|(b>>(w-1)))&m
  if i<n-1 or not a&sg:a=(a+d+bool(d&sg))&m
  b=bn
 z=bool(b&sg);a,b=b,a
 if na!=nd:a^=m
 if not na:b^=m
 return a,b,int(z)
def model(op,f,activity,A,B,C,D,Z):
 out=[A,B,C,D,Z]
 for lo,w in groups(f):
  q=(lo+w)//9-1;m=(1<<w)-1;wm=m<<lo
  if not activity & (((1<<(w//9))-1)<<(lo//9)):continue
  a,b,c,d=[(x>>lo)&m for x in [A,B,C,D]];z=(Z>>q)&1
  shared=27 if f==2 and activity&14 else w
  count=signed((d>>(w-9))&511,9)
  if op in [0o67,0o77]:
   rhs=d if op==0o67 else d^m;c=a&rhs
   v=ring(a,rhs,w);z=int((a>>(w-1))==(rhs>>(w-1)) and (v>>(w-1))!=(a>>(w-1)));a=v
  elif op==0o65:c|=a&d;a^=d
  elif op==0o76:
   aa,bb,c=micro_mul(a,d,w,shared-1)
   if shared==w:
    product=2*abs(signed(a,w))*abs(signed(d,w));product^=((1<<(2*w))-1) if (a^d)>>(w-1) else 0
    assert (aa<<w)|bb==product
   a,b,z=aa,bb,0
  elif op==0o75:
   aa,bb,z=micro_div(a,b,d,w,shared)
   da=abs(signed(d,w));mag=(((a<<w)|b)^((1<<(2*w))-1) if a>>(w-1) else (a<<w)|b)>>1
   if da and shared==w and mag//da < 1<<(w-1):
    quotient,remainder=divmod(mag,da)
    assert aa==encode(quotient,w,bool((a^d)>>(w-1))) and bb==encode(remainder,w,bool(a>>(w-1))) and not z
   a,b,c=aa,bb,0
  elif op==0o74:
   for _ in range(shared):
    if a>>(w-1):d=(d&((1<<(w-9))-1))|(ring(d>>(w-9),1,9)<<(w-9))
    a=((a<<1)|(a>>(w-1)))&m
  else:
   double=op in [0o62,0o66,0o72];useb=op in [0o61,0o71];cyc=op in [0o60,0o61,0o62]
   bits=w*2 if double else w;mm=(1<<bits)-1
   v=(a<<w)|b if double else b if useb else a
   normal=op in [0o64,0o66]
   if normal:
    if z:
     v=(v>>1)|(v&(1<<(bits-1)));v^=1<<(bits-1);n=-1
    else:
     n=0;bound=(2*shared-1) if double else shared-1
     while n<bound and (v>>(bits-1))==((v>>(bits-2))&1):
      oldsign=v&(1<<(bits-1));v=((v<<1)|(v>>(bits-1)))&mm;v=(v&~(1<<(bits-1)))|oldsign;n+=1
    d=(d&((1<<(w-9))-1))|(ring(d>>(w-9),encode(-n,9),9)<<(w-9));z=0
   else:
    if not cyc and not useb and z:
     if count<0:
      v=(v>>1)|(v&(1<<(bits-1)));v^=1<<(bits-1);count+=1
     else:v^=1<<(bits-1)
     z=0
    for _ in range(abs(count)):
     sign=v&(1<<(bits-1))
     if cyc:v=((v<<1)|(v>>(bits-1)))&mm if count>0 else (v>>1)|((v&1)<<(bits-1))
     elif count>0:v=((v<<1)|(sign>>(bits-1)))&mm;v=(v&~(1<<(bits-1)))|sign
     else:v=(v>>1)|sign
    d=(d&((1<<(w-9))-1))|(511<<(w-9))
   if double:a,b=v>>w,v&m
   elif useb:b=v
   else:a=v
  for idx,v in enumerate([a,b,c,d]):out[idx]=(out[idx]&~wm)|((v&m)<<lo)
  out[4]=(out[4]&~(1<<q))|(z<<q)
 return out
vectors=[]
def add(op,f,act,a,b,c,d,z):vectors.append([op,f,act,a,b,c,d,z,*model(op,f,act,a,b,c,d,z)])
def generate():
    for op in ops:
     for f in range(4):
      for _ in range(140):
       activity=0
       for lo,w in groups(f):
        if R.randrange(4):activity|=((1<<(w//9))-1)<<(lo//9)
       a,b,c,d=[R.getrandbits(36) for _ in range(4)];z=R.randrange(16)
       if op in [0o60,0o61,0o62,0o70,0o71,0o72]:
        for lo,w in groups(f):
         qlo=lo+w-9;d=(d&~(511<<qlo))|(encode(R.randint(-255,255),9)<<qlo)
       add(op,f,activity,a,b,c,d,z)
    # Explicit handbook arithmetic and signed-zero boundaries.
    for aa,dd in [(0o277,0o307),(0o510,0o470),(0,0),(511,0),(0,511),(511,511)]:
     for op in [0o67,0o77,0o76]:add(op,3,1,aa,0,0,dd,0)
    add(0o75,3,1,0,0o52,0,5,0)
    add(0o75,3,1,511,0o725,0,0o772,0)
    for f in range(4):
     for op in ops:
      for val in [0,MASK]:add(op,f,15,val,val,val,val,15)
    Path('build').mkdir(exist_ok=True)
    with Path('build/alu-vectors.hex').open('w') as out:
     for vs in vectors:out.write(' '.join(f'{x:x}' for x in vs)+'\n')
    Path('build/alu-summary.json').write_text(json.dumps({'vectors':len(vectors),'opcodes':[f'{op:02o}' for op in ops],'seed':'545832','reference':'fraction mathematics checked against micro-pulse invariants'},indent=2)+'\n')
    print(f'{len(vectors)} ALU vectors')

if __name__ == '__main__':
    generate()
