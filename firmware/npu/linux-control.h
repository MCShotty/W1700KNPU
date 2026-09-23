#ifndef W1700K_NPU_LINUX_CONTROL_H
#define W1700K_NPU_LINUX_CONTROL_H

#include <linux/mutex.h>
#include <linux/types.h>
#include "control-v2.h"

struct airoha_npu;

/* Initialize once before publishing a zeroed instance, only for an independently
 * contained cold provider lifetime and fresh nonce. The caller retains its
 * provider reference until close returns, and this allocation until all callers
 * retire. Close joins CPU calls; it does not retire device-visible storage.
 * Client state is private to these functions, including after failure/close.
 */
struct npu_linux_control {
	struct mutex mutex;
	struct airoha_npu *provider;
	struct npu_control_v2_client client;
	int error;
	bool initialized;
	bool closed;
};

struct npu_linux_control_snapshot {
	struct npu_control_v2_client client;
	int error;
	bool closed;
};

int npu_linux_control_init(struct npu_linux_control *control,
			   struct airoha_npu *provider, u32 nonce_lo, u32 nonce_hi);
int npu_linux_control_exchange(struct npu_linux_control *control,
			       enum npu_control_operation operation);
int npu_linux_control_snapshot(struct npu_linux_control *control,
			       struct npu_linux_control_snapshot *snapshot);
void npu_linux_control_close(struct npu_linux_control *control);

#endif
