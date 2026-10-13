"""Observe the new cold snapshot/lease without seeding native ownership state."""
from unicorn import riscv_const as r
from test_provider_plan_native import ProviderRequest
from test_cold_packet_native import GETTER
from test_cold_page_native import GETTER as PAGE_GETTER
from test_bootstrap_native import ADM
from emulation_layout import STATE
from test_firmware_memory_layout import STACK_TOPS
from emulation_layout import CODE
from unicorn import UC_HOOK_CODE


class ColdProviderRequest(ProviderRequest):
    def __init__(self, *args, **kwargs):
        self.cold_request = False
        self.cold_getters = 0
        self.cold_count = 0
        self.cold_txbuf = False
        self.cold_rx_event = False
        self.indication_fault = self.indication_injected = False
        self.tx_fault = None
        self.tx_injected = False
        self.descriptor_fault = self.descriptor_injected = False
        super().__init__(*args, **kwargs)

    def message(self, words, **kwargs):
        self.cold_request = len(words) == 20 and words[2] == 0x3253434e
        self.cold_txbuf = self.cold_request and words[12] == 21
        self.cold_rx_event = self.cold_request and words[12] == 22
        self.cold_count = words[13] if self.cold_request and words[12] == 1 and words[11] in (0x10, 0x12, 0x15, 0x16, 0x17, 0x18) else 0
        self.cold_getter = 0x8400bb10 if self.cold_request and words[11] == 0x18 else (
            PAGE_GETTER if self.cold_request and words[11] in (0x15, 0x16, 0x17) else GETTER)
        if self.cold_request and words[12] == 4 and words[11] in (0x35, 0x37):
            self.cold_count = 512 if words[11] == 0x35 else 1024
            self.cold_getter = self.descriptor.symbols[
                'npu_emulation_descriptor_status0' if words[11] == 0x35 else 'npu_emulation_descriptor_status2']
        if self.cold_txbuf or self.cold_rx_event:
            self.cold_count = 16 * 53260
            self.cold_getter = self.rv.symbols['npu_cold_txbuf_recipe']
        self.cold_getters = 0
        previous_probe = self.probing
        # This selects the existing RX observer, not a native admission bypass.
        self.probing = bool(self.cold_count) and not (self.cold_txbuf or self.cold_rx_event)
        observers = []
        if self.cold_txbuf or self.cold_rx_event:
            self.cpu.hook_del(self.instruction_hook)
            self.cpu.hook_del(self.callback_hook)
            observers = [
                self.cpu.hook_add(UC_HOOK_CODE, self.code_hook, begin=CODE, end=CODE + len(self.code) - 1),
                self.cpu.hook_add(UC_HOOK_CODE, self.native_callback, begin=CODE, end=CODE + len(self.code) - 1),
                self.cpu.hook_add(UC_HOOK_CODE, self.code_hook, begin=self.cold_getter, end=self.cold_getter),
            ]
        try:
            reply = super().message(words, **kwargs)
            if self.cold_txbuf:
                reply['api21_recipe_entries'] = self.cold_getters
            if self.cold_rx_event:
                reply['api22_prior_recipe_entries'] = self.cold_getters
            return reply
        finally:
            if observers:
                for hook in observers:
                    self.cpu.hook_del(hook)
                self.instruction_hook = self.cpu.hook_add(UC_HOOK_CODE, self.code_hook)
                self.callback_hook = self.cpu.hook_add(UC_HOOK_CODE, self.native_callback)
            self.cold_request = False
            self.cold_txbuf = False
            self.cold_rx_event = False
            self.probing = previous_probe

    def code_hook(self, cpu, pc, size, data):
        if self.cold_request and pc == 0x8400dd82:
            state = self.rv.symbols['npu_emulation_cold_setup_state']
            assert self.get32(state + 4) == self.get32(ADM + 4) == 1
            assert cpu.reg_read(r.UC_RISCV_REG_A1) in (0, 2, 5, 6, 7, 8)
            assert cpu.reg_read(r.UC_RISCV_REG_A0) == self.cold_count
        super().code_hook(cpu, pc, size, data)

    def write_hook(self, cpu, access, address, size, value, data):
        if self.descriptor_fault and not self.descriptor_injected and self.cold_request:
            offset = 0x26044 if self.descriptor_fault == 7 else 0x6024
            if address == self.get32(0x3e9030fc) + offset and size == 4 and value == 0x80000000:
                self.descriptor_injected = True
                self.put32(STATE + 16, 1)
        if not self.tx_injected and ((self.tx_fault == 'register' and address == 0x1fc08030) or
                                     (self.tx_fault == 'token' and address == 0x3e900bc0)):
            self.tx_injected = True
            self.put32(STATE + 16, 1)
        if self.indication_fault and not self.indication_injected:
            plan = self.binding.symbols['npu_emulation_indication_plan']
            if address == self.get32(plan) + 4 and size == 4 and value == 0xe0000000:
                self.indication_injected = True
                self.put32(STATE + 16, 1)
        super().write_hook(cpu, access, address, size, value, data)

    def native_callback(self, cpu, pc, size, data):
        if not self.cold_request:
            return super().native_callback(cpu, pc, size, data)
        if pc not in (0x840101a6, 0x8400ff34, 0x8400fe34, 0x8400fdc4, 0x8400fc16, 0x8400fdda, 0x84010164, 0x8400fbca, 0x8400fbb4):
            return
        self.callback_entries.append(hex(pc))
        snapshot = cpu.reg_read(r.UC_RISCV_REG_A0)
        state = self.rv.symbols['npu_emulation_cold_setup_state']
        assert STACK_TOPS[0] - 0x4000 <= snapshot <= STACK_TOPS[0] - 12
        assert snapshot != self.request_alias
        assert bytes(cpu.mem_read(snapshot, 12)) == bytes(cpu.mem_read(state + 36, 12))
        assert self.get32(state + 4) == self.get32(ADM + 4) == 1

    def run(self, start, stops):
        if not self.cold_request or not self.cold_count or (self.cold_count > 1536 and not (self.cold_txbuf or self.cold_rx_event)):
            return super().run(start, stops)
        pc, chunks = start, 0
        while True:
            pc = super().run(pc, list(stops) + [self.cold_getter])
            chunks += 1
            assert chunks <= self.cold_count + 3, 'cold-wire-getter-progress'
            if pc != self.cold_getter:
                return pc
            self.cold_getters += 1
