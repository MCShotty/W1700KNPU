import { sha256 } from 'digest';

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

export function mld_config_id(config) {
	let common = { ...config };
	// netifd adds these descriptor fields and assigns ifname/MAC per link.
	for (let field in [ 'phy', 'radio_config', '4addr', 'ifname', 'macaddr' ])
		delete common[field];
	return sha256(sprintf('%J', canonical(common)));
}
