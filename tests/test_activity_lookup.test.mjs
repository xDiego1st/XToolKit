import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const source = readFileSync(new URL('../assets/frida/billing.js', import.meta.url), 'utf8');
const begin = source.indexOf('function activityUsable(activity)');
const end = source.indexOf('function boot(){', begin);
assert.ok(begin > 0 && end > begin, 'Frida Activity lookup functions not found');
const lookup = source.slice(begin, end);

function simulate({ mode = 'auto', choose = 'success', thread = 'success' } = {}) {
  const events = [];
  const activity = {
    isFinishing: () => false,
    isDestroyed: () => false,
    getClass: () => ({ getName: () => 'com.example.Activity' })
  };
  let chooseCalls = 0;
  let threadCalls = 0;
  const context = {
    ACTIVITY_METHOD: mode,
    L: () => {},
    S: event => events.push(event),
    Java: {
      choose: (_name, cb) => {
        chooseCalls++;
        if (choose === 'error') throw new Error('libart.so: EnsurePluginLoaded missing');
        if (choose === 'success') cb.onMatch(activity);
        cb.onComplete();
      },
      use: name => {
        if (name === 'android.app.ActivityThread') {
          threadCalls++;
          if (thread === 'error') throw new Error('mActivities inaccessible');
          return { currentActivityThread: () => ({
            mActivities: { value: {
              size: () => thread === 'success' ? 1 : 0,
              valueAt: () => ({ activity: { value: activity } })
            } }
          }) };
        }
        if (name === 'android.app.ActivityThread$ActivityClientRecord') return {};
        throw new Error('Unknown mock class: ' + name);
      },
      cast: value => value
    }
  };
  runInNewContext(lookup + '\nthis.result = getActivity();', context, { timeout: 1000 });
  return { activity: context.result, events, chooseCalls, threadCalls };
}

test('auto preserves original Java.choose when it works', () => {
  const result = simulate();
  assert.equal(result.chooseCalls, 1);
  assert.equal(result.threadCalls, 0);
  assert.ok(result.activity);
  assert.equal(result.events.find(e => e.ev === 'activity_selected').method, 'choose');
});

test('auto falls back after the Android 15 ART symbol failure', () => {
  const result = simulate({ choose: 'error' });
  assert.equal(result.chooseCalls, 1);
  assert.equal(result.threadCalls, 1);
  assert.ok(result.activity);
  assert.equal(result.events.find(e => e.ev === 'activity_selected').method, 'thread');
});

test('choose mode never falls back automatically', () => {
  const result = simulate({ mode: 'choose', choose: 'error' });
  assert.equal(result.chooseCalls, 1);
  assert.equal(result.threadCalls, 0);
  assert.equal(result.activity, null);
  assert.ok(result.events.some(e => e.ev === 'no_activity'));
});

test('thread mode never calls Java.choose', () => {
  const result = simulate({ mode: 'thread', choose: 'error' });
  assert.equal(result.chooseCalls, 0);
  assert.equal(result.threadCalls, 1);
  assert.ok(result.activity);
});

test('auto fails closed if both strategies fail', () => {
  const result = simulate({ choose: 'error', thread: 'error' });
  assert.equal(result.activity, null);
  assert.ok(result.events.some(e => e.ev === 'activity_thread_err'));
  assert.ok(result.events.some(e => e.ev === 'no_activity'));
});
