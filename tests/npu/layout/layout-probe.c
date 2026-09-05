#include <linux/module.h>
#include <linux/stddef.h>
#ifdef NPU_LAYOUT_PREIMAGE
#include "airoha_offload-before.h"
#else
#include <linux/soc/airoha/airoha_offload.h>
#endif

static const u32 layout[] __used __section(".npu_layout") = {
	sizeof(struct airoha_npu_core),
	sizeof(struct airoha_npu),
	offsetof(struct airoha_npu_core, lock),
	offsetof(struct airoha_npu_core, wdt_work),
	offsetof(struct airoha_npu_core, buf),
	offsetof(struct airoha_npu_core, addr),
	offsetof(struct airoha_npu, irqs),
	offsetof(struct airoha_npu, stats),
	offsetof(struct airoha_npu, ops),
};
MODULE_LICENSE("GPL");
