export function splitTags(value) {
  return value.split(',').map(tag => tag.trim());
}
