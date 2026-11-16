const { spawnSync } = require('node:child_process');
const test = require('node:test');
const assert = require('node:assert/strict');

test('package CLI resolves from its directory', () => {
  const result = spawnSync(process.execPath, ['.'], { input: '"one,two,one"', encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout, '["one","two"]\n');
});

test('parser export is compatible and normalization preserves ordering', async () => {
  const { splitTags, normalizeTags } = await import('../src/tags.js');
  assert.deepEqual(splitTags(' one , , two '), ['one', '', 'two']);
  assert.deepEqual(normalizeTags('one, two, one, , ONE'), ['one', 'two', 'ONE']);
});
