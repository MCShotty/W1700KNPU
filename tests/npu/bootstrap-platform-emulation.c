/* Test-only native callback binding; no production loader or drain witness. */
#include "bootstrap.h"

extern struct npu_barrier npu_emulation_barrier_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_bootstrap npu_emulation_bootstrap_state;

typedef uint32_t (*native_callback)(struct npu_bootstrap_packet *);

uint32_t npu_emulation_bootstrap_mailbox(uint32_t address, uint32_t bytes)
{
    struct npu_bootstrap *s = &npu_emulation_bootstrap_state;
    struct npu_admission *a = &npu_emulation_admission_state;
    struct npu_barrier *b = &npu_emulation_barrier_state;
    volatile struct npu_bootstrap_packet *host =
        (volatile void *)(uintptr_t)((address & 0x3fffffffu) | 0x40000000u);
    struct npu_bootstrap_packet packet;
    uint32_t callback, slot, result;

    if (bytes != sizeof(packet))
        return 0;
    packet.header = host->header;
    packet.api = host->api;
    packet.value = host->value;
    if (!npu_bootstrap_begin(s, a, b, &packet, bytes))
        return 0;
    slot = 0x3e900178u + s->packet.api * 4;
    if (s->packet.header == 0x30) {
        slot = 0x3e900170u;
        callback = 0x840101a6u;
    } else {
        switch (s->packet.api) {
        case 18: callback = 0x8400ff88u; break;
        case 32: callback = 0x8400fb84u; break;
        case 8: callback = 0x8400febeu; break;
        case 23: callback = 0x8400fb2eu; break;
        case 7: callback = 0x8400feacu; break;
        case 12: callback = 0x8400ff0cu; break;
        default: return npu_bootstrap_finish(s, a, b, 0);
        }
    }
    if (*(const volatile uint32_t *)(uintptr_t)slot != callback)
        return npu_bootstrap_finish(s, a, b, 0);
    result = ((native_callback)(uintptr_t)callback)(&s->packet);
    if (!npu_bootstrap_finish(s, a, b, result))
        return 0;
    if (packet.header == 0x30)
        host->value = s->packet.value;
    return 1;
}
