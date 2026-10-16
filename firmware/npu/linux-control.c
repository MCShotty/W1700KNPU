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
	control->descriptor_gets = control->descriptor_arena = 0;
	control->txbuf_enrolled = 0;
	control->txbuf_steps = 0;
	control->rx_event = control->rx_event_steps = 0;
	control->tx0_register = control->tx2_register = control->pcie_tail_steps = 0;
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
	snapshot->descriptor_gets = control->descriptor_gets;
	snapshot->descriptor_arena = control->descriptor_arena;
	snapshot->txbuf_enrolled = control->txbuf_enrolled;
	snapshot->txbuf_steps = control->txbuf_steps;
	snapshot->rx_event = control->rx_event;
	snapshot->rx_event_steps = control->rx_event_steps;
	snapshot->tx0_register = control->tx0_register;
	snapshot->tx2_register = control->tx2_register;
	snapshot->pcie_tail_steps = control->pcie_tail_steps;
	snapshot->error = control->error;
	snapshot->closed = control->closed;
	mutex_unlock(&control->mutex);
	return 0;
}

int npu_linux_control_cold_exchange(struct npu_linux_control *control,
				    const struct npu_bootstrap_packet *command,
				    u32 *value)
{
	struct npu_bootstrap_packet snapshot;
	struct npu_cold_packet packet;
	enum npu_client_result result;
	u32 ticket, output, descriptor, arena, enrollment, txbuf, rx_bind, rx_command, desc10, rx_pcie;
	u32 tail, tx0_before, tx2_before, tail_before, address, offset;
	int error;

	if (!control || !control->initialized || !command || !value)
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
	snapshot = *command;
	enrollment = npu_cold_txbuf_enrollment_step(&snapshot);
	rx_bind = npu_cold_rx_event_enrollment(&snapshot);
	rx_command = npu_cold_rx_event_command(&snapshot);
	desc10 = npu_cold_txdone_command(&snapshot);
	rx_pcie = npu_cold_rx_pcie_command(&snapshot);
	tail = npu_cold_pcie_tail_command_step(&snapshot);
	tx0_before = control->tx0_register;
	tx2_before = control->tx2_register;
	tail_before = control->pcie_tail_steps;
	if (tail < NPU_COLD_PCIE_TAIL_STAGES) {
		address = tail ? tx2_before : tx0_before;
		offset = tail ? 0x110u : 0x160u;
		if (tail != tail_before || control->rx_event_steps != 3 || !control->rx_event ||
		    control->txbuf_enrolled != NPU_COLD_TXBUF_RECORDS ||
		    control->txbuf_steps != NPU_COLD_TXBUF_STEPS ||
		    control->descriptor_gets != NPU_COLD_DESCRIPTOR_STEPS || !tx0_before || !tx2_before ||
		    (tail == 2 ? snapshot.value != 0 :
		     address > 0xffffffffu - offset || snapshot.value != address + offset)) {
			error = hold(control, -EPROTO);
			goto unlock;
		}
	}
	if ((enrollment < NPU_COLD_TXBUF_RECORDS && enrollment != control->txbuf_enrolled) ||
	    (control->txbuf_enrolled && control->txbuf_enrolled < NPU_COLD_TXBUF_RECORDS &&
	     enrollment == NPU_COLD_TXBUF_RECORDS && !rx_bind) ||
	    (rx_bind && (control->rx_event || control->rx_event_steps ||
	     control->txbuf_enrolled != NPU_COLD_TXBUF_MAILBOXES ||
	     control->descriptor_gets || control->descriptor_arena || control->txbuf_steps)) ||
	    (rx_command && (!control->rx_event || control->rx_event_steps ||
	     snapshot.value != control->rx_event || control->txbuf_enrolled != NPU_COLD_TXBUF_RECORDS ||
	     control->txbuf_steps != NPU_COLD_TXBUF_STEPS ||
	     control->descriptor_gets != NPU_COLD_DESCRIPTOR_STEPS)) ||
	    (desc10 && (!control->rx_event || control->rx_event_steps != 1 || snapshot.value != 512 ||
	     control->txbuf_enrolled != NPU_COLD_TXBUF_RECORDS || control->txbuf_steps != NPU_COLD_TXBUF_STEPS ||
	     control->descriptor_gets != NPU_COLD_DESCRIPTOR_STEPS)) ||
	    (rx_pcie && (!control->rx_event || control->rx_event_steps != 2 ||
	     control->txbuf_enrolled != NPU_COLD_TXBUF_RECORDS || control->txbuf_steps != NPU_COLD_TXBUF_STEPS ||
	     control->descriptor_gets != NPU_COLD_DESCRIPTOR_STEPS))) {
		error = hold(control, -EPROTO);
		goto unlock;
	}
	descriptor = npu_cold_descriptor_command_step(&snapshot);
	txbuf = npu_cold_txbuf_command_step(&snapshot);
	if ((txbuf < NPU_COLD_TXBUF_STEPS &&
	     (txbuf != control->txbuf_steps || control->txbuf_enrolled != NPU_COLD_TXBUF_RECORDS ||
	      control->descriptor_gets != (txbuf < 3 ? 7u : 8u))) ||
	    (descriptor == 7 && control->txbuf_enrolled == NPU_COLD_TXBUF_RECORDS &&
	     control->txbuf_steps != 3)) {
		error = hold(control, -EPROTO);
		goto unlock;
	}
	if (descriptor < NPU_COLD_DESCRIPTOR_STEPS && descriptor != control->descriptor_gets) {
		error = hold(control, -EPROTO);
		goto unlock;
	}
	ticket = npu_cold_client_request(&control->client, &packet,
					 sizeof(packet), &snapshot);
	if (!ticket) {
		error = hold(control, -EPROTO);
		goto unlock;
	}
	error = airoha_npu_wlan_control(control->provider, &packet, sizeof(packet));
	result = npu_cold_client_complete(&control->client, ticket, error,
					  &packet, sizeof(packet), &snapshot, &output);
	if (error || result != NPU_CLIENT_ACCEPTED)
		error = hold(control, error < 0 ? error : error ? -EIO : -EPROTO);
	else if (control->tx0_register != tx0_before || control->tx2_register != tx2_before ||
		 control->pcie_tail_steps != tail_before)
		error = hold(control, -EPROTO);
	else {
		if (enrollment < NPU_COLD_TXBUF_RECORDS)
			control->txbuf_enrolled++;
		if (txbuf < NPU_COLD_TXBUF_STEPS)
			control->txbuf_steps++;
		if (rx_bind)
			control->rx_event = snapshot.value;
		if (rx_command || desc10 || rx_pcie)
			control->rx_event_steps++;
		if (tail < NPU_COLD_PCIE_TAIL_STAGES)
			control->pcie_tail_steps++;
		if (snapshot.api == 19 && snapshot.header == 0x10)
			control->tx0_register = snapshot.value;
		if (snapshot.api == 19 && snapshot.header == 0x12)
			control->tx2_register = snapshot.value;
		if (descriptor < NPU_COLD_DESCRIPTOR_STEPS) {
			arena = npu_cold_descriptor_reply_arena(descriptor, output, control->descriptor_arena);
			if (!arena) {
				error = hold(control, -EPROTO);
				goto unlock;
			}
			control->descriptor_arena = arena;
			control->descriptor_gets++;
		}
		*value = output;
	}
unlock:
	mutex_unlock(&control->mutex);
	return error;
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
