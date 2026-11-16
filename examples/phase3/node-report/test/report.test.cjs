const { test } = require('node:test');
const assert = require('node:assert/strict');
const { summarize } = require('../src/report');

test('count and order duplicate labels', () => {
  assert.deepEqual(summarize([' y ', 'x', 'y']), [['y', 2], ['x', 1]]);
});
