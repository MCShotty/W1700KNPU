"""Fresh CSR reads through the C API; the Python engine-handle bridge is pinned."""
import ctypes
import sys
import threading

import unicorn
import unicorn.unicorn_py3.unicorn as binding
from unicorn import UcError, UC_ARCH_RISCV, UC_ERR_OK, UC_MODE_RISCV32, riscv_const as r

REGISTERS = (r.UC_RISCV_REG_MSTATUS, r.UC_RISCV_REG_MIE, r.UC_RISCV_REG_MTVEC)


class CsrSampler:
    def __init__(self, cpu):
        if (sys.platform != 'linux' or unicorn.__version__ != '2.1.4' or
                unicorn.uc_version() != (2, 1, 0x020104ff)):
            raise RuntimeError('CSR handle bridge requires the reviewed Linux Unicorn2.1.4 binding')
        if cpu.ctl_get_arch() != UC_ARCH_RISCV or cpu.ctl_get_mode() != UC_MODE_RISCV32:
            raise RuntimeError('CSR sampler requires an RV32 engine')
        if not isinstance(cpu._uch, ctypes.c_void_p) or not cpu._uch.value:
            raise RuntimeError('CSR sampler engine/library layout changed')
        self._cpu, self._handle, self._thread = cpu, cpu._uch.value, threading.get_ident()
        self._library = binding.uclib
        self.library = str(self._library._name)
        self._read = self._library.uc_reg_read_batch
        signature = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_void_p), ctypes.c_int)
        if tuple(self._read.argtypes or ()) != signature or self._read.restype is not ctypes.c_int:
            raise RuntimeError('CSR C API signature changed')
        self._ids = (ctypes.c_int * 3)(*REGISTERS)
        self._values = (ctypes.c_uint64 * 3)()
        self._pointers = (ctypes.c_void_p * 3)(*(ctypes.addressof(self._values) + index * 8 for index in range(3)))
        self._count = ctypes.c_int(3)
        if self() != tuple(cpu.reg_read(register) for register in REGISTERS):
            raise RuntimeError('CSR C API representation differs from the reviewed Python binding')

    def __call__(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError('CSR sampler is per-engine and per-thread')
        handle = self._cpu._uch
        if not handle or handle.value != self._handle:
            raise RuntimeError('CSR sampler engine handle changed')
        status = self._read(handle, self._ids, self._pointers, self._count)
        if status != UC_ERR_OK:
            raise UcError(status)
        return tuple(self._values)
