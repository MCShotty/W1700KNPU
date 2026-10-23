#!/usr/bin/env python3
"""Modeled A/B checks for the real Pair observer methods, without native imports.

Set RRO_OBSERVER_BEFORE and RRO_OBSERVER_CANDIDATE to override the default
frozen-reference and edited-candidate paths. This suite compiles only selected
AST nodes from those files. CPU memory, registers, metadata ownership and the
parent write callback are fixtures, not Unicorn or whole-stack evidence. The
small cache-cap control uses a modeled limit of two unique blocks.
"""

import ast
from collections import Counter
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[2]
CAPSULE = ROOT / '.local/npu-rro-observer-20261023'
RELATIVE_PAIR = Path('tests/npu/test_rro_wire_native_pair.py')
BEFORE = Path(os.environ.get('RRO_OBSERVER_BEFORE', CAPSULE / 'before' / RELATIVE_PAIR))
CANDIDATE = Path(os.environ.get('RRO_OBSERVER_CANDIDATE', CAPSULE / 'edited' / RELATIVE_PAIR))

# Addresses and memory below are deliberately synthetic. The extracted methods,
# including their containment predicate and configure-time observer assignments,
# are the code under test; the real image and inherited native graph are not.
CODE, ORIGINAL_CODE_BYTES = 0x84000000, 0x20000
MAILBOX_VENEER, READY_VENEER = 0x84100000, 0x84100004
MAILBOX_BINDING, READY_BINDING = 0x84104010, 0x84104014
MUTABLE, COLD, BROKER = 0x84106000, 0x83000000, 0x83010000
STACK_TOP, PAYLOAD, ADM, STATE, SESSION = (
    0x90000000, 0x30000000, 0x31000000, 0x32000000, 0x33000000)
DMA, DMA_BYTES = 0x48000000, 0xc00000
BLOCK_TABLE, SESSION_TABLE = 0x3e901fdc, 0x3e90458c
INITIAL_SP = STACK_TOP - 0x1000
RAW_CODE = bytes(range(256)) * (0x110000 // 256)
MANIFEST = {'sections': (
    {'component': 'base', 'flags': 4, 'start': MAILBOX_VENEER,
     'end': MAILBOX_VENEER + 0x100},
    {'component': 'rro-wire', 'flags': 4, 'start': 0x84104000,
     'end': 0x84105000},
    {'component': 'rro-wire', 'flags': 1, 'start': MUTABLE,
     'end': MUTABLE + 0x20},
)}
MODEL_WRITABLE = (
    (STACK_TOP - 0x4000, 0x4000), (PAYLOAD, 256), (ADM, 44),
    (STATE, 104), (SESSION, 20), (COLD, 412), (MUTABLE, 0x20),
)


def _self_assignment(statement, attribute):
    return (isinstance(statement, ast.Assign) and len(statement.targets) == 1 and
            isinstance(statement.targets[0], ast.Attribute) and
            isinstance(statement.targets[0].value, ast.Name) and
            statement.targets[0].value.id == 'self' and
            statement.targets[0].attr == attribute)


def _only(nodes, predicate, description):
    matches = [node for node in nodes if predicate(node)]
    assert len(matches) == 1, (description, len(matches))
    return deepcopy(matches[0])


def _source_parts(path, optimized):
    assert path.is_file(), f'observer source missing: {path}'
    module = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    contained = _only(module.body, lambda node: isinstance(node, ast.FunctionDef)
                      and node.name == 'contained', 'contained')
    pair = _only(module.body, lambda node: isinstance(node, ast.ClassDef)
                 and node.name == 'Pair', 'Pair')
    methods = {}
    for name in ('__init__', 'configure', 'block', 'write_hook', 'effect'):
        methods[name] = _only(pair.body, lambda node, wanted=name:
                              isinstance(node, ast.FunctionDef) and node.name == wanted,
                              f'Pair.{name}')
    setup = [_only(methods['__init__'].body,
                   lambda node: _self_assignment(node, 'block_cache'),
                   'Pair.__init__.block_cache')]
    for name in ('executables', 'rro_mutable'):
        setup.append(_only(methods['configure'].body,
                           lambda node, wanted=name: _self_assignment(node, wanted),
                           f'Pair.configure.{name}'))
    for name in ('block_sites', 'rpc_writable'):
        matches = [node for node in methods['configure'].body
                   if _self_assignment(node, name)]
        assert len(matches) == int(optimized), (f'Pair.configure.{name}', len(matches))
        setup.extend(deepcopy(matches))
    return contained, methods, setup


def _mutate(method, kind):
    if kind == 'drop_block_sp':
        old = len(method.body)
        method.body = [node for node in method.body
                       if not _self_assignment(node, 'min_sp')]
        assert len(method.body) == old - 1, kind
    elif kind == 'skip_repeated_sites':
        loops = [node for node in method.body if isinstance(node, ast.For)
                 and isinstance(node.target, ast.Name) and node.target.id == 'name']
        assert len(loops) == 1 and len(loops[0].body) == 1, kind
        increment = loops[0].body[0]
        assert isinstance(increment, ast.AugAssign), kind
        increment.value = ast.parse("int(self.counts['blocks'] == 1)", mode='eval').body
    elif kind == 'shrink_writable':
        class Shrink(ast.NodeTransformer):
            changes = 0

            def visit_Call(self, node):
                self.generic_visit(node)
                if (isinstance(node.func, ast.Name) and node.func.id == 'contained'
                        and len(node.args) == 4 and isinstance(node.args[3], ast.Name)
                        and node.args[3].id == 'count'):
                    node.args[3] = ast.BinOp(left=node.args[3], op=ast.Sub(),
                                             right=ast.Constant(value=1))
                    self.changes += 1
                return node

        change = Shrink()
        change.visit(method)
        assert change.changes == 1, (kind, change.changes)
    else:
        raise AssertionError(('unknown mutation', kind))


def _compile_pair(path, optimized, *, limit=16384, mutation=None):
    contained, methods, setup_body = _source_parts(path, optimized)
    if mutation:
        target = 'write_hook' if mutation == 'shrink_writable' else 'block'
        _mutate(methods[target], mutation)
    setup = ast.parse('def setup_observer(self, manifest):\n    pass\n').body[0]
    setup.body = setup_body
    pair = ast.parse('class Pair(BasePair):\n    pass\n').body[0]
    pair.body = [setup, methods['block'], methods['write_hook'], methods['effect']]
    isolated = ast.fix_missing_locations(ast.Module(body=[contained, pair], type_ignores=[]))
    raw = SimpleNamespace(
        image=SimpleNamespace(ORIGINAL_CODE_BYTES=ORIGINAL_CODE_BYTES,
                              CODE_LIMIT=ORIGINAL_CODE_BYTES),
        composition=SimpleNamespace(boot=SimpleNamespace(SESSION=SESSION)),
    )
    namespace = dict(__name__='rro_wire_observer_isolated',
                     BasePair=BasePair, Counter=Counter, hashlib=hashlib,
                     struct=struct, raw=raw,
                     r=SimpleNamespace(UC_RISCV_REG_SP='SP',
                                       UC_RISCV_REG_MSTATUS='MSTATUS',
                                       UC_RISCV_REG_PC='PC'),
                     CODE=CODE, MAILBOX_VENEER=MAILBOX_VENEER,
                     READY_VENEER=READY_VENEER, STACK_TOPS=(STACK_TOP,),
                     PAYLOAD=PAYLOAD, ADM=ADM, STATE=STATE, COLD=COLD,
                     DMA=DMA, DMA_BYTES=DMA_BYTES, BLOCK_TABLE=BLOCK_TABLE,
                     SESSION_TABLE=SESSION_TABLE, MAX_UNIQUE_BLOCKS=limit)
    exec(compile(isolated, str(path), 'exec'), namespace)
    return namespace['Pair']


class FakeCPU:
    def __init__(self):
        self.regs = {'SP': INITIAL_SP, 'MSTATUS': 0, 'PC': CODE + 0x100}
        self.read_calls = []
        self.overrides = {}

    def reg_read(self, register):
        return self.regs[register]

    def mem_read(self, address, size):
        self.read_calls.append((address, size))
        if (address, size) in self.overrides:
            return self.overrides[(address, size)]
        offset = address - CODE
        assert 0 <= offset and 0 <= size and offset + size <= len(RAW_CODE), \
            ('fixture code read outside image', hex(address), size)
        return RAW_CODE[offset:offset + size]


class BasePair:
    def __init__(self):
        self.cpu = FakeCPU()
        self.raw_code = RAW_CODE
        self.rro = {'npu_emulation_rro_mailbox': MAILBOX_BINDING,
                    'npu_emulation_rro_cold_ready': READY_BINDING}
        self.cold, self.broker = COLD, BROKER
        self.rpc_active = True
        self.counts = Counter()
        self.min_sp = INITIAL_SP
        self.current = {'kind': 'publish', 'table': BLOCK_TABLE,
                        'pointer': 0x12345678}
        self.words = {ADM + 4: 1, BROKER + 8: 1}
        self.io_digest = hashlib.sha256()
        self.injection = None
        self.injected = False
        self.put_calls = []
        self.base_calls = []

    def is_memory(self, address, size):
        if size <= 0:
            return False
        guarded = (*MODEL_WRITABLE, (0x60000000, 0x100))
        return any(address < start + count + 1 and address + size > start - 1
                   for start, count in guarded)

    def write_hook(self, cpu, access, address, size, value, data):
        self.base_calls.append((access, address, size, value, data))
        return ('parent-write', address, size, value)

    def get32(self, address):
        return self.words.get(address, 0)

    def put32(self, address, value):
        self.words[address] = value
        self.put_calls.append((address, value))


def _new(pair_type):
    pair = pair_type()
    pair.setup_observer(MANIFEST)
    return pair


def _outcome(call):
    try:
        return ('return', call())
    except AssertionError as error:
        return ('raise', str(error))


def _block(pair, address, size, sp=INITIAL_SP):
    pair.cpu.regs['SP'] = sp
    return _outcome(lambda: pair.block(pair.cpu, address, size, None))


def _write(pair, address, size, value=0, sp=INITIAL_SP):
    pair.cpu.regs['SP'] = sp
    return _outcome(lambda: pair.write_hook(pair.cpu, 7, address, size, value, None))


def _state(pair):
    return dict(counts=dict(pair.counts), min_sp=pair.min_sp,
                reads=tuple(pair.cpu.read_calls), cache_keys=set(pair.block_cache),
                digest=pair.io_digest.hexdigest(), words=dict(pair.words),
                injected=pair.injected, put_calls=tuple(pair.put_calls),
                base_calls=tuple(pair.base_calls))


class ObserverEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before_type = _compile_pair(BEFORE, False)
        cls.candidate_type = _compile_pair(CANDIDATE, True)

    def paired(self):
        return _new(self.before_type), _new(self.candidate_type)

    def assert_same_state(self, before, candidate):
        left, right = _state(before), _state(candidate)
        for field in left:
            self.assertEqual(left[field], right[field], f'{field} diverged')

    def assert_same_call(self, before, candidate, invoke):
        self.assertEqual(invoke(before), invoke(candidate), 'outcome diverged')
        self.assert_same_state(before, candidate)

    def test_repeated_unique_overlapping_blocks_and_every_site(self):
        before, candidate = self.paired()
        self.assertEqual(candidate.block_sites, (
            (MAILBOX_VENEER, 'mailbox_veneer'),
            (READY_VENEER, 'ready_veneer'),
            (MAILBOX_BINDING, 'mailbox_binding'),
            (READY_BINDING, 'cold_ready_binding'),
        ))
        visits = (
            (CODE + 0x100, 8, INITIAL_SP),
            (CODE + 0x100, 8, STACK_TOP - 0x1800),
            (MAILBOX_VENEER, 8, STACK_TOP - 0x1900),
            (MAILBOX_VENEER, 8, STACK_TOP - 0x2000),
            (MAILBOX_BINDING, 8, STACK_TOP - 0x2100),
            (MAILBOX_BINDING, 8, STACK_TOP - 0x2800),
            (CODE + 0x104, 4, STACK_TOP - 0x2800),
            (READY_VENEER, 4, STACK_TOP - 0x2900),
            (READY_BINDING, 4, STACK_TOP - 0x2a00),
            (MAILBOX_VENEER, 4, STACK_TOP - 0x2b00),
        )
        for address, size, sp in visits:
            with self.subTest(address=hex(address), size=size, sp=hex(sp)):
                self.assert_same_call(before, candidate,
                                      lambda pair: _block(pair, address, size, sp))
        self.assertEqual(candidate.counts, Counter(
            blocks=10, mailbox_veneer=3, ready_veneer=3,
            mailbox_binding=2, cold_ready_binding=3))
        self.assertEqual(candidate.min_sp, STACK_TOP - 0x2b00)
        first_seen = tuple(dict.fromkeys((address, size) for address, size, _ in visits))
        self.assertEqual(tuple(candidate.cpu.read_calls), first_seen)
        self.assertEqual(tuple(before.cpu.read_calls), first_seen)
        self.assertEqual(candidate.block_cache[(MAILBOX_VENEER, 8)],
                         ('mailbox_veneer', 'ready_veneer'))
        self.assertEqual(candidate.block_cache[(MAILBOX_BINDING, 8)],
                         ('mailbox_binding', 'cold_ready_binding'))

    def test_first_seen_static_rejections_and_cache_cap(self):
        cases = (
            ('zero-size', CODE + 0x100, 0, 'unexpected-executed-component'),
            ('outside', CODE + 0x30000, 4, 'unexpected-executed-component'),
            ('cross-executable', CODE + ORIGINAL_CODE_BYTES - 4, 8,
             'unexpected-executed-component'),
            ('old-callback', 0x8400fc28, 8, 'original raw RRO callback/helper'),
            ('old-helper', 0x8400e080, 8, 'original raw RRO callback/helper'),
            ('code-mismatch', CODE + 0x200, 4, None),
        )
        for label, address, size, message in cases:
            with self.subTest(label=label):
                before, candidate = self.paired()
                if label == 'code-mismatch':
                    for pair in (before, candidate):
                        pair.cpu.overrides[(address, size)] = b'\xff' * size
                result = _block(before, address, size)
                self.assertEqual(result, _block(candidate, address, size))
                self.assertEqual(result[0], 'raise')
                if message:
                    self.assertIn(message, result[1])
                self.assert_same_state(before, candidate)
                expected_reads = ((address, size),) if label == 'code-mismatch' else ()
                self.assertEqual(tuple(candidate.cpu.read_calls), expected_reads)
                self.assertEqual(len(candidate.block_cache), 0)

        before_type = _compile_pair(BEFORE, False, limit=2)
        candidate_type = _compile_pair(CANDIDATE, True, limit=2)
        before, candidate = _new(before_type), _new(candidate_type)
        for address in (CODE + 0x100, CODE + 0x104):
            self.assert_same_call(before, candidate,
                                  lambda pair, at=address: _block(pair, at, 4))
        result = _block(before, CODE + 0x108, 4)
        self.assertEqual(result, _block(candidate, CODE + 0x108, 4))
        self.assertIn('bounded exact-code observer exhausted', result[1])
        self.assert_same_state(before, candidate)
        self.assertEqual(tuple(candidate.cpu.read_calls),
                         ((CODE + 0x100, 4), (CODE + 0x104, 4)))

    def test_rpc_inactive_bypasses_observers(self):
        before, candidate = self.paired()
        for pair in (before, candidate):
            pair.rpc_active = False
        self.assert_same_call(before, candidate,
                              lambda pair: _block(pair, MAILBOX_VENEER, 8,
                                                  STACK_TOP - 0x3000))
        self.assert_same_call(before, candidate,
                              lambda pair: _write(pair, 0x60000010, 4, 9,
                                                  STACK_TOP - 0x3000))
        self.assertEqual(candidate.counts, Counter())
        self.assertEqual(candidate.min_sp, INITIAL_SP)
        self.assertEqual(candidate.cpu.read_calls, [])
        self.assertEqual(candidate.base_calls,
                         [(7, 0x60000010, 4, 9, None)])

    def test_every_metadata_region_exact_edges(self):
        before, candidate = self.paired()
        self.assertEqual(candidate.rpc_writable, MODEL_WRITABLE)
        self.assertEqual(tuple(before.rro_mutable), ((MUTABLE, 0x20),))
        for start, count in MODEL_WRITABLE:
            probes = ((start, 1, 'return'), (start + count - 1, 1, 'return'),
                      (start, count, 'return'), (start - 1, 2, 'raise'),
                      (start + count - 1, 2, 'raise'))
            for address, size, expected in probes:
                with self.subTest(region=hex(start), address=hex(address), size=size):
                    result = _write(before, address, size, 0x55,
                                    STACK_TOP - 0x2100)
                    self.assertEqual(result, _write(candidate, address, size, 0x55,
                                                     STACK_TOP - 0x2100))
                    self.assertEqual(result[0], expected)
                    self.assert_same_state(before, candidate)
        self.assertEqual(candidate.counts['metadata_writes'], 3 * len(MODEL_WRITABLE))
        self.assertEqual(candidate.min_sp, STACK_TOP - 0x2100)
        self.assertEqual(candidate.cpu.read_calls, [])

    def test_protected_unknown_and_dynamic_effects(self):
        for address, size, expected in ((0x60000010, 4, 'raise'),
                                        (0xdead0000, 4, 'return')):
            before, candidate = self.paired()
            result = _write(before, address, size, 0x44)
            self.assertEqual(result, _write(candidate, address, size, 0x44))
            self.assertEqual(result[0], expected)
            self.assert_same_state(before, candidate)
            if expected == 'return':
                self.assertEqual(candidate.base_calls,
                                 [(7, address, size, 0x44, None)])
            else:
                self.assertIn('unexpected raw RRO memory write', result[1])

        def configure(pair, case):
            if case == 'reset-table':
                pair.current['kind'] = 'reset'
            elif case == 'wrong-pointer':
                pair.current['pointer'] = 0x87654321
            elif case == 'irq-on':
                pair.cpu.regs['MSTATUS'] = 8
            elif case == 'no-owner':
                pair.words[ADM + 4] = 0
            elif case == 'no-broker-owner':
                pair.words[BROKER + 8] = 0
            elif case in ('extent-byte', 'extent-word', 'bad-extent-byte'):
                pair.current = {'kind': 'publish', 'base': DMA + 0x1000,
                                'bytes': 65536}
            elif case == 'session-table':
                pair.current = {'kind': 'publish', 'table': SESSION_TABLE,
                                'pointer': 0x12345678}
            elif case == 'barrier-injection':
                pair.injection = 'barrier'

        cases = (
            ('table', BLOCK_TABLE, 4, 0x12345678, 'return'),
            ('reset-table', BLOCK_TABLE, 4, 0x12345678, 'raise'),
            ('wrong-pointer', BLOCK_TABLE, 4, 0x12345678, 'raise'),
            ('irq-on', BLOCK_TABLE, 4, 0x12345678, 'raise'),
            ('no-owner', BLOCK_TABLE, 4, 0x12345678, 'raise'),
            ('no-broker-owner', BLOCK_TABLE, 4, 0x12345678, 'raise'),
            ('extent-byte', DMA + 0x1007, 1, 0xff, 'return'),
            ('extent-word', DMA + 0x1000, 4, 0, 'return'),
            ('bad-extent-byte', DMA + 0x1007, 1, 0xfe, 'raise'),
            ('outside-scope', DMA + 0x2000, 4, 0, 'raise'),
            ('session-table', SESSION_TABLE, 4, 0x12345678, 'return'),
            ('barrier-injection', BLOCK_TABLE, 4, 0x12345678, 'return'),
        )
        for label, address, size, value, expected in cases:
            with self.subTest(case=label):
                before, candidate = self.paired()
                for pair in (before, candidate):
                    configure(pair, label)
                result = _write(before, address, size, value, STACK_TOP - 0x2300)
                self.assertEqual(result, _write(candidate, address, size, value,
                                                 STACK_TOP - 0x2300))
                self.assertEqual(result[0], expected)
                self.assert_same_state(before, candidate)
                self.assertEqual(candidate.cpu.read_calls, [])
                if expected == 'return':
                    digest = hashlib.sha256(struct.pack('<IIIQ',
                                            candidate.cpu.regs['PC'], address,
                                            size, value)).hexdigest()
                    self.assertEqual(candidate.io_digest.hexdigest(), digest)
                if label == 'barrier-injection':
                    self.assertEqual(candidate.put_calls, [(STATE + 16, 1)])
                    self.assertTrue(candidate.injected)

    def test_python_mutation_controls_are_caught(self):
        no_sp_type = _compile_pair(CANDIDATE, True, mutation='drop_block_sp')
        baseline, mutant = _new(self.candidate_type), _new(no_sp_type)
        for pair in (baseline, mutant):
            self.assertEqual(_block(pair, CODE + 0x100, 4), ('return', None))
            self.assertEqual(_block(pair, CODE + 0x100, 4,
                                    STACK_TOP - 0x3000), ('return', None))
        with self.assertRaisesRegex(AssertionError, 'min_sp diverged'):
            self.assert_same_state(baseline, mutant)

        no_repeat_type = _compile_pair(CANDIDATE, True,
                                       mutation='skip_repeated_sites')
        baseline, mutant = _new(self.candidate_type), _new(no_repeat_type)
        for pair in (baseline, mutant):
            for address in (MAILBOX_VENEER, MAILBOX_VENEER,
                            MAILBOX_BINDING, MAILBOX_BINDING):
                self.assertEqual(_block(pair, address, 8), ('return', None))
        with self.assertRaisesRegex(AssertionError, 'counts diverged'):
            self.assert_same_state(baseline, mutant)

        narrow_type = _compile_pair(CANDIDATE, True, mutation='shrink_writable')
        baseline, mutant = _new(self.candidate_type), _new(narrow_type)
        self.assertEqual(_write(baseline, PAYLOAD + 255, 1), ('return', None))
        changed = _write(mutant, PAYLOAD + 255, 1)
        self.assertEqual(changed[0], 'raise')
        with self.assertRaisesRegex(AssertionError, 'outcome diverged'):
            self.assertEqual(('return', None), changed, 'outcome diverged')


if __name__ == '__main__':
    unittest.main()
