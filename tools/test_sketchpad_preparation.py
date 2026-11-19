#!/usr/bin/env python3
"""End-to-end compiler probes with independently stated TX-2 machine words."""
import re,subprocess,tempfile,unittest
from pathlib import Path
from prepare_sketchpad import E,Expander,ROOT,AE_PREASSIGNMENTS,m4_tool_syntax
from build_sketchpad_image import decode_tape
ASSEMBLER=ROOT/'work/tx2-sketchpad-tools/target/debug/tx2m4as'
def compile_words(source):
 x=Expander();plain=x.collect([(E.encode(m4_tool_syntax(line)),f'test:{i}') for i,line in enumerate(source.splitlines()) if line.strip()]);expanded=[]
 for text,where in plain:expanded+=x.expand(text,where)
 expanded += [('1000|','RC helper block'),*x.rc]
 equalities=[t for t,_ in expanded if re.match(r'^[^→|,{}]+=',t)]
 body=[t for t,_ in expanded if t not in equalities]
 with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
  path=Path(folder);src=path/'probe.tx2as';out=path/'probe.tape'
  src.write_text('\n'.join(AE_PREASSIGNMENTS+[E.render(t) for t in equalities+body])+'\n')
  r=subprocess.run([str(ASSEMBLER),'--output',str(out),str(src)],capture_output=True,text=True)
  if r.returncode:raise AssertionError(r.stderr)
  image,_=decode_tape(out)
 return image
class M4Probes(unittest.TestCase):
 def test_negative_zero_and_coordinate_insert_masks(self):
  im=compile_words('100|\n-0\n-0,400,,-0,400\n-40,-0,,100,0')
  self.assertEqual(im[0o100],(1<<36)-1)
  self.assertEqual(im[0o101],0o777400777400)
  self.assertEqual(im[0o102],0o737777100000)
 def test_aop_mnemonic_selects_arithmetic_command(self):
  im=compile_words('100|\nAOP 66000\nAOP 67000')
  self.assertEqual(im[0o100],(0o04<<24)|0o166000)
  self.assertEqual(im[0o101],(0o04<<24)|0o167000)
 def test_m4_predefined_arithmetic_register_addresses(self):
  im=compile_words('100|\nLDA A\nLDB B\nLDC C\nLDD D\nLDE E')
  self.assertEqual([im[0o100+i] for i in range(5)],
   [0o002400377604,0o002500377605,0o002600377606,0o002700377607,0o402000377610])
 def test_omitted_leading_and_trailing_parameters(self):
  im=compile_words('@hand@@hand@DEF COPY|P@arr@Q\nLDA P\nSTA Q\n@hand@@hand@EMD\n100|\nCOPY@arr@400')
  self.assertEqual(im[0o100],0o003400000400)
  self.assertNotIn(0o101,im)
 def test_word_argument_keeps_configuration_and_index_during_arithmetic(self):
  im=compile_words('@hand@@hand@DEF NEXT@hamb@P\nLDA P+1\n@hand@@hand@EMD\n100|\nNEXT@hamb@@sup_1@400@sub_2@')
  self.assertEqual(im[0o100],0o012402000401)
 def test_scoped_local_labels(self):
  im=compile_words('@hand@@hand@DEF LOOP\nHERE@arr@JPQ HERE\n@hand@@hand@EMD\n100|\nLOOP\nLOOP')
  self.assertEqual(im[0o100],0o140500000100)
  self.assertEqual(im[0o101],0o140500000101)
 def test_stateful_rc_macro_references_share_one_instance(self):
  im=compile_words('@hand@@hand@DEF STATE\nRETURN@arr@JPQ #\n0\n@hand@@hand@EMD\n100|\nLDA {STATE}\nSTA {STATE}+1')
  self.assertEqual(im[0o100],0o002400001000)
  self.assertEqual(im[0o101],0o003400001001)
  self.assertEqual(im[0o1000],0o140500001000)
  self.assertNotIn(0o1002,im)
 def test_explicit_not_hold_overrides_jnx_automatic_hold(self):
  im=compile_words('100|\nℏ@sup_1@JNX@sub_3@400')
  self.assertEqual(im[0o100],0o010703000400)
 def test_pipe_current_location_is_captured_at_instruction(self):
  im=compile_words('100|\nDPX@sub_3@@sub_pipe@@sub_4@#-1')
  self.assertEqual(im[0o100],0o001603401000)
  self.assertEqual(im[0o1000],0o000004000077)
if __name__=='__main__':unittest.main()
