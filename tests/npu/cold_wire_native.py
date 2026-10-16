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
import test_bootstrap_v2_composition as composition


class ColdProviderRequest(ProviderRequest):
    def __init__(self, *args, **kwargs):
        self.cold_request = False
        self.cold_getters = 0
        self.cold_count = 0
        self.cold_callback_count = 0
        self.cold_checkpoints = ()
        self.cold_checkpoint_hits = {}
        self.cold_txbuf = False
        self.cold_rx_event = False
        self.cold_desc10 = False
        self.cold_pcie = False
        self.cold_tail = False
        self.indication_fault = self.indication_injected = False
        self.tx_fault = None
        self.tx_injected = False
        self.descriptor_fault = self.descriptor_injected = False
        super().__init__(*args, **kwargs)

    def message(self, words, **kwargs):
        self.cold_request = len(words) == 20 and words[2] == 0x3253434e
        self.cold_txbuf = self.cold_request and words[12] == 21
        self.cold_rx_event = self.cold_request and words[12] == 22
        self.cold_desc10 = self.cold_request and words[11:13] == [0x1a, 1]
        self.cold_pcie = self.cold_request and words[11:13] == [0x1a, 0]
        self.cold_tail = self.cold_request and words[12] == 0 and words[11] in (0x10, 0x12, 0x1f)
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
        if self.cold_desc10:
            self.cold_count = 64 * 53260
            self.cold_getter = self.desc10.symbols['npu_cold_txdone_recipe']
        if self.cold_pcie or self.cold_tail:
            self.cold_count = 64 * 53260
            self.cold_getter = self.desc10.symbols['npu_cold_txdone_memory_live']
        self.cold_callback_count = words[13] if self.cold_request and words[12] == 1 else self.cold_count
        self.cold_checkpoints = (self.cold_getter,)
        if self.cold_desc10 or self.cold_pcie or self.cold_tail:
            # Prior effect verification runs before the first DESC10 recipe.
            self.cold_checkpoints += (self.rv.symbols['npu_cold_txbuf_recipe'],)
        self.cold_checkpoint_hits = {hex(pc): 0 for pc in self.cold_checkpoints}
        self.cold_getters = 0
        previous_probe = self.probing
        # This selects the existing RX observer, not a native admission bypass.
        self.probing = bool(self.cold_count) and not (self.cold_txbuf or self.cold_rx_event or self.cold_desc10 or self.cold_pcie or self.cold_tail)
        observers = []
        if self.cold_txbuf or self.cold_rx_event or self.cold_desc10 or self.cold_pcie or self.cold_tail:
            self.cpu.hook_del(self.instruction_hook)
            self.cpu.hook_del(self.callback_hook)
            observers = [
                self.cpu.hook_add(UC_HOOK_CODE, self.code_hook, begin=CODE, end=CODE + len(self.code) - 1),
                self.cpu.hook_add(UC_HOOK_CODE, self.native_callback, begin=CODE, end=CODE + len(self.code) - 1),
            ]
            observers += [self.cpu.hook_add(UC_HOOK_CODE, self.code_hook, begin=pc, end=pc)
                          for pc in self.cold_checkpoints]
        try:
            reply = super().message(words, **kwargs)
            if self.cold_txbuf:
                reply['api21_recipe_entries'] = self.cold_getters
            if self.cold_rx_event:
                reply['api22_prior_recipe_entries'] = self.cold_getters
            if self.cold_desc10:
                reply['desc10_recipe_entries'] = self.cold_getters
                reply['desc10_checkpoints'] = self.cold_checkpoint_hits.copy()
            if self.cold_pcie:
                reply['pcie_final_memory_entries'] = self.cold_getters
            if self.cold_tail:
                reply['pcie_tail_final_memory_entries'] = self.cold_getters
                reply['pcie_tail_checkpoints'] = self.cold_checkpoint_hits.copy()
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
            self.cold_desc10 = False
            self.cold_pcie = False
            self.cold_tail = False
            self.probing = previous_probe

    def code_hook(self, cpu, pc, size, data):
        if self.cold_request and pc == 0x8400dd82:
            assert not getattr(self, 'cold_tail', False), 'unexpected-tail-allocator'
            state = self.rv.symbols['npu_emulation_cold_setup_state']
            assert self.get32(state + 4) == self.get32(ADM + 4) == 1
            assert cpu.reg_read(r.UC_RISCV_REG_A1) in (0, 2, 5, 6, 7, 8, 10)
            assert cpu.reg_read(r.UC_RISCV_REG_A0) == self.cold_callback_count
            if self.cold_desc10:
                assert cpu.reg_read(r.UC_RISCV_REG_A1) == 10
                owner = self.desc10.symbols['npu_emulation_desc10_state']
                assert [self.get32(owner + 4 * i) for i in range(4)] == [0x31445443, 1, 0, 1]
                assert self.get32(self.desc10.symbols['npu_emulation_desc10_running']) == 1
                self.executions[pc] += 1
                # Only the parking-only observer's no-DESC assertion is bypassed.
                super(composition.Composed, self).code_hook(cpu, pc, size, data)
                return
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

    def register_model(self, address, write):
        if getattr(self, 'cold_tail', False):
            setup = self.rv.symbols['npu_emulation_cold_setup_state']
            base, tx2 = self.get32(setup + 48), self.get32(setup + 388)
            if base == 0x20000000 and tx2 - base in (0xd4450, 0xd8450):
                stores = (base + 0xd4588, tx2 + 0x118, base + 0xd45a8, base + 0xd45b8,
                          base + 0xd45c8, base + 0xa048, base + 0xd4598)
                allowed = stores if write else tuple(cell + delta for cell in stores for delta in (-4, 0, 4))
                if address in allowed:
                    return 'Selected PCIe-tail BAR count/neighbor storage; no physical MMIO or DMA effect proof'
        return super().register_model(address, write)

    def observe_tx_write(self, cpu, address, size, value):
        if not (self.cold_request and self.cold_desc10):
            return super().observe_tx_write(cpu, address, size, value)
        owner = self.desc10.symbols['npu_emulation_desc10_state']
        words = [self.get32(owner + 4 * i) for i in range(16)]
        assert words[:4] == [0x31445443, 1, 0, 1]
        assert words[4] == words[5] == words[6] + 1
        assert words[7:11] == [512, 512, 512, 1]
        assert self.get32(self.desc10.symbols['npu_emulation_desc10_running']) == 1
        assert self.get32(self.allocator_rv.symbols['npu_emulation_callback_guarded']) == 1
        assert not cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        stores = {
            self.desc10.symbols['npu_emulation_desc10_4aac_store']: 0,
            self.desc10.symbols['npu_emulation_desc10_4ad2_store']: 3,
        }
        pc = cpu.reg_read(r.UC_RISCV_REG_PC)
        assert pc in stores and size == 2 and value == stores[pc]
        assert words[13:16] == [value, address, size]
        # Keep the boot clear counter separate from later owned SKB effects.

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
        if not (self.cold_request and (self.cold_pcie or getattr(self, 'cold_tail', False))):
            return self._run_cold(start, stops)
        reader = self.desc10.symbols['npu_emulation_desc10_read']
        if reader not in self.cold_checkpoints:
            self.cold_checkpoints += (reader,)
            self.cold_checkpoint_hits[hex(reader)] = 0
        hook = self.cpu.hook_add(UC_HOOK_CODE, self.code_hook, begin=reader, end=reader)
        try:
            return self._run_cold(start, stops)
        finally:
            self.cpu.hook_del(hook)

    def _run_cold(self, start, stops):
        if not self.cold_request or not self.cold_count or (self.cold_count > 1536 and not (self.cold_txbuf or self.cold_rx_event or self.cold_desc10 or self.cold_pcie or getattr(self, 'cold_tail', False))):
            return super().run(start, stops)
        pc, chunks = start, 0
        while True:
            pc = super().run(pc, list(stops) + list(self.cold_checkpoints))
            chunks += 1
            assert chunks <= self.cold_count + 3, 'cold-wire-getter-progress'
            if pc not in self.cold_checkpoints:
                return pc
            self.cold_checkpoint_hits[hex(pc)] += 1
            self.cold_getters += int(pc == self.cold_getter)
