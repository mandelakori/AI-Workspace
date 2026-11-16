const fs = require('node:fs');
const { summarize } = require('./report');

console.log(JSON.stringify(summarize(JSON.parse(fs.readFileSync(0, 'utf8')))));
