"""Real Unicorn write routing without retaining completed per-call traces."""
import gc
import struct
import unittest
import weakref

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32
from unicorn.riscv_const import UC_RISCV_REG_A0, UC_RISCV_REG_A1, UC_RISCV_REG_A2

from test_rro_lifetime_native import RroWriteObserver


class Host:
    def __init__(self):
        self.cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        self.cpu.mem_map(0x1000, 0x2000)
        self.cpu.mem_write(0x1000, struct.pack('<II', 0x00b52023, 0x00c52223))
        self.cpu.reg_write(UC_RISCV_REG_A0, 0x2000)
        self.cpu.reg_write(UC_RISCV_REG_A1, 0x11223344)
        self.cpu.reg_write(UC_RISCV_REG_A2, 0xaabbccdd)

    def call(self, address):
        self.cpu.emu_start(address, address + 8, count=2, timeout=1000000)
        return 7


class Trace:
    def __init__(self):
        self.writes = []

    def write(self, cpu, access, address, size, value, unused):
        self.writes.append((address, size, value))


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.host = Host()
        self.observer = RroWriteObserver(self.host.cpu)

    def tearDown(self):
        self.observer.close()

    def test_every_write_is_routed_once_in_order(self):
        first, second = Trace(), Trace()
        for trace in (first, second):
            self.assertEqual(self.observer.call(self.host, trace, 0x1000), 7)
            self.assertIsNone(self.observer.trace)
            self.assertEqual(trace.writes, [(0x2000, 4, 0x11223344), (0x2004, 4, 0xaabbccdd)])
        self.assertEqual(len(first.writes), 2)

    def test_completed_traces_are_released_without_cyclic_collection(self):
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            for _ in range(128):
                trace = Trace()
                reference = weakref.ref(trace)
                self.observer.call(self.host, trace, 0x1000)
                del trace
                self.assertIsNone(reference())
        finally:
            if was_enabled:
                gc.enable()

    def test_unscoped_guest_write_is_not_silently_dropped(self):
        with self.assertRaisesRegex(AssertionError, 'RRO-write-outside-observed-call'):
            self.host.call(0x1000)
        self.assertIsNone(self.observer.trace)

    def test_callback_error_propagates_and_clears_active_trace(self):
        class FailingTrace:
            def write(self, *arguments):
                raise ValueError('intended-observer-error')
        with self.assertRaisesRegex(ValueError, 'intended-observer-error'):
            self.observer.call(self.host, FailingTrace(), 0x1000)
        self.assertIsNone(self.observer.trace)

    def test_nested_calls_fail_before_entering_guest(self):
        observer, host = self.observer, self.host
        class NestedTrace:
            def write(self, *arguments):
                observer.call(host, Trace(), 0x1000)
        with self.assertRaisesRegex(AssertionError, 'nested-RRO-write-observer'):
            self.observer.call(self.host, NestedTrace(), 0x1000)
        self.assertIsNone(self.observer.trace)

    def test_closed_or_different_engine_cannot_be_observed(self):
        other = Host()
        with self.assertRaises(AssertionError):
            self.observer.call(other, Trace(), 0x1000)
        self.observer.close()
        with self.assertRaises(AssertionError):
            self.observer.call(self.host, Trace(), 0x1000)


if __name__ == '__main__':
    unittest.main()
