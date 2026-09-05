'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const sourceRoot = process.argv[2];
assert(sourceRoot, 'usage: node mlo-country-alias.test.js SOURCE_ROOT');

const hostapdPath = path.join(
	sourceRoot,
	'package/network/config/wifi-scripts/files-ucode/usr/share/ucode/wifi/hostapd.uc'
);
const mac80211Path = path.join(
	sourceRoot,
	'package/network/config/wifi-scripts/files-ucode/lib/netifd/wireless/mac80211.sh'
);
const schemaPath = path.join(
	sourceRoot,
	'package/network/config/wifi-scripts/files-ucode/usr/share/schema/wireless.wifi-device.json'
);
const wirelessViewPath = path.join(
	sourceRoot,
	'feeds/luci/modules/luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js'
);
const validatorPath = path.join(
	sourceRoot,
	'target/linux/airoha/an7581/base-files/usr/sbin/w1700k-wireless-validate'
);
const sanityPath = path.join(
	sourceRoot,
	'target/linux/airoha/an7581/base-files/usr/sbin/w1700k-radio-sanity'
);

const hostapd = fs.readFileSync(hostapdPath, 'utf8');
const mac80211 = fs.readFileSync(mac80211Path, 'utf8');
const schema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
const wirelessView = fs.readFileSync(wirelessViewPath, 'utf8');
const validator = fs.readFileSync(validatorPath, 'utf8');
const sanity = fs.readFileSync(sanityPath, 'utf8');
const match = hostapd.match(/function mlo_country\(config\)\s*\{([\s\S]*?)\n\}/);

assert(match, 'mlo_country() is missing');
const mloCountry = new Function(
	'uc',
	`return function mlo_country(config) {${match[1]}\n};`
)(value => String(value).toUpperCase());

assert.strictEqual(mloCountry({ country: 'us' }), 'US');
assert.strictEqual(mloCountry({ country_code: 'us' }), 'US');
assert.strictEqual(mloCountry({ country: 'us', country_code: 'sa' }), 'SA');
assert.strictEqual(mloCountry({ country: '00' }), null);
assert.strictEqual(mloCountry({ country_code: '00' }), null);
assert.strictEqual(mloCountry({}), null);

assert.strictEqual(schema.properties.country.type, 'alias');
assert.strictEqual(schema.properties.country.default, 'country_code');
assert(
	mac80211.indexOf("validate('device', config);") < mac80211.indexOf('hostapd.setup(data);'),
	'device alias conversion must remain before hostapd setup for this regression contract'
);
assert(
	hostapd.includes("mlo_radio_index(config.radio) == 0 && config.htmode != 'EHT20'"),
	'hostapd must reject unreliable 2.4GHz EHT40 MLO after alias validation'
);
assert(
	wirelessView.includes("'0': { channel: '6', htmodes: [ 'EHT20' ] }") &&
		wirelessView.includes("w1700kRadioIndex(dev) != '0' || htmode == 'EHT20'"),
	'LuCI must choose and enforce the reliable 2.4GHz MLO width'
);
assert(
	validator.includes('MLO requires EHT20 on 2.4GHz radio $dev') &&
		sanity.includes('set_if_diff wireless."$dev".htmode EHT20'),
	'backend validation and boot repair must share the 2.4GHz MLO width contract'
);

console.log('PASS hostapd MLO country alias and 2.4GHz coexistence contracts');
