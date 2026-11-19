#!/usr/bin/env python3
"""End-to-end instruction cases. Registers are initialized by real LD/SPG/SKX
instructions before each target; compare all registers, RAM, X, F, P and meta.
"""
import json,random
from pathlib import Path
from generate_rtl_vectors import exchange,add_index,quarters,join,signed18
from generate_alu_vectors import model as alu
M=(1<<36)-1;MX=(1<<18)-1
R=random.Random(0x1963)
ops=[0o04,0o05,0o06,0o07,0o10,0o11,0o12,0o14,0o15,0o16,0o17,0o20,0o21,0o22,0o24,0o25,0o26,0o27,0o30,0o31,0o32,0o34,0o35,0o36,0o37,0o40,0o41,0o42,0o43,0o45,0o46,0o47,0o54,0o55,0o56,0o57,0o60,0o61,0o62,0o64,0o65,0o66,0o67,0o70,0o71,0o72,0o74,0o75,0o76,0o77]
def ins(op,cf=0,j=0,addr=0,held=1):return (held<<35)|(cf<<30)|(op<<24)|(j<<18)|addr
cases=[]
for op in ops:
 for sample in range(8):
  cfg=[0,0o340,0o760,0o763,0o410,0o600,0o172,0o070][sample]
  regs=[R.getrandbits(36) for _ in range(5)];a,b,c,d,e=regs;m=R.getrandbits(36)
  f=[0,cfg,0o763,0o410,0o340]+[0]*27
  x=MX-3 if op==0o07 else 3
  initial_x=x;cf=1;j=0;addr=0o1006;p=0o110;meta=0;new_m=m;z=0
  if op in [0o10,0o11,0o12,0o14,0o15,0o16,0o06,0o07]:j=5
  if op in [0o05,0o06,0o07,0o45,0o46,0o47]:addr=0o110
  if op==0o04:cf=0;j=0o42;addr=0o30000
  if op==0o05:cf=0o14
  if op==0o12:cf=1
  if op==0o17:j=[1,0o21,0o41,0o61,10,11,12,0][sample];cf=[3,1,0o34,0o22,3,0o30,0o20,0o14][sample]
  instruction=ins(op,cf,j,addr)
  if op in [0o20,0o24,0o25,0o26,0o27]:
   ri=4 if op==0o20 else op-0o24;regs[ri]=exchange(m,regs[ri],cfg)[0]
   if ri!=4:regs[4]=m
  elif op in [0o30,0o34,0o35,0o36,0o37,0o16]:
   source=(signed18(x)&M) if op==0o16 else regs[4 if op==0o30 else op-0o34]
   new_m=exchange(source,m,cfg,True,False)[0]
   if op!=0o30:regs[4]=new_m
  elif op in [0o10,0o11]:
   val=exchange(m,x if op==0o11 else 0,cfg)[0]&MX
   x=add_index(x,val) if op==0o10 else val;regs[4]=m
  elif op in [0o14,0o15,0o54]:
   if op==0o54:regs[0]=exchange(m,a,cfg)[0];new_m=exchange(a,m,cfg,True,False)[0]
   elif op==0o14:
    val=exchange(m,x,cfg)[0]&MX;new_m=exchange(signed18(x)&M,m,cfg,True,False)[0];x=val
   else:
    val=exchange(m,0,cfg)[0];val=(val&~MX)|add_index(x,val&MX);new_m=exchange(val,m,cfg,True,False)[0]
   regs[4]=new_m
  elif op==0o12:x=(~addr)&MX
  elif op in [0o21,0o22]:
   for n in range(1 if op==0o21 else 4):f[(cf+n)&31]=quarters(m)[n]
   f[0]=0;regs[4]=m
  elif op in [0o31,0o32]:
   qs=quarters(m)
   for n in range(1 if op==0o31 else 4):qs[n]=f[(cf+n)&31]
   new_m=join(qs);regs[4]=new_m
  elif op==0o05:regs[4]=(0o1004<<18)|p
  elif op in [0o06,0o07]:regs[4]=(e&~MX)|p;x=add_index(x,cf,True)
  elif op in [0o45,0o46,0o47]:
   _,act=exchange(m,0,cfg);take=False
   from generate_rtl_vectors import GROUPS
   for g in GROUPS[cfg>>7]:
    val=(a>>(g[0]*9))&((1<<(9*len(g)))-1)
    if act&(1<<g[0]) and op!=0o45:
     sv=val if not val>>(9*len(g)-1) else -((~val)&((1<<(9*len(g)))-1))
     take|=sv>0 if op==0o46 else sv<0
   if take:regs[4]=(e&~MX)|p
  elif op in [0o40,0o41,0o42,0o43,0o56,0o55]:
   _,act=exchange(m,0,cfg);mask=sum(511<<(9*q) for q in range(4) if act&(1<<q));qmask=sum(511<<(9*q) for q in range(4) if not cfg&(1<<(q+3)))
   if op==0o40:regs[4]=e&(exchange(m,e,cfg,False,False)[0]|(M^qmask))
   elif op in [0o41,0o42]:
    val=exchange(m,0,cfg)[0];regs[0]=(a&~mask)|(((a&val) if op==0o41 else (a|val))&mask);regs[4]=m
   elif op==0o43:
    if exchange(m,e,cfg,False,False)[0]!=e:p+=1
   elif op==0o55:
    mask=exchange(b,0,cfg,True,False)[0];val=exchange(a,m,cfg,True,False)[0];new_m=(m&~mask)|(val&mask);regs[4]=new_m
   else:
    perm=exchange(m,0,cfg&~0o170,False,False)[0];new_m=exchange(m,perm,cfg)[0]^mask;regs[4]=new_m
  elif op==0o17:
   bit=j&15;quarter=((j>>4)-1)%4;selected=0
   if 1<=bit<=9:selected=(m>>(quarter*9+bit-1))&1
   elif bit==10:selected=0
   elif bit in [11,12]:selected=1^(m.bit_count()%2)
   skip=cf>>3
   if skip==1 or skip==2 and bit in range(1,13) and not selected or skip==3 and bit in range(1,13) and selected:p+=1
   if 1<=bit<=9:
    pos=quarter*9+bit-1
    if cf&3==1:new_m^=1<<pos
    elif cf&3==2:new_m&=~(1<<pos)
    elif cf&3==3:new_m|=1<<pos
   elif bit==10:meta=int(cf&3 in [1,3])
   if cf&4:new_m=(new_m>>1)|((new_m&1)<<35)
  elif op==0o57:new_m=((m<<1)|(m>>35))&M;regs[4]=new_m
  elif op>=0o60:
   val,act=exchange(m,a if op==0o74 else d,cfg)
   out=alu(op,cfg>>7,act,val if op==0o74 else a,b,c,d if op==0o74 else val,0)
   regs=[*out[:4],m];z=out[4]
  cases.append([instruction,cfg,*[a,b,c,d,e],m,initial_x,*regs,z,x,f[1],new_m,p,meta])
# AOP operations reuse D, preserve E, and perform no QK read.
for op in [0o60,0o61,0o62,0o64,0o65,0o66,0o67,0o70,0o71,0o72,0o74,0o75,0o76,0o77]:
 regs=[R.getrandbits(36) for _ in range(5)];a,b,c,d,e=regs
 direct=0o600 # four independent active quarters
 address=(1<<15)|(op<<9)|direct
 out=alu(op,direct>>7,15,a,b,c,d,0)
 cases.append([ins(0o04,0,0,address),0,*regs,0,3,*out[:4],e,out[4],3,0,0,0o110,0])
Path('build').mkdir(exist_ok=True)
Path('build/machine-vectors.hex').write_text(''.join(' '.join(f'{x:x}' for x in vs)+'\n' for vs in cases))
Path('build/machine-summary.json').write_text(json.dumps({'cases':len(cases),'opcodes':[f'{x:02o}' for x in ops],'initialization':'LD/SPG/SKX instructions','aop_cases':14},indent=2)+'\n')
print(f'{len(cases)} machine cases; {len(ops)} opcode numbers')
