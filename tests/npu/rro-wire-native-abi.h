#ifndef W1700K_RRO_WIRE_NATIVE_ABI_H
#define W1700K_RRO_WIRE_NATIVE_ABI_H

/* The RRO component owns both four-byte entries. A base built with
 * NPU_EMULATION_RRO_WIRE must be packaged with that exact component. */
#define NPU_RRO_NATIVE_MAILBOX_VENEER 0x84100000u
#define NPU_RRO_NATIVE_COLD_READY_VENEER 0x84100004u
#define NPU_RRO_NATIVE_SESSION_BYTES 30588u

#endif
