"""Explicit, source-bound fast dispatch for the raw RRO Pair's cold instruction hook."""
from collections import Counter
import ctypes
import hashlib
import inspect
import json
from pathlib import Path

import native_read_api as read_api
import unicorn.unicorn_py3.unicorn as binding
from unicorn import riscv_const as r
from emulation_layout import CODE

ROOT = Path(__file__).resolve().parents[2]
PROFILE_SOURCES = tuple('tests/npu/' + name for name in (
    'native_cold_observer.py', 'test_native_cold_observer.py', 'test_rro_wire_native_pair.py',
    'test_cold_txdone_native.py', 'test_cold_packet_native.py', 'test_rx_stats.py',
    'test_cold_page_native.py', 'test_cold_page_caller.py', 'test_bootstrap_v2_composition.py',
    'test_bootstrap_control_v2.py', 'test_multihart_cold_boot.py', 'test_native_wifi_boot.py',
    'test_bootstrap_native.py', 'test_boot_irq_installation.py', 'test_firmware_memory_layout.py',
    'emulation_layout.py')) + (
    'research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt',)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_reviewed(receipt_path):
    receipt_path = Path(receipt_path).resolve(strict=True)
    if not receipt_path.is_relative_to(ROOT / '.local'):
        raise RuntimeError('cold observer requires an explicit private build receipt')
    receipt = json.loads(receipt_path.read_bytes())
    if receipt.get('format') != 'w1700k-npu-read-api-build-v1' or receipt.get('passed') is not True:
        raise RuntimeError('cold observer build receipt is not successful')
    required = set(PROFILE_SOURCES) | {'tests/npu/native-read-api.c', 'tests/npu/native_read_api.py',
        'tests/npu/npu_csr_sampler.py', 'tools/build_npu_read_api.py'}
    inputs = receipt['inputs']
    for name in required:
        path = ROOT / name
        if str(path) not in inputs or sha(path) != inputs[str(path)]:
            raise RuntimeError('cold observer source profile differs: ' + name)
    module = read_api.load_extension(receipt['extension']['path'], receipt['extension']['sha256'])
    check_module(module)
    return module


def check_module(module):
    if (CODE != 0x84000000 or getattr(module, 'COLD_OBSERVER_API_VERSION', None) != 4 or
            getattr(module, 'COLD_OBSERVER_PC_REG', None) != r.UC_RISCV_REG_PC or
            getattr(module, 'COLD_OBSERVER_X0_REG', None) != r.UC_RISCV_REG_X0 or
            any(getattr(r, 'UC_RISCV_REG_X' + str(i)) != r.UC_RISCV_REG_X0 + i for i in range(32))):
        raise RuntimeError('compiled cold observer API/register/code profile differs')


def install_emulator(cpu, reader):
    function = binding.uclib.uc_emu_start
    if (cpu.reg_read is not reader or getattr(reader.original_read, '__self__', None) is not cpu or
            tuple(function.argtypes or ()) != (ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64,
                ctypes.c_uint64, ctypes.c_size_t) or function.restype is not ctypes.c_int or
            ctypes.sizeof(ctypes.c_size_t) != 8):
        raise RuntimeError('native cold emulation engine/API signature differs')
    reader.bind_emulator(ctypes.cast(function, ctypes.c_void_p).value)
    original = cpu.emu_start
    cpu.emu_start = reader.emulate
    return original


def profile_pcs(owner):
    import test_boot_irq_installation as irq
    import test_bootstrap_v2_composition as composition
    import test_multihart_cold_boot as harts

    pcs = set(irq.FUNCTIONS) | set(harts.STARTUP_PCS) | {
        0x84004212, 0x840048f4, 0x84004384, 0x84003f2e, irq.SENTINEL,
        0x84004492, 0x84003254, 0x84004130, 0x8400452a, 0x8400dd82,
        composition.allocator.GETTER, 0x84005200, 0x8400e37a, 0x8400e37e,
        owner.rv.symbols['npu_barrier_init'], owner.rv.symbols['npu_emulation_admission_init']}
    return frozenset(pcs)


def enable(owner, observer, reader):
    import test_multihart_cold_boot as harts

    if (type(owner.executions) is not Counter or
            getattr(owner.record, '__func__', None) is not harts.AllHarts.record or
            type(owner.events) is not list or type(owner.csr_events) is not list or
            owner.csr_sampler.__self__ is not reader or owner.csr_sampler.__name__ != 'csrs' or
            owner.get32.__self__ is not reader or owner.get32.__name__ != 'u32'):
        raise RuntimeError('cold observer requires the exact reviewed counter/record/read profile')
    observer.enable(reader, profile_pcs(owner))


def make_pair_type(base_type, module):
    import test_rro_wire_native_pair as raw
    import test_cold_txdone_native as done
    import test_cold_packet_native as packets
    import test_rx_stats as stats
    import test_cold_page_native as pages
    import test_cold_page_caller as caller
    import test_bootstrap_v2_composition as composition
    import test_multihart_cold_boot as harts
    import test_native_wifi_boot as wifi
    import test_boot_irq_installation as irq

    expected = (done.TxPackets, packets.NativePackets, stats.RxStats, pages.NativePages,
        caller.Caller, composition.Composed, harts.AllHarts, wifi.NativeWifi, irq.Installation)
    actual = tuple(kind for kind in base_type.__mro__ if 'code_hook' in kind.__dict__)
    if (actual != expected or base_type.__name__ != 'Pair' or
            Path(inspect.getsourcefile(base_type)).resolve() != ROOT / 'tests/npu/test_rro_wire_native_pair.py'):
        raise RuntimeError('cold observer supports only the reviewed raw RRO Pair method order')
    check_module(module)

    class NativeColdPair(base_type):
        def memory_observer(self, name, write):
            key = '_native_' + name
            observer = self.__dict__.get(key)
            if observer is None:
                original = getattr(base_type, name).__get__(self, type(self))
                observer = module.MemoryObserver(self, original, write)
                self.__dict__[key] = observer
            return observer

        @property
        def read_hook(self):
            return self.memory_observer('read_hook', False)

        @property
        def write_hook(self):
            return self.memory_observer('write_hook', True)

        @property
        def block(self):
            observer = self.__dict__.get('_native_block_observer')
            if observer is None:
                original = base_type.block.__get__(self, type(self))
                observer = module.BlockObserver(self, original, self.native_reader)
                self.__dict__['_native_block_observer'] = observer
            return observer

        @property
        def code_hook(self):
            observer = self.__dict__.get('_native_cold_observer')
            if observer is None:
                original = base_type.code_hook.__get__(self, type(self))
                observer = module.ColdObserver(self, original)
                self.__dict__['_native_cold_observer'] = observer
            return observer

        def __init__(self, paths, parts):
            super().__init__(paths, parts)
            self.native_reader = read_api.install(self.cpu, module)
            self.csr_sampler = self.native_reader.csrs
            self.get32 = self.native_reader.u32
            self._original_emu_start = install_emulator(self.cpu, self.native_reader)
            enable(self, self.code_hook, self.native_reader)
            enable_memory(self, self.read_hook, self.write_hook, self.native_reader, raw)

    return NativeColdPair


def enable_memory(owner, read, write, reader, raw):
    from emulation_layout import SRAM, SRAM_BYTES

    if (raw.CODE != CODE or raw.SRAM != SRAM or raw.SRAM_BYTES != SRAM_BYTES or
            type(owner.executions) is not Counter):
        raise RuntimeError('memory observer source/range profile differs')
    effects = ((raw.DMA, raw.DMA_BYTES), (raw.BLOCK_TABLE, 128 * 4), (raw.SESSION_TABLE, 4))
    read.enable(reader, ((CODE, raw.raw.image.CODE_LIMIT), (SRAM, SRAM_BYTES)),
        ((raw.PAYLOAD, 256), *effects))
    write.enable(reader, (), effects)
