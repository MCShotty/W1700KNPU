'use strict';

const radio_bands = {
	'0': "2g",
	'1': "5g",
	'2': "6g",
};

export function validate_device_list(dev_names, devices, radio_idx)
{
	if (type(dev_names) != "array" || length(dev_names) < 2)
		return "requires at least two declared radios";

	let seen_names = {};
	let seen_radios = {};
	let country;

	for (let name in dev_names) {
		if (type(name) != "string" || !length(name))
			return "contains an empty or malformed radio name";
		if (seen_names[name])
			return `declares radio ${name} more than once`;
		seen_names[name] = true;

		let dev = devices[name];
		if (!dev)
			return `references missing radio ${name}`;
		if (type(dev.config) != "object")
			return `references malformed radio ${name}`;
		if (dev.config.disabled)
			return `references disabled radio ${name}`;

		let radio = radio_idx[name];
		let expected_band = radio_bands[radio];
		if (!expected_band)
			return `${name} has unsupported physical radio index ${radio ?? "unset"}`;
		if (seen_radios[radio])
			return `${name} duplicates physical radio index ${radio}`;
		seen_radios[radio] = true;

		let band = '' + (dev.config.band ?? '');
		if (band != expected_band)
			return `${name} is physical ${expected_band}; it cannot be configured as ${band || "unset"}`;

		let channel = '' + (dev.config.channel ?? '');
		if (!length(channel) || channel == "auto")
			return `${name} requires a fixed channel`;

		let htmode = '' + (dev.config.htmode ?? '');
		if (!match(htmode, /^EHT(20|40|80|160|320)$/))
			return `${name} requires an EHT channel width`;
		if (radio == 0 && htmode != "EHT20")
			return `${name} requires EHT20 for a 2.4 GHz MLO link`;
		if (radio == 1 && htmode == "EHT320")
			return `${name} cannot use EHT320 on 5 GHz`;

		let link_country = uc('' + (dev.config.country ?? ''));
		if (!match(link_country, /^[A-Z]{2}$/) || link_country == "00")
			return `${name} requires an explicit two-letter regulatory country`;
		if (country && country != link_country)
			return `${name} uses country ${link_country} while another MLO link uses ${country}`;
		country = link_country;
	}

	return null;
}
