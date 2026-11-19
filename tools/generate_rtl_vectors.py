#!/usr/bin/env python3
"""Independent instruction-level test model based on original TX-2 manuals.

Quarter tuples and subword traversal are used rather than the RTL mux/gate
implementation. The CPU image is produced separately by the upstream assembler.
This covers the supported profile, not the complete historical TX-2.
"""
import json
import hashlib
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build'
BUILD.mkdir(exist_ok=True)
MASK17, MASK18, MASK36 = (1 << 17) - 1, (1 << 18) - 1, (1 << 36) - 1
LOAD_MAPS = [(0,1,2,3), (1,2,3,0), (2,3,0,1), (3,0,1,2),
             (1,0,3,2), (3,2,1,0), (0,3,1,2), (0,2,3,1)]
GROUPS = [((0,1,2,3),), ((0,1),(2,3)), ((0,),(1,2,3)), ((0,),(1,),(2,),(3,))]


def quarters(word):
    return [(word >> (9*q)) & 0o777 for q in range(4)]


def join(values):
    return sum(v << (9*q) for q,v in enumerate(values))


def exchange(source, destination, configuration, store=False, sign=True):
    active = [not bool(configuration & (1 << (q+3))) for q in range(4)]
    src, dst = quarters(source), quarters(destination)
    mapping = LOAD_MAPS[configuration & 7]
    for eq, mq in enumerate(mapping):
        if active[eq]:
            if store:
                dst[mq] = src[eq]
            else:
                dst[eq] = src[mq]
    extended = 0
    for group in GROUPS[configuration >> 7]:
        starts = [i for i,q in enumerate(group) if active[q]]
        if starts:
            extended |= sum(1 << q for q in group)
        if sign and not store:
            for start in starts:
                fill = 0o777 if dst[group[start]] & 0o400 else 0
                for distance in range(1, len(group)):
                    target = group[(start + distance) % len(group)]
                    if active[target]:
                        break
                    dst[target] = fill
    return join(dst), extended


def pack(fields):
    result = 0
    for width, value in fields:
        assert 0 <= value < 1 << width, (width, value)
        result = (result << width) | value
    return result


def make_exchange_vectors():
    book_examples = [
        (0o555666777000,0o111222333444,0o340,False,True,0o111222777000),
        (0o555666777400,0o111222333444,0o160,False,True,0o777777777400),
        (0o400000000000,0o123456101202,0o070,False,True,0o400777777777),
        (0o401000000000,0o777222333123,0o470,False,True,0o401777777123),
        (0o111222333444,0o555666777000,0o342,True,False,0o333444777000),
    ]
    for source,dest,cfg,store,sign,expected in book_examples:
        assert exchange(source,dest,cfg,store,sign)[0] == expected
    rng = random.Random(0x545832)
    count = 0
    with (BUILD / 'exchange-vectors.hex').open('w') as out:
        for cfg in range(512):
            for sample in range(32):
                source = [0, MASK36, 0o111222333444, 0o400000400000][sample] if sample < 4 else rng.getrandbits(36)
                dest = 0o765432123456 if sample < 4 else rng.getrandbits(36)
                for store,sign in [(False,False),(False,True),(True,False),(True,True)]:
                    expected,extended = exchange(source,dest,cfg,store,sign)
                    word = pack([(9,cfg),(1,int(store)),(1,int(sign)),(36,source),(36,dest),(36,expected),(4,extended)])
                    out.write(f'{word:031x}\n')
                    count += 1
    return count


def signed18(value):
    return value if value < (1 << 17) else -((~value) & MASK18)


def indexed(base, index):
    return (base + signed18(index)) & MASK17


def add_index(lhs, rhs, force_minus_zero=False):
    # Integer modulo 2^18-1 independently models end-around carry;
    # AUX is a ring sum; JPX/JNX additionally force a zero result negative.
    result = (lhs + rhs) % MASK18
    return result if result else (MASK18 if (lhs or rhs or force_minus_zero) else 0)


def load_image():
    memory = {}
    digest = hashlib.sha256((ROOT / 'programs/configured-copy.tx2as').read_bytes()).hexdigest()
    image_text = (ROOT / 'programs/configured-copy.hex').read_text()
    assert f'# source_sha256 {digest}' in image_text, 'Assembly source changed: run make assemble-demo'
    for line in image_text.splitlines():
        if line and not line.startswith('#'):
            addr,value = line.split()
            memory[int(addr,16)] = int(value,16)
    # Spot-check encodings against Handbook ch.3 independently of the CPU model.
    assert memory[0o100] == 0o002200000400
    assert memory[0o115] == 0o760601000113
    assert memory[0o116] == 0o011201000002
    return memory


def make_cpu_vectors():
    memory = load_image()
    original_memory = dict(memory)
    ae, x, f = [0]*5, [0]*64, [0]*32
    p,q = 0o100,0
    trace = []
    aliases = {0o377604:0,0o377605:1,0o377606:2,0o377607:3,0o377610:4}

    def read(address):
        return ae[aliases[address]] if address in aliases else memory[address]

    def write(address, value):
        if address in aliases:
            ae[aliases[address]] = value
        else:
            memory[address] = value

    for step in range(500):
        pc = p
        word = read(p)
        p = (p+1) & MASK17
        held = bool(word >> 35)
        cf,op,j = (word >> 30)&31, (word >> 24)&63, (word >> 18)&63
        base,defer = word & MASK17, bool(word & (1 << 17))
        if op == 0:
            break
        is_load = op in [0o20,0o24,0o25,0o26,0o27]
        is_store = op in [0o30,0o34,0o35,0o36,0o37]
        while defer:
            q = base
            pointer = read(base)
            base = indexed(pointer & MASK17,x[(pointer >> 18)&63])
            defer = bool(pointer & (1 << 17))
        addr = indexed(base, x[j]) if (is_load or is_store or op in [0o21,0o22] or (op==0o05 and cf&1)) else base
        if is_load or is_store or op in [0o10,0o11,0o16,0o21,0o22]:
            q = addr
            m = read(addr)
        if is_load:
            register = 4 if op == 0o20 else op-0o24
            ae[register] = exchange(m,ae[register],f[cf])[0]
            if op != 0o20:
                ae[4] = m
        elif is_store or op == 0o16:
            register = 4 if op == 0o30 else op-0o34
            source = (signed18(x[j]) & MASK36) if op == 0o16 else ae[register]
            result = exchange(source,m,f[cf],True,False)[0]
            write(addr,result)
            if op != 0o30:
                ae[4] = result
        elif op in [0o10,0o11]:
            existing = x[j] if op == 0o11 else 0
            value = exchange(m,existing,f[cf])[0] & MASK18
            if j:
                x[j] = add_index(x[j],value) if op==0o10 else value
            ae[4] = m
        elif op in [0o21,0o22]:
            for offset in range(1 if op==0o21 else 4):
                target = (cf+offset)&31
                if target:
                    f[target] = quarters(m)[offset]
            ae[4] = m
        elif op == 0o12:
            assert cf in [0,1]
            if j:
                x[j] = ((~addr)&MASK18) if cf else addr
        elif op == 0o05:
            assert not (cf&16 and not held)
            if cf&8:
                ae[4] = (ae[4]&MASK18) | (q << 18)
            if cf&4:
                ae[4] = (ae[4] & (MASK18 << 18)) | p
            if cf&2 and j:
                x[j] = p
            p = addr
        elif op in [0o06,0o07]:
            old = signed18(x[j])
            taken = old>0 if op==0o06 else old<0
            increment = cf if cf<16 else (~((~cf)&31))&MASK18
            if j:
                x[j] = add_index(x[j],increment,True)
            if taken:
                assert held
                ae[4] = (ae[4] & (MASK18 << 18)) | p
                p = addr
        else:
            raise AssertionError(f'Unsupported test opcode {op:o}')
        fields = [(17,pc),(36,word),(17,p),(17,q)] + [(36,n) for n in ae] + [(18,x[j]),(9,f[cf])]
        trace.append({'pc':f'{pc:06o}','instruction':f'{word:012o}',
                      'next_pc':f'{p:06o}','q':f'{q:06o}',
                      'registers':{name:f'{value:012o}' for name,value in zip('ABCDE',ae)},
                      'index_j':f'{x[j]:06o}','config_cf':f'{f[cf]:03o}',
                      'packed':f'{pack(fields):074x}'})
    else:
        raise AssertionError('Reference program did not stop')
    # Explicit end-to-end checks from the hand-calculated examples and table scan.
    assert memory[0o500] == 0o111222777000
    assert memory[0o501] == 0o123456777000
    assert memory[0o502] == 0o777000030040
    assert memory[0o511] == 0o405406407410
    assert memory[0o512] == 4
    assert memory[0o513] == 0o765432123456
    for offset in range(3):
        assert memory[0o503+offset] == memory[0o407+offset]
        assert memory[0o506+offset] == memory[0o407+offset]
    assert f[0] == 0 and f[31] == 0o234 and f[1] == 0o456 and f[2] == 0o123
    assert ae[2] == 0o777777777400
    assert p == 0o147
    (BUILD / 'demo.trace.hex').write_text('\n'.join(t['packed'] for t in trace)+'\n')
    (BUILD / 'demo.expected.json').write_text(json.dumps({'instructions_retired':len(trace),'trace':trace},indent=2))
    with (BUILD / 'demo.memory.hex').open('w') as out:
        for addr,value in sorted(memory.items()):
            if original_memory[addr] != value:
                out.write(f'{addr:05x} {value:09x}\n')
    (BUILD / 'demo.f-memory.hex').write_text(''.join(f'{value:03x}\n' for value in f))
    return len(trace)


if __name__ == '__main__':
    result = {'exchange_vectors':make_exchange_vectors(), 'demo_retired_instructions':make_cpu_vectors(),
              'random_seed':'0x545832','trace_width_bits':294}
    (BUILD / 'vector-summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
