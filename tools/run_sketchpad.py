#!/usr/bin/env python3
"""Build the recovered Sketchpad listing and boot it through the TX-2 RTL PETR."""
import argparse,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TOOL_REV='7480ac70bfece86c58b28a9f085ab4fe63880aae'
LISTING_REV='3d134b23d207f169d0fb65ac5768177867689ed2'
def call(args,log=None):
 if log:
  with (ROOT/'results'/log).open('w') as out:
   subprocess.run([str(a) for a in args],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,check=True)
 else:subprocess.run([str(a) for a in args],cwd=ROOT,check=True)
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args],cwd=ROOT)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cycles',type=int,default=10000000);args=p.parse_args()
 (ROOT/'build').mkdir(exist_ok=True);(ROOT/'work').mkdir(exist_ok=True)
 upstream=ROOT/'upstream/TX-2-simulator';fork=ROOT/'work/tx2-sketchpad-tools'
 assert git(upstream,'rev-parse','HEAD').decode().strip()==TOOL_REV,'unexpected reference tool revision'
 assert git(ROOT/'upstream/Sketchpad','rev-parse','HEAD').decode().strip()==LISTING_REV,'unexpected listing revision'
 patch=ROOT/'tools/sketchpad-assembler.patch'
 if not fork.exists():call(['git','-C',upstream,'worktree','add','--detach',fork,TOOL_REV])
 actual=git(fork,'diff','--binary')
 if not actual:
  call(['git','-C',fork,'apply','--check',patch]);call(['git','-C',fork,'apply',patch])
 else:assert actual.strip()==patch.read_bytes().strip(),'tool worktree differs from the recorded patch; existing files were preserved'
 print('Building the isolated assembler and checking compiler regressions',flush=True)
 call(['cargo','build','--locked','-p','assembler','--bin','tx2m4as','--manifest-path',fork/'Cargo.toml'],'sketchpad-tool-build.log')
 call(['cargo','test','--locked','-p','assembler','--lib','--manifest-path',fork/'Cargo.toml'],'sketchpad-assembler-tests.log')
 call(['python3','tools/test_sketchpad_preparation.py'],'sketchpad-macro-tests.log')
 print('Assembling seven modules and making the checksummed physical paper stream',flush=True)
 call(['python3','tools/build_sketchpad_image.py','--assemble','--modules','main','calculate','constraints','math','display','io','build'],'sketchpad-image-build.log')
 print('Compiling the TX-2 RTL simulation',flush=True)
 call(['verilator','--binary','--timing','-Wno-fatal','--top-module','tb_sketchpad','--Mdir','build/obj_sketchpad','-o','Vtb_sketchpad','-j','4',
       *[str(p.relative_to(ROOT)) for p in sorted((ROOT/'rtl').glob('*.v'))],'tb/tb_sketchpad.v'],'sketchpad-verilator-build.log')
 print(f'Booting from plugboard 377750; then running {args.cycles:,} application clocks',flush=True)
 call(['build/obj_sketchpad/Vtb_sketchpad','+paper_boot=1',f'+max_cycles={args.cycles}'],'sketchpad-run.log')
 call(['python3','tools/render_sketchpad.py'])
if __name__=='__main__':main()
