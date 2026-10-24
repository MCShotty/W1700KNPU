"""Explicit opt-in read adapter; no hooks, guest instructions or register values are cached."""
import ctypes
import hashlib
import importlib.util
from pathlib import Path
import sys
import sysconfig

from unicorn import UcError, riscv_const as r
import unicorn.unicorn_py3.unicorn as binding
from npu_csr_sampler import CsrSampler, REGISTERS

ROOT = Path(__file__).resolve().parents[2]


def load_extension(path, expected_sha256):
    if hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled():
        raise RuntimeError('native reader requires the reviewed GIL-enabled interpreter')
    path = Path(path).resolve(strict=True)
    if (not path.is_relative_to(ROOT / '.local') or
            path.name != '_npu_read_api' + sysconfig.get_config_var('EXT_SUFFIX')):
        raise RuntimeError('native reader extension must be an explicit private ABI-matched build')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise RuntimeError('native reader extension byte identity differs')
    if '_npu_read_api' in sys.modules:
        module = sys.modules['_npu_read_api']
        if (Path(module.__file__).resolve() != path or
                module._verified_sha256 != expected_sha256):
            raise RuntimeError('a different native reader extension is already loaded')
        return module
    spec = importlib.util.spec_from_file_location('_npu_read_api', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._verified_sha256 = expected_sha256
    sys.modules[spec.name] = module
    return module


def install(cpu, module):
    original = cpu.reg_read
    if isinstance(original, module.Reader):
        raise RuntimeError('native reader is already installed')
    read = binding.uclib.uc_reg_read
    if (tuple(read.argtypes or ()) != (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p) or
            read.restype is not ctypes.c_int or ctypes.sizeof(ctypes.c_void_p) != 8):
        raise RuntimeError('native reader C API signature/host width changed')
    reviewed = CsrSampler(cpu)
    registers = tuple(getattr(r, 'UC_RISCV_REG_X' + str(index)) for index in range(32))
    registers += (r.UC_RISCV_REG_PC, *REGISTERS)
    if any(cpu._select_reg_class(register) is not ctypes.c_uint64 for register in registers):
        raise RuntimeError('native reader register representation changed')
    reader = module.Reader(cpu, original, UcError,
        ctypes.cast(read, ctypes.c_void_p).value,
        ctypes.cast(binding.uclib.uc_reg_read_batch, ctypes.c_void_p).value, REGISTERS)
    if any(reader(register) != original(register) for register in registers) or reader.csrs() != reviewed():
        raise RuntimeError('native reader values differ from the reviewed Python binding')
    cpu.reg_read = reader
    return reader


def uninstall(cpu, reader):
    if cpu.reg_read is not reader:
        raise RuntimeError('native reader installation changed')
    cpu.reg_read = reader.original_read
