/* Raw native cold-command binding; physical backing/drains remain unproved. */
#include "cold-setup.h"

extern struct npu_bootstrap npu_emulation_bootstrap_state;
extern struct npu_control_v2_session npu_emulation_control_v2_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;
struct npu_cold_setup npu_emulation_cold_setup_state;

typedef uint32_t (*native_callback)(struct npu_bootstrap_packet *);

int npu_emulation_cold_mailbox(struct npu_cold_packet *host, uint32_t bytes)
{
    struct npu_cold_packet snapshot;
    struct npu_cold_setup *s = &npu_emulation_cold_setup_state;
    struct npu_bootstrap_packet command;
    enum npu_cold_status status;
    uint32_t callback, slot, result = 0;

    if (bytes != sizeof(snapshot))
        return 0;
    npu_cold_packet_copy(&snapshot, host);
    status = npu_cold_setup_begin(s, &npu_emulation_control_v2_state,
        &npu_emulation_admission_state, &npu_emulation_barrier_state,
        &npu_emulation_bootstrap_state, &snapshot, bytes);
    if (status == NPU_COLD_OK) {
        command.header = s->command.header;
        command.api = s->command.api;
        command.value = s->command.value;
        if (command.header == NPU_COLD_BIND_HEADER &&
                   (command.api == NPU_COLD_BIND_BASE_API ||
                    command.api == NPU_COLD_BIND_BYTES_API ||
                    npu_cold_txbuf_enrollment_step(&command) < NPU_COLD_TXBUF_RECORDS ||
                    npu_cold_rx_event_enrollment(&command))) {
            result = 1;
            slot = callback = 0;
        } else if (command.api == NPU_COLD_INODE_API) {
            /* Constructor history is not an original-store owner binding. */
            slot = callback = 0;
        } else if ((command.header & ~15u) == 0x30u) {
            slot = 0x3e900148u + command.api * 4;
            callback = command.api == 4 ? 0x84010164u : 0x840101a6u;
        } else {
            slot = 0x3e900178u + command.api * 4;
            callback = command.api == 14 ? 0x8400ff34u :
                       command.api == 0 ? 0x8400fdc4u :
                       command.api == 19 ? 0x8400fc16u :
                       command.api == 21 ? 0x8400fbcau :
                       command.api == 22 ? 0x8400fbb4u :
                       command.api == 33 ? 0x8400fddau : 0x8400fe34u;
        }
        if (slot && *(const volatile uint32_t *)(uintptr_t)slot == callback)
            result = ((native_callback)(uintptr_t)callback)(&command);
        status = npu_cold_setup_finish(s, &npu_emulation_control_v2_state,
            &npu_emulation_admission_state, &npu_emulation_barrier_state,
            &npu_emulation_bootstrap_state, result, &command);
        if (status == NPU_COLD_OK)
            snapshot.command.value = command.value;
    }
    snapshot.magic = NPU_COLD_REPLY;
    snapshot.status = status;
    npu_cold_packet_copy(host, &snapshot);
    return 1;
}
