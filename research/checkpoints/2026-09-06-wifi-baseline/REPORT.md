# Read-Only Wi-Fi Baseline

2026-09-06, 07:23:05 to 07:25:38 UTC. Expected W1700K identity and R1 revision
were verified through the existing Ethernet-bound, host-key-pinned SSH route.
WLAN NPU remains compiled out and detached from mt76.

## Current AP Prerequisite Is Missing

- UCI contains three `wifi-device` sections and zero `wifi-iface` or `wifi-mld`
  sections. No Wi-Fi network is currently configured.
- All three radios report `up=true`, but every runtime interface list is empty.
- The global hostapd ubus object exists; `hostapd status` reports an empty
  `interfaces` object and no per-BSS ubus object exists.
- This changes the next action: establish the user's intended AP configuration
  before client reproduction. Radio-level `up` alone did not prove an AP was
  available. The current empty configuration does not identify the cause of
  the earlier iPhone/laptop failures or establish when/why networks were removed.

The user was asked which network configuration to restore, and which current
client/band/symptom reproduces. No network was created, restored or enabled.
The configured SA/channel161 value remains parked, not approved for activation.
No regulatory, transmit-power, association, module, image, flash or raw-MMIO
change was made. Captures are separate snapshots, not atomic state.

`router-observation.json` records sanitized observations from direct commands.
It contains no SSIDs, passphrases, station identifiers or raw device backup.
Hostapd process presence is not beacon, association or traffic proof.

## Collector Candidate

`tools/router/read_wifi_baseline.ps1` adds structured, read-only collection and
separates empty configuration, missing hostapd interfaces, stale runtime/config
mismatch and unvalidated hostapd presence. It allowlists public status fields;
credential-bearing UCI data is not exported. It is designed to reject identity mismatch,
missing/malformed response shapes, a missing Ethernet source, unpinned SSH,
output outside the canonical repository and overwriting an earlier capture.

`tests/router/test_wifi_baseline.ps1` defines five nominal fixtures and ten
rejection controls, including radio-up without any AP and private-data
sentinels. Both scripts parse with zero PowerShell syntax errors. **They have
not executed:** Windows `RemoteSigned` blocked the unsigned test script on the
WSL UNC share. No execution-policy setting was changed and no alternate route
was used to run the scripts. A process-only override for these two scripts was
requested from the user; approval is pending. The direct live observations
above do not validate this collector or its fixtures.

Candidate hashes: collector
`51b999b1abf48ad19fea0f85f6c1467ddb312c8e4e627138d75c11969e0a6fdb`;
fixture test `e1b5ae705dd0fbcf4959ca3a753177a8c6cbf162dbb21fdad7258b9d0605c677`.

## Supplemental Readbacks

The current kernel reports country SA/DFS-ETSI, with its highest 5 GHz rule
ending at 5710 MHz. This is kernel regulatory state, not legal advice or
authorization to activate any parked channel. No regulatory setting changed.

Sysfs shows `mt7996e` bound to `0000:01:00.0` and `mt7996e_hif` bound to
`0002:01:00.0`. This does not by itself prove internal HIF pairing or NPU
attachment. `lspci` was absent; no package was installed. Ordinary read-only
sysfs driver bindings supplied the inventory without raw register access.

This is progress on the actual-client reproduction prerequisite, not a Wi-Fi
fix or full NPU implementation. Both full goals remain open. The separate
restricted provider-INODE and native DESC5/6/7/8 operations remain untouched.
