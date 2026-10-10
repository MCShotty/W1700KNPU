"""Observe the new cold snapshot/lease without seeding native ownership state."""
from unicorn import riscv_const as r
from test_provider_plan_native import ProviderRequest
from test_cold_packet_native import GETTER
from test_bootstrap_native import ADM
from test_firmware_memory_layout import STACK_TOPS


class ColdProviderRequest(ProviderRequest):
    def __init__(self, *args, **kwargs):
        self.cold_request = False
        self.cold_getters = 0
        self.cold_count = 0
        super().__init__(*args, **kwargs)

    def message(self, words, **kwargs):
        self.cold_request = len(words) == 20 and words[2] == 0x3253434e
        self.cold_count = words[13] if self.cold_request and words[12] == 1 and words[11] in (0x10, 0x12) else 0
        self.cold_getters = 0
        previous_probe = self.probing
        # This selects the existing RX observer, not a native admission bypass.
        self.probing = bool(self.cold_count)
        try:
            return super().message(words, **kwargs)
        finally:
            self.cold_request = False
            self.probing = previous_probe

    def code_hook(self, cpu, pc, size, data):
        if self.cold_request and pc == 0x8400dd82:
            state = self.rv.symbols['npu_emulation_cold_setup_state']
            assert self.get32(state + 4) == self.get32(ADM + 4) == 1
            assert cpu.reg_read(r.UC_RISCV_REG_A1) in (0, 2)
            assert cpu.reg_read(r.UC_RISCV_REG_A0) == self.cold_count
        super().code_hook(cpu, pc, size, data)

    def native_callback(self, cpu, pc, size, data):
        if not self.cold_request:
            return super().native_callback(cpu, pc, size, data)
        if pc not in (0x840101a6, 0x8400ff34, 0x8400fe34):
            return
        self.callback_entries.append(hex(pc))
        snapshot = cpu.reg_read(r.UC_RISCV_REG_A0)
        state = self.rv.symbols['npu_emulation_cold_setup_state']
        assert STACK_TOPS[0] - 0x4000 <= snapshot <= STACK_TOPS[0] - 12
        assert snapshot != self.request_alias
        assert bytes(cpu.mem_read(snapshot, 12)) == bytes(cpu.mem_read(state + 36, 12))
        assert self.get32(state + 4) == self.get32(ADM + 4) == 1

    def run(self, start, stops):
        if not self.cold_request or not 1 <= self.cold_count <= 1536:
            return super().run(start, stops)
        pc, chunks = start, 0
        while True:
            pc = super().run(pc, list(stops) + [GETTER])
            chunks += 1
            assert chunks <= self.cold_count + 3, 'cold-wire-getter-progress'
            if pc != GETTER:
                return pc
            self.cold_getters += 1
