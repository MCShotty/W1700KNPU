'use strict';

import {
	append, append_raw, append_vars, dump_config, flush_config, set_default,
	wiphy_info, wiphy_band
} from 'wifi.common';
import { validate } from 'wifi.validate';
import * as netifd from 'wifi.netifd';
import * as iface from 'wifi.iface';
import * as nl80211 from 'nl80211';
import * as ap from 'wifi.ap';
import * as fs from 'fs';

const NL80211_EXT_FEATURE_ENABLE_FTM_RESPONDER = 33;
const NL80211_EXT_FEATURE_RADAR_BACKGROUND = 61;

let phy_features = {};
let phy_capabilities = {};

const mlo_common_fields = [
	'ssid', 'encryption', 'key', 'sae_password', 'ieee80211w', 'sae_pwe',
	'network', 'wpa_group_rekey', 'eap_server', 'auth_server', 'auth_port',
	'auth_secret'
];

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
	for (let field in mlo_common_fields)
		if (!mlo_same_value(a[field], b[field]))
			return false;

	return true;
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

	let encryption = split('' + (config.encryption ?? ''), '+', 2)[0];
	if (!(encryption in [ 'sae', 'owe', 'wpa3', 'wpa3-192' ]))
		return `MLO owner ${owner} requires WPA3-SAE, OWE, or WPA3 Enterprise security`;
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

export function mlo_status_generation_error(data, status) {
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

export function validate_mlo_config(data, status) {
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

function validate_mlo_setup(data) {
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

/* make sure old style UCI and hwmode and newer band properties are correctly resolved */
function set_device_defaults(config) {
	/* validate the hw mode */
	if (config.hw_mode in [ '11a', '11b', '11g', '11ad' ])
		config.hw_mode = substr(config.hw_mode, 2);
	else if (config.channel > 14)
		config.hw_mode = 'a';
	else
		config.hw_mode = 'g';

	/* validate band */
	if (config.band == '2g')
		config.hw_mode = 'g';
	else if (config.band in [ '5g', '6g', '60g' ])
		config.hw_mode = 'a';
	else
		switch (config.hw_mode) {
		case 'a':
			config.band = '5g';
			break;

		case 'ad':
			config.band = '60g';
			break;

		default:
			config.band = '2g';
			break;
		}
}

/* setup sylog / stdout */
function device_log_append(config) {
	let log_mask = 0;

	for (let k in [ 'log_mlme', 'log_iapp', 'log_driver', 'log_wpa', 'log_radius', 'log_8021x', 'log_80211' ]) {
		log_mask <<= 1;
		log_mask |= config[k] ? 1 : 0;
	}

	append('logger_syslog', log_mask);
	append('logger_syslog_level', config.log_level);
	append('logger_stdout', log_mask);
	append('logger_stdout_level', config.log_level);
}

/* setup country code */
function device_country_code(config) {
	let status = global.ubus.call('network.wireless', 'status');
	for (let name, radio in status) {
		if (!radio.config.country)
			continue;
		config.country_code = radio.config.country;
	}

	if (!exists(config, 'country_code'))
		return;

	if (config.hw_mode != 'a')
		delete config.ieee80211h;
	append_vars(config, [ 'country_code', 'country3', 'ieee80211h' ]);
	if (config.ieee80211d)
		append_vars(config, [ 'ieee80211d', 'local_pwr_constraint', 'spectrum_mgmt_required' ]);
}


/* setup cell density */
function device_cell_density_append(config) {
	switch (config.hw_mode) {
	case 'b':
		if (config.cell_density == 1) {
			config.supported_rates ??= [ 5500, 11000 ];
			config.basic_rates ??= [ 5500, 11000 ];
		} else if (config.cell_density > 2) {
			config.supported_rates ??= [ 11000 ];
			config.basic_rates ??= [ 11000 ];
		}
		;;
	case 'g':
		if (config.cell_density in [ 0, 1 ]) {
			if (!config.legacy_rates) {
				config.supported_rates ??= [ 6000, 9000, 12000, 18000, 24000, 36000, 48000, 54000 ];
				config.basic_rates ??= [ 6000, 12000, 24000 ];
			} else if (config.cell_density == 1) {
				config.supported_rates ??= [ 5500, 6000, 9000, 11000, 12000, 18000, 24000, 36000, 48000, 54000 ];
				config.basic_rates ??= [ 5500, 11000 ];
			}
		} else if (config.cell_density == 2 || (config.cell_density > 3 && config.legacy_rates)) {
			if (!config.legacy_rates) {
				config.supported_rates ??= [ 12000, 18000, 24000, 36000, 48000, 54000 ];
				config.basic_rates ??= [ 12000, 24000 ];
			} else {
				config.supported_rates ??= [ 11000, 12000, 18000, 24000, 36000, 48000, 54000 ];
				config.basic_rates ??= [ 11000 ];
			}
		} else if (config.cell_density > 2) {
			 config.supported_rates ??= [ 24000, 36000, 48000, 54000 ];
			 config.basic_rates ??= [ 24000 ];
		}
		;;
	case 'a':
		switch (config.cell_density) {
		case 1:
			config.supported_rates ??= [ 6000, 9000, 12000, 18000, 24000, 36000, 48000, 54000 ];
			config.basic_rates ??= [ 6000, 12000, 24000 ];
			break;

		case 2:
			config.supported_rates ??= [ 12000, 18000, 24000, 36000, 48000, 54000 ];
			config.basic_rates ??= [ 12000, 24000 ];
			break;

		case 3:
			config.supported_rates ??= [ 24000, 36000, 48000, 54000 ];
			config.basic_rates ??= [ 24000 ];
			break;
		}
	}
}

function device_rates(config) {
	for (let key in [ 'supported_rates', 'basic_rates' ])
		config[key] = map(config[key], x => x / 100);

	append_vars(config, [ 'beacon_rate', 'supported_rates', 'basic_rates' ]);
}

function device_htmode_append(config) {
	config.channel_offset = config.band == '6g' ? 1 : 0;

	/* 802.11n */
	config.ieee80211n = 0;
	if (config.band != '6g') {
		if (config.htmode in [ 'VHT20', 'HT20', 'HE20', 'EHT20' ]) {
			config.ieee80211n = 1;
			config.ht_capab = '';
		}
		if (config.htmode in [ 'HT40', 'HT40+', 'HT40-', 'VHT40', 'VHT80', 'VHT160', 'HE40', 'HE80', 'HE160', 'EHT40', 'EHT80', 'EHT160' ]) {
			config.ieee80211n = 1;
			if (!config.channel)
				config.ht_capab = '[HT40+]';
			else
				switch (config.hw_mode) {
				case 'a':
					switch (((config.channel / 4) + config.channel_offset) % 2) {
					case 0:
						config.ht_capab = '[HT40-]';
						break;

					case 1:
						config.ht_capab = '[HT40+]';
						break;
					}
					break;

				default:
					switch (config.htmode) {
					case 'HT40+':
					case 'HT40-':
						config.ht_capab = '[' + config.htmode + ']';
						break;

					default:
						if (config.channel < 7)
							config.ht_capab = '[HT40+]';
						else
							config.ht_capab = '[HT40-]';
						break;
					}
				}
		}

		if (config.ieee80211n) {
			let ht_capab = phy_capabilities.ht_capa;

			if (ht_capab & 0x1 && config.ldpc)
				config.ht_capab += '[LDPC]';
			if (ht_capab & 0x10 && config.greenfield)
				config.ht_capab += '[GF]';
			if (ht_capab & 0x20 && config.short_gi_20)
				config.ht_capab += '[SHORT-GI-20]';
			if (ht_capab & 0x40 && config.short_gi_40)
				config.ht_capab += '[SHORT-GI-40]';
			if (ht_capab & 0x80 && config.tx_stbc)
				config.ht_capab += '[TX-STBC]';
			if (ht_capab & 0x800 && config.max_amsdu)
				config.ht_capab += '[MAX-AMSDU-7935]';
			if (ht_capab & 0x1000 && config.dsss_cck_40)
				config.ht_capab += '[DSSS_CCK-40]';
			let rx_stbc = [ '', '[RX-STBC1]', '[RX-STBC12]', '[RX-STBC123]' ];
			config.ht_capab += rx_stbc[min(config.rx_stbc, (ht_capab >> 8) & 3)];

			append_vars(config, [ 'ieee80211n', 'ht_coex', 'ht_capab' ]);
		}
	}

	/* 802.11ac */
	config.ieee80211ac = 1;
	config.vht_oper_centr_freq_seg0_idx = 0;
	config.vht_oper_chwidth = 0;

	switch (config.htmode) {
	case 'VHT20':
	case 'HE20':
	case 'EHT20':
		break;

	case 'VHT40':
	case 'HE40':
	case 'EHT40':
		config.vht_oper_centr_freq_seg0_idx = config.channel + (((config.channel / 4) + config.channel_offset) % 2 ? 2 : -2);
		break;

	case 'VHT80':
	case 'HE80':
	case 'EHT80':
		let delta = [ -6, 6, 2, -2 ];
		config.vht_oper_centr_freq_seg0_idx = config.channel + delta[((config.channel / 4) + config.channel_offset) % 4];
		config.vht_oper_chwidth = 1;
		break;

	case 'VHT160':
	case 'HE160':
	case 'EHT160':
		let vht_oper_centr_freq_seg0_idx_map = [[ 64, 50 ], [ 128, 114 ], [ 177, 163 ]];
		if (config.band == '6g')
			vht_oper_centr_freq_seg0_idx_map = [
				[ 29, 15 ], [ 61, 47 ], [ 93, 79 ], [ 125, 111 ],
				[ 157, 143 ], [ 189, 175 ], [ 221, 207 ]];
		for (let k, v in vht_oper_centr_freq_seg0_idx_map)
			if (config.channel >= (v[0] - 28) && config.channel <= v[0]) {
				config.vht_oper_centr_freq_seg0_idx = v[1];
				break;
			}
		config.vht_oper_chwidth = 2;
		break;

	default:
		config.ieee80211ac = 0;
		break;
	}

	config.eht_oper_chwidth = config.vht_oper_chwidth;
	config.eht_oper_centr_freq_seg0_idx = config.vht_oper_centr_freq_seg0_idx;

	if (config.band == '6g') {
		config.ieee80211ac = 0;

		switch(config.htmode) {
		case 'HE20':
		case 'EHT20':
			config.op_class = 131;
			break;

		case 'EHT320':
			let eht_center_seg0_map = [
				[ 61, 31 ], [ 125, 95 ], [ 189, 159 ], [ 221, 191 ]
			];

			for (let k, v in eht_center_seg0_map)
				if (config.channel <= v[0]) {
					config.eht_oper_centr_freq_seg0_idx = v[1];
					break;
				}
			config.op_class = 137;
			config.eht_oper_chwidth = 9;

			/*
			 * Set HE operation values for 160MHz backward compatibility
			 * with WiFi 6E clients. Pick the 160MHz half that contains
			 * the primary channel.
			 */
			config.he_oper_chwidth = 3;
			if (config.channel < config.eht_oper_centr_freq_seg0_idx)
				config.he_oper_centr_freq_seg0_idx = config.eht_oper_centr_freq_seg0_idx - 16;
			else
				config.he_oper_centr_freq_seg0_idx = config.eht_oper_centr_freq_seg0_idx + 16;
			break;

		case 'HE40':
		case 'HE80':
		case 'HE160':
		case 'EHT40':
		case 'EHT80':
		case 'EHT160':
			config.op_class = 132 + config.eht_oper_chwidth;
			break;
		}

		append_vars(config, [ 'op_class' ]);
	}

	if (config.ieee80211ac && config.hw_mode == 'a') {
		/* VHT capab */
		if (config.vht_oper_chwidth < 2) {
			config.vht160 = 0;
			config.short_gi_160 = 0;
		}

		set_default(config, 'tx_queue_data2_burst', '2.0');

		let vht_capab = phy_capabilities.vht_capa;
		
		config.vht_capab = '';
		if (vht_capab & 0x10 && config.rxldpc)
			config.vht_capab += '[RXLDPC]';
		if (vht_capab & 0x20 && config.short_gi_80)
			config.vht_capab += '[SHORT-GI-80]';
		if (vht_capab & 0x40 && config.short_gi_160)
			config.vht_capab += '[SHORT-GI-160]';
		if (vht_capab & 0x80 && config.tx_stbc_2by1)
			config.vht_capab += '[TX-STBC-2BY1]';
		if (vht_capab & 0x800 && config.su_beamformer)
			config.vht_capab += '[SU-BEAMFORMER]';
		if (vht_capab & 0x1000 && config.su_beamformee)
			config.vht_capab += '[SU-BEAMFORMEE]';
		if (vht_capab & 0x80000 && config.mu_beamformer)
			config.vht_capab += '[MU-BEAMFORMER]';
		if (vht_capab & 0x100000 && config.mu_beamformee)
			config.vht_capab += '[MU-BEAMFORMEE]';
		if (vht_capab & 0x200000 && config.vht_txop_ps)
			config.vht_capab += '[VHT-TXOP-PS]';
		if (vht_capab & 0x400000 && config.htc_vht)
			config.vht_capab += '[HTC-VHT]';
		if (vht_capab & 0x10000000 && config.rx_antenna_pattern)
			config.vht_capab += '[RX-ANTENNA-PATTERN]';
		if (vht_capab & 0x20000000 && config.tx_antenna_pattern)
			config.vht_capab += '[TX-ANTENNA-PATTERN]';
		let rx_stbc = [ '', '[RX-STBC-1]', '[RX-STBC-12]', '[RX-STBC-123]', '[RX-STBC-1234]' ];
		config.vht_capab += rx_stbc[min(config.rx_stbc, (vht_capab >> 8) & 7)];

		if (vht_capab & 0x800 && config.su_beamformer)
			config.vht_capab += '[SOUNDING-DIMENSION-' + min(((vht_capab >> 16) & 3) + 1, config.beamformer_antennas) + ']';
		if (vht_capab & 0x1000 && config.su_beamformee)
			config.vht_capab += '[BF-ANTENNA-' + min(((vht_capab >> 13) & 3) + 1, config.beamformee_antennas) + ']';

		/* supported Channel widths */
		if ((vht_capab & 0xc) == 8 && config.vht160 >= 2)
			config.vht_capab += '[VHT160-80PLUS80]';
		else if (((vht_capab & 0xc) == 4 || (vht_capab & 0xc) == 8) && config.vht160 >= 1)
			config.vht_capab += '[VHT160]';

		/* maximum MPDU length */
		if ((vht_capab & 3) > 1 && config.vht_max_mpdu >= 11454)
			config.vht_capab += '[MAX-MPDU-11454]';
		else if ((vht_capab & 3) && config.vht_max_mpdu >= 7991)
			config.vht_capab += '[MAX-MPDU-7991]';

		/* maximum A-MPDU length exponent */
		let max_a_mpdu_len_exp = (vht_capab >> 20) & 0x38;
		for (let exp = 7; exp; exp--)
			if (max_a_mpdu_len_exp >= (0x8 * exp) && exp <= config.vht_max_a_mpdu_len_exp) {
				config.vht_capab += '[MAX-A-MPDU-LEN-EXP' + exp + ']';
				break;
			}

		/* whether or not the STA supports link adaptation using VHT variant */
		let vht_link_adapt = vht_capab & 0xC000000;
		if (vht_link_adapt >= 0xC000000 && config.vht_link_adapt > 3)
			config.vht_capab += '[VHT-LINK-ADAPT-3]';
		if (vht_link_adapt >= 0x8000000 && config.vht_link_adapt > 2)
			config.vht_capab += '[VHT-LINK-ADAPT-2]';

		append_vars(config, [
			'ieee80211ac', 'vht_oper_chwidth', 'vht_oper_centr_freq_seg0_idx',
			'vht_capab'
		]);
	}

	/* 802.11ax */
	if (wildcard(config.htmode, 'HE*') || wildcard(config.htmode, 'EHT*')) {
		let he_phy_cap = phy_capabilities.he_phy_cap;
		let he_mac_cap = phy_capabilities.he_mac_cap;

		config.ieee80211ax = true;

		if (config.hw_mode == 'a') {
			/*
			 * Only set HE values from VHT if not already set.
			 * For 6GHz 320MHz, these are pre-set for 160MHz backward
			 * compatibility with WiFi 6E clients.
			 */
			if (!config.he_oper_chwidth)
				config.he_oper_chwidth = config.vht_oper_chwidth;
			if (!config.he_oper_centr_freq_seg0_idx)
				config.he_oper_centr_freq_seg0_idx = config.vht_oper_centr_freq_seg0_idx;
		}

		if (config.band == "6g") {
			config.stationary_ap = true;
			append_vars(config, [ 'he_6ghz_reg_pwr_type', ]);
		}

		if (config.he_bss_color_enabled) {
			if (config.he_spr_non_srg_obss_pd_max_offset)
				config.he_spr_sr_control |= 1 << 2;
			if (!config.he_spr_psr_enabled)
				config.he_spr_sr_control |= 1;
			append_vars(config, [ 'he_bss_color', 'he_spr_non_srg_obss_pd_max_offset', 'he_spr_sr_control' ]);
		}

		if (!(he_phy_cap[3] & 0x80))
			config.he_su_beamformer = false;
		if (!(he_phy_cap[4] & 0x1))
			config.he_su_beamformee = false;
		if (!(he_phy_cap[4] & 0x2))
			config.he_mu_beamformer = false;
		if (!(he_phy_cap[7] & 0x1))
			config.he_spr_psr_enabled = false;
		if (!(he_mac_cap[0] & 0x4))
			config.he_twt_responder = false;
		if (!config.he_twt_responder)
			config.he_twt_required= false;

		append_vars(config, [
			'ieee80211ax', 'he_oper_chwidth', 'he_oper_centr_freq_seg0_idx',
			'he_su_beamformer', 'he_su_beamformee', 'he_mu_beamformer',
			'he_twt_required', 'he_twt_responder',
			'he_default_pe_duration', 'he_rts_threshold', 'he_mu_edca_qos_info_param_count',
			'he_mu_edca_qos_info_q_ack', 'he_mu_edca_qos_info_queue_request', 'he_mu_edca_qos_info_txop_request',
			'he_mu_edca_ac_be_aifsn', 'he_mu_edca_ac_be_aci', 'he_mu_edca_ac_be_ecwmin',
			'he_mu_edca_ac_be_ecwmax', 'he_mu_edca_ac_be_timer', 'he_mu_edca_ac_bk_aifsn',
			'he_mu_edca_ac_bk_aci', 'he_mu_edca_ac_bk_ecwmin', 'he_mu_edca_ac_bk_ecwmax',
			'he_mu_edca_ac_bk_timer', 'he_mu_edca_ac_vi_ecwmin', 'he_mu_edca_ac_vi_ecwmax',
			'he_mu_edca_ac_vi_aifsn', 'he_mu_edca_ac_vi_aci', 'he_mu_edca_ac_vi_timer',
			'he_mu_edca_ac_vo_aifsn', 'he_mu_edca_ac_vo_aci', 'he_mu_edca_ac_vo_ecwmin',
			'he_mu_edca_ac_vo_ecwmax', 'he_mu_edca_ac_vo_timer',
		]);
	}

	if (wildcard(config.htmode, 'EHT*')) {
		config.ieee80211be = true;
		append_vars(config, [ 'ieee80211be' ]);

		if (config.hw_mode == 'a')
			append_vars(config, [ 'eht_oper_chwidth', 'eht_oper_centr_freq_seg0_idx' ]);

		if (config.band != '2g') {
			if (config.punct_bitmap)
				append_vars(config, [ 'punct_bitmap' ]);
			if (config.channel == 'auto' && config.punct_acs_threshold)
				append_vars(config, [ 'punct_acs_threshold' ]);
		}
	}

	append_vars(config, [ 'tx_queue_data2_burst', 'stationary_ap' ]);
}

function device_extended_features(data, flag) {
	return !!(data[flag / 8] | (1 << (flag % 8)));
}

function device_capabilities(config) {
	let phy = config.phy;

	phy = wiphy_info(phy);
	let band = wiphy_band(phy, config.band);

	phy_capabilities.ht_capa = band.ht_capa ?? 0;
	phy_capabilities.vht_capa = band.vht_capa ?? 0;
	phy_capabilities.he_mac_cap = [];
	phy_capabilities.he_phy_cap = [];
	for (let iftype in band.iftype_data) {
		if (!iftype.iftypes.ap)
			continue;
		phy_capabilities.he_mac_cap = iftype.he_cap_mac;
		phy_capabilities.he_phy_cap = iftype.he_cap_phy;
	}

	phy_features.ftm_responder = device_extended_features(phy.extended_features, NL80211_EXT_FEATURE_ENABLE_FTM_RESPONDER);
	phy_features.radar_background = device_extended_features(phy.extended_features, NL80211_EXT_FEATURE_RADAR_BACKGROUND);
}

function generate(config) {
	if (!config)
		die(`${config.path} is an unknown phy`);

	device_capabilities(config);

	append('driver', 'nl80211');

	set_device_defaults(config);

	device_log_append(config);

	device_country_code(config);

	device_cell_density_append(config);

	device_rates(config);

	/* beacon */
	append_vars(config, [ 'beacon_int', 'beacon_rate', 'rnr_beacon' ]);

	/* wpa_supplicant co-exist */
	append_vars(config, [ 'noscan' ]);

	/* airtime */
	if (config.airtime_mode)
		append_vars(config, [ 'airtime_mode' ]);

	/* assoc/thresholds */
	append_vars(config, [ 'rssi_reject_assoc_rssi', 'rssi_reject_assoc_timeout', 'rssi_ignore_probe_request', 'iface_max_num_sta' ]);

	/* ACS / Radar*/
	if (!phy_features.radar_background || config.band != '5g')
		delete config.enable_background_radar;
	else
		set_default(config, 'enable_background_radar', false);

	append_vars(config, [ 'acs_chan_bias', 'acs_exclude_dfs', 'enable_background_radar' ]);

	/* TX Power */
	append_vars(config, [ 'min_tx_power' ]);

	/* hwmode, channel, op_class, ... */
	append_vars(config, [ 'hw_mode', 'channel', 'rts_threshold', 'chanlist' ]);
	if (config.hw_mode in [ 'a', 'g' ] && config.require_mode in [ 'n', 'ac', 'ax' ]) {
		let require_mode = { n: 'require_ht', ac: 'require_vht', ax: 'require_he' };

		config.legacy_rates = false;
		append(require_mode[config.require_mode], 1);
	}
	device_htmode_append(config);

	if (config.ieee80211ax || config.ieee80211be)
		append_vars(config, [ 'mbssid' ]);

	/* 6G power mode */
	if (config.band != '6g')
		append_vars(config, [ 'reg_power_type' ]);

	/* raw options */
	for (let raw in config.hostapd_options)
		append_raw(raw);
}

let iface_idx = 0;
function setup_interface(interface, data, config, vlans, stas, phy_features, fixup) {
	config = { ...config, fixup };

	config.idx = iface_idx++;
	ap.generate(interface, data, config, vlans, stas, phy_features);
}

export function setup(data) {
	let file_name = `/var/run/hostapd-${data.phy}${data.vif_phy_suffix}.conf`;

	validate_mlo_setup(data);

	flush_config();

	if (fs.stat(file_name))
		fs.rename(file_name, file_name + '.prev');

	data.config.phy = data.phy;

	generate(data.config);

	if (data.config.num_global_macaddr)
		append('\n#num_global_macaddr', data.config.num_global_macaddr);
	if (data.config.macaddr_base)
		append('\n#macaddr_base', data.config.macaddr_base);

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
};
