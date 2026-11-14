/* Raw game sessions only. No game score is converted into a health reading. */
'use strict';
(() => {
  const params = new URLSearchParams(location.search);
  const crew = params.get('crew');
  const enabled = /^[A-Za-z0-9_-]{1,64}$/.test(crew || '');
  const ts = params.get('ts') || new Date().toISOString();
  const prefix = `aura_game_outbox_v1:${crew}:`;
  let queue = [], busy = false, storageIssue = false;
  if (enabled) {
    try {
      for (const key of Object.keys(localStorage).filter((k) => k.startsWith(prefix))) {
        const entry = JSON.parse(localStorage.getItem(key));
        if (entry.crew_id !== crew || key !== prefix + entry.session_id) throw new Error('Invalid pending session');
        queue.push(entry);
      }
    } catch { storageIssue = true; } // leave unreadable entries in storage; never erase them silently
  }
  let text, retry;
  function show(message) { if (text) text.textContent = message; }
  async function sendPending() {
    if (!enabled || busy || !queue.length) return;
    busy = true;
    if (retry) retry.disabled = true;
    try {
      while (queue.length) {
        show(`Saving game session for ${crew.toUpperCase()}…`);
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 15000);
        let response;
        try {
          response = await fetch('/game-sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(queue[0]), signal: controller.signal });
        } finally { clearTimeout(timer); }
        if (!response.ok) throw new Error(`core answered ${response.status}`);
        const result = await response.json();
        if (result.saved !== queue[0].session_id) throw new Error('session acknowledgement did not match');
        try { localStorage.removeItem(prefix + queue[0].session_id); }
        catch { storageIssue = true; } // a remaining entry can be retried safely with the same UUID
        queue.shift();
      }
      show(`Saved for ${crew.toUpperCase()} · game performance, not a health measurement.`);
    } catch (error) {
      show(`Not sent (${error.message}). ${queue.length} session(s) kept${storageIssue ? ' in this tab only; do not close it' : ' for retry'}.`);
    } finally {
      busy = false;
      if (retry) retry.disabled = !queue.length;
    }
  }
  window.auraGameSession = (raw) => {
    if (!enabled) return; // standalone play never uploads to an assumed crew
    try {
      const session = JSON.parse(raw);
      const entry = { session_id: crypto.randomUUID(), crew_id: crew, ts,
        game_id: session.game_id, difficulty: session.difficulty, result: session.result };
      queue.push(entry);
      // One key per UUID prevents separate game tabs from overwriting other pending results.
      try { localStorage.setItem(prefix + entry.session_id, JSON.stringify(entry)); }
      catch { storageIssue = true; }
      void sendPending();
    } catch (error) {
      show(`Game export failed (${error.message}); the arcade's own result remains available.`);
    }
  };
  document.addEventListener('DOMContentLoaded', () => {
    const bar = document.createElement('aside');
    bar.setAttribute('aria-label', 'AURA-Bio game connection');
    bar.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:10000;display:flex;gap:12px;align-items:center;padding:7px 12px;background:#1a1e24;color:#e6e1d5;font:13px/1.4 system-ui;flex-wrap:wrap;border-bottom:1px solid #4a515c';
    const back = document.createElement('a');
    back.href = '/#checkin';
    back.textContent = 'Return to AURA-Bio';
    back.style.color = '#e6e1d5';
    text = document.createElement('span');
    text.setAttribute('role', 'status');
    retry = document.createElement('button');
    retry.type = 'button';
    retry.textContent = 'Retry sending';
    retry.disabled = !queue.length;
    retry.style.cssText = 'color:#e6e1d5;background:#20252c;border:1px solid #4a515c;padding:5px 10px;font:inherit;cursor:pointer';
    retry.addEventListener('click', sendPending);
    bar.append(back, text, retry);
    document.body.append(bar);
    show(enabled ? `Completed sessions will be saved for ${crew.toUpperCase()} · demo game data only.${queue.length ? ' Pending sessions available; choose Retry sending.' : ''}${storageIssue ? ' Browser storage unavailable or unreadable; keep this tab open.' : ''}`
      : 'Standalone play · open games from AURA-Bio Check-in to save for a crew member.');
  });
})();
