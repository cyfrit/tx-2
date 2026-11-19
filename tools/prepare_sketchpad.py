#!/usr/bin/env python3
"""Expand M4 macros in isolated historical Sketchpad modules.
The unmodified upstream transcription remains the source; changes and each
expanded line's provenance are emitted alongside the assembly input.
"""
import argparse,dataclasses,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
# Users' Handbook 6-2.3 (October 1961), rule 3: these single letters
# are predefined by M4, not implicitly allocated RC storage.
AE_PREASSIGNMENTS = [f'{name}={address:o}' for name,address in zip('ABCDE',range(0o377604,0o377611))]
# OPR with address bits 2.8/2.7 = 0/1 selects the AE command variant.
# Technical Manual vol.3 16-5; e.g. AOP 66000 is OPR 166000.
AE_PREASSIGNMENTS += ['AOP=000400100000']
def m4_tool_syntax(text):
 text=re.sub(r'\bAOP\s+(?=\S)', 'AOP+', text)
 # The reference parser loses the sign of literal zero. M4's -0 is
 # all ones; comma assembly masks this value to the relevant syllable.
 return re.sub(r'(?<![\w#)])-0(?![0-9.])', '777777777777', text)
GLYPHS={'arr':'→','times':'×','hamb':'≡','sup':'⊃','and':'∧','or':'∨','xor':'⊻','square':'□','rect_dash':'▭',
 'alpha':'α','beta':'β','gamma':'γ','delta':'δ','eps':'ε','lambda':'λ','pi':'π','theta':'θ',
 'minus':'-','plus':'+','dot':'.','pipe':'|','hash':'#','hand':'☛','leftbrace':'{','rightbrace':'}',
 'leftparen':'(','rightparen':')','asterisk':'*','solidus':'/','equals':'=','comma':','}
class Encoding:
 def __init__(self):self.codes={};self.dec={};self.names={}
 def encode(self,text):
  def glyph(m):
   name=m[1];script='n'
   for prefix,s in [('sub_','s'),('sup_','u')]:
    if name.startswith(prefix):script=s;name=name[len(prefix):];break
   value=GLYPHS.get(name,name if len(name)==1 else None)
   if value is None:raise ValueError('unknown glyph '+m[0])
   self.names[value]=name
   if script=='n':return value
   return self.script(value,script)
  return re.sub(r'@([^@]+)@',glyph,text)
 def script(self,text,script):
  if script=='n':return text
  out=''
  for ch in text:
   if ch.isspace():continue
   if ch in self.dec:out+=ch;continue
   key=(script,ch)
   if key not in self.codes:
    code=chr(0xe000+len(self.codes));self.codes[key]=code;self.dec[code]=key
   out+=self.codes[key]
  return out
 def render(self,text):
  out=''
  for ch in text:
   if ch in self.dec:
    script,base=self.dec[ch];name=self.names.get(base,base)
    if name in ['-','+','|','.','#','*','/','=',',']:
     name={'-':'minus','+':'add','|':'pipe','.':'dot','#':'hash','*':'asterisk','/':'solidus','=':'equals',',':'comma'}[name]
    out+='@'+('sub_' if script=='s' else 'sup_')+name+'@'
   else:out+=('@'+self.names[ch]+'@') if ch in self.names and not ch.isascii() else ch
  return out
 def underlying(self,ch):return self.dec.get(ch,('n',ch))
 def identifiers(self,text):
  i=0
  while i<len(text):
   script,base=self.underlying(text[i])
   if not (base.isalnum() or base=='_'):i+=1;continue
   start=i;name=''
   while i<len(text):
    s,c=self.underlying(text[i])
    if s!=script or not(c.isalnum() or c=='_'):break
    name+=c;i+=1
   yield start,i,script,name
E=Encoding()
TERMS=set('☛,=→|⊃≡~<>∩∪/×∨∧▭')
@dataclasses.dataclass
class Macro:
 name:str
 params:list
 body:list
 preparam:str|None=None
class Expander:
 def __init__(self):self.macros={};self.serial=0;self.rc=[];self.rc_cache={};self.stats={};self.records=[]
 def collect(self,lines):
  plain=[];i=0
  while i<len(lines):
   text,where=lines[i];i+=1
   m=re.match(r'\s*☛☛DEF(?:INE)?\s+(.+)',text)
   if not m:plain.append((text,where));continue
   header=m[1].strip();first=next((j for j,c in enumerate(header) if c in TERMS),len(header))
   name=header[:first].strip();params=[];tail=header[first:];pre=None
   comp=re.match(r'(.+?)(□|▭)(.*)',header)
   if comp:
    pre,name,tail=comp.groups();pre=pre.strip()
    if name=='▭':tail='▭'+tail

   while tail:
    term=tail[0];end=next((j for j,c in enumerate(tail[1:],1) if c in TERMS),len(tail))
    param=tail[1:end].strip()
    if param:params.append((term,param))
    tail=tail[end:]
   body=[]
   while i<len(lines) and not re.match(r'\s*☛☛EMD',lines[i][0]):body.append(lines[i]);i+=1
   if i==len(lines):raise ValueError('unterminated macro '+name)
   i+=1
   self.macros[name]=Macro(name,params,body,pre)
  return plain
 def strip_outer(self,value):
  while value.startswith('(') and value.endswith(')'):
   depth=0
   for i,ch in enumerate(value):
    if ch=='(':depth+=1
    if ch==')':depth-=1
    if depth==0:break
   if i!=len(value)-1:break
   value=value[1:-1].strip()
  return value
 def call(self,line):
  line=line.strip()
  for name in sorted(self.macros,key=len,reverse=True):
   if self.macros[name].preparam:
    m=re.match(r'([^\s≡×,→|]+)\s*'+re.escape(name)+r'(.*)',line)
    if m:return self.macros[name],(name if name=='▭' else '')+m[2],{self.macros[name].preparam:m[1]}
   elif line.startswith(name) and (len(line)==len(name) or line[len(name)] in TERMS or line[len(name)].isspace()):
    return self.macros[name],line[len(name):].strip(),{}
  return None
 def arguments(self,macro,tail,bindings):
  parts=[];depth=0;start=0;term=None
  for i,ch in enumerate(tail):
   if ch in '({':depth+=1
   elif ch in ')}':depth-=1
   elif depth==0 and ch in TERMS:
    if term is not None:parts.append((term,tail[start:i].strip()))
    elif tail[:i].strip():raise ValueError(f'{macro.name}: unseparated argument {tail}')
    term=ch;start=i+1
  if term is not None:parts.append((term,tail[start:].strip()))
  elif tail.strip():raise ValueError(f'{macro.name}: bad arguments {tail}')
  cursor=0
  for preceding,name in macro.params:
   if cursor<len(parts) and parts[cursor][0]==preceding:
    bindings[name]=parts[cursor][1] or None;cursor+=1
   else:bindings[name]=None
  if cursor!=len(parts):raise ValueError(f'{macro.name}: unmatched arguments {parts[cursor:]} expected {macro.params}')
  return bindings
 def replace(self,text,bindings,locals_,is_equality=False,aliases=None):
  out='';pos=0;elide=False
  for a,b,script,name in E.identifiers(text):
   out+=text[pos:a];pos=b
   if name in bindings:
    value=bindings[name]
    if value is None:
     # M4 parenthesized dummy references preserve the line and insert zero.
     parenthesized=text[:a].rstrip().endswith('(') and text[b:].lstrip().startswith(')')
     if not is_equality and not parenthesized:elide=True
     value='0'
    if script=='n' and aliases and name in aliases and not text[b:].lstrip().startswith(('→','=')):value=aliases[name]
    out+=E.script(value,script)
   elif name in locals_:out+=E.script(locals_[name],script)
   else:out+=text[a:b]
  out+=text[pos:]
  return None if elide else out
 def expand(self,line,where,depth=0):
  if depth>50:raise ValueError('macro recursion '+line)
  line=line.strip()
  if not line:return []
  # Peel labels so a macro's first emitted word retains the caller's tag.
  labels=''
  while '→' in line:
   if self.call(line):break
   before,after=line.split('→',1)
   if any(c in before for c in TERMS-{'→'}):break
   labels+=before.strip()+'→';line=after.strip()
  stripped=self.strip_outer(line);call=self.call(stripped)
  if call:
   macro,tail,bindings=call;bindings=self.arguments(macro,tail,bindings)
   self.serial+=1;prefix=f'MAC{self.serial}';locals_={}
   for body,_ in macro.body:
    tag=re.match(r'\s*([^≡×=,{}()|→]+)→',body)
    eq=re.match(r'\s*([^≡×=,{}()|→]+)=',body)
    for m in [tag,eq]:
     if m and m[1].strip() not in bindings:locals_[m[1].strip()]=prefix+m[1].strip().replace(' ','')
   aliases={};expanded=[]
   for name,value in bindings.items():
    if value is not None and not self.call(self.strip_outer(value)):
     alias=prefix+'ARG'+name.replace(' ','');aliases[name]=alias
     expanded+=self.expand(alias+'='+value,where,depth+1)
   self.stats[macro.name]=self.stats.get(macro.name,0)+1
   for body,source in macro.body:
    replaced=self.replace(body,bindings,locals_,bool(re.match(r'[^=→]+=',body)),aliases)
    if replaced is not None:expanded+=self.expand(replaced,source+' via '+where,depth+1)
   if labels:
    # Equalties are non-emitting; put the tag on the first real instruction.
    for i,(body,source) in enumerate(expanded):
     if '=' not in body and not body.startswith('☛'):
      expanded[i]=(labels+body,source);break
    else:expanded.append((labels,where))
   return expanded
  # Expand RC-word macro bodies out of line with private, relocated labels.
  # Lower the documented subscript pipe shorthand to a shared pointer
  # word. A source # in the base expression denotes this instruction.
  pipe=E.script('|','s')
  if pipe in line:
   at=line.index(pipe);end=at+1
   while end<len(line) and E.underlying(line[end])[0]=='s':end+=1
   right_index=line[at+1:end];operand=line[end:].strip() or '0'
   if '#' in operand:
    self.serial+=1;site=f'PIPESITE{self.serial}';labels+=site+'→';operand=operand.replace('#',site)
   line=line[:at]+' *{'+operand+right_index+'}'
  i=0
  while i<len(line):
   if line[i]!='{':i+=1;continue
   nesting=1;j=i+1
   while j<len(line) and nesting:
    if line[j]=='{':nesting+=1
    if line[j]=='}':nesting-=1
    j+=1
   if nesting:raise ValueError('unclosed RC '+line)
   body=line[i+1:j-1].strip()
   rawkey=('source',body)
   if rawkey in self.rc_cache:label=self.rc_cache[rawkey]
   else:
    expanded=self.expand(body,where,depth+1)
    key=tuple(text for text,_ in expanded)
    if key in self.rc_cache:label=self.rc_cache[key]
    else:
     self.serial+=1;label=f'RCMAC{self.serial}';self.rc_cache[key]=label
     self.rc.append((label+'→',where));self.rc.extend(expanded)
    self.rc_cache[rawkey]=label
   # "LDA{1,,K}" / "hJPQ{TURNOFFΔ}": the listing may abut an RC word on the mnemonic.
   if i and line[i-1].isascii() and line[i-1].isalpha():label=' '+label
   line=line[:i]+label+line[j:];i+=len(label)
  return [(labels+line,where)]

def load(first,last,part=1):
 path=ROOT/'upstream/Sketchpad'/('sk.tx2as' if part==1 else 'sk2.tx2as')
 page=0;out=[]
 for n,line in enumerate(path.read_text().splitlines(),1):
  meta=re.match(r'\[meta .*pdf_page=(\d+)',line)
  if meta:page=int(meta[1])
  if first<=page<=last:
   if line.lstrip().startswith('['):continue
   line=re.sub(r'\[[^\]]*\]','',line).split('**',1)[0].rstrip()
   if line.strip():out.append((E.encode(line),f'part{part}:{n}:pdf{page}'))
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--module',default='main');p.add_argument('--rc-origin',type=lambda x:int(x,8),default=0o210000);args=p.parse_args()
 # Program boundaries come from independent equalities/macros/main sections.
 # The constraint program (IES BOO7) ends part 1 with "ORIGIN|"; its code at ORIGIN
 # (PRLCOMP, ONLINECOMP, PNNU1, ...) is on part 2 PDF 2-7, after the pages that
 # repeat part 1 (the transcription omits that repeated code).
 sections={'main':[(1,11,58)],'calculate':[(2,11,51)],'constraints':[(1,138,152),(2,2,7)],'io':[(1,84,135)],
           'display':[(2,81,112)],'math':[(2,54,78)],'build':[(2,116,155)]}
 lines=[x for part,first,last in sections[args.module] for x in load(first,last,part)]
 changes=[]
 # Transcription errors checked glyph by glyph against the CHM scan (crops in
 # references/figures/sketchpad-scan-fixes/). Key: (part, transcription line).
 scan_fixes={(1,1371):('RSZ','RSX'),(1,2111):('SPX','DPX'),(1,2476):('LDS','LDA'),(1,911):('74BUT','76BUT'),
             (1,2205):('VORDE','VORD'),(1,6263):('JNK','JNX'),(1,4330):('JQP','JPQ'),
             (2,6895):('2DPX',E.encode('@sup_2@DPX')),(2,2394):('SPX','DPX'),(2,2414):('MAB','NAB'),
             (2,3357):('VORDE','VORD'),(2,1315):('RES','REX'),(2,1900):('RES','REX'),
             # TRUEUP (PDF34): the handwritten "← MKN MOVED" points at this JPQ, so the
             # new HORV constraint triggers relaxation (76PUNCH tests MOVED).
             (1,1417):('JPQ TRUEUPX','MKN MOVED'),
             # WORKER (PDF75/76): the labels read WRK1A / WRK4, as every reference does.
             (2,3263):('WKR1A','WRK1A'),(2,3280):('WKR4','WRK4'),
             # RI (PDF78): the final glyph is the listing's 0, as in "200000" below; reader-in 377750.
             (2,3390):('377758','377750'),
             # SOLVEM (PDF67/68): "LDA x1|x3"; SLVAD's matrix location is SLVT5-1 like every
             # other "**MATRIX LOCATION"; the DIV overflow goes to SLVAD8 "OVERFLOW IN MAKING TERMS".
             (2,2908):(E.encode('@sub_x@@sub_1@@sub_S@@sub_pipe@@sub_beta@@sub_x@@sub_3@'),E.encode('@sub_x@@sub_1@@sub_pipe@@sub_x@@sub_3@')),
             (2,2888):('SLVTS-1','SLVT5-1'),(2,2911):('SLVAD9','SLVAD8'),
             # io PDF99: XSETKβ as in its label and line 4405; PDF132: 45RWSW (all four letters).
             (1,4414):('XSETX','XSETK'),(1,6153):('45RSW','45RWSW'),
             # build PDF144: fifth digit of the -.7689 constant is the page's 3, not 5.
             (2,6371):('26415202030','26413202030'),
             # constraint program part 2 PDF7: eighth digit is a two-lobed 8.
             (2,291):('343597302','343597382'),
             # MAGIGOA (PDF47) saves MAG1X: the glyph is the listing's slanted 1, as in the
             # MAG1 target of the GORR on PDF48, not the upright I of MAGIX on the line above.
             (2,2007):('MAGIX','MAG1X'),
             # MAGPIC (PDF41): "STA MATM **DIAGONAL MATRIX"; MATH is not a symbol of the block.
             (2,1662):('MATH','MATM'),
             # PDF41 handwritten arrow moves "DPX NDISP" up to MAG's entry (inserted below).
             (2,1660):('DPX NDISP',''),
             # io PDF113 NUMMON: the mnemonic JPX was dropped; JPA carries superscript 1.
             # PDF110 TYPESTART: IOS 66 operand 50000.
             (1,5111):(E.encode('@sup_minus@@sup_1@ @sub_C@'),E.encode('@sup_minus@@sup_1@JPX @sub_C@')),
             (1,5108):('JPA',E.encode('@sup_1@JPA')),(1,4935):('30000','50000'),
             # TEXTCNG (PDF110): REX β MOVINGS-LIST, the generic ring of moving things.
             (1,4964):('MOVING-LIST','MOVINGS-LIST'),
             # build PDF148 MKN PLPUBUSY; io PDF124 RXF 54 45IT1; io PDF104 TAPEK3 (twice).
             (2,6596):('PLPBUSY','PLPUBUSY'),(1,5721):('45SIT1','45IT1'),
             (1,4659):('TAPER3','TAPEK3'),(1,4660):('TAPER3','TAPEK3')}
 # Glyphs the transcription marked unreadable or misread, read on enlarged scans
 # (PDF23-25, PDF39 STOPMOVEP2J label, PDF51 GARB3; part 2 PDF103 PS2P).
 scan_read={(1,829),(1,831),(1,885),(1,887),(1,888),(1,891),(1,919),(1,2351),(1,1673),(2,4436)}
 # Full-listing pass (part 1 PDF 11-58, 84-152; part 2 PDF 2-155): one reviewer per eight
 # pages compared every transcribed line with the scan glyphs. (part, line): (old, new) in
 # transcription markup; '(inferred)' marks the one reading the scan cannot settle.
 scan_fixes.update({(p,l):(E.encode(o),E.encode(n)) for (p,l),(o,n) in {
  # Main equalities PDF14 say 126; io origin 200120, PDF109, puts RDTX2 at
  # 200126 (the T-memory offset differs by 200000). PDF23's BUILD header
  # explicitly annotates "RDTX2=200126" in handwriting (transcription:790).
  # Original automatic link mechanism unknown; apply the recorded relocation.
  (1,383):('RDTX2= 126','RDTX2= 200126'),
  # TX2RD2 (PDF134): checksum-high arrived through ⁶TSD (q4), then ²ADD
  # consumes B's left half. Its checksum-low must arrive through ⁵TSD (q3),
  # as the writer's paired checksum halves require (PDF107, SK:4834–4836).
  # Scan glyph is ambiguous/3-like; retain this arithmetic reconstruction as inferred.
  (1,6264):('@sup_3@TSD','@sup_5@TSD'),
  (1,1496):('JPX','JPQ'),  # PDF35
  (1,1596):('MERGEIPFX','MERGEIFPX'),  # PDF37
  (1,1927):('DUMEX','DUMMEX'),  # PDF43
  (1,2702):('JNA','JNX'),  # PDF58
  (1,3959):('STA A+D','STD A+D'),  # PDF91 STAE
  (1,4722):('SRCENTRY','SCRENTRY'),  # PDF105 label
  (1,4793):('}+8','}+8.'),  # PDF106 decimal 8
  (1,4884):('{TPK@beta@},ERRS','{TPK@beta@}+3,ERRS'),  # PDF108
  (1,5417):('3,,','3,'),  # PDF119
  (1,5518):('SIZE/2..SIZE/2','SIZE/2,,SIZE/2'),  # PDF121
  (1,5520):('1..-200000','1,,-200000'),  # PDF121
  (1,5818):('@sub_R@@sub_X@@sub_2@','@sub_X@@sub_2@'),  # PDF126 45X2
  (2,902):('42,41,,,20,45','42,41,,20,45'),  # PDF22 assembled 042041 020045
  (2,1014):('SMASBL,4,MM2','SMASBL,4,,MM2'),  # PDF24 H10
  (2,1041):('(24,35,,,30,33)','(24,35,,30,33)'),  # PDF25 L2 name
  (2,2521):('@sup_?@','@sup_2@'),  # PDF60 clipped superscript, best reading 2 (inferred)
  (2,3743):('STA A+D','STD A+D'),  # PDF89 STAE
  (2,4394):('TYPE,@sub_P@@sub_S@@sub_gamma@','TYPE,PS@gamma@'),  # PDF102 baseline macro arg
  (2,5073):('@sup_8@SCB','@sup_2@SCB'),  # PDF118 superscript 2
  (2,5216):('STA A+D','STD A+D'),  # PDF121 STAE
  (2,5780):('JPX CMGNL4AX','JPQ CMGNL4AX'),  # PDF133
  (2,6011):('{-0,400,,-0,,400}','{-0,400,,-0,400}'),  # PDF137
  (2,6243):('LMSLRT@arr@','LMSLRX@arr@'),  # PDF142 label
  # COPYFIXC (part 1 PDF47): δ already holds new block + tie offset (AUX δ COPYFIXI), so the
  # chicken is at offset 0; with α (=1) MOVEL relinks the next block's TYPE word. The scan's
  # first argument is a filled round glyph that the listing uses for both 0 and α (inferred).
  (1,2147):('MOVEL@hamb@@alpha@@times@@delta@','MOVEL@hamb@0@times@@delta@'),
  # MKCN1 (PDF31) and COPYIT (PDF46): "MUL {100.,}" — decimal 100 in the left half.
  (1,1252):('{ 100.}','{ 100.,}'),(1,2060):('{ 100.}','{ 100.,}'),
  # LLCROSS (part 2 PDF90): ¹DPX Q A — a slanted 1, unlike the ² of CCCROSS above it.
  (2,3793):('@sup_2@DPX','@sup_1@DPX'),
 }.items()})
 scan_inferred={(2,2521),(1,2147),(1,383),(1,6264)}
 for i,(line,where) in enumerate(lines):
  old=line
  key=tuple(map(int,re.match(r'part(\d+):(\d+):',where).groups()))
  if key in scan_fixes:line=line.replace(*scan_fixes[key],1)
  # MSCOMP (part 2 PDF3): an ink blot covers the subscript of the second PYTH; SETIX β,γ
  # and the β/γ VARLOC pair just above make it LISTγ ('?' in the old text marks it inferred).
  if key==(2,89):line=line.replace('LIST??',E.encode('LIST@sub_gamma@'))
  line=m4_tool_syntax(line)
  line=re.sub(r'^NLIST\s*=.*','NLIST=22000',line)
  line=line.replace('⋁','∨').replace('ħ','ℏ')
  if args.module=='io' and line=='?=#':line='δ=4'
  if args.module=='calculate':
   line=line.replace('HEADERS≡','HEADER≡')
   if ':940:' in where:line=line.replace('HEADER→','HEADER≡')
  if args.module=='main':
   # The two marked missing glyphs on PDF23 read as bit 1.8; retain review evidence.
   line=line.replace(E.script('?', 's'),E.script('α' if any(f':{n}:' in where for n in [885,887,888]) else '8','s'))
   if 'RSN' in line and '76TABLE' in line:line=line.replace('RSN','RSX')
   line=line.replace('STOMOVEP2J','STOPMOVEP2J')
   # DESIGNATE (PDF35, printed 33): after SNN DESIGNATED, the jump must pass over
   # "SKN 1.1 DESTS / hJPQ DELETE" when no earlier circle centre exists; with #+1
   # DELETE runs on an empty CCENT and never returns. The scan glyph is unclear.
   if ':1473:' in where:line=line.replace('JPQ #+1','JPQ #+3')
   # PUTR (PDF18, printed 16): the hJPX glyph is the same "2" as PUTLQ/PUTRQ on that page
   # (references/figures/sketchpad-putr-p18.png); every other PUTR copy reads #+2.
   # With #+3 the chicken's hen-block reference (word N) is never written.
   if ':586:' in where:line=re.sub(r'#\+3.*','#+2',line)
  line=line.replace('(h)','(400000000000)').replace('GARB?','GARB3')
  line=re.sub(r'\{\s*h\s*\}','{400000000000}',line)
  if args.module=='display':
   line=line.replace('Ps2P','PS2P').replace('LLCROSS≡','LLCROSSP≡')
   # PDF100/101 (printed250/251): decimal 18, not 10. This is
   # the inverse of SCNORM's conversion from a 36-bit fraction to 18 bits.
   line=line.replace('SAB { 10.,}', 'SAB { 18.,}')
   if ':3952:' in where:line=line.replace('SKX','SKN')
   if ':3881:' in where:line=line.replace('hLDQ','hLDE')
   # SQ60SEE uses the scope's S1α index (34), as defined on printed235.
   # PDF93/printed243 has a digit 1, not a subscript pipe shorthand.
   if any(f':{n}:' in where for n in [3879,3881,3882,3883]):
    line=line.replace(E.encode('@sub_S@@sub_pipe@@sub_alpha@'),E.encode('@sub_S@@sub_1@@sub_alpha@'))
  if args.module=='io':
   line=line.replace('45RW?','45RWUNREAD')
   line=re.sub(r'(?<![\w])\?(?![\w])','#',line)
  if args.module=='build':
   if ':6095:' in where:line=line.replace('INC C','INS C')
   line=line.replace('SCNORM|LMEND1','SCNORM|LMEND+1')
   if line.lstrip().startswith('SCNORM|'):
    line=line.replace('LMSST-LMAG5A','LMSST→LMAG5A').replace('LMSEND-LMAG5B','LMSEND→LMAG5B')

  for at in range(len(line)-1,0,-1):
   if line[at]=='|' and at+1<len(line) and E.underlying(line[at-1])[0]=='s' and E.underlying(line[at+1])[0]=='s':
    line=line[:at]+E.script('|','s')+line[at+1:]
  # A blank left index of the subscript pipe construct denotes X0.
  pipe=E.script('|','s')
  for match in list(re.finditer(re.escape(pipe),line))[::-1]:
   at=match.start()
   if at==0 or E.underlying(line[at-1])[0]!='s':line=line[:at]+E.script('0','s')+line[at:]

  if line!=old:
   verified=(key in scan_fixes and key not in scan_inferred) or key in scan_read or (args.module=='display' and any(f':{n}:' in where for n in [3879,3881,3882,3883,3952,4291,4300])) or (args.module=='calculate' and ':940:' in where) or (args.module=='main' and ('RSN' in old and '76TABLE' in old or ':586:' in where)) or (args.module=='build' and any(s in old for s in ['INC C','SCNORM|LMEND1','LMSST-LMAG5A','LMSEND-LMAG5B']))
   # io: the listing itself prints "?=#" (PDF90), so replacing a lone ? operand with # is an alias.
   alias=args.module=='io' and old!='?=#' and '?' in E.render(old)
   kind='verified' if verified else 'mechanical' if alias else 'inferred' if key in scan_inferred or any(s in E.render(old) for s in ['?','Ps2P','LLCROSS≡','STOMOVEP2J']) or (args.module=='main' and ':1473:' in where) else 'mechanical'
   changes.append({'source':where,'old':E.render(old),'new':E.render(line),'class':kind})
  lines[i]=(line,where)
 # Each omitted instruction records its listing part, insertion line, text, and evidence.
 omitted={(2,3897):('hLDE @sub_L@@sub_P@@sub_alpha@ 0','PDF93/printed243'),
          # PDF page 149 shows PLTABLE-1 but clips the opcode and index. The parallel punch
          # initialization at part 2 line 6620 and the indexed reads in PLPL2 support this inference.
          (2,6667):('SKX @sub_P@@sub_L@@sub_P@ PLTABLE-1','PDF149 clipped bottom; inferred from part2:6620 and 6675–6680'),
          (1,6725):('hJMP HOVSCOMP','PDF152/printed150, assembled |400500 021103| at 771'),
         (2,1652):('DPX NDISP','PDF41 handwritten arrow from MAGPIC to the line after MAG entry'),
         (2,4053):(['hJPQ TRREX','@sup_2@@sup_0@INX @sub_6@@sub_0@ 1'],'PDF96: TRLP prints three hJPQ TRREX / INX pairs')}
 fixed=[]
 for line,where in lines:
  fixed.append((line,where))
  key=tuple(map(int,re.match(r'part(\d+):(\d+):',where).groups()))
  if key in omitted:
   for text in ([omitted[key][0]] if isinstance(omitted[key][0],str) else omitted[key][0]):
    missing=E.encode(text)
    fixed.append((missing,where+':scan-omitted-next-line'))
    changes.append({'source':where+' '+omitted[key][1],'old':'Transcription omits the next instruction',
     'new':E.render(missing),'class':'inferred' if key==(2,6667) else 'verified'})
 lines=fixed
 x=Expander();plain=x.collect(lines);expanded=[]
 for line,where in plain:expanded+=x.expand(line,where)
 if x.rc:expanded += [('RCSPACE|','generated RC area'),*x.rc]
 # RC helper code gets a separate address block, avoiding module code/data.
 expanded=[(line.replace('RCSPACE|',f"{args.rc_origin:o}|"),where) for line,where in expanded]
 rendered=[]
 for line,where in expanded:
  # M4 accepts address expressions as origins; the reference parser requires
  # a literal or symbol. Introduce a non-emitting equality for the same value.
  if re.fullmatch(r'[^|→{}]+[+\-×/][^|→{}]*\|',line):
   name=f'ORGEXPR{len(rendered)}';rendered.append(name+'='+E.render(line[:-1])+' ** '+where);line=name+'|'
  # Avoid the reference assembler's sign-extension of negative CF literals.
  minus=E.script('-','u');digits=''.join(E.script(str(n),'u') for n in range(8))
  def config_negative(match):
   value=int(''.join(E.underlying(ch)[1] for ch in match[0][1:]),8)
   return E.script(f'{(~value)&31:o}','u')
  line=re.sub(re.escape(minus)+'['+digits+']+',config_negative,line)
  rendered.append(E.render(line)+' ** '+where)
 # Word assembly inside parentheses is legal M4; give that word an
 # equality so the reference parser sees an ordinary arithmetic atom.
 constants=[]
 for i,line in enumerate(rendered):
  while True:
   matches=list(re.finditer(r'\(([^()]*)\)',line.split(' ** ',1)[0]))
   match=next((m for m in matches if ',' in m[1] or '@sub_' in m[1] or '@sup_' in m[1]),None)
   if match is None:break
   name=f'WORDCONST{len(constants)}';constants.append(name+'='+match[1])
   line=line[:match.start()]+'('+name+')'+line[match.end():]
  rendered[i]=line
 rendered=AE_PREASSIGNMENTS+constants+rendered
 changes.append({'source':'Users Handbook 6-2.3 rule 3, PDF pages 159-160; Technical Manual vol.3 16-5 AOP',
  'old':'Reference tool lacks M4 A/B/C/D/E preassignments and the AOP mnemonic',
  'new':'; '.join(AE_PREASSIGNMENTS),'class':'verified'})
 equalities=[line for line in rendered if re.match(r'^[^→|,{}]+=',line.split(' ** ',1)[0])]
 code=[line for line in rendered if line not in equalities]
 rendered=equalities+code+(['☛☛PUNCH 200002'] if args.module=='main' else [])
 out=ROOT/'work/sketchpad'/f'{args.module}-expanded.tx2as'
 out.parent.mkdir(parents=True, exist_ok=True)
 out.write_text('\n'.join(rendered)+'\n')
 out.with_suffix('.json').write_text(json.dumps({'module':args.module,'source_pages':sections[args.module],
  'changes':changes,'macro_calls':x.stats,'rc_origin':f'{args.rc_origin:o}','expanded_lines':len(expanded),'lines':[{'text':E.render(a),'source':b} for a,b in expanded]},ensure_ascii=False,indent=2)+'\n')
 print(f'{args.module}: {len(expanded)} expanded lines; {sum(x.stats.values())} macro calls; {len(changes)} source changes')
if __name__=='__main__':main()
