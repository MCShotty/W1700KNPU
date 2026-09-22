#!/usr/bin/env python3
"""Extract the real security options/default handlers for isolated browser QA."""
import argparse
import hashlib
import json
from pathlib import Path

from test_frequency_consumers import function

ROOT = Path(__file__).resolve().parents[2]
LUCI = ROOT / '.build/openwrt/feeds/luci'
WIRELESS = Path('modules/luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js')
FORM = LUCI / 'modules/luci-base/htdocs/luci-static/resources/form.js'


def program(source):
    form = FORM.read_text()
    start = form.index('\tupdateDefaultValue(section_id) {')
    end = form.index('\n\t},', start) + 3
    method = form[start:end].replace('\tupdateDefaultValue', 'function updateDefaultValue', 1)
    common = '\n'.join(function(source, name) for name in
                       ['w1700kFormValue', 'eht_compat_default', 'add_dependency_permutations'])
    start = source.index("o = ss.taboption('encryption', form.Flag, 'gcmp256'")
    end = source.index("o = ss.taboption('encryption', form.Flag, 'transition_disable'", start)
    options = 'function buildOptions(ss) { let o;\n' + source[start:end] + '\n}'
    return method + '\n' + common + '\n' + options


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    source = (LUCI / WIRELESS).read_text()
    payload = dict(current=program(source), before=program(args.before.read_text()),
                   source_sha256=hashlib.sha256((LUCI / WIRELESS).read_bytes()).hexdigest(),
                   form_sha256=hashlib.sha256(FORM.read_bytes()).hexdigest())
    args.out.write_text(json.dumps(payload, indent=2) + '\n')
    print(args.out)


if __name__ == '__main__':
    main()
