// cache_harness.mjs — behavioral harness for the Server-view history fetch layer.
//
// Extracts the REAL shipped code (PX_HIST_CFG, pxTtlFor, pxMakeHistCache) from
// tablet/tablet-panel.js and exercises it in isolation with injected deps
// (fake clock, fake AbortController, counting/controllable fetch). Proves:
//   1. cache hit within TTL (no refetch)     2. single-flight dedup
//   3. abort on supersede + on leave-view     4. TTL expiry -> refetch
// and measures the recorder-GET reduction vs a naive fetch-per-render panel.
//
// Read-only: never touches HA, never prints a token. Exit non-zero on failure.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import vm from 'node:vm';

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(resolve(HERE, '../../../tablet/tablet-panel.js'), 'utf-8');

// --- extract a top-level `function NAME(...) { ... }` by brace matching ---
function extractFn(src, name) {
  const sig = 'function ' + name + '(';
  const i = src.indexOf(sig);
  if (i < 0) throw new Error('function not found: ' + name);
  let depth = 0, started = false, j = i;
  for (; j < src.length; j++) {
    const c = src[j];
    if (c === '{') { depth++; started = true; }
    else if (c === '}') { depth--; if (started && depth === 0) { j++; break; } }
  }
  return src.slice(i, j);
}
// --- extract a top-level `const NAME = { ... };` ---
function extractConstObj(src, name) {
  const sig = 'const ' + name + ' = {';
  const i = src.indexOf(sig);
  if (i < 0) throw new Error('const not found: ' + name);
  let depth = 0, started = false, j = i;
  for (; j < src.length; j++) {
    const c = src[j];
    if (c === '{') { depth++; started = true; }
    else if (c === '}') { depth--; if (started && depth === 0) { j++; break; } }
  }
  // include trailing ';'
  while (j < src.length && src[j] !== ';') j++;
  return src.slice(i, j + 1);
}

const code =
  extractConstObj(SRC, 'PX_HIST_CFG') + '\n' +
  extractFn(SRC, 'pxTtlFor') + '\n' +
  extractFn(SRC, 'pxMakeHistCache') + '\n' +
  'globalThis.PX_HIST_CFG = PX_HIST_CFG;\n' +
  'globalThis.pxTtlFor = pxTtlFor;\n' +
  'globalThis.pxMakeHistCache = pxMakeHistCache;\n';

const sandbox = { globalThis: {}, AbortController: undefined };
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(code, sandbox, { filename: 'extracted-cache.js' });
const { PX_HIST_CFG, pxTtlFor, pxMakeHistCache } = sandbox;

// ---- test helpers ----
let failures = 0;
function ok(cond, msg) { if (cond) { console.log('  ok   ' + msg); } else { failures++; console.log('  FAIL ' + msg); } }
function eq(a, b, msg) { ok(a === b, msg + ' (got ' + JSON.stringify(a) + ', want ' + JSON.stringify(b) + ')'); }

class FakeAC { constructor() { this.signal = { aborted: false }; } abort() { this.signal.aborted = true; } }

// The store schedules doFetch on a microtask (Promise.resolve().then(...)), so a
// caller must yield the microtask queue before the mock fetch has been invoked.
const tick = () => Promise.resolve();
const flush = () => new Promise(r => setTimeout(r, 0));

// Controllable fetch: counts calls, hands back a promise resolved on demand so we
// can test in-flight dedup and late (superseded) resolution deterministically.
function makeFetch() {
  const pending = [];
  let calls = 0;
  const fn = (key, ids, hours, signal) => {
    calls++;
    return new Promise((res, rej) => pending.push({ key, signal, res, rej }));
  };
  return {
    fn,
    get calls() { return calls; },
    resolveLast(series) { const p = pending.pop(); p.res(series); return p; },
    resolveFirst(series) { const p = pending.shift(); p.res(series); return p; },
    resolveAll(series) { while (pending.length) pending.shift().res(series); },
    pendingCount() { return pending.length; },
  };
}

const SERIES = { 'sensor.a': [{ t: 1, v: 10 }, { t: 2, v: 20 }] };
const IDS = ['sensor.a', 'sensor.b'];
const KEY = h => h + '|' + IDS.join(',');

// ================= 1. cache hit within TTL =================
async function testCacheHit() {
  console.log('[1] cache hit within TTL — re-render/toggle does not refetch');
  let clock = 1_000_000;
  const F = makeFetch();
  const store = pxMakeHistCache({ fetch: F.fn, ttlFor: pxTtlFor, now: () => clock, AbortCtrl: FakeAC, onUpdate: () => {} });
  const p1 = store.ensure(KEY(168), IDS, 168);
  await tick(); F.resolveLast(SERIES); await p1;
  eq(F.calls, 1, 'first ensure triggers one fetch');
  // simulate 50 re-renders + a bunch of 24h<->7d toggles, all within TTL
  for (let i = 0; i < 50; i++) await store.ensure(KEY(168), IDS, 168);
  clock += 5 * 60_000; // +5 min, still < TTL_LONG (10 min)
  for (let i = 0; i < 10; i++) await store.ensure(KEY(168), IDS, 168);
  eq(F.calls, 1, '50 re-renders + toggles within TTL => still 1 fetch');
  const e = store.get(KEY(168));
  eq(e.ttl, PX_HIST_CFG.TTL_LONG, '7d window uses TTL_LONG');
  ok(store.fresh(e), 'entry reported fresh within TTL');
}

// ================= 2. single-flight dedup =================
async function testDedup() {
  console.log('[2] single-flight dedup — concurrent ensures share one GET');
  let clock = 2_000_000;
  const F = makeFetch();
  const store = pxMakeHistCache({ fetch: F.fn, ttlFor: pxTtlFor, now: () => clock, AbortCtrl: FakeAC, onUpdate: () => {} });
  const a = store.ensure(KEY(168), IDS, 168);
  const b = store.ensure(KEY(168), IDS, 168);
  const c = store.ensure(KEY(168), IDS, 168);
  ok(a === b && b === c, 'concurrent ensures return the SAME promise');
  await tick();
  eq(F.calls, 1, '3 concurrent ensures => 1 in-flight GET');
  F.resolveLast(SERIES); await Promise.all([a, b, c]);
  eq(F.pendingCount(), 0, 'no dangling in-flight requests');
}

// ================= 3. abort on supersede + leave view =================
async function testAbort() {
  console.log('[3] abort on supersede & on leave-view — stale result discarded');
  let clock = 3_000_000;
  const F = makeFetch();
  const store = pxMakeHistCache({ fetch: F.fn, ttlFor: pxTtlFor, now: () => clock, AbortCtrl: FakeAC, onUpdate: () => {} });
  // supersede: entity-set changes (key A -> key B) while A is in-flight
  const pA = store.ensure('168|old', ['sensor.old'], 168);
  const eA = store.get('168|old');
  await tick(); // let doFetch(old) run so it is genuinely in-flight
  store.ensure('168|new', ['sensor.new'], 168); // supersedes A
  ok(eA.ctrl.signal.aborted, 'in-flight key A aborted when key B supersedes it');
  eq(eA.loading, false, 'aborted key A no longer marked loading');
  await tick(); // let doFetch(new) run — now [old, new] are both in-flight
  // late resolution of the superseded A must NOT write state (keep new pending)
  F.resolveFirst(SERIES); await pA.catch(() => {}); await flush();
  eq(eA.ts, 0, 'superseded key A never committed a timestamp (result dropped)');
  eq(Object.keys(eA.series).length, 0, 'superseded key A kept empty series (no stale write)');
  // leave view while B is still in-flight: abortAll aborts it
  const eB = store.get('168|new');
  ok(eB.loading, 'key B still loading before leave');
  store.abortAll();
  ok(eB.ctrl.signal.aborted, 'abortAll() aborts in-flight key B on leaving the view');
  F.resolveAll(SERIES); await flush(); // late B result must be dropped
  eq(eB.ts, 0, 'left-view key B result also dropped');
}

// ================= 4. TTL expiry -> refetch =================
async function testTtlExpiry() {
  console.log('[4] TTL expiry — refetch after TTL, both TTL branches wired');
  let clock = 4_000_000;
  const F = makeFetch();
  const store = pxMakeHistCache({ fetch: F.fn, ttlFor: pxTtlFor, now: () => clock, AbortCtrl: FakeAC, onUpdate: () => {} });
  const p1 = store.ensure(KEY(168), IDS, 168); await tick(); F.resolveLast(SERIES); await p1;
  eq(F.calls, 1, 'initial fetch');
  clock += PX_HIST_CFG.TTL_LONG - 1; // just inside TTL
  await store.ensure(KEY(168), IDS, 168);
  eq(F.calls, 1, 'just inside TTL => no refetch');
  clock += 2; // now past TTL_LONG
  const p2 = store.ensure(KEY(168), IDS, 168); await tick(); F.resolveLast(SERIES); await p2;
  eq(F.calls, 2, 'past TTL => refetch');
  // pxTtlFor policy: both constants genuinely reachable
  eq(pxTtlFor(168), PX_HIST_CFG.TTL_LONG, 'pxTtlFor(7d) => TTL_LONG');
  eq(pxTtlFor(24), PX_HIST_CFG.TTL_SHORT, 'pxTtlFor(24h) => TTL_SHORT');
}

// ================= 5. fetch-count reduction measurement =================
async function measure() {
  console.log('[5] measured recorder-GET reduction (this cache vs naive per-render)');
  let clock = 5_000_000;
  const F = makeFetch();
  const store = pxMakeHistCache({ fetch: F.fn, ttlFor: pxTtlFor, now: () => clock, AbortCtrl: FakeAC, onUpdate: () => {} });
  // Realistic 30-min Server-view session: hass push re-renders every ~1.2s
  // (~1500 renders) + 12 manual 24ч<->7д toggles. Naive panel = 1 GET each.
  const RENDER_MS = 1200, SESSION_MIN = 30;
  const renders = Math.floor(SESSION_MIN * 60_000 / RENDER_MS);
  const toggles = 12;
  let naive = 0;
  for (let i = 0; i < renders; i++) {
    clock += RENDER_MS;
    const p = store.ensure(KEY(168), IDS, 168);
    await tick();                              // let a cold/expired fetch reach the mock
    if (F.pendingCount()) F.resolveLast(SERIES);
    await p;
    naive++;
  }
  naive += toggles; // each toggle would also be a GET on a naive panel
  const cached = F.calls;
  const pct = ((1 - cached / naive) * 100).toFixed(1);
  console.log(`       session: ${renders} renders + ${toggles} toggles over ${SESSION_MIN} min`);
  console.log(`       naive per-render/-toggle GETs : ${naive}`);
  console.log(`       with TTL cache (10-min 7d TTL): ${cached}`);
  console.log(`       reduction                     : ${pct}%  (${naive}→${cached} recorder GETs)`);
  ok(cached < naive, 'cache issues far fewer GETs than a naive panel');
  eq(cached, Math.floor(SESSION_MIN / (PX_HIST_CFG.TTL_LONG / 60000)),
    'exactly 1 GET per 10-min TTL window');
  return { naive, cached, pct };
}

(async () => {
  await testCacheHit();
  await testDedup();
  await testAbort();
  await testTtlExpiry();
  const m = await measure();
  console.log('\n' + (failures ? failures + ' FAILURE(S)' : 'ALL CHECKS PASSED') +
    `  | fetch-count: ${m.naive} -> ${m.cached} (-${m.pct}%)`);
  process.exit(failures ? 1 : 0);
})();
