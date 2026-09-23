#include <linux/errno.h>
#include <linux/soc/airoha/airoha_offload.h>
#include "linux-control.h"

_Static_assert(sizeof(struct npu_control_v2_packet) == NPU_CONTROL_V2_SIZE,
	       "control packet layout changed");

static int hold(struct npu_linux_control *control, int error)
{
	if (!control->error)
		control->error = error;
	npu_client_v2_abort(&control->client);
	return control->error;
}

int npu_linux_control_init(struct npu_linux_control *control,
			   struct airoha_npu *provider, u32 nonce_lo, u32 nonce_hi)
{
	if (!control)
		return -EINVAL;
	if (control->initialized)
		return -EALREADY;

	mutex_init(&control->mutex);
	control->provider = provider;
	control->error = 0;
	control->closed = false;
	npu_client_v2_init(&control->client, nonce_lo, nonce_hi);
	control->initialized = true;
	if (!provider || control->client.base.phase == NPU_CLIENT_FAILED) {
		control->provider = NULL;
		control->closed = true;
		return hold(control, provider ? -EINVAL : -ENODEV);
	}
	return 0;
}

static int next_operation(const struct npu_linux_control *control)
{
	switch (control->client.base.phase) {
	case NPU_CLIENT_NEW:
		return NPU_CONTROL_DISCOVER;
	case NPU_CLIENT_DISCOVERED:
		return NPU_CONTROL_BIND;
	case NPU_CLIENT_BOUND:
		return NPU_CONTROL_STOP;
	case NPU_CLIENT_STOPPING:
	case NPU_CLIENT_PARKED:
		return NPU_CONTROL_STATUS;
	default:
		return -EINVAL;
	}
}

int npu_linux_control_exchange(struct npu_linux_control *control,
			       enum npu_control_operation operation)
{
	struct npu_control_v2_packet packet;
	enum npu_client_result result;
	u32 ticket;
	int error;

	if (!control || !control->initialized)
		return -EINVAL;
	mutex_lock(&control->mutex);
	if (control->error) {
		error = control->error;
		goto unlock;
	}
	if (control->closed || !control->provider) {
		error = hold(control, -ESHUTDOWN);
		goto unlock;
	}
	/* A repeated BIND must never silently turn into the client's next STOP. */
	if (next_operation(control) != (int)operation) {
		error = hold(control, -EINVAL);
		goto unlock;
	}
	ticket = npu_client_v2_request(&control->client, &packet, sizeof(packet));
	if (!ticket) {
		error = hold(control, -EPROTO);
		goto unlock;
	}
	/* Firmware uses the provider's coherent copy, including after a timeout.
	 * This synchronous call never retains the address of the stack packet.
	 */
	error = airoha_npu_wlan_control(control->provider, &packet, sizeof(packet));
	result = npu_client_v2_complete(&control->client, ticket, error,
				       &packet, sizeof(packet));
	if (error || result != NPU_CLIENT_ACCEPTED)
		error = hold(control, error < 0 ? error : error ? -EIO : -EPROTO);
unlock:
	mutex_unlock(&control->mutex);
	return error;
}

int npu_linux_control_snapshot(struct npu_linux_control *control,
			       struct npu_linux_control_snapshot *snapshot)
{
	if (!control || !control->initialized || !snapshot)
		return -EINVAL;
	mutex_lock(&control->mutex);
	snapshot->client = control->client;
	snapshot->error = control->error;
	snapshot->closed = control->closed;
	mutex_unlock(&control->mutex);
	return 0;
}

void npu_linux_control_close(struct npu_linux_control *control)
{
	if (!control || !control->initialized)
		return;
	mutex_lock(&control->mutex);
	hold(control, -ESHUTDOWN);
	control->closed = true;
	control->provider = NULL;
	mutex_unlock(&control->mutex);
}
