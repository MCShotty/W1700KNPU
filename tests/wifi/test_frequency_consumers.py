#!/usr/bin/env python3
"""Offline actual-source LuCI frequency regressions; no browser/router proof."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
OPENWRT = ROOT / ".build/openwrt"
LUCI = OPENWRT / "feeds/luci"
NETWORK = "modules/luci-base/htdocs/luci-static/resources/network.js"
WIRELESS = "modules/luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js"
STATUS = "modules/luci-mod-status/htdocs/luci-static/resources/view/status/include/60_wifi.js"
SBIN = "target/linux/airoha/an7581/base-files/usr/sbin/"
SELECTED = {"openwrt": [SBIN + "w1700k-radio-sanity", SBIN + "w1700k-wifi-capabilities"],
            "luci": [NETWORK, WIRELESS, STATUS]}
REQUIRE_SOURCE_LOCK = False


def function(source, name):
    match = re.search(r"^function " + re.escape(name) + r"\([^\n]*\) \{\n.*?^\}",
                      source, re.M | re.S)
    if not match:
        raise AssertionError(f"Missing source function: {name}")
    return match[0]


def source_program(wireless=None):
    """Return an async JS function body accepting the test framework's assert object."""
    wireless = wireless if wireless is not None else (LUCI / WIRELESS).read_text()
    network = (LUCI / NETWORK).read_text()
    status = (LUCI / STATUS).read_text()
    functions = [
        "w1700kExplicitRadioIndex", "w1700kRadioMapActive", "w1700kRadioIndex",
        "w1700kRadioIndexOwners", "w1700kRadioInfo", "w1700kRadioBand",
        "w1700kNormalizeCountry", "w1700kDeviceCountry", "w1700kChannelAllowed",
        "w1700kRuntimeChannelAllowed", "w1700kDeviceNames", "w1700kLoadMloApChannels",
        "w1700kStaticApChannels", "w1700kApChannelsForBand", "w1700kHtmodeAllowed",
        "w1700kHtmodeWidth", "w1700kChannelsUsable", "w1700kRunWidthBlock",
        "w1700k5gWidthBlock", "w1700k6gWidthBlock", "w1700kChannelValuesForHtmode",
        "w1700kApChannelsFromFrequencyList", "w1700kFrequencyMatchesBand",
        "w1700kScanResultFrequencyGHz", "w1700kScanResultBand",
        "w1700kScanResultMatchesRadio", "w1700kChannelFrequencyGHz",
        "w1700kRadioRuntimeFacts",
    ]
    # Execute original consumer functions. Only UCI/RPC/form framework inputs are modeled.
    program = r"""
const config = {
  radio0: { radio: '0', band: '2g', country: 'US' },
  radio1: { radio: '1', band: '5g', country: 'US' },
  radio2: { radio: '2', band: '6g', country: 'US' }
};
const uci = {
  get: (_c, section, key) => config[section]?.[key],
  sections: () => Object.entries(config).map(([name, value]) => ({ '.name': name, ...value }))
};
let rpcRows = [];
const requests = [];
const callIwinfoFrequencyList = async device => {
  requests.push(device);
  if (rpcRows instanceof Error) throw rpcRows;
  return rpcRows;
};
const L = { toArray: value => value == null ? [] : (Array.isArray(value) ? value : [value]),
  hasSystemFeature: () => true, bind: (fn, self) => fn.bind(self),
  resolveDefault: (promise, fallback) => Promise.resolve(promise).catch(() => fallback) };
String.prototype.format = function(...args) {
  let index = 0;
  return this.replace(/%[ds]/g, () => String(args[index++]));
};
"""
    for name in ("W1700K_RADIO_INFO", "W1700K_5G_STATIC_AP_CHANNELS", "W1700K_5G_CHANNEL_RUNS"):
        match = re.search(r"^const " + name + r" = .*?^\s*[}\]];", wireless, re.M | re.S)
        if not match:
            raise AssertionError(f"Missing source constant: {name}")
        program += match[0] + "\n"
    program += "\n".join(function(wireless, name) for name in functions)
    program += "\n" + "\n".join(function(network, name) for name in (
        "wifiFrequencyFromChannel", "wifiFrequencyMatchesBand", "wifiChannelMatchesBand",
        "wifiRuntimeChannelFacts"))
    program += "\nconst status = new Function('baseclass', 'uci', 'L', '_', 'rpc', "
    program += json.dumps(status) + ")( { extend: value => value }, uci, L, value => value, { declare: () => null } );\n"
    start = wireless.index("var CBIWifiFrequencyValue = form.Value.extend({")
    end = wireless.index("\n\t// Set values in the select element", start)
    widget = wireless[start:end] + "\n});"
    program += "\nconst form = { Value: { extend: value => value } };\n"
    program += "const network = { getWifiDevice: async () => ({ getHWModes: () => ['a', 'n', 'ac', 'ax', 'be'], getHTModes: () => ['HT20', 'VHT80', 'HE20', 'EHT20', 'EHT80'] }) };\n"
    program += widget
    program += r"""
return (async () => {
  const row = { band: 5, channel: 161, mhz: 5805, restricted: true, flags: ['no_ir'] };
  const upper = { ...row, flags: ['NO_IR'] };
  const valid = { ...row, restricted: false, flags: [] };
  const extended = { band: 5, channel: 169, mhz: 5845, restricted: false, flags: [] };
  const allowed = input => w1700kApChannelsFromFrequencyList('radio1', [input])['5g'][input.channel] === true;
  const load = async (section, rows) => {
    rpcRows = rows;
    const widget = Object.create(CBIWifiFrequencyValue);
    await widget.load(section);
    return widget;
  };
  const widget = await load('radio1', [row, extended]);
  const cases = {};
  const check = async (name, section, input) => {
    const loaded = await load(section, [input]);
    const band = String(input.band) + 'g';
    const maps = await w1700kLoadMloApChannels([section]);
    const choices = loaded.channels[band] || [];
    const offset = choices.findIndex((value, index) => index % 3 === 0 && value === input.channel);
    cases[name] = {
      mlo: maps[section]?.[band]?.[input.channel] === true,
      widget: loaded.apChannels[band]?.[input.channel] === true,
      metadata: offset < 0 ? null : choices[offset + 2],
      auto: choices[0] === 'auto' && choices[2].available
    };
  };
  for (const flags of [['no_ir'], ['NO_IR'], ['No_Ir']])
    await check(flags[0], 'radio1', { ...row, flags });
  await check('explicit-no-ir', 'radio1', { ...row, flags: [], no_ir: true });
  await check('no-ir-unrestricted', 'radio1', { ...row, restricted: false });
  await check('restricted-only', 'radio1', { ...valid, restricted: true });
  await check('disabled', 'radio1', { ...extended, disabled: true });
  await check('runtime169', 'radio1', extended);
  await check('runtime177', 'radio1', { ...extended, channel: 177, mhz: 5885 });
  await check('dfs', 'radio1', { band: 5, channel: 100, mhz: 5500, restricted: false, flags: ['no_ht40minus'] });
  await check('indoor', 'radio1', { ...valid, flags: ['indoor_only'], no_outdoor: true });
  await check('non-array-flags', 'radio1', { ...valid, flags: null });
  for (const channel of [0, -1, 35, 37, 148, 150, 170, 181, 161.5, '', 'auto', 'bad', null])
    await check('bad-5g-' + JSON.stringify(channel), 'radio1', { ...valid, channel });
  for (const channel of [0, 3, 232, 234, 237, 5.5])
    await check('bad-6g-' + channel, 'radio2', { band: 6, channel, mhz: 5975, restricted: false, flags: [] });
  for (const channel of [2, 1, 5, 233])
    await check('good-6g-' + channel, 'radio2', { band: 6, channel,
      mhz: channel === 2 ? 5935 : 5950 + 5 * channel, restricted: false, flags: [] });
  for (const channel of [1, 11, 12, 13, 14, 15])
    await check('2g-' + channel, 'radio0', { band: 2, channel,
      mhz: channel === 14 ? 2484 : 2407 + 5 * channel, restricted: false, flags: [] });
  for (const band of [2, 6, 60, 4, null])
    await check('foreign-' + band, 'radio1', { ...valid, band });
  await check('unmapped', 'missing', valid);
  config.duplicate = { radio: '1', band: '5g', country: 'US' };
  await check('duplicate', 'radio1', valid);
  delete config.duplicate;
  config.renamed = config.radio1;
  delete config.radio1;
  await check('renamed', 'renamed', valid);
  config.radio1 = config.renamed;
  delete config.renamed;

  const fallback = {};
  for (const [name, rows] of [['empty', []], ['missing', null], ['error', new Error('fixture RPC failure')]]) {
    rpcRows = rows;
    const maps = await w1700kLoadMloApChannels('radio1');
    fallback[name] = [maps.radio1, w1700kChannelAllowed('radio1', 161, maps.radio1),
      w1700kChannelAllowed('radio1', 169, maps.radio1)];
    if (name === 'empty') {
      const empty = await load('radio1', rows);
      assert.deepEqual(empty.apChannels['5g'], {});
      assert.equal(empty.channels['5g'][2].available, false);
    } else {
      await assert.rejects(load('radio1', rows));
    }
  }
  rpcRows = [row];
  const rejected = (await w1700kLoadMloApChannels('radio1')).radio1;
  fallback.rejected = [w1700kChannelAllowed('radio1', 161, rejected),
    w1700kChannelAllowed('radio1', 'auto', rejected),
    Object.keys(w1700kApChannelsForBand('5g', rejected)).length];
  fallback.static = [w1700kChannelAllowed('radio1', 161), w1700kChannelAllowed('radio1', 169),
    !!w1700kStaticApChannels('5g')[169]];
  fallback.country = {};
  for (const country of ['US', 'CA', 'MX', 'DE', 'JP']) {
    config.radio0.country = country;
    fallback.country[country] = [11, 12, 13, 14].map(ch => w1700kChannelAllowed('radio0', ch));
  }
  config.radio0.country = 'US';
  const fullRows = [165, 169, 173, 177].map(channel => ({ ...valid, channel, mhz: 5000 + channel * 5 }));
  const widths = {};
  for (const [name, rows] of [['full', fullRows], ['missing', fullRows.slice(0, 3)],
    ['no-ir', fullRows.map(input => input.channel === 173 ? { ...input, restricted: true, flags: ['no_ir'] } : input)]]) {
    const loaded = await load('radio1', rows);
    widths[name] = [w1700kChannelAllowed('radio1', 169, loaded.apChannels),
      w1700kHtmodeAllowed('radio1', 'EHT80', 169, loaded.apChannels),
      w1700kChannelValuesForHtmode('radio1', loaded.channels['5g'], 'EHT80', loaded.apChannels)
        .filter((value, index) => index % 3 === 2).some(meta => meta.available)];
  }
  const samples = {};
  const decimal = ['5805.0', 5805, 5.805];
  for (const value of decimal) {
    const sample = { channel: 161, frequency: value, bitrate: 100000 };
    const radio = { getName: () => 'radio1', isUp: () => true, ubus: () => sample };
    samples[value] = [w1700kRadioRuntimeFacts(radio, []).frequency,
                      status.radioRuntimeFacts(radio, []).frequency];
    assert.equal(w1700kScanResultBand({ mhz: value }), '5g');
    assert.equal(w1700kScanResultMatchesRadio({ getName: () => 'radio2' }, { mhz: value }), false);
    const wrapped = { getRadioConfig: () => '5g', isMultiRadio: () => true,
      ubus: (scope, key, field) => key === 'up' ? true : sample[field] };
    assert.equal(wifiRuntimeChannelFacts(wrapped).frequency, 5805);
    const wrong = { ...radio, getName: () => 'radio2' };
    assert.equal(w1700kRadioRuntimeFacts(wrong, []).frequency, null);
    assert.equal(status.radioRuntimeFacts(wrong, []).frequency, null);
    assert.equal(wifiRuntimeChannelFacts({ ...wrapped, getRadioConfig: () => '6g' }).frequency, null);
  }
  return {
    lowerNoIrAccepted: allowed(row), upperNoIrAccepted: allowed(upper),
    explicitNoIrAccepted: allowed({ ...row, no_ir: true }),
    validAccepted: allowed(valid), disabledAccepted: allowed({ ...valid, disabled: true }),
    foreignBandAccepted: Object.keys(w1700kApChannelsFromFrequencyList('radio2', [valid])['5g']).length > 0,
    extendedChannelAccepted: allowed(extended),
    widgetLowerNoIrAccepted: widget.apChannels['5g'][161] === true,
    widgetExtendedChannelAccepted: widget.apChannels['5g'][169] === true,
    cases, fallback, widths, requests,
    decimals: samples
  };
})();
"""
    return program


def source_facts(wireless=None):
    program = "const run = new Function('assert', " + json.dumps(source_program(wireless)) + ");\n"
    program += "run(require('node:assert/strict')).then(facts => console.log(JSON.stringify(facts)))"
    program += ".catch(error => { console.error(error); process.exitCode = 1; });\n"
    result = subprocess.run(["node", "-"], input=program, text=True, cwd=ROOT,
                            capture_output=True, timeout=20)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class FrequencyConsumers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = source_facts()
        print(f"Actual-source fixtures: {len(cls.facts['cases'])} row cases; "
              f"{len(cls.facts['requests'])} modeled RPC calls")

    def test_unchanged_selected_source_lock_hashes(self):
        lock = json.loads((ROOT / "firmware/source-lock.json").read_text())
        for tree, paths in SELECTED.items():
            hashes = {entry["path"]: entry["sha256"] for entry in lock[tree]["changed_files"]}
            for path in paths:
                # Parent owns the lock refresh for this unpromoted wireless candidate.
                if tree == "luci" and path == WIRELESS and not REQUIRE_SOURCE_LOCK:
                    continue
                with self.subTest(path=path):
                    actual = ((OPENWRT if tree == "openwrt" else LUCI) / path).read_bytes()
                    self.assertEqual(hashlib.sha256(actual).hexdigest(), hashes[path])

    def test_selected_patch_hunks_match_prepared_source(self):
        for tree, paths in SELECTED.items():
            patch = (ROOT / f"firmware/patches/{tree}.patch").read_text()
            checked = set()
            for section in re.split(r"(?=^diff --git )", patch, flags=re.M):
                header = re.match(r"diff --git a/(.*?) b/(.*?)\n", section)
                if not header or header[2] not in paths:
                    continue
                path = header[2]
                lines = ((OPENWRT if tree == "openwrt" else LUCI) / path).read_text().splitlines()
                new_line = None
                for line in section.splitlines():
                    hunk = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                    if hunk:
                        new_line = int(hunk[1]) - 1
                    elif new_line is not None and line.startswith(("+", " ")):
                        self.assertEqual(line[1:], lines[new_line], f"{path}:{new_line + 1}")
                        new_line += 1
                checked.add(path)
            self.assertEqual(checked, set(paths))

    def test_decimal_and_cross_radio_controls(self):
        self.assertEqual(len(self.facts["decimals"]), 3)
        for values in self.facts["decimals"].values():
            self.assertEqual(values, [5.805, 5.805])
        self.assertFalse(self.facts["foreignBandAccepted"])

    def test_unrestricted_disabled_and_uppercase_controls(self):
        self.assertTrue(self.facts["validAccepted"])
        for key in ("disabledAccepted", "upperNoIrAccepted", "explicitNoIrAccepted",
                    "widgetLowerNoIrAccepted"):
            self.assertFalse(self.facts[key], key)

    def test_mlo_rejects_rpc_lowercase_no_ir(self):
        self.assertFalse(self.facts["lowerNoIrAccepted"])

    def test_runtime_permitted_extended_channel_survives_static_fallback(self):
        self.assertTrue(self.facts["extendedChannelAccepted"])
        self.assertTrue(self.facts["widgetExtendedChannelAccepted"])

    def test_row_guards_and_dfs_metadata(self):
        accepted = {"runtime169", "runtime177", "dfs", "indoor", "non-array-flags",
                    "restricted-only", "renamed", "2g-1", "2g-11", "2g-12", "2g-13", "2g-14",
                    "good-6g-2", "good-6g-1", "good-6g-5", "good-6g-233"}
        for name, result in self.facts["cases"].items():
            with self.subTest(case=name):
                self.assertEqual(result["mlo"], name in accepted)
                # Preserve the widget's preexisting restricted && no_ir predicate.
                self.assertEqual(result["widget"], name in accepted or name == "no-ir-unrestricted")
                self.assertEqual(bool(result["auto"]), result["widget"])
                if result["metadata"] is not None:
                    self.assertEqual(result["metadata"]["available"], result["widget"])
        self.assertTrue(self.facts["cases"]["no_ir"]["metadata"]["no_ir"])
        self.assertFalse(self.facts["cases"]["dfs"]["metadata"]["no_ir"])
        self.assertTrue(self.facts["cases"]["indoor"]["metadata"]["no_outdoor"])

    def test_runtime_empty_failure_and_country_fallbacks(self):
        for name in ("empty", "missing", "error"):
            self.assertEqual(self.facts["fallback"][name], [None, True, False])
        self.assertEqual(self.facts["fallback"]["rejected"], [False, False, 0])
        self.assertEqual(self.facts["fallback"]["static"], [True, False, False])
        for country in ("US", "CA", "MX"):
            self.assertEqual(self.facts["fallback"]["country"][country], [True, False, False, False])
        self.assertEqual(self.facts["fallback"]["country"]["DE"], [True, True, True, False])
        self.assertEqual(self.facts["fallback"]["country"]["JP"], [True, True, True, True])
        self.assertIn("renamed", self.facts["requests"])

    def test_width_requires_all_runtime_subchannels(self):
        self.assertEqual(self.facts["widths"]["full"], [True, True, True])
        for name in ("missing", "no-ir"):
            self.assertEqual(self.facts["widths"][name], [True, False, False])

    def test_each_correction_is_required(self):
        source = (LUCI / WIRELESS).read_text()
        mutants = [
            ("const noIr = freq.no_ir || flags.some(flag => String(flag).toLowerCase() == 'no_ir')",
             "const noIr = freq.no_ir || flags.indexOf('NO_IR') >= 0", "lowerNoIrAccepted", True),
            ("!noIr && w1700kRuntimeChannelAllowed(section_id, freq.channel)",
             "!noIr && w1700kChannelAllowed(section_id, freq.channel)", "extendedChannelAccepted", False),
            ("\t\t\t\t\tw1700kRuntimeChannelAllowed(section_id, freq.channel)",
             "\t\t\t\t\tw1700kChannelAllowed(section_id, freq.channel)", "widgetExtendedChannelAccepted", False),
        ]
        for before, after, fact, expected in mutants:
            with self.subTest(mutant=fact):
                self.assertEqual(source.count(before), 1)
                self.assertEqual(source_facts(source.replace(before, after))[fact], expected)
                self.assertNotEqual(self.facts[fact], expected)

    def test_exact_wireless_patch_reconstruction(self):
        lock = json.loads((ROOT / "firmware/source-lock.json").read_text())
        base = lock["luci"]["base"]
        patch = (ROOT / "firmware/patches/luci.patch").read_bytes()
        sections = re.split(rb"(?=^diff --git )", patch, flags=re.M)
        selected = [section for section in sections if section.startswith(
            f"diff --git a/{WIRELESS} b/{WIRELESS}\n".encode())]
        self.assertEqual(len(selected), 1)
        original = subprocess.check_output(["git", "show", f"{base}:{WIRELESS}"], cwd=LUCI)
        fd = os.memfd_create("frequency-luci-base")
        try:
            with os.fdopen(os.dup(fd), "wb") as stream:
                stream.write(original)
            result = subprocess.run(["patch", "--silent", "--fuzz=0", "--follow-symlinks", "--no-backup-if-mismatch",
                                     "--reject-file=-", "--output=-", f"/proc/self/fd/{fd}"],
                                    input=selected[0], capture_output=True, pass_fds=(fd,), timeout=20)
        finally:
            os.close(fd)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, (LUCI / WIRELESS).read_bytes())
        subprocess.run(["git", "apply", "--reverse", "--check", "-"], input=selected[0],
                       cwd=LUCI, check=True, capture_output=True, timeout=20)


if __name__ == "__main__":
    if sys.argv[1:] == ["--emit-js"]:
        print(source_program())
    else:
        if "--require-source-lock" in sys.argv:
            sys.argv.remove("--require-source-lock")
            REQUIRE_SOURCE_LOCK = True
        unittest.main(verbosity=2)
