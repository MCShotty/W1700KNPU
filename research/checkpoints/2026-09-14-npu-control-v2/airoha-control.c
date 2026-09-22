int airoha_npu_wlan_control(struct airoha_npu *npu, void *data, int len)
{
	const u8 *bytes = data;

	if (!npu)
		return -ENODEV;
	if (!data || len != 80)
		return -EINVAL;
	/* Dedicated NQC2 envelope: WLAN GET selector 15, API 0. */
	if (get_unaligned_le32(bytes) != 0x3f ||
	    get_unaligned_le32(bytes + 4) != 0 ||
	    get_unaligned_le32(bytes + 8) != 0x3243514e ||
	    get_unaligned_le32(bytes + 12) != 2 ||
	    get_unaligned_le32(bytes + 16) != 80)
		return -EINVAL;

	/* The coherent bounce buffer, including timeout retention, owns the
	 * firmware transaction. A successful reply is still not a drain witness.
	 */
	return __airoha_npu_send_msg(npu, NPU_FUNC_WIFI, data, len, data, len);
}
EXPORT_SYMBOL_GPL(airoha_npu_wlan_control);
