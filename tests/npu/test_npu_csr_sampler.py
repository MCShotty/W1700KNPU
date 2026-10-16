"""Read-API equivalence controls; no current NPU observer replacement."""
import ctypes
import io
import subprocess
import threading
import unittest
from unittest.mock import Mock, patch

from elftools.elf.elffile import ELFFile
from unicorn import (Uc, UcError, UC_ARCH_RISCV, UC_ERR_ARG, UC_HOOK_CODE,
                     UC_MODE_RISCV32, UC_MODE_RISCV64, riscv_const as r)

import npu_csr_sampler as sampler


def scalar(cpu):
    return tuple(cpu.reg_read(register) for register in sampler.REGISTERS)


class CsrSamplerTests(unittest.TestCase):
    def setUp(self):
        self.cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)

    def test_every_call_reads_fresh_values_in_exact_scalar_order(self):
        read = sampler.CsrSampler(self.cpu)
        for values in ((0, 0, 0), (8, 0x100, 0x84004100), (0x1880, 0x888, 0x84004101), (0, 0, 0)):
            for register, value in zip(sampler.REGISTERS, values): self.cpu.reg_write(register, value)
            self.assertEqual(read(), scalar(self.cpu))

    def test_context_restoration_is_not_hidden_by_a_value_cache(self):
        read = sampler.CsrSampler(self.cpu)
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
        saved = self.cpu.context_save()
        first = read()
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        self.assertEqual(read(), scalar(self.cpu))
        self.assertNotEqual(read(), first)
        self.cpu.context_restore(saved)
        self.assertEqual(read(), first)

    def test_reading_does_not_mutate_memory_or_architectural_registers(self):
        self.cpu.mem_map(0x1000, 4096)
        self.cpu.mem_write(0x1000, b'\xa5' * 4096)
        registers = [getattr(r, 'UC_RISCV_REG_X' + str(index)) for index in range(1, 32)]
        registers += [r.UC_RISCV_REG_PC, *sampler.REGISTERS]
        for index, register in enumerate(registers[:31]): self.cpu.reg_write(register, 0xa100 + index)
        before = tuple(self.cpu.reg_read(register) for register in registers)
        read = sampler.CsrSampler(self.cpu)
        for _ in range(100): read()
        self.assertEqual(tuple(self.cpu.reg_read(register) for register in registers), before)
        self.assertEqual(bytes(self.cpu.mem_read(0x1000, 4096)), b'\xa5' * 4096)

    def test_backend_errors_are_not_replaced_by_old_values(self):
        read = sampler.CsrSampler(self.cpu)
        read._read = lambda *args: UC_ERR_ARG
        with self.assertRaises(UcError) as caught: read()
        self.assertEqual(caught.exception.errno, UC_ERR_ARG)

    def test_unknown_version_or_wrong_architecture_mode_is_rejected(self):
        with patch.object(sampler.unicorn, '__version__', 'unknown'):
            with self.assertRaises(RuntimeError): sampler.CsrSampler(self.cpu)
        with self.assertRaises(RuntimeError): sampler.CsrSampler(Uc(UC_ARCH_RISCV, UC_MODE_RISCV64))

    def test_native_patch_version_and_loaded_API_signature_are_checked(self):
        with patch.object(sampler.unicorn, 'uc_version', return_value=(2, 1, 0x020103ff)):
            with self.assertRaises(RuntimeError): sampler.CsrSampler(self.cpu)
        with patch.object(sampler.binding.uclib, 'uc_reg_read_batch', Mock(argtypes=(), restype=ctypes.c_int)):
            with self.assertRaises(RuntimeError): sampler.CsrSampler(self.cpu)
        read = sampler.CsrSampler(self.cpu)
        self.assertIs(read._library, sampler.binding.uclib)

    def test_handle_change_and_cross_thread_use_fail_before_native_read(self):
        read = sampler.CsrSampler(self.cpu)
        original = self.cpu._uch
        try:
            for changed in (ctypes.c_void_p(), ctypes.c_void_p(original.value + 8)):
                self.cpu._uch = changed
                with self.assertRaises(RuntimeError): read()
        finally: self.cpu._uch = original
        errors = []

        def other_thread():
            try: read()
            except Exception as error: errors.append(error)

        worker = threading.Thread(target=other_thread)
        worker.start()
        worker.join()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)

    def test_actual_CSR_instruction_and_explicit_hook_transcripts_match(self):
        assembly = b'''\n.option norvc\n.text\n.globl sample\nsample:\ncsrrci t0,mstatus,8\ncsrw mie,a1\ncsrw mtvec,a2\ncsrw mstatus,a0\nfence iorw,iorw\nret\n'''
        built = subprocess.run(['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
            '-x', 'assembler', '-c', '-o', '-', '-'], input=assembly, capture_output=True, timeout=30)
        self.assertEqual(built.returncode, 0, built.stderr)
        code = ELFFile(io.BytesIO(built.stdout)).get_section_by_name('.text').data()

        def execute(batched, injected):
            cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
            cpu.mem_map(0x1000, 8192)
            cpu.mem_write(0x1000, code)
            for register, value in ((r.UC_RISCV_REG_RA, 0x2000), (r.UC_RISCV_REG_A0, 8),
                (r.UC_RISCV_REG_A1, 0x800), (r.UC_RISCV_REG_A2, 0x84004100),
                (r.UC_RISCV_REG_MSTATUS, 0x1880)):
                cpu.reg_write(register, value)
            read = sampler.CsrSampler(cpu) if batched else lambda: scalar(cpu)
            transcript = []

            def observe(cpu, pc, size, unused):
                if injected and pc == 0x1008: cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
                transcript.append((pc, read()))

            cpu.hook_add(UC_HOOK_CODE, observe)
            cpu.emu_start(0x1000, 0x2000, count=100, timeout=1000000)
            self.assertEqual(cpu.reg_read(r.UC_RISCV_REG_PC), 0x2000)
            self.assertEqual(len(transcript), 6)
            self.assertGreaterEqual(len({state for _, state in transcript}), 3)
            self.assertEqual(scalar(cpu), (8, 0x800, 0x84004100))
            return transcript, scalar(cpu), bytes(cpu.mem_read(0x1000, len(code)))

        for injected in (False, True):
            self.assertEqual(execute(False, injected), execute(True, injected))


if __name__ == '__main__': unittest.main()
