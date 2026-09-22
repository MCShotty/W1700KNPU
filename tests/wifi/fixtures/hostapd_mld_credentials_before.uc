function mld_radio_matches(data, phy, radio)
{
	radio ??= 0;
	return data && data.config.phy == phy &&
		radio >= 0 && radio < 32 && radio == (radio | 0) &&
		!!(data.radio_mask & (1 << radio));
}

function mld_ssid_matches(data, bss)
{
	return type(data?.config?.ssid) != 'string' ||
		(type(bss.ssid) == 'string' && bss.ssid == data.config.ssid);
}

function bss_check_mld(phydev, iface_name, bss, radio)
{
	if (!bss.ifname)
		return;

	let mld_data = hostapd.data.mld[bss.ifname];
	if (!mld_data || !mld_data.ifname || !mld_data.macaddr)
		return;
	if (!mld_radio_matches(mld_data, phydev.name, radio))
		return;
	if (!mld_ssid_matches(mld_data, bss))
		return;

	bss.mld_bssid = mld_data.macaddr;
	bss.mld_anchor_radio = mld_data.anchor_radio;

	if (!access('/sys/class/net/' + bss.ifname, 'x'))
		mld_data.has_wdev = false;

	if (mld_data.has_wdev)
		return true;

	hostapd.printf(`Create MLD interface ${bss.ifname} on phy ${phydev.name}, radio mask: ${mld_data.radio_mask}`);
	let err = phy_wdev_add(phydev, bss.ifname, {
		mode: "ap",
		macaddr: mld_data.macaddr,
		radio_mask: mld_data.radio_mask,
	});
	if (err) {
		hostapd.printf(`Failed to create MLD ${bss.ifname} on phy ${phydev.name}: ${err}`);
		return;
	}

	if (!wdev_set_up(bss.ifname, true)) {
		hostapd.printf(`Failed to set MLD ${bss.ifname} up on phy ${phydev.name}`);
		wdev_remove(bss.ifname);
		delete mld_data.has_wdev;
		return;
	}

	mld_data.has_wdev = true;

	return true;
}

function iface_set_config(name, config, complete, allow_mld_filter)
{
	let old_config = hostapd.data.config[name];

	if (config?.load_error) {
		if (complete)
			complete(false);
		return false;
	}

	if (!config) {
		delete hostapd.data.config[name];
		let ret = iface_config_remove(name, old_config);
		if (complete)
			complete(true);
		return ret;
	}

	// A late radio worker must not replace a newer MLD link configuration.
	for (let bss in config.bss) {
		if (!bss.mld_ap || mld_ssid_matches(hostapd.data.mld[bss.ifname], bss))
			continue;

		hostapd.printf(`Reject stale MLD SSID config on phy ${name}`);
		if (complete)
			complete(false);
		return false;
	}

	let phy = config.phy;
	let phydev = phy_open(phy, config.radio_idx);
	if (!phydev) {
		hostapd.printf(`Failed to open phy ${phy}`);
		if (complete)
			complete(false);
		return false;
	}

	config.orig_bss = [ ...config.bss ];
	let mld_valid = iface_check_mld(phydev, name, config);
	let config_valid = mld_valid || allow_mld_filter;
	hostapd.data.config[name] = config;
	if (!length(config.bss)) {
		let ret = iface_config_remove(name, old_config) ?? (config_valid ? 0 : false);
		if (complete)
			complete(config_valid);
		return ret;
	}

	try {
		let ret = iface_reload_config(name, phydev, config, old_config);
		if (ret) {
			iface_update_supplicant_macaddr(phydev);
			hostapd.printf(`Reloaded settings for phy ${name}`);
			if (complete)
				complete(config_valid);
			return config_valid ? 0 : false;
		}
	} catch (e) {
		log_exception("Error reloading config: ", e);
	}

	hostapd.printf(`Restart interface for phy ${name}`);
	let ret = iface_restart(phydev, config, old_config, complete ? (valid) => {
		complete(config_valid && valid);
	} : null);

	return config_valid ? ret : false;
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

function mld_config_uses(config, mld_name, data)
{
	for (let bss in config?.orig_bss ?? config?.bss ?? [])
		if (bss.mld_ap && bss.ifname == mld_name && mld_ssid_matches(data, bss))
			return true;

	return false;
}

function mld_collect_reload(reload_iface, name, data, include_config)
{
	let candidates = {};
	for (let iface in data?.iface ?? {})
		candidates[iface] = true;

	for (let iface, bss_list in hostapd.bss)
		if (bss_list[name])
			candidates[iface] = true;

	if (include_config)
		for (let iface, iface_config in hostapd.data.config)
			if (mld_config_uses(iface_config, name))
				candidates[iface] = true;

	// Detach all old references, but reactivate only matching links in the new MLD.
	for (let iface in candidates) {
		let config = hostapd.data.config[iface];
		if (!include_config || (config &&
		    mld_radio_matches(data, config.phy, config.radio_idx) &&
		    mld_config_uses(config, name, data)))
			reload_iface[iface] = true;
	}
}
