#!/usr/bin/env python3
"""Snapshot a completed make-check log with hashes and stable summaries."""
import argparse,hashlib,json,pathlib,re,shutil
from datetime import datetime
from zoneinfo import ZoneInfo
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--log',default='results/full-machine-check.log')
args=parser.parse_args()
root=pathlib.Path(__file__).resolve().parents[1]
log=root/args.log;text=log.read_text()
assert not re.search(r'FATAL:|ERROR:|make: \*\*\*',text),'check log contains a failure'
passes=[line for line in text.splitlines() if line.startswith('PASS:')]
assert len(passes) in [15,16],(len(passes),passes)
rtl=sorted((root/'rtl').glob('*.v'))
assert len(rtl)==10
module_checks=[]
for src in rtl:
 for suffix in ['lint','yosys']:
  p=root/'build'/f'{src.stem}-{suffix}.log'
  assert p.exists() and p.stat().st_mtime>=max(q.stat().st_mtime for q in rtl)
  content=p.read_text();assert not re.search(r'%Error:|ERROR:',content),p
 module_checks.append({'module':src.stem,'lint':'pass','structural_synthesis':'pass'})
gates=root/'build/tx2_core-gates.log';gate_log=gates.read_text()
assert gates.stat().st_mtime>=max(q.stat().st_mtime for q in rtl) and 'ERROR:' not in gate_log
assert '14. Executing JSON backend.' in gate_log
cells=int(re.findall(r'Number of cells:\s+(\d+)',gate_log)[-1])
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
summary={'recorded_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 'scope':'serial functional TX-2 machine; original cycle overlap, physical peripherals and board validation remain separate',
 'reproduction':'make clean && make check',
 'testbenches':10,'passes':passes,'modules':module_checks,
 'alu':json.loads((root/'build/alu-summary.json').read_text()),
 'machine_cases':json.loads((root/'build/machine-summary.json').read_text()),
 'paper_fixtures':json.loads((root/'build/fixture-validation.json').read_text()),
 'core_generic_cells':cells,
 'source_sha256':{str(p.relative_to(root)):digest(p) for p in rtl},
 'verification_log_sha256':digest(log),
 'core_gate_json_sha256':digest(root/'build/tx2_core-gates.json'),
 'known_limits':['PK/QK/AK overlap and alpha/beta electrical timing',
 'rare partial-activity AOP arithmetic combinations and zero-normalization ASK bounds need further primary-source calibration',
 'paper transport mechanics, seventh channel and free-running timing',
 'specialized external controllers: magnetic tape, Xerox, punch and others',
 'original Sketchpad listing/binary verification and complete interactive workflows',
 'FPGA device mapping, timing closure and board tests']}
(root/'results/machine-progress.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
for src,dst in [('alu-summary.json','machine-alu-summary.json'),('machine-summary.json','machine-vector-summary.json'),
                ('fixture-validation.json','machine-fixture-validation.json'),('tx2_core-gates.log','machine-core-gates.log')]:
 shutil.copyfile(root/'build'/src,root/'results'/dst)
print(f'Saved machine-progress.json: 10 benches, 10 lint/synthesis modules, {cells:,} generic core cells')
