'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/static/app.js', 'utf8');
const elements = {};
const element = (id) => elements[id] ||= { children: [], innerHTML: '', hidden: false, textContent: '',
  attrs: {}, querySelectorAll: () => [], contains: () => false, focus: () => {}, setAttribute(k,v) { this.attrs[k]=v; } };
const parts = ['neuro', 'cardio', 'immune', 'bone', 'habitat', 'metab'].map((id) => ({ dataset: { lane: id }, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; } }));
const buttons = parts.map((p) => ({ dataset: p.dataset, word: {}, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, querySelector() { return this.word; } }));
const context = { document: { getElementById: element, addEventListener: () => {}, activeElement: {},
  querySelectorAll: (s) => s === '#figure .part' ? parts : s === '#systems button' ? buttons : [] },
  location: { hash: '' }, fetch: () => { throw new Error('network not expected'); }, console };
vm.runInNewContext(source.slice(0, source.indexOf('// ---------- events ----------')) + `
globalThis.UI = { LANES, laneBand, renderBody, renderTodo, renderAlarms, alertHtml, headline, openAlerts, renderSignals,
 contributionData, renderDrift, toggleDrift, themeDrift, loadCrew, loadHistory, openSignal,
 current() { return {crew,status,timeline}; },
 changeCrew(id, st = null) { crew=id; crewRevision++; status=st; timeline=null; for(const k in history) delete history[k]; },
 set(st, lane = null) { for (const sig of Object.keys(st.signals)) history[sig] = {points:[]}; status = st; selectedLane = lane; crew = 'cm2'; timeline = { first_ts: '2026-11-14T10:00:00Z', baseline_days: 14, days: [{day:35}], episodes: [] }; } };`, context);
const ui = context.UI;
const habitat = ui.LANES.find((l) => l.id === 'habitat');
assert.equal(ui.laneBand({environment: 'green', radiation: 'unknown'}, habitat), 'unknown');
assert.equal(ui.laneBand({environment: 'green', radiation: 'stale'}, habitat), 'stale');
assert.equal(ui.laneBand({environment: 'amber', radiation: 'red'}, habitat), 'red');
assert.equal(ui.laneBand({}, ui.LANES.find((l) => l.id === 'metab')), 'unknown');
const makeAlert = (id, level, active, ack = null) => ({ alert_id: id, id: 'pattern', name: '<Sleep loss>', level, active, acknowledged_at: ack,
 started_ts: '2026-12-18T10:00:00Z', last_ts: '2026-12-18T10:00:00Z', fired: {sleep_duration_h: {value:4, band:'red'}},
 response_crew: 'Follow onboard protocol.', response_system: 'Review with medical team.', citation: 'Example source', basis: 'proposed' });
const st = { systems: { neurocognitive: 'red', cardiovascular: 'stale', immune: 'amber', bone_muscle: 'green', environment: 'green', radiation: 'unknown' },
 signals: { sleep_duration_h: {system:'neurocognitive', value:4, band:'red', baseline_mean:7, provenance:'simulated', ts:'2026-12-18T10:00:00Z', rule:{kind:'abs', direction:'below', red:5, basis:'published', citation:'Sleep source'}} },
 alerts: [makeAlert(1,'amber',true), makeAlert(2,'red',true), makeAlert(3,'red',false)] };
ui.set(st, 'neuro');
element('figure').innerHTML = 'stable svg nodes';
ui.renderBody();
assert.equal(element('figure').innerHTML, 'stable svg nodes', 'live updates retain SVG/focus nodes');
assert.match(parts[0].attrs.class, /red/);
assert.match(parts[1].attrs.class, /stale/);
assert.match(parts[4].attrs.class, /unknown/);
assert.match(parts[5].attrs.class, /unknown/);
assert.match(parts[0].attrs['aria-label'], /Red/);
assert.equal(parts[0].attrs['aria-pressed'], 'true');
assert.match(element('system-content').innerHTML, /simulated/);
assert.match(element('system-content').innerHTML, /Show more · limits/);
assert.match(element('system-content').innerHTML, /Baseline 7 h/);
ui.renderAlarms();
assert(element('alarms').innerHTML.indexOf('data-alert="2"') < element('alarms').innerHTML.indexOf('data-alert="1"'), 'higher urgency sorts first');
assert.match(element('alarms').innerHTML, /resolved, to review/);
assert.match(element('alarms').innerHTML, /alarm-button red active/);
assert.match(element('alarms').innerHTML, /alarm-button amber active/);
assert.match(element('alarms').innerHTML, /alarm-button red resolved/, 'resolved-to-review cards retain their backend urgency hue');
const html = ui.alertHtml(st.alerts[1]);
assert.match(html, /alert red active/);
assert.match(html, /&lt;Sleep loss&gt;/);
assert(html.indexOf('Follow onboard protocol.') < html.indexOf('<details'), 'crew response remains visible');
assert.match(html, /Show more · medical response and sources/);
assert.match(html, /Review with medical team/);
assert.match(html, /Example source/);
assert.match(ui.alertHtml(makeAlert(4,'red',false,'now')), /Resolved · acknowledged/);
ui.set({systems:{}, signals:{sleep_duration_h:{value:null,band:'unknown'}}, alerts:[]}, 'metab');
assert.equal(ui.headline().band, 'unknown');
ui.renderTodo();
assert.match(element('todo').innerHTML, /Check the sensor feed/);
assert.doesNotMatch(element('todo').innerHTML, /normal routine/);
ui.renderBody();
assert.match(element('system-content').innerHTML, /No metabolic readings/);
ui.set({systems:{}, signals:{sleep_duration_h:{value:4,band:'unknown'}}, alerts:[]});
assert.equal(ui.headline().band, 'unknown', 'unclassified readings do not imply normal');
ui.set({systems:{}, signals:{sleep_duration_h:{value:null,band:'stale'}}, alerts:[]});
assert.equal(ui.headline().band, 'stale', 'overdue readings do not need a value to remain overdue');
ui.set(st);
const dialog = element('d-alerts'); dialog.open = true; dialog.contains = () => false;
ui.openAlerts();
assert.match(element('da-list').innerHTML, /Active/);
const resolved = {...st, alerts:[makeAlert(2,'red',false)]};
ui.set(resolved); ui.openAlerts();
assert.match(element('da-list').innerHTML, /Resolved · to review/);
assert.match(source, /if \(\$\('d-alerts'\)\.open\) openAlerts\(\)/, 'render refreshes an open alert dialog');
ui.set(st);
const signalsCheck = ui.renderSignals().then(() => assert.match(element('sig-rows').innerHTML, /class="tag">simulated/));
const contributions = { available:true, score:0.2, anomalous:false, detector:'ewma', contributions:{sleep_duration_h:0, reaction_lapses_pct:0.524, mood_score:0.217, cabin_co2_mmhg:0.208} };
const shares = ui.contributionData(contributions);
assert.equal(shares.entries.length, 4, 'zero terms remain in the named list');
assert(Math.abs(shares.entries.reduce((sum,e) => sum+e.share,0) - 1) < 1e-12);
assert.equal(shares.entries[0].signal, 'reaction_lapses_pct');
assert.match(ui.contributionData({available:false,reason:'baseline not ready'}).reason, /baseline/);
assert.match(ui.contributionData({available:true,contributions:{mood_score:0}}).reason, /No non-zero/);
for (const invalid of [-0.1, NaN, Infinity, '0.1', null]) assert.match(ui.contributionData({available:true,contributions:{mood_score:invalid}}).reason, /Invalid/);
let chartConfig, destroyed = false, chartCount = 0;
context.window = {Chart: function(canvas, config) { chartCount++; chartConfig=config; this.data=config.data; this.update=()=>{}; this.destroy=()=>{destroyed=true;}; }};
context.getComputedStyle = () => ({getPropertyValue:()=> '#1a1e24'});
const chartStatus = {...st, anomaly:contributions};
element('drift-content').hidden = true;
ui.set(chartStatus); ui.renderDrift();
assert.equal(chartCount, 0, 'the chart is not constructed before the user requests it');
assert.equal(element('drift-legend').innerHTML, '');
ui.toggleDrift();
assert.equal(element('drift-content').hidden, false);
assert.equal(element('drift-toggle').attrs['aria-expanded'], 'true');
assert.equal(element('drift-toggle').textContent, 'Hide drift contributions');
assert.equal(chartConfig.type, 'pie');
assert.equal(chartConfig.data.datasets[0].data.length, 4);
assert.match(element('drift-legend').innerHTML, /Sleep duration/);
assert.match(element('drift-legend').innerHTML, /0.0%/);
assert.match(element('drift-context').textContent, /EWMA.*not flagged by model/);
assert.equal(chartStatus.signals.sleep_duration_h.band, 'red', 'chart never rewrites backend signal bands');
ui.toggleDrift();
assert.equal(destroyed, true, 'closing destroys the hidden chart');
assert.equal(element('drift-content').hidden, true);
assert.equal(element('drift-toggle').attrs['aria-expanded'], 'false');
assert.equal(element('drift-toggle').textContent, 'Show drift contributions');
ui.set({...st, anomaly:{...contributions, score:0.7}}); ui.renderDrift(); ui.themeDrift();
assert.equal(chartCount, 1, 'live and theme updates cannot recreate or reopen a closed chart');
assert.equal(element('drift-content').hidden, true);
destroyed = false;
ui.toggleDrift();
assert.equal(chartCount, 2);
assert.match(element('drift-context').textContent, /score 0.7/, 'reopening uses the latest backend output');
ui.set({...st, anomaly:{available:false,reason:'baseline not ready'}}); ui.renderDrift();
assert.equal(destroyed,true); assert.equal(element('drift-chart').hidden,true);
assert.match(element('drift-empty').textContent, /baseline/);
assert.equal(element('drift-content').hidden, false, 'requested unavailable output retains its honest message');
assert.match(source, /t.id === 'drift-toggle'\) toggleDrift\(\)/, 'the real button is bound to the disclosure');
// Both persistence and storage denial must leave an operable preference switch.
const themeSource = fs.readFileSync('web/static/theme.js','utf8');
for (const denied of [false, true]) {
  const listeners = {}, toggle = {setAttribute(k,v){this[k]=v;}, addEventListener(k,fn){listeners[k]=fn;}};
  const doc = {documentElement:{dataset:{}}, getElementById:() => toggle, addEventListener(k,fn){listeners[k]=fn;}, dispatchEvent:() => {}};
  let saved = 'light';
  const storage = {getItem(){if(denied) throw Error(); return saved;}, setItem(k,v){if(denied) throw Error(); saved=v;}};
  vm.runInNewContext(themeSource, {document:doc, localStorage:storage, Event:function(){}});
  assert.equal(doc.documentElement.dataset.theme, denied ? 'dark' : 'light');
  listeners.DOMContentLoaded(); listeners.click();
  assert.equal(doc.documentElement.dataset.theme, denied ? 'light' : 'dark');
  assert.equal(toggle['aria-pressed'], denied ? 'true' : 'false');
}
console.log('Console UI checks passed: backend band mapping, unknown/stale, urgency, disclosure, focus-node retention and theme storage.');

(async () => {
  await signalsCheck;
  const pending = [];
  context.fetch = (url) => new Promise((resolve) => pending.push({url,resolve}));
  const reply = (i, body) => pending[i].resolve({ok:true,json:()=>Promise.resolve(body)});
  ui.changeCrew('cm2');
  const oldCrew = ui.loadCrew();
  ui.changeCrew('demo_normal');
  const newCrew = ui.loadCrew();
  reply(2,{crew_id:'demo_normal',signals:{},ts:'2026-12-01T10:00:00Z'}); reply(3,{crew_id:'demo_normal',days:[]});
  assert.equal(await newCrew,true);
  reply(0,{crew_id:'cm2',signals:{},ts:'2026-12-01T10:00:00Z'}); reply(1,{crew_id:'cm2',days:[]});
  assert.equal(await oldCrew,false);
  assert.equal(ui.current().status.crew_id,'demo_normal');
  assert.equal(ui.current().timeline.crew_id,'demo_normal');
  ui.changeCrew('cm2',st);
  const oldHistory = ui.loadHistory();
  ui.changeCrew('demo_normal'); reply(4,{points:[{value:99}]});
  assert.equal(await oldHistory,false);
  ui.changeCrew('cm2',st);
  const oldSignal = ui.openSignal('sleep_duration_h');
  ui.changeCrew('demo_normal'); reply(5,{points:[{value:99}]});
  await oldSignal;
  assert.equal(element('ds-title').textContent,'','late old-crew trends cannot label a new-crew dialog');
  console.log('Delayed response checks passed: status, timeline, history and trend stay scoped to the selected crew.');
})().catch((error)=>{console.error(error);process.exitCode=1;});
