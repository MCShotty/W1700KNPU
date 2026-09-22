
import { md5, sha256 } from 'digest';
let files = {}, writes = [], results = [], cases = [], config_data = '', iface_idx = 0;
let phy_features = {}, status = {};
const mlo_link_local_fields = { macaddr: true };
let fs = {
  stat: path => exists(files, path),
  rename: (a, b) => { files[b] = files[a]; delete files[a]; push(writes, b); },
  readfile: path => files[path],
  writefile: (path, value) => { files[path] = value; push(writes, path); return length(value); },
  open: function(path, mode) {
    if (mode == 'w') { files[path] = ''; push(writes, path); }
    if (mode == 'a') files[path] ??= '';
    let offset = 0;
    return {
      write: value => { files[path] += value; return length(value); },
      close: () => true,
      read: function() {
        if (offset >= length(files[path])) return null;
        let end = index(substr(files[path], offset), '\n');
        end = end < 0 ? length(files[path]) - 1 : offset + end;
        let line = substr(files[path], offset, end + 1 - offset);
        offset = end + 1;
        return line;
      }
    };
  }
};
let open = fs.open, readfile = fs.readfile;
let netifd = { set_vlan: function() {}, add_process: function() {},
  setup_failed: function() {} };
global.ubus = { list: () => true, call: name => name == 'network.wireless' ? status : ({ pid: 1 }) };
let hostapd = { data: { file_fields: {} } };
let libuci = { cursor: () => ({ get: () => null }) };
function check(name, pass) { push(cases, { name, pass: !!pass }); }
function clone(value) { return json(sprintf('%J', value)); }
function append_raw(value) {
	config_data += value + '\n';
}

function append(key, value) {
	if (value == null)
		return;

	switch (type(value)) {
	case 'array':
		value = join(' ', value);
		break;
	case 'bool':
		value = value ? 1 : 0;
		break;
	}

	append_raw(key + '=' + value);
}

function escape_string(value) {
	let chars = map(split(value, ''), (v) => ord(v));
	if (length(filter(chars, (v) => (v < 32 || v >= 128))) > 0)
		return hexenc(value);

	return `"${value}"`;
}

function append_string(key, value) {
	if (value == null)
		return;

	append(key, escape_string(value));
}

function append_vars(dict, keys) {
	for (let key in keys)
		append(key, dict[key]);
}

function append_list(dict, keys) {
	for (let key in keys) {
		let val = dict[key];
		if (val == null)
			continue;
		if (type(val) != 'array')
			val = [ val ];
		for (let v in val)
			append(key, v);
	}
}

function append_string_vars(dict, keys) {
	for (let key in keys)
		append_string(key, dict[key]);
}

function set_default(dict, key, value) {
	if (dict[key] == null)
		dict[key] = value;
}

function push_config(dict, key, option, value) {
	if (!dict[option])
		return;

	dict[key] ??= [];
	push(dict[key], value);
}

function touch_file(filename) {
	let file = fs.open(filename, "a");
	if (file)
		file.close();
	else
		log('Failed to touch ' + filename);
}

function append_value(config, key, value) {
	if (!config[key])
		config[key] = value;
	else
		config[key] += ' ' + value;
}

function comment(comment) {
	append_raw('\n# ' + comment);
}

function dump_config(file) {
	if (file)
		fs.writefile(file, config_data);

	return config_data;
}

function flush_config() {
	config_data = '';
}

function log(msg) {
	printf(`wifi-scripts: ${msg}\n`);
}
function generate(config) { append('driver', 'nl80211'); append('channel', 6); }
let iface = (function() {
function parse_encryption(config, dev_config, phy_features) {
	if (!config.encryption)
		return;

	let encryption = split(config.encryption, '+', 2);

	config.wpa = 0;
	for (let k, v in { 'wpa2*': 2, 'wpa3*': 2, '*psk2*': 2, 'psk3*': 2, 'sae*': 2,
			'owe*': 2, 'dpp': 2, 'wpa*mixed*': 3, '*psk*mixed*': 3, 'wpa*': 1, '*psk*': 1, })
		if (wildcard(config.encryption, k)) {
			config.wpa = v;
			break;
		}

	config.auth_type = encryption[0] ?? 'none';

	// MLO needs the enhanced suites in its RSNE; sae-compat uses RSN Override.
	// Preserve non-MLO defaults and explicit per-BSS compatibility overrides.
	let compat = (config.auth_type == 'sae-compat');
	let mlo = config.mlo === true || config.mlo === 1 || config.mlo === '1';
	let enhanced = mlo || (compat && wildcard(dev_config?.htmode ?? '', 'EHT*'));
	config.gcmp256 ??= enhanced;
	config.sae_ext_key ??= enhanced;

	switch(config.auth_type) {
	case 'owe':
		config.auth_type = 'owe';
		break;

	case 'dpp':
		config.auth_type = 'dpp';
		break;

	case 'wpa3-192':
		config.auth_type = 'eap192';
		config.wpa_pairwise = 'GCMP-256';
		break;

	case 'wpa3-mixed':
		config.auth_type = 'eap-eap2';
		break;

	case 'wpa3':
		config.auth_type = 'eap2';
		break;

	case 'psk':
	case 'psk2':
	case 'psk-mixed':
		config.auth_type = 'psk';
		break;

	case 'sae':
	case 'psk3':
		config.auth_type = 'sae';
		break;

	case 'psk3-mixed':
	case 'sae-mixed':
		config.auth_type = 'psk-sae';
		break;

	case 'sae-compat':
		config.auth_type = 'psk-sae-compat';
		config.wpa_pairwise = 'CCMP';
		if (dev_config.band != '6g')
			config.rsn_override_pairwise = 'CCMP';
		if (config.gcmp256 && phy_features?.cipher_gcmp256)
			config.rsn_override_pairwise_2 = 'GCMP-256';
		break;

	case 'wpa':
	case 'wpa2':
	case 'wpa-mixed':
		config.auth_type = 'eap';
		break;
	}

	switch(encryption[1]){
	case 'tkip+aes':
	case 'tkip+ccmp':
	case 'aes+tkip':
	case 'ccmp+tkip':
		config.wpa_pairwise = 'CCMP TKIP';
		break;

	case 'ccmp256':
		config.wpa_pairwise = 'CCMP-256';
		break;

	case 'aes':
	case 'ccmp':
		config.wpa_pairwise = 'CCMP';
		break;

	case 'tkip':
		config.wpa_pairwise = 'TKIP';
		break;

	case 'gcmp256':
		config.wpa_pairwise = 'GCMP-256';
		break;

	case 'gcmp':
		config.wpa_pairwise = 'GCMP';
		break;
	}

	if (!config.wpa)
		config.wpa_pairwise ??= null;
	else if (dev_config.band == '60g')
		config.wpa_pairwise ??= 'GCMP';
	else if (config.gcmp256 && phy_features?.cipher_gcmp256)
		config.wpa_pairwise ??= 'GCMP-256 CCMP';
	else
		config.wpa_pairwise ??= 'CCMP';
}

function wpa_key_mgmt(config, band) {
	if (!config.wpa)
		return;

	switch(config.auth_type) {
	case 'psk':
	case 'psk2':
		append_value(config, 'wpa_key_mgmt', 'WPA-PSK');
		if (config.wpa >= 2 && config.ieee80211r)
			append_value(config, 'wpa_key_mgmt', 'FT-PSK');
		if (config.ieee80211w)
			append_value(config, 'wpa_key_mgmt', 'WPA-PSK-SHA256');
		break;

	case 'eap':
		append_value(config, 'wpa_key_mgmt', 'WPA-EAP');
		if (config.wpa >= 2 && config.ieee80211r)
			append_value(config, 'wpa_key_mgmt', 'FT-EAP');
		if (config.ieee80211w)
			append_value(config, 'wpa_key_mgmt', 'WPA-EAP-SHA256');
		break;

	case 'eap192':
		append_value(config, 'wpa_key_mgmt', 'WPA-EAP-SUITE-B-192');
		if (config.ieee80211r)
			append_value(config, 'wpa_key_mgmt', 'FT-EAP-SHA384');
		break;

	case 'eap-eap2':
		append_value(config, 'wpa_key_mgmt', 'WPA-EAP-SHA256');
		if (config.ieee80211r)
			append_value(config, 'wpa_key_mgmt', 'FT-EAP');

		append_value(config, 'wpa_key_mgmt', 'WPA-EAP');
		break;

	case 'eap2':
		append_value(config, 'wpa_key_mgmt', 'WPA-EAP-SHA256');
		if (config.ieee80211r)
			append_value(config, 'wpa_key_mgmt', 'FT-EAP');
		break;

	case 'sae':
		append_value(config, 'wpa_key_mgmt', 'SAE');
		if (config.sae_ext_key)
			append_value(config, 'wpa_key_mgmt', 'SAE-EXT-KEY');
		if (config.ieee80211r) {
			append_value(config, 'wpa_key_mgmt', 'FT-SAE');
			if (config.sae_ext_key)
				append_value(config, 'wpa_key_mgmt', 'FT-SAE-EXT-KEY');
		}
		break;

	case 'psk-sae':
		append_value(config, 'wpa_key_mgmt', 'SAE');
		if (config.sae_ext_key)
			append_value(config, 'wpa_key_mgmt', 'SAE-EXT-KEY');
		if (config.ieee80211r) {
			append_value(config, 'wpa_key_mgmt', 'FT-SAE');
			if (config.sae_ext_key)
				append_value(config, 'wpa_key_mgmt', 'FT-SAE-EXT-KEY');
		}

		append_value(config, 'wpa_key_mgmt', 'WPA-PSK');
		if (config.ieee80211w)
			append_value(config, 'wpa_key_mgmt', 'WPA-PSK-SHA256');
		if (config.ieee80211r)
			append_value(config, 'wpa_key_mgmt', 'FT-PSK');
		break;

	case 'psk-sae-compat':
		if (band == '6g') {
			append_value(config, 'wpa_key_mgmt', 'SAE');
			if (config.ieee80211r)
				append_value(config, 'wpa_key_mgmt', 'FT-SAE');

			if (config.sae_ext_key) {
				append_value(config, 'rsn_override_key_mgmt_2', 'SAE-EXT-KEY');
				if (config.ieee80211r)
					append_value(config, 'rsn_override_key_mgmt_2', 'FT-SAE-EXT-KEY');
			}
		} else {
			append_value(config, 'wpa_key_mgmt', 'WPA-PSK');
			if (config.ieee80211w)
				append_value(config, 'wpa_key_mgmt', 'WPA-PSK-SHA256');
			if (config.ieee80211r)
				append_value(config, 'wpa_key_mgmt', 'FT-PSK');

			append_value(config, 'rsn_override_key_mgmt', 'SAE');
			if (config.ieee80211r)
				append_value(config, 'rsn_override_key_mgmt', 'FT-SAE');

			if (config.sae_ext_key) {
				append_value(config, 'rsn_override_key_mgmt_2', 'SAE-EXT-KEY');
				if (config.ieee80211r)
					append_value(config, 'rsn_override_key_mgmt_2', 'FT-SAE-EXT-KEY');
			}
		}
		break;

	case 'owe':
		append_value(config, 'wpa_key_mgmt', 'OWE');
		break;

	case 'dpp':
		append_value(config, 'wpa_key_mgmt', 'DPP');
		break;
	}

	if (config.dpp && config.auth_type != 'dpp')
		append_value(config, 'wpa_key_mgmt', 'DPP');

	if (config.fils) {
		switch(config.auth_type) {
		case 'eap192':
			append_value(config, 'wpa_key_mgmt', 'FILS-SHA384');
			if (config.ieee80211r)
				append_value(config, 'wpa_key_mgmt', 'FT-FILS-SHA384');
			break;

		case 'eap-eap2':
		case 'eap2':
		case 'eap':
			append_value(config, 'wpa_key_mgmt', 'FILS-SHA256');
			if (config.ieee80211r)
				append_value(config, 'wpa_key_mgmt', 'FT-FILS-SHA256');
			break;
		}
	}

	config.key_mgmt = config.wpa_key_mgmt;
}
return { parse_encryption, wpa_key_mgmt, prepare: config => { config.macaddr ??= '02:00:00:00:00:02'; } }; })();
let ap = (function() {
function iface_setup(config, phy, num_global_macaddr, macaddr_base) {
	switch(config.fixup) {
	case 'owe':
		config.ignore_broadcast_ssid = true;
		config.ssid = config.ssid + 'OWE';
		break;

	case 'owe-transition':
		let ifname = config.ifname;
		config.ifname = config.owe_transition_ifname;
		config.owe_transition_ifname = ifname;
		config.owe_transition_ssid = config.ssid + 'OWE';
		config.encryption = 'none';
		config.ignore_broadcast_ssid = false;
		/* the transition BSS needs its own address, not the main BSS's */
		config.macaddr = null;
		delete config.default_macaddr;
		delete config.random_macaddr;
		iface.prepare(config, phy, num_global_macaddr, macaddr_base);
		break;
	}

	comment('Setup interface: ' + config.ifname);

	config.bridge = config.network_bridge;
	config.snoop_iface = config.network_ifname;
	if (!config.wds)
		config.wds_bridge = null;
	else
		config.wds_sta = true;

	if (!config.idx)
		append('interface', config.ifname);
	else
		append('bss', config.ifname);

	if (config.multicast_to_unicast || config.proxy_arp)
		config.ap_isolate = 1;

	if (config.proxy_arp)
		set_default(config, 'na_mcast_to_ucast', true);

	append('bssid', config.macaddr);
	config.ssid2 = config.ssid;
	config.wmm_enabled = 1;
	append_string_vars(config, [ 'ssid2' ]);

	/* vendor_elements is a single concatenated hex blob, not one per line */
	if (type(config.vendor_elements) == 'array')
		config.vendor_elements = join('', config.vendor_elements);

	append_vars(config, [
		'ctrl_interface', 'ap_isolate', 'max_num_sta', 'ap_max_inactivity', 'airtime_bss_weight',
		'airtime_bss_limit', 'airtime_sta_weight', 'bss_load_update_period', 'chan_util_avg_period',
		'disassoc_low_ack', 'skip_inactivity_poll', 'ignore_broadcast_ssid', 'uapsd_advertisement_enabled',
		'utf8_ssid', 'multi_ap', 'multi_ap_vlanid', 'multi_ap_profile', 'tdls_prohibit', 'bridge',
		'wds_sta', 'wds_bridge', 'snoop_iface', 'vendor_elements', 'nas_identifier', 'radius_acct_interim_interval',
		'ocv', 'spp_amsdu', 'multicast_to_unicast', 'preamble', 'proxy_arp', 'per_sta_vif', 'mbo',
		'bss_transition', 'wnm_sleep_mode', 'wnm_sleep_mode_no_keys', 'qos_map_set', 'max_listen_int',
		'dtim_period', 'wmm_enabled', 'start_disabled', 'na_mcast_to_ucast', 'no_probe_resp_if_max_sta',
	]);
}

function iface_authentication_server(config) {
	for (let server in config.auth_server_addr) {
		append('auth_server_addr', server);
		append_vars(config, [ 'auth_server_port', 'auth_server_shared_secret' ]);
	}

	append_list(config, [ 'radius_auth_req_attr' ]);
}

function iface_accounting_server(config) {
	for (let server in config.acct_server_addr) {
		append('acct_server_addr', server);
		append_vars(config, [ 'acct_server_port', 'acct_server_shared_secret' ]);
	}

	append_list(config, [ 'radius_acct_req_attr' ]);
}

function iface_auth_type(config, band) {
	if (config.auth_type in [ 'sae', 'owe', 'eap2', 'eap192', 'dpp' ])
		config.ieee80211w = 2;

	if (config.auth_type in [ 'psk-sae', 'eap-eap2' ])
		set_default(config, 'ieee80211w', 1);

	if (config.auth_type == 'psk-sae-compat') {
		if (band == '6g') {
			set_default(config, 'ieee80211w', 2);
		} else {
			set_default(config, 'ieee80211w', 0);
			config.rsn_override_mfp = 2;
			config.rsn_override_omit_rsnxe = 1;
		}
		if (config.rsn_override_pairwise_2)
			config.rsn_override_mfp_2 = 2;
	}

	if (config.auth_type == 'owe') {
		set_default(config, 'owe_groups', '19 20 21');
		set_default(config, 'owe_ptk_workaround', 1);
	}

	if (config.auth_type in [ 'sae', 'psk-sae', 'psk-sae-compat' ]) {
		config.sae_require_mfp = 1;
		set_default(config, 'sae_groups', '19 20 21');
		if (!config.ppsk) {
			if (band == '6g')
				set_default(config, 'sae_pwe', 1);
			else
				set_default(config, 'sae_pwe', 2);
		}
	}

	if (config.own_ip_addr)
		config.dynamic_own_ip_addr = null;

	if (!config.wpa)
		config.wpa_disable_eapol_key_retries = null;

	switch(config.auth_type) {
	case 'none':
	case 'owe':
		config.wps_possible = 1;
		config.wps_state = 1;

		append_string_vars(config, [ 'owe_transition_ssid' ]);
		append_vars(config, [
			'owe_transition_bssid', 'owe_transition_ifname',
		]);
		break;

	case 'dpp':
		append_vars(config, [
			'dpp_connector', 'dpp_csign', 'dpp_netaccesskey',
		]);
		break;

	case 'psk':
	case 'psk2':
	case 'sae':
	case 'psk-sae':
	case 'psk-sae-compat':
		config.vlan_possible = 1;
		config.wps_possible = 1;

		if (config.ppsk) {
			iface_authentication_server(config);
			config.macaddr_acl = 2;
			config.wpa_psk_radius = 2;
		} else if (length(config.key) == 64) {
			config.wpa_psk = config.key;
		} else if (length(config.key) >= 8 && length(config.key) <= 63) {
			config.wpa_passphrase = config.key;
		} else if (config.key) {
			 netifd.setup_failed('INVALID_WPA_PSK');
		}

		if (config.auth_type in [ 'psk', 'psk-sae', 'psk-sae-compat' ] && band != '6g') {
			set_default(config, 'wpa_psk_file', `/var/run/hostapd-${config.ifname}.psk`);
			touch_file(config.wpa_psk_file);
		}

		if (config.auth_type in [ 'sae', 'psk-sae', 'psk-sae-compat' ]) {
			set_default(config, 'sae_password_file', `/var/run/hostapd-${config.ifname}.sae`);
			touch_file(config.sae_password_file);
		}
		break;

	case 'eap':
	case 'eap2':
	case 'eap-eap2':
	case 'eap192':
		config.vlan_possible = 1;

		if (config.fils) {
			set_default(config, 'erp_domain', config.mobility_domain);
			set_default(config, 'erp_domain', substr(md5(config.ssid + '\n'), 0, 8));
			set_default(config, 'fils_realm', config.erp_domain);
			set_default(config, 'erp_send_reauth_start', 1);
			set_default(config, 'fils_cache_id', substr(md5(config.fils_realm + '\n'), 0, 4));
		}

		if (!config.eap_server) {
			iface_authentication_server(config);
			iface_accounting_server(config);
		}

		if (config.radius_das_client && config.radius_das_secret) {
			set_default(config, 'radius_das_port', 3799);
			config.radius_das_client = config.radius_das_client + ' ' + config.radius_das_secret;
		}

		set_default(config, 'eapol_version', config.wpa & 1);
		if (!config.eapol_version)
			config.eapol_version = null;
		append('eapol_key_index_workaround', '1');
		append('ieee8021x', '1');

		break;
	}

	append_vars(config, [
		'sae_require_mfp', 'sae_password_file', 'sae_pwe', 'sae_groups', 'sae_track_password', 'time_advertisement', 'time_zone',
		'wpa_group_rekey', 'wpa_ptk_rekey', 'wpa_gmk_rekey', 'wpa_strict_rekey',
		'macaddr_acl', 'wpa_psk_radius', 'wpa_psk', 'wpa_passphrase', 'wpa_psk_file',
		'eapol_version', 'dynamic_vlan', 'radius_request_cui', 'eap_reauth_period',
		'radius_das_client', 'radius_das_port', 'owe_groups', 'owe_ptk_workaround', 'own_ip_addr', 'dynamic_own_ip_addr',
		'wpa_disable_eapol_key_retries', 'auth_algs', 'wpa', 'wpa_pairwise',
		'erp_domain', 'fils_realm', 'erp_send_reauth_start', 'fils_cache_id'
	]);

	if (config.dpp && config.auth_type != 'dpp')
		append_vars(config, [
			'dpp_connector', 'dpp_csign', 'dpp_netaccesskey',
		]);
}

function iface_ppsk(config) {
	if (!(config.auth_type in [ 'none', 'owe', 'psk', 'sae', 'psk-sae', 'psk-sae-compat', 'wep' ]) || !config.auth_server_addr)
		return;

	iface_authentication_server(config);
	append('macaddr_acl', '2');
}

function iface_wps(config) {
	push_config(config, 'config_methods', 'wps_pushbutton', 'push_button');
	push_config(config, 'config_methods', 'wps_label', 'label');

	if (config.multi_ap == 1)
		config.wps_possible = false;

	if (config.wps_possible && length(config.config_methods)) {
		config.eap_server = 1;
		set_default(config, 'wps_state', 2);

		if (config.ext_registrar && config.network_bridge)
			set_default(config, 'upnp_iface', config.network_bridge);

		if (config.multi_ap && config.multi_ap_backhaul_ssid) {
			append_string_vars(config, [ 'multi_ap_backhaul_ssid' ]);
			if (length(config.multi_ap_backhaul_key) == 64)
				append('multi_ap_backhaul_wpa_psk', config.multi_ap_backhaul_key);
			else if (length(config.multi_ap_backhaul_key) > 8)
				append('multi_ap_backhaul_wpa_passphrase', config.multi_ap_backhaul_key);
			else
				netifd.setup_failed('INVALID_WPA_PSK');
		}

		append_vars(config, [
			'wps_state', 'device_type', 'device_name', 'config_methods', 'wps_independent', 'eap_server',
			'ap_pin', 'ap_setup_locked', 'upnp_iface', 'uuid'
		]);
	}
}

function iface_rrm(config) {
	set_default(config, 'rrm_neighbor_report', config.ieee80211k);
	set_default(config, 'rrm_beacon_report', config.ieee80211k);

	append_vars(config, [
		'rrm_neighbor_report', 'rrm_beacon_report', 'rnr', 'ftm_responder',
	]);
}

function iface_ftm(config, phy_features) {
	if (!phy_features.ftm_responder || !config.ftm_responder)
		return;

	append_vars(config, [
		'ftm_responder', 'lci', 'civic'
	]);
}

function iface_macfilter(config) {
	let path = `/var/run/hostapd-${config.ifname}.maclist`;

	switch(config.macfilter) {
	case 'allow':
		append('accept_mac_file', path);
		append('macaddr_acl', 1);
		config.vlan_possible = 1;
		break;

	case 'deny':
		append('deny_mac_file', path);
		append('macaddr_acl', 0);
		break;

	default:
		return;
	}

	let file = fs.open(path, 'w');
	if (!file) {
		warn(`Failed to open ${path}`);
		return;
	}

	if (config.maclist)
		file.write(join('\n', config.maclist));

	let macfile = fs.readfile(config.macfile);
	if (macfile)
		file.write(macfile);
	file.close();
}

function iface_vlan(interface, config, vlans) {
	let path = `/var/run/hostapd-${config.ifname}.vlan`;

	let file = fs.open(path, 'w');
	for (let k, vlan in vlans)
		if (vlan.config.name && vlan.config.vid) {
			let ifname = `${config.ifname}-${vlan.config.name}`;
			file.write(`${vlan.config.vid} ${ifname}\n`);
			netifd.set_vlan(interface, ifname, k);
		}
	file.close();

	set_default(config, 'vlan_file', path);
	append_vars(config, [ 'vlan_file' ]);

	if (!config.vlan_possible || !config.dynamic_vlan)
		return;

	set_default(config, 'vlan_no_bridge', !config.vlan_bridge);

	append_vars(config, [
		'dynamic_vlan', 'vlan_naming', 'vlan_bridge', 'vlan_no_bridge',
		'vlan_tagged_interface'
	]);
}

function iface_wpa_stations(config, stas) {
	let path = `/var/run/hostapd-${config.ifname}.psk`;

	let file = fs.open(path, 'w');
	for (let k, sta in stas)
		if (sta.config.mac && sta.config.key) {
			for (let mac in sta.config.mac) {
				let station = `${mac} ${sta.config.key}\n`;
				if (sta.config.vid)
					station = `vlanid=${sta.config.vid} ` + station;
				file.write(station);
			}
		}
	file.close();

	set_default(config, 'wpa_psk_file', path);
}

function iface_sae_stations(config, stas) {
	let path = `/var/run/hostapd-${config.ifname}.sae`;

	let file = fs.open(path, 'w');
	for (let k, sta in stas)
		if (sta.config.mac && sta.config.key) {
			for (let mac in sta.config.mac) {
				if (mac == '00:00:00:00:00:00')
					mac = 'ff:ff:ff:ff:ff:ff';

				let station = `${sta.config.key}|mac=${mac}`;
				if (sta.config.vid)
					station = station + `|vlanid=${sta.config.vid}`;
				station = station + '\n';
				file.write(station);
			}
		}
	file.close();

	set_default(config, 'sae_password_file', path);
}

function iface_eap_server(config) {
	if (!config.eap_server)
		return;

	set_default(config, 'eap_server', true);
	set_default(config, 'eap_server_erp', true);

	append_vars(config, [
		'eap_server', 'eap_server_erp', 'eap_user_file', 'ca_cert', 'server_cert',
		'private_key', 'private_key_passwd', 'server_id',
	]);
}

function iface_roaming(config) {
	if (!config.ieee80211r || config.wpa < 2)
		return;

	set_default(config, 'mobility_domain', substr(md5(config.ssid + '\n'), 0, 4));
	set_default(config, 'ft_psk_generate_local', config.auth_type == 'psk');
	set_default(config, 'ft_iface', config.network_ifname);

	if (!config.ft_psk_generate_local) {
		if (!config.r0kh || !config.r1kh) {
			if (!config.auth_secret && !config.key)
				netifd.setup_failed('FT_KEY_CANT_BE_DERIVED');

			let ft_key = md5(`${config.mobility_domain}/${config.auth_secret ?? config.key}`);

			set_default(config, 'r0kh', [ 'ff:ff:ff:ff:ff:ff,*,' + ft_key ]);
			set_default(config, 'r1kh', [ '00:00:00:00:00:00,00:00:00:00:00:00,' + ft_key ]);
		}

		for (let name in [ 'r0kh', 'r1kh' ])
			for (let val in config[name])
				append(name, join(' ', split(val, ',', 3)));

		append_vars(config, [
			'r1_key_holder', 'r0_key_lifetime', 'pmk_r1_push'
		]);
	}

	append_vars(config, [
		'mobility_domain', 'ft_psk_generate_local', 'ft_over_ds', 'reassociation_deadline',
		'ft_iface'
	]);
}

function default_group_mgmt_cipher(config) {
	let p = ' ' + (config.wpa_pairwise ?? '') + ' ';

	if (wildcard(p, '* CCMP *') || wildcard(p, '* TKIP *'))
		return 'AES-128-CMAC';
	if (wildcard(p, '* CCMP-256 *'))
		return 'BIP-CMAC-256';
	if (wildcard(p, '* GCMP *'))
		return 'BIP-GMAC-128';
	if (wildcard(p, '* GCMP-256 *'))
		return 'BIP-GMAC-256';
	return 'AES-128-CMAC';
}

function iface_mfp(config) {
	let override_mfp = config.rsn_override_mfp || config.rsn_override_mfp_2;

	if ((!config.ieee80211w && !override_mfp) || config.wpa < 2) {
		append('ieee80211w', 0);
		return;
	}

	config.group_mgmt_cipher = config.ieee80211w_mgmt_cipher ?? default_group_mgmt_cipher(config);

	set_default(config, 'beacon_prot', 1);

	append_vars(config, [
		'ieee80211w', 'group_mgmt_cipher', 'beacon_prot',
		'assoc_sa_query_max_timeout', 'assoc_sa_query_retry_timeout'
	]);
}

function iface_transition_disable(config) {
	if (config.wpa < 2)
		return;

	let list = config.transition_disable;
	if (!list || !length(list))
		return;

	for (let s in list)
		if (s == 'off' || s == '0')
			return;

	let bits = 0;
	for (let s in list) {
		if (s == 'on' || s == '1') {
			bits = 0;
			switch (config.auth_type) {
			case 'sae':    bits = 0x01; break;
			case 'eap2':
			case 'eap192': bits = 0x04; break;
			case 'owe':    if (!config.owe_transition) bits = 0x08; break;
			}
			break;
		}
		switch (s) {
		case 'sae':    bits |= 0x01; break;
		case 'sae-pk': bits |= 0x02; break;
		case 'wpa3':   bits |= 0x04; break;
		case 'owe':    bits |= 0x08; break;
		}
	}

	if (bits)
		append('transition_disable', sprintf('0x%02x', bits));
}

function iface_key_caching(config) {
	if (config.wpa < 2)
		return;

	if (config.network_bridge && config.rsn_preauth) {
		set_default(config, 'okc', true);
		config.rsn_preauth_interfaces = config.network_bridge;

		append_vars(config, [
			'rsn_preauth', 'rsn_preauth_interfaces'
		]);
	} else {
		set_default(config, 'okc', (config.auth_type in  [ 'sae', 'psk-sae', 'psk-sae-compat', 'owe' ]));
	}

	if (!config.okc && !config.fils)
		config.disable_pmksa_caching = 1;

	append_vars(config, [
		'okc', 'disable_pmksa_caching'
	]);
}

function iface_hs20(config) {
	if (!config.hs20)
		return;

	append_vars(config, [
		'hs20', 'disable_dgaf', 'anqp_domain_id', 'hs20_deauth_req_timeout',
		'hs20_wan_metrics', 'hs20_operating_class', 'hs20_t_c_filename', 'hs20_t_c_timestamp',
		'hs20_t_c_server_url'
	]);
	append_list(config, [ 'hs20_conn_capab' ]);
}

function iface_interworking(config) {
	if (!config.iw_enabled)
		return;

	config.interworking = true;

	if (config.domain_name)
		config.domain_name = join(',', config.domain_name);

	if (config.anqp_3gpp_cell_net)
		config.anqp_3gpp_cell_net = join(';', config.anqp_3gpp_cell_net);

	append_vars(config, [
		'interworking', 'internet', 'asra', 'uesa', 'access_network_type', 'hessid', 'venue_group',
		'venue_type', 'network_auth_type', 'gas_address3', 'roaming_consortium',
		'domain_name', 'anqp_3gpp_cell_net',
	]);
	append_list(config, [ 'anqp_elem', 'nai_realm', 'venue_name', 'venue_url' ]);
}

function iface_rates(config) {
	for (let key in [ 'supported_rates', 'basic_rates' ])
		append(key, map(config[key], x => x / 100))
}

function generate(interface, data, config, vlans, stas, phy_features) {
	config.ctrl_interface = '/var/run/hostapd';

	config.start_disabled = data.ap_start_disabled;
	iface_setup(config, data.phy + data.phy_suffix, data.config.num_global_macaddr, data.config.macaddr_base);

	iface.parse_encryption(config, data.config, phy_features);
	if (data.config.band == '6g') {
		if (config.auth_type == 'psk-sae')
			config.auth_type = 'sae';
		if (config.auth_type == 'eap-eap2')
			config.auth_type = 'eap2';
	}

	if (config.auth_type in [ 'psk', 'psk-sae', 'psk-sae-compat' ] && data.config.band != '6g')
		iface_wpa_stations(config, stas);
	if (config.auth_type in [ 'sae', 'psk-sae', 'psk-sae-compat' ])
		iface_sae_stations(config, stas);

	iface_rates(data.config);

	iface_auth_type(config, data.config.band);

	iface_accounting_server(config);

	iface_ppsk(config);

	iface_wps(config);

	iface_rrm(config);

	iface_ftm(config, phy_features);

	iface_macfilter(config);

	iface_vlan(interface, config, vlans);

	iface_eap_server(config);

	iface_roaming(config);

	iface_mfp(config);

	iface_transition_disable(config);

	iface_key_caching(config);

	iface_hs20(config);

	iface_interworking(config);

	iface.wpa_key_mgmt(config, data.config.band);
	append_vars(config, [
		'wpa_key_mgmt',
	]);

	if (config.rsn_override_key_mgmt && config.rsn_override_pairwise && config.rsn_override_mfp) {
		append_vars(config, [
			'rsn_override_key_mgmt',
			'rsn_override_pairwise',
			'rsn_override_mfp'
		]);
	}

	if (config.rsn_override_key_mgmt_2 && config.rsn_override_pairwise_2 && config.rsn_override_mfp_2) {
		append_vars(config, [
			'rsn_override_key_mgmt_2',
			'rsn_override_pairwise_2',
			'rsn_override_mfp_2'
		]);
	}

	if (config.rsn_override_omit_rsnxe) {
		append_vars(config, ['rsn_override_omit_rsnxe']);
	}

	/* raw options */
	for (let raw in config.hostapd_bss_options)
		append_raw(raw);

	if (config.mlo) {
		append_raw('mld_ap=1');
		if (data.config.radio != null)
			append_raw('mld_link_id=' + data.config.radio);
	}

	if (config.default_macaddr)
		append_raw('#default_macaddr');
	else if (config.random_macaddr)
		append_raw('#random_macaddr');
}
return { generate }; })();
function canonical(value) {
	if (type(value) == 'array')
		return map(value, canonical);
	if (type(value) != 'object')
		return value;

	let result = {};
	for (let key in sort(keys(value)))
		result[key] = canonical(value[key]);
	return result;
}

function mld_config_id(config) {
	let common = { ...config };
	// netifd adds these descriptor fields and assigns ifname/MAC per link.
	for (let field in [ 'phy', 'radio_config', '4addr', 'ifname', 'macaddr' ])
		delete common[field];
	return sha256(sprintf('%J', canonical(common)));
}
function mlo_enabled(value) {
	return value === true || value === 1 || value === '1';
}

function mlo_radio_index(value) {
	if (value == null || !match('' + value, /^(0|[1-9][0-9]*)$/))
		return null;

	value = +value;
	return value <= 30 ? value : null;
}

function mlo_radio_list(config, owner) {
	if (type(config.radios) != 'array')
		return { error: `MLO owner ${owner} must declare a radio list` };

	let radios = [];
	let seen = {};
	for (let value in config.radios) {
		let radio = mlo_radio_index(value);
		if (radio == null)
			return { error: `MLO owner ${owner} has invalid radio index ${value}` };
		if (seen[radio])
			return { error: `MLO owner ${owner} declares radio index ${radio} more than once` };

		seen[radio] = true;
		push(radios, radio);
	}

	sort(radios, (a, b) => a - b);
	if (length(radios) < 2)
		return { error: `MLO owner ${owner} requires at least two unique radios` };

	return { radios };
}

function mlo_same_value(a, b) {
	let a_type = type(a);
	if (a_type != type(b))
		return false;

	if (a_type == 'array') {
		if (length(a) != length(b))
			return false;
		for (let i = 0; i < length(a); i++)
			if (!mlo_same_value(a[i], b[i]))
				return false;
		return true;
	}

	if (a_type == 'object') {
		let a_keys = keys(a);
		let b_keys = keys(b);
		if (length(a_keys) != length(b_keys))
			return false;
		for (let key in a_keys)
			if (!exists(b, key) || !mlo_same_value(a[key], b[key]))
				return false;
		return true;
	}

	return a == b;
}

function mlo_same_common_config(a, b) {
	let a_common = {};
	let b_common = {};
	for (let field, value in a)
		if (!mlo_link_local_fields[field])
			a_common[field] = value;
	for (let field, value in b)
		if (!mlo_link_local_fields[field])
			b_common[field] = value;
	return mlo_same_value(a_common, b_common);
}

function mlo_country(config) {
	let country = uc('' + (config.country_code ?? config.country ?? ''));
	return !country || country == '00' ? null : country;
}

function mlo_validate_device(name, config) {
	if (mlo_enabled(config.disabled))
		return `${name} is disabled`;
	if (!mlo_country(config))
		return `${name} requires an explicit regulatory country; world regdomain 00 is not valid for MLO`;
	if (config.channel == null || config.channel == 'auto' || +config.channel <= 0)
		return `${name} requires a fixed channel for MLO`;
	if (!match('' + (config.htmode ?? ''), /^EHT(20|40|80|160|320)$/))
		return `${name} must use an EHT width for MLO; current mode is ${config.htmode ?? 'unset'}`;
	if (mlo_radio_index(config.radio) == 0 && config.htmode != 'EHT20')
		return `${name} must use EHT20 for a reliable 2.4GHz MLO link; this stack cannot recover an MLD from mandatory 20/40 coexistence fallback`;
}

function mlo_validate_iface(owner, config) {
	let ifname = config.ifname;
	if (type(ifname) != 'string' || !length(ifname) || length(ifname) > 15)
		return `MLO owner ${owner} requires one valid interface name of at most 15 bytes`;
	if (type(config.ssid) != 'string' || !length(config.ssid) || length(config.ssid) > 32)
		return `MLO owner ${owner} requires an SSID of 1 to 32 bytes`;

	let encryption_parts = split(lc('' + (config.encryption ?? '')), '+');
	let encryption = encryption_parts[0];
	if (!(encryption in [ 'sae', 'owe', 'wpa3', 'wpa3-192' ]))
		return `MLO owner ${owner} requires WPA3-SAE, OWE, or WPA3 Enterprise security`;
	if ('tkip' in encryption_parts)
		return `MLO owner ${owner} cannot use TKIP; MLO requires CCMP or GCMP`;
	if (+config.ieee80211w != 2)
		return `MLO owner ${owner} requires 802.11w management frame protection`;

	if (encryption == 'sae') {
		let key_len = type(config.key) == 'string' ? length(config.key) : 0;
		if (!((key_len >= 8 && key_len <= 63) ||
		      (key_len == 64 && match(config.key, /^[0-9A-Fa-f]{64}$/))))
			return `MLO owner ${owner} requires a valid WPA3-SAE key`;
	}
}

function mlo_status_inventory(status) {
	if (type(status) != 'object')
		return { error: 'network.wireless status is unavailable', retryable: true };

	let inventory = {
		radios: {},
		claims_by_owner: {},
		claims_by_radio: {},
		ifname_owner: {}
	};

	for (let device, radio_data in status) {
		let radio = mlo_radio_index(radio_data?.config?.radio);
		if (radio == null)
			continue;
		if (inventory.radios[radio])
			return { error: `physical radio index ${radio} is assigned to both ${inventory.radios[radio].name} and ${device}` };

		inventory.radios[radio] = { name: device, data: radio_data };
		if (type(radio_data.interfaces) != 'array')
			return { error: `${device} has no inspectable interface inventory`, retryable: true };

		for (let interface in radio_data.interfaces) {
			let config = interface?.config;
			let owner = interface.section;
			let is_mlo = mlo_enabled(config?.mlo) && config.mode == 'ap';
			let ifname = config?.ifname ?? interface?.ifname;
			if (is_mlo && (type(owner) != 'string' || !length(owner)))
				return { error: `${device} contains an MLO link without a logical owner` };
			if (is_mlo && (type(ifname) != 'string' || !length(ifname)))
				return { error: `MLO owner ${owner} has no shared interface name on ${device}` };
			if (type(ifname) == 'string' && length(ifname)) {
				let prior = inventory.ifname_owner[ifname];
				if (prior && !(is_mlo && prior.mlo && prior.owner == owner)) {
					if (is_mlo && prior.mlo)
						return { error: `MLD interface ${ifname} is claimed by both ${prior.owner} and ${owner}` };
					if (is_mlo || prior.mlo)
						return {
							error: `MLD interface ${ifname} conflicts with non-MLO interface ${prior.mlo ? owner : prior.owner}`,
							retryable: prior.owner == owner
						};
					return { error: `interface ${ifname} is claimed by both ${prior.owner} and ${owner}` };
				}

				inventory.ifname_owner[ifname] ??= { owner, mlo: is_mlo };
			}

			if (!is_mlo)
				continue;

			let claim = { owner, ifname, radio, device, config };
			inventory.claims_by_owner[owner] ??= [];
			inventory.claims_by_radio[radio] ??= [];
			push(inventory.claims_by_owner[owner], claim);
			push(inventory.claims_by_radio[radio], claim);
		}
	}

	for (let radio, claims in inventory.claims_by_radio) {
		let owners = {};
		for (let claim in claims) {
			if (owners[claim.owner])
				return { error: `MLO owner ${claim.owner} has duplicate link entries on radio index ${radio}` };
			owners[claim.owner] = true;
		}

		let owner_names = keys(owners);
		if (length(owner_names) > 1)
			return { error: `radio index ${radio} is claimed by multiple MLO owners: ${join(', ', owner_names)}` };
	}

	return inventory;
}

function mlo_same_radio_set(a, b) {
	return length(a) == length(b) && mlo_same_value(a, b);
}

function mlo_local_links(data) {
	let local = [];
	for (let key, interface in data?.interfaces ?? {}) {
		let config = interface?.config;
		if (!mlo_enabled(config?.mlo) || config.mode != 'ap')
			continue;
		push(local, { key, owner: interface.name, config });
	}

	return local;
}

function mlo_status_generation_error(data, status) {
	let local = mlo_local_links(data);
	if (!length(local))
		return null;

	let current_radio = mlo_radio_index(data?.config?.radio);
	if (current_radio == null)
		return null;

	let inventory = mlo_status_inventory(status);
	if (inventory.error)
		return inventory.retryable ? inventory.error : null;

	let current_entry = inventory.radios[current_radio];
	if (!current_entry)
		return `current radio index ${current_radio} is absent from network.wireless status`;

	let payload_country = mlo_country(data.config);
	let status_country = mlo_country(current_entry.data.config);
	if (+current_entry.data.config.channel != +data.config.channel ||
	    current_entry.data.config.htmode != data.config.htmode ||
	    (payload_country && status_country && payload_country != status_country))
		return `current radio index ${current_radio} payload does not match network.wireless status`;

	for (let local_link in local) {
		let owner = local_link.owner;
		if (type(owner) != 'string' || !length(owner))
			continue;

		let declared = mlo_radio_list(local_link.config, owner);
		if (declared.error)
			continue;

		let claims = inventory.claims_by_owner[owner] ?? [];
		let actual = map(claims, claim => claim.radio);
		sort(actual, (a, b) => a - b);
		if (!mlo_same_radio_set(declared.radios, actual))
			return `MLO owner ${owner} link inventory is from another wireless configuration generation`;

		for (let claim in claims) {
			let claim_radios = mlo_radio_list(claim.config, owner);
			if (!claim_radios.error && !mlo_same_radio_set(declared.radios, claim_radios.radios))
				return `MLO owner ${owner} radio inventory is from another wireless configuration generation`;
			if (claim.ifname != local_link.config.ifname ||
			    !mlo_same_common_config(local_link.config, claim.config))
				return `MLO owner ${owner} link settings are from another wireless configuration generation`;
		}
	}

	return null;
}

function validate_mlo_config(data, status) {
	let local = mlo_local_links(data);

	if (!length(local))
		return null;

	let current_radio = mlo_radio_index(data?.config?.radio);
	if (current_radio == null)
		return 'the current MLO link has no valid physical radio index';

	let device_error = mlo_validate_device(`radio index ${current_radio}`, data.config);
	if (device_error)
		return device_error;

	let local_owner = {};
	let local_ifname = {};
	for (let link in local) {
		let owner = link.owner;
		if (type(owner) != 'string' || !length(owner))
			return `interface ${link.key} has no logical MLO owner`;
		if (local_owner[owner])
			return `MLO owner ${owner} has duplicate link entries on radio index ${current_radio}`;
		local_owner[owner] = true;

		let iface_error = mlo_validate_iface(owner, link.config);
		if (iface_error)
			return iface_error;

		let radio_list = mlo_radio_list(link.config, owner);
		if (radio_list.error)
			return radio_list.error;
		if (!(current_radio in radio_list.radios))
			return `MLO owner ${owner} does not include current radio index ${current_radio}`;

		let previous = local_ifname[link.config.ifname];
		if (previous && previous != owner)
			return `MLD interface ${link.config.ifname} is claimed by both ${previous} and ${owner}`;
		local_ifname[link.config.ifname] = owner;
	}

	let owners = keys(local_owner);
	if (length(owners) > 1)
		return `radio index ${current_radio} is claimed by multiple MLO owners: ${join(', ', owners)}`;

	let inventory = mlo_status_inventory(status);
	if (inventory.error)
		return inventory.error;
	let current_entry = inventory.radios[current_radio];
	if (!current_entry)
		return `current radio index ${current_radio} is absent from network.wireless status`;
	let status_error = mlo_validate_device(current_entry.name, current_entry.data.config);
	if (status_error)
		return status_error;
	if (+current_entry.data.config.channel != +data.config.channel ||
	    current_entry.data.config.htmode != data.config.htmode ||
	    mlo_country(current_entry.data.config) != mlo_country(data.config))
		return `current radio index ${current_radio} payload does not match network.wireless status`;

	for (let local_link in local) {
		let owner = local_link.owner;
		let declared = mlo_radio_list(local_link.config, owner);
		let claims = inventory.claims_by_owner[owner] ?? [];
		let actual = map(claims, claim => claim.radio);
		sort(actual, (a, b) => a - b);

		if (!mlo_same_radio_set(declared.radios, actual))
			return `MLO owner ${owner} declares radios ${join(',', declared.radios)} but has links on radios ${join(',', actual)}`;

		let country;
		for (let claim in claims) {
			let radio_entry = inventory.radios[claim.radio];
			if (!radio_entry)
				return `MLO owner ${owner} references unavailable radio index ${claim.radio}`;
			if (radio_entry.data.disabled || mlo_enabled(radio_entry.data.config?.disabled))
				return `${radio_entry.name} is disabled and cannot be used by MLO owner ${owner}`;

			let status_error = mlo_validate_device(radio_entry.name, radio_entry.data.config);
			if (status_error)
				return status_error;
			let iface_error = mlo_validate_iface(owner, claim.config);
			if (iface_error)
				return iface_error;

			let claim_radios = mlo_radio_list(claim.config, owner);
			if (claim_radios.error)
				return claim_radios.error;
			if (!mlo_same_radio_set(declared.radios, claim_radios.radios))
				return `MLO owner ${owner} has inconsistent radio lists across links`;

			let link_country = mlo_country(radio_entry.data.config);
			if (country && country != link_country)
				return `MLO owner ${owner} mixes regulatory countries ${country} and ${link_country}`;
			country = link_country;

			if (claim.ifname != local_link.config.ifname)
				return `MLO owner ${owner} has inconsistent MLD interface names across links`;
			if (!mlo_same_common_config(local_link.config, claim.config))
				return `MLO owner ${owner} has inconsistent SSID, security, or network configuration across links`;
		}
	}

	return null;
}

function mlo_setup_snapshot(data) {
	if (!length(mlo_local_links(data)))
		return null;

	// Keep the raw netifd view: schema defaults and iface.prepare mutate setup data.
	return json(sprintf('%J', { config: data.config, interfaces: data.interfaces }));
}

function validate_owe_transition(data) {
	for (let key, interface in data?.interfaces ?? {}) {
		let config = interface?.config;
		if (config?.mode != 'ap' || split(config.encryption ?? '', '+')[0] != 'owe')
			continue;
		if (!mlo_enabled(config.mlo) && data.config.band != '6g')
			continue;
		if (!mlo_enabled(config.owe_transition) &&
		    !config.owe_transition_ifname && !config.owe_transition_bssid)
			continue;

		netifd.setup_failed('INVALID_ENCRYPTION');
		die(`OWE transition is not supported on MLO or 6 GHz AP ${key}`);
	}
}

function validate_mlo_setup(data) {
	validate_owe_transition(data);

	let has_mlo_ap = false;
	for (let key, interface in data?.interfaces ?? {})
		if (mlo_enabled(interface?.config?.mlo) && interface.config.mode == 'ap') {
			has_mlo_ap = true;
			break;
		}

	if (!has_mlo_ap)
		return;

	let status;
	try {
		status = global.ubus.call('network.wireless', 'status');
	} catch (e) {
		die('Deferred MLO setup: network.wireless status query failed');
	}

	let generation_error = mlo_status_generation_error(data, status);
	if (generation_error)
		die(`Deferred MLO setup: ${generation_error}`);

	let error = validate_mlo_config(data, status);
	if (!error)
		return;

	netifd.setup_failed('INVALID_MLO_CONFIG');
	die(`Invalid MLO configuration: ${error}`);
}

function setup_interface(interface, data, config, vlans, stas, phy_features, fixup) {
	config = { ...config, fixup };

	config.idx = iface_idx++;
	ap.generate(interface, data, config, vlans, stas, phy_features);
}

function setup(data, mlo_snapshot) {
	let file_name = `/var/run/hostapd-${data.phy}${data.vif_phy_suffix}.conf`;

	mlo_snapshot ??= mlo_setup_snapshot(data);
	validate_mlo_setup(mlo_snapshot ?? data);

	flush_config();

	if (fs.stat(file_name))
		fs.rename(file_name, file_name + '.prev');

	data.config.phy = data.phy;

	generate(data.config);

	if (data.config.num_global_macaddr)
		append('\n#num_global_macaddr', data.config.num_global_macaddr);
	if (data.config.macaddr_base)
		append('\n#macaddr_base', data.config.macaddr_base);
	if (data.config.frequency)
		append('\n#frequency', data.config.frequency);
	if (data.channel_follow)
		append('\n#channel_follow', 1);

	let has_ap;
	for (let k, interface in data.interfaces) {
		if (interface.config.mode != 'ap')
			continue;

		interface.config.network_bridge = interface.bridge;
		interface.config.network_ifname = interface['bridge-ifname'];

		let owe = interface.config.encryption == 'owe' && interface.config.owe_transition;

		setup_interface(k, data, interface.config, interface.vlans, interface.stas, phy_features, owe ? 'owe' : null );
		if (owe)
			setup_interface(k, data, interface.config, interface.vlans, interface.stas, phy_features, 'owe-transition');
		if (mlo_enabled(interface.config.mlo))
			append('#mld_config_id', mld_config_id((mlo_snapshot ?? data).interfaces[k].config));
		has_ap = true;
	}

	let config = dump_config(file_name);

	let msg = {
		phy: data.phy,
		radio: data.config.radio,
		config: has_ap ? file_name : "",
		prev_config: file_name + '.prev'
	};
	if (!global.ubus.list('hostapd'))
		system('ubus wait_for hostapd');
	let ret = global.ubus.call('hostapd', 'config_set', msg);

	if (ret)
		netifd.add_process('/usr/sbin/hostapd', ret.pid, true, true);
	else
		netifd.setup_failed('HOSTAPD_START_FAILED');
}
function config_add_bss(config, name)
{
	let bss = {
		ifname: name,
		data: [],
		hash: {}
	};

	push(config.bss, bss);

	return bss;
}

function iface_load_config(phy, radio, filename)
{
	if (radio < 0)
		radio = null;

	let config = {
		phy,
		radio_idx: radio,
		radio: {
			data: []
		},
		bss: [],
		orig_file: filename,
	};

	let f = open(filename, "r");
	if (!f) {
		if (filename)
			config.load_error = true;
		return config;
	}

	let bss;
	let line;
	while ((line = rtrim(f.read("line"), "\n")) != null) {
		let val = split(line, "=", 2);
		if (!val[0])
			continue;

		if (substr(line, 0, 2) == "# ")
			continue;

		if (val[0] == "interface") {
			bss = config_add_bss(config, val[1]);
			break;
		}

		if (val[0] == "channel") {
			config.radio.channel = val[1];
			continue;
		}

		if (val[0] == "#frequency") {
			config.radio.frequency = int(val[1]);
			continue;
		}

		if (val[0] == "#channel_follow") {
			config.radio.channel_follow = int(val[1]) == 1;
			continue;
		}

		if (val[0] == "#num_global_macaddr")
			config[substr(val[0], 1)] = int(val[1]);
		else if (val[0] == "#macaddr_base")
			config[substr(val[0], 1)] = val[1];
		else if (val[0] == "mbssid")
			config[val[0]] = int(val[1]);

		push(config.radio.data, line);
	}

	while ((line = rtrim(f.read("line"), "\n")) != null) {
		if (line == "#default_macaddr")
			bss.default_macaddr = true;
		if (line == "#random_macaddr")
			bss.random_macaddr = true;

		let val = split(line, "=", 2);
		if (!val[0])
			continue;

		if (substr(line, 0, 2) == "# ")
			continue;

		if (val[0] == "bssid") {
			bss.bssid = lc(val[1]);
			continue;
		}

		if (val[0] == "nas_identifier")
			bss.nasid = val[1];

		if (val[0] == "mld_ap")
			bss[val[0]] = int(val[1]);
		if (val[0] == "#mld_config_id")
			bss.mld_config_id = val[1];

		if (val[0] == "ssid")
			bss.ssid = val[1];
		if (val[0] == "ssid2") {
			// wifi-scripts emits quoted printable strings or hexadecimal bytes.
			let value = val[1];
			bss.ssid = length(value) >= 2 && substr(value, 0, 1) == '"' &&
				substr(value, length(value) - 1) == '"' ?
				substr(value, 1, length(value) - 2) : hexdec(value, '');
		}

		if (val[0] == "bss") {
			bss = config_add_bss(config, val[1]);
			continue;
		}

		if (hostapd.data.file_fields[val[0]]) {
			if (val[0] == "rxkh_file") {
				bss.hash[val[0]] = hostapd.sha1(normalize_rxkhs(readfile(val[1])));
			} else {
				bss.hash[val[0]] = hostapd.sha1(readfile(val[1]));
			}
		}

		push(bss.data, line);
	}
	f.close();

	return config;
}

function mld_ssid_matches(data, bss)
{
	return type(data?.config?.ssid) != 'string' ||
		(type(bss.ssid) == 'string' && bss.ssid == data.config.ssid);
}

function mld_config_matches(data, bss)
{
	return mld_ssid_matches(data, bss) &&
		(!data?.config_id || bss.mld_config_id == data.config_id);
}
let profiles = [
  { name: 'sae', encryption: 'sae', mlo: true, extended: true, gcmp: true },
  { name: 'sae-ft', encryption: 'sae', mlo: true, extended: true, ft: true, gcmp: true },
  { name: 'owe', encryption: 'owe', mlo: true, gcmp: true },
  { name: 'enterprise', encryption: 'wpa3', mlo: true, gcmp: true },
  { name: 'enterprise192', encryption: 'wpa3-192', mlo: true, gcmp: true },
  { name: 'sae-explicit-off', encryption: 'sae', mlo: true,
    overrides: { gcmp256: false, sae_ext_key: false } },
  { name: 'sae-forced-ccmp', encryption: 'sae+ccmp', mlo: true, extended: true },
  { name: 'sae-forced-gcmp256', encryption: 'sae+gcmp256', mlo: true, extended: true, gcmp: true },
  { name: 'sae-no-driver-gcmp', encryption: 'sae', mlo: true, extended: true, no_gcmp: true },
  { name: 'ordinary-sae', encryption: 'sae' },
  { name: 'ordinary-sae-mixed', encryption: 'sae-mixed', legacy: true },
  { name: 'ordinary-compat-eht', encryption: 'sae-compat', override_gcmp: true, legacy: true },
  { name: 'ordinary-compat-he', encryption: 'sae-compat', htmode: 'HE20', legacy: true },
  { name: 'ordinary-sae-explicit-on', encryption: 'sae', extended: true, gcmp: true,
    overrides: { gcmp256: true, sae_ext_key: true } },
  { name: 'owe-transition', encryption: 'owe', mlo: true, transition: 'auto' },
  { name: 'owe-manual-ifname', encryption: 'owe', mlo: true, transition: 'ifname' },
  { name: 'owe-manual-bssid', encryption: 'owe', mlo: true, transition: 'bssid' },
  { name: 'ordinary-owe-transition', encryption: 'owe', transition: 'auto' },
  { name: 'ordinary-owe-manual-ifname', encryption: 'owe', transition: 'ifname' },
  { name: 'ordinary-owe-manual-bssid', encryption: 'owe', transition: 'bssid' }
];
for (let band in ['2g', '5g', '6g']) {
  for (let profile in profiles) {
    if (band == '6g' && profile.legacy) continue;
    let path = '/var/run/hostapd-phy0.0.conf';
    files = { [path]: 'prior-config' }; writes = []; config_data = 'prior-buffer'; iface_idx = 0;
    phy_features = { cipher_gcmp256: !profile.no_gcmp };
    let mlo = !!profile.mlo;
    let transition = profile.transition;
    let name = mlo ? 'ap-mld0' : 'ordinary0';
    let config = { mode: 'ap', ifname: name, ssid: 'Synthetic',
      encryption: profile.encryption, key: 'synthetic-passphrase',
      ieee80211w: 2, sae_pwe: 2, rnr: true, mlo, radios: [1, 2, 0],
      macaddr: '02:00:00:00:00:01', ieee80211r: !!profile.ft,
      auth_server: '192.0.2.1', auth_secret: 'synthetic-radius-secret',
      ...(profile.overrides ?? {}) };
    if (transition == 'auto') config.owe_transition = true;
    if (transition == 'ifname') config.owe_transition_ifname = 'ordinary-open0';
    if (transition == 'bssid') {
      config.owe_transition_bssid = '02:00:00:00:00:03';
      config.owe_transition_ssid = 'Synthetic-open';
    }
    let descriptor = clone(config);
    let radio = index(['2g', '5g', '6g'], band);
    let radios = map(['2g', '5g', '6g'], (band, radio) => ({ band, radio,
      country: 'SA', channel: [6, 36, 37][radio], htmode: profile.htmode ?? 'EHT20' }));
    let data = { phy: 'phy0', phy_suffix: '.0', vif_phy_suffix: '.0',
      config: { ...radios[radio], num_global_macaddr: 1 },
      interfaces: { test: { name: 'test', config, vlans: [], stas: [] } } };
    status = {};
    for (let rc in radios)
      status['radio' + rc.radio] = { config: rc, interfaces: [{ section: 'test', config: clone(config) }] };
    let snapshot = clone(data);
    if (transition == 'auto') data.interfaces.test.config.owe_transition_ifname = 'ordinary-open0';
    let label = band + '-' + profile.name;
    let rejected;
    try { setup(data, snapshot); } catch (e) { rejected = '' + e; }
    let should_reject = transition && (mlo || band == '6g');
    check(label + '-admission', should_reject ? !!rejected && index(rejected, 'OWE transition') >= 0 : !rejected);
    if (should_reject) {
      check(label + '-no-file-mutation', !length(writes) && files[path] == 'prior-config' && config_data == 'prior-buffer');
      push(results, { profile: label, rejected: !!rejected, error: rejected, writes: length(writes) });
      continue;
    }
    if (rejected) { push(results, { profile: label, error: rejected }); continue; }
    let parsed = iface_load_config('phy0', radio, path);
    let id = mld_config_id(descriptor);
    let encrypted = parsed.bss[0];
    let rows = [];
    for (let bss in parsed.bss) {
      let props = {};
      for (let line in bss.data) {
        let pair = split(line, '=', 2);
        props[pair[0]] = pair[1];
      }
      push(rows, { ifname: bss.ifname, ssid: bss.ssid, mld: !!bss.mld_ap,
        fingerprint: bss.mld_config_id != null,
        wpa: props.wpa ?? '0', key_mgmt: props.wpa_key_mgmt,
        pairwise: props.wpa_pairwise ?? props.rsn_pairwise,
        override_pairwise: props.rsn_override_pairwise_2,
        transition_ifname: props.owe_transition_ifname });
    }
    push(results, { profile: label, bss: rows });
    if (mlo) {
      check(label + '-encrypted-mld', encrypted.mld_ap == 1);
      check(label + '-descriptor-admission', mld_config_matches({ config: descriptor, config_id: id }, encrypted));
      check(label + '-encrypted-fingerprint', encrypted.mld_config_id == id);
    }
    let want_open = transition == 'auto';
    check(label + '-bss-count', length(parsed.bss) == (want_open ? 2 : 1));
    if (want_open) {
      let bss = parsed.bss[1];
      check(label + '-open-not-mld', !bss.mld_ap);
      check(label + '-open-visible-ssid', bss.ssid == descriptor.ssid);
    }
    if (band == '6g')
      check(label + '-all-bss-rsn', !length(filter(rows, x => x.wpa != '2')));
    check(label + '-gcmp256', (index(rows[0].pairwise ?? '', 'GCMP-256') >= 0) == !!profile.gcmp);
    if (index(profile.encryption, 'sae') == 0 && !profile.legacy)
      check(label + '-sae-ext-key', (index(rows[0].key_mgmt ?? '', 'SAE-EXT-KEY') >= 0) == !!profile.extended);
    if (profile.ft)
      check(label + '-ft-sae-ext-key', index(rows[0].key_mgmt ?? '', 'FT-SAE-EXT-KEY') >= 0);
    if (profile.override_gcmp)
      check(label + '-override-gcmp256', rows[0].override_pairwise == 'GCMP-256');
  }
}
let failures = filter(cases, x => !x.pass);
print(sprintf('%J\n', { cases: length(cases), failures, results,
  scope: 'Actual AP/security generation, full setup validation, parser and admission; ubus inventory, radio capabilities, I/O, schema defaults and MAC allocation modeled',
  radio_or_config_changes: false }));
exit(length(failures) ? 1 : 0);
