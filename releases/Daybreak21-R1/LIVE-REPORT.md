# R1 Live Engineering Check

## Summary

The exact R1 image is flashed and responding on the W1700K, kernel 6.18.44.
Its NAND FIT prefix matches SHA256
0788f405337ceb030d873463bbf278497dcd9b86e8f75a1a3f57fd318eda195f.
The three installed driver hashes match the verified package artifacts.
Factory data and the original wireless configuration are unchanged.

## Hardware Checks

| Check | Result |
| --- | --- |
| 2.4 GHz standalone AP | Pass: channel 6, 2437 MHz, EHT20 |
| 5 GHz standalone AP | Pass: channel 36, 5180 MHz, EHT80 |
| 6 GHz standalone AP | Pass: channel 33, 6115 MHz, EHT320 |
| 5 + 6 GHz MLO | Pass: one AP, two links, radios 1 and 2 |
| Tri-band MLO | Pass: one AP, three links; configured order 1, 2, 0 |
| LuCI iwinfo scan API | Successful calls for radio0, radio1 and radio2 |
| Invalid band/width/security/one-link MLO | Five cases rejected |
| Cleanup | No test interfaces left; original wireless bytes restored |
| Fatal kernel patterns | No matched BUG/Oops/panic/OOM patterns |
| Memory after matrix | About 1.58 GiB available |
| NPU status JSON | Real installed jshn path passes; compiled-out is explicit |

Country SA and transmit-power settings were preserved. Scan responses contain
shared-wiphy cached results across bands; successful API calls are not proof of
fresh per-band discoveries. No neighboring SSIDs or credentials are included.

The restored configuration has no permanent WiFi interfaces. Its parked 5 GHz
channel is 161 under SA; current regdb does not allow that AP block. The test
used valid channel 36 temporarily. Choose a valid channel before adding a
permanent 5 GHz network; the backend intentionally rejects the old setting.

## LuCI QA

Environment: installed Edge via regular Playwright, 1365x900 viewport, through
an encrypted pinned-SSH tunnel at http://127.0.0.1:18880. The dedicated Browser
plugin/skill was unavailable. No WiFi association or routing setting changed.

Flow: login -> Wireless Overview -> Add MLO -> dialog -> Dismiss; and login ->
System/W1700K NPU -> Refresh -> current status. No permanent GUI config applied.

An additional tri-band creation test filled a synthetic SSID/key, clicked Save
once, reloaded the page, and verified the staged radio order radio1/radio2/radio0,
SAE and PMF-required settings. It passed without TypeError or a hidden invalid
field blocking Save. This used temporary legal SA/channel36 and did not click
Save & Apply. The session was logged out and original configuration restored;
the evidence is GUI-SAVE-VERIFICATION.json.

| Check | Result |
| --- | --- |
| Page identity and nonblank content | Pass |
| Framework/error overlay | None observed |
| JavaScript page errors | None |
| Post-authentication warning/error console | Empty |
| NPU Refresh | Pass; current, compiled-out, provider presence truthful |
| MLO dialog open/dismiss | Pass; no TypeError |
| Tri-band dialog Save and reload | Pass with one click; staged values verified |
| Radio labels | Correct 2.4/5/6 GHz physical mapping |

Desktop screenshots and machine QA records are retained in the linked workspace
evidence directory. Mobile, other dialog-save combinations, GUI Save & Apply, real-client joining,
and long-term browser behavior were not certified. Initial menu-selector test
timeouts were harness targeting errors; navigation then used the observed page
links. The existing no-root-password warning was not changed by this task.

## Remaining Work

- WLAN NPU is compiled out. Active-NPU recovery ignores provider errors in
  upstream code; full stock hostadpt/lifetime behavior is still not ported.
- CPU-frequency SMC readback is unavailable and cpufreq policies do not
  register. Zero reported clock is not a measured zero hardware frequency.
  No guessed-frequency fallback, governor, voltage, or clock-register write
  was introduced to hide this.
- Real-client association, throughput, advanced MLO modes and long-term
  teardown/fault behavior still require separate evidence.

Evidence directory:
C:/Users/captain/Documents/Codex/2026-06-12/i-need-help-wiping-the-nand/work/router-tests/daybreak21-preflash-20260905-033019

Private backups remain outside this result bundle.
