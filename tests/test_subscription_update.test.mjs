import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const code = readFileSync(new URL('../assets/frida/billing.js', import.meta.url), 'utf8');
const start = code.indexOf('function launchWithStack(');
const end = code.indexOf('\nfunction launch(', start);
assert.ok(start >= 0 && end > start, 'Original stack callback not found');
const stackCode = code.slice(start, end);

function simulate({ products = [], error = false, responseCode = 0 } = {}) {
  const events = [];
  const launches = [];
  const purchases = products.map((product, index) => ({
    getProducts: () => ({ contains: id => id === product, toString: () => String(product) }),
    getPurchaseToken: () => 'test-token-' + index
  }));
  const context = {
    dexLoader: {},
    S: event => events.push(event),
    L: () => {},
    Java: {
      use: () => ({newBuilder: () => ({
        setProductType: () => ({ build: () => ({}) })
      })}),
      registerClass: definition => ({ $new: () => definition.methods }),
      cast: value => value
    },
    clientRef: { queryPurchasesAsync: (params, callback) => {
      if (error) throw new Error('Mocked BillingClient query error');
      callback.onQueryPurchasesResponse({getResponseCode: () => responseCode}, {
        size: () => purchases.length,
        get: index => purchases[index]
      });
    } },
    launch: (...args) => launches.push(args)
  };
  runInNewContext(stackCode + '\nlaunchWithStack({}, {});', context, {timeout: 1000});
  return {events, launches};
}

test('no existing subscription cannot open standalone checkout', () => {
  const result = simulate();
  assert.equal(result.launches.length, 0);
  assert.ok(result.events.some(event => event.ev === 'no_purchase'));
});

test('unrelated subscription cannot substitute its purchase token', () => {
  const result = simulate({products: ['unrelated.product']});
  assert.equal(result.launches.length, 0);
  assert.ok(result.events.some(event => event.ev === 'no_matching_purchase'));
});

test('non-OK Billing response fails closed', () => {
  const result = simulate({products: ['g1.2tb.ai.subs_variant'], responseCode: 5});
  assert.equal(result.launches.length, 0);
});

test('query exception cannot launch checkout without a token', () => {
  const result = simulate({error: true});
  assert.equal(result.launches.length, 0);
  assert.ok(result.events.some(event => event.ev === 'stack_outer_err'));
});

test('only matching Pro purchase passes its token to update flow', () => {
  const result = simulate({products: ['unrelated.product', 'g1.2tb.ai.subs_variant']});
  assert.equal(result.launches.length, 1);
  assert.equal(result.launches[0][2], 'test-token-1');
});
