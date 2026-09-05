'use strict';
'require view';
'require fs';
'require ui';

var initScript = '/etc/init.d/softethervpnserver';
var allowedActions = [ 'start', 'stop', 'restart', 'enable', 'disable' ];

function checkState(action) {
	return fs.exec_direct(initScript, [ action ]).then(
		function() { return true; },
		function() { return false; }
	);
}

function stateRow(title, value) {
	return E('div', { 'class': 'cbi-value' }, [
		E('div', { 'class': 'cbi-value-title' }, title),
		E('div', { 'class': 'cbi-value-field' }, value)
	]);
}

return view.extend({
	load: function() {
		return Promise.all([ checkState('enabled'), checkState('running') ]);
	},

	handleAction: function(action) {
		if (allowedActions.indexOf(action) < 0)
			return Promise.reject(new Error('Unsupported service action'));
		if (this.actionRequest)
			return this.actionRequest;

		ui.showModal(_('SoftEther Server'), [
			E('p', { 'class': 'spinning' }, _('Applying service state...'))
		]);
		this.actionRequest = fs.exec_direct(initScript, [ action ])
			.then(function() { window.location.reload(); })
			.catch(function(error) {
				ui.hideModal();
				ui.addNotification(null, E('p', {},
					_('Service action failed: %s').format(error.message || error)), 'error');
			})
			.finally(L.bind(function() { this.actionRequest = null; }, this));
		return this.actionRequest;
	},

	handleAutostart: function(event) {
		return this.handleAction(event.target.checked ? 'enable' : 'disable');
	},

	render: function(data) {
		var enabled = !!data[0];
		var running = !!data[1];

		return E('div', { 'class': 'cbi-map' }, [
			E('h2', {}, _('SoftEther Server')),
			E('div', { 'class': 'cbi-section' }, [
				stateRow(_('Service state'), running ? _('running') : _('stopped')),
				stateRow(_('Start at boot'), E('input', {
					'type': 'checkbox',
					'checked': enabled,
					'change': L.bind(this.handleAutostart, this)
				})),
				stateRow(_('Configuration file'),
					'/usr/libexec/softethervpn/vpn_server.config')
			]),
			E('div', { 'class': 'cbi-page-actions' }, [
				E('button', {
					'class': 'btn cbi-button cbi-button-action',
					'click': ui.createHandlerFn(this, 'handleAction', running ? 'stop' : 'start')
				}, running ? _('Stop') : _('Start')),
				' ',
				E('button', {
					'class': 'btn cbi-button cbi-button-neutral',
					'disabled': running ? null : 'disabled',
					'click': ui.createHandlerFn(this, 'handleAction', 'restart')
				}, _('Restart')),
				' ',
				E('button', {
					'class': 'btn cbi-button cbi-button-neutral',
					'click': function() { window.location.reload(); }
				}, _('Refresh'))
			])
		]);
	},

	handleSave: null,
	handleSaveApply: null,
	handleReset: null
});
