"""Differential actual RV32 fixture traces for the selected raw Pair hook, not NPU replay."""
from collections import Counter
from copy import deepcopy
import ast
import ctypes
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

from elftools.elf.elffile import ELFFile
from unicorn import (Uc, UcError, UC_ARCH_RISCV, UC_ERR_ARG, UC_HOOK_BLOCK, UC_HOOK_CODE,
    UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_READ, UC_MEM_WRITE, UC_MODE_RISCV32, riscv_const as r)
import native_cold_observer as profile
import native_read_api as api
import test_rro_wire_native_pair as raw
from emulation_layout import CODE, SRAM, SRAM_BYTES, STATE

PROGRAM = CODE + 0x180000
END = CODE + 0x200000


class NativeColdObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        receipt = os.environ.get('NPU_READ_API_BUILD_RECEIPT')
        if not receipt:
            raise RuntimeError('explicit native-reader build receipt is required')
        cls.receipt_path = Path(receipt)
        cls.receipt = json.loads(cls.receipt_path.read_bytes())
        cls.module = api.load_extension(cls.receipt['extension']['path'], cls.receipt['extension']['sha256'])
        profile.check_module(cls.module)
        lld = shutil.which('ld.lld') or str(profile.ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
        assembly = b'''.option norvc
.text
.globl sample,loop,dynamic_word,after_store
sample:
addi a0,zero,8
csrw mstatus,a0
dynamic_word:
addi t2,zero,0
addi t0,zero,7
loop:
addi t0,t0,-1
addi a1,a1,1
bnez t0,loop
csrw mie,a1
csrw mtvec,a2
csrr t1,mhartid
sw a1,0(a3)
after_store:
lw a4,0(a3)
ret
'''
        built = subprocess.run(['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
            '-nostdlib', '--ld-path=' + str(lld), '-Wl,-Ttext=' + hex(PROGRAM) + ',--no-relax,--entry=sample',
            '-x', 'assembler', '-o', '-', '-'], input=assembly, capture_output=True, timeout=60)
        if built.returncode:
            raise RuntimeError(built.stderr.decode())
        elf = ELFFile(io.BytesIO(built.stdout))
        cls.program = elf.get_section_by_name('.text').data()
        cls.symbols = {symbol.name:symbol['st_value'] for symbol in elf.get_section_by_name('.symtab').iter_symbols()}

    def owner(self, native=True):
        h = object.__new__(raw.Pair)
        h.cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        h.cpu.mem_map(CODE, 0x201000)
        h.cpu.mem_map(SRAM, SRAM_BYTES)
        h.code = bytes(PROGRAM - CODE) + self.program
        h.cpu.mem_write(PROGRAM, self.program)
        h.executions = Counter()
        h.tick, h.last_csr = 0, None
        h.events, h.csr_events = [], []
        h.done_tracking = h.packet_tracking = h.rx_tracking = h.tracking = h.probing = h.rpc_active = False
        h.done_min_sp = CODE + 0x21e00
        h.packet_changed = h.changed = True
        h.packet_mode = h.mode = h.done_mode = h.inject = None
        h.injected = False
        h.getter_calls = 0
        h.getters, h.fallbacks = [], []
        h.packet = SimpleNamespace(symbols={'npu_emulation_packet_entry':self.symbols['loop'],
            'npu_emulation_packet_txdone_publish':self.symbols['loop']})
        h.binding = SimpleNamespace(symbols={name:self.symbols['loop'] for name in
            ('npu_emulation_page_ready5','npu_emulation_page_ready6','npu_emulation_page_ready7')})
        h.rx = SimpleNamespace(symbols={'npu_emulation_rx_ready0':self.symbols['loop'],
            'npu_emulation_rx_ready2':self.symbols['loop']})
        h.deny_type = h.denied = h.pending_call = None
        h.intercept, h.intercepted = None, False
        h.hart, h.omit = 5, None
        h.stops, h.stop, h.skip_once = set(), None, None
        h.stub_counts, h.stub_returns = {}, {}
        h.allocations, h.returns, h.logs = [], [], []
        h.rv = SimpleNamespace(symbols={'npu_barrier_init':CODE + 0x1000,
            'npu_emulation_admission_init':CODE + 0x1004})
        for register, value in ((r.UC_RISCV_REG_SP,CODE + 0x21e00), (r.UC_RISCV_REG_RA,END),
            (r.UC_RISCV_REG_A1,0xfffffff8), (r.UC_RISCV_REG_A2,CODE + 0x100),
            (r.UC_RISCV_REG_A3,SRAM), (r.UC_RISCV_REG_MSTATUS,0x1880)):
            h.cpu.reg_write(register,value)
        reader = api.install(h.cpu,self.module)
        h.csr_sampler, h.get32 = reader.csrs, reader.u32
        h.put32(STATE + 40,1)
        observer = self.module.ColdObserver(h,h.code_hook) if native else None
        if native:
            profile.install_emulator(h.cpu,reader)
            profile.enable(h,observer,reader)
        return h,reader,observer

    def snapshot(self,h):
        registers = [getattr(r,'UC_RISCV_REG_X'+str(i)) for i in range(32)]
        registers += [r.UC_RISCV_REG_PC,*api.REGISTERS]
        return dict(registers=[h.cpu.reg_read(reg) for reg in registers],tick=h.tick,
            executions=sorted(h.executions.items()),events=deepcopy(h.events),csr_events=deepcopy(h.csr_events),
            memory=bytes(h.cpu.mem_read(SRAM,SRAM_BYTES)),code=bytes(h.cpu.mem_read(PROGRAM,len(self.program))),
            stubs=dict(h.stub_counts),allocations=deepcopy(h.allocations),returns=deepcopy(h.returns),
            stop=h.stop,skip_once=h.skip_once,injected=h.injected,packet_changed=h.packet_changed,
            getters=deepcopy(h.getters),fallbacks=deepcopy(h.fallbacks),getter_calls=h.getter_calls,
            done_min_sp=h.done_min_sp,pending_call=deepcopy(h.pending_call))

    def execute(self,native,mode=None):
        h,reader,observer = self.owner(native)
        before,after,memory = [],[],[]
        triggered = False
        error = None

        def before_hook(cpu,pc,size,unused):
            nonlocal triggered
            if mode == 'dynamic-csr' and pc == self.symbols['loop']:
                cpu.reg_write(r.UC_RISCV_REG_MSTATUS,0 if cpu.reg_read(r.UC_RISCV_REG_T0)&1 else 8)
            if mode == 'dynamic-word' and pc == self.symbols['dynamic_word']:
                cpu.mem_write(pc,(0xf14023f3).to_bytes(4,'little'))
            if not triggered and pc == self.symbols['loop']:
                if mode == 'pending':
                    h.pending_call = dict(type=9,return_pc=pc)
                elif mode == 'tracking':
                    h.tracking,h.inject,h.injected = True,'before-ready',False
                elif mode == 'rx_tracking':
                    h.rx_tracking,h.mode,h.changed = True,'before-ready',False
                elif mode == 'packet_tracking':
                    h.packet_tracking,h.packet_mode,h.packet_changed = True,'worker-unparked',True
                elif mode == 'done_tracking':
                    h.done_tracking,h.done_mode,h.packet_changed = True,'before-ready',False
                elif mode in ('probing','rpc_active'):
                    setattr(h,mode,True)
                triggered = True
            before.append((pc,h.tick,cpu.reg_read(r.UC_RISCV_REG_T1)))

        def after_hook(cpu,pc,size,unused):
            after.append((pc,h.tick,cpu.reg_read(r.UC_RISCV_REG_T1),len(h.csr_events)))

        def memory_hook(cpu,kind,address,size,value,unused):
            memory.append((kind,address,size,value,h.tick,cpu.reg_read(r.UC_RISCV_REG_PC)))

        if mode == 'stops':
            h.stops = {self.symbols['loop']}
        if mode == 'invalid-last-csr':
            h.last_csr = (-1,1 << 70,0)
        h.cpu.hook_add(UC_HOOK_CODE,before_hook)
        h.cpu.hook_add(UC_HOOK_CODE,observer if native else h.code_hook)
        h.cpu.hook_add(UC_HOOK_CODE,after_hook)
        h.cpu.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory_hook)
        try:
            h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
            if mode == 'stops':
                self.assertEqual(h.stop,self.symbols['loop'])
                h.skip_once = self.symbols['loop']
                h.stop = None
                h.cpu.emu_start(self.symbols['loop'],END,count=1000,timeout=1000000)
                self.assertEqual(h.stop,self.symbols['loop'])
            else:
                self.assertEqual(h.cpu.reg_read(r.UC_RISCV_REG_PC),END)
                self.assertEqual(h.cpu.reg_read(r.UC_RISCV_REG_T1),h.hart)
        except Exception as failure:
            error = (type(failure).__name__,str(failure))
        result = dict(state=self.snapshot(h),before=before,after=after,memory=memory,error=error)
        if native:
            self.assertGreater(observer.stats()['fast'],0)
            if mode in ('pending','tracking','rx_tracking','packet_tracking','done_tracking','probing','rpc_active','stops'):
                self.assertGreater(observer.stats()['reference'],0)
        return result

    def test_complete_instruction_counter_csr_register_memory_transcript(self):
        reference,candidate = self.execute(False),self.execute(True)
        self.assertEqual(reference,candidate)
        self.assertIsNone(candidate['error'])
        self.assertGreater(max(dict(candidate['state']['executions']).values()),1)
        self.assertEqual(candidate['state']['stubs'],{'mhartid-csr':1})

    def test_other_code_hooks_keep_order_and_fresh_injected_csrs(self):
        self.assertEqual(self.execute(False,'dynamic-csr'),self.execute(True,'dynamic-csr'))

    def test_fresh_instruction_bytes_detect_a_new_hart_csr(self):
        reference,candidate = self.execute(False,'dynamic-word'),self.execute(True,'dynamic-word')
        self.assertEqual(reference,candidate)
        self.assertIsNone(candidate['error'])
        self.assertEqual(candidate['state']['stubs'],{'mhartid-csr':2})

    def test_dynamic_pending_return_uses_the_reference_path(self):
        reference,candidate = self.execute(False,'pending'),self.execute(True,'pending')
        self.assertEqual(reference,candidate)
        self.assertEqual(len(candidate['state']['allocations']),1)

    def test_each_tracking_or_rpc_mode_reenters_the_reference_chain(self):
        for flag in ('done_tracking','packet_tracking','rx_tracking','tracking','probing','rpc_active'):
            with self.subTest(flag=flag):
                self.assertEqual(self.execute(False,flag),self.execute(True,flag))

    def test_stop_and_skip_once_resume_match_the_actual_reference(self):
        self.assertEqual(self.execute(False,'stops'),self.execute(True,'stops'))

    def test_negative_or_large_previous_csr_values_are_not_read_errors(self):
        reference,candidate = self.execute(False,'invalid-last-csr'),self.execute(True,'invalid-last-csr')
        self.assertEqual(reference,candidate)
        self.assertIsNone(candidate['error'])

    def test_source_bound_receipt_and_actual_pair_method_order(self):
        self.assertIs(profile.load_reviewed(self.receipt_path),self.module)
        pair = profile.make_pair_type(raw.Pair,self.module)
        self.assertIn(raw.Pair,pair.__mro__)
        self.assertIsInstance(pair.__dict__['code_hook'],property)
        with patch.object(profile,'CODE',0):
            with self.assertRaises(RuntimeError): profile.check_module(self.module)
        with patch.object(self.module,'COLD_OBSERVER_PC_REG',0):
            with self.assertRaises(RuntimeError): profile.check_module(self.module)
        with patch.object(profile,'sha',return_value='0' * 64):
            with self.assertRaises(RuntimeError): profile.load_reviewed(self.receipt_path)
        with patch.object(profile,'PROFILE_SOURCES',profile.PROFILE_SOURCES + ('missing-profile-source.py',)):
            with self.assertRaises(RuntimeError): profile.load_reviewed(self.receipt_path)

    def test_unconfigured_callback_keeps_the_original_arguments(self):
        calls = []
        def original(*args,**kwargs):
            calls.append((args,kwargs))
            return 'reference'
        observer = self.module.ColdObserver(SimpleNamespace(),original)
        self.assertEqual(observer(1,2,3,4),'reference')
        self.assertEqual(observer(1,2,other=3),'reference')
        self.assertEqual(calls,[((1,2,3,4),{}),((1,2),dict(other=3))])
        self.assertEqual(observer.stats(),dict(fast=0,reference=2))

    def test_changed_callback_metadata_falls_back_without_stale_state(self):
        for field,value in (('events',None),('csr_events',None),('code',b'changed'),
                            ('executions',Counter()),('csr_sampler',lambda: (0,0,0)),
                            ('get32',lambda address:0)):
            with self.subTest(field=field):
                h,reader,observer = self.owner()
                setattr(h,field,value)
                h.cpu.reg_write(r.UC_RISCV_REG_PC,PROGRAM)
                try: observer(h.cpu,PROGRAM,4,None)
                except (AttributeError,TypeError,KeyError): pass
                self.assertEqual(observer.stats(),dict(fast=0,reference=1))
        h,reader,observer = self.owner()
        del h.events
        with self.assertRaises(AttributeError): observer(h.cpu,PROGRAM,4,None)
        self.assertEqual(observer.stats()['reference'],1)

    def test_engine_handle_and_thread_guards_precede_native_reads(self):
        h,reader,observer = self.owner()
        with self.assertRaises(RuntimeError): observer(Uc(UC_ARCH_RISCV,UC_MODE_RISCV32),PROGRAM,4,None)
        original = h.cpu._uch
        try:
            h.cpu._uch = ctypes.c_void_p()
            with self.assertRaises(RuntimeError): observer(h.cpu,PROGRAM,4,None)
        finally:
            h.cpu._uch = original
        errors = []
        def other():
            try: observer(h.cpu,PROGRAM,4,None)
            except Exception as error: errors.append(error)
        thread = threading.Thread(target=other)
        thread.start()
        thread.join()
        self.assertEqual(len(errors),1)
        self.assertIsInstance(errors[0],RuntimeError)

    def test_cycle_collection_releases_the_observer_and_cpu(self):
        h,reader,observer = self.owner()
        h._native_cold_observer = observer
        reference = weakref.ref(h.cpu)
        h.cpu.hook_add(UC_HOOK_CODE,observer)
        del h,reader,observer
        gc.collect()
        self.assertIsNone(reference())

    def test_native_backend_errors_preserve_reference_counters_and_error_state(self):
        batch_type = ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.POINTER(ctypes.c_int),
                                     ctypes.POINTER(ctypes.c_void_p),ctypes.c_int)
        memory_type = ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_uint64,
                                      ctypes.c_void_p,ctypes.c_uint64)

        def execute(native,kind):
            h,real,unused = self.owner(False)
            calls = []
            def batch_error(*args):
                calls.append('batch')
                return UC_ERR_ARG
            def memory_error(handle,address,target,size):
                calls.append('memory')
                ctypes.memset(target,0xa5,size)
                return UC_ERR_ARG
            fake = batch_type(batch_error) if kind == 'batch' else memory_type(memory_error)
            library = api.binding.uclib
            batch = fake if kind == 'batch' else library.uc_reg_read_batch
            memory = fake if kind == 'memory' else library.uc_mem_read
            reader = self.module.Reader(h.cpu,real.original_read,UcError,
                ctypes.cast(library.uc_reg_read,ctypes.c_void_p).value,
                ctypes.cast(batch,ctypes.c_void_p).value,api.REGISTERS,
                ctypes.cast(memory,ctypes.c_void_p).value)
            h.csr_sampler,h.get32 = reader.csrs,reader.u32
            observer = self.module.ColdObserver(h,h.code_hook)
            profile.enable(h,observer,reader)
            h.cpu.reg_write(r.UC_RISCV_REG_PC,PROGRAM)
            with self.assertRaises(UcError) as caught:
                (observer if native else h.code_hook)(h.cpu,PROGRAM,4,None)
            self.assertEqual(caught.exception.errno,UC_ERR_ARG)
            self.assertEqual(calls,[kind])
            return self.snapshot(h),str(caught.exception)

        for kind in ('batch','memory'):
            with self.subTest(kind=kind):
                self.assertEqual(execute(False,kind),execute(True,kind))

    def test_enable_requires_the_reviewed_profile_and_cannot_rebind(self):
        h,reader,observer = self.owner()
        with self.assertRaises(RuntimeError): observer.enable(reader,profile.profile_pcs(h))
        with self.assertRaises(RuntimeError): observer.__init__(h,h.code_hook)
        with self.assertRaises(TypeError): self.module.ColdObserver(h,object())
        observer = self.module.ColdObserver.__new__(self.module.ColdObserver)
        with self.assertRaises(RuntimeError): observer(h.cpu,PROGRAM,4,None)
        with self.assertRaises(RuntimeError): observer.enable(reader,frozenset())

    def test_native_emulator_retains_count_timeout_and_callback_exception_behavior(self):
        for native in (False,True):
            h,reader,observer = self.owner(native)
            h.cpu.mem_write(PROGRAM,bytes.fromhex('6f000000'))
            h.cpu._hook_exception = RuntimeError('stale')
            h.cpu.emu_start(PROGRAM,END,timeout=1000000,count=17)
            self.assertEqual(h.cpu.reg_read(r.UC_RISCV_REG_PC),PROGRAM)
            self.assertFalse(h.cpu.query(raw.unicorn.UC_QUERY_TIMEOUT))
            self.assertIsNone(h.cpu._hook_exception)
            began = time.monotonic()
            h.cpu.emu_start(begin=PROGRAM,until=END,timeout=50000,count=0)
            self.assertTrue(h.cpu.query(raw.unicorn.UC_QUERY_TIMEOUT))
            self.assertLess(time.monotonic()-began,2)
            expected = RuntimeError('first callback failure')
            def fail(*args):
                raise expected
            h.cpu.hook_add(UC_HOOK_CODE,fail)
            h.cpu.ctl_remove_cache(PROGRAM,PROGRAM+4)
            with self.assertRaises(RuntimeError) as caught:
                h.cpu.emu_start(PROGRAM,END,count=100,timeout=1000000)
            self.assertIs(caught.exception,expected)

    def test_native_emulator_forwards_exact_arguments_and_backend_error_precedence(self):
        h,reader,observer = self.owner(False)
        function_type = ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_uint64,
            ctypes.c_uint64,ctypes.c_uint64,ctypes.c_size_t)
        calls = []
        def fail(handle,begin,until,timeout,count):
            calls.append((handle,begin,until,timeout,count))
            h.cpu._hook_exception = RuntimeError('secondary')
            return UC_ERR_ARG
        function = function_type(fail)
        reader.bind_emulator(ctypes.cast(function,ctypes.c_void_p).value)
        with self.assertRaises(UcError) as caught:
            reader.emulate(1,2,count=100000000,timeout=60000000)
        self.assertEqual(caught.exception.errno,UC_ERR_ARG)
        self.assertEqual(calls,[(h.cpu._uch.value,1,2,60000000,100000000)])
        for args in ((-1,2),(1,2,-1),(True,2),(1,2,0,1 << 64)):
            with self.assertRaises((OverflowError,TypeError)): reader.emulate(*args)
        with self.assertRaises(RuntimeError): reader.bind_emulator(ctypes.cast(function,ctypes.c_void_p).value)

    def test_replay_cli_explicit_native_output_root_stays_private_and_unaliased(self):
        self.assertEqual(raw.select_output_root(None),raw.OUTPUT)
        with tempfile.TemporaryDirectory(prefix='cold-observer-cli-',dir=self.receipt_path.parent) as temporary:
            root = Path(temporary).resolve()
            self.assertEqual(raw.select_output_root(root),root)
            marker = root/'keep.txt'
            marker.write_text('unchanged')
            with self.assertRaises(ValueError): raw.select_output_root(marker)
            alias = root/'alias'
            alias.symlink_to(root,target_is_directory=True)
            with self.assertRaises(ValueError): raw.select_output_root(alias)
            with self.assertRaises(ValueError): raw.select_output_root(profile.ROOT/'tests')
            self.assertEqual(marker.read_text(),'unchanged')

    def test_replay_cli_help_exposes_opt_in_backend_without_building_or_emulating(self):
        result = subprocess.run([os.sys.executable,'-B',str(profile.ROOT/'tests/npu/test_rro_wire_native_pair.py'),'--help'],
            capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('--native-cold-receipt',result.stdout)
        self.assertIn('--output-root',result.stdout)

    def call_protocol_observers(self, callback):
        h,reader,unused = self.block_owner()
        return [self.module.ColdObserver(h,callback),
            self.module.BlockObserver(h,callback,reader),
            self.module.MemoryObserver(h,callback,False),
            self.module.MemoryObserver(h,callback,True)]

    def test_vectorcall_pointers_exist_before_init_and_after_construction(self):
        function = ctypes.pythonapi.PyVectorcall_Function
        function.argtypes, function.restype = (ctypes.py_object,), ctypes.c_void_p
        for kind in (self.module.ColdObserver,self.module.BlockObserver,self.module.MemoryObserver):
            observer = kind.__new__(kind)
            self.assertTrue(function(observer),kind.__name__)
            with self.assertRaisesRegex(RuntimeError,'not initialized'):
                observer()
        for observer in self.call_protocol_observers(lambda *args,**kwargs: None):
            self.assertTrue(function(observer),type(observer).__name__)

    def test_vectorcall_and_tuple_bridge_forward_all_fallback_arguments(self):
        calls,token = [],object()
        def original(*args,**kwargs):
            calls.append((args,kwargs))
            return token
        bridge = ctypes.pythonapi.PyVectorcall_Call
        bridge.argtypes,bridge.restype = (ctypes.py_object,ctypes.py_object,ctypes.py_object),ctypes.py_object
        cases = [((),{}),((object(),),{}),((1,2,3,4),{}),((1,2,3,4,5,6),{}),
            ((),{'address':17,'unused':token}),((3,4),{'size':8,'marker':token})]
        for observer in self.call_protocol_observers(original):
            for args,kwargs in cases:
                with self.subTest(observer=type(observer).__name__,args=len(args),keywords=tuple(kwargs)):
                    calls.clear()
                    self.assertIs(observer(*args,**kwargs),token)
                    self.assertEqual(calls,[(args,kwargs)])
                    self.assertIs(bridge(observer,args,kwargs),token)
                    self.assertEqual(calls,[(args,kwargs),(args,kwargs)])

    def test_vectorcall_keyword_fallback_keeps_original_exception_identity(self):
        failure = ValueError('original vectorcall fallback')
        def original(*args,**kwargs):
            raise failure
        for observer in self.call_protocol_observers(original):
            with self.assertRaises(ValueError) as caught:
                observer(marker=17)
            self.assertIs(caught.exception,failure)

    def test_vectorcall_reference_cycles_raise_recursion_error_without_crashing(self):
        h,reader,unused = self.block_owner()
        for kind in (self.module.ColdObserver,self.module.BlockObserver,self.module.MemoryObserver):
            observer = kind.__new__(kind)
            if kind is self.module.BlockObserver:
                observer.__init__(h,observer,reader)
            elif kind is self.module.MemoryObserver:
                observer.__init__(h,observer,False)
            else:
                observer.__init__(h,observer)
            with self.assertRaises(RecursionError):
                observer(marker=17)

    def block_owner(self):
        h,reader,unused = self.owner(False)
        h.rpc_active = True
        h.counts, h.block_cache = Counter(), {}
        h.min_sp = CODE + 0x21e00
        h.executables = ((PROGRAM,len(self.program)),)
        h.raw_code = h.code
        h.block_sites = ((PROGRAM,'entry'),(self.symbols['loop'],'loop'))
        return h,reader,self.module.BlockObserver(h,h.block,reader)

    def test_cached_blocks_keep_actual_execution_order_counts_and_fresh_sp(self):
        def run(native):
            h,reader,observer = self.block_owner()
            trace = []
            def before(cpu,pc,size,unused):
                cpu.reg_write(r.UC_RISCV_REG_SP,CODE + 0x21d00 - 16 * len(trace))
            def after(cpu,pc,size,unused):
                trace.append((pc,size,dict(h.counts),h.min_sp))
            h.cpu.hook_add(UC_HOOK_BLOCK,before)
            h.cpu.hook_add(UC_HOOK_BLOCK,observer if native else h.block)
            h.cpu.hook_add(UC_HOOK_BLOCK,after)
            h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
            self.assertEqual(h.cpu.reg_read(r.UC_RISCV_REG_PC),END)
            self.assertEqual(h.counts['blocks'],len(trace))
            self.assertGreater(h.counts['loop'],1)
            if native:
                self.assertGreater(observer.stats()['fast'],0)
                self.assertGreater(observer.stats()['reference'],0)
            return self.snapshot(h),trace,dict(h.block_cache)
        self.assertEqual(run(False),run(True))

    def test_block_cache_misses_retain_all_reference_refusals(self):
        for mode in ('range','forbidden','bytes','capacity'):
            results = []
            for native in (False,True):
                h,reader,observer = self.block_owner()
                address,size = PROGRAM,4
                if mode == 'range': h.executables = ()
                if mode == 'forbidden':
                    address = 0x8400fc2c
                    h.executables = ((address,4),)
                if mode == 'bytes': h.cpu.mem_write(PROGRAM,b'\x00' * 4)
                if mode == 'capacity':
                    h.block_cache = {(i,1):() for i in range(raw.MAX_UNIQUE_BLOCKS)}
                with self.assertRaises(AssertionError) as caught:
                    (observer if native else h.block)(h.cpu,address,size,None)
                self.assertFalse(h.counts)
                if native: self.assertEqual(observer.stats()['reference'],1)
                results.append((str(caught.exception),len(h.block_cache),h.min_sp))
            self.assertEqual(*results)

    def test_cached_block_counter_replacement_and_live_stack_changes(self):
        h,reader,observer = self.block_owner()
        observer(h.cpu,PROGRAM,4,None)
        for offset in (32,16,64,0):
            h.counts = Counter()
            h.cpu.reg_write(r.UC_RISCV_REG_SP,CODE + 0x21d00 - offset)
            observer(h.cpu,PROGRAM,4,None)
            self.assertEqual(h.counts,Counter(blocks=1,entry=1))
        self.assertEqual(h.min_sp,CODE + 0x21d00 - 64)
        self.assertEqual(observer.stats(),dict(fast=4,reference=1,inactive=0))

    def block_counter_reentry(self, mode, native):
        h,reader,observer = self.block_owner()
        key = (PROGRAM,4)
        held_names = tuple(['entry','loop'])
        h.block_cache[key] = held_names
        held_counts = h.counts
        replacement = Counter(entry=40,loop=50)
        lower = CODE + 0x21000
        h.cpu.reg_write(r.UC_RISCV_REG_SP,CODE + 0x21d00)
        calls = []
        error = RuntimeError('counter arithmetic marker')

        class Value:
            def __iadd__(self, other):
                calls.append(('iadd',other))
                if mode in ('counter','per-name'):
                    h.counts = replacement
                elif mode == 'minimum':
                    h.min_sp = lower
                elif mode == 'cache':
                    h.block_cache[key] = tuple(['changed'])
                elif mode == 'clear-cache':
                    h.block_cache.clear()
                elif mode == 'exception':
                    raise error
                return 1

            def __add__(self, other):
                calls.append(('add',other))
                return self.__iadd__(other)

        held_counts['entry' if mode == 'per-name' else 'blocks'] = Value()
        caught = None
        try:
            (observer if native else h.block)(h.cpu,PROGRAM,4,None)
        except (KeyError,RuntimeError) as failure:
            caught = failure
        if mode == 'exception':
            self.assertIs(caught,error)
            held_counts.clear()
        elif mode == 'clear-cache':
            self.assertIsInstance(caught,KeyError)
            self.assertEqual(caught.args,(key,))
        else:
            self.assertIsNone(caught)
        self.assertEqual(calls,[('iadd',1)])
        if native:
            self.assertEqual(observer.stats(),dict(fast=0,reference=1,inactive=0))
        return dict(counts=dict(h.counts),old_counts=dict(held_counts),minimum=h.min_sp,
                    cache=dict(h.block_cache),calls=calls)

    def test_block_custom_arithmetic_reloads_current_counter(self):
        self.assertEqual(self.block_counter_reentry('counter',False),
                         self.block_counter_reentry('counter',True))

    def test_block_custom_arithmetic_reloads_current_minimum(self):
        self.assertEqual(self.block_counter_reentry('minimum',False),
                         self.block_counter_reentry('minimum',True))

    def test_block_custom_arithmetic_reloads_current_cache(self):
        self.assertEqual(self.block_counter_reentry('cache',False),
                         self.block_counter_reentry('cache',True))

    def test_block_custom_arithmetic_reloads_counter_for_each_name(self):
        self.assertEqual(self.block_counter_reentry('per-name',False),
                         self.block_counter_reentry('per-name',True))

    def test_block_custom_arithmetic_preserves_cleared_cache_refusal(self):
        self.assertEqual(self.block_counter_reentry('clear-cache',False),
                         self.block_counter_reentry('clear-cache',True))

    def test_block_custom_arithmetic_preserves_exception_identity(self):
        self.assertEqual(self.block_counter_reentry('exception',False),
                         self.block_counter_reentry('exception',True))

    def test_inactive_blocks_are_noops_and_metadata_changes_use_reference(self):
        h,reader,observer = self.block_owner()
        h.rpc_active = False
        observer(h.cpu,PROGRAM,4,None)
        self.assertFalse(h.counts)
        self.assertEqual(observer.stats(),dict(fast=0,reference=0,inactive=1))
        h.rpc_active = True
        observer(h.cpu,PROGRAM,4,None)
        for field,value in (('min_sp',-1),('counts',{}),('block_cache',{(PROGRAM,4):['entry']})):
            h,reader,observer = self.block_owner()
            observer(h.cpu,PROGRAM,4,None)
            setattr(h,field,value)
            try: observer(h.cpu,PROGRAM,4,None)
            except KeyError: pass
            self.assertEqual(observer.stats()['fast'],0)
            self.assertEqual(observer.stats()['reference'],2)

    def test_block_backend_sp_error_preserves_count_and_error_order(self):
        function_type = ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p)
        results = []
        for native in (False,True):
            h,real,unused = self.block_owner()
            h.block_cache[(PROGRAM,4)] = ('entry',)
            calls = []
            def fail(handle,register,target):
                calls.append(register)
                return UC_ERR_ARG
            function = function_type(fail)
            library = api.binding.uclib
            reader = self.module.Reader(h.cpu,real.original_read,UcError,
                ctypes.cast(function,ctypes.c_void_p).value,
                ctypes.cast(library.uc_reg_read_batch,ctypes.c_void_p).value,api.REGISTERS,
                ctypes.cast(library.uc_mem_read,ctypes.c_void_p).value)
            h.cpu.reg_read = reader
            observer = self.module.BlockObserver(h,h.block,reader)
            with self.assertRaises(UcError) as caught:
                (observer if native else h.block)(h.cpu,PROGRAM,4,None)
            self.assertEqual(calls,[r.UC_RISCV_REG_SP])
            self.assertEqual(h.counts,Counter(blocks=1))
            results.append((str(caught.exception),caught.exception.errno,h.min_sp))
        self.assertEqual(*results)

    def test_block_observer_engine_thread_rebind_and_cycle_guards(self):
        h,reader,observer = self.block_owner()
        observer(h.cpu,PROGRAM,4,None)
        with self.assertRaises(RuntimeError): observer.__init__(h,h.block,reader)
        errors = []
        def other():
            try: observer(h.cpu,PROGRAM,4,None)
            except Exception as error: errors.append(error)
        thread = threading.Thread(target=other)
        thread.start()
        thread.join()
        self.assertEqual(len(errors),1)
        self.assertIsInstance(errors[0],RuntimeError)
        original = h.cpu._uch
        try:
            h.cpu._uch = ctypes.c_void_p()
            with self.assertRaises(RuntimeError): observer(h.cpu,PROGRAM,4,None)
        finally: h.cpu._uch = original
        h._native_block_observer = observer
        reference = weakref.ref(h.cpu)
        h.cpu.hook_add(UC_HOOK_BLOCK,observer)
        del h,reader,observer
        errors.clear()
        gc.collect()
        self.assertIsNone(reference())

    @staticmethod
    def hook_api(function, original):
        function.argtypes, function.restype = original.argtypes, original.restype
        return function

    def test_native_block_hook_pointer_and_registry_holder(self):
        h,reader,observer = self.block_owner()
        address,userdata = observer.hook_info(h.cpu)
        self.assertEqual(userdata,id(observer))
        handle = profile.install_block_hook(h.cpu,observer)
        pointer = h.cpu._callbacks[handle]
        self.assertIsInstance(pointer,profile.binding.HOOK_CODE_CFUNC)
        self.assertEqual(ctypes.cast(pointer,ctypes.c_void_p).value,address)
        self.assertIs(pointer._observer,observer)
        self.assertEqual(len(h.cpu._callbacks),1)
        h.cpu.hook_del(handle)
        self.assertFalse(h.cpu._callbacks)

    def test_native_block_hook_actual_order_counts_and_stack(self):
        def run(mode):
            h,reader,observer = self.block_owner()
            trace = []
            def before(cpu,pc,size,unused):
                cpu.reg_write(r.UC_RISCV_REG_SP,CODE + 0x21d00 - 16 * len(trace))
                if len(trace) == 2:
                    h.counts = Counter()
            def after(cpu,pc,size,unused):
                trace.append((pc,size,dict(h.counts),h.min_sp))
            h.cpu.hook_add(UC_HOOK_BLOCK,before)
            if mode == 'gateway':
                profile.install_emulator(h.cpu,reader)
                profile.install_block_hook(h.cpu,observer)
            else:
                h.cpu.hook_add(UC_HOOK_BLOCK,observer if mode == 'vectorcall' else h.block)
            h.cpu.hook_add(UC_HOOK_BLOCK,after)
            h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
            self.assertEqual(h.cpu.reg_read(r.UC_RISCV_REG_PC),END)
            self.assertGreater(len(trace),3)
            if mode != 'reference':
                self.assertGreater(observer.stats()['fast'],0)
                self.assertGreater(observer.stats()['reference'],0)
            return self.snapshot(h),trace,dict(h.block_cache)
        reference = run('reference')
        self.assertEqual(reference,run('vectorcall'))
        self.assertEqual(reference,run('gateway'))

    def test_native_block_hook_fallback_arguments(self):
        results = []
        for native in (False,True):
            h,reader,unused = self.block_owner()
            calls = []
            def original(*args):
                self.assertIs(args[0],h.cpu)
                calls.append(args[1:])
            observer = self.module.BlockObserver(h,original,reader)
            if native: profile.install_block_hook(h.cpu,observer)
            else: h.cpu.hook_add(UC_HOOK_BLOCK,observer)
            h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
            self.assertGreater(len(calls),3)
            self.assertTrue(all(len(row) == 3 and row[2] is None for row in calls))
            self.assertEqual(observer.stats()['reference'],len(calls))
            results.append(calls)
        self.assertEqual(*results)

    def test_native_block_hook_preserves_exception_identity(self):
        for native_emulator in (False,True):
            for kind in (AssertionError,KeyboardInterrupt):
                with self.subTest(native_emulator=native_emulator,kind=kind):
                    h,reader,unused = self.block_owner()
                    error = kind('native block exception identity')
                    def original(*args): raise error
                    observer = self.module.BlockObserver(h,original,reader)
                    profile.install_block_hook(h.cpu,observer)
                    if native_emulator: profile.install_emulator(h.cpu,reader)
                    with self.assertRaises(kind) as caught:
                        h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
                    self.assertIs(caught.exception,error)
                    self.assertIs(h.cpu._hook_exception,error)

    def test_native_block_hook_preserves_first_hook_exception(self):
        h,reader,unused = self.block_owner()
        first,second = AssertionError('first'),ValueError('second')
        def before(cpu,pc,size,unused): cpu._hook_exception = first
        def original(*args): raise second
        h.cpu.hook_add(UC_HOOK_BLOCK,before)
        profile.install_block_hook(h.cpu,self.module.BlockObserver(h,original,reader))
        profile.install_emulator(h.cpu,reader)
        with self.assertRaises(AssertionError) as caught:
            h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
        self.assertIs(caught.exception,first)
        self.assertIs(h.cpu._hook_exception,first)

    def test_native_block_hook_stop_failure_is_unraisable_not_replacement(self):
        h,reader,unused = self.block_owner()
        first,stop = AssertionError('first'),RuntimeError('stop failed')
        ignored = []
        def original(*args): raise first
        def failed_stop(): raise stop
        profile.install_block_hook(h.cpu,self.module.BlockObserver(h,original,reader))
        profile.install_emulator(h.cpu,reader)
        h.cpu.emu_stop = failed_stop
        with patch.object(sys,'unraisablehook',ignored.append):
            with self.assertRaises(AssertionError) as caught:
                h.cpu.emu_start(PROGRAM,END,count=1,timeout=1000000)
        self.assertIs(caught.exception,first)
        self.assertEqual(len(ignored),1)
        self.assertIs(ignored[0].exc_value,stop)

    def test_native_block_hook_unhook_stops_observation(self):
        h,reader,observer = self.block_owner()
        handle = profile.install_block_hook(h.cpu,observer)
        h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
        self.assertGreater(h.counts['blocks'],0)
        counts,stats = h.counts.copy(),observer.stats()
        h.cpu.hook_del(handle)
        h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
        self.assertEqual(h.counts,counts)
        self.assertEqual(observer.stats(),stats)
        self.assertNotIn(handle,h.cpu._callbacks)

    def test_native_block_hook_handled_exception_context_matches_binding(self):
        for native in (False,True):
            with self.subTest(native=native):
                h,reader,unused = self.block_owner()
                outer,first,stop = LookupError('outer'),AssertionError('first'),RuntimeError('stop')
                seen,ignored = [],[]
                def original(*args): raise first
                def failed_stop():
                    seen.append(sys.exception())
                    raise stop
                observer = self.module.BlockObserver(h,original,reader)
                if native: profile.install_block_hook(h.cpu,observer)
                else: h.cpu.hook_add(UC_HOOK_BLOCK,observer)
                profile.install_emulator(h.cpu,reader)
                h.cpu.emu_stop = failed_stop
                with patch.object(sys,'unraisablehook',ignored.append):
                    try: raise outer
                    except LookupError:
                        with self.assertRaises(AssertionError) as caught:
                            h.cpu.emu_start(PROGRAM,END,count=1,timeout=1000000)
                        self.assertIs(sys.exception(),outer)
                self.assertIs(caught.exception,first)
                self.assertEqual(seen,[first])
                self.assertEqual(len(ignored),1)
                self.assertIs(ignored[0].exc_value,stop)
                self.assertIs(stop.__context__,first)

    def test_native_block_hook_holds_inflight_reference_during_self_unhook(self):
        h,reader,unused = self.block_owner()
        calls = []
        def original(cpu,pc,size,userdata):
            self.assertGreaterEqual(sys.getrefcount(observer),outside + 1)
            cpu.hook_del(handle)
            gc.collect()
            calls.append((pc,size,userdata))
        observer = self.module.BlockObserver(h,original,reader)
        handle = profile.install_block_hook(h.cpu,observer)
        outside = sys.getrefcount(observer)
        h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
        self.assertEqual(len(calls),1)
        self.assertFalse(h.cpu._callbacks)

    def test_native_block_hook_cycles_are_collectable(self):
        h,reader,observer = self.block_owner()
        h._native_block_observer = observer
        profile.install_block_hook(h.cpu,observer)
        h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
        reference = weakref.ref(h.cpu)
        collected = []
        weakref.finalize(h.cpu,collected.append,'cpu')
        del h,reader,observer
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(collected,['cpu'])

    def test_native_block_hook_registration_error_removes_guard(self):
        h,reader,observer = self.block_owner()
        def fail(*args):
            self.assertEqual(len(h.cpu._callbacks),1)
            self.assertIs(next(iter(h.cpu._callbacks.values()))._observer,observer)
            return UC_ERR_ARG
        function = self.hook_api(fail,profile.binding.uclib.uc_hook_add)
        with patch.object(profile.binding.uclib,'uc_hook_add',function):
            with self.assertRaises(UcError) as caught:
                profile.install_block_hook(h.cpu,observer)
        self.assertEqual(caught.exception.errno,UC_ERR_ARG)
        self.assertFalse(h.cpu._callbacks)

    def test_native_block_hook_commit_failure_rolls_back(self):
        h,reader,observer = self.block_owner()
        add,remove = profile.binding.uclib.uc_hook_add,profile.binding.uclib.uc_hook_del
        handles,removed = [],[]
        error = MemoryError('registry commit fixture')
        def record_add(*args):
            status = add(*args)
            handles.append(int.from_bytes(ctypes.string_at(args[1],ctypes.sizeof(profile.binding.uc_hook_h)),sys.byteorder))
            return status
        def record_remove(cpu,handle):
            removed.append(int.from_bytes(ctypes.string_at(ctypes.byref(handle),ctypes.sizeof(handle)),sys.byteorder))
            return remove(cpu,handle)
        def fail_value(handle): raise error
        # Fail Python handle publication after a real successful native registration.
        with patch.object(profile.binding.uclib,'uc_hook_add',self.hook_api(record_add,add)), \
                patch.object(profile.binding.uclib,'uc_hook_del',self.hook_api(record_remove,remove)), \
                patch.object(profile.binding.uc_hook_h,'value',property(fail_value)):
            with self.assertRaises(MemoryError) as caught:
                profile.install_block_hook(h.cpu,observer)
        self.assertIs(caught.exception,error)
        self.assertEqual(handles,removed)
        self.assertEqual(len(handles),1)
        self.assertFalse(h.cpu._callbacks)
        h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
        self.assertFalse(h.counts)

    def test_native_block_hook_rollback_failure_keeps_userdata_alive(self):
        h,reader,observer = self.block_owner()
        add,remove = profile.binding.uclib.uc_hook_add,profile.binding.uclib.uc_hook_del
        handles = []
        error = MemoryError('registry commit fixture')
        def record_add(*args):
            status = add(*args)
            handles.append(int.from_bytes(ctypes.string_at(args[1],ctypes.sizeof(profile.binding.uc_hook_h)),sys.byteorder))
            return status
        def fail_value(handle): raise error
        with patch.object(profile.binding.uclib,'uc_hook_add',self.hook_api(record_add,add)), \
                patch.object(profile.binding.uclib,'uc_hook_del',self.hook_api(lambda *args:UC_ERR_ARG,remove)), \
                patch.object(profile.binding.uc_hook_h,'value',property(fail_value)):
            with self.assertRaisesRegex(RuntimeError,'callback retained') as caught:
                profile.install_block_hook(h.cpu,observer)
        self.assertIs(caught.exception.__cause__,error)
        try:
            self.assertEqual(len(h.cpu._callbacks),1)
            self.assertIs(next(iter(h.cpu._callbacks.values()))._observer,observer)
            gc.collect()
            h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
            self.assertGreater(h.counts['blocks'],0)
        finally:
            self.assertEqual(remove(h.cpu._uch,profile.binding.uc_hook_h(handles[0])),0)
            h.cpu._callbacks.clear()

    def test_native_block_hook_engine_thread_and_preinit_refusals(self):
        h,reader,observer = self.block_owner()
        other = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
        with self.assertRaises(RuntimeError): profile.install_block_hook(other,observer)
        uninitialized = self.module.BlockObserver.__new__(self.module.BlockObserver)
        with self.assertRaises(RuntimeError): uninitialized.hook_info(h.cpu)
        errors = []
        def attempt():
            try: profile.install_block_hook(h.cpu,observer)
            except Exception as error: errors.append(error)
        thread = threading.Thread(target=attempt)
        thread.start()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors),1)
        self.assertIsInstance(errors[0],RuntimeError)
        original = h.cpu._uch
        try:
            h.cpu._uch = ctypes.c_void_p()
            with self.assertRaises(RuntimeError): profile.install_block_hook(h.cpu,observer)
        finally: h.cpu._uch = original
        address,userdata = observer.hook_info(h.cpu)
        stopped = []
        h.cpu.emu_stop = lambda:stopped.append(True)
        ctypes.cast(address,profile.binding.HOOK_CODE_CFUNC)(other._uch,PROGRAM,4,ctypes.c_void_p(userdata))
        self.assertIsInstance(h.cpu._hook_exception,RuntimeError)
        self.assertIn('engine differs',str(h.cpu._hook_exception))
        self.assertEqual(stopped,[True])
        self.assertFalse(h.counts)
        self.assertFalse(h.cpu._callbacks)

    def test_native_block_hook_api_and_registry_refusals(self):
        h,reader,observer = self.block_owner()
        class OtherDict(dict): pass
        with patch.object(h.cpu,'_callbacks',OtherDict()):
            with self.assertRaises(RuntimeError): profile.install_block_hook(h.cpu,observer)
        with patch.object(profile.binding.uclib.uc_hook_add,'restype',ctypes.c_uint64):
            with self.assertRaises(RuntimeError): profile.install_block_hook(h.cpu,observer)
        with patch.object(profile.binding,'HOOK_CODE_CFUNC',ctypes.CFUNCTYPE(ctypes.c_int)):
            with self.assertRaises(RuntimeError): profile.install_block_hook(h.cpu,observer)
        with self.assertRaises(RuntimeError): profile.install_block_hook(h.cpu,object())
        self.assertFalse(h.cpu._callbacks)

    def test_native_block_hook_pair_default_and_binding_source(self):
        h,reader,unused = self.block_owner()
        calls = []
        with patch.object(h.cpu,'hook_add',lambda *args:calls.append(args) or 123):
            self.assertEqual(raw.Pair.install_block_hook(h),123)
        self.assertEqual(calls,[(UC_HOOK_BLOCK,h.block)])
        kind = profile.make_pair_type(raw.Pair,self.module)
        candidate = object.__new__(kind)
        candidate.__dict__.update(h.__dict__)
        candidate.native_reader = reader
        handle = candidate.install_block_hook()
        self.assertIs(candidate.cpu._callbacks[handle]._observer,candidate.block)
        candidate.cpu.hook_del(handle)
        with patch.object(profile.binding,'__file__',str(Path(__file__).resolve())):
            with self.assertRaisesRegex(RuntimeError,'binding source'):
                profile.load_reviewed(self.receipt_path)

    def memory_owner(self):
        h,reader,unused = self.block_owner()
        h.retained = []
        h.rpc_writable = ((SRAM,SRAM_BYTES),)
        read = self.module.MemoryObserver(h,h.read_hook,False)
        write = self.module.MemoryObserver(h,h.write_hook,True)
        profile.enable_memory(h,read,write,reader,raw)
        return h,reader,read,write

    def memory_gateway_owner(self, write=False, original=None):
        gc.collect()
        h,reader,read,store = self.memory_owner()
        observer = store if write else read
        if original is not None:
            observer = self.module.MemoryObserver(h,original,write)
        return h,reader,observer,UC_HOOK_MEM_WRITE if write else UC_HOOK_MEM_READ

    def test_native_memory_hook_pointer_and_registry_holder(self):
        for write in (False,True):
            h,reader,observer,kind = self.memory_gateway_owner(write)
            address,userdata = observer.hook_info(h.cpu,kind)
            self.assertEqual(userdata,id(observer))
            handle = profile.install_memory_hook(h.cpu,observer,kind)
            pointer = h.cpu._callbacks[handle]
            self.assertIsInstance(pointer,profile.binding.HOOK_MEM_ACCESS_CFUNC)
            self.assertEqual(ctypes.cast(pointer,ctypes.c_void_p).value,address)
            self.assertIs(pointer._observer,observer)
            self.assertEqual(len(h.cpu._callbacks),1)
            h.cpu.hook_del(handle)
            self.assertFalse(h.cpu._callbacks)

    def test_native_memory_hook_actual_order_and_dynamic_stack_counter(self):
        def run(mode):
            gc.collect()
            h,reader,read,write = self.memory_owner()
            trace = []
            def before(cpu,kind,address,size,value,unused):
                cpu.reg_write(r.UC_RISCV_REG_SP,CODE + 0x21d00 - 16 * len(trace))
                if kind == UC_MEM_WRITE:
                    h.counts = Counter(metadata_writes=4)
                else:
                    cpu.mem_write(address,(0x12345678).to_bytes(4,'little'))
                trace.append(('before',kind,address,size,value,h.min_sp,dict(h.counts)))
            def after(cpu,kind,address,size,value,unused):
                trace.append(('after',kind,address,size,value,h.min_sp,dict(h.counts)))
            both = UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE
            h.cpu.hook_add(both,before)
            for kind,observer,reference in ((UC_HOOK_MEM_READ,read,h.read_hook),
                                            (UC_HOOK_MEM_WRITE,write,h.write_hook)):
                if mode == 'gateway': profile.install_memory_hook(h.cpu,observer,kind)
                else: h.cpu.hook_add(kind,observer if mode == 'vectorcall' else reference)
            h.cpu.hook_add(both,after)
            if mode == 'gateway': profile.install_emulator(h.cpu,reader)
            h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
            self.assertEqual(h.cpu.reg_read(r.UC_RISCV_REG_PC),END)
            self.assertEqual(h.cpu.reg_read(r.UC_RISCV_REG_A4),0x12345678)
            self.assertEqual(h.counts,Counter(metadata_writes=5))
            if mode != 'reference':
                self.assertEqual(read.stats(),dict(fast=1,reference=0))
                self.assertEqual(write.stats(),dict(fast=1,reference=0))
            return self.snapshot(h),trace,h.min_sp
        reference = run('reference')
        self.assertEqual(reference,run('vectorcall'))
        self.assertEqual(reference,run('gateway'))

    def test_native_memory_hook_fallback_arguments_and_signed_values(self):
        for write in (False,True):
            observations = []
            for native in (False,True):
                h,reader,unused,kind = self.memory_gateway_owner(write)
                calls = []
                def original(*args):
                    self.assertIs(args[0],h.cpu)
                    calls.append(args[1:])
                observer = self.module.MemoryObserver(h,original,write)
                handle = (profile.install_memory_hook(h.cpu,observer,kind) if native else
                          h.cpu.hook_add(kind,observer))
                pointer = h.cpu._callbacks[handle]
                access = UC_MEM_WRITE if write else UC_MEM_READ
                for address,size,value in ((SRAM,4,-1),(0xffffffffffffffff,-7,-(1<<63)),
                                           (SRAM,8,(1<<63)-1)):
                    userdata = ctypes.c_void_p(id(observer)) if native else None
                    pointer(h.cpu._uch,access,address,size,value,userdata)
                self.assertEqual(calls,[(access,SRAM,4,-1,None),
                    (access,0xffffffffffffffff,-7,-(1<<63),None),
                    (access,SRAM,8,(1<<63)-1,None)])
                self.assertEqual(observer.stats(),dict(fast=0,reference=3))
                observations.append(calls)
                h.cpu.hook_del(handle)
            self.assertEqual(*observations)

    def test_native_memory_hook_can_register_before_enable(self):
        for write in (False,True):
            h,reader,unused,kind = self.memory_gateway_owner(write)
            observer = self.module.MemoryObserver(h,h.write_hook if write else h.read_hook,write)
            handle = profile.install_memory_hook(h.cpu,observer,kind)
            h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
            self.assertEqual(observer.stats(),dict(fast=0,reference=1))
            observer.enable(reader,((SRAM,SRAM_BYTES),),())
            h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
            self.assertEqual(observer.stats(),dict(fast=1,reference=1))
            self.assertEqual(h.counts,Counter(metadata_writes=2) if write else Counter())
            h.cpu.hook_del(handle)

    def test_native_memory_hook_rejects_enable_with_replaced_owner_cpu(self):
        h,reader,unused,kind = self.memory_gateway_owner()
        observer = self.module.MemoryObserver(h,h.read_hook,False)
        cpu = h.cpu
        handle = profile.install_memory_hook(cpu,observer,kind)
        other = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
        other_reader = api.install(other,self.module)
        try:
            h.cpu = other
            with self.assertRaisesRegex(RuntimeError,'binding differs'):
                observer.enable(other_reader,((SRAM,SRAM_BYTES),),())
            self.assertEqual(observer.stats(),dict(fast=0,reference=0))
        finally:
            h.cpu = cpu
            cpu.hook_del(handle)

    def test_native_memory_hook_preserves_exception_identity(self):
        for write in (False,True):
            for native_emulator in (False,True):
                for error_type in (AssertionError,KeyboardInterrupt):
                    error = error_type('memory callback marker')
                    def original(*args): raise error
                    h,reader,observer,kind = self.memory_gateway_owner(write,original)
                    profile.install_memory_hook(h.cpu,observer,kind)
                    if native_emulator: profile.install_emulator(h.cpu,reader)
                    with self.assertRaises(error_type) as caught:
                        h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
                    self.assertIs(caught.exception,error)
                    self.assertIs(h.cpu._hook_exception,error)

    def test_native_memory_hook_preserves_first_exception(self):
        for write in (False,True):
            first,second = AssertionError('first'),ValueError('second')
            def original(*args): raise second
            h,reader,observer,kind = self.memory_gateway_owner(write,original)
            h.cpu.hook_add(kind,lambda cpu,*args:setattr(cpu,'_hook_exception',first))
            profile.install_memory_hook(h.cpu,observer,kind)
            profile.install_emulator(h.cpu,reader)
            with self.assertRaises(AssertionError) as caught:
                h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
            self.assertIs(caught.exception,first)
            self.assertIs(h.cpu._hook_exception,first)

    def test_native_memory_hook_backend_error_precedence(self):
        error = AssertionError('callback marker')
        def original(*args): raise error
        h,reader,observer,kind = self.memory_gateway_owner(False,original)
        address,userdata = observer.hook_info(h.cpu,kind)
        pointer = ctypes.cast(address,profile.binding.HOOK_MEM_ACCESS_CFUNC)
        function_type = ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_uint64,
            ctypes.c_uint64,ctypes.c_uint64,ctypes.c_size_t)
        def backend(handle,begin,end,timeout,count):
            pointer(handle,UC_MEM_READ,SRAM,4,0,ctypes.c_void_p(userdata))
            return UC_ERR_ARG
        function = self.hook_api(function_type(backend),profile.binding.uclib.uc_emu_start)
        with patch.object(profile.binding.uclib,'uc_emu_start',function):
            profile.install_emulator(h.cpu,reader)
            with self.assertRaises(UcError) as caught:
                h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
        self.assertEqual(caught.exception.errno,UC_ERR_ARG)
        self.assertIs(h.cpu._hook_exception,error)

    def test_native_memory_hook_handled_exception_context_matches_binding(self):
        for native in (False,True):
            outer,first,stop = LookupError('outer'),AssertionError('first'),RuntimeError('stop')
            def original(*args): raise first
            h,reader,observer,kind = self.memory_gateway_owner(False,original)
            seen,ignored = [],[]
            def failed_stop():
                seen.append(sys.exception())
                raise stop
            if native: profile.install_memory_hook(h.cpu,observer,kind)
            else: h.cpu.hook_add(kind,observer)
            profile.install_emulator(h.cpu,reader)
            h.cpu.emu_stop = failed_stop
            with patch.object(sys,'unraisablehook',ignored.append):
                try: raise outer
                except LookupError:
                    with self.assertRaises(AssertionError) as caught:
                        h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
                    self.assertIs(sys.exception(),outer)
            self.assertIs(caught.exception,first)
            self.assertEqual(seen,[first])
            self.assertEqual(len(ignored),1)
            self.assertIs(ignored[0].exc_value,stop)
            self.assertIs(stop.__context__,first)

    def test_native_memory_hook_unhook_stops_observation(self):
        h,reader,observer,kind = self.memory_gateway_owner(True)
        handle = profile.install_memory_hook(h.cpu,observer,kind)
        h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
        counts,stats = h.counts.copy(),observer.stats()
        h.cpu.hook_del(handle)
        h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
        self.assertEqual(h.counts,counts)
        self.assertEqual(observer.stats(),stats)
        self.assertNotIn(handle,h.cpu._callbacks)

    def test_native_memory_hook_holds_inflight_reference_during_self_unhook(self):
        calls = []
        def original(cpu,access,address,size,value,unused):
            self.assertGreaterEqual(sys.getrefcount(observer),outside + 1)
            cpu.hook_del(handle)
            gc.collect()
            calls.append((access,address,size,value))
        h,reader,observer,kind = self.memory_gateway_owner(False,original)
        handle = profile.install_memory_hook(h.cpu,observer,kind)
        outside = sys.getrefcount(observer)
        h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
        self.assertEqual(len(calls),1)
        self.assertFalse(h.cpu._callbacks)

    def test_native_memory_hook_cycles_are_collectable(self):
        for write in (False,True):
            h,reader,observer,kind = self.memory_gateway_owner(write)
            h._native_memory_observer = observer
            profile.install_memory_hook(h.cpu,observer,kind)
            reference = weakref.ref(h.cpu)
            del h,reader,observer
            gc.collect()
            self.assertIsNone(reference())

    def test_native_memory_hook_registration_error_removes_guard(self):
        h,reader,observer,kind = self.memory_gateway_owner()
        def fail(*args):
            self.assertEqual(len(h.cpu._callbacks),1)
            self.assertIs(next(iter(h.cpu._callbacks.values()))._observer,observer)
            return UC_ERR_ARG
        with patch.object(profile.binding.uclib,'uc_hook_add',self.hook_api(fail,profile.binding.uclib.uc_hook_add)):
            with self.assertRaises(UcError) as caught:
                profile.install_memory_hook(h.cpu,observer,kind)
        self.assertEqual(caught.exception.errno,UC_ERR_ARG)
        self.assertFalse(h.cpu._callbacks)

    def memory_hook_rollback(self, fails):
        calls = []
        h,reader,observer,kind = self.memory_gateway_owner(False,lambda *args:calls.append(args))
        add,remove = profile.binding.uclib.uc_hook_add,profile.binding.uclib.uc_hook_del
        handles,removed = [],[]
        error = MemoryError('registry commit marker')
        def record_add(*args):
            status = add(*args)
            handles.append(int.from_bytes(ctypes.string_at(args[1],ctypes.sizeof(profile.binding.uc_hook_h)),sys.byteorder))
            return status
        def record_remove(cpu,handle):
            removed.append(int.from_bytes(ctypes.string_at(ctypes.byref(handle),ctypes.sizeof(handle)),sys.byteorder))
            return UC_ERR_ARG if fails else remove(cpu,handle)
        def fail_value(handle): raise error
        with patch.object(profile.binding.uclib,'uc_hook_add',self.hook_api(record_add,add)), \
                patch.object(profile.binding.uclib,'uc_hook_del',self.hook_api(record_remove,remove)), \
                patch.object(profile.binding.uc_hook_h,'value',property(fail_value)):
            with self.assertRaises(RuntimeError if fails else MemoryError) as caught:
                profile.install_memory_hook(h.cpu,observer,kind)
        self.assertEqual(handles,removed)
        self.assertEqual(len(handles),1)
        if fails:
            self.assertIs(caught.exception.__cause__,error)
            self.assertEqual(len(h.cpu._callbacks),1)
            self.assertIs(next(iter(h.cpu._callbacks.values()))._observer,observer)
            try:
                gc.collect()
                h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
                self.assertEqual(len(calls),1)
            finally:
                self.assertEqual(remove(h.cpu._uch,profile.binding.uc_hook_h(handles[0])),0)
                h.cpu._callbacks.clear()
        else:
            self.assertIs(caught.exception,error)
            self.assertFalse(h.cpu._callbacks)
            h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
            self.assertFalse(calls)

    def test_native_memory_hook_commit_failure_rolls_back(self):
        self.memory_hook_rollback(False)

    def test_native_memory_hook_rollback_failure_keeps_userdata_alive(self):
        self.memory_hook_rollback(True)

    def test_native_memory_hook_engine_thread_mode_and_preinit_guards(self):
        h,reader,observer,kind = self.memory_gateway_owner()
        other = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
        with self.assertRaises(RuntimeError): profile.install_memory_hook(other,observer,kind)
        with self.assertRaises(ValueError): profile.install_memory_hook(h.cpu,observer,UC_HOOK_MEM_WRITE)
        uninitialized = self.module.MemoryObserver.__new__(self.module.MemoryObserver)
        with self.assertRaises(RuntimeError): uninitialized.hook_info(h.cpu,kind)
        errors = []
        def attempt():
            try: profile.install_memory_hook(h.cpu,observer,kind)
            except Exception as error: errors.append(error)
        thread = threading.Thread(target=attempt)
        thread.start()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors),1)
        self.assertIsInstance(errors[0],RuntimeError)
        original = h.cpu._uch
        try:
            h.cpu._uch = ctypes.c_void_p()
            with self.assertRaises(RuntimeError): profile.install_memory_hook(h.cpu,observer,kind)
        finally: h.cpu._uch = original
        address,userdata = observer.hook_info(h.cpu,kind)
        stopped = []
        h.cpu.emu_stop = lambda:stopped.append(True)
        ctypes.cast(address,profile.binding.HOOK_MEM_ACCESS_CFUNC)(
            other._uch,UC_MEM_READ,SRAM,4,0,ctypes.c_void_p(userdata))
        self.assertIsInstance(h.cpu._hook_exception,RuntimeError)
        self.assertIn('engine differs',str(h.cpu._hook_exception))
        self.assertEqual(stopped,[True])
        self.assertEqual(observer.stats(),dict(fast=0,reference=0))
        self.assertFalse(h.cpu._callbacks)

    def test_native_memory_hook_api_and_registry_refusals(self):
        h,reader,observer,kind = self.memory_gateway_owner()
        class OtherDict(dict): pass
        with patch.object(h.cpu,'_callbacks',OtherDict()):
            with self.assertRaises(RuntimeError): profile.install_memory_hook(h.cpu,observer,kind)
        with patch.object(profile.binding.uclib.uc_hook_add,'restype',ctypes.c_uint64):
            with self.assertRaises(RuntimeError): profile.install_memory_hook(h.cpu,observer,kind)
        with patch.object(profile.binding,'HOOK_MEM_ACCESS_CFUNC',ctypes.CFUNCTYPE(ctypes.c_int)):
            with self.assertRaises(RuntimeError): profile.install_memory_hook(h.cpu,observer,kind)
        with self.assertRaises(RuntimeError): profile.install_memory_hook(h.cpu,object(),kind)
        with self.assertRaises(RuntimeError): profile.install_memory_hook(h.cpu,observer,UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE)
        self.assertFalse(h.cpu._callbacks)

    def test_native_memory_hook_default_and_registration_order(self):
        h,reader,observer,kind = self.memory_gateway_owner()
        calls = []
        with patch.object(h.cpu,'hook_add',lambda *args:calls.append(args) or 123):
            self.assertEqual(raw.Pair.install_memory_hook(h,kind,h.read_hook),123)
        self.assertEqual(calls,[(kind,h.read_hook)])
        candidate = object.__new__(profile.make_pair_type(raw.Pair,self.module))
        candidate.__dict__.update(h.__dict__)
        candidate.native_reader = reader
        handle = candidate.install_memory_hook(kind,candidate.read_hook)
        self.assertIs(candidate.cpu._callbacks[handle]._observer,candidate.read_hook)
        candidate.cpu.hook_del(handle)
        source = (profile.ROOT/'tests/npu/test_boot_irq_installation.py').read_text()
        tree = ast.parse(source)
        installation, = [node for node in tree.body if isinstance(node,ast.ClassDef) and node.name == 'Installation']
        init, = [node for node in installation.body if isinstance(node,ast.FunctionDef) and node.name == '__init__']
        registrations = sorted((node for node in ast.walk(init) if isinstance(node,ast.Call) and
            isinstance(node.func,ast.Attribute) and node.func.attr in ('hook_add','install_memory_hook')),key=lambda node:node.lineno)
        self.assertEqual([(node.func.attr,node.args[0].id) for node in registrations],
            [('hook_add','UC_HOOK_CODE'),('install_memory_hook','UC_HOOK_MEM_READ'),
             ('install_memory_hook','UC_HOOK_MEM_WRITE'),('hook_add','UC_HOOK_MEM_INVALID')])

    def test_memory_callbacks_keep_actual_register_memory_and_hook_order_transcripts(self):
        def run(native):
            h,reader,read,write = self.memory_owner()
            trace = []
            def before(cpu,kind,address,size,value,unused):
                cpu.reg_write(r.UC_RISCV_REG_SP,CODE + 0x21d00 - 16 * len(trace))
                if kind == UC_MEM_READ:
                    cpu.mem_write(address,(0x12345678).to_bytes(4,'little'))
                trace.append(('before',kind,address,size,value,h.min_sp,dict(h.counts)))
            def after(cpu,kind,address,size,value,unused):
                trace.append(('after',kind,address,size,value,h.min_sp,dict(h.counts)))
            both = UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE
            h.cpu.hook_add(both,before)
            h.cpu.hook_add(UC_HOOK_MEM_READ,read if native else h.read_hook)
            h.cpu.hook_add(UC_HOOK_MEM_WRITE,write if native else h.write_hook)
            h.cpu.hook_add(both,after)
            h.cpu.emu_start(PROGRAM,END,count=1000,timeout=1000000)
            self.assertEqual(h.cpu.reg_read(r.UC_RISCV_REG_PC),END)
            self.assertEqual(h.cpu.reg_read(r.UC_RISCV_REG_A4),0x12345678)
            self.assertEqual(h.counts,Counter(metadata_writes=1))
            if native:
                self.assertEqual(read.stats(),dict(fast=1,reference=0))
                self.assertEqual(write.stats(),dict(fast=1,reference=0))
            return self.snapshot(h),trace,h.min_sp
        self.assertEqual(run(False),run(True))

    def test_memory_payload_and_io_reads_keep_reference_effects_and_counts(self):
        def run(native):
            h,reader,read,write = self.memory_owner()
            effects = []
            h.effect = lambda *args: effects.append(args)
            callback = read if native else h.read_hook
            for address in (raw.PAYLOAD,raw.PAYLOAD+252,raw.DMA,raw.BLOCK_TABLE,raw.SESSION_TABLE):
                callback(h.cpu,UC_MEM_READ,address,4,0,None)
            self.assertEqual(h.counts,Counter(payload_reads=2))
            self.assertEqual(len(effects),3)
            if native: self.assertEqual(read.stats(),dict(fast=0,reference=5))
            return dict(h.counts),effects,h.min_sp
        self.assertEqual(run(False),run(True))

    def test_memory_io_writes_observe_sp_before_the_original_effect(self):
        def run(native):
            h,reader,read,write = self.memory_owner()
            effects = []
            h.effect = lambda *args: effects.append((args,h.min_sp,dict(h.counts)))
            callback = write if native else h.write_hook
            for index,address in enumerate((raw.DMA,raw.BLOCK_TABLE,raw.SESSION_TABLE)):
                h.cpu.reg_write(r.UC_RISCV_REG_SP,CODE + 0x21d00 - 16 * index)
                callback(h.cpu,UC_MEM_WRITE,address,4,index,None)
            self.assertFalse(h.counts)
            self.assertEqual([row[1] for row in effects],
                [CODE + 0x21d00 - 16 * index for index in range(3)])
            if native: self.assertEqual(write.stats(),dict(fast=0,reference=3))
            return effects,h.min_sp
        self.assertEqual(run(False),run(True))

    def test_memory_full_interval_boundaries_and_protected_retained_refusals(self):
        def run(native):
            h,reader,read,write = self.memory_owner()
            effects = []
            h.effect = lambda *args: effects.append(args)
            callback = read if native else h.read_hook
            for address,size in ((CODE,4),(CODE+raw.raw.image.CODE_LIMIT-4,4),
                    (SRAM+SRAM_BYTES-4,4),(raw.BLOCK_TABLE-4,8),(raw.SESSION_TABLE+2,4)):
                callback(h.cpu,UC_MEM_READ,address,size,0,None)
            self.assertFalse(effects)
            if native: self.assertEqual(read.stats(),dict(fast=5,reference=0))
            h.retained = [(0x50000000,4096)]
            with self.assertRaisesRegex(AssertionError,'protected retained') as caught:
                callback(h.cpu,UC_MEM_READ,0x50000000,4,0,None)
            return caught.exception.args,dict(h.counts),effects,h.min_sp
        self.assertEqual(run(False),run(True))

    def test_metadata_write_uses_fresh_ranges_counter_and_sp_each_time(self):
        def run(native):
            h,reader,read,write = self.memory_owner()
            callback = write if native else h.write_hook
            for offset in (32,16,64,0):
                h.counts = Counter()
                h.cpu.reg_write(r.UC_RISCV_REG_SP,CODE + 0x21d00 - offset)
                callback(h.cpu,UC_MEM_WRITE,SRAM,4,9,None)
                self.assertEqual(h.counts,Counter(metadata_writes=1))
            self.assertEqual(h.min_sp,CODE + 0x21d00 - 64)
            h.counts = Counter()
            for index in range(3): callback(h.cpu,UC_MEM_WRITE,SRAM,4,index,None)
            self.assertEqual(h.counts,Counter(metadata_writes=3))
            h.rpc_writable = ((PROGRAM,4),)
            with self.assertRaisesRegex(AssertionError,'unexpected raw RRO memory write') as caught:
                callback(h.cpu,UC_MEM_WRITE,SRAM,4,9,None)
            if native: self.assertEqual(write.stats(),dict(fast=7,reference=1))
            return caught.exception.args,dict(h.counts),h.min_sp
        self.assertEqual(run(False),run(True))

    def test_memory_unconfigured_and_inactive_callbacks_keep_original_arguments(self):
        calls = []
        def original(*args,**kwargs):
            calls.append((args,kwargs))
            return 'reference'
        observer = self.module.MemoryObserver(SimpleNamespace(),original,False)
        self.assertEqual(observer(1,2),'reference')
        self.assertEqual(observer(cpu=3),'reference')
        h,reader,read,write = self.memory_owner()
        observer = self.module.MemoryObserver(h,original,False)
        observer.enable(reader,((SRAM,SRAM_BYTES),),())
        h.rpc_active = False
        self.assertEqual(observer(h.cpu,UC_MEM_READ,SRAM,4,0,None),'reference')
        self.assertEqual(observer.stats(),dict(fast=0,reference=1))
        self.assertEqual(calls[:2],[((1,2),{}),((),dict(cpu=3))])
        self.assertEqual(calls[2],((h.cpu,UC_MEM_READ,SRAM,4,0,None),{}))
        with self.assertRaises(TypeError): self.module.MemoryObserver(h,original,0)

    def test_memory_changed_metadata_falls_back_without_stale_owner_state(self):
        for field,value in (('counts',{}),('min_sp',-1),('rpc_writable',[(SRAM,SRAM_BYTES)]),
                            ('rpc_writable',((SRAM,-1),)),('__dict__',None)):
            outcomes = []
            for native in (False,True):
                h,reader,read,write = self.memory_owner()
                setattr(h,field,dict(h.__dict__) if field == '__dict__' else value.copy() if isinstance(value,dict) else value)
                error = None
                try: (write if native else h.write_hook)(h.cpu,UC_MEM_WRITE,SRAM,4,0,None)
                except (KeyError,TypeError,AssertionError) as caught: error = (type(caught).__name__,str(caught))
                outcomes.append((error,dict(h.counts),h.min_sp))
                if native: self.assertEqual(write.stats(),dict(fast=0,reference=1))
            self.assertEqual(*outcomes)

    def test_memory_sp_backend_failure_precedes_metadata_count_and_io_effect(self):
        function_type = ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p)
        for address in (SRAM,raw.DMA):
            outcomes = []
            for native in (False,True):
                h,real,read,unused = self.memory_owner()
                calls = []
                def fail(handle,register,target):
                    calls.append(register)
                    return UC_ERR_ARG
                function = function_type(fail)
                library = api.binding.uclib
                reader = self.module.Reader(h.cpu,real.original_read,UcError,
                    ctypes.cast(function,ctypes.c_void_p).value,
                    ctypes.cast(library.uc_reg_read_batch,ctypes.c_void_p).value,api.REGISTERS,
                    ctypes.cast(library.uc_mem_read,ctypes.c_void_p).value)
                h.cpu.reg_read = reader
                read = self.module.MemoryObserver(h,h.read_hook,False)
                write = self.module.MemoryObserver(h,h.write_hook,True)
                profile.enable_memory(h,read,write,reader,raw)
                with self.assertRaises(UcError) as caught:
                    (write if native else h.write_hook)(h.cpu,UC_MEM_WRITE,address,4,0,None)
                self.assertEqual(calls,[r.UC_RISCV_REG_SP])
                self.assertFalse(h.counts)
                outcomes.append((caught.exception.errno,str(caught.exception),h.min_sp))
            self.assertEqual(*outcomes)

    def test_memory_observer_profile_engine_thread_and_rebind_guards(self):
        h,reader,read,write = self.memory_owner()
        with self.assertRaises(RuntimeError): read.enable(reader,(),())
        with self.assertRaises(RuntimeError): read.__init__(h,h.read_hook,False)
        observer = self.module.MemoryObserver.__new__(self.module.MemoryObserver)
        with self.assertRaises(RuntimeError): observer(h.cpu,UC_MEM_READ,SRAM,4,0,None)
        errors = []
        def other():
            try: read(h.cpu,UC_MEM_READ,SRAM,4,0,None)
            except Exception as error: errors.append(error)
        thread = threading.Thread(target=other)
        thread.start()
        thread.join()
        self.assertEqual(len(errors),1)
        self.assertIsInstance(errors[0],RuntimeError)
        original = h.cpu._uch
        try:
            h.cpu._uch = ctypes.c_void_p()
            with self.assertRaises(RuntimeError): read(h.cpu,UC_MEM_READ,SRAM,4,0,None)
        finally: h.cpu._uch = original
        for ranges in ([[]],((SRAM,0),),((1 << 32,4),),tuple((SRAM,4) for i in range(17))):
            observer = self.module.MemoryObserver(h,h.read_hook,False)
            with self.assertRaises((TypeError,ValueError)): observer.enable(reader,ranges,())

    def test_memory_observer_cycles_release_all_callbacks_and_cpu(self):
        h,reader,read,write = self.memory_owner()
        h._native_read_hook,h._native_write_hook = read,write
        reference = weakref.ref(h.cpu)
        h.cpu.hook_add(UC_HOOK_MEM_READ,read)
        h.cpu.hook_add(UC_HOOK_MEM_WRITE,write)
        del h,reader,read,write
        gc.collect()
        self.assertIsNone(reference())

    def memory_effect_owner(self):
        h,reader,read,write = self.memory_owner()
        h.broker = CODE + 0x1f0000
        h.current = dict(kind='publish',table=raw.BLOCK_TABLE,pointer=raw.DMA,base=raw.DMA,bytes=65536)
        h.io_digest = hashlib.sha256()
        h.injected,h.injection = False,None
        h.put32(raw.ADM+4,1)
        h.put32(raw.ADM+8,0)
        h.put32(h.broker+8,1)
        h.put32(raw.BLOCK_TABLE,raw.DMA)
        h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS,0)
        return h,reader,read,write

    def test_memory_effect_irq_and_owner_refusals_are_preserved(self):
        for violation in ('irq','admission','broker'):
            for kind,address,value in ((UC_MEM_READ,raw.DMA,0),(UC_MEM_READ,raw.BLOCK_TABLE,0),
                    (UC_MEM_WRITE,raw.DMA,0),(UC_MEM_WRITE,raw.BLOCK_TABLE,raw.DMA)):
                outcomes = []
                for native in (False,True):
                    h,reader,read,write = self.memory_effect_owner()
                    h.cpu.reg_write(r.UC_RISCV_REG_SP,CODE + 0x21d00)
                    if violation == 'irq': h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS,8)
                    else: h.put32(raw.ADM+4 if violation == 'admission' else h.broker+8,0)
                    callback = (write if native else h.write_hook) if kind == UC_MEM_WRITE else (read if native else h.read_hook)
                    message = 'IRQs enabled' if violation == 'irq' else 'without active owner'
                    with self.assertRaisesRegex(AssertionError,message) as caught:
                        callback(h.cpu,kind,address,4,value,None)
                    self.assertFalse(h.counts)
                    self.assertFalse(h.injected)
                    if native:
                        self.assertEqual((write if kind == UC_MEM_WRITE else read).stats(),dict(fast=0,reference=1))
                    outcomes.append((caught.exception.args,h.min_sp,h.io_digest.hexdigest()))
                self.assertEqual(*outcomes)

    def test_memory_effect_barrier_admission_and_readback_injections_match(self):
        for injection in ('barrier','admission','readback'):
            outcomes = []
            for native in (False,True):
                h,reader,read,write = self.memory_effect_owner()
                h.injection = injection
                if injection == 'readback':
                    callback = read if native else h.read_hook
                    args = (h.cpu,UC_MEM_READ,raw.BLOCK_TABLE,4,0,None)
                else:
                    callback = write if native else h.write_hook
                    args = (h.cpu,UC_MEM_WRITE,raw.DMA,4,0,None)
                callback(*args)
                self.assertTrue(h.injected)
                if injection == 'readback': self.assertEqual(h.get32(raw.BLOCK_TABLE),raw.DMA ^ 4)
                else: self.assertEqual(h.get32(STATE+16 if injection == 'barrier' else raw.ADM+8),1)
                callback(*args)
                self.assertEqual(h.counts,Counter(table_reads=2) if injection == 'readback' else Counter(extent_writes=2))
                outcomes.append((dict(h.counts),h.io_digest.hexdigest(),h.min_sp,h.injected,
                    h.get32(STATE+16),h.get32(raw.ADM+8),h.get32(raw.BLOCK_TABLE)))
            self.assertEqual(*outcomes)

    def test_memory_write_intervals_cannot_widen_the_current_metadata_range(self):
        def run(native):
            h,reader,read,write = self.memory_owner()
            h.rpc_writable = ((SRAM+0x100,4),)
            callback = write if native else h.write_hook
            observations = []
            cases = ((0,4,True),(1,4,False),(0,8,False),(-1,2,False),(3,1,True),(0,0,False),(0,-1,False))
            for index,(offset,size,allowed) in enumerate(cases):
                h.cpu.reg_write(r.UC_RISCV_REG_SP,CODE+0x21d00-16*index)
                if allowed: callback(h.cpu,UC_MEM_WRITE,SRAM+0x100+offset,size,0,None)
                else:
                    with self.assertRaisesRegex(AssertionError,'unexpected raw RRO memory write'):
                        callback(h.cpu,UC_MEM_WRITE,SRAM+0x100+offset,size,0,None)
                observations.append((dict(h.counts),h.min_sp))
            self.assertEqual(h.counts,Counter(metadata_writes=2))
            if native: self.assertEqual(write.stats(),dict(fast=2,reference=5))
            return observations
        self.assertEqual(run(False),run(True))


if __name__ == '__main__':
    unittest.main()
