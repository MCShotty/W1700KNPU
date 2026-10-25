"""Differential actual RV32 fixture traces for the selected raw Pair hook, not NPU replay."""
from collections import Counter
from copy import deepcopy
import ctypes
import gc
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

from elftools.elf.elffile import ELFFile
from unicorn import (Uc, UcError, UC_ARCH_RISCV, UC_ERR_ARG, UC_HOOK_BLOCK, UC_HOOK_CODE,
    UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MODE_RISCV32, riscv_const as r)
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


if __name__ == '__main__':
    unittest.main()
