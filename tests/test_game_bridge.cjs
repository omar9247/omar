'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { randomUUID } = require('node:crypto');
const code = fs.readFileSync('web/static/lunar-arcade-hub/aura-bridge.js', 'utf8');
const raw = JSON.stringify({ game_id: 'reaction_test', difficulty: 'normal', result: { score: 1, accuracy: 100, mistakes: 0, hits: 1, avg_reaction_ms: 300, duration: 20, stats: [], extra: {} } });
function storage() {
  const s = {};
  Object.defineProperties(s, {
    getItem: { value: (k) => s[k] ?? null }, setItem: { configurable: true, value: (k, v) => { s[k] = v; } }, removeItem: { value: (k) => { delete s[k]; } },
  });
  return s;
}
function boot(search, localStorage, fetch) {
  const elements = [];
  let ready;
  const document = { body: { append() {} }, addEventListener(name, fn) { if (name === 'DOMContentLoaded') ready = fn; },
    createElement(tag) { const el = { tag, style: {}, setAttribute() {}, append() {}, addEventListener(name, fn) { this[name] = fn; } }; elements.push(el); return el; } };
  const ctx = { window: {}, document, location: { search }, localStorage, fetch, URLSearchParams, crypto: { randomUUID }, AbortController, setTimeout, clearTimeout };
  vm.runInNewContext(code, ctx);
  ready();
  return { send: ctx.window.auraGameSession, message: () => elements.find((e) => e.tag === 'span').textContent,
    retry: () => elements.find((e) => e.tag === 'button').click() };
}
const settle = async () => { for (let i = 0; i < 10; i++) await new Promise(setImmediate); };
(async () => {
  let requests = [], online = false;
  const fetch = async (_url, options) => { const body = JSON.parse(options.body); requests.push(body); return { ok: online, status: online ? 200 : 503, json: async () => ({ saved: body.session_id }) }; };
  const shared = storage();
  const first = boot('?crew=cm1&ts=2026-11-14T10%3A00%3A00Z', shared, fetch);
  first.send(raw);
  await settle();
  assert.match(first.message(), /Not sent/);
  assert.equal(Object.keys(shared).length, 1);
  const original = requests[0];
  const second = boot('?crew=cm1', shared, fetch);
  second.send(raw);
  await settle();
  assert.equal(Object.keys(shared).length, 2, 'a second tab must not overwrite the first pending UUID');
  const otherCrew = boot('?crew=cm2', shared, fetch);
  await otherCrew.retry();
  assert.equal(Object.keys(shared).length, 2, 'another crew must not transmit cm1 pending sessions');
  const reloaded = boot('?crew=cm1', shared, fetch);
  online = true;
  await reloaded.retry();
  assert.equal(Object.keys(shared).length, 0);
  assert(requests.some((b) => b.session_id === original.session_id && b.ts === original.ts));
  assert.match(reloaded.message(), /Saved for CM1/);
  const standalone = boot('', shared, () => { throw new Error('must not send'); });
  standalone.send(raw);
  assert.equal(Object.keys(shared).length, 0);
  const invalid = boot('?crew=cm1/evil', shared, () => { throw new Error('must not send'); });
  invalid.send(raw);
  assert.equal(Object.keys(shared).length, 0);
  const denied = storage();
  Object.defineProperty(denied, 'setItem', { value: () => { throw new Error('quota'); } });
  online = false;
  const limited = boot('?crew=cm1', denied, fetch);
  limited.send(raw);
  await settle();
  assert.match(limited.message(), /in this tab only; do not close it/);
  online = true;
  await limited.retry();
  assert.match(limited.message(), /Saved for CM1/);
  console.log('Game bridge checks passed: save, durable retry, timestamp/UUID preservation, crew isolation, multi-tab safety, standalone no-op, storage-denied warning.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
