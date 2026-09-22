	/* Register work cleanup before IRQs, so devres stops producers first. */
	for (i = 0; i < ARRAY_SIZE(npu->cores); i++) {
		struct airoha_npu_core *core = &npu->cores[i];

		spin_lock_init(&core->lock);
		core->npu = npu;
		err = devm_work_autocancel(dev, &core->wdt_work,
					   airoha_npu_wdt_work);
		if (err)
			return err;
	}
