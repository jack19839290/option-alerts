import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const fixture = JSON.parse(fs.readFileSync(0, 'utf8'));
const code = fs.readFileSync(new URL('../apps-script/Code.gs', import.meta.url), 'utf8');
const context = vm.createContext({});
vm.runInContext(code, context);
let reads = 0;
context.fixture = fixture;
context.sheet = {
  getLastRow: () => fixture.chunks.length + 1,
  getRange: () => ({getValues: () => { reads++; return fixture.chunks; }}),
};
vm.runInContext(`getSpreadsheet_ = () => ({getSheetByName: () => sheet});
  this.reader = createNotificationPayloadReader_();`, context);
const restored = context.reader(fixture.raw);
assert.deepEqual(JSON.parse(JSON.stringify(restored)), fixture.expected);
context.reader(fixture.raw);
assert.ok(reads <= 1, 'Chunk table must be loaded once per reader');
if (fixture.expected.groups) {
  context.restored = restored;
  const logCount = vm.runInContext(`buildAlertLogRowsForEvent_('E', 'FIRST_CLOSE', restored, 'test@example.invalid', '').length`, context);
  assert.equal(logCount, fixture.expected.groups.reduce((sum, g) => sum + Math.max(1, g.items.length), 0));
  const email = vm.runInContext(`buildQueueEmail_('FIRST_CLOSE', restored, 'https://example.invalid')`, context);
  for (const group of fixture.expected.groups) {
    for (const item of group.items) assert.ok(email.body.includes(`履約價 ${item.strike}`));
  }
}
if (fixture.chunks.length) {
  const chunks = fixture.chunks.slice();
  // An identical append repeated after an uncertain response must still work.
  fixture.chunks.push(chunks[0]);
  vm.runInContext('this.reader = createNotificationPayloadReader_()', context);
  assert.deepEqual(JSON.parse(JSON.stringify(context.reader(fixture.raw))), fixture.expected);
  fixture.chunks = chunks.slice(1);
  vm.runInContext('this.reader = createNotificationPayloadReader_()', context);
  assert.throws(() => context.reader(fixture.raw));
  fixture.chunks = chunks.concat([[chunks[0][0], chunks[0][1], 'corrupted']]);
  vm.runInContext('this.reader = createNotificationPayloadReader_()', context);
  assert.throws(() => context.reader(fixture.raw));
  fixture.chunks = chunks;
  const wrongLength = JSON.parse(fixture.raw);
  wrongLength.length++;
  vm.runInContext('this.reader = createNotificationPayloadReader_()', context);
  assert.throws(() => context.reader(JSON.stringify(wrongLength)));
}
console.log('Python write / Apps Script read, email and alert-log round trip OK');
