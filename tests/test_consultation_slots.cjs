const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const pending = []; let change;
const date = {value: '', addEventListener: (_, fn) => change = fn};
const time = {value: '', disabled: false, children: [], replaceChildren(...items) {this.children = items; this.value = '';}, add(item) {this.children.push(item);}};
const status = {textContent: ''};
const form = {querySelector: selector => selector.includes('date') ? date : selector.includes('time') ? time : status};
vm.runInNewContext(fs.readFileSync('apps/appointments/static/appointments/js/consultation.js', 'utf8'), {
 document: {addEventListener: (_, fn) => fn(), querySelector: () => form},
 Option: function(text, value) {this.text = text; this.value = value;}, encodeURIComponent,
 fetch: url => new Promise((resolve, reject) => pending.push({url, resolve, reject})),
});
(async () => {
 assert.equal(time.disabled, true);
 date.value = '2027-02-01'; const first = change();
 date.value = '2027-02-02'; const second = change();
 pending[1].resolve({ok: true, json: async () => ({slots: [{time: '11:00', available: true}, {time: '12:00', available: false}]})}); await second;
 assert.equal(time.disabled, false); assert.deepEqual(time.children.map(x => x.value), ['', '11:00']);
 pending[0].resolve({ok: true, json: async () => ({slots: [{time: '10:00', available: true}]})}); await first;
 assert.deepEqual(time.children.map(x => x.value), ['', '11:00']);
 date.value = '2027-02-03'; const empty = change();
 pending[2].resolve({ok: true, json: async () => ({slots: []})}); await empty;
 assert.equal(time.disabled, true); assert.match(status.textContent, /свободного времени нет/);
 date.value = '2027-02-04'; const failed = change(); pending[3].reject(new Error('offline')); await failed;
 assert.equal(time.disabled, true); assert.match(status.textContent, /соединение/);
 console.log('consultation slots: available-only, stale response, no date, no slots, network failure — OK');
})().catch(error => {console.error(error); process.exitCode = 1;});
