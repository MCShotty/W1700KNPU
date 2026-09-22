import { readfile } from 'fs';

let run = ARGV[0], stage = ARGV[1];
if (!match(run, /^\/tmp\/w1700k-wifi-transitions-20260907-[a-zA-Z0-9_-]+$/) ||
    !match(stage, /^[0-9][0-9]-[a-zA-Z0-9_-]+$/))
  die('Unexpected test capture path');

function rows(path) {
  let result = [];
  for (let line in split(trim(readfile(path)), '\n')) {
    let values = split(line, /\s+/);
    if (length(values) != 4) die('Invalid channel capture row');
    let row = { channel: +values[0], frequency: +values[1], width: +values[2], center: +values[3] };
    for (let key, value in row)
      if (value <= 0 || value != (value | 0)) die('Invalid numeric channel field');
    row.band = row.frequency < 2500 ? '2g' : row.frequency < 5900 ? '5g' : '6g';
    push(result, row);
  }
  return result;
}

let expected = rows(run + '/' + stage + '.expected-channels.txt');
let actual = rows(run + '/' + stage + '.actual-channels.txt');
let marker = 'W1700K-TRANSITION ' + run + ' ' + stage + ' BEGIN';
let started = false, coex = false;
for (let line in split(readfile(run + '/' + stage + '.current.system.private.log'), '\n')) {
  if (index(line, marker) >= 0) started = true;
  else if (started && index(line, 'hostapd: Switch own primary and secondary channel ') >= 0)
    coex = true;
}

let valid = length(expected) == length(actual), adjusted = 0, checks = [];
for (let want in expected) {
  let matches = filter(actual, row => row.band == want.band);
  let got = matches[0];
  let same = length(matches) == 1 && got.width == want.width && got.center == want.center;
  let exact = same && got.channel == want.channel && got.frequency == want.frequency;
  let partner = want.channel + (((want.channel - (want.channel < 149 ? 36 : 149)) % 8) == 0 ? 4 : -4);
  let swap = same && !exact && coex && want.band == '5g' && want.width >= 40 &&
    got.channel == partner && got.frequency == 5000 + got.channel * 5;
  valid &&= exact || swap;
  if (swap) adjusted++;
  push(checks, { expected: want, actual: got, exact, observed_coexistence_swap: !!swap });
}
printf('%J\n', { valid: !!valid, exact_primary_match: valid && !adjusted,
  adjusted_5g_primaries: adjusted, new_stage_coexistence_message: coex, checks });
exit(valid ? 0 : 1);
