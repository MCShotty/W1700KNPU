static struct sk_buff *mt76_npu_dequeue(struct mt76_dev *dev,
				      struct mt76_queue *q, u32 *info)
{
	struct airoha_npu_rx_dma_desc *desc = (void *)q->desc;
	int i, nframes, index = q->tail;
	struct sk_buff *skb = NULL;
	u16 lengths[16];
	u32 ctrl, packet_info;
	bool drop;

	if (!desc || !q->entry || q->ndesc <= 0 || q->queued <= 0 ||
	    q->queued > q->ndesc || index >= q->ndesc || q->buf_size <= 0 ||
	    q->buf_size <= SKB_DATA_ALIGN(sizeof(struct skb_shared_info)))
		return NULL;

	ctrl = READ_ONCE(desc[index].ctrl);
	if (!(ctrl & NPU_RX_DMA_DESC_DONE_MASK))
		return NULL;
	dma_rmb();
	packet_info = READ_ONCE(desc[index].info);
	nframes = max_t(int, FIELD_GET(NPU_RX_DMA_PKT_COUNT_MASK, packet_info), 1);
	if (nframes > ARRAY_SIZE(lengths) || nframes > q->queued)
		return NULL;
	drop = nframes > MAX_SKB_FRAGS + 1;

	/* Retain every buffer until the complete packet can be consumed. */
	for (i = 0; i < nframes; i++) {
		struct mt76_queue_entry *e = &q->entry[index];

		if (i) {
			ctrl = READ_ONCE(desc[index].ctrl);
			if (!(ctrl & NPU_RX_DMA_DESC_DONE_MASK))
				return NULL;
			dma_rmb();
			packet_info = READ_ONCE(desc[index].info);
		}
		if (!e->buf || !e->dma_len[0] ||
		    e->dma_len[0] > SKB_WITH_OVERHEAD(q->buf_size))
			return NULL;
		lengths[i] = FIELD_GET(NPU_RX_DMA_DESC_CUR_LEN_MASK, ctrl);
		drop |= lengths[i] > e->dma_len[0];
		index = (index + 1) % q->ndesc;
	}

	index = q->tail;
	for (i = 0; i < nframes; i++) {
		struct mt76_queue_entry *e = &q->entry[index];

		dma_sync_single_for_cpu(dev->dma_dev, e->dma_addr[0],
					e->dma_len[0],
					page_pool_get_dma_dir(q->page_pool));
		if (drop) {
			mt76_put_page_pool_buf(e->buf, false);
		} else if (!i) {
			skb = napi_build_skb(e->buf, q->buf_size);
			if (!skb)
				return NULL;
			__skb_put(skb, lengths[i]);
			skb_reset_mac_header(skb);
			skb_mark_for_recycle(skb);
		} else {
			struct page *page = virt_to_head_page(e->buf);

			skb_add_rx_frag(skb, i - 1, page,
					e->buf - page_address(page),
					lengths[i], q->buf_size);
		}
		e->buf = NULL;
		index = (index + 1) % q->ndesc;
	}
	q->tail = index;
	q->queued -= nframes;
	Q_WRITE(q, dma_idx, q->tail);

	if (drop)
		return ERR_PTR(-EINVAL);
	*info = packet_info;

	return skb;
}
