import { readFileSync } from 'node:fs';
import { splitTags } from './tags.js';

try {
  const input = JSON.parse(readFileSync(0, 'utf8'));
  if (typeof input !== 'string') throw new Error('expected string');
  console.log(JSON.stringify([...new Set(splitTags(input).filter(Boolean))]));
} catch {
  console.error('invalid tags');
  process.exitCode = 2;
}
