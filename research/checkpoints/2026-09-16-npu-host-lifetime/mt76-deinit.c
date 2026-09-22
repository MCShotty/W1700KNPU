void mt76_npu_deinit(struct mt76_dev *dev)
{
	struct airoha_ppe_dev *ppe_dev;
	struct airoha_npu *npu;

	mutex_lock(&dev->mutex);

	npu = rcu_replace_pointer(dev->mmio.npu, NULL,
				  lockdep_is_held(&dev->mutex));
	ppe_dev = rcu_replace_pointer(dev->mmio.ppe_dev, NULL,
				      lockdep_is_held(&dev->mutex));
	if (npu || ppe_dev)
		synchronize_rcu();

	mutex_unlock(&dev->mutex);

	mt76_npu_queue_cleanup(dev, &dev->q_rx[MT_RXQ_NPU0]);
	mt76_npu_queue_cleanup(dev, &dev->q_rx[MT_RXQ_NPU1]);

	if (npu)
		airoha_npu_put(npu);
	if (ppe_dev)
		airoha_ppe_put_dev(ppe_dev);
}
