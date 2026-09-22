const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const fixture = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const output = process.argv[3];
const html = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>W1700K Security Control Fixture</title>
<style>body{font:16px Arial,sans-serif;letter-spacing:0;margin:24px;color:#222;background:#fff}main{max-width:760px}h1{font-size:22px}label{display:block;margin:18px 0}select{font:inherit;max-width:100%;padding:5px}input{width:18px;height:18px;vertical-align:middle}fieldset{border:0;border-top:1px solid #aaa;padding:12px 0;margin-top:24px}.description{font-size:14px;line-height:1.5;color:#444;margin:6px 0 24px}#flags>div[hidden]{display:none}</style>
<main><h1>W1700K Wireless Security</h1><label><input id="mlo" type="checkbox"> MLO</label>
<label>Encryption <select id="encryption"><option value="sae">WPA3-SAE</option><option value="sae-compat">WPA3 Compatibility</option><option value="owe">OWE</option><option value="wpa3">WPA3 Enterprise</option></select></label>
<label>Radio mode <select id="htmode"><option>EHT20</option><option>HE20</option></select></label><fieldset id="flags"></fieldset></main></html>`;

const adapter = `
const _ = value => value;
const L = { isObject: value => value && typeof value === 'object',
  toArray: value => value == null ? [] : Array.isArray(value) ? value : [value] };
const saved = { device: ['radio1', 'radio0'] };
const uci = { get: (pkg, sid, key) => sid === 'test' ? saved[key] : key === 'htmode' ? 'EHT20' : null };
const dom = { callClassMethod: (node, name, value) => { node.checked = value === '1'; } };
const form = { Flag: function() {} };
form.Flag.prototype.updateDefaultValue = updateDefaultValue;
const input = name => document.getElementById(name);
const value = name => name === 'mode' ? 'ap' : name === 'mlo' ? (input(name).checked ? '1' : '0') : input(name).value;
const controls = {};
const map = { config: 'wireless',
  lookupOption: (name, dev) => Array.isArray(dev) ? null : [{ formvalue: () => [value('htmode')] }],
  findElement: (attr, id) => input(id),
  isDependencySatisfied: deps => deps.some(dep => Object.entries(dep).every(([k, v]) => value(k) === v)) };
const ss = { uciconfig: 'wireless', children: ['mode', 'mlo', 'encryption'].map(option => ({
  option, isActive: () => true, formvalue: () => value(option) })),
  taboption: (tab, kind, option, label, description) => {
    const wrapper = document.createElement('div');
    const text = document.createElement('label');
    const node = document.createElement('input'); node.type = 'checkbox'; node.id = option;
    text.append(node, document.createTextNode(' ' + label));
    const info = document.createElement('p'); info.className = 'description'; info.textContent = description;
    wrapper.append(text, info); input('flags').append(wrapper);
    node.addEventListener('change', () => node.setAttribute('data-changed', 'true'));
    const control = { option, section: ss, map, deps: [],
      depends: dep => control.deps.push(dep), cfgvalue: () => saved[option], cbid: () => option };
    controls[option] = control; return control;
  } };
buildOptions(ss);
window.refresh = () => Object.values(controls).forEach(control => {
  const node = input(control.option);
  node.parentElement.parentElement.hidden = !map.isDependencySatisfied(control.deps);
  control.updateDefaultValue('test');
});
window.restoreFixture = overrides => {
  for (const name of ['gcmp256', 'sae_ext_key']) {
    delete saved[name]; input(name).removeAttribute('data-changed'); input(name).checked = false;
  }
  Object.assign(saved, overrides || {});
  input('mlo').checked = false; input('encryption').value = 'sae'; input('htmode').value = 'EHT20';
  for (const [name, v] of Object.entries(overrides || {})) if (input(name)) input(name).checked = v === '1';
  window.refresh();
};
for (const name of ['mlo', 'encryption', 'htmode']) input(name).addEventListener('change', window.refresh);
window.restoreFixture();
`;

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const results = [];
  try {
    for (const version of ['before', 'current']) {
      for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
        const page = await browser.newPage({ viewport });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', event => { if (['error', 'warning'].includes(event.type())) errors.push(event.text()); });
        await page.route('http://w1700k-security.test/**', route => route.fulfill({ contentType: 'text/html', body: html }));
        await page.goto('http://w1700k-security.test/');
        await page.addScriptTag({ content: fixture[version] + '\n' + adapter });
        assert.deepEqual(errors, []);
        assert.equal(await page.title(), 'W1700K Security Control Fixture');
        assert.equal(page.url(), 'http://w1700k-security.test/');
        assert.equal(await page.locator('#flags input').count(), 2);
        assert.equal(await page.locator('#gcmp256').isChecked(), false);
        await page.check('#mlo');
        const enabled = await page.locator('#gcmp256').isChecked() && await page.locator('#sae_ext_key').isChecked();
        assert.equal(enabled, version === 'current');
        const screenshot = path.join(output, `${version}-${viewport.width}.png`);
        await page.screenshot({ path: screenshot, fullPage: true });
        if (version === 'current') {
          await page.uncheck('#gcmp256');
          await page.evaluate(() => window.refresh());
          assert.equal(await page.locator('#gcmp256').isChecked(), false);
          await page.evaluate(() => window.restoreFixture({ gcmp256: '0', sae_ext_key: '0' }));
          await page.check('#mlo');
          assert.equal(await page.locator('#gcmp256').isChecked(), false);
          assert.equal(await page.locator('#sae_ext_key').isChecked(), false);
          await page.evaluate(() => window.restoreFixture());
          await page.check('#mlo');
          for (const encryption of ['owe', 'wpa3']) {
            await page.selectOption('#encryption', encryption);
            assert.equal(await page.locator('#gcmp256').isVisible(), true);
            assert.equal(await page.locator('#gcmp256').isChecked(), true);
            assert.equal(await page.locator('#sae_ext_key').isVisible(), false);
          }
          await page.uncheck('#mlo');
          await page.selectOption('#encryption', 'sae');
          assert.equal(await page.locator('#gcmp256').isChecked(), false);
          await page.evaluate(() => { saved.device = 'radio1'; });
          await page.selectOption('#encryption', 'sae-compat');
          assert.equal(await page.locator('#gcmp256').isChecked(), true);
          await page.selectOption('#htmode', 'HE20');
          assert.equal(await page.locator('#gcmp256').isChecked(), false);
        }
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        assert.deepEqual(errors, []);
        results.push({ version, viewport, identity: true, nonblank: true, errors,
          no_horizontal_overflow: true, mlo_defaults_enabled: enabled, screenshot });
        await page.close();
      }
    }
  } finally { await browser.close(); }
  const report = { scope: 'Actual option definitions and both LuCI default handlers; synthetic UCI/form/DOM adapters. Not authenticated LuCI save/apply.',
    browser_path: 'Browser plugin not available; existing Playwright with Microsoft Edge',
    source_sha256: fixture.source_sha256, form_sha256: fixture.form_sha256, results };
  fs.writeFileSync(path.join(output, 'browser.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
