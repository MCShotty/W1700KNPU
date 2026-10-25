"""Same-engine read-API equivalence, not native NPU lifetime or throughput proof."""
import ctypes
import gc
import io
import json
import os
from pathlib import Path
import subprocess
import threading
import unittest
from unittest.mock import Mock, patch
import weakref

from elftools.elf.elffile import ELFFile
from unicorn import (Uc, UcError, UC_ARCH_RISCV, UC_ERR_ARG, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MODE_RISCV32,
                     UC_MODE_RISCV64, riscv_const as r)
import native_read_api as adapter


class NativeReadAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        receipt_path = os.environ.get('NPU_READ_API_BUILD_RECEIPT')
        if not receipt_path:
            raise RuntimeError('explicit compiled native-reader receipt is required')
        cls.receipt = json.loads(Path(receipt_path).read_bytes())
        cls.path = Path(cls.receipt['extension']['path'])
        cls.digest = cls.receipt['extension']['sha256']
        cls.extension = adapter.load_extension(cls.path, cls.digest)

    def setUp(self):
        self.cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        self.original = self.cpu.reg_read
        self.reader = adapter.install(self.cpu, self.extension)

    def test_every_integer_register_and_csr_is_fresh(self):
        registers = tuple(getattr(r, 'UC_RISCV_REG_X' + str(index)) for index in range(32))
        registers += (r.UC_RISCV_REG_PC, *adapter.REGISTERS)
        for seed in (0, 0xffffffff, 0x81234567, 0):
            for index, register in enumerate(registers):
                self.cpu.reg_write(register, (seed + 4 * index) & 0xffffffff)
                self.assertEqual(self.reader(register), self.original(register))
            self.assertEqual(self.reader.csrs(), tuple(self.original(register) for register in adapter.REGISTERS))

    def test_context_restore_is_not_hidden_by_old_values(self):
        self.cpu.reg_write(r.UC_RISCV_REG_SP, 0x80102030)
        before = self.cpu.context_save()
        self.cpu.reg_write(r.UC_RISCV_REG_SP, 0x12345678)
        self.assertEqual(self.reader(r.UC_RISCV_REG_SP), 0x12345678)
        self.cpu.context_restore(before)
        self.assertEqual(self.reader(r.UC_RISCV_REG_SP), 0x80102030)

    def test_observation_changes_no_register_or_memory(self):
        self.cpu.mem_map(0x1000, 4096)
        self.cpu.mem_write(0x1000, b'\xa5' * 4096)
        for index in range(1, 32):
            self.cpu.reg_write(getattr(r, 'UC_RISCV_REG_X' + str(index)), index * 0x10001)
        registers = [getattr(r, 'UC_RISCV_REG_X' + str(index)) for index in range(32)]
        registers += [r.UC_RISCV_REG_PC, *adapter.REGISTERS]
        before = [self.original(register) for register in registers]
        for _ in range(30):
            for register in registers:
                self.reader(register)
            self.reader.csrs()
        self.assertEqual(before, [self.original(register) for register in registers])
        self.assertEqual(bytes(self.cpu.mem_read(0x1000, 4096)), b'\xa5' * 4096)

    def test_keywords_auxiliary_and_nonexact_integers_keep_original_path(self):
        self.cpu.reg_write(r.UC_RISCV_REG_SP, 0xa0000000)
        for call in (lambda: self.reader(reg_id=r.UC_RISCV_REG_SP),
                     lambda: self.reader(r.UC_RISCV_REG_SP, None),
                     lambda: self.reader(r.UC_RISCV_REG_SP, aux=None)):
            self.assertEqual(call(), self.original(r.UC_RISCV_REG_SP))
        self.assertEqual(self.reader(True), self.original(True))

    def test_handle_change_and_null_handle_fail_before_native_access(self):
        original = self.cpu._uch
        try:
            for value in (ctypes.c_void_p(), ctypes.c_void_p(original.value + 8)):
                self.cpu._uch = value
                with self.assertRaises(RuntimeError): self.reader(r.UC_RISCV_REG_SP)
                with self.assertRaises(RuntimeError): self.reader.csrs()
                with self.assertRaises(RuntimeError): self.reader.u32(0x1000)
        finally:
            self.cpu._uch = original

    def test_cross_thread_calls_fail_without_reading_another_engine(self):
        errors = []

        def other_thread():
            for call in (lambda: self.reader(r.UC_RISCV_REG_SP), self.reader.csrs,
                         lambda: self.reader.u32(0x1000)):
                try: call()
                except Exception as error: errors.append(error)

        thread = threading.Thread(target=other_thread)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 3)
        self.assertTrue(all(isinstance(error, RuntimeError) for error in errors))

    def test_reinitialization_and_duplicate_installation_are_rejected(self):
        with self.assertRaises(RuntimeError): adapter.install(self.cpu, self.extension)
        with self.assertRaises(RuntimeError): self.reader.__init__()
        adapter.uninstall(self.cpu, self.reader)
        self.assertEqual(self.cpu.reg_read, self.original)
        with self.assertRaises(RuntimeError): adapter.uninstall(self.cpu, self.reader)

    def test_cycle_collection_releases_the_engine_owner(self):
        cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        reader = adapter.install(cpu, self.extension)
        reference = weakref.ref(cpu)
        del reader, cpu
        gc.collect()
        self.assertIsNone(reference())

    def test_backend_errors_are_exact_and_no_previous_value_is_returned(self):
        read_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
        batch_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                                     ctypes.POINTER(ctypes.c_void_p), ctypes.c_int)
        read = read_type(lambda *args: UC_ERR_ARG)
        batch = batch_type(lambda *args: UC_ERR_ARG)
        reader = self.extension.Reader(self.cpu, self.original, UcError,
            ctypes.cast(read, ctypes.c_void_p).value, ctypes.cast(batch, ctypes.c_void_p).value, adapter.REGISTERS)
        for call in (lambda: reader(r.UC_RISCV_REG_SP), reader.csrs):
            with self.assertRaises(UcError) as caught: call()
            self.assertEqual(caught.exception.errno, UC_ERR_ARG)

    def test_invalid_registers_preserve_scalar_error_behavior(self):
        for register in (-1, 0x7fffffff, 1 << 64):
            outcomes = []
            for read in (self.original, self.reader):
                try: outcomes.append(('value', read(register)))
                except Exception as error:
                    outcomes.append((type(error), getattr(error, 'errno', None), str(error)))
            self.assertEqual(outcomes[0], outcomes[1])

    def test_wrong_mode_version_signature_or_representation_is_rejected(self):
        with self.assertRaises(RuntimeError): adapter.install(Uc(UC_ARCH_RISCV, UC_MODE_RISCV64), self.extension)
        cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        import npu_csr_sampler
        with patch.object(npu_csr_sampler.unicorn, '__version__', 'unknown'):
            with self.assertRaises(RuntimeError): adapter.install(cpu, self.extension)
        with patch.object(adapter.binding.uclib, 'uc_reg_read', Mock(argtypes=(), restype=ctypes.c_int)):
            with self.assertRaises(RuntimeError): adapter.install(cpu, self.extension)
        with patch.object(adapter.binding.uclib, 'uc_mem_read', Mock(argtypes=(), restype=ctypes.c_int)):
            with self.assertRaises(RuntimeError): adapter.install(cpu, self.extension)
        with patch.object(cpu, '_select_reg_class', return_value=ctypes.c_uint32):
            with self.assertRaises(RuntimeError): adapter.install(cpu, self.extension)

    def test_extension_digest_and_loaded_identity_are_enforced(self):
        with self.assertRaises(RuntimeError): adapter.load_extension(self.path, '0' * 64)
        self.assertIs(adapter.load_extension(self.path, self.digest), self.extension)
        with patch.object(self.extension, '_verified_sha256', '0' * 64):
            with self.assertRaises(RuntimeError): adapter.load_extension(self.path, self.digest)
        with patch.object(self.extension, 'API_VERSION', 1):
            with self.assertRaises(RuntimeError): adapter.load_extension(self.path, self.digest)

    def test_words_are_little_endian_unaligned_and_fresh(self):
        self.cpu.mem_map(0x1000, 8192)
        for payload in (bytes(range(256)) * 32, b'\xff' * 8192, bytes(8192)):
            self.cpu.mem_write(0x1000, payload)
            for offset in (0, 1, 2, 3, 255, 4093, 4094, 4095, 4096, 8188):
                expected = int.from_bytes(self.cpu.mem_read(0x1000 + offset, 4), 'little')
                self.assertEqual(self.reader.u32(0x1000 + offset), expected)
        self.cpu.mem_unmap(0x1000, 8192)
        with self.assertRaises(UcError): self.reader.u32(0x1000)
        self.cpu.mem_map(0x1000, 8192)
        self.cpu.mem_write(0x1000, b'\x78\x56\x34\x12')
        self.assertEqual(self.reader.u32(0x1000), 0x12345678)

    def test_word_boundaries_preserve_backend_errors_without_partial_values(self):
        self.cpu.mem_map(0x1000, 4096)
        self.cpu.mem_write(0x1000, b'\xa5' * 4096)
        for address in (0, 0xffd, 0xfff, 0x1ffd, 0x1fff, 0x2000, 0xfffffffc):
            errors = []
            for read in (lambda a: int.from_bytes(self.cpu.mem_read(a, 4), 'little'), self.reader.u32):
                with self.assertRaises(UcError) as caught: read(address)
                errors.append((caught.exception.errno, str(caught.exception)))
            self.assertEqual(errors[0], errors[1])
        self.assertEqual(self.reader.u32(0x1ffc), 0xa5a5a5a5)

    def test_word_arguments_are_explicitly_strict(self):
        class Integer(int): pass

        for argument in (True, False, 1.0, '4096', None, Integer(4096), object()):
            with self.assertRaises(TypeError): self.reader.u32(argument)
        for argument in (-1, 1 << 64, (1 << 64) - 3, (1 << 64) - 1):
            with self.assertRaises(OverflowError): self.reader.u32(argument)
        with self.assertRaises(TypeError): self.reader.u32()
        with self.assertRaises(TypeError): self.reader.u32(address=4096)
        with self.assertRaises(TypeError): self.reader.u32(4096, 4)

    def test_word_read_has_no_guest_hook_or_memory_side_effect(self):
        self.cpu.mem_map(0x1000, 4096)
        self.cpu.mem_write(0x1000, b'\x78\x56\x34\x12' * 1024)
        events = []
        self.cpu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, lambda *args: events.append(args[1:]))
        before = self.cpu.context_save()
        for _ in range(50): self.assertEqual(self.reader.u32(0x1001), 0x78123456)
        self.assertEqual(events, [])
        self.assertEqual(bytes(self.cpu.mem_read(0x1000, 4096)), b'\x78\x56\x34\x12' * 1024)
        registers = [getattr(r, 'UC_RISCV_REG_X' + str(index)) for index in range(32)]
        registers += [r.UC_RISCV_REG_PC, *adapter.REGISTERS]
        current = [self.original(register) for register in registers]
        self.cpu.context_restore(before)
        self.assertEqual(current, [self.original(register) for register in registers])

    def test_word_backend_error_and_unbound_memory_are_not_values(self):
        read = adapter.binding.uclib.uc_reg_read
        batch = adapter.binding.uclib.uc_reg_read_batch
        memory_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint64,
                                       ctypes.c_void_p, ctypes.c_uint64)

        def fail(handle, address, target, count):
            ctypes.memset(target, 0xa5, count)
            return UC_ERR_ARG

        memory = memory_type(fail)
        arguments = (self.cpu, self.original, UcError, ctypes.cast(read, ctypes.c_void_p).value,
                     ctypes.cast(batch, ctypes.c_void_p).value, adapter.REGISTERS)
        unbound = self.extension.Reader(*arguments)
        with self.assertRaises(RuntimeError): unbound.u32(0x1000)
        reader = self.extension.Reader(*arguments, ctypes.cast(memory, ctypes.c_void_p).value)
        for _ in range(2):
            with self.assertRaises(UcError) as caught: reader.u32(0x1000)
            self.assertEqual(caught.exception.errno, UC_ERR_ARG)

    def test_word_instruction_transcripts_include_current_guest_and_host_writes(self):
        # lw a0,0(a1); addi a0,a0,1; sw a0,0(a1); ret
        code = bytes.fromhex('03a505001305150023a0a50067800000')

        def execute(native):
            cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
            cpu.mem_map(0x1000, 8192)
            cpu.mem_write(0x1000, code)
            cpu.mem_write(0x1800, b'\x00' * 4)
            cpu.reg_write(r.UC_RISCV_REG_RA, 0x2000)
            cpu.reg_write(r.UC_RISCV_REG_A1, 0x1800)
            reader = adapter.install(cpu, self.extension) if native else None
            word = reader.u32 if native else lambda a: int.from_bytes(cpu.mem_read(a, 4), 'little')
            events = []

            def instruction(cpu, pc, size, unused):
                if pc == 0x1000: cpu.mem_write(0x1800, b'\xfe\xff\xff\xff')
                events.append(('code', pc, word(0x1800), word(pc)))

            def access(cpu, kind, address, size, value, unused):
                events.append(('memory', kind, address, size, value, word(0x1800)))

            cpu.hook_add(UC_HOOK_CODE, instruction)
            cpu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, access)
            cpu.emu_start(0x1000, 0x2000, count=100, timeout=1000000)
            self.assertEqual(cpu.reg_read(r.UC_RISCV_REG_PC), 0x2000)
            self.assertEqual(word(0x1800), 0xffffffff)
            return events, bytes(cpu.mem_read(0x1800, 4)), cpu.reg_read(r.UC_RISCV_REG_A0)

        self.assertEqual(execute(False), execute(True))

    def test_actual_instruction_hook_transcripts_match_with_dynamic_injection(self):
        assembly = b'''.option norvc\n.text\n.globl sample\nsample:\naddi sp,sp,-16\ncsrrci t0,mstatus,8\ncsrw mie,a1\ncsrw mtvec,a2\ncsrw mstatus,a0\naddi sp,sp,16\nret\n'''
        built = subprocess.run(['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
            '-x', 'assembler', '-c', '-o', '-', '-'], input=assembly, capture_output=True, timeout=30)
        self.assertEqual(built.returncode, 0, built.stderr)
        code = ELFFile(io.BytesIO(built.stdout)).get_section_by_name('.text').data()

        def execute(native, injected):
            cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
            cpu.mem_map(0x1000, 8192)
            cpu.mem_write(0x1000, code)
            for register, value in ((r.UC_RISCV_REG_RA, 0x2000), (r.UC_RISCV_REG_SP, 0x2800),
                (r.UC_RISCV_REG_A0, 8), (r.UC_RISCV_REG_A1, 0x800),
                (r.UC_RISCV_REG_A2, 0x84004100), (r.UC_RISCV_REG_MSTATUS, 0x1880)):
                cpu.reg_write(register, value)
            reader = adapter.install(cpu, self.extension) if native else cpu.reg_read
            sample = reader.csrs if native else lambda: tuple(reader(register) for register in adapter.REGISTERS)
            transcript = []

            def observe(cpu, pc, size, unused):
                if injected and pc == 0x100c: cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
                transcript.append((pc, cpu.reg_read(r.UC_RISCV_REG_SP), sample()))

            cpu.hook_add(UC_HOOK_CODE, observe)
            cpu.emu_start(0x1000, 0x2000, count=100, timeout=1000000)
            self.assertEqual(cpu.reg_read(r.UC_RISCV_REG_PC), 0x2000)
            self.assertEqual(len(transcript), 7)
            return transcript, cpu.reg_read(r.UC_RISCV_REG_SP), sample(), bytes(cpu.mem_read(0x1000, len(code)))

        for injected in (False, True): self.assertEqual(execute(False, injected), execute(True, injected))


if __name__ == '__main__':
    unittest.main()
