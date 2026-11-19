#!/usr/bin/env python3
"""63/74 IOS/TSD acceptance and Sketchpad 4.7/4.8; primary sources in device spec.
TX2_CLI selects a private CLI build; default is build/obj_cli/tx2-cli.
"""
import json, math, os, subprocess
from pathlib import Path
from test_sketchpad_functions import Sketchpad, BUTTONS, QB

ROOT = Path(__file__).resolve().parents[1]
CLI = Path(os.environ.get('TX2_CLI', ROOT / 'build/obj_cli/tx2-cli')).resolve()
MASK = (1 << 36) - 1

def ins(op, cf=0, j=0, addr=0, held=1):
    return (held << 35) | (cf << 30) | (op << 24) | (j << 18) | addr

class Client:
    def __init__(self):
        self.p = subprocess.Popen([str(CLI)], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.tape, self.direct, self.offline, self.records = [], [], [], []
    def cmd(self, text):
        self.p.stdin.write(text + '\n'); self.p.stdin.flush()
        result = json.loads(self.p.stdout.readline())
        if isinstance(result, dict):
            dev = result.get('dev', {})
            self.tape.extend(dev.get('punch', []))
            plot = dev.get('plotter', {})
            self.direct.extend(plot.get('direct', [])); self.offline.extend(plot.get('offline', []))
            self.records.extend(plot.get('records', []))
        return result
    def run(self, n):
        s = self.cmd(f'run {n} 0 0 0')
        assert s['fault'] == 0, s
        return s
    def close(self):
        self.p.terminate(); self.p.wait()

def program(c, unit, body):
    # Sequence zero installs X_unit and connects/dismisses. Every TSD in body
    # executes in the real output sequence, with hardware buffer/flag scheduling.
    c.cmd(f'poke {0o1000} {ins(0o12,j=unit,addr=0o1100)}')
    c.cmd(f'poke {0o1001} {ins(0o04,cf=0o20,j=unit,addr=0o30000,held=0)}')
    for i, w in enumerate(body): c.cmd(f'poke {0o1100+i} {w}')
    c.cmd(f'press codabo {0o1000}')

def finish(body):
    body += [ins(0o04,cf=1,j=0o63), ins(0o30,addr=0o1501), ins(0o24,addr=0o1502), ins(0o34,addr=0o1503)]
    body.append(ins(0o05,addr=0o1100+len(body)))
    return body

def punch_tests():
    c=Client()
    try:
        c.cmd('set suppress 1023'); c.cmd('dev punch startup_us 0'); c.cmd('dev punch us 10')
        word=0o123456701234; expected=[]; body=[]
        for m in (0,4,2,6):
            addr=0o1600+m; c.cmd(f'poke {addr} {word}')
            body += [ins(0o04,j=0o63,addr=0o30000+m), ins(0o04,j=0o63,addr=0o50000)]
            d=word
            for _ in range(6 if m&2 else 1):
                expected.append(0x80 | (0x40 if m&4 else 0) | (sum(((d>>(6*k+5))&1)<<k for k in range(6)) if m&2 else d&63))
                body.append(ins(0o57,addr=addr,held=0))
                if m&2: d=((d<<1)|(d>>35))&MASK
        # Software-generated blank leader and END MARK, no intrinsic punch alphabet.
        for addr,value in ((0o1620,0),(0o1621,0o73)):
            c.cmd(f'poke {addr} {value}')
            body += [ins(0o04,j=0o63,addr=0o30000),ins(0o57,addr=addr,held=0)]
            expected.append(0x80|value)
        c.cmd(f'poke {0o1502} 1'); program(c,0o63,finish(body)); s=c.run(100000)
        assert c.tape==expected,(c.tape,expected)
        for m in (2,6): assert c.cmd(f'peek {0o1600+m} 1')[0]==((word<<6)|(word>>30))&MASK
        report=c.cmd(f'peek {0o1501} 1')[0]
        assert report&(1<<14) and report&(1<<16),oct(report) # connected + available
        assert int(s['flags'],8)&(1<<0o63),s['flags']
    finally: c.close()
    c=Client()
    try:
        c.cmd('set suppress 1023'); c.cmd(f'poke {0o1600} 42'); c.cmd(f'poke {0o1502} 1')
        c.cmd('dev punch low 1')
        program(c,0o63,finish([ins(0o57,addr=0o1600,held=0)]))
        s=c.run(200000); assert s['units']['punch']['ready']==0 and not c.tape
        s=c.run(2100000); assert c.tape==[0x80|42] and s['units']['punch']['eia']==1
        report=c.cmd(f'peek {0o1501} 1')[0]; assert report&(1<<13),oct(report)
        c.cmd('dev punch ack 1');c.cmd('dev punch low 0');s=c.cmd('state')
        assert s['units']['punch']['lamp'] and not s['units']['punch']['buzzer']
        c.cmd('dev punch reset');s=c.cmd('state');assert not s['units']['punch']['lamp'] and s['units']['punch']['eia']
        program(c,0o63,finish([ins(0o04,j=0o63,addr=0o20000),ins(0o04,j=0o63,addr=0o30000)]));s=c.run(10000)
        assert not s['units']['punch']['eia']
        c.cmd('dev punch supply 1');c.cmd('dev punch startup_us 0');c.cmd('dev punch us 10');c.tape=[]
        program(c,0o63,finish([ins(0o57,addr=0o1600,held=0)]));s=c.run(10000)
        assert not c.tape and not s['units']['punch']['ready'] and s['units']['punch']['eia']
        c.cmd('dev punch supply 0');s=c.run(10000);assert c.tape==[0x80|42]
    finally: c.close()
    c=Client()
    try:
        c.cmd('set timing 1'); c.cmd('dev punch profile technical'); c.cmd('dev punch feed 1')
        s=c.run(999999); assert not c.tape and s['units']['punch']['motor']
        s=c.run(10000); assert c.tape and all(b==0x80 for b in c.tape)
        c.cmd('dev punch feed 0'); s=c.run(4999000); assert s['units']['punch']['motor']
        s=c.run(2000); assert not s['units']['punch']['motor']
    finally:c.close()
    return {'modes':4,'splayed_rows':12,'leader_endmark':True,'motor_startup':True,'low_supply_eia_ack_reset':True,'manual_feed_cpu_stopped':True}

def plotter_tests():
    c=Client()
    try:
        def xy(x,y,f=0): return (((x<<3)|f)<<18)|((y<<3)|f)
        c.cmd(f'poke {0o1600} {xy(0,0)}');c.cmd(f'poke {0o1601} {xy(1000,0)}')
        body=[ins(0o57,addr=0o1600,held=0),ins(0o04,j=0o74,addr=0o30001),
              ins(0o57,addr=0o1601,held=0),ins(0o04,j=0o74,addr=0o30000),
              ins(0o04,cf=1,j=0o74),ins(0o30,addr=0o1501)]
        body.append(ins(0o05,addr=0o1100+len(body)))
        program(c,0o74,body);s=c.run(500000)
        assert c.direct==[[0,0,1000,0]],c.direct
        report=c.cmd(f'peek {0o1501} 1')[0];assert report&(1<<14),oct(report)
        assert int(s['flags'],8)&(1<<0o74),s['flags']
        tape=[]
        for mode,w in [(0,xy(0,0)),(1,xy(1000,0)),(0,xy(2000,0))]+[(0o55,xy(1000,0,4))]*13:
            tape.append(0xc0|mode)
            tape.extend(0xc0|sum(((w>>(6*k+5-r))&1)<<k for k in range(6)) for r in range(6))
            tape.append(0x80|0o47)
        # Split inside a record to exercise incremental off-line transport input.
        c.cmd('dev plotter tape '+bytes(tape[:11]).hex());c.cmd('dev plotter tape '+bytes(tape[11:]).hex());s=c.cmd('state')
        assert s['units']['plotter']['tape_records']==16 and s['units']['plotter']['tally']==0o47
        assert c.offline[0]==[0,0,1000,0] and len(c.offline)>300,c.offline[:2]
        assert math.hypot(c.offline[-1][2]-2000,c.offline[-1][3])<0.01,c.offline[-1]
        for x0,y0,x1,y1 in c.offline[1:]: assert abs(math.hypot(x1-1000,y1)-1000)<0.02
        return {'ios_tsd_line':True,'offline_records':16,'closed_circle':True}
    finally:c.close()

class PlotSketchpad(Sketchpad, Client):
    def __init__(self):
        Client.__init__(self)
        self.pen=(0,0,0);self.ext=0
        self.cmd('load programs/sketchpad/sketchpad.tape');self.cmd(f'set suppress {0o200}')
        self.cmd('set reader_us 64')  # explicit accelerated fixture; free-running transport
        self.cmd(f'press codabo {0o377750}')
        for _ in range(100):
            s=self.run(2000000)
            assert s['running'], ('paper boot stopped',s['alarms'],s['tape'])
            if s['tape']['pos']==s['tape']['size']:break
        else:raise AssertionError(('paper boot incomplete',s['tape']))
        self.run(1000000)
        self.run(800000,-128,110,1)
    cmd=Client.cmd

def sketchpad_test():
    BUTTONS.update(plot=QB(4,8),punch=QB(4,7))
    sp=PlotSketchpad()
    try:
        sp.press('draw');sp.glide(-40,160);sp.press('stop')
        sp.glide(60,-40);sp.press('circle');sp.glide(110,-40);sp.press('draw')
        for a in range(15,361,15):sp.glide(round(60+50*math.cos(math.radians(a))),round(-40+50*math.sin(math.radians(a))))
        sp.press('stop'); model=sp.model(); assert model['lines']==1 and model['circles']==1, model
        sp.cmd('set timing 1')  # one board clock/us: same physical device intervals
        sp.press('plot')
        progress=None; stalled=0
        for _ in range(100):
            s=sp.run(2000000)
            if sp.direct and not (int(s['connected'],8)&(1<<0o74)): break
            p=(s['units']['plotter']['records'],s['units']['plotter']['arcs'])
            stalled=stalled+1 if p==progress else 0; progress=p
            assert stalled<5,('plotter stopped making progress',s['units']['plotter'],s['k'],s['pc'],s['flags'])
        assert not (int(s['connected'],8)&(1<<0o74)),s['units']['plotter']
        assert len(sp.direct)>30 and any(m&0o44==0o44 for m,w in sp.records),(len(sp.direct),sp.records,s['units']['plotter'])
        direct_arcs=s['units']['plotter']['arcs'];assert direct_arcs>0
        sp.press('punch')
        for _ in range(30):
            s=sp.run(2000000)
            if sp.tape and not (int(s['connected'],8)&(1<<0o63)):break
        assert sp.tape[:8]==[0x80]*6+[0x80|0o73,0x80|0o63],sp.tape[:16]
        assert len(sp.tape)>500 and sp.tape[-320:]==[0x80]*320,len(sp.tape)
        sp.cmd('dev plotter tape '+bytes(sp.tape).hex());s=sp.cmd('state')
        assert len(sp.offline)>30 and s['units']['plotter']['tape_arcs']>0,s['units']['plotter']
        assert direct_arcs==20*s['units']['plotter']['tape_arcs'],(direct_arcs,s['units']['plotter']['tape_arcs'])
        return {'model':sp.model(),'direct_records':len(sp.records),'direct_strokes':len(sp.direct),'direct_arcs':direct_arcs,'punched_lines':len(sp.tape),'offline_strokes':len(sp.offline),'offline_arcs':s['units']['plotter']['tape_arcs']}
    finally:sp.close()

if __name__=='__main__':
    print(json.dumps({'punch':punch_tests(),'plotter':plotter_tests(),'sketchpad':sketchpad_test()},ensure_ascii=False,indent=2))
    print('PASS: unit 63 four modes, assembly rotation, software leader, speed and alarms; Sketchpad 4.8 PLOT / 4.7 PUNCH line and circle plotting')
