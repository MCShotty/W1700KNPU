'use strict';
'require view';
'require dom';
'require poll';
'require fs';
'require ui';
'require rpc';
'require uci';
'require form';
'require network';
'require firewall';
'require tools.widgets as widgets';
'require uqr';

const isReadonlyView = !L.hasViewPermission();

const W1700K_RADIO_INFO = {
	'0': { band: '2g', label: '2.4 GHz', defaultHtmode: { '': 'HT20', n: 'HT40', ax: 'HE40', be: 'EHT40' } },
	'1': { band: '5g', label: '5 GHz', defaultHtmode: { '': 'HT20', n: 'HT40', ac: 'VHT80', ax: 'HE80', be: 'EHT80' } },
	'2': { band: '6g', label: '6 GHz', defaultHtmode: { ax: 'HE160', be: 'EHT320' } }
};

const W1700K_5G_CHANNEL_RUNS = [
	[36, 40, 44, 48, 52, 56, 60, 64],
	[100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144],
	[149, 153, 157, 161, 165, 169, 173, 177]
];

const W1700K_5G_STATIC_AP_CHANNELS = [
	36, 40, 44, 48,
	52, 56, 60, 64,
	100, 104, 108, 112,
	116, 120, 124, 128,
	132, 136, 140, 144,
	149, 153, 157, 161,
	165
];

const W1700K_PMF_ENCRYPTIONS = [
	'owe', 'psk2', 'psk-mixed', 'sae', 'sae-mixed',
	'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'
];

const W1700K_PUNCT_ACTIVE_MASKS = {
	80: [ 0xf, 0xe, 0xd, 0xb, 0x7 ],
	160: [ 0xff, 0xfe, 0xfd, 0xfb, 0xf7, 0xef, 0xdf, 0xbf, 0x7f, 0xfc, 0xf3, 0xcf, 0x3f ],
	320: [
		0xffff, 0xfffc, 0xfff3, 0xffcf, 0xff3f, 0xfcff, 0xf3ff, 0xcfff,
		0x3fff, 0xfff0, 0xff0f, 0xf0ff, 0x0fff, 0xffc0, 0xff30, 0xfcf0,
		0xf3f0, 0xcff0, 0x3ff0, 0x0ffc, 0x0ff3, 0x0fcf, 0x0f3f, 0x0cff,
		0x03ff
	]
};

let w1700kWifiCapabilitiesPromise = null;

const callIwinfoFrequencyList = rpc.declare({
	object: 'iwinfo',
	method: 'freqlist',
	params: [ 'device' ],
	expect: { results: [] }
});

function w1700kLoadWifiCapabilities() {
	if (!w1700kWifiCapabilitiesPromise)
		w1700kWifiCapabilitiesPromise = L.resolveDefault(
			fs.exec_direct('/usr/sbin/w1700k-wifi-capabilities', [], 'json'), {});

	return w1700kWifiCapabilitiesPromise;
}

function w1700kDeviceNames(value) {
	const values = Array.isArray(value) ? value :
		(typeof(value) == 'string' ? [ value ] : L.toArray(value));
	const names = [];

	values.forEach(function(value) {
		if (typeof(value) != 'string')
			return;

		value.trim().split(/\s+/).forEach(function(name) {
			if (name && names.indexOf(name) < 0)
				names.push(name);
		});
	});

	return names;
}

function w1700kExplicitRadioIndex(section_id) {
	const idx = uci.get('wireless', section_id, 'radio');
	return W1700K_RADIO_INFO.hasOwnProperty(String(idx)) ? String(idx) : null;
}

function w1700kRadioMapActive() {
	return uci.sections('wireless', 'wifi-device').some(function(dev) {
		return w1700kExplicitRadioIndex(dev['.name']) != null;
	});
}

function w1700kRadioIndex(section_id) {
	const idx = w1700kExplicitRadioIndex(section_id);
	return W1700K_RADIO_INFO.hasOwnProperty(String(idx)) ? String(idx) : null;
}

function w1700kRadioIndexOwners(idx) {
	if (!w1700kRadioMapActive() || !W1700K_RADIO_INFO.hasOwnProperty(String(idx)))
		return [];

	return uci.sections('wireless', 'wifi-device').map(function(dev) {
		return dev['.name'];
	}).filter(function(name) {
		return w1700kRadioIndex(name) == String(idx);
	});
}

function w1700kRadioIndexConflict(section_id) {
	const idx = w1700kRadioIndex(section_id);
	const owners = (idx != null) ? w1700kRadioIndexOwners(idx) : [];

	return owners.length > 1 ? owners : null;
}

function w1700kRadioInfo(section_id) {
	const idx = w1700kRadioIndex(section_id);

	if (!w1700kRadioMapActive() || idx == null || w1700kRadioIndexOwners(idx).length != 1)
		return null;

	return W1700K_RADIO_INFO[idx] || null;
}

function w1700kMappedRadioNames() {
	return uci.sections('wireless', 'wifi-device').map(function(dev) {
		return dev['.name'];
	}).filter(function(name) {
		return w1700kRadioInfo(name) != null;
	});
}

function w1700kMloAvailable() {
	return w1700kMappedRadioNames().length >= 2;
}

function w1700kRadioBand(section_id) {
	const info = w1700kRadioInfo(section_id);
	return info ? info.band : uci.get('wireless', section_id, 'band') || null;
}

function w1700kRadioLabel(section_id) {
	const idx = w1700kRadioIndex(section_id);
	const info = w1700kRadioInfo(section_id);

	return info ? '%s / idx %s / %s'.format(section_id, idx, info.label) : section_id;
}

function w1700kRadioRuntimeFacts(radioDev, wifiNets) {
	const radioName = typeof radioDev?.getName == 'function' ? radioDev.getName() : null;
	const radioBand = w1700kRadioBand(radioName);
	let iwinfo = typeof radioDev?.ubus == 'function' ? (radioDev.ubus('dev', 'iwinfo') || {}) : {};
	const configuredChannel = +uci.get('wireless', radioName, 'channel');
	const configuredFrequency = w1700kChannelFrequencyGHz(radioBand, configuredChannel);
	let source = 'runtime';

	// Only a local, single-radio interface can supply missing radio telemetry.
	if (iwinfo.channel == null && iwinfo.frequency == null) {
		for (const net of wifiNets || []) {
			if (w1700kWifiNetDeviceNames(net).length != 1 || w1700kWifiLocalRadio(net) != radioName ||
			    net.get?.('mlo') == '1' || net.ubus?.('net', 'config', 'mlo') == '1')
				continue;
			const local = net.ubus?.('net', 'iwinfo');
			if (local && (local.channel != null || local.frequency != null)) {
				iwinfo = local;
				source = 'network';
				break;
			}
		}
	}
	let channel = +iwinfo.channel;
	let frequency = +iwinfo.frequency;
	let bitrate = +iwinfo.bitrate;

	channel = Number.isInteger(channel) && channel > 0 ? channel : null;
	frequency = Number.isFinite(frequency) && frequency > 0
		? (frequency > 100 ? frequency / 1000 : frequency)
		: null;
	bitrate = Number.isFinite(bitrate) && bitrate > 0
		? bitrate / 1000
		: null;

	const expected = w1700kChannelFrequencyGHz(radioBand, channel);
	const knownBand = [ '2g', '5g', '6g' ].includes(radioBand);
	if (!radioDev?.isUp?.() ||
	    (knownBand && frequency != null && !w1700kFrequencyMatchesBand(radioBand, frequency)) ||
	    (knownBand && channel != null && expected == null) ||
	    (radioBand == '6g' && channel != null && channel != 2 && (channel - 1) % 4 != 0) ||
	    (expected != null && frequency != null && Math.abs(expected - frequency) > 0.0025)) {
		channel = null;
		frequency = null;
		bitrate = null;
	}

	if (frequency == null && (w1700kRadioMapActive() ||
	    (wifiNets || []).some(net => w1700kWifiNetDeviceNames(net).length > 1 || net.get?.('mlo') == '1')))
		bitrate = null;

	if (channel == null)
		source = 'unavailable';

	return {
		channel,
		frequency,
		bitrate,
		source,
		configuredChannel: Number.isFinite(configuredChannel) && configuredChannel > 0 ? configuredChannel : null,
		configuredFrequency: w1700kFrequencyMatchesBand(radioBand, configuredFrequency) ? configuredFrequency : null
	};
}

function w1700kWifiNetDeviceNames(wifiNet) {
	if (!wifiNet)
		return [];
	if (typeof wifiNet.getWifiDeviceNames == 'function')
		return w1700kDeviceNames(wifiNet.getWifiDeviceNames());
	if (typeof wifiNet.getWifiDeviceName == 'function')
		return w1700kDeviceNames(wifiNet.getWifiDeviceName());
	return [];
}

function w1700kWifiUsesRadio(wifiNet, radioname) {
	return w1700kWifiNetDeviceNames(wifiNet).indexOf(radioname) >= 0;
}

function w1700kWifiPrimaryRadio(wifiNet) {
	const section = wifiNet?.sid || (typeof wifiNet?.getName == 'function' ? wifiNet.getName() : null);
	const configured = section
		? w1700kDeviceNames(uci.get('wireless', section, 'device'))
		: [];
	const radios = w1700kWifiNetDeviceNames(wifiNet);

	return configured[0] || (radios.length ? radios[0] : null);
}

function w1700kWifiLocalRadio(wifiNet) {
	const runtime = typeof wifiNet?.ubus == 'function' ? wifiNet.ubus('radio') : null;

	if (runtime)
		return runtime;
	if (typeof wifiNet?.getWifiDeviceName == 'function')
		return wifiNet.getWifiDeviceName();

	return w1700kWifiNetDeviceNames(wifiNet)[0] || null;
}

function w1700kUniqueWifiNetworks(networks) {
	const seen = Object.create(null);
	const unique = [];

	for (let wifiNet of networks || []) {
		if (!wifiNet)
			continue;

		const name = typeof wifiNet.getName == 'function' ? wifiNet.getName() : null;

		if (!name) {
			unique.push(wifiNet);
			continue;
		}

		if (seen[name] == null) {
			seen[name] = unique.length;
			unique.push(wifiNet);
			continue;
		}

		const index = seen[name];
		const primary = w1700kWifiPrimaryRadio(wifiNet);
		if (primary && w1700kWifiLocalRadio(wifiNet) == primary &&
		    w1700kWifiLocalRadio(unique[index]) != primary)
			unique[index] = wifiNet;
	}

	return unique;
}

function w1700kIfaceConfigUsesRadio(wifiIface, radioname) {
	return w1700kDeviceNames(wifiIface?.device).indexOf(radioname) >= 0;
}

function w1700kRadioDisabled(radioname) {
	return radioname && uci.get('wireless', radioname, 'disabled') == '1';
}

function w1700kHtmodeWidth(htmode) {
	const match = String(htmode || '20').match(/(20|40|80|160|320)/);
	return match ? +match[1] : 20;
}

function w1700kStaticApChannels(band) {
	const rv = {};

	switch (band) {
	case '2g':
		for (let i = 1; i <= 13; i++)
			rv[i] = true;
		break;
	case '5g':
		for (let ch of W1700K_5G_STATIC_AP_CHANNELS)
			rv[ch] = true;
		break;
	case '6g':
		rv[2] = true;
		for (let i = 1; i <= 233; i += 4)
			rv[i] = true;
		break;
	}

	return rv;
}

function w1700kApChannelsForBand(band, apChannels) {
	return (apChannels && apChannels[band]) || w1700kStaticApChannels(band);
}

function w1700kApChannelsFromFrequencyList(section_id, freqlist) {
	const lockedBand = w1700kRadioBand(section_id);
	const apChannels = { '2g': {}, '5g': {}, '6g': {}, '60g': {} };

	for (const freq of freqlist || []) {
		const band = freq.band ? String(freq.band) + 'g' : null;
		const flags = Array.isArray(freq.flags) ? freq.flags : [];
		const noIr = freq.no_ir || flags.some(flag => String(flag).toLowerCase() == 'no_ir');

		if (!band || !apChannels[band] || (lockedBand && band != lockedBand))
			continue;
		if (!freq.disabled && !noIr && w1700kRuntimeChannelAllowed(section_id, freq.channel))
			apChannels[band][freq.channel] = true;
	}

	return apChannels;
}

function w1700kLoadMloApChannels(devices) {
	const tasks = w1700kDeviceNames(devices).map(function(dev) {
		return L.resolveDefault(callIwinfoFrequencyList(dev), null).then(function(freqlist) {
			return [ dev, Array.isArray(freqlist) && freqlist.length
				? w1700kApChannelsFromFrequencyList(dev, freqlist)
				: null ];
		});
	});

	return Promise.all(tasks).then(function(entries) {
		const maps = {};

		for (const [ dev, channels ] of entries)
			maps[dev] = channels;

		return maps;
	});
}

function w1700kChannelsUsable(channels, apChannels) {
	if (!channels || !channels.length)
		return false;

	for (let ch of channels)
		if (!apChannels[ch])
			return false;

	return true;
}

function w1700kRunWidthBlock(channel, width, runs) {
	const groupSize = width / 20;

	if (width <= 20)
		return [ channel ];

	for (let run of runs) {
		const pos = run.indexOf(channel);

		if (pos < 0)
			continue;

		const start = Math.floor(pos / groupSize) * groupSize;
		const block = run.slice(start, start + groupSize);

		return block.length == groupSize ? block : null;
	}

	return null;
}

function w1700k5gWidthBlock(channel, width) {
	if (width != 20 && width != 40 && width != 80 && width != 160)
		return null;

	/*
	 * The upper 149-177 run is modeled for future regulatory databases, but
	 * every 20 MHz subchannel still has to be AP-usable in the live map.
	 */
	return w1700kRunWidthBlock(channel, width, W1700K_5G_CHANNEL_RUNS);
}

function w1700k6gWidthBlock(channel, width) {
	if (channel == 2)
		return width <= 20 ? [ channel ] : null;

	if (channel < 1 || channel > 233 || ((channel - 1) % 4) != 0)
		return null;
	if ([ 20, 40, 80, 160, 320 ].indexOf(width) < 0)
		return null;

	if (width <= 20)
		return [ channel ];

	/* hostapd's fourth 320 MHz center (191) overlaps the third block. */
	if (width == 320 && channel > 189 && channel <= 221) {
		const block = [];

		for (let ch = 161; ch <= 221; ch += 4)
			block.push(ch);

		return block;
	}

	const groupSize = width / 20;
	const index = (channel - 1) / 4;
	const start = Math.floor(index / groupSize) * groupSize;
	const rv = [];

	for (let i = 0; i < groupSize; i++) {
		const ch = 1 + (start + i) * 4;
		if (ch > 233)
			return null;
		rv.push(ch);
	}

	return rv;
}

function w1700kHtmodeAllowed(section_id, htmode, channel, apChannels) {
	const info = w1700kRadioInfo(section_id);
	let width, channels;

	if (!info && w1700kRadioMapActive())
		return false;
	if (!info || !htmode)
		return true;

	if (htmode == 'NOHT')
		return info.band != '6g' && w1700kChannelAllowed(section_id, channel, apChannels);

	switch (info.band) {
	case '2g':
		if (!/^(HT|HE|EHT)(20|40)(\+|-)?$/.test(htmode))
			return false;
		break;
	case '5g':
		if (!/^(HT|VHT|HE|EHT)(20|40|80|160)(\+|-)?$/.test(htmode))
			return false;
		break;
	case '6g':
		if (!/^(HE|EHT)(20|40|80|160|320)$/.test(htmode))
			return false;
		break;
	}

	if (channel == null || channel == '')
		return true;

	channel = String(channel);
	width = w1700kHtmodeWidth(htmode);

	if (channel == 'auto') {
		switch (info.band) {
		case '5g':
			if (width > 80)
				return false;
			break;
		case '6g':
			if (width > 80)
				return false;
			break;
		}

		const liveChannels = w1700kApChannelsForBand(info.band, apChannels);
		return Object.keys(liveChannels).some(function(ch) {
			return w1700kHtmodeAllowed(section_id, htmode, ch, apChannels);
		});
	}

	channel = +channel;

	if (!Number.isInteger(channel))
		return false;
	if (info.band == '2g' && channel == 14)
		return w1700kDeviceCountry(section_id) == 'JP' && htmode == 'NOHT';

	switch (info.band) {
	case '2g':
		if (width <= 20)
			channels = [ channel ];
		else
			return w1700kChannelsUsable([ channel, channel + 4 ], w1700kApChannelsForBand('2g', apChannels)) ||
				w1700kChannelsUsable([ channel, channel - 4 ], w1700kApChannelsForBand('2g', apChannels));
		break;
	case '5g':
		channels = w1700k5gWidthBlock(channel, width);
		break;
	case '6g':
		channels = w1700k6gWidthBlock(channel, width);
		break;
	}

	return w1700kChannelsUsable(channels, w1700kApChannelsForBand(info.band, apChannels));
}

function w1700kChannelValuesForHtmode(section_id, channelValues, htmode, apChannels) {
	const rv = [];

	for (let i = 0; channelValues && i < channelValues.length; i += 3) {
		const meta = Object.assign({}, channelValues[i + 2] || {});

		meta.available = !!meta.available &&
			(!htmode || w1700kHtmodeAllowed(section_id, htmode, channelValues[i], apChannels));

		rv.push(channelValues[i], channelValues[i + 1], meta);
	}

	return rv;
}

function w1700kPunctWidthAllowed(section_id, htmode) {
	const info = w1700kRadioInfo(section_id);
	const width = w1700kHtmodeWidth(htmode);

	if (!info || !/^EHT/.test(String(htmode || '')))
		return false;

	switch (info.band) {
	case '5g':
		return width == 80 || width == 160;
	case '6g':
		return width == 80 || width == 160 || width == 320;
	}

	return false;
}

function w1700kParsePunctBitmap(value) {
	value = String(value || '').trim();

	if (value == '')
		return 0;

	if (!/^(0x[0-9a-fA-F]+|[0-9]+)$/.test(value))
		return null;

	const n = value.slice(0, 2).toLowerCase() == '0x' ? parseInt(value, 16) : parseInt(value, 10);

	return Number.isInteger(n) && n >= 0 && n <= 0xffff ? n : null;
}

function w1700kPunctPrimaryBit(section_id, channel, width) {
	const info = w1700kRadioInfo(section_id);
	let block;

	channel = +channel;

	if (!info || !Number.isInteger(channel))
		return null;

	if (info.band == '5g') {
		block = w1700k5gWidthBlock(channel, width);
		return block ? block.indexOf(channel) : null;
	}
	else if (info.band == '6g') {
		block = w1700k6gWidthBlock(channel, width);
		return block ? block.indexOf(channel) : null;
	}

	return null;
}

function w1700kValidatePunctBitmap(section_id, htmode, channel, value) {
	const bitmap = w1700kParsePunctBitmap(value);
	const width = w1700kHtmodeWidth(htmode);
	const mask = width == 80 ? 0xf : width == 160 ? 0xff : width == 320 ? 0xffff : 0;
	const valid = W1700K_PUNCT_ACTIVE_MASKS[width] || [];
	let active, primaryBit;

	if (bitmap == null)
		return _('Use a decimal value or a hexadecimal value such as 0x0002.');

	if (bitmap == 0)
		return true;

	if (!w1700kPunctWidthAllowed(section_id, htmode))
		return _('EHT puncturing requires 5GHz or 6GHz EHT80 or wider.');

	if (channel == null || channel == '' || channel == 'auto')
		return _('Manual EHT puncturing requires a fixed channel.');

	primaryBit = w1700kPunctPrimaryBit(section_id, channel, width);
	if (primaryBit == null)
		return _('The puncturing bitmap cannot be mapped to this channel width.');

	active = (~bitmap) & mask;
	if (!active)
		return _('At least one 20 MHz subchannel must remain active.');

	if ((active & (1 << primaryBit)) == 0)
		return _('The primary 20 MHz subchannel cannot be punctured.');

	if (valid.indexOf(active) < 0)
		return _('This puncturing pattern is not valid for the selected channel width.');

	return true;
}

function w1700kDefaultHtmode(section_id, mode) {
	const info = w1700kRadioInfo(section_id);

	return info ? (info.defaultHtmode[mode] || info.defaultHtmode.be || info.defaultHtmode.ax || 'NOHT') : null;
}

// Runtime rows supply regulatory availability; only check the mapped channel shape here.
function w1700kRuntimeChannelAllowed(section_id, channel) {
	const info = w1700kRadioInfo(section_id);
	const n = +channel;

	if (!info && w1700kRadioMapActive())
		return false;
	if (!info)
		return true;
	if (!Number.isInteger(n) || n <= 0)
		return false;

	switch (info.band) {
	case '2g':
		return n <= 14;
	case '5g':
		return (n >= 36 && n <= 144 && n % 4 == 0) ||
			(n >= 149 && n <= 177 && (n - 149) % 4 == 0);
	case '6g':
		return n == 2 || (n <= 233 && (n - 1) % 4 == 0);
	}

	return false;
}

function w1700kChannelAllowed(section_id, channel, apChannels) {
	const info = w1700kRadioInfo(section_id);
	const country = w1700kDeviceCountry(section_id);
	let n, max2g;

	if (!info && w1700kRadioMapActive())
		return false;
	if (!info || channel == null || channel == '')
		return true;
	if (channel == 'auto')
		return !apChannels?.[info.band] || Object.keys(apChannels[info.band]).length > 0;

	n = +channel;
	if (!Number.isInteger(n))
		return false;

	if (apChannels && apChannels[info.band])
		return apChannels[info.band][n] === true;

	switch (info.band) {
	case '2g':
		max2g = (country == 'US' || country == 'CA' || country == 'MX') ? 11 : 13;
		return (n >= 1 && n <= max2g) || (country == 'JP' && n == 14);
	case '5g':
		return W1700K_5G_STATIC_AP_CHANNELS.indexOf(n) >= 0;
	case '6g':
		return n == 2 || (n >= 1 && n <= 233 && ((n - 1) % 4) == 0);
	}

	return true;
}

function w1700kDeviceDisabled(dev) {
	return uci.get('wireless', dev, 'disabled') == '1';
}

function w1700kNormalizeCountry(country) {
	country = String(country || '').toUpperCase();
	return (!country || country == '00') ? 'US' : country;
}

function w1700kDeviceCountry(dev) {
	return w1700kNormalizeCountry(uci.get('wireless', dev, 'country'));
}

function w1700kExplicitDeviceCountry(dev) {
	const country = String(uci.get('wireless', dev, 'country') || '').toUpperCase();

	return /^[A-Z]{2}$/.test(country) && country != '00' ? country : null;
}

function w1700kChannelFrequencyGHz(band, channel) {
	channel = +channel;

	if (!Number.isFinite(channel))
		return null;

	switch (band) {
	case '2g':
		if (channel == 14)
			return 2.484;
		if (channel >= 1 && channel <= 13)
			return +(2.407 + channel * 0.005).toFixed(3);
		break;
	case '5g':
		if (channel >= 1 && channel <= 177)
			return +(5.0 + channel * 0.005).toFixed(3);
		break;
	case '6g':
		if (channel == 2)
			return 5.935;
		if (channel >= 1 && channel <= 233)
			return +(5.95 + channel * 0.005).toFixed(3);
		break;
	}

	return null;
}

function w1700kFrequencyMatchesBand(band, frequency) {
	frequency = +frequency;

	if (!Number.isFinite(frequency))
		return false;

	switch (band) {
	case '2g':
		return frequency >= 2.4 && frequency < 2.5;
	case '5g':
		return frequency >= 5.0 && frequency < 5.925;
	case '6g':
		return frequency >= 5.925 && frequency <= 7.125;
	}

	return false;
}

function w1700kScanResultFrequencyGHz(result) {
	const frequency = +(result?.mhz ?? result?.frequency);

	if (!Number.isFinite(frequency) || frequency <= 0)
		return null;

	return frequency >= 1000 ? frequency / 1000 : frequency;
}

function w1700kScanResultBand(result) {
	const frequency = w1700kScanResultFrequencyGHz(result);

	if (frequency != null) {
		for (let band of [ '2g', '5g', '6g' ])
			if (w1700kFrequencyMatchesBand(band, frequency))
				return band;
	}

	switch (String(result?.band ?? '').toLowerCase().replace(/\s+/g, '')) {
	case '2':
	case '2g':
	case '2.4':
	case '2.4g':
	case '2.4ghz':
		return '2g';
	case '5':
	case '5g':
	case '5ghz':
		return '5g';
	case '6':
	case '6g':
	case '6ghz':
		return '6g';
	}

	return null;
}

function w1700kScanResultMatchesRadio(radioDev, result) {
	const expectedBand = w1700kRadioBand(radioDev?.getName?.());

	return expectedBand == null || w1700kScanResultBand(result) == expectedBand;
}

function w1700kScanOperationWidth(operation, fallback) {
	const width = +(operation?.channel_width);

	return [ 20, 40, 80, 160, 320 ].indexOf(width) >= 0 ? width : fallback;
}

function w1700kValidSsid(value) {
	return typeof value == 'string' && value.length > 0 && new TextEncoder().encode(value).length <= 32;
}

function w1700kScanJoinHtmode(radioDev, bss, currentHtmode) {
	const radioName = radioDev?.getName?.();
	if (!Number.isInteger(+bss?.channel) || +bss.channel <= 0 ||
	    !w1700kScanResultMatchesRadio(radioDev, bss) ||
	    !w1700kChannelAllowed(radioName, bss.channel))
		return null;
	const htmodes = L.toArray(radioDev?.getHTModes?.());
	const current = String(currentHtmode || '');
	const currentValid = /^(?:NOHT|(?:HT|VHT|HE|EHT)(?:20|40|80|160|320)(?:\+|-)?)$/.test(current) &&
		(!htmodes.length || htmodes.indexOf(current) >= 0) &&
		w1700kHtmodeAllowed(radioName, current, bss?.channel);
	const operations = [
		[ 'EHT', bss?.eht_operation, w1700kScanOperationWidth(bss?.eht_operation, 20), [ 320, 160, 80, 40, 20 ] ],
		[ 'HE', bss?.he_operation, w1700kScanOperationWidth(bss?.he_operation, 20), [ 160, 80, 40, 20 ] ],
		[ 'VHT', bss?.vht_operation, w1700kScanOperationWidth(bss?.vht_operation, 20), [ 160, 80, 40, 20 ] ],
		[ 'HT', bss?.ht_operation, w1700kScanOperationWidth(bss?.ht_operation, 20),
			[ 40, 20 ] ]
	];

	for (const [ prefix, operation, maximumWidth, widths ] of operations) {
		if (operation == null)
			continue;
		for (const width of widths) {
			const htmode = prefix + width;

			if (width <= maximumWidth && htmodes.indexOf(htmode) >= 0 &&
			    w1700kHtmodeAllowed(radioName, htmode, bss?.channel))
				return htmode;
		}
	}

	if (currentValid && operations.every(function(entry) { return entry[1] == null; }))
		return current;

	return null;
}

function w1700kDeviceIs6g(dev) {
	return w1700kRadioBand(dev) == '6g';
}

function w1700kFormValue(section, section_id, option) {
	const opt = section?.children?.filter(function(o) { return o.option == option; })[0];

	if (opt && opt.isActive(section_id))
		return opt.formvalue(section_id);

	return uci.get('wireless', section_id, option);
}

function w1700kCurrentOptionValue(option, section_id, fallback) {
	if (option?.getUIElement?.(section_id))
		return option.formvalue(section_id);

	return fallback;
}

function w1700kCurrentFrequencyValue(option, section_id) {
	const fallback = [
		uci.get('wireless', section_id, 'htmode'),
		uci.get('wireless', section_id, 'hwmode') || uci.get('wireless', section_id, 'band'),
		uci.get('wireless', section_id, 'channel')
	];
	const value = L.toArray(w1700kCurrentOptionValue(option, section_id, fallback));

	return [ value[0] ?? fallback[0], value[1] ?? fallback[1], value[2] ?? fallback[2] ];
}

function w1700kFrequencyWidgetActive(ifaceSection, ifaceSectionId) {
	return w1700kFormValue(ifaceSection, ifaceSectionId, 'mlo') != '1';
}

function w1700kSetFormValue(section, section_id, option, value) {
	const opt = section?.children?.filter(function(o) { return o.option == option; })[0];
	const elem = opt ? opt.getUIElement(section_id) : null;

	uci.set('wireless', section_id, option, value);

	if (elem && elem.setValue)
		elem.setValue(value);
}

function w1700kNormalizeDeviceList(value, current) {
	const seen = {};
	const devices = [];

	w1700kDeviceNames(value).forEach(function(dev) {
		dev = (dev != null) ? String(dev) : '';

		if (!dev || seen[dev])
			return;

		seen[dev] = true;
		devices.push(dev);
	});

	if (current && !seen[current])
		devices.unshift(current);

	devices.sort(function(a, b) {
		const ranks = { 1: 0, 2: 1, 0: 2 };
		const aidx = w1700kRadioIndex(a);
		const bidx = w1700kRadioIndex(b);
		const arank = (ranks[aidx] != null) ? ranks[aidx] : 100 + aidx;
		const brank = (ranks[bidx] != null) ? ranks[bidx] : 100 + bidx;

		if (arank != brank)
			return arank - brank;

		return a.localeCompare(b);
	});

	return devices;
}

function w1700kMloRadioOwner(section_id, radioname) {
	let owner = null;

	uci.sections('wireless', 'wifi-iface').some(function(iface) {
		if (iface['.name'] == section_id || iface.disabled == '1' || iface.mlo != '1')
			return false;
		if (w1700kDeviceNames(iface.device).indexOf(radioname) < 0)
			return false;

		owner = iface;
		return true;
	});

	return owner;
}

function w1700kMloOwnerLabel(owner) {
	if (!owner)
		return '';

	return owner.ssid || owner['.name'];
}

function w1700kAvailableMloDevices(section_id, current) {
	const devices = [];

	uci.sections('wireless', 'wifi-device')
		.sort(function(a, b) { return w1700kRadioIndex(a['.name']) - w1700kRadioIndex(b['.name']); })
		.forEach(function(dev) {
			const name = dev['.name'];

			if (w1700kRadioMapActive() && !w1700kRadioInfo(name))
				return;
			if (w1700kMloRadioOwner(section_id, name))
				return;

			devices.push(name);
		});

	return w1700kNormalizeDeviceList(devices, current);
}

const w1700kMloSafeRadioDefaults = {
	'0': { channel: '6', htmodes: [ 'EHT20' ] },
	'1': { channel: '36', htmodes: [ 'EHT80', 'EHT40', 'EHT20' ] },
	'2': { channel: '37', htmodes: [ 'EHT160', 'EHT80', 'EHT40', 'EHT20' ] }
};

function w1700kMloRadioStateValid(dev, channel, htmode, apChannels) {
	const idx = w1700kRadioIndex(dev);

	return channel != null && channel != '' && channel != 'auto' &&
		/^EHT(?:20|40|80|160|320)$/.test(String(htmode || '')) &&
		(idx != '0' || htmode == 'EHT20') &&
		(idx != '1' || htmode != 'EHT320') &&
		w1700kChannelAllowed(dev, channel, apChannels) &&
		w1700kHtmodeAllowed(dev, htmode, channel, apChannels);
}

function w1700kMloSafeRadioState(dev, apChannels) {
	const defaults = w1700kMloSafeRadioDefaults[w1700kRadioIndex(dev)];
	const band = w1700kRadioBand(dev);
	const channels = [];

	if (!defaults || !band)
		return null;

	channels.push(defaults.channel);
	Object.keys(w1700kApChannelsForBand(band, apChannels))
		.sort(function(a, b) { return +a - +b; })
		.forEach(function(channel) {
			if (channels.indexOf(String(channel)) < 0)
				channels.push(String(channel));
		});

	for (const htmode of defaults.htmodes)
		for (const channel of channels)
			if (w1700kMloRadioStateValid(dev, channel, htmode, apChannels))
				return { channel, htmode };

	return null;
}

function w1700kEnsureMloRadioDefaults(devices, apChannelsByRadio) {
	let complete = true;

	w1700kDeviceNames(devices).forEach(function(dev) {
		const channel = uci.get('wireless', dev, 'channel');
		const htmode = uci.get('wireless', dev, 'htmode');
		const apChannels = apChannelsByRadio?.[dev] || null;
		const valid = w1700kMloRadioStateValid(dev, channel, htmode, apChannels);
		const safe = valid ? null : w1700kMloSafeRadioState(dev, apChannels);

		if (valid)
			return;
		if (!safe) {
			complete = false;
			return;
		}

		uci.set('wireless', dev, 'channel', safe.channel);
		uci.set('wireless', dev, 'htmode', safe.htmode);
	});

	return complete;
}

function w1700kSelectVisibleModalTab(name) {
	const tabs = document.querySelectorAll('ul.cbi-tabmenu > li[data-tab="%s"] > a'.format(name));

	for (let tab of tabs) {
		if (tab.offsetParent != null) {
			tab.click();
			return true;
		}
	}

	return false;
}

function w1700kSelectedDevices(section, section_id, current) {
	const opt = section?.children?.filter(function(o) { return o.option == '_mlo_devices'; })[0];
	const raw = (opt && opt.isActive(section_id)) ? opt.formvalue(section_id) : uci.get('wireless', section_id, 'device');
	const devices = w1700kNormalizeDeviceList(raw);

	return devices.length ? devices : w1700kNormalizeDeviceList(current);
}

function w1700kMloChoiceState(device, selected) {
	const disabled = String(device?.disabled || '') == '1';

	return { disabled: disabled, visible: !disabled || selected };
}

function w1700kRefreshMloChoices(option, section_id) {
	const elem = option?.getUIElement?.(section_id);
	const values = [];
	const labels = {};

	if (!elem?.clearChoices || !elem?.addChoices)
		return;

	for (let i = 0; i < option.keylist.length; i++) {
		const name = option.keylist[i];

		if (w1700kDeviceDisabled(name))
			continue;

		values.push(name);
		labels[name] = option.vallist[i];
	}

	elem.clearChoices(false);
	elem.addChoices(values, labels);
}

function w1700kValidateMloDevices(section_id, value, apChannelsByRadio) {
	const devices = w1700kNormalizeDeviceList(value);
	const countries = {};
	const indexes = {};

	if (devices.length < 2)
		return _('Select at least two radios for an MLO network.');

	for (let dev of devices) {
		const idx = w1700kRadioIndex(dev);
		const info = w1700kRadioInfo(dev);
		const conflict = w1700kRadioIndexConflict(dev);
		const owner = w1700kMloRadioOwner(section_id, dev);
		const band = uci.get('wireless', dev, 'band');
		const channel = uci.get('wireless', dev, 'channel');
		const htmode = uci.get('wireless', dev, 'htmode');
		const country = w1700kExplicitDeviceCountry(dev);
		const apChannels = apChannelsByRadio ? apChannelsByRadio[dev] : null;

		if (owner)
			return _('%s is already linked to MLO network %s. Edit that network instead.').format(
				w1700kRadioLabel(dev), w1700kMloOwnerLabel(owner));

		if (conflict)
			return _('Physical radio index %s is assigned to multiple sections: %s.').format(
				idx, conflict.join(', '));

		if (idx == null || (w1700kRadioMapActive() && !info))
			return idx == null
				? _('%s has no explicit physical radio index. Every W1700K MLO radio requires option radio 0, 1, or 2.').format(dev)
				: _('%s is not a supported W1700K physical radio.').format(dev);

		if (info && band != info.band)
			return _('%s is physical %s; it cannot be configured as %s.').format(
				w1700kRadioLabel(dev), info.label, band || _('unset'));

		if (indexes[idx])
			return _('Multiple MLO links cannot use physical radio index %s.').format(idx);
		indexes[idx] = true;

		if (w1700kDeviceDisabled(dev))
			return _('%s is disabled and cannot be used for MLO.').format(dev);

		if (!channel || channel == 'auto')
			return _('%s requires a fixed channel for MLO.').format(w1700kRadioLabel(dev));

		if (!/^EHT(?:20|40|80|160|320)$/.test(String(htmode || '')))
			return _('%s must use an EHT width for MLO; current mode is %s.').format(
				w1700kRadioLabel(dev), htmode || _('unset'));

		if (idx == '0' && htmode != 'EHT20')
			return _('%s requires EHT20 when used by MLO.').format(w1700kRadioLabel(dev));

		if (idx == '1' && htmode == 'EHT320')
			return _('%s cannot use EHT320; 320 MHz is only available on the 6 GHz radio.').format(
				w1700kRadioLabel(dev));

		if (!country)
			return _('%s requires an explicit two-letter regulatory country for MLO; world regdomain 00 is not valid.').format(
				w1700kRadioLabel(dev));

		if (apChannelsByRadio && !apChannels)
			return _('Could not load the live AP channel map for %s. Reload the page before saving.').format(
				w1700kRadioLabel(dev));

		if (!w1700kChannelAllowed(dev, channel, apChannels))
			return _('Channel %s is not AP-usable on %s.').format(channel, w1700kRadioLabel(dev));

		if (!w1700kHtmodeAllowed(dev, htmode, channel, apChannels))
			return _('%s is not valid on channel %s for %s.').format(
				htmode, channel, w1700kRadioLabel(dev));

		countries[country] = true;
	}

	if (Object.keys(countries).length > 1)
		return _('All MLO radios must use the same country code.');

	return true;
}

function w1700kCurrentPuncturingState(deviceSection, deviceSectionId,
		ifaceSection, ifaceSectionId, frequencyOption, overrides) {
	const frequency = w1700kCurrentFrequencyValue(frequencyOption, deviceSectionId);
	const has = function(name) { return overrides && Object.prototype.hasOwnProperty.call(overrides, name); };

	return {
		htmode: frequency[0],
		channel: frequency[2],
		mlo: w1700kFormValue(ifaceSection, ifaceSectionId, 'mlo') == '1',
		devices: w1700kSelectedDevices(ifaceSection, ifaceSectionId),
		bitmap: has('bitmap') ? overrides.bitmap : w1700kFormValue(deviceSection, deviceSectionId, 'punct_bitmap'),
		threshold: has('threshold') ? overrides.threshold : w1700kFormValue(deviceSection, deviceSectionId, 'punct_acs_threshold')
	};
}

function w1700kSecureFor6gOrMlo(encryption) {
	const parts = String(encryption || '').toLowerCase().split('+');

	return parts.indexOf('tkip') < 0 &&
		(parts[0] == 'sae' || parts[0] == 'owe' || parts[0] == 'wpa3' || parts[0] == 'wpa3-192');
}

function w1700kModeIsApLike(mode) {
	return mode == 'ap' || mode == 'ap-wds';
}

function w1700kUses6gOrMlo(section, section_id, current) {
	const mlo = w1700kFormValue(section, section_id, 'mlo') == '1';
	const devices = w1700kSelectedDevices(section, section_id, current);

	return devices.some(w1700kDeviceIs6g) || (mlo && devices.length > 1);
}

function w1700kEnsure6gMloApDefaults(section, section_id, apChannelsByRadio) {
	const mode = w1700kFormValue(section, section_id, 'mode');
	const mlo = w1700kFormValue(section, section_id, 'mlo') == '1';
	const encryption = w1700kFormValue(section, section_id, 'encryption');
	const effectiveEncryption = w1700kSecureFor6gOrMlo(encryption) ? encryption : 'sae';
	const networks = L.toArray(w1700kFormValue(section, section_id, 'network'));
	const devices = w1700kSelectedDevices(section, section_id);

	if (!w1700kModeIsApLike(mode))
		return;

	if (mlo && devices.length > 1)
		w1700kEnsureMloRadioDefaults(devices, apChannelsByRadio);

	if (!w1700kSecureFor6gOrMlo(encryption))
		w1700kSetFormValue(section, section_id, 'encryption', 'sae');

	w1700kSetFormValue(section, section_id, 'ieee80211w', '2');
	w1700kSetFormValue(section, section_id, 'rnr', '1');

	if (String(effectiveEncryption || '').replace(/\+.*$/, '') == 'sae')
		w1700kSetFormValue(section, section_id, 'sae_pwe', '2');

	if (!networks.length || (networks.indexOf('lan') >= 0 && (networks.indexOf('wan') >= 0 || networks.indexOf('wan6') >= 0)))
		w1700kSetFormValue(section, section_id, 'network', 'lan');
}

function count_changes(section_id) {
	const changes = ui.changes.changes?.wireless;
	if (!Array.isArray(changes)) return 0;

	return changes.reduce((count, [, id]) => count + (id === section_id), 0);
}

function render_radio_badge(radioDev) {
	return E('span', { 'class': 'ifacebadge' }, [
		E('img', { 'src': L.resource('icons/wifi%s.svg').format(radioDev.isUp() ? '' : '_disabled') }),
		' ',
		w1700kRadioLabel(radioDev.getName())
	]);
}

function buildSVGQRCode(data, code, options, dummy=false) {
	const opts = {
		pixelSize: 4,
		whiteColor: 'white',
		blackColor: 'black',
		ecc: 'M',
		...options
	};
	const svg = uqr.renderSVG(data, opts);
	if (dummy)
		return svg;
	else {
		code.style.opacity = '';
		dom.content(code, Object.assign(E(svg), { style: 'width:100%;height:auto' }));
	}
}

function render_signal_badge(signalPercent, signalValue, noiseValue, wrap, mode) {
	let icon = L.resource('icons/signal-075-100.svg'), title, value;

	switch(true) {
	case(signalPercent  < 0): icon = L.resource('icons/signal-none.svg'); 	break;
	case(signalPercent == 0): icon = L.resource('icons/signal-000-000.svg');		break;
	case(signalPercent < 25): icon = L.resource('icons/signal-000-025.svg'); 	break;
	case(signalPercent < 50): icon = L.resource('icons/signal-025-050.svg');	break;
	case(signalPercent < 75): icon = L.resource('icons/signal-050-075.svg');	break;
	}

	if (signalValue) {
		if (noiseValue) {
			value = `${signalValue}/${noiseValue}\xa0${_('dBm')}`;
			title = [
				`${_('Signal')}: ${signalValue} ${_('dBm')}`,
				`${_('Noise')}: ${noiseValue} ${_('dBm')}`,
				`${_('SNR')}: ${signalValue - noiseValue} ${_('dBm')}`
			].filter(Boolean).join(' / ');
		}
		else {
			value = `${signalValue}\xa0${_('dBm')}`;
			title = `${_('Signal')} ${signalValue} ${_('dBm')}`;
		}
	}
	else if (signalPercent > -1) {
		switch (mode) {
			case 'ap':
				title = _('No client associated');
				break;

			case 'sta':
			case 'adhoc':
			case 'mesh':
				title = _('Not associated');
				break;

			default:
				title = _('No RX signal');
		}

		if (noiseValue) {
			value = `---/${noiseValue}\xa0${_('dBm')}`;
			title = `${title} / ${_('Noise')}: ${noiseValue} ${_('dBm')}`;
		}
		else {
			value = `---\xa0${_('dBm')}`;
		}
	}
	else {
		value = E('em', {}, E('small', {}, [ _('disabled') ]));
		title = _('Interface is disabled');
	}

	return E('div', {
		'class': wrap ? 'center' : 'ifacebadge',
		'title': title,
		'data-signal': signalValue,
		'data-noise': noiseValue
	}, [
		E('img', { 'src': icon }),
		E('span', {}, [
			wrap ? E('br') : ' ',
			value
		])
	]);
}

function render_network_badge(radioNet) {
	const isUp = radioNet && radioNet.getDevice && radioNet.getIfname && radioNet.getIfname() != null && radioNet.isUp();

	return render_signal_badge(
		isUp ? radioNet.getSignalPercent() : -1,
		radioNet?.getSignal ? radioNet.getSignal() : 0,
		radioNet?.getNoise ? radioNet.getNoise() : 0,
		false,
		radioNet?.getMode ? radioNet.getMode() : null);
}

function render_radio_status(radioDev, wifiNets) {
	const name = radioDev.getI18n().replace(/ Wireless Controller .+$/, '');
	const node = E('div', [ E('big', {}, E('strong', {}, name)), E('div') ]);
	const facts = w1700kRadioRuntimeFacts(radioDev, wifiNets);

	if (radioDev.isUp())
		L.itemlist(node.lastElementChild, [
			_('Channel'), facts.channel != null && facts.frequency != null
				? `${facts.channel} (${facts.frequency} ${_('GHz')})` : null,
			_('Configured channel'), facts.channel == null && facts.configuredChannel != null && facts.configuredFrequency != null
				? `${facts.configuredChannel} (${facts.configuredFrequency} ${_('GHz')})` : null,
			_('Bitrate'), facts.bitrate != null ? `${facts.bitrate} ${_('Mbit/s')}` : null
		], ' | ');
	else
		node.lastElementChild.appendChild(E('em', _('Device is not active')));

	return node;
}

function render_network_status(radioNet) {
	if (!radioNet)
		return E('em', _('Wireless network is unavailable'));

	const mode = radioNet.getActiveMode();
	const bssid = radioNet.getActiveBSSID();
	const channel = radioNet.getChannel();
	const disabled = (radioNet.get('disabled') == '1' ||
		w1700kWifiNetDeviceNames(radioNet).some(w1700kRadioDisabled));
	const is_assoc = (bssid && bssid != '00:00:00:00:00:00' && channel && mode != 'Unknown' && !disabled);
	const is_mesh = (radioNet.getMode() == 'mesh');
	const changecount = count_changes(radioNet.getName());
	let status_text = null;

	if (changecount)
		status_text = E('a', {
			href: '#',
			click: L.bind(ui.changes.displayChanges, ui.changes)
		}, _('Interface has %d pending changes').format(changecount));
	else if (!is_assoc)
		status_text = E('em', disabled ? _('Wireless is disabled') : _('Wireless is not associated'));

	return L.itemlist(E('div'), [
		is_mesh ? _('Mesh ID') : _('SSID'), (is_mesh ? radioNet.getMeshID() : radioNet.getSSID()) ?? '?',
		_('Mode'),       mode,
		_('BSSID'),      (!changecount && is_assoc) ? bssid : null,
		_('Encryption'), (!changecount && is_assoc) ? radioNet.getActiveEncryption() ?? _('None') : null,
		'',            status_text
	], [ ' | ', E('br') ]);
}

function render_modal_status(node, radioNet) {
	if (!radioNet) return;

	const mode = radioNet.getActiveMode();
	const noise = radioNet.getNoise();
	const bssid = radioNet.getActiveBSSID();
	const channel = radioNet.getChannel();
	const disabled = (radioNet.get('disabled') == '1' ||
		w1700kWifiNetDeviceNames(radioNet).some(w1700kRadioDisabled));
	const is_assoc = (bssid && bssid != '00:00:00:00:00:00' && channel && mode != 'Unknown' && !disabled);

	if (node == null)
		node = E('span', { 'class': 'ifacebadge large', 'data-network': radioNet.getName() }, [ E('small'), E('span') ]);

	dom.content(node.firstElementChild, render_signal_badge(
		disabled ? -1 : radioNet.getSignalPercent(),
		radioNet.getSignal(), noise, true, radioNet.getMode()));

	L.itemlist(node.lastElementChild, [
		_('Mode'),       mode,
		_('SSID'),       radioNet.getSSID() ?? '?',
		_('BSSID'),      is_assoc ? bssid : null,
		_('Encryption'), is_assoc ? radioNet.getActiveEncryption() ?? _('None') : null,
		_('Channel'),    is_assoc ? `${radioNet.getChannel()} (${radioNet.getFrequency() ?? 0} ${_('GHz')})` : null,
		_('Tx-Power'),   is_assoc ? `${radioNet.getTXPower()} ${_('dBm')}` : null,
		_('Signal'),     is_assoc ? `${radioNet.getSignal()} ${_('dBm')}` : null,
		_('Noise'),      (is_assoc && noise != null) ? `${noise} ${_('dBm')}` : null,
		_('Bitrate'),    is_assoc ? `${radioNet.getBitRate() ?? 0} ${_('Mbit/s')}` : null,
		_('Country'),    is_assoc ? radioNet.getCountryCode() : null
	], [ ' | ', E('br'), E('br'), E('br'), E('br'), E('br'), ' | ', E('br'), ' | ' ]);

	if (!is_assoc)
		dom.append(node.lastElementChild, E('em', disabled ? _('Wireless is disabled') : _('Wireless is not associated')));

	return node;
}

function format_wifirate(rate) {
	let s = `${rate.rate / 1000}\xa0${_('Mbit/s')}, ${rate.mhz}\xa0${_('MHz')}`;

	if (rate?.ht || rate?.vht) s += [
		rate?.vht && `, VHT-MCS\xa0${rate?.mcs}`,
		rate?.nss && `, VHT-NSS\xa0${rate?.nss}`,
		rate?.ht  && `, MCS\xa0${rate?.mcs}`,
		rate?.short_gi && ', ' + _('Short GI').replace(/ /g, '\xa0')
	].filter(Boolean).join('');

	if (rate?.he) s += [
		`, HE-MCS\xa0${rate?.mcs}`,
		rate?.nss    && `, HE-NSS\xa0${rate?.nss}`,
		rate?.he_gi  && `, HE-GI\xa0${rate?.he_gi}`,
		rate?.he_dcm && `, HE-DCM\xa0${rate?.he_dcm}`
	].filter(Boolean).join('');

	if (rate?.eht) s += [
		`, EHT-MCS\xa0${rate?.mcs}`,
		rate?.nss    && `, EHT-NSS\xa0${rate?.nss}`,
		rate?.eht_gi  && `, EHT-GI\xa0${rate?.eht_gi}`,
		rate?.eht_dcm && `, EHT-DCM\xa0${rate?.eht_dcm}`
	].filter(Boolean).join('');

	return s;
}

function radio_restart(id, ev) {
	const row = document.querySelector('.cbi-section-table-row[data-sid="%s"]'.format(id));
	const dsc = row.querySelector('[data-name="_stat"] > div');
	const btn = row.querySelector('.cbi-section-actions button');

	btn.blur();
	btn.classList.add('spinning');
	btn.disabled = true;

	dsc.setAttribute('restart', '');
	dom.content(dsc, E('em', _('Device is restarting…')));
}

function network_updown(id, map, ev) {
	const radios = w1700kDeviceNames(uci.get('wireless', id, 'device'));
	const disabled = (uci.get('wireless', id, 'disabled') == '1') ||
		radios.some(w1700kRadioDisabled);

	if (disabled) {
		uci.unset('wireless', id, 'disabled');
		radios.forEach(function(radio) {
			uci.unset('wireless', radio, 'disabled');
		});
	}
	else {
		uci.set('wireless', id, 'disabled', '1');

		const wifi_ifaces = uci.sections('wireless', 'wifi-iface');

		radios.forEach(function(radio) {
			let all_networks_disabled = true;

			wifi_ifaces.forEach(function(wifi_iface) {
				if (wifi_iface['.name'] == id)
					return;
				if (w1700kIfaceConfigUsesRadio(wifi_iface, radio) &&
				    wifi_iface.disabled != '1')
					all_networks_disabled = false;
			});

			if (all_networks_disabled)
				uci.set('wireless', radio, 'disabled', '1');
		});
	}

	return map.save().then(function() {
		ui.changes.apply();
	});
}

function next_free_sid(offset) {
	let sid = 'wifinet' + offset;

	while (uci.get('wireless', sid))
		sid = 'wifinet' + (++offset);

	return sid;
}

function add_dependency_permutations(o, deps) {
	let res = [{}];

	Object.entries(deps).forEach(([key, list]) => {
		if (!Array.isArray(list)) return;

		res = list.flatMap(value => res.map(item => ({ ...item, [key]: value })));
	});

	res.forEach(dep => o.depends(dep));
}

// Default gcmp256/sae_ext_key like the wifi-scripts backend: on only for
// WPA3-Personal Compatibility Mode (sae-compat) on an EHT (Wi-Fi 7) radio, off
// otherwise. htmode is a radio property, not a wifi-iface one, so it cannot be a
// same-section o.defaults dependency. Read the currently selected htmode from the
// radio's frequency/width widget so the default reacts to changes made in the
// same modal, and only fall back to the saved config if that widget is not
// available. On EHT the base updateDefaultValue picks the default from the
// encryption mode (sae-compat -> on, sae/sae-mixed -> off); otherwise force off.
// Both paths go through the base method so the checkbox is updated reactively.
function eht_compat_default(section_id) {
	const dev = uci.get('wireless', section_id, 'device');
	let htmode = dev ? uci.get('wireless', dev, 'htmode') : null;

	const freq = dev ? this.map.lookupOption('_freq', dev) : null;
	if (freq)
		htmode = freq[0].formvalue(dev)?.[0] ?? htmode;

	this.defaults = (htmode && htmode.match(/^EHT/))
		? { '1': [{ encryption: 'sae-compat' }], '0': [{ encryption: 'sae' }, { encryption: 'sae-mixed' }] }
		: { '0': [] };

	return form.Flag.prototype.updateDefaultValue.call(this, section_id);
}

// Define a class CBIWifiFrequencyValue that extends form.Value
var CBIWifiFrequencyValue = form.Value.extend({
	// Declare an RPC method to get the frequency list for a given device
	callFrequencyList: callIwinfoFrequencyList,

	// Load method to fetch WiFi device details and frequency list
	load: function(section_id) {
		this.ucisection = section_id;

		return Promise.all([
			network.getWifiDevice(section_id),
			this.callFrequencyList(section_id)
		]).then(L.bind(function(data) {
			const wifidevs = data[0];
			const freqlist = data[1];
			const lockedBand = w1700kRadioBand(section_id);
			const hasAcs = L.hasSystemFeature('hostapd', 'acs');

			this.channels = {
				'2g': hasAcs ? [ 'auto', 'auto', { available: false } ] : [],
				'5g': hasAcs ? [ 'auto', 'auto', { available: false } ] : [],
				'6g': hasAcs ? [ 'auto', 'auto', { available: false } ] : [],
				'60g': []
			};
			this.apChannels = { '2g': {}, '5g': {}, '6g': {}, '60g': {} };

			freqlist.forEach(freq => {
				if (!freq.band)
					return;

				const band = '%dg'.format(freq.band);
				if (!this.channels[band])
					return;
				if (lockedBand && band != lockedBand)
					return;

				const flags = Array.isArray(freq.flags) ? freq.flags : [];
				const no_ir = !!freq.no_ir || flags.some(flag => String(flag).toLowerCase() == 'no_ir');
				const available = !freq.disabled && !(freq.restricted && no_ir) &&
					w1700kRuntimeChannelAllowed(section_id, freq.channel);

				if (available)
					this.apChannels[band][freq.channel] = true;

				this.channels[band].push(
					freq.channel,
					'%d (%d Mhz)'.format(freq.channel, freq.mhz),
					{
						available: available,
						no_ir: no_ir,
						no_outdoor: freq.no_outdoor
					}
				);
			});

			for (let band in this.apChannels) {
				if (hasAcs && this.channels[band].length >= 3)
					this.channels[band][2].available = Object.keys(this.apChannels[band]).length > 0;
			}

			const hwmodelist = L.toArray(wifidevs ? wifidevs.getHWModes() : null)
				.reduce(function(o, v) { o[v] = true; return o; }, {});

			// Define supported modes
			this.modes = [
				'', 'Legacy', { available: hwmodelist.a || hwmodelist.b || hwmodelist.g },
				'n', 'N', { available: hwmodelist.n },
				'ac', 'AC', { available: L.hasSystemFeature('hostapd', '11ac') && hwmodelist.ac },
				'ax', 'AX', { available: L.hasSystemFeature('hostapd', '11ax') && hwmodelist.ax },
				'be', 'BE', { available: L.hasSystemFeature('hostapd', '11be') && hwmodelist.be }
			];

			// Create a list of HT modes based on device capabilities
			const htmodelist = L.toArray(wifidevs ? wifidevs.getHTModes() : null)
				.reduce(function(o, v) { o[v] = true; return o; }, {});

			this.htmodes = {
				'': [ '', '-', { available: true } ],
				'n': [
					'HT20', '20 MHz', { available: htmodelist.HT20 && w1700kHtmodeAllowed(section_id, 'HT20') },
					'HT40', '40 MHz', { available: htmodelist.HT40 && w1700kHtmodeAllowed(section_id, 'HT40') }
				],
				'ac': [
					'VHT20', '20 MHz', { available: htmodelist.VHT20 && w1700kHtmodeAllowed(section_id, 'VHT20') },
					'VHT40', '40 MHz', { available: htmodelist.VHT40 && w1700kHtmodeAllowed(section_id, 'VHT40') },
					'VHT80', '80 MHz', { available: htmodelist.VHT80 && w1700kHtmodeAllowed(section_id, 'VHT80') },
					'VHT160', '160 MHz', { available: htmodelist.VHT160 && w1700kHtmodeAllowed(section_id, 'VHT160') }
				],
				'ax': [
					'HE20', '20 MHz', { available: htmodelist.HE20 && w1700kHtmodeAllowed(section_id, 'HE20') },
					'HE40', '40 MHz', { available: htmodelist.HE40 && w1700kHtmodeAllowed(section_id, 'HE40') },
					'HE80', '80 MHz', { available: htmodelist.HE80 && w1700kHtmodeAllowed(section_id, 'HE80') },
					'HE160', '160 MHz', { available: htmodelist.HE160 && w1700kHtmodeAllowed(section_id, 'HE160') }
				],
				'be': [
					'EHT20', '20 MHz', { available: htmodelist.EHT20 && w1700kHtmodeAllowed(section_id, 'EHT20') },
					'EHT40', '40 MHz', { available: htmodelist.EHT40 && w1700kHtmodeAllowed(section_id, 'EHT40') },
					'EHT80', '80 MHz', { available: htmodelist.EHT80 && w1700kHtmodeAllowed(section_id, 'EHT80') },
					'EHT160', '160 MHz', { available: htmodelist.EHT160 && w1700kHtmodeAllowed(section_id, 'EHT160') },
					'EHT320', '320 MHz', { available: htmodelist.EHT320 && w1700kHtmodeAllowed(section_id, 'EHT320') }
				]
			};

			// Define available bands for widget selection based on channel availability
			// AX and BE are available on 2/5/6G bands
			const bandAvailable = band => (!lockedBand || lockedBand == band) &&
				Object.keys(this.apChannels[band]).length > 0;

			this.bands = {
				'': [
					'2g', '2.4 GHz', { available: bandAvailable('2g') },
					'5g', '5 GHz', { available: bandAvailable('5g') },
					'60g', '60 GHz', { available: (!lockedBand || lockedBand == '60g') && this.channels['60g'].length > 0 }
				],
				'n': [
					'2g', '2.4 GHz', { available: bandAvailable('2g') },
					'5g', '5 GHz', { available: bandAvailable('5g') }
				],
				'ac': [
					'5g', '5 GHz', { available: bandAvailable('5g') }
				],
				'ax': [
					'2g', '2.4 GHz', { available: bandAvailable('2g') },
					'5g', '5 GHz', { available: bandAvailable('5g') },
					'6g', '6 GHz', { available: bandAvailable('6g') }
				],
				'be': [
					'2g', '2.4 GHz', { available: bandAvailable('2g') },
					'5g', '5 GHz', { available: bandAvailable('5g') },
					'6g', '6 GHz', { available: bandAvailable('6g') }
				]
			};
		}, this));
	},

	// Set values in the select element
	setValues: function(sel, vals) {
		const selectedValue = sel.value;
		let matched = false;

		sel.options.length = 0;

		for (let i = 0; vals && i < vals.length; i += 3)
			if (vals[i+2]?.available) {
				const opt = E('option', { value: vals[i], 'data-index': i }, [ vals[i+1] ]);
				sel.add(opt);
				if (String(vals[i]) == String(selectedValue)) {
					sel.selectedIndex = sel.options.length - 1;
					matched = true;
				}
			}

		if (!matched && Number.isInteger(vals?.selected) && vals.selected < sel.options.length)
			sel.selectedIndex = vals.selected;
		if (sel.selectedIndex < 0 && sel.options.length)
			sel.selectedIndex = 0;

		sel.parentNode.style.display = (sel.options.length <= 1) ? 'none' : '';
		sel.vals = vals;
	},

		channelsForHtmode: function(band, htmode) {
			return w1700kChannelValuesForHtmode(this.ucisection, this.channels[band], htmode, this.apChannels);
		},

		toggleWifiMode: function(elem) {
			this.toggleWifiBand(elem);
			this.toggleWifiHTMode(elem);
			this.toggleWifiChannelList(elem);
		},

		htmodesForChannel: function(mode, channel) {
			const vals = this.htmodes[mode];
			const rv = [];

			for (let i = 0; vals && i < vals.length; i += 3) {
				const meta = Object.assign({}, vals[i+2]);

				meta.available = !!meta.available &&
					w1700kHtmodeAllowed(this.ucisection, vals[i], channel, this.apChannels);

				rv.push(vals[i], vals[i+1], meta);
			}

			return rv;
		},

		toggleWifiHTMode: function(elem) {
			const mode = elem.querySelector('.mode');
			const chan = elem.querySelector('.channel');
			const bwdt = elem.querySelector('.htmode');
			const fallback = w1700kDefaultHtmode(this.ucisection, mode.value);
			const htmodes = this.htmodesForChannel(mode.value, chan.value);

			this.setValues(bwdt, htmodes);

			if (!w1700kHtmodeAllowed(this.ucisection, bwdt.value, chan.value, this.apChannels) || bwdt.selectedIndex < 0)
				bwdt.value = w1700kHtmodeAllowed(this.ucisection, fallback, chan.value, this.apChannels) ? fallback : '';
			if (bwdt.selectedIndex < 0 && bwdt.options.length)
				bwdt.selectedIndex = 0;
	},

	toggleWifiChannelList: function(elem) {
		const band = elem.querySelector('.band');
		const chan = elem.querySelector('.channel');
		const bwdt = elem.querySelector('.htmode');
		const htmode = bwdt ? bwdt.value : null;

		this.setValues(chan, this.channelsForHtmode(band.value, htmode));
	},

	toggleWifiWidth: function(elem) {
		this.toggleWifiChannelList(elem);
		this.toggleWifiHTMode(elem);
		this.map.checkDepends();
		this.checkWifiChannelRestriction(elem);
	},

	toggleWifiBand: function(elem) {
		const mode = elem.querySelector('.mode');
		const band = elem.querySelector('.band');

		this.setValues(band, this.bands[mode.value]);
		this.setValues(elem.querySelector('.channel'), this.channels[band.value]);
		this.toggleWifiHTMode(elem);
		this.toggleWifiChannelList(elem);
		this.toggleWifiHTMode(elem);

		this.map.checkDepends();
	},

	checkWifiChannelRestriction: function(elem) {
		const band = elem.querySelector('.band');
		const chan = elem.querySelector('.channel');
		const restricted_chan = elem.querySelector('.restricted_channel');
		const channels = this.channels[band.value];

		if (!channels || chan.selectedIndex < 0)
			return;

		const index = +chan.options[chan.selectedIndex]?.getAttribute('data-index');
		const channel = Number.isInteger(index) ? channels[index + 2] : null;
		const no_outdoor = channel?.no_outdoor;
		restricted_chan.style.display = no_outdoor ? '': 'none';
	},

	toggleWifiChannel: function(elem) {
		this.toggleWifiHTMode(elem);
		this.map.checkDepends();
		this.checkWifiChannelRestriction(elem);
	},

	setInitialValues: function(section_id, elem) {
		const mode = elem.querySelector('.mode');
		const band = elem.querySelector('.band');
		const chan = elem.querySelector('.channel');
		const bwdt = elem.querySelector('.htmode');
		const htval = uci.get('wireless', section_id, 'htmode');
		const hwval = uci.get('wireless', section_id, 'hwmode');
		const chval = uci.get('wireless', section_id, 'channel');
		const bandval = uci.get('wireless', section_id, 'band');

		this.setValues(mode, this.modes);

		// Determine mode based on htmode value
		if (/EHT20|EHT40|EHT80|EHT160|EHT320/.test(htval))
			mode.value = 'be';		
		else if (/HE20|HE40|HE80|HE160/.test(htval))
			mode.value = 'ax';
		else if (/VHT20|VHT40|VHT80|VHT160/.test(htval))
			mode.value = 'ac';
		else if (/HT20|HT40/.test(htval))
			mode.value = 'n';
		else
			mode.value = '';

		this.toggleWifiMode(elem);

		if (hwval != null) {
			this.useBandOption = false;

			band.value = /a/.test(hwval) ? '5g': '2g';
		}
		else {
			this.useBandOption = true;

			band.value = bandval;
		}

			if (w1700kRadioBand(section_id))
				band.value = w1700kRadioBand(section_id);

			this.toggleWifiBand(elem);

			chan.value = w1700kChannelAllowed(section_id, chval, this.apChannels) ? chval : (chan.options[0] ? chan.options[0].value : 'auto');
			if (chan.selectedIndex < 0 && chan.options.length)
				chan.selectedIndex = 0;

			this.toggleWifiHTMode(elem);

			bwdt.value = w1700kHtmodeAllowed(section_id, htval, chan.value, this.apChannels) ? htval : w1700kDefaultHtmode(section_id, mode.value);
			if (!w1700kHtmodeAllowed(section_id, bwdt.value, chan.value, this.apChannels) || bwdt.selectedIndex < 0 && bwdt.options.length)
				bwdt.selectedIndex = 0;

			this.toggleWifiChannelList(elem);
			this.toggleWifiHTMode(elem);
			this.checkWifiChannelRestriction(elem);

			return elem;
	},

	renderWidget: function(section_id, option_index, cfgvalue) {
		const elem = E('div');

		dom.content(elem, [
			E('div', { 'class' : 'restricted_channel', 'style': 'display:none'}, [
				E('div', {'class': 'cbi-button alert-message warning disabled'}, _('Indoor Only Channel Selected'))
			]),
			E('label', { 'style': 'float:left; margin-right:3px' }, [
				_('Mode'), E('br'),
				E('select', {
					'class': 'mode',
					'style': 'width:auto',
					'change': L.bind(this.toggleWifiMode, this, elem),
					'disabled': (this.disabled != null) ? this.disabled : this.map.readonly
				})
			]),
			E('label', { 'style': 'float:left; margin-right:3px' }, [
				_('Band'), E('br'),
				E('select', {
					'class': 'band',
					'style': 'width:auto',
					'change': L.bind(this.toggleWifiBand, this, elem),
					'disabled': (this.disabled != null) ? this.disabled : this.map.readonly
				})
			]),
			E('label', { 'style': 'float:left; margin-right:3px' }, [
				_('Channel'), E('br'),
				E('select', {
					'class': 'channel',
					'style': 'width:auto',
					'change': L.bind(this.toggleWifiChannel, this, elem),
					'disabled': (this.disabled != null) ? this.disabled : this.map.readonly
				})
			]),
			E('label', { 'style': 'float:left; margin-right:3px' }, [
				_('Width'), E('br'),
				E('select', {
					'class': 'htmode',
					'style': 'width:auto',
					'change': L.bind(this.toggleWifiWidth, this, elem),
					'disabled': (this.disabled != null) ? this.disabled : this.map.readonly
				})
			]),
			E('br', { 'style': 'clear:left' })
		]);

		return this.setInitialValues(section_id, elem);
	},

	cfgvalue: function(section_id) {
		return [
		    uci.get('wireless', section_id, 'htmode'),
		    uci.get('wireless', section_id, 'hwmode') || uci.get('wireless', section_id, 'band'),
		    uci.get('wireless', section_id, 'channel')
		];
	},

	formvalue: function(section_id) {
		const node = this.map.findElement('data-field', this.cbid(section_id));

		return [
		    node.querySelector('.htmode').value,
		    node.querySelector('.band').value,
		    node.querySelector('.channel').value
		];
	},

	validate: function(section_id, value) {
		const band = w1700kRadioBand(section_id);
		const conflict = w1700kRadioIndexConflict(section_id);
		value = L.toArray(value);

		if (w1700kRadioMapActive() && w1700kExplicitRadioIndex(section_id) == null)
			return _('%s has no explicit physical radio index. Set option radio to 0, 1, or 2 before applying this configuration.').format(section_id);

		if (conflict)
			return _('Physical radio index %s is assigned to multiple sections: %s.').format(
				w1700kRadioIndex(section_id), conflict.join(', '));

		if (band && value[1] != band)
			return _('%s is physical %s; use the matching radio for other bands.').format(section_id, band);

		if (!w1700kHtmodeAllowed(section_id, value[0], value[2], this.apChannels))
			return _('%s is not a valid width on channel %s for %s.').format(value[0], value[2], band || section_id);

		if (!w1700kChannelAllowed(section_id, value[2], this.apChannels))
			return _('Channel %s is outside the physical range for %s.').format(value[2], band || section_id);

		return true;
	},

	write: function(section_id, value) {
		const band = w1700kRadioBand(section_id);

		if (band)
			value[1] = band;

		uci.set('wireless', section_id, 'htmode', value[0] || null);

		this.useBandOption ?
			uci.set('wireless', section_id, 'band', value[1]) : 
			uci.set('wireless', section_id, 'hwmode', (value[1] == '2g') ? '11g' : '11a');

		uci.set('wireless', section_id, 'channel', value[2]);
	}
});

var CBIWifiTxPowerValue = form.ListValue.extend({
	callTxPowerList: rpc.declare({
		object: 'iwinfo',
		method: 'txpowerlist',
		params: [ 'device' ],
		expect: { results: [] }
	}),

	load: function(section_id) {
		return this.callTxPowerList(section_id).then(L.bind(function(pwrlist) {
			this.powerval = this.wifiNetwork ? this.wifiNetwork.getTXPower() : null;
			this.poweroff = this.wifiNetwork ? this.wifiNetwork.getTXPowerOffset() : null;

			this.value('', _('driver default'));

			for (let p of pwrlist)
				this.value(p.dbm, `${p.dbm} dBm (${p.mw} mW)`);

			return form.ListValue.prototype.load.apply(this, [section_id]);
		}, this));
	},

	renderWidget: function(section_id, option_index, cfgvalue) {
		const widget = form.ListValue.prototype.renderWidget.apply(this, [section_id, option_index, cfgvalue]);

		widget.firstElementChild.style.width = 'auto';

		dom.append(widget, E('span', [
			' - ', _('Current power'), ': ',
			E('span', [ this.powerval != null ? `${this.powerval} dBm` : E('em', _('unknown')) ]),
			this.poweroff ? ` + ${this.poweroff} dB offset = ${this.powerval != null ? this.powerval + this.poweroff : '?'} dBm` : ''
		]));

		return widget;
	}
});

var CBIWifiCountryValue = form.Value.extend({
	callCountryList: rpc.declare({
		object: 'iwinfo',
		method: 'countrylist',
		params: [ 'device' ],
		expect: { results: [] }
	}),

	load: function(section_id) {
		return this.callCountryList(section_id).then(L.bind(function(countrylist) {
			if (Array.isArray(countrylist) && countrylist.length > 0) {
				if (!w1700kRadioInfo(section_id))
					this.value('', _('driver default'));

				for (let c of countrylist) {
					if (w1700kRadioInfo(section_id) && c.iso3166 == '00')
						continue;
					this.value(c.iso3166, `${c.iso3166} - ${c.country}`);
				}
			}

			return form.Value.prototype.load.apply(this, [section_id]);
		}, this));
	},

	cfgvalue: function(section_id) {
		const value = form.Value.prototype.cfgvalue.apply(this, [section_id]);
		return w1700kRadioInfo(section_id) ? w1700kNormalizeCountry(value) : value;
	},

	validate: function(section_id, formvalue) {
		if (w1700kRadioInfo(section_id))
			formvalue = w1700kNormalizeCountry(formvalue);

		if (formvalue != null && formvalue != '' && !/^[A-Z0-9][A-Z0-9]$/.test(formvalue))
			return _('Use ISO/IEC 3166 alpha2 country codes.');

		return true;
	},

	write: function(section_id, formvalue) {
		if (w1700kRadioInfo(section_id)) {
			const country = w1700kNormalizeCountry(formvalue);

			for (let dev of w1700kMappedRadioNames())
				uci.set('wireless', dev, 'country', country);
			return;
		}

		return form.Value.prototype.write.apply(this, [section_id, formvalue]);
	},

	remove: function(section_id) {
		if (w1700kRadioInfo(section_id)) {
			for (let dev of w1700kMappedRadioNames())
				uci.set('wireless', dev, 'country', 'US');
			return;
		}

		return form.Value.prototype.remove.apply(this, [section_id]);
	},

	renderWidget: function(section_id, option_index, cfgvalue) {
		const typeClass = (this.keylist && this.keylist.length) ? form.ListValue : form.Value;
		return typeClass.prototype.renderWidget.apply(this, [section_id, option_index, cfgvalue]);
	}
});

return view.extend({
	poll_status: function(map, data) {
		const rows = map.querySelectorAll('.cbi-section-table-row[data-sid]');

		rows.forEach(row => {
			const section_id = row.getAttribute('data-sid');
			const radioDev = data[1].filter(function(d) { return d.getName() == section_id; })[0];
			const radioNet = data[2].filter(function(n) { return n.getName() == section_id; })[0];
			if (!row)
				return;
			const badge = row.querySelector('[data-name="_badge"] > div');
			const stat = row.querySelector('[data-name="_stat"]');
			const btns = row.querySelectorAll('.cbi-section-actions button');
			if (!badge || !stat || btns.length < 3) return;
			const busy = btns[0].classList.contains('spinning') || btns[1].classList.contains('spinning') || btns[2].classList.contains('spinning');

				if (radioDev) {
					dom.content(badge, render_radio_badge(radioDev));
					dom.content(stat, render_radio_status(radioDev, data[2].filter(function(n) { return w1700kWifiUsesRadio(n, radioDev.getName()); })));
				}
			else {
				dom.content(badge, render_network_badge(radioNet));
				dom.content(stat, render_network_status(radioNet));
			}

			if (stat.hasAttribute('restart'))
				dom.content(stat, E('em', _('Device is restarting…')));

			btns[0].disabled = isReadonlyView || busy;
			btns[1].disabled = (isReadonlyView && radioDev) || busy;
			btns[2].disabled = isReadonlyView || busy;
		});

		const table = document.querySelector('#wifi_assoclist_table');
		const hosts = data[0];
		let trows = [];
		const radios = data[3];
		const zones = data[4];

		radios.forEach(zone => {
			const bss = zone;
			const name = hosts.getHostnameByMACAddr(bss.mac);
			const ipv4 = hosts.getIPAddrByMACAddr(bss.mac);
			const ipv6 = hosts.getIP6AddrByMACAddr(bss.mac);

			let hint;

			if (name && ipv4 && ipv6)
				hint = `${'%h'.format(name)} <span class="hide-xs">(${ipv4}, ${ipv6})</span>`;
			else if (name && (ipv4 ?? ipv6))
				hint = `${'%h'.format(name)} <span class="hide-xs">(${ipv4 || ipv6})</span>`;
			else
				hint = name || ipv4 || ipv6 || '?';

			let row = [
				E('span', {
					'class': 'ifacebadge',
					'data-ifname': bss.network.getIfname(),
					'data-ssid': bss.network.getSSID()
				}, [
					E('img', {
						'src': L.resource('icons/wifi%s.svg').format(bss.network.isUp() ? '' : '_disabled'),
						'title': bss.radio ? bss.radio.getI18n() : w1700kWifiNetDeviceNames(bss.network).join(', ')
					}),
					E('span', [
						` ${bss.network.getShortName()} `,
						E('small', `(${bss.network.getIfname()})`)
					])
				]),
				bss.mac,
				hint,
				render_signal_badge(Math.min((bss.signal + 110) / 70 * 100, 100), bss.signal, bss.noise),
				E('span', {}, [
					E('span', format_wifirate(bss.rx)),
					E('br'),
					E('span', format_wifirate(bss.tx))
				])
			];

			if (bss.vlan) {
				const desc = bss.vlan.getI18n();
				const vlan_network = bss.vlan.getNetwork();
				let vlan_zone;

				if (vlan_network && zones)
					for (let zone of zones)
						if (zone.getNetworks().includes(vlan_network))
							vlan_zone = zone;

				row[0].insertBefore(
					E('div', {
						'class' : 'zonebadge',
						'title' : desc,
						'style' : firewall.getZoneColorStyle(vlan_zone)
					}, [ desc ]), row[0].firstChild);
			}

			if (bss.network.isClientDisconnectSupported()) {
				if (table.firstElementChild.childNodes.length < 6)
					table.firstElementChild.appendChild(E('th', { 'class': 'th cbi-section-actions'}));

				row.push(E('button', {
					'class': 'cbi-button cbi-button-remove',
					'click': L.bind(function(net, mac, ev) {
						dom.parent(ev.currentTarget, '.tr').style.opacity = 0.5;
						ev.currentTarget.classList.add('spinning');
						ev.currentTarget.disabled = true;
						ev.currentTarget.blur();

						net.disconnectClient(mac, true, 5, 60000);
					}, this, bss.network, bss.mac),
					'disabled': isReadonlyView || null
				}, [ _('Disconnect') ]));
			}
			else {
				row.push('-');
			}

			trows.push(row);
		});

		cbi_update_table(table, trows, E('em', _('No information available')));

		const status = document.querySelector('.cbi-modal [data-name="_wifistat_modal"] .ifacebadge.large');

		if (status)
			render_modal_status(status, data[2].filter(function(n) { return n.getName() == status.getAttribute('data-network'); })[0]);

		return network.flushCache();
	},

	load: function() {
		return Promise.all([
			uci.changes(),
			uci.load('wireless'),
			uci.load('system'),
			firewall.getZones(),
		]);
	},

	checkAnonymousSections: function() {
		return uci.sections('wireless', 'wifi-iface').some(iface => iface['.anonymous']);
	},

	callUciRename: rpc.declare({
		object: 'uci',
		method: 'rename',
		params: [ 'config', 'section', 'name' ]
	}),

	render: function(data) {
		if (this.checkAnonymousSections())
			return this.renderMigration();
		else
			return this.renderOverview(data[3]);
	},

	handleMigration: function(ev) {
		const wifiIfaces = uci.sections('wireless', 'wifi-iface');
		let id_offset = 0;
		const tasks = [];

		wifiIfaces.forEach((iface) => {
			if (iface['.anonymous']) {
				const new_name = next_free_sid(id_offset);
				tasks.push(this.callUciRename('wireless', iface['.name'], new_name));
				id_offset = parseInt(new_name.substring(7), 10) + 1;
		    }
		});

		return Promise.all(tasks)
			.then(L.bind(ui.changes.init, ui.changes))
			.then(L.bind(ui.changes.apply, ui.changes));
	},

	renderMigration: function() {
		ui.showModal(_('Wireless configuration migration'), [
			E('p', _('The existing wireless configuration needs to be changed for LuCI to function properly.')),
			E('p', _('Upon pressing "Continue", anonymous "wifi-iface" sections will be assigned with a name in the form <em>wifinet#</em> and the network will be restarted to apply the updated configuration.')),
			E('div', { 'class': 'right' },
				E('button', {
					'class': 'btn cbi-button-action important',
					'click': ui.createHandlerFn(this, 'handleMigration')
				}, _('Continue')))
		]);
	},

	renderOverview: function(zones) {
		let m, s, o;

		m = new form.Map('wireless');
		m.chain('network');
		m.chain('firewall');

		s = m.section(form.GridSection, 'wifi-device', _('Wireless Overview'));
		s.anonymous = true;
		s.addremove = false;

		s.load = function() {
			return network.getWifiDevices().then(L.bind(function(radios) {
				this.radios = radios.sort(function(a, b) {
					return a.getName().localeCompare(b.getName());
				});

				const tasks = [];

				radios.forEach(radio => {
					tasks.push(radio.getWifiNetworks());
				});

				return Promise.all(tasks);
			}, this)).then(L.bind(function(data) {
				const wifis = [];

				data.forEach(d => {
					wifis.push.apply(wifis, d);
				});
				this.wifis = w1700kUniqueWifiNetworks(wifis);
			}, this));
		};

			s.cfgsections = function() {
				const rv = [];
				const seenWifi = {};

				this.radios.forEach(radio => {
					rv.push(radio.getName());

					this.wifis.forEach(wifi => {
						const primary = w1700kWifiPrimaryRadio(wifi);
						const belongs = primary ? primary == radio.getName() : w1700kWifiUsesRadio(wifi, radio.getName());

						if (!seenWifi[wifi.getName()] && belongs) {
							seenWifi[wifi.getName()] = true;
							rv.push(wifi.getName());
						}
					});
				});

				return rv;
		};

		s.modaltitle = function(section_id) {
			const radioNet = this.wifis.filter(function(w) { return w.getName() == section_id; })[0];
			return radioNet ? radioNet.getI18n() : _('Edit wireless network');
		};

		s.lookupRadioOrNetwork = function(section_id) {
			const radioDev = this.radios.filter(function(r) { return r.getName() == section_id; })[0];
			if (radioDev)
				return radioDev;

			const radioNet = this.wifis.filter(function(w) { return w.getName() == section_id; })[0];
			if (radioNet)
				return radioNet;

			return null;
		};

			s.renderRowActions = function(section_id) {
			const inst = this.lookupRadioOrNetwork(section_id);
			let btns;

			if (inst.getWifiNetworks) {
					const mloOwner = w1700kRadioMapActive() ? w1700kMloRadioOwner(null, inst.getName()) : null;

				btns = [
					E('button', {
						'class': 'cbi-button cbi-button-neutral',
						'title': _('Restart radio interface'),
						'click': ui.createHandlerFn(this, radio_restart, section_id)
					}, _('Restart')),
					E('button', {
						'class': 'cbi-button cbi-button-action important',
						'title': _('Find and join network'),
						'click': ui.createHandlerFn(this, 'handleScan', inst)
					}, _('Scan'))
				];

					if (mloOwner || w1700kMloAvailable())
					btns.push(E('button', {
						'class': 'cbi-button cbi-button-action',
						'title': mloOwner ? _('Edit MLO network') : _('Create MLO network'),
						'click': mloOwner
							? ui.createHandlerFn(this, 'renderMoreOptionsModal', mloOwner['.name'])
							: ui.createHandlerFn(this, 'handleAddMlo', inst)
					}, mloOwner ? _('Edit MLO') : _('Add MLO')));

				btns.push(
					E('button', {
						'class': 'cbi-button cbi-button-add',
						'title': _('Provide new network'),
						'click': ui.createHandlerFn(this, 'handleAdd', inst)
					}, _('Add'))
				);
			}
			else {
				const isDisabled = (inst.get('disabled') == '1' ||
					uci.get('wireless', inst.getWifiDeviceName(), 'disabled') == '1');

				btns = [
					E('button', {
						'class': 'cbi-button cbi-button-neutral enable-disable',
						'title': isDisabled ? _('Enable this network') : _('Disable this network'),
						'click': ui.createHandlerFn(this, network_updown, section_id, this.map)
					}, isDisabled ? _('Enable') : _('Disable')),
					E('button', {
						'class': 'cbi-button cbi-button-action important',
						'title': _('Edit this network'),
						'click': ui.createHandlerFn(this, 'renderMoreOptionsModal', section_id)
					}, _('Edit')),
					E('button', {
						'class': 'cbi-button cbi-button-negative remove',
						'title': _('Delete this network'),
						'click': ui.createHandlerFn(this, 'handleRemove', section_id)
					}, _('Remove'))
				];
			}

			return E('td', { 'class': 'td middle cbi-section-actions' }, E('div', btns));
		};

		s.addModalOptions = function(s) {
			return network.getWifiNetwork(s.section).then(function(radioNet) {
				const hwtype = uci.get('wireless', radioNet.getWifiDeviceName(), 'type');
				const have_mesh = L.hasSystemFeature('hostapd', 'mesh') || L.hasSystemFeature('wpasupplicant', 'mesh');
				let o, ss, frequencyOption, ifaceSection;
				const ifaceSectionId = s.section;

				o = s.option(form.SectionValue, '_device', form.NamedSection, radioNet.getWifiDeviceName(), 'wifi-device', _('Device Configuration'));
				o.modalonly = true;

				ss = o.subsection;
				ss.tab('general', _('General Setup'));
				ss.tab('advanced', _('Advanced Settings'));

				const isDisabled = (radioNet.get('disabled') == '1' ||
					uci.get('wireless', radioNet.getWifiDeviceName(), 'disabled') == 1);

				o = ss.taboption('general', form.DummyValue, '_wifistat_modal', _('Status'));
				o.cfgvalue = L.bind(function(radioNet) {
					return render_modal_status(null, radioNet);
				}, this, radioNet);
				o.write = function() {};

				o = ss.taboption('general', form.Button, '_toggle', isDisabled ? _('Wireless network is disabled') : _('Wireless network is enabled'));
				o.inputstyle = isDisabled ? 'apply' : 'reset';
				o.inputtitle = isDisabled ? _('Enable') : _('Disable');
				o.onclick = ui.createHandlerFn(s, network_updown, s.section, s.map);

				o = ss.taboption('general', CBIWifiFrequencyValue, '_freq', '<br />' + _('Operating frequency'), _('Some channels may be restricted to Indoor Only use by your Regulatory Domain. Make sure to follow this advice if a channel is reported as such.'));
				o.ucisection = s.section;
				frequencyOption = o;
				const frequencyCheckDepends = o.checkDepends;
				o.checkDepends = function(section_id) {
					return frequencyCheckDepends.call(this, section_id) &&
						w1700kFrequencyWidgetActive(ifaceSection, ifaceSectionId);
				};

				if (hwtype == 'mac80211') {
					o = ss.taboption('general', form.Flag, 'legacy_rates', _('Allow legacy 802.11b rates'), _('Legacy or badly behaving devices may require legacy 802.11b rates to interoperate. Airtime efficiency may be significantly reduced where these are used. It is recommended to not allow 802.11b rates where possible.'));
					o.depends({'_freq': '2g', '!contains': true});

					if (!w1700kRadioMapActive()) {
						o = ss.taboption('general', CBIWifiTxPowerValue, 'txpower', _('Maximum transmit power'), _('Specifies the maximum transmit power the wireless radio may use. Depending on regulatory requirements and wireless usage, the actual transmit power may be reduced by the driver.'));
						o.wifiNetwork = radioNet;
					}

					o = ss.taboption('general', CBIWifiCountryValue, 'country', _('Country Code'));
					o.wifiNetwork = radioNet;

					o = ss.taboption('advanced', form.ListValue, 'cell_density', _('Coverage cell density'), _('Configures data rates based on the coverage cell density. Normal configures basic rates to 6, 12, 24 Mbps if legacy 802.11b rates are not used else to 5.5, 11 Mbps. High configures basic rates to 12, 24 Mbps if legacy 802.11b rates are not used else to the 11 Mbps rate. Very High configures 24 Mbps as the basic rate. Supported rates lower than the minimum basic rate are not offered.'));
					o.value('0', _('Disabled'));
					o.value('1', _('Normal'));
					o.value('2', _('High'));
					o.value('3', _('Very High'));

					if (!w1700kRadioMapActive()) {
						o = ss.taboption('advanced', form.Value, 'distance', _('Distance Optimization'), _('Distance to farthest network member in meters. Set only for distances above one kilometer; otherwise it is harmful.'));
						o.datatype = 'or(range(0,114750),"auto")';
						o.placeholder = 'auto';
					}

					o = ss.taboption('advanced', form.Value, 'frag', _('Fragmentation Threshold'));
					o.datatype = 'min(256)';
					o.placeholder = _('off');

					o = ss.taboption('advanced', form.Value, 'rts', _('RTS/CTS Threshold'));
					o.datatype = 'uinteger';
					o.placeholder = _('off');

					o = ss.taboption('advanced', form.Flag, 'noscan', _('Force 40MHz mode'), _('Always use 40MHz channels even if the secondary channel overlaps. Using this option does not comply with IEEE 802.11n-2009!'));
					o.rmempty = true;

					o = ss.taboption('advanced', form.Value, 'beacon_int', _('Beacon Interval'));
					o.datatype = 'range(15,65535)';
					o.placeholder = 100;
					o.rmempty = true;

					o = ss.taboption('advanced', form.Flag, 'rxldpc', _('Rx LDPC'), _('Low-Density Parity-Check'));
					o.default = '1';

					o = ss.taboption('advanced', form.Flag, 'ldpc', _('Tx LDPC'));
					o.depends({'rxldpc': '1'});
					o.default = '1';

					o = ss.taboption('advanced', form.DummyValue, '_w1700k_eht_capabilities', _('Wi-Fi 7 capabilities'));
					o.load = function(section_id) {
						return w1700kLoadWifiCapabilities().then(L.bind(function(caps) {
							this.w1700kCaps = caps || {};
							return form.DummyValue.prototype.load.apply(this, [section_id]);
						}, this));
					};
					o.cfgvalue = function() {
						const caps = this.w1700kCaps || {};

						return L.itemlist(E('div'), [
							_('4096-QAM'), caps.eht4096qam ? _('advertised') : _('not advertised'),
							_('EHT non-OFDMA UL MU-MIMO'), caps.ehtNonOfdmaUlMuMimo ? _('advertised') : _('not advertised'),
							_('EHT Multi-RU/OFDMA RU'), caps.ehtMultiRu ? _('advertised') : _('not advertised'),
							_('EHT puncturing'), caps.puncturing ? _('advertised') : _('not advertised'),
							_('Beamforming'), caps.beamforming ? _('advertised') : _('not advertised'),
							_('MU-MIMO'), caps.muMimo ? _('advertised') : _('not advertised')
						], ' | ');
					};
					o.write = function() {};

					if (w1700kRadioInfo(s.section)) {
						o = ss.taboption('advanced', form.Value, 'punct_bitmap', _('EHT puncturing bitmap'),
							_('Disabled 20 MHz subchannel bitmap, for example 0x0002.'));
						o.placeholder = '0';
						o.rmempty = true;
						o.load = function(section_id) {
							return w1700kLoadWifiCapabilities().then(L.bind(function(caps) {
								this.w1700kCaps = caps || {};
								return form.Value.prototype.load.apply(this, [section_id]);
							}, this));
						};
						o.validate = function(section_id, value) {
							const state = w1700kCurrentPuncturingState(
								this.section, section_id, ifaceSection, ifaceSectionId,
								frequencyOption, { bitmap: value });

							const bitmap = w1700kParsePunctBitmap(value);
							const threshold = +state.threshold || 0;
							let rv;

							if (bitmap == 0)
								return true;

							if (bitmap == null)
								return _('Use a decimal value or a hexadecimal value such as 0x0002.');

							if (!(this.w1700kCaps || {}).puncturing)
								return _('EHT puncturing is not advertised by the current mt7996 driver.');

							if (threshold > 0)
								return _('Use either a manual puncturing bitmap or ACS puncturing threshold, not both.');

							rv = w1700kValidatePunctBitmap(
								section_id,
								state.htmode,
								state.channel,
								value);

							return rv;
						};

						o = ss.taboption('advanced', form.Value, 'punct_acs_threshold', _('EHT ACS puncturing threshold'),
							_('Automatic puncturing threshold percentage used with auto channel selection.'));
						o.placeholder = '0';
						o.datatype = 'range(0,100)';
						o.rmempty = true;
						o.load = function(section_id) {
							return w1700kLoadWifiCapabilities().then(L.bind(function(caps) {
								this.w1700kCaps = caps || {};
								return form.Value.prototype.load.apply(this, [section_id]);
							}, this));
						};
						o.validate = function(section_id, value) {
							const threshold = String(value || '').trim();
							const state = w1700kCurrentPuncturingState(
								this.section, section_id, ifaceSection, ifaceSectionId,
								frequencyOption, { threshold: value });
							const bitmap = w1700kParsePunctBitmap(state.bitmap);

							if (threshold == '' || threshold == '0')
								return true;

							if (!/^[0-9]+$/.test(threshold) || +threshold > 100)
								return _('Use a value between 0 and 100.');

							if (!(this.w1700kCaps || {}).puncturing)
								return _('EHT puncturing is not advertised by the current mt7996 driver.');

							if (!w1700kPunctWidthAllowed(section_id, state.htmode))
								return _('EHT ACS puncturing requires 5GHz or 6GHz EHT80 or wider.');

							if (state.channel != 'auto')
								return _('EHT ACS puncturing requires channel auto.');

							if (bitmap > 0)
								return _('Use either a manual puncturing bitmap or ACS puncturing threshold, not both.');

							return true;
						};
					}
				}


				o = s.option(form.SectionValue, '_device', form.NamedSection, radioNet.getName(), 'wifi-iface', _('Interface Configuration'));
				o.modalonly = true;

				ss = o.subsection;
				ifaceSection = ss;
				ss.tab('general', _('General Setup'));
				ss.tab('encryption', _('Wireless Security'));
				ss.tab('macfilter', _('MAC-Filter'));
				ss.tab('advanced', _('Advanced Settings'));
				ss.tab('roaming', _('WLAN Roaming'), _('Settings for assisting wireless clients in roaming between multiple APs: 802.11r, 802.11k and 802.11v'));
				if (w1700kMloAvailable())
					ss.tab('mlo', _('MLO'));
				const mloTab = w1700kMloAvailable() ? 'mlo' : 'advanced';

				o = ss.taboption('general', form.ListValue, 'mode', _('Mode') , !have_mesh ? '<a id="installmesh" href="%s" target="_blank" rel="noreferrer">%s</a>'
						.format(L.url('admin/system/package-manager') + '?query=wpad-mesh', _('802.11s? Install mesh wpad') ) : '');
				o.value('ap', _('Access Point'));
				o.value('sta', _('Client'));
				o.value('adhoc', _('Ad-Hoc'));

				o = ss.taboption('general', form.Value, 'mesh_id', _('Mesh Id'));
				o.depends('mode', 'mesh');

				o = ss.taboption('advanced', form.Flag, 'mesh_fwding', _('Forward mesh peer traffic'));
				o.rmempty = false;
				o.default = '1';
				o.depends('mode', 'mesh');

				o = ss.taboption('advanced', form.Value, 'mesh_rssi_threshold', _('RSSI threshold for joining mesh'), _('0 = not using RSSI threshold, 1 = do not change driver default') + ' ' +
					_('Units: dBm. Where -255 is weakest, and -10 is strong.'));
				o.rmempty = false;
				o.default = '0';
				o.datatype = 'range(-255,1)';
				o.depends('mode', 'mesh');

				o = ss.taboption('general', form.Value, 'ssid', _('<abbr title="Extended Service Set Identifier">ESSID</abbr>'));
				o.datatype = 'maxlength(32)';
				o.depends('mode', 'ap');
				o.depends('mode', 'sta');
				o.depends('mode', 'adhoc');
				o.depends('mode', 'ahdemo');
				o.depends('mode', 'monitor');
				o.depends('mode', 'ap-wds');
				o.depends('mode', 'sta-wds');
				o.depends('mode', 'wds');

				o = ss.taboption('general', form.Value, 'bssid', _('<abbr title="Basic Service Set Identifier">BSSID</abbr>'));
				o.datatype = 'macaddr';

				o = ss.taboption('general', widgets.NetworkSelect, 'network', _('Network'), _('Choose the network(s) you want to attach to this wireless interface or fill out the <em>custom</em> field to define a new network.'));
				o.rmempty = true;
				o.multiple = true;
				o.novirtual = true;
				o.write = function(section_id, value) {
					return network.getDevice(section_id).then(L.bind(function(dev) {
						const old_networks = dev.getNetworks().reduce(function(o, v) { o[v.getName()] = v; return o; }, {});
						const new_networks = {};
						const values = L.toArray(value);
						const tasks = [];

						values.forEach(value => {

							new_networks[value] = true;

							if (old_networks[value])
								return;

							tasks.push(network.getNetwork(value).then(L.bind(function(name, net) {
								return net || network.addNetwork(name, { proto: 'none' });
							}, this, value)).then(L.bind(function(dev, net) {
								if (net) {
									if (!net.isEmpty()) {
										let target_dev = net.getDevice();

										/* Resolve parent interface of vlan */
										while (target_dev && target_dev.getType() == 'vlan')
											target_dev = target_dev.getParent();

										if (!target_dev || target_dev.getType() != 'bridge')
											net.set('type', 'bridge');
									}

									net.addDevice(dev);
								}
							}, this, dev)));
						});

						for (let name in old_networks)
							if (!new_networks[name])
								tasks.push(network.getNetwork(name).then(L.bind(function(dev, net) {
									if (net)
										net.deleteDevice(dev);
								}, this, dev)));

						return Promise.all(tasks);
					}, this));
				};

				let encr;
				if (hwtype == 'mac80211') {
					const mode = ss.children.find(obj => obj.option === 'mode');
					const bssid = ss.children.find(obj => obj.option === 'bssid');

					if (have_mesh) mode.value('mesh', '802.11s');
					mode.value('ahdemo', _('Pseudo Ad-Hoc (ahdemo)'));
					mode.value('monitor', _('Monitor'));

					bssid.depends('mode', 'adhoc');
					bssid.depends('mode', 'sta');
					bssid.depends('mode', 'sta-wds');

					o = ss.taboption('macfilter', form.ListValue, 'macfilter', _('MAC Address Filter'));
					o.depends('mode', 'ap');
					o.depends('mode', 'ap-wds');
					o.value('', _('disable'));
					o.value('allow', _('Allow listed only'));
					o.value('deny', _('Allow all except listed'));

					o = ss.taboption('macfilter', form.DynamicList, 'maclist', _('MAC-List'));
					o.datatype = 'macaddr';
					o.retain = true;
					o.depends('macfilter', 'allow');
					o.depends('macfilter', 'deny');
					o.load = function(section_id) {
						return network.getHostHints().then(L.bind(function(hints) {
							hints.getMACHints().map(L.bind(function(hint) {
								this.value(hint[0], hint[1] ? '%s (%s)'.format(hint[0], hint[1]) : hint[0]);
							}, this));

							return form.DynamicList.prototype.load.apply(this, [section_id]);
						}, this));
					};

					mode.value('ap-wds', '%s (%s)'.format(_('Access Point'), _('WDS')));
					mode.value('sta-wds', '%s (%s)'.format(_('Client'), _('WDS')));

					mode.write = function(section_id, value) {
						switch (value) {
						case 'ap-wds':
							uci.set('wireless', section_id, 'mode', 'ap');
							uci.set('wireless', section_id, 'wds', '1');
							break;

						case 'sta-wds':
							uci.set('wireless', section_id, 'mode', 'sta');
							uci.set('wireless', section_id, 'wds', '1');
							break;

						default:
							uci.set('wireless', section_id, 'mode', value);
							uci.unset('wireless', section_id, 'wds');
							break;
						}
					};

					mode.cfgvalue = function(section_id) {
						const mode = uci.get('wireless', section_id, 'mode');
						const wds = uci.get('wireless', section_id, 'wds');

						if (mode == 'ap' && wds)
							return 'ap-wds';
						else if (mode == 'sta' && wds)
							return 'sta-wds';

						return mode;
					};

					o = ss.taboption('general', form.Flag, 'hidden', _('Hide <abbr title="Extended Service Set Identifier">ESSID</abbr>'), _('Where the ESSID is hidden, clients may fail to roam and airtime efficiency may be significantly reduced.'));
					o.depends('mode', 'ap');
					o.depends('mode', 'ap-wds');

					o = ss.taboption('general', form.Flag, 'wmm', _('WMM Mode'), _('Where Wi-Fi Multimedia (WMM) Mode QoS is disabled, clients may be limited to 802.11a/802.11g rates.'));
					o.depends('mode', 'ap');
					o.depends('mode', 'ap-wds');
					o.default = o.enabled;

				o = ss.taboption(mloTab, form.Flag, 'mlo', _('Multi-Link Operation'));
				o.depends('mode', 'ap');
				o.rmempty = true;
				o.validate = function(section_id, value) {
					const owner = value == '1' ? w1700kMloRadioOwner(section_id, radioNet.getWifiDeviceName()) : null;

					return owner
						? _('%s is already linked to MLO network %s. Edit that network instead.').format(
							w1700kRadioLabel(radioNet.getWifiDeviceName()), w1700kMloOwnerLabel(owner))
						: true;
				};
					o.onchange = function(ev, section_id, value) {
						if (value == '1') {
							uci.set('wireless', section_id, 'mlo', '1');
							w1700kEnsure6gMloApDefaults(this.section, section_id);
						}
						else {
							uci.unset('wireless', section_id, 'mlo');
						}

						this.map.checkDepends();
					};
					o.write = function(section_id, value) {
						if (value == '1') {
							uci.set('wireless', section_id, 'mlo', '1');
							w1700kEnsure6gMloApDefaults(this.section, section_id);
						}
						else {
							uci.unset('wireless', section_id, 'mlo');
						}
					};

				o = ss.taboption(mloTab, form.DummyValue, '_mlo_status', _('MLO capability'));
				o.depends({ mode: 'ap', mlo: '1' });
					o.cfgvalue = function() {
						return L.hasSystemFeature('hostapd', '11be') ? _('Core 802.11be MLO available') : _('802.11be MLO support not detected');
					};
					o.write = function() {};

				o = ss.taboption(mloTab, form.MultiValue, '_mlo_devices', _('MLO link radios'));
					o.depends({ mode: 'ap', mlo: '1' });
					o.placeholder = _('Select radios');
					o.rmempty = true;
					o.onchange = function(ev, section_id, value) {
						const devices = w1700kNormalizeDeviceList(value);
						const elem = this.getUIElement(section_id);

						if (elem && elem.setValue)
							elem.setValue(devices);
						w1700kRefreshMloChoices(this, section_id);

						w1700kEnsure6gMloApDefaults(this.section, section_id, this.apChannelsByRadio);
						this.map.checkDepends();
					};

				uci.sections('wireless', 'wifi-device').forEach(function(dev) {
					const name = dev['.name'];
					const owner = w1700kMloRadioOwner(s.section, name);
					const selected = w1700kDeviceNames(uci.get('wireless', s.section, 'device')).indexOf(name) >= 0;
					const choice = w1700kMloChoiceState(dev, selected);
					let label = w1700kRadioLabel(name);

					if (w1700kRadioMapActive() && !w1700kRadioInfo(name))
						return;

					if (!choice.visible)
						return;
					if (owner && !selected)
						return;
					if (choice.disabled)
						label += ' / ' + _('disabled - remove to save');
					if (owner)
						label += ' / ' + _('used by MLO network %s').format(w1700kMloOwnerLabel(owner));

					o.value(name, label);
				});

				o.load = function(section_id) {
					return w1700kLoadMloApChannels(w1700kMappedRadioNames()).then(L.bind(function(maps) {
						this.apChannelsByRadio = maps;
						return form.MultiValue.prototype.load.apply(this, [ section_id ]);
					}, this));
				};

				o.cfgvalue = function(section_id) {
						const current = radioNet.getWifiDeviceName();
						const devices = w1700kNormalizeDeviceList(uci.get('wireless', section_id, 'device'));

						return devices.length ? devices : [ current ];
					};

					o.validate = function(section_id, value) {
						if (w1700kFormValue(this.section, section_id, 'mlo') != '1')
							return true;

					return w1700kValidateMloDevices(section_id, value, this.apChannelsByRadio || {});
				};

					o.write = function(section_id, value) {
						const devices = w1700kNormalizeDeviceList(value);

						uci.set('wireless', section_id, 'device', devices);

						if (devices.length > 1) {
							uci.set('wireless', section_id, 'mlo', '1');
							w1700kEnsure6gMloApDefaults(this.section, section_id, this.apChannelsByRadio);
						}
					};

					o.remove = function(section_id) {
						uci.set('wireless', section_id, 'device', radioNet.getWifiDeviceName());
						uci.unset('wireless', section_id, 'mlo');
					};

					/* https://w1.fi/cgit/hostap/commit/?id=34f7c699a6bcb5c45f82ceb6743354ad79296078  */
					/* multicast_to_unicast https://github.com/openwrt/openwrt/commit/7babb978ad9d7fc29acb1ff86afb1eb343af303a */
					o = ss.taboption('advanced', form.Flag, 'multicast_to_unicast_all', _('Multi To Unicast'), _('ARP, IPv4 and IPv6 (even 802.1Q) with multicast destination MACs are unicast to the STA MAC address. Note: This is not Directed Multicast Service (DMS) in 802.11v. Note: might break receiver STA multicast expectations.'));
					o.rmempty = true;

					o = ss.taboption('advanced', form.Flag, 'isolate', _('Isolate Clients'), _('Prevents client-to-client communication'));
					o.depends('mode', 'ap');
					o.depends('mode', 'ap-wds');

					o = ss.taboption('advanced', form.Flag, 'bridge_isolate', _('Isolate Bridge Port'), _('Prevents communication only with targets on isolated bridge ports (while allowing it with targets on non-isolated ones). This also prevents client-to-client communication on the same interface when the WiFi device is in AP mode.'));

					o = ss.taboption('advanced', form.Value, 'ifname', _('Interface name'), _('Override default interface name'));
					o.optional = true;
					o.datatype = 'netdevname';
					o.placeholder = radioNet.getIfname();
					if (/^radio\d+\.network/.test(o.placeholder))
						o.placeholder = '';

					const macaddr = uci.get('wireless', radioNet.getName(), 'macaddr');
					o = ss.taboption('advanced', form.Value, 'macaddr', _('MAC address'), _('Override default MAC address - the range of usable addresses might be limited by the driver'));
					o.value('', _('driver default (%s)').format(!macaddr ? radioNet.getActiveBSSID() : _('no override')));
					o.value('random', _('randomly generated'));
					o.datatype = "or('random',macaddr)";

					o = ss.taboption('advanced', form.Flag, 'short_preamble', _('Short Preamble'));
					o.default = o.enabled;

					o = ss.taboption('advanced', form.Value, 'dtim_period', _('DTIM Interval'), _('Delivery Traffic Indication Message Interval'));
					o.optional = true;
					o.placeholder = 2;
					o.datatype = 'range(1,255)';

					o = ss.taboption('advanced', form.Value, 'wpa_group_rekey', _('Time interval for rekeying GTK'), _('sec'));
					o.optional    = true;
					o.placeholder = 600;
					o.datatype    = 'uinteger';

					o = ss.taboption('advanced', form.Flag , 'skip_inactivity_poll', _('Disable Inactivity Polling'));
					o.optional    = true;
					o.datatype    = 'uinteger';

					o = ss.taboption('advanced', form.Value, 'max_inactivity', _('Station inactivity limit'), _('802.11v: BSS Max Idle. Units: seconds.'));
					o.optional    = true;
					o.placeholder = 300;
					o.datatype    = 'uinteger';

					o = ss.taboption('advanced', form.Value, 'max_listen_interval', _('Maximum allowed Listen Interval'));
					o.optional    = true;
					o.placeholder = 65535;
					o.datatype    = 'uinteger';

					o = ss.taboption('advanced', form.Flag, 'disassoc_low_ack', _('Disassociate On Low Acknowledgement'), _('Allow AP mode to disconnect STAs based on low ACK condition'));
					o.default = o.enabled;
				}


				encr = o = ss.taboption('encryption', form.ListValue, 'encryption', _('Encryption'));
				o.depends('mode', 'ap');
				o.depends('mode', 'sta');
				o.depends('mode', 'adhoc');
				o.depends('mode', 'ahdemo');
				o.depends('mode', 'ap-wds');
				o.depends('mode', 'sta-wds');
				o.depends('mode', 'mesh');

				o.cfgvalue = function(section_id) {
					const v = String(uci.get('wireless', section_id, 'encryption'));
					if (v == 'wep')
						return 'wep-open';
					else if (v.match(/\+/))
						return v.replace(/\+.+$/, '');
					return v;
				};

				o.validate = function(section_id, value) {
					const modeval = w1700kFormValue(this.section, section_id, 'mode');
					const mlo = w1700kFormValue(this.section, section_id, 'mlo') == '1';
					const devices = w1700kSelectedDevices(this.section, section_id, radioNet.getWifiDeviceName());
					const has6g = devices.some(w1700kDeviceIs6g);
					const hasMloLinks = mlo && devices.length > 1;

					if ((modeval == 'ap' || modeval == 'ap-wds') && (has6g || hasMloLinks) && !w1700kSecureFor6gOrMlo(value))
						return _('6 GHz and MLO APs require WPA3-SAE, OWE, or WPA3 Enterprise security.');

					return true;
				};

				o.write = function(section_id, value) {
					let e = this.section.children.filter(function(o) { return o.option == 'encryption'; })[0].formvalue(section_id);
					const co = this.section.children.filter(function(o) { return o.option == 'cipher'; })[0];
					const c = co.formvalue(section_id);
					const modeval = w1700kFormValue(this.section, section_id, 'mode');
					const uses6gOrMlo = w1700kUses6gOrMlo(this.section, section_id, radioNet.getWifiDeviceName());

					if (uses6gOrMlo && String(c || '').toLowerCase().split('+').includes('tkip'))
						throw new Error(_('TKIP is not valid for 6 GHz or MLO.'));

					if (value == 'wpa' || value == 'wpa2' || value == 'wpa3' || value == 'wpa3-mixed' || value == 'wpa3-192')
						uci.unset('wireless', section_id, 'key');

					if (co.isActive(section_id) && e && (c == 'tkip' || c == 'ccmp' || c == 'ccmp256' || c == 'gcmp' || c == 'gcmp256' || c == 'tkip+ccmp'))
						e += '+' + c;

					if (w1700kModeIsApLike(modeval) && uses6gOrMlo && w1700kSecureFor6gOrMlo(e))
						w1700kEnsure6gMloApDefaults(this.section, section_id);

					uci.set('wireless', section_id, 'encryption', e);
				};

				o = ss.taboption('encryption', form.ListValue, 'cipher', _('Cipher'));
				o.depends('encryption', 'wpa');
				o.depends('encryption', 'wpa2');
				o.depends('encryption', 'wpa3');
				o.depends('encryption', 'wpa3-mixed');
				o.depends('encryption', 'wpa3-192');
				o.depends('encryption', 'psk');
				o.depends('encryption', 'sae');
				o.depends('encryption', 'psk2');
				o.depends('encryption', 'wpa-mixed');
				o.depends('encryption', 'psk-mixed');
				o.value('auto', _('auto'));
				o.value('ccmp', _('Force CCMP (AES)'));
				o.value('ccmp256', _('Force CCMP-256 (AES)'));
				o.value('gcmp', _('Force GCMP (AES)'));
				o.value('gcmp256', _('Force GCMP-256 (AES)'));
				o.value('tkip', _('Force TKIP'));
				o.value('tkip+ccmp', _('Force TKIP and CCMP (AES)'));
				o.validate = function(section_id, value) {
					const uses6gOrMlo = w1700kUses6gOrMlo(this.section, section_id, radioNet.getWifiDeviceName());

					if (uses6gOrMlo &&
					    String(value || '').toLowerCase().split('+').indexOf('tkip') >= 0)
						return _('TKIP is not valid for 6 GHz or MLO. Select auto, CCMP, or GCMP.');

					return true;
				};
				o.write = ss.children.filter(function(o) { return o.option == 'encryption'; })[0].write;

				o.cfgvalue = function(section_id) {
					let v = String(uci.get('wireless', section_id, 'encryption'));
					if (v.match(/\+/)) {
						v = v.replace(/^[^+]+\+/, '');
						if (v == 'aes')
							v = 'ccmp';
						else if (v == 'tkip+aes' || v == 'aes+tkip' || v == 'ccmp+tkip')
							v = 'tkip+ccmp';
					}
					return v;
				};


				const crypto_modes = [];

				if (hwtype == 'mac80211') {
					const has_supplicant = L.hasSystemFeature('wpasupplicant');
					const has_hostapd = L.hasSystemFeature('hostapd');

					// Probe EAP support
					const has_ap_eap = L.hasSystemFeature('hostapd', 'eap');
					const has_sta_eap = L.hasSystemFeature('wpasupplicant', 'eap');

					// Probe SAE support
					const has_ap_sae = L.hasSystemFeature('hostapd', 'sae');
					const has_sta_sae = L.hasSystemFeature('wpasupplicant', 'sae');

					// Probe OWE support
					const has_ap_owe = L.hasSystemFeature('hostapd', 'owe');
					const has_sta_owe = L.hasSystemFeature('wpasupplicant', 'owe');

					// Probe Suite-B support
					const has_ap_eap192 = L.hasSystemFeature('hostapd', 'suiteb192');
					const has_sta_eap192 = L.hasSystemFeature('wpasupplicant', 'suiteb192');

					// Probe WEP support
					const has_ap_wep = L.hasSystemFeature('hostapd', 'wep');
					const has_sta_wep = L.hasSystemFeature('wpasupplicant', 'wep');

					if (has_hostapd || has_supplicant) {
						crypto_modes.push(['psk2',      'WPA2-PSK',                    35]);
						crypto_modes.push(['psk-mixed', 'WPA-PSK/WPA2-PSK Mixed Mode', 22]);
						crypto_modes.push(['psk',       'WPA-PSK',                     12]);
					}
					else {
						encr.description = _('WPA-Encryption requires wpa_supplicant (for client mode) or hostapd (for AP and ad-hoc mode) to be installed.');
					}

					if (has_ap_sae || has_sta_sae) {
						crypto_modes.push(['sae',       'WPA3-SAE',                     31]);
						crypto_modes.push(['sae-mixed', 'WPA2-PSK/WPA3-SAE Mixed Mode', 30]);
					}

					// WPA3-Personal Compatibility Mode uses RSN overriding, which is an AP-only feature
					if (has_ap_sae)
						crypto_modes.push(['sae-compat', 'WPA2-PSK/WPA3-SAE Compatibility Mode', 30]);

					if (has_ap_wep || has_sta_wep) {
						crypto_modes.push(['wep-open',   _('WEP Open System'), 11]);
						crypto_modes.push(['wep-shared', _('WEP Shared Key'),  10]);
					}

					if (has_ap_eap || has_sta_eap) {
						if (has_ap_eap192 || has_sta_eap192) {
							crypto_modes.push(['wpa3', 'WPA3-EAP', 33]);
							crypto_modes.push(['wpa3-mixed', 'WPA2-EAP/WPA3-EAP Mixed Mode', 32]);
							crypto_modes.push(['wpa3-192', 'WPA3-EAP 192-bit Mode', 36]);
						}

						crypto_modes.push(['wpa2', 'WPA2-EAP', 34]);
						crypto_modes.push(['wpa',  'WPA-EAP',  20]);
					}

					if (has_ap_owe || has_sta_owe) {
						crypto_modes.push(['owe', 'OWE', 1]);
					}

					encr.crypto_support = {
						'ap': {
							'wep-open': has_ap_wep || _('Requires hostapd with WEP support'),
							'wep-shared': has_ap_wep || _('Requires hostapd with WEP support'),
							'psk': has_hostapd || _('Requires hostapd'),
							'psk2': has_hostapd || _('Requires hostapd'),
							'psk-mixed': has_hostapd || _('Requires hostapd'),
							'sae': has_ap_sae || _('Requires hostapd with SAE support'),
							'sae-mixed': has_ap_sae || _('Requires hostapd with SAE support'),
							'sae-compat': has_ap_sae || _('Requires hostapd with SAE support'),
							'wpa': has_ap_eap || _('Requires hostapd with EAP support'),
							'wpa2': has_ap_eap || _('Requires hostapd with EAP support'),
							'wpa3': has_ap_eap192 || _('Requires hostapd with EAP Suite-B support'),
							'wpa3-mixed': has_ap_eap192 || _('Requires hostapd with EAP Suite-B support'),
							'wpa3-192': has_ap_eap192 || _('Requires hostapd with EAP Suite-B support'),
							'owe': has_ap_owe || _('Requires hostapd with OWE support')
						},
						'sta': {
							'wep-open': has_sta_wep || _('Requires wpa-supplicant with WEP support'),
							'wep-shared': has_sta_wep || _('Requires wpa-supplicant with WEP support'),
							'psk': has_supplicant || _('Requires wpa-supplicant'),
							'psk2': has_supplicant || _('Requires wpa-supplicant'),
							'psk-mixed': has_supplicant || _('Requires wpa-supplicant'),
							'sae': has_sta_sae || _('Requires wpa-supplicant with SAE support'),
							'sae-mixed': has_sta_sae || _('Requires wpa-supplicant with SAE support'),
							'wpa': has_sta_eap || _('Requires wpa-supplicant with EAP support'),
							'wpa2': has_sta_eap || _('Requires wpa-supplicant with EAP support'),
							'wpa3': has_sta_eap192 || _('Requires wpa-supplicant with EAP Suite-B support'),
							'wpa3-mixed': has_sta_eap192 || _('Requires wpa-supplicant with EAP Suite-B support'),
							'wpa3-192': has_sta_eap192 || _('Requires wpa-supplicant with EAP Suite-B support'),
							'owe': has_sta_owe || _('Requires wpa-supplicant with OWE support')
						},
						'adhoc': {
							'wep-open': true,
							'wep-shared': true,
							'psk': has_supplicant || _('Requires wpa-supplicant'),
							'psk2': has_supplicant || _('Requires wpa-supplicant'),
							'psk-mixed': has_supplicant || _('Requires wpa-supplicant'),
						},
						'mesh': {
							'sae': has_sta_sae || _('Requires wpa-supplicant with SAE support')
						},
						'ahdemo': {
							'wep-open': true,
							'wep-shared': true
						},
						'wds': {
							'wep-open': true,
							'wep-shared': true
						}
					};

					encr.crypto_support['ap-wds'] = encr.crypto_support['ap'];
					encr.crypto_support['sta-wds'] = encr.crypto_support['sta'];

					encr.validate = function(section_id, value) {
						const modeopt = this.section.children.filter(function(o) { return o.option == 'mode'; })[0];
						const modeval = modeopt.formvalue(section_id);
						const modeidx = (modeopt.keylist || []).indexOf(modeval);
						const encidx = (this.keylist || []).indexOf(value);
						const modetitle = (modeidx >= 0) ? modeopt.vallist[modeidx] : (modeval || _('unknown'));
						const enctitle = (encidx >= 0) ? this.vallist[encidx] : (value || _('unknown'));
						const uses6gOrMlo = w1700kUses6gOrMlo(this.section, section_id, radioNet.getWifiDeviceName());

						if (w1700kModeIsApLike(modeval) && uses6gOrMlo && !w1700kSecureFor6gOrMlo(value))
							return _('6 GHz and MLO APs require WPA3-SAE, OWE, or WPA3 Enterprise security.');

						if (value == 'none')
							return true;

						if (!L.isObject(this.crypto_support[modeval]) || !this.crypto_support[modeval].hasOwnProperty(value))
							return _('The selected %s mode is incompatible with %s encryption').format(modetitle, enctitle);

						return this.crypto_support[modeval][value];
					};
				}
				else if (hwtype == 'broadcom') {
					crypto_modes.push(['psk2',     'WPA2-PSK',                    33]);
					crypto_modes.push(['psk+psk2', 'WPA-PSK/WPA2-PSK Mixed Mode', 22]);
					crypto_modes.push(['psk',      'WPA-PSK',                     12]);
					crypto_modes.push(['wep-open',   _('WEP Open System'),        11]);
					crypto_modes.push(['wep-shared', _('WEP Shared Key'),         10]);
				}

				crypto_modes.push(['none',       _('No Encryption'),   0]);

				crypto_modes.sort(function(a, b) { return b[2] - a[2]; });

				crypto_modes.forEach(crypto_mode => {
					const security_level = (crypto_mode[2] >= 30) ? _('strong security')
						: (crypto_mode[2] >= 20) ? _('medium security')
							: (crypto_mode[2] >= 10) ? _('weak security') : _('open network');

					encr.value(crypto_mode[0], '%s (%s)'.format(crypto_mode[1], security_level));
				});

				// QR Code
				o = ss.taboption('encryption', form.DummyValue, '_qrops', _('QR Code'),
					_('SSID and passwords with URIencoded sequences (e.g. %20) may not work.'));
				o.modalonly = true;

				o.createWiFiPassword = function(section_id) {
					// https://www.wi-fi.org/system/files/WPA3%20Specification%20v3.5.pdf#page=33
					/*
					WIFI:T:WPA;S:mynetwork;P:mypass;;

					WIFI-qr = "WIFI:" [type ";"] [trdisable ";"] ssid ";" [hidden ";"] [id ";"] [password ";"] [public-key ";"] ";"

					Param 		Description
					type		"T:" *(unreserved) ; security type
					trdisable	"R:" *(HEXDIG) ; Transition Disable value
					ssid		"S:" *(printable / pct-encoded) ; SSID of the network
					hidden		"H:true" ; when present, indicates a hidden (stealth) SSID is used
					id			"I:" *(printable / pct-encoded) ; UTF-8 encoded password identifier, present if the password has an SAE password identifier
					password	"P:" *(printable / pct-encoded) ; password, present for password-based authentication
					public-key	"K:" *PKCHAR ; DER of ASN.1 SubjectPublicKeyInfo in compressed form and encoded in "base64" as per [6], present when the network supports SAE-PK, else absent

					printable = %x20-3a / %x3c-7e ; semi-colon excluded
					PKCHAR = ALPHA / DIGIT / %x2b / %x2f / %x3d
					*/

					function pctEncode(str) {
						const bytes = new TextEncoder().encode(str);
						let out = "";
						for (const b of bytes) {
							// printable = 0x20–0x3A and 0x3C–0x7E, but semicolon (0x3B) excluded
							// anything *within* this range %encoded should be treated as printable literal(?)
							// There seems to be a glaring bug in this WiFi spec. Ofc there are bugs. 
							// By not encoding the "%" character, a string literal % with two successive
							// digits is ambiguous. If the password contains "%20" which
							// should be interpreted literally ['%', '2', '0'] and not " ", some
							// clients interpret this as " ". YMMV.
							const printable = (b >= 0x20 && b <= 0x3A && b !== 0x3B)
								|| (b >= 0x3C && b <= 0x7E);

							if (printable) {
								out += String.fromCharCode(b);
							} else {
								out += "%" + b.toString(16).toUpperCase().padStart(2, "0");
							}
						}
						return out;
					}

					const wifiSSID = this.section.formvalue(section_id, 'ssid'); // S
					const wifiEncr = this.section.formvalue(section_id, 'encryption'); // T
					const wifiKey  = this.section.formvalue(section_id, '_wpa_key'); // P
					const wifiHide = this.section.formvalue(section_id, 'hidden') === '1'; // H

					/* trdisable:
					0 WPA3-Personal
					1 SAE-PK
					2 WPA3-Enterprise
					3 WiFi-Enhanced Open */
					let trdisable = ''; // R
					switch (true) {
					case (wifiEncr === 'sae'): trdisable = 0; break; // 'sae' i.e. WPA3-Personal
					// case (???): trdisable = 1; break; // SAE-PK
					case (wifiEncr.startsWith('wpa3')): trdisable = 2; break; // 'wpa3*' i.e. WPA3-Enterprise
					case (wifiEncr === 'owe'): trdisable = 3; break; // 'open' i.e. WiFi-Enhanced Open
					default: trdisable = ''; break;
					}

					return [
						`WIFI:`,
						(wifiKey) ? `T:WPA;`: null, // absent indicates [open || Wi-Fi Enhanced Open ]
						(trdisable !== '') ? `R:${trdisable};` : null,
						`S:${wifiSSID};`,
						(wifiHide) ? `H:${wifiHide};` : null,
						(wifiKey) ? `P:${pctEncode(wifiKey)};`: null,
					].filter(Boolean).join('') + ';';
				};

				o.handleGenerateQR = function(section_id, ev) {
					const parent = s.map;
					const mapNode = document.querySelector('body.modal-overlay-active > #modal_overlay > .modal.cbi-modal > .cbi-map:not(.hidden)');
					const headNode = mapNode.parentNode.querySelector('h4');
					const wifiQRGenerator = this.createWiFiPassword.bind(this, section_id);

					return Promise.all([
						parent.save(null, true)
					]).then(function(data) {
						let qrm, qrs, qro;

						qrm = new form.JSONMap({ qrcode: {  } },
							null, _('Scan this QR code with the client device.'));
						qrm.parent = parent;

						qrs = qrm.section(form.NamedSection, 'qrcode');

						function handleQRParamChange(ev, section_id, value) {
							const code = this.map.findElement('.qr-code');
							const conf = this.map.findElement('.wifi-qr-code-content');
							const ecc = this.section.getUIElement(section_id, 'ecc');

							if (this.isValid(section_id)) {
								conf.firstChild.data = wifiQRGenerator(section_id);
								code.style.opacity = '.5';

								buildSVGQRCode(conf.firstChild.data, code, {ecc: ecc.getValue()});
							}
						};

						qro = qrs.option(form.ListValue, 'ecc', _('QR Error Correction Code Level'));
						qro.value('L', _('Low'));
						qro.value('M', _('Medium'));
						qro.value('Q', _('Quartile'));
						qro.value('H', _('High'));
						qro.onchange = handleQRParamChange;


						qro = qrs.option(form.DummyValue, 'output');
						qro.renderWidget = function() {
							const wifi_qr = wifiQRGenerator(section_id);
							const ecc = this.section.formvalue(section_id, 'ecc');

							return E('div', {
								'class': 'qr-code-display',
								'style': 'display:flex; flex-wrap:wrap; align-items:center; gap:.5em',
							}, [
								E('div', {
									'class': 'qr-code',
									// any width and height should be ~360: enough for QR with K: field and High ECC.
								}, [
									// fill initial QR code
									E(buildSVGQRCode(wifi_qr, null, {ecc: ecc || undefined}, true))
								]),
								E('pre', {
									'class': 'wifi-qr-code-content',
									'style': 'flex:1; overflow:auto; word-break:break-all; ',
									'click': function(ev) {
										const sel = window.getSelection();
										const range = document.createRange();

										range.selectNodeContents(ev.currentTarget);

										sel.removeAllRanges();
										sel.addRange(range);
									}
								}, [ wifi_qr ])
							]);
						};

						return qrm.render().then(function(nodes) {
							// stash the current dialogue style (visible)
							const dStyle = mapNode.style;
							// hide the current modal window
							mapNode.style.display = 'none';
							// stash the current button row style (visible)
							const bRowStyle = mapNode.nextElementSibling.style;
							// hide the [ Dismiss | Save ] button row
							mapNode.nextElementSibling.style.display = 'none';

							headNode.appendChild(E('span', [ ' » ', _('Generate WiFi QR…') ]));
							mapNode.parentNode.appendChild(E([], [
								nodes,
								E('div', {
									'class': 'right'
								}, [
									E('button', {
										'class': 'btn',
										'click': function() {
											// Remove QR code button (row)
											nodes.parentNode.removeChild(nodes.nextSibling);
											// Remove QR code form
											nodes.parentNode.removeChild(nodes);
											// unhide the WiFi modal dialogue
											mapNode.style = dStyle;
											// Revert button row style to visible again
											mapNode.nextSibling.style = bRowStyle;
											// Remove the H4 span (») title
											headNode.removeChild(headNode.lastChild);
										}
									}, [ _('Back to settings') ])
								])
							]));
						});
					});
				};

				o.cfgvalue = function(section_id, value) {
					return E('button', {
						'class': 'btn qr-code',
						'style': 'display:inline-flex;align-items:center;gap:.5em',
						'click': ui.createHandlerFn(this, 'handleGenerateQR', section_id),
					}, [
						// inject dummy QR code
						E(buildSVGQRCode('openwrt.org', null, {pixelSize: 1, ecc: 'L'}, true)),
						_('Generate QR…')
					]);
				};
				// End QR Code

				o = ss.taboption('encryption', form.Flag, 'ppsk', _('Enable Private PSK (PPSK)'), _('Private Pre-Shared Key (PPSK) allows the use of different Pre-Shared Key for each STA MAC address. Private MAC PSKs are stored on the RADIUS server.'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk', 'psk2', 'psk+psk2', 'psk-mixed'] });

				o = ss.taboption('encryption', form.Value, 'auth_server', _('RADIUS Authentication Server'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk', 'psk2', 'psk+psk2', 'psk-mixed'], ppsk: ['1'] });
				o.rmempty = true;
				o.datatype = 'host(0)';

				o = ss.taboption('encryption', form.Value, 'auth_port', _('RADIUS Authentication Port'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk', 'psk2', 'psk+psk2', 'psk-mixed'], ppsk: ['1'] });
				o.rmempty = true;
				o.datatype = 'port';
				o.placeholder = '1812';

				o = ss.taboption('encryption', form.Value, 'auth_secret', _('RADIUS Authentication Secret'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk', 'psk2', 'psk+psk2', 'psk-mixed'], ppsk: ['1'] });
				o.rmempty = true;
				o.password = true;

				o = ss.taboption('encryption', form.Value, 'acct_server', _('RADIUS Accounting Server'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				o.rmempty = true;
				o.datatype = 'host(0)';

				o = ss.taboption('encryption', form.Value, 'acct_port', _('RADIUS Accounting Port'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				o.rmempty = true;
				o.datatype = 'port';
				o.placeholder = '1813';

				o = ss.taboption('encryption', form.Value, 'acct_secret', _('RADIUS Accounting Secret'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				o.rmempty = true;
				o.password = true;

				/* extra RADIUS settings start */
				const attr_validate = function(section_id, value) {
					if (!value)
						return true;

					if (!/^[0-9]+(:s:.+|:d:[0-9]+|:x:([0-9a-zA-Z]{2})+)?$/.test(value) )
						return _('Must be in %s format.').format('<attr_id>[:<syntax:value>]');

					return true;
				};

				const req_attr_syntax = _('Format:') + '<code>&lt;attr_id&gt;[:&lt;syntax:value&gt;]</code>' + '<br />' +
					'<code>syntax: s = %s; '.format(_('string (UTF-8)')) + 'd = %s; '.format(_('integer')) + 'x = %s</code>'.format(_('octet string'));

				/* https://w1.fi/cgit/hostap/commit/?id=af35e7af7f8bb1ca9f0905b4074fb56a264aa12b */
				o = ss.taboption('encryption', form.DynamicList, 'radius_auth_req_attr', _('RADIUS Access-Request attributes'),
					_('Attributes to add/replace in each request.') + '<br />' + req_attr_syntax );
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				o.rmempty = true;
				o.validate = attr_validate;
				o.placeholder = '126:s:Operator';

				o = ss.taboption('encryption', form.DynamicList, 'radius_acct_req_attr', _('RADIUS Accounting-Request attributes'),
					_('Attributes to add/replace in each request.') + '<br />' + req_attr_syntax );
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				o.rmempty = true;
				o.validate = attr_validate;
				o.placeholder = '77:x:74657374696e67';

				o = ss.taboption('encryption', form.ListValue, 'dynamic_vlan', _('RADIUS Dynamic VLAN Assignment'), _('Required: Rejects auth if RADIUS server does not provide appropriate VLAN attributes.'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk', 'psk2', 'psk+psk2', 'psk-mixed'], ppsk: ['1'] });
				o.value('0', _('Disabled'));
				o.value('1', _('Optional'));
				o.value('2', _('Required'));
				o.write = function (section_id, value) {
					return this.super('write', [section_id, (value == 0) ? null: value]);
				};

				o = ss.taboption('encryption', form.Flag, 'per_sta_vif', _('RADIUS Per STA VLAN'), _('Each STA is assigned its own AP_VLAN interface.'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk', 'psk2', 'psk+psk2', 'psk-mixed'], ppsk: ['1'] });

				//hostapd internally defaults to vlan_naming=1 even with dynamic VLAN off
				o = ss.taboption('encryption', form.Flag, 'vlan_naming', _('RADIUS VLAN Naming'), _('Off: <code>vlanXXX</code>, e.g., <code>vlan1</code>. On: <code>vlan_tagged_interface.XXX</code>, e.g. <code>eth0.1</code>.'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk', 'psk2', 'psk+psk2', 'psk-mixed'], ppsk: ['1'] });
				o.enabled = '1';
				o.disabled = '0';
				o.default = o.enabled;

				o = ss.taboption('encryption', widgets.DeviceSelect, 'vlan_tagged_interface', _('RADIUS VLAN Tagged Interface'), _('E.g. eth0, eth1'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk', 'psk2', 'psk+psk2', 'psk-mixed'], ppsk: ['1'] });
				o.size = 1;
				o.rmempty = true;
				o.multiple = false;
				o.noaliases = true;
				o.nocreate = true;
				o.noinactive = true;

				o = ss.taboption('encryption', form.Value, 'vlan_bridge', _('RADIUS VLAN Bridge Naming Scheme'), _('E.g. <code>br-vlan</code> or <code>brvlan</code>.'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk', 'psk2', 'psk+psk2', 'psk-mixed'], ppsk: ['1'] });
				o.rmempty = true;

				/* extra RADIUS settings end */

				o = ss.taboption('encryption', form.Value, 'dae_client', _('DAE-Client'), _('Dynamic Authorization Extension client.'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				o.rmempty = true;
				o.datatype = 'host(0)';

				o = ss.taboption('encryption', form.Value, 'dae_port', _('DAE-Port'), _('Dynamic Authorization Extension port.'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				o.rmempty = true;
				o.datatype = 'port';
				o.placeholder = '3799';

				o = ss.taboption('encryption', form.Value, 'dae_secret', _('DAE-Secret'), _('Dynamic Authorization Extension secret.'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
				o.rmempty = true;
				o.password = true;

				//WPA(1) has only WPA IE. Only >= WPA2 has RSN IE Preauth frames.
				o = ss.taboption('encryption', form.Flag, 'rsn_preauth', _('RSN Preauth'), _('Robust Security Network (RSN): Allow roaming preauth for WPA2-EAP networks (and advertise it in WLAN beacons). Only works if the specified network interface is a bridge. Shortens the time-critical reassociation process.'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa2', 'wpa3', 'wpa3-mixed'] });


				o = ss.taboption('encryption', form.Value, '_wpa_key', _('Key'));
				add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk', 'psk2', 'psk+psk2', 'psk-mixed'], ppsk: ['0'] });
				add_dependency_permutations(o, { mode: ['sta', 'adhoc', 'mesh', 'sta-wds'], encryption: ['psk', 'psk2', 'psk+psk2', 'psk-mixed'] });
				o.depends('encryption', 'sae');
				o.depends('encryption', 'sae-mixed');
				o.depends('encryption', 'sae-compat');
				o.datatype = 'wpakey';
				o.rmempty = true;
				o.password = true;

				o.validate = function(section_id, value) {
					const mode = w1700kFormValue(this.section, section_id, 'mode');
					const encryption = w1700kFormValue(this.section, section_id, 'encryption');
					const uses6gOrMlo = w1700kUses6gOrMlo(this.section, section_id, radioNet.getWifiDeviceName());

					if (w1700kModeIsApLike(mode) && uses6gOrMlo && encryption == 'sae' && (!value || String(value).length == 0))
						return _('MLO and 6 GHz WPA3-SAE networks require a Wi-Fi key.');

					return form.Value.prototype.validate.apply(this, arguments);
				};

				o.cfgvalue = function(section_id) {
					const key = uci.get('wireless', section_id, 'key');
					return /^[1234]$/.test(key) ? null : key;
				};

				o.write = function(section_id, value) {
					uci.set('wireless', section_id, 'key', value);
					uci.unset('wireless', section_id, 'key1');
					uci.unset('wireless', section_id, 'key2');
					uci.unset('wireless', section_id, 'key3');
					uci.unset('wireless', section_id, 'key4');
				};


				o = ss.taboption('encryption', form.ListValue, '_wep_key', _('Used Key Slot'));
				o.depends('encryption', 'wep-open');
				o.depends('encryption', 'wep-shared');
				o.value('1', _('Key #%d').format(1));
				o.value('2', _('Key #%d').format(2));
				o.value('3', _('Key #%d').format(3));
				o.value('4', _('Key #%d').format(4));

				o.cfgvalue = function(section_id) {
					const slot = +uci.get('wireless', section_id, 'key');
					return (slot >= 1 && slot <= 4) ? String(slot) : '';
				};

				o.write = function(section_id, value) {
					uci.set('wireless', section_id, 'key', value);
				};

				for (let slot = 1; slot <= 4; slot++) {
					o = ss.taboption('encryption', form.Value, 'key%d'.format(slot), _('Key #%d').format(slot));
					o.depends('encryption', 'wep-open');
					o.depends('encryption', 'wep-shared');
					o.datatype = 'wepkey';
					o.rmempty = true;
					o.password = true;

					o.write = function(section_id, value) {
						if (value != null && (value.length == 5 || value.length == 13))
							value = 's:%s'.format(value);
						uci.set('wireless', section_id, this.option, value);
					};
				}


				if (hwtype == 'mac80211') {
					// Probe 802.11r support (and EAP support as a proxy for Openwrt)
					const has_80211r = L.hasSystemFeature('hostapd', '11r') || L.hasSystemFeature('hostapd', 'eap');

					o = ss.taboption('roaming', form.Flag, 'ieee80211r', _('802.11r Fast Transition'), _('Enables fast roaming among access points that belong to the same Mobility Domain'));
					add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
					if (has_80211r)
						add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk2', 'psk-mixed', 'sae', 'sae-mixed', 'sae-compat'] });
					o.rmempty = true;

					o = ss.taboption('roaming', form.Value, 'nasid', _('NAS ID'), _('Used for two different purposes: RADIUS NAS ID and 802.11r R0KH-ID. Not needed with normal WPA(2)-PSK.'));
					add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
					o.depends({ ieee80211r: '1' });
					o.rmempty = true;

					o = ss.taboption('roaming', form.Value, 'mobility_domain', _('Mobility Domain'), _('4-character hexadecimal ID'));
					o.depends({ ieee80211r: '1' });
					o.placeholder = _('automatically derived from SSID');
					o.datatype = 'and(hexstring,length(4))';
					o.rmempty = true;

					o = ss.taboption('roaming', form.Value, 'reassociation_deadline', _('Reassociation Deadline'), _('time units (TUs / 1.024 ms) [1000-65535]'));
					o.depends({ ieee80211r: '1' });
					o.placeholder = '20000';
					o.datatype = 'range(1000,65535)';
					o.rmempty = true;

					o = ss.taboption('roaming', form.ListValue, 'ft_over_ds', _('FT protocol'));
					o.depends({ ieee80211r: '1' });
					o.value('0', _('FT over the Air'));
					o.value('1', _('FT over DS'));
					o.rmempty = true;

					o = ss.taboption('roaming', form.Flag, 'ft_psk_generate_local', _('Generate PMK locally'), _('When using a PSK, the PMK can be automatically generated. When enabled, the R0/R1 key options below are not applied. Disable this to use the R0 and R1 key options.'));
					add_dependency_permutations(o, { ieee80211r: ['1'], mode: ['ap', 'ap-wds'], encryption: ['psk2', 'psk-mixed'] });
					o.default = o.enabled;
					o.rmempty = false;

					o = ss.taboption('roaming', form.Value, 'r0_key_lifetime', _('R0 Key Lifetime'), _('minutes'));
					o.depends({ ieee80211r: '1' });
					o.placeholder = '10000';
					o.datatype = 'uinteger';
					o.rmempty = true;

					o = ss.taboption('roaming', form.Value, 'r1_key_holder', _('R1 Key Holder'), _('6-octet identifier as a hex string - no colons'));
					o.depends({ ieee80211r: '1' });
					o.placeholder = _('automatically derived from Mobility Domain and PSK');
					o.datatype = 'and(hexstring,length(12))';
					o.rmempty = true;

					o = ss.taboption('roaming', form.Flag, 'pmk_r1_push', _('PMK R1 Push'));
					o.depends({ ieee80211r: '1' });
					o.placeholder = '0';
					o.rmempty = true;

					o = ss.taboption('roaming', form.DynamicList, 'r0kh', _('External R0 Key Holder List'), _('List of R0KHs in the same Mobility Domain. <br />Format: MAC-address,NAS-Identifier,256-bit key as hex string. <br />This list is used to map R0KH-ID (NAS Identifier) to a destination MAC address when requesting PMK-R1 key from the R0KH that the STA used during the Initial Mobility Domain Association.'));
					o.depends({ ieee80211r: '1' });
					o.rmempty = true;

					o = ss.taboption('roaming', form.DynamicList, 'r1kh', _('External R1 Key Holder List'), _ ('List of R1KHs in the same Mobility Domain. <br />Format: MAC-address,R1KH-ID as 6 octets with colons,256-bit key as hex string. <br />This list is used to map R1KH-ID to a destination MAC address when sending PMK-R1 key from the R0KH. This is also the list of authorized R1KHs in the MD that can request PMK-R1 keys.'));
					o.depends({ ieee80211r: '1' });
					o.rmempty = true;
					// End of 802.11r options

					// Probe 802.11k and 802.11v support via EAP support (full hostapd has EAP)
					if (L.hasSystemFeature('hostapd', 'eap')) {
						/* 802.11k settings start */
						o = ss.taboption('roaming', form.Flag, 'ieee80211k', _('802.11k RRM'), _('Radio Resource Measurement - Sends beacons to assist roaming. Not all clients support this.'));
						// add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk', 'psk2', 'psk-mixed', 'sae', 'sae-mixed'] });
						o.depends('mode', 'ap');
						o.depends('mode', 'ap-wds');

						o = ss.taboption('roaming', form.Flag, 'rrm_neighbor_report', _('Neighbour Report'), _('802.11k: Enable neighbor report via radio measurements.'));
						o.depends({ ieee80211k: '1' });
						o.default = o.enabled;

						o = ss.taboption('roaming', form.Flag, 'rrm_beacon_report', _('Beacon Report'), _('802.11k: Enable beacon report via radio measurements.'));
						o.depends({ ieee80211k: '1' });
						o.default = o.enabled;
						/* 802.11k settings end */

						/* 802.11v settings start */
						o = ss.taboption('roaming', form.ListValue, 'time_advertisement', _('Time advertisement'), _('802.11v: Time Advertisement in management frames.'));
						o.value('0', _('Disabled'));
						o.value('2', _('Enabled'));
						o.write = function (section_id, value) {
							return this.super('write', [section_id, (value == 2) ? value: null]);
						};

						//Pull current System TZ setting
						const tz = uci.get('system', '@system[0]', 'timezone');
						o = ss.taboption('roaming', form.Value, 'time_zone', _('Time zone'), _('802.11v: Local Time Zone Advertisement in management frames.'));
						o.value(tz);
						o.rmempty = true;

						o = ss.taboption('roaming', form.Flag, 'wnm_sleep_mode', _('WNM Sleep Mode'), _('802.11v: Wireless Network Management (WNM) Sleep Mode (extended sleep mode for stations).'));
						o.rmempty = true;

						/* wnm_sleep_mode_no_keys: https://git.openwrt.org/?p=openwrt/openwrt.git;a=commitdiff;h=bf98faaac8ed24cf7d3d93dd4fcd7304d109363b */
						o = ss.taboption('roaming', form.Flag, 'wnm_sleep_mode_no_keys', _('WNM Sleep Mode Fixes'), _('802.11v: Wireless Network Management (WNM) Sleep Mode Fixes: Prevents reinstallation attacks.'));
						o.rmempty = true;

						o = ss.taboption('roaming', form.Flag, 'bss_transition', _('BSS Transition'), _('802.11v: Basic Service Set (BSS) transition management.'));
						o.rmempty = true;

						/* in master, but not 21.02.1: proxy_arp */
						o = ss.taboption('roaming', form.Flag, 'proxy_arp', _('ProxyARP'), _('802.11v: Proxy ARP enables non-AP STA to remain in power-save for longer.'));
						o.rmempty = true;

						/* TODO: na_mcast_to_ucast is missing: needs adding to hostapd.sh - nice to have */
					}
					/* 802.11v settings end */
				}

				if (hwtype == 'mac80211') {
					o = ss.taboption('encryption', form.ListValue, 'eap_type', _('EAP-Method'));
					o.value('tls',  'TLS');
					o.value('ttls', 'TTLS');
					o.value('peap', 'PEAP');
					o.value('fast', 'FAST');
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });

					o = ss.taboption('encryption', form.Flag, 'ca_cert_usesystem', _('Use system certificates'), _("Validate server certificate using built-in system CA bundle,<br />requires the \"ca-bundle\" package"));
					o.enabled = '1';
					o.disabled = '0';
					o.default = o.disabled;
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });
					o.validate = function(section_id, value) {
						if (value == '1' && !L.hasSystemFeature('cabundle')) {
							return _("This option cannot be used because the ca-bundle package is not installed.");
						}
						return true;
					};

					o = ss.taboption('encryption', form.FileUpload, 'ca_cert', _('Path to CA-Certificate'));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], ca_cert_usesystem: ['0'] });

					o = ss.taboption('encryption', form.Value, 'subject_match', _('Certificate constraint (Subject)'), _("Certificate constraint substring - e.g. /CN=wifi.mycompany.com<br />See `logread -f` during handshake for actual values"));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });

					o = ss.taboption('encryption', form.DynamicList, 'altsubject_match', _('Certificate constraint (SAN)'), _("Certificate constraint(s) via Subject Alternate Name values<br />(supported attributes: EMAIL, DNS, URI) - e.g. DNS:wifi.mycompany.com"));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });

					o = ss.taboption('encryption', form.DynamicList, 'domain_match', _('Certificate constraint (Domain)'), _("Certificate constraint(s) against DNS SAN values (if available)<br />or Subject CN (exact match)"));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });

					o = ss.taboption('encryption', form.DynamicList, 'domain_suffix_match', _('Certificate constraint (Wildcard)'), _("Certificate constraint(s) against DNS SAN values (if available)<br />or Subject CN (suffix match)"));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'] });

					o = ss.taboption('encryption', form.FileUpload, 'client_cert', _('Path to Client-Certificate'));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], eap_type: ['tls'] });

					o = ss.taboption('encryption', form.FileUpload, 'private_key', _('Path to Private Key'));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], eap_type: ['tls'] });

					o = ss.taboption('encryption', form.Value, 'private_key_passwd', _('Password of Private Key'));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], eap_type: ['tls'] });
					o.password = true;

					o = ss.taboption('encryption', form.ListValue, 'auth', _('Authentication'));
					o.value('PAP', 'PAP');
					o.value('CHAP', 'CHAP');
					o.value('MSCHAP', 'MSCHAP');
					o.value('MSCHAPV2', 'MSCHAPv2');
					o.value('EAP-GTC', 'EAP-GTC');
					o.value('EAP-MD5', 'EAP-MD5');
					o.value('EAP-MSCHAPV2', 'EAP-MSCHAPv2');
					o.value('EAP-TLS', 'EAP-TLS');
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], eap_type: ['fast', 'peap', 'ttls'] });

					o.validate = function(section_id, value) {
						const eo = this.section.children.filter(function(o) { return o.option == 'eap_type'; })[0];
						const ev = eo.formvalue(section_id);

						if (ev != 'ttls' && (value == 'PAP' || value == 'CHAP' || value == 'MSCHAP' || value == 'MSCHAPV2'))
							return _('This authentication type is not applicable to the selected EAP method.');

						return true;
					};

					o = ss.taboption('encryption', form.Flag, 'ca_cert2_usesystem', _('Use system certificates for inner-tunnel'), _("Validate server certificate using built-in system CA bundle,<br />requires the \"ca-bundle\" package"));
					o.enabled = '1';
					o.disabled = '0';
					o.default = o.disabled;
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], auth: ['EAP-TLS'] });
					o.validate = function(section_id, value) {
						if (value == '1' && !L.hasSystemFeature('cabundle')) {
							return _("This option cannot be used because the ca-bundle package is not installed.");
						}
						return true;
					};

					o = ss.taboption('encryption', form.FileUpload, 'ca_cert2', _('Path to inner CA-Certificate'));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], auth: ['EAP-TLS'], ca_cert2_usesystem: ['0'] });

					o = ss.taboption('encryption', form.Value, 'subject_match2', _('Inner certificate constraint (Subject)'), _("Certificate constraint substring - e.g. /CN=wifi.mycompany.com<br />See `logread -f` during handshake for actual values"));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], auth: ['EAP-TLS'] });

					o = ss.taboption('encryption', form.DynamicList, 'altsubject_match2', _('Inner certificate constraint (SAN)'), _("Certificate constraint(s) via Subject Alternate Name values<br />(supported attributes: EMAIL, DNS, URI) - e.g. DNS:wifi.mycompany.com"));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], auth: ['EAP-TLS'] });

					o = ss.taboption('encryption', form.DynamicList, 'domain_match2', _('Inner certificate constraint (Domain)'), _("Certificate constraint(s) against DNS SAN values (if available)<br />or Subject CN (exact match)"));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], auth: ['EAP-TLS'] });

					o = ss.taboption('encryption', form.DynamicList, 'domain_suffix_match2', _('Inner certificate constraint (Wildcard)'), _("Certificate constraint(s) against DNS SAN values (if available)<br />or Subject CN (suffix match)"));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], auth: ['EAP-TLS'] });

					o = ss.taboption('encryption', form.FileUpload, 'client_cert2', _('Path to inner Client-Certificate'));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], auth: ['EAP-TLS'] });

					o = ss.taboption('encryption', form.FileUpload, 'private_key2', _('Path to inner Private Key'));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], auth: ['EAP-TLS'] });

					o = ss.taboption('encryption', form.Value, 'private_key2_passwd', _('Password of inner Private Key'));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], auth: ['EAP-TLS'] });
					o.password = true;

					o = ss.taboption('encryption', form.Value, 'identity', _('Identity'));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], eap_type: ['fast', 'peap', 'tls', 'ttls'] });

					o = ss.taboption('encryption', form.Value, 'anonymous_identity', _('Anonymous Identity'));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], eap_type: ['fast', 'peap', 'tls', 'ttls'] });

					o = ss.taboption('encryption', form.Value, 'password', _('Password'));
					add_dependency_permutations(o, { mode: ['sta', 'sta-wds'], encryption: ['wpa', 'wpa2', 'wpa3', 'wpa3-mixed', 'wpa3-192'], eap_type: ['fast', 'peap', 'ttls'] });
					o.password = true;


					if (hwtype == 'mac80211') {
						// ieee802.11w options
						o = ss.taboption('encryption', form.ListValue, 'ieee80211w', _('802.11w Management Frame Protection'), _("Note: Some wireless drivers do not fully support 802.11w. E.g. mwlwifi may have problems"));
						o.value('0', _('Disabled'));
						o.value('1', _('Optional'));
						o.value('2', _('Required'));
						add_dependency_permutations(o, { mode: ['ap', 'ap-wds', 'sta', 'sta-wds'], encryption: W1700K_PMF_ENCRYPTIONS });

						o.defaults = {
							'2': [{ encryption: 'sae' }, { encryption: 'owe' }, { encryption: 'wpa3' }, { encryption: 'wpa3-mixed' }, { encryption: 'wpa3-192' }],
							'1': [{ encryption: 'sae-mixed'}],
							'0': []
						};

						o.validate = function(section_id, value) {
							const modeval = w1700kFormValue(this.section, section_id, 'mode');
							const mlo = w1700kFormValue(this.section, section_id, 'mlo') == '1';
							const devices = w1700kSelectedDevices(this.section, section_id, radioNet.getWifiDeviceName());
							const has6g = devices.some(w1700kDeviceIs6g);
							const hasMloLinks = mlo && devices.length > 1;

							if ((modeval == 'ap' || modeval == 'ap-wds') && (has6g || hasMloLinks) && value != '2')
								return _('6 GHz and MLO APs require management frame protection set to Required.');

							return true;
						};

						o.write = function(section_id, value) {
							const modeval = w1700kFormValue(this.section, section_id, 'mode');
							const uses6gOrMlo = w1700kUses6gOrMlo(this.section, section_id, radioNet.getWifiDeviceName());

							if (w1700kModeIsApLike(modeval) && uses6gOrMlo && value == '2')
								return form.ListValue.prototype.write.call(this, section_id, value);
							else if (value != this.default)
								return form.ListValue.prototype.write.call(this, section_id, value);
							else
								return form.ListValue.prototype.remove.call(this, section_id);
						};

						o.remove = function(section_id) {
							const modeval = w1700kFormValue(this.section, section_id, 'mode');
							const uses6gOrMlo = w1700kUses6gOrMlo(this.section, section_id, radioNet.getWifiDeviceName());

							if (w1700kModeIsApLike(modeval) && uses6gOrMlo)
								return form.ListValue.prototype.write.call(this, section_id, '2');

							return form.ListValue.prototype.remove.call(this, section_id);
						};

						o = ss.taboption('encryption', form.Value, 'ieee80211w_max_timeout', _('802.11w maximum timeout'), _('802.11w Association SA Query maximum timeout'));
						o.depends('ieee80211w', '1');
						o.depends('ieee80211w', '2');
						o.datatype = 'uinteger';
						o.placeholder = '1000';
						o.rmempty = true;

						o = ss.taboption('encryption', form.Value, 'ieee80211w_retry_timeout', _('802.11w retry timeout'), _('802.11w Association SA Query retry timeout'));
						o.depends('ieee80211w', '1');
						o.depends('ieee80211w', '2');
						o.datatype = 'uinteger';
						o.placeholder = '201';
						o.rmempty = true;

						if (L.hasSystemFeature('hostapd', 'ocv') || L.hasSystemFeature('wpasupplicant', 'ocv')) {
							o = ss.taboption('encryption', form.ListValue, 'ocv', _('Operating Channel Validation'), _("Note: Workaround mode allows a STA that claims OCV capability to connect even if the STA doesn't send OCI or negotiate PMF."));
							o.value('0', _('Disabled'));
							o.value('1', _('Enabled'));
							o.value('2', _('Enabled (workaround mode)'));
							o.default = '0';
							o.depends('ieee80211w', '1');
							o.depends('ieee80211w', '2');

							o.validate = function(section_id, value) {
								const modeopt = this.section.children.filter(function(o) { return o.option == 'mode'; })[0];
								const modeval = modeopt.formvalue(section_id);

								if ((value == '2') && ((modeval == 'sta') || (modeval == 'sta-wds'))) {
									return _('Workaround mode can only be used when acting as an access point.');
								}

								return true;
							};
						}

						o = ss.taboption('encryption', form.Flag, 'wpa_disable_eapol_key_retries', _('Enable key reinstallation (KRACK) countermeasures'), _('Complicates key reinstallation attacks on the client side by disabling retransmission of EAPOL-Key frames that are used to install keys. This workaround might cause interoperability issues and reduced robustness of key negotiation especially in environments with heavy traffic load.'));
						add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['psk2', 'psk-mixed', 'sae', 'sae-mixed', 'sae-compat', 'wpa2', 'wpa3', 'wpa3-mixed'] });

						o = ss.taboption('encryption', form.Flag, 'gcmp256', _('GCMP-256 pairwise cipher'), _('Advertise the GCMP-256 pairwise cipher. Mandatory for Wi-Fi 7 (EHT) and recommended otherwise, but some clients and chipsets fail to associate when it is offered. Enabled by default only in Compatibility Mode on a Wi-Fi 7 (EHT) radio, disabled otherwise.'));
						add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['sae', 'sae-mixed', 'sae-compat'] });
						o.updateDefaultValue = eht_compat_default;

						o = ss.taboption('encryption', form.Flag, 'sae_ext_key', _('SAE-EXT-KEY (SAE-GDH)'), _('Advertise the SAE-EXT-KEY AKM (SAE using a group-dependent hash). Mandatory for Wi-Fi 7 (EHT) and recommended otherwise, but some clients misbehave when it is offered, in particular together with 802.11r Fast Transition. Enabled by default only in Compatibility Mode on a Wi-Fi 7 (EHT) radio, disabled otherwise.'));
						add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['sae', 'sae-mixed', 'sae-compat'] });
						o.updateDefaultValue = eht_compat_default;

						o = ss.taboption('encryption', form.Flag, 'transition_disable', _('Transition Disable'), _('Signal Transition Disable (WPA3 Specification v3.5 section 13) so that a client which has connected once no longer downgrades to a weaker security mode for this SSID. The advertised bitmap is derived from the encryption mode.'));
						o.enabled = 'on';
						add_dependency_permutations(o, { mode: ['ap', 'ap-wds'], encryption: ['sae', 'wpa3', 'wpa3-192', 'owe'] });
						o.cfgvalue = function(section_id) {
							const v = L.toArray(uci.get('wireless', section_id, 'transition_disable'))[0];
							return (v && v != 'off' && v != '0') ? 'on' : '0';
						};

						if (L.hasSystemFeature('hostapd', 'wps') && L.hasSystemFeature('wpasupplicant')) {
							o = ss.taboption('encryption', form.Flag, 'wps_pushbutton', _('Enable WPS pushbutton, requires WPA(2)-PSK/WPA3-SAE'));
							o.enabled = '1';
							o.disabled = '0';
							o.default = o.disabled;
							o.depends('encryption', 'psk');
							o.depends('encryption', 'psk2');
							o.depends('encryption', 'psk-mixed');
							o.depends('encryption', 'sae');
							o.depends('encryption', 'sae-mixed');
							o.depends('encryption', 'sae-compat');
						}
					}
				}
			});
		};

		s.handleRemove = function(section_id, ev) {
			document.querySelector('.cbi-section-table-row[data-sid="%s"]'.format(section_id)).style.opacity = 0.5;
			return form.TypedSection.prototype.handleRemove.apply(this, [section_id, ev]);
		};

		s.handleScan = function(radioDev, ev) {
			const table = E('table', { 'class': 'table' }, [
				E('tr', { 'class': 'tr table-titles' }, [
					E('th', { 'class': 'th col-2 middle center' }, _('Signal')),
					E('th', { 'class': 'th col-4 middle left' }, _('SSID')),
					E('th', { 'class': 'th col-2 middle center hide-xs' }, _('Channel')),
					E('th', { 'class': 'th col-2 middle left hide-xs' }, _('Mode')),
					E('th', { 'class': 'th col-3 middle left hide-xs' }, _('BSSID')),
					E('th', { 'class': 'th col-3 middle left' }, _('Encryption')),
					E('th', { 'class': 'th cbi-section-actions right' }, ' '),
				])
			]);

			const stop = E('button', {
				'class': 'btn',
				'click': L.bind(this.handleScanStartStop, this),
				'style': 'display:none',
				'data-state': 'stop'
			}, _('Stop refresh'));

			cbi_update_table(table, [], E('em', { class: 'spinning' }, _('Starting wireless scan...')));

			const md = ui.showModal(_('Join Network: Wireless Scan'), [
				table,
				E('div', { 'class': 'right' }, [
					stop,
					' ',
					E('button', {
						'class': 'btn',
						'click': L.bind(this.handleScanAbort, this)
					}, _('Dismiss'))
				])
			]);

			md.style.maxWidth = '90%';
			md.style.maxHeight = 'none';

			this.pollFn = L.bind(this.handleScanRefresh, this, radioDev, {}, table, stop);

			poll.add(this.pollFn);
			poll.start();
		};

		s.handleScanRefresh = function(radioDev, scanCache, table, stop) {
			return radioDev.getScanList().catch(L.bind(function(err) {
				cbi_update_table(table, [], E('em', _('Wireless scan failed: %s').format(err?.message || err || _('unknown error'))));
				stop.disabled = false;
				stop.style.display = '';
				stop.classList.remove('spinning');
				return [];
			}, this)).then(L.bind(function(results) {
				const rows = [];

				results = results.filter(function(result) {
					return w1700kScanResultMatchesRadio(radioDev, result);
				});

				for (let r of results)
					scanCache[r.bssid] = r;

				for (let k in scanCache) {
					if (!w1700kScanResultMatchesRadio(radioDev, scanCache[k]))
						delete scanCache[k];
					else if (scanCache[k].stale)
						results.push(scanCache[k]);
				}

				results.sort(function(a, b) {
					const diff = (b.quality - a.quality) || (a.channel - b.channel);

					if (diff)
						return diff;

					if (a.ssid < b.ssid)
						return -1;
					else if (a.ssid > b.ssid)
						return 1;

					if (a.bssid < b.bssid)
						return -1;
					else if (a.bssid > b.bssid)
						return 1;
					return 0;
				});

				results.forEach(res => {
					const qv = res?.quality ?? 0;
					const qm = res?.quality_max ?? 0;
					const q = (qv > 0 && qm > 0) ? Math.floor((100 / qm) * qv) : 0;
					const s = res.stale ? 'opacity:0.5' : '';
					const ssid = (typeof res.ssid === 'string' && res.ssid.length > 0) ? document.createTextNode(`${res?.ssid}`) : null;

					rows.push([
						E('span', { 'style': s }, render_signal_badge(q, res?.signal, res?.noise)),
						E('span', { 'style': s }, ssid ?? E('em', _('hidden'))),
						E('span', { 'style': s }, `${res?.channel}`),
						E('span', { 'style': s }, `${res?.mode}`),
						E('span', { 'style': s }, `${res?.bssid}`),
						E('span', { 'style': s }, `${network.formatWifiEncryption(res?.encryption)}`),
						E('div', { 'class': 'right' }, E('button', {
							'class': 'cbi-button cbi-button-action important',
							'click': ui.createHandlerFn(this, 'handleJoin', radioDev, res)
						}, _('Join Network')))
					]);

					res.stale = true;
				});

				cbi_update_table(table, rows);

				stop.disabled = false;
				stop.style.display = '';
				stop.classList.remove('spinning');
			}, this));
		};

		s.handleScanStartStop = function(ev) {
			const btn = ev.currentTarget;

			if (btn.getAttribute('data-state') == 'stop') {
				if (this.pollFn)
					poll.remove(this.pollFn);
				btn.firstChild.data = _('Start refresh');
				btn.setAttribute('data-state', 'start');
			}
			else {
				poll.add(this.pollFn);
				btn.firstChild.data = _('Stop refresh');
				btn.setAttribute('data-state', 'stop');
				btn.classList.add('spinning');
				btn.disabled = true;
			}
		};

		s.handleScanAbort = function(ev) {
			const md = dom.parent(ev.target, 'div[aria-modal="true"]');
			if (md) {
				md.style.maxWidth = '';
				md.style.maxHeight = '';
			}

			ui.hideModal();
			if (this.pollFn)
				poll.remove(this.pollFn);
			this.pollFn = null;
		};

		s.handleJoinConfirm = function(radioDev, bss, form, ev) {
			const nameopt = L.toArray(form.lookupOption('name', '_new_'))[0];
			const passopt = L.toArray(form.lookupOption('password', '_new_'))[0];
			const ssidopt = L.toArray(form.lookupOption('ssid', '_new_'))[0];
			const bssidopt = L.toArray(form.lookupOption('bssid', '_new_'))[0];
			const zoneopt = L.toArray(form.lookupOption('zone', '_new_'))[0];
			const replopt = L.toArray(form.lookupOption('replace', '_new_'))[0];
			const nameval = (nameopt && nameopt.isValid('_new_')) ? nameopt.formvalue('_new_') : null;
			const passval = (passopt && passopt.isValid('_new_')) ? passopt.formvalue('_new_') : null;
			const ssidval = (ssidopt && ssidopt.isValid('_new_')) ? ssidopt.formvalue('_new_') : null;
			const bssidval = (bssidopt && bssidopt.isValid('_new_')) ? bssidopt.formvalue('_new_') : null;
			const zoneval = zoneopt ? zoneopt.formvalue('_new_') : null;
			const enc = L.isObject(bss.encryption) ? bss.encryption : null;
			const is_wep = (enc && Array.isArray(enc.wep));
			const is_psk = (enc && Array.isArray(enc.wpa) && L.toArray(enc.authentication).some(a => a == 'psk'));
			const is_sae = (enc && Array.isArray(enc.wpa) && L.toArray(enc.authentication).some(a => a == 'sae'));
			const htmode = w1700kScanJoinHtmode(
				radioDev, bss, uci.get('wireless', radioDev.getName(), 'htmode'));

			if (nameval == null || (passopt && passval == null) ||
			    ((ssidopt || !bss.ssid) && !w1700kValidSsid(ssidval)))
				return;

			if (w1700kRadioBand(radioDev.getName()) == '6g' &&
			    L.toArray(enc?.ciphers).some(cipher => String(cipher).toLowerCase() == 'tkip')) {
				ui.addNotification(null, E('p', _('TKIP is not valid for 6 GHz.')));
				return;
			}

			if (!htmode) {
				ui.addNotification(null, E('p', _(
					'No regulatory-valid channel width could be selected for channel %s on %s. The wireless configuration was not changed.'
				).format(bss.channel ?? _('unknown'), w1700kRadioLabel(radioDev.getName()))));
				return;
			}

			let section_id = null;

			return this.map.save(function() {
				const wifi_sections = uci.sections('wireless', 'wifi-iface');

				if (replopt.formvalue('_new_') == '1') {
					for (let ws of wifi_sections)
						if (w1700kIfaceConfigUsesRadio(ws, radioDev.getName()))
							uci.remove('wireless', ws['.name']);
				}

				if (uci.get('wireless', radioDev.getName(), 'disabled') == '1') {
					for (let ws of wifi_sections)
						if (w1700kIfaceConfigUsesRadio(ws, radioDev.getName()))
							uci.set('wireless', ws['.name'], 'disabled', '1');

					uci.unset('wireless', radioDev.getName(), 'disabled');
				}

				uci.set('wireless', radioDev.getName(), 'htmode', htmode);
				uci.set('wireless', radioDev.getName(), 'channel', bss.channel);

				section_id = next_free_sid(wifi_sections.length);

				uci.add('wireless', 'wifi-iface', section_id);
				uci.set('wireless', section_id, 'device', radioDev.getName());
				uci.set('wireless', section_id, 'mode', (bss.mode == 'Ad-Hoc') ? 'adhoc' : 'sta');
				uci.set('wireless', section_id, 'network', nameval);

				if (bss.ssid != null) {
					uci.set('wireless', section_id, 'ssid', bss.ssid);

					if (bssidval == '1')
						uci.set('wireless', section_id, 'bssid', bss.bssid);
				}
				else if (bss.bssid != null) {
					uci.set('wireless', section_id, 'bssid', bss.bssid);
				}

				if (ssidval != null)
					uci.set('wireless', section_id, 'ssid', ssidval);

				if (is_sae) {
					uci.set('wireless', section_id, 'encryption', 'sae');
					uci.set('wireless', section_id, 'key', passval);
				}
				else if (is_psk) {
					for (let i = enc.wpa.length - 1; i >= 0; i--) {
						if (enc.wpa[i] == 2) {
							uci.set('wireless', section_id, 'encryption', 'psk2');
							break;
						}
						else if (enc.wpa[i] == 1) {
							uci.set('wireless', section_id, 'encryption', 'psk');
							break;
						}
					}

					uci.set('wireless', section_id, 'key', passval);
				}
				else if (is_wep) {
					uci.set('wireless', section_id, 'encryption', 'wep-open');
					uci.set('wireless', section_id, 'key', '1');
					uci.set('wireless', section_id, 'key1', passval);
				}
				else {
					uci.set('wireless', section_id, 'encryption', 'none');
				}

				return network.addNetwork(nameval, { proto: 'dhcp' }).then(function(net) {
					firewall.deleteNetwork(net.getName());

					const zonePromise = zoneval ?
						firewall.getZone(zoneval).then(function(zone) { return zone || firewall.addZone(zoneval); })
						: Promise.resolve();

					return zonePromise.then(function(zone) {
						if (zone)
							zone.addNetwork(net.getName());
					});
				});
			}).then(L.bind(function() {
				ui.showModal(null, E('p', { 'class': 'spinning' }, [ _('Loading data…') ]));

				return this.renderMoreOptionsModal(section_id);
			}, this));
		};

		s.handleJoin = function(radioDev, bss, ev) {
			if (typeof(bss?.ssid) != 'string' || bss.ssid.length == 0)
				bss = Object.assign({}, bss, { ssid: null });

			if (!w1700kScanResultMatchesRadio(radioDev, bss)) {
				const radioName = radioDev?.getName?.() || _('Selected radio');
				const expected = w1700kRadioInfo(radioName)?.label || _('its configured band');
				const actualBand = w1700kScanResultBand(bss);
				const actual = (actualBand == '2g') ? _('2.4 GHz') :
					(actualBand == '5g') ? _('5 GHz') :
					(actualBand == '6g') ? _('6 GHz') : _('an unknown band');

				ui.addNotification(null, E('p', _('%s is physical %s; it cannot join a %s scan result.').format(radioName, expected, actual)));
				return;
			}

			if (this.pollFn)
				poll.remove(this.pollFn);
			const m2 = new form.Map('wireless');
			const s2 = m2.section(form.NamedSection, '_new_');
			const enc = L.isObject(bss.encryption) ? bss.encryption : null;
			const is_wep = (enc && Array.isArray(enc.wep));
			const is_psk = (enc && Array.isArray(enc.wpa) && L.toArray(enc.authentication).some(a => a == 'psk'  || a == 'sae'));
			let replace, passphrase, name, bssid, zone;

			function nameUsed(name) {
				const s = uci.get('network', name);
				if (s != null && s['.type'] != 'interface')
					return true;

				const net = (s != null) ? network.instantiateNetwork(name) : null;
				return (net != null && !net.isEmpty());
			}

			s2.render = function() {
				return Promise.all([
					{},
					this.renderUCISection('_new_')
				]).then(this.renderContents.bind(this));
			};

			if (bss.ssid == null) {
				name = s2.option(form.Value, 'ssid', _('Network SSID'), _('The correct SSID must be manually specified when joining a hidden wireless network'));
				name.rmempty = false;
				name.validate = function(section_id, value) {
					return w1700kValidSsid(value) || _('SSID must contain between 1 and 32 bytes.');
				};
			}

			replace = s2.option(form.Flag, 'replace', _('Replace wireless configuration'), _('Check this option to delete the existing networks from this radio.'));

			name = s2.option(form.Value, 'name', _('Name of the new network'),
				_('Name for OpenWrt network configuration. (No relation to wireless network name/SSID)') + '<br />' +
				_('The allowed characters are: <code>A-Z</code>, <code>a-z</code>, <code>0-9</code> and <code>_</code>'));
			name.datatype = 'uciname';
			name.default = 'wwan';
			name.rmempty = false;
			name.validate = function(section_id, value) {
				if (nameUsed(value))
					return _('The network name is already used');

				return true;
			};

			for (let i = 2; nameUsed(name.default); i++)
				name.default = 'wwan%d'.format(i);

			if (is_wep || is_psk) {
				passphrase = s2.option(form.Value, 'password', is_wep ? _('WEP passphrase') : _('WPA passphrase'), _('Specify the secret encryption key here.'));
				passphrase.datatype = is_wep ? 'wepkey' : 'wpakey';
				passphrase.password = true;
				passphrase.rmempty = false;
			}

			if (bss.ssid != null) {
				bssid = s2.option(form.Flag, 'bssid', _('Lock to BSSID'), _('Instead of joining any network with a matching SSID, only connect to the BSSID <code>%h</code>.').format(bss.bssid));
				bssid.default = '0';
			}

			zone = s2.option(widgets.ZoneSelect, 'zone', _('Create / Assign firewall-zone'), _('Choose the firewall zone you want to assign to this interface. Select <em>unspecified</em> to remove the interface from the associated zone or fill out the <em>custom</em> field to define a new zone and attach the interface to it.'));
			zone.default = 'wan';

			return m2.render().then(L.bind(function(nodes) {
				ui.showModal(_('Joining Network: %q').replace(/%q/, '"%h"'.format(bss.ssid)), [
					nodes,
					E('div', { 'class': 'right' }, [
						E('button', {
							'class': 'btn',
							'click': ui.hideModal
						}, _('Cancel')), ' ',
						E('button', {
							'class': 'cbi-button cbi-button-positive important',
							'click': ui.createHandlerFn(this, 'handleJoinConfirm', radioDev, bss, m2)
						}, _('Submit'))
					])
				], 'cbi-modal').querySelector('[id="%s"] input[class][type]'.format((passphrase || name).cbid('_new_'))).focus();
			}, this));
		};

		s.handleAdd = function(radioDev, ev) {
			const section_id = next_free_sid(uci.sections('wireless', 'wifi-iface').length);

			uci.unset('wireless', radioDev.getName(), 'disabled');

			uci.add('wireless', 'wifi-iface', section_id);
			uci.set('wireless', section_id, 'device', radioDev.getName());
			uci.set('wireless', section_id, 'mode', 'ap');
			uci.set('wireless', section_id, 'ssid', 'OpenWrt');
			uci.set('wireless', section_id, 'encryption', 'none');

			m.addedSection = section_id;
			return this.renderMoreOptionsModal(section_id);
		};

		s.handleAddMlo = function(radioDev, ev) {
			const owner = w1700kMloRadioOwner(null, radioDev.getName());
			const section_id = next_free_sid(uci.sections('wireless', 'wifi-iface').length);
			const devices = w1700kAvailableMloDevices(section_id, radioDev.getName());

			if (owner)
				return this.renderMoreOptionsModal(owner['.name']);

			if (devices.length < 2) {
				ui.addNotification(null, E('p', _('At least two unassigned radios are required for a new MLO network.')));
				return;
			}

			devices.forEach(function(dev) {
				uci.unset('wireless', dev, 'disabled');
			});

			uci.add('wireless', 'wifi-iface', section_id);
			uci.set('wireless', section_id, 'device', devices);
			uci.set('wireless', section_id, 'mode', 'ap');
			uci.set('wireless', section_id, 'network', 'lan');
			uci.set('wireless', section_id, 'ssid', 'OpenWrt MLO');
			uci.set('wireless', section_id, 'encryption', 'sae');
			uci.set('wireless', section_id, 'mlo', '1');
			uci.set('wireless', section_id, 'ieee80211w', '2');
			uci.set('wireless', section_id, 'rnr', '1');
			uci.set('wireless', section_id, 'sae_pwe', '2');
			w1700kEnsureMloRadioDefaults(devices);

			m.addedSection = section_id;
			return this.renderMoreOptionsModal(section_id).then(function(result) {
				w1700kSelectVisibleModalTab('encryption');

				const key = Array.from(document.querySelectorAll('[data-name="key"] input'))
					.find(function(input) { return input.offsetParent != null; });

				if (key)
					key.focus();

				return result;
			});
		};

		o = s.option(form.DummyValue, '_badge');
		o.modalonly = false;
		o.textvalue = function(section_id) {
			const inst = this.section.lookupRadioOrNetwork(section_id);
			const node = E('div', { 'class': 'center' });

			if (inst.getWifiNetworks)
				node.appendChild(render_radio_badge(inst));
			else
				node.appendChild(render_network_badge(inst));

			return node;
		};

		o = s.option(form.DummyValue, '_stat');
		o.modalonly = false;
		o.textvalue = function(section_id) {
			const inst = this.section.lookupRadioOrNetwork(section_id);

				if (inst.getWifiNetworks)
					return render_radio_status(inst, this.section.wifis.filter(function(e) {
						return w1700kWifiUsesRadio(e, inst.getName());
					}));
			else
				return render_network_status(inst);
		};

		return m.render().then(L.bind(function(m, nodes) {
			poll.add(L.bind(function() {
				const tasks = [ network.getHostHints(), network.getWifiDevices() ];

				m?.children[0]?.cfgsections?.().forEach(s => {
					const row = nodes.querySelector('.cbi-section-table-row[data-sid="%s"]'.format(s));
					const dsc = row.querySelector('[data-name="_stat"] > div');
					const btns = row.querySelectorAll('.cbi-section-actions button');

					if (dsc.getAttribute('restart') == '') {
						dsc.setAttribute('restart', '1');
						tasks.push(fs.exec('/sbin/wifi', ['up', s]).catch(function(e) {
							ui.addNotification(null, E('p', e.message));
						}));
					}
					else if (dsc.getAttribute('restart') == '1') {
						dsc.removeAttribute('restart');
						btns[0].classList.remove('spinning');
						btns[0].disabled = false;
					}
				});

				return Promise.all(tasks)
					.then(L.bind(function(hosts_radios) {
						const tasks = [];

						hosts_radios[1].forEach(r => tasks.push(r.getWifiNetworks()) );

						return Promise.all(tasks).then(function(data) {
							const wifis = [];

							for (let d of data)
								wifis.push.apply(wifis, d);
							hosts_radios[2] = w1700kUniqueWifiNetworks(wifis);

							return hosts_radios;
						});
					}, network))
					.then(L.bind(function(hosts_radios_wifis) {
						const tasks = [];

						hosts_radios_wifis[2].forEach(hrw => tasks.push(hrw.getAssocList()) );

						return Promise.all(tasks).then(function(data) {
							hosts_radios_wifis[3] = [];

							for (let i = 0; i < data.length; i++) {
								const wifiNetwork = hosts_radios_wifis[2][i];
								const primaryRadio = w1700kWifiPrimaryRadio(wifiNetwork);
								const radioDev = hosts_radios_wifis[1].filter(function(d) { return d.getName() == primaryRadio; })[0] ||
									hosts_radios_wifis[1].filter(function(d) { return w1700kWifiUsesRadio(wifiNetwork, d.getName()); })[0];

								for (let dy of data[i])
									hosts_radios_wifis[3].push(Object.assign({ radio: radioDev, network: wifiNetwork }, dy));
							}

							return hosts_radios_wifis;
						});
					}, network))
					.then(L.bind(function(zones, data) {
						data.push(zones);
						return data;
					}, network, zones))
					.then(L.bind(this.poll_status, this, nodes));
			}, this), 5);

			const table = E('table', { 'class': 'table assoclist', 'id': 'wifi_assoclist_table' }, [
				E('tr', { 'class': 'tr table-titles' }, [
					E('th', { 'class': 'th nowrap' }, _('Network')),
					E('th', { 'class': 'th hide-xs' }, _('MAC address')),
					E('th', { 'class': 'th' }, _('Host')),
					E('th', { 'class': 'th' }, _('Signal / Noise')),
					E('th', { 'class': 'th' }, _('RX Rate / TX Rate'))
				])
			]);

			cbi_update_table(table, [], E('em', { 'class': 'spinning' }, _('Collecting data...')));

			return E([ nodes, E('h3', _('Associated Stations')), table ]);
		}, this, m));
	},

	handleReset: null
});
