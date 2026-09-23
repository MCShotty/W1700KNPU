static int mt7996_mac_rx_prepare(struct sk_buff *skb)
{
	u32 rxd0, rxd1, rxd2, rxd4;
	unsigned int offset = 8 * sizeof(__le32), len;
	__le16 fc, group_fc = 0;
	bool is_mesh;

	if (!pskb_may_pull(skb, offset))
		return -EINVAL;
	rxd0 = get_unaligned_le32(skb->data);
	rxd1 = get_unaligned_le32(skb->data + 4);
	rxd2 = get_unaligned_le32(skb->data + 8);
	rxd4 = get_unaligned_le32(skb->data + 16);

	if (rxd1 & MT_RXD1_NORMAL_GROUP_4)
		offset += 4 * sizeof(__le32);
	if (rxd1 & MT_RXD1_NORMAL_GROUP_1)
		offset += 4 * sizeof(__le32);
	if (rxd1 & MT_RXD1_NORMAL_GROUP_2)
		offset += 4 * sizeof(__le32);
	if (rxd1 & MT_RXD1_NORMAL_GROUP_3) {
		offset += 4 * sizeof(__le32);
		if (rxd1 & MT_RXD1_NORMAL_GROUP_5)
			offset += 24 * sizeof(__le32);
	}
	offset += 2 * FIELD_GET(MT_RXD2_NORMAL_HDR_OFFSET, rxd2);
	if (!pskb_may_pull(skb, offset + sizeof(__le16)))
		return -EINVAL;

	if (rxd2 & MT_RXD2_NORMAL_HDR_TRANS) {
		len = ETH_HLEN;
		if (!pskb_may_pull(skb, offset + len))
			return -EINVAL;
		if ((rxd2 & MT_RXD2_NORMAL_HDR_TRANS_ERROR) &&
		    get_unaligned_be16(skb->data + offset + 12) == ETH_P_8021Q)
			len += VLAN_HLEN + 2;
	} else {
		fc = cpu_to_le16(get_unaligned_le16(skb->data + offset));
		len = ieee80211_hdrlen(fc);
		if (rxd1 & MT_RXD1_NORMAL_GROUP_4) {
			u32 v0 = get_unaligned_le32(skb->data + 32);

			group_fc = cpu_to_le16(FIELD_GET(MT_RXD8_FRAME_CONTROL, v0));
		}
		is_mesh = (rxd0 & (MT_RXD0_MESH | MT_RXD0_MHCP)) ==
			  (MT_RXD0_MESH | MT_RXD0_MHCP);
		if (FIELD_GET(MT_RXD4_NORMAL_PAYLOAD_FORMAT, rxd4) &&
		    !(ieee80211_has_a4(group_fc) && is_mesh))
			len = max_t(unsigned int, len + 2, 10);
	}

	return pskb_may_pull(skb, offset + len) ? 0 : -EINVAL;
}
