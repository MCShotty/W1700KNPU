// Extracted unchanged from hostapd.uc SHA256 8736ac333c18c125ea31215c37174c40cbfa72a009dbc4c204bb900cf64104c7.
// Original pre-membership-fix functions; framework inputs are supplied by the test.

function bss_check_mld(phydev, iface_name, bss)
{
	if (!bss.ifname)
		return;

	let mld_data = hostapd.data.mld[bss.ifname];
	if (!mld_data || !mld_data.ifname || !mld_data.macaddr)
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

function mld_update_iface_refs(iface_name, active)
{
	for (let mld_name, mld_data in hostapd.data.mld) {
		delete mld_data.iface[iface_name];
		if (active[mld_name])
			mld_data.iface[iface_name] = true;

		if (length(mld_data.iface) > 0 || !mld_data.has_wdev)
			continue;

		hostapd.printf(`Remove unused MLD interface ${mld_name}`);
		wdev_remove(mld_name);
		delete mld_data.has_wdev;
	}
}

function iface_check_mld(phydev, name, config)
{
	phydev = phy_open(phydev.phy);
	if (!phydev) {
		hostapd.printf(`Failed to open base phy for MLD config ${name}`);
		return false;
	}

	let active = {};
	let valid = true;
	for (let i = 0; i < length(config.bss); i++) {
		let bss = config.bss[i];
		if (!bss.mld_ap)
			continue;

		if (!bss_check_mld(phydev, name, bss)) {
			hostapd.printf(`Skip MLD interface ${name} on phy ${phydev.name}`);
			splice(config.bss, i--, 1);
			valid = false;
			continue;
		}

		active[bss.ifname] = true;
	}

	mld_update_iface_refs(name, active);

	return valid;
}

function mld_config_uses(config, mld_name)
{
	for (let bss in config?.orig_bss ?? config?.bss ?? [])
		if (bss.mld_ap && bss.ifname == mld_name)
			return true;

	return false;
}

function mld_collect_reload(reload_iface, name, data, include_config)
{
	for (let iface in data?.iface ?? {})
		reload_iface[iface] = true;

	for (let iface, bss_list in hostapd.bss)
		if (bss_list[name])
			reload_iface[iface] = true;

	if (!include_config)
		return;

	for (let iface, iface_config in hostapd.data.config)
		if (mld_config_uses(iface_config, name))
			reload_iface[iface] = true;
}
