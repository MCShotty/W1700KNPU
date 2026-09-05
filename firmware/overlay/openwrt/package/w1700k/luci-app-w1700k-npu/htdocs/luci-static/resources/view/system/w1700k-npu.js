'use strict';
'require view';
'require fs';
'require poll';
'require ui';

var helper = '/usr/sbin/w1700k-wlan-npu-mode';
var pollInterval = 30;
var statusData = {};

function errorMessage(error) {
	if (!error)
		return _('helper returned no data');
	return String(error.message || error);
}

function display(value) {
	if (value === null || value === undefined || value === '')
		return '-';
	if (value === true)
		return _('yes');
	if (value === false)
		return _('no');
	return String(value);
}

function setText(id, value) {
	var element = document.getElementById(id);
	if (element)
		element.textContent = display(value);
}

function row(id, title, value) {
	return E('div', { 'class': 'cbi-value' }, [
		E('div', { 'class': 'cbi-value-title' }, title),
		E('div', { 'class': 'cbi-value-field' }, [
			E('span', { 'id': id }, display(value))
		])
	]);
}

return view.extend({
	applyStatus: function(data) {
		statusData = data || {};
		this.statusHealth = 'current';
		this.statusLastSuccess = new Date().toISOString();
		this.statusLastError = null;
		var source = statusData.source || {};
		var npu = statusData.npu || {};
		var parameters = statusData.module_parameters || {};
		var rps = statusData.rps || {};
		var cpufreq = statusData.cpufreq || {};
		var coredump = statusData.coredump || {};

		setText('npu_status_health', this.statusHealth);
		setText('npu_status_last_success', this.statusLastSuccess);
		setText('npu_status_last_error', this.statusLastError);
		setText('npu_openwrt_base_commit', source.openwrt_base_commit);
		setText('npu_openwrt_candidate_commit', source.openwrt_candidate_commit);
		setText('npu_openwrt_build_revision', source.openwrt_build_revision);
		setText('npu_openwrt_build_target', source.openwrt_build_target);
		setText('npu_openwrt_build_version', source.openwrt_build_version);
		setText('npu_mt76_commit', source.mt76_commit);
		setText('npu_classification', source.classification);
		setText('npu_runtime_state', npu.runtime_state);
		setText('npu_compiled_support', npu.compiled_support);
		setText('npu_runtime_reason', npu.runtime_reason);
		setText('npu_mt76_loaded', npu.mt76_loaded);
		setText('npu_mt7996e_loaded', npu.mt7996e_loaded);
		setText('npu_provider_present', npu.npu_provider_present);
		setText('npu_ppe_present', npu.ppe_provider_present);
		setText('npu_debugfs_path', npu.debugfs_path);
		setText('npu_provider_attached', npu.provider_attached);
		setText('npu_ppe_attached', npu.ppe_attached);
		setText('npu_hwrro_mode', npu.hwrro_mode);
		setText('npu_rx_token_size', npu.rx_token_size);
		setText('npu_type', npu.npu_type);
		setText('npu_numeric_modes', npu.numeric_mode_api);
		setText('npu_wed_enable', parameters.wed_enable);
		setText('npu_coredump_memdump', parameters.coredump_memdump);
		setText('npu_sr_scene_detect', parameters.sr_scene_detect);
		setText('npu_packet_steering', rps.packet_steering);
		setText('npu_steering_flows', rps.steering_flows);
		setText('npu_rps_entries', rps.rps_sock_flow_entries);
		setText('npu_rps_queues', rps.observed_rx_queue_count);
		setText('npu_cpufreq_count', cpufreq.policy_count);
		setText('npu_cpufreq_policies', cpufreq.policies);
		setText('npu_core_pattern', coredump.core_pattern);
		setText('npu_suid_dumpable', coredump.suid_dumpable);

		return statusData;
	},

	applyStatusError: function(error) {
		this.statusHealth = Object.keys(statusData).length ? 'stale' : 'unavailable';
		this.statusLastError = errorMessage(error);
		setText('npu_status_health', this.statusHealth);
		setText('npu_status_last_success', this.statusLastSuccess);
		setText('npu_status_last_error', this.statusLastError);
		return statusData;
	},

	loadStatus: function() {
		var generation = this.pollGeneration || 0;
		var request = this.statusRequest;

		if (!request) {
			request = fs.exec_direct(helper, [ 'json' ], 'json')
				.then(function(data) { return { data: data }; },
					function(error) { return { error: error }; })
				.finally(L.bind(function() {
					if (this.statusRequest === request)
						this.statusRequest = null;
				}, this));
			this.statusRequest = request;
		}

		return request.then(L.bind(function(result) {
			if (generation !== (this.pollGeneration || 0))
				return statusData;
			if (result.error || !result.data)
				return this.applyStatusError(result.error);
			return this.applyStatus(result.data);
		}, this));
	},

	stopStatusPolling: function() {
		this.pollGeneration = (this.pollGeneration || 0) + 1;
		if (this.statusPollFn)
			poll.remove(this.statusPollFn);
		this.statusPollFn = null;
	},

	armStatusUnload: function() {
		if (this.statusUnloadFn)
			return;
		this.statusUnloadFn = L.bind(this.handleStatusUnload, this);
		window.addEventListener('pagehide', this.statusUnloadFn);
		window.addEventListener('unload', this.statusUnloadFn);
	},

	handleStatusUnload: function() {
		this.stopStatusPolling();
		if (this.statusUnloadFn) {
			window.removeEventListener('pagehide', this.statusUnloadFn);
			window.removeEventListener('unload', this.statusUnloadFn);
			this.statusUnloadFn = null;
		}
	},

	startStatusPolling: function() {
		var generation = this.pollGeneration || 0;
		if (this.statusPollFn)
			return;
		this.statusPollFn = L.bind(function() {
			if (generation !== (this.pollGeneration || 0))
				return Promise.resolve(null);
			return this.loadStatus();
		}, this);
		poll.add(this.statusPollFn, pollInterval);
		this.armStatusUnload();
	},

	handleRefresh: function() {
		return this.loadStatus();
	},

	handleSnapshot: function() {
		var request = this.snapshotRequest;
		if (!request) {
			request = L.resolveDefault(fs.exec_direct(helper, [ 'snapshot' ]),
				_('Unable to load snapshot.')).finally(L.bind(function() {
					if (this.snapshotRequest === request)
						this.snapshotRequest = null;
				}, this));
			this.snapshotRequest = request;
		}
		return request.then(function(text) {
			ui.showModal(_('W1700K NPU snapshot'), [
				E('pre', { 'style': 'max-height:70vh;overflow:auto' }, text || '-'),
				E('div', { 'class': 'right' }, [
					E('button', {
						'class': 'btn',
						'click': ui.hideModal
					}, _('Close'))
				])
			]);
			return text;
		});
	},

	load: function() {
		this.stopStatusPolling();
		statusData = {};
		this.statusHealth = 'loading';
		this.statusLastSuccess = null;
		this.statusLastError = null;
		return this.loadStatus();
	},

	render: function(data) {
		data = data || {};
		statusData = data;
		var source = data.source || {};
		var npu = data.npu || {};
		var parameters = data.module_parameters || {};
		var rps = data.rps || {};
		var cpufreq = data.cpufreq || {};
		var coredump = data.coredump || {};
		var node = E('div', { 'class': 'cbi-map' }, [
			E('h2', {}, _('W1700K NPU')),
			E('div', { 'class': 'cbi-section' }, [
				E('h3', {}, _('Status freshness')),
				row('npu_status_health', _('State'), this.statusHealth || 'unavailable'),
				row('npu_status_last_success', _('Last successful refresh'), this.statusLastSuccess),
				row('npu_status_last_error', _('Last error'), this.statusLastError)
			]),
			E('div', { 'class': 'cbi-section' }, [
				E('h3', {}, _('Implementation')),
				row('npu_classification', _('Current source classification'), source.classification),
				row('npu_runtime_state', _('Runtime state'), npu.runtime_state),
				row('npu_compiled_support', _('WLAN NPU compiled in'), npu.compiled_support),
				row('npu_runtime_reason', _('Evidence boundary'), npu.runtime_reason),
				row('npu_openwrt_base_commit', _('Official OpenWrt base'), source.openwrt_base_commit),
				row('npu_openwrt_candidate_commit', _('W1700K candidate source'), source.openwrt_candidate_commit),
				row('npu_openwrt_build_revision', _('Runtime build revision'), source.openwrt_build_revision),
				row('npu_openwrt_build_target', _('Runtime build target'), source.openwrt_build_target),
				row('npu_openwrt_build_version', _('Runtime build version'), source.openwrt_build_version),
				row('npu_mt76_commit', _('mt76 source'), source.mt76_commit),
				row('npu_numeric_modes', _('Numeric mode API available'), npu.numeric_mode_api)
			]),
			E('div', { 'class': 'cbi-section' }, [
				E('h3', {}, _('Observed runtime surfaces')),
				row('npu_mt76_loaded', _('mt76 loaded'), npu.mt76_loaded),
				row('npu_mt7996e_loaded', _('mt7996e loaded'), npu.mt7996e_loaded),
				row('npu_provider_present', _('Airoha NPU provider present'), npu.npu_provider_present),
				row('npu_ppe_present', _('Airoha PPE provider present'), npu.ppe_provider_present),
				row('npu_provider_attached', _('NPU attached to mt7996'), npu.provider_attached),
				row('npu_ppe_attached', _('PPE attached to mt7996'), npu.ppe_attached),
				row('npu_hwrro_mode', _('HW-RRO mode'), npu.hwrro_mode),
				row('npu_rx_token_size', _('RX token capacity'), npu.rx_token_size),
				row('npu_type', _('NPU PCIe port type'), npu.npu_type),
				row('npu_debugfs_path', _('Kernel evidence path'), npu.debugfs_path),
				row('npu_wed_enable', _('wed_enable'), parameters.wed_enable),
				row('npu_coredump_memdump', _('coredump_memdump'), parameters.coredump_memdump),
				row('npu_sr_scene_detect', _('sr_scene_detect'), parameters.sr_scene_detect)
			]),
			E('div', { 'class': 'cbi-section' }, [
				E('h3', {}, _('Policy observations')),
				row('npu_packet_steering', _('packet_steering'), rps.packet_steering),
				row('npu_steering_flows', _('steering_flows'), rps.steering_flows),
				row('npu_rps_entries', _('rps_sock_flow_entries'), rps.rps_sock_flow_entries),
				row('npu_rps_queues', _('Observed RX queues'), rps.observed_rx_queue_count),
				row('npu_cpufreq_count', _('CPU frequency policies'), cpufreq.policy_count),
				row('npu_cpufreq_policies', _('CPU frequency state'), cpufreq.policies),
				row('npu_core_pattern', _('Process core pattern'), coredump.core_pattern),
				row('npu_suid_dumpable', _('SUID dump policy'), coredump.suid_dumpable)
			]),
			E('div', { 'class': 'cbi-page-actions' }, [
				E('button', {
					'class': 'btn cbi-button cbi-button-neutral',
					'click': ui.createHandlerFn(this, 'handleRefresh')
				}, _('Refresh')),
				' ',
				E('button', {
					'class': 'btn cbi-button cbi-button-neutral',
					'click': ui.createHandlerFn(this, 'handleSnapshot')
				}, _('Snapshot'))
			])
		]);

		this.startStatusPolling();
		return node;
	},

	handleSave: null,
	handleSaveApply: null,
	handleReset: null
});
