/* Run with Node: exercises the shipped queue script without extra packages. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const {webcrypto} = require('node:crypto');
class Element {
  constructor() { this.events = {}; this.children = []; this.dataset = {}; }
  addEventListener(name, fn) { this.events[name] = fn; }
  querySelectorAll() { return []; }
  append(...items) { this.children.push(...items); }
  replaceChildren() { this.children = []; }
  remove() { this.removed = true; }
}
const nodes = new Map();
const element = name => { if (!nodes.has(name)) nodes.set(name, new Element()); return nodes.get(name); };
const root = element('root');
root.dataset = {prepare: '/prepare', upload: '/upload'};
root.querySelector = element;
root.querySelectorAll = () => [];
element('[name=csrfmiddlewaretoken]').value = 'csrf-test';
const cap = element('gallery-upload-limits');
cap.textContent = JSON.stringify({files: 60, bytes: 1000, total: 10000, pixels: 40000000, gallery: 300});
let calls = [], failBlue = true, saved = new Set(), warnings = [];
const orderInput = {value: '1', defaultValue: '1'};
const savedPhotos = element('[data-saved-photos]');
const firstCard = {}, secondCard = {};
let savedCards = [firstCard, secondCard];
savedPhotos.querySelectorAll = selector => {
  if (selector === '[data-saved-photo]') return savedCards;
  if (selector === '.car-gallery__order input') return [orderInput];
  return [];
};
const navigation = element('window');
navigation.crypto = webcrypto;
const context = {
  document: {getElementById: id => id === 'product-gallery' ? root : element(id), createElement: () => new Element()},
  window: navigation, crypto: webcrypto,
  URL: {createObjectURL: f => f.name, revokeObjectURL() {}},
  Intl, FormData, AbortController, setTimeout, clearTimeout, Uint8Array,
  alert: message => warnings.push(message), confirm: () => true, location: {reload() {}},
  fetch: async (url, options) => {
    assert.equal(options.headers['X-CSRFToken'], 'csrf-test');
    assert.equal(options.method, 'POST');
    const data = options.body;
    let body = {}, ok = true;
    if (url === '/prepare') {
      if (data.get('action') === 'snapshot') {
        ok = false;
        body = {error: 'Тест сбоя обновления'};
      } else {
        body = data.get('action') === 'hashes' ? {ready: true} : {token: 'signed'};
      }
    } else {
      const file = data.get('image'); calls.push(file.name);
      const content = await file.text();
      if (content === 'blue' && failBlue) { failBlue = false; ok = false; body = {error: 'Временная ошибка'}; }
      else { body = {status: saved.has(content) ? 'duplicate' : 'added'}; saved.add(content); }
    }
    return {ok, status: ok ? 200 : 409, headers: {get: () => 'application/json'}, json: async () => body};
  },
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/products/js/gallery-manager.js'), 'utf8'), context);
(async () => {
  const event = attrs => ({...attrs, preventDefault() { this.blocked = true; }});
  const photoAction = {hasAttribute: name => name === 'data-photo-action'};
  savedCards = [secondCard, firstCard];
  savedPhotos.events.input();
  assert.equal(element('[data-pending-order]').hidden, false);
  const click = event({target: {closest: () => photoAction}});
  savedPhotos.events.click(click);
  assert.equal(click.blocked, true);
  assert.match(warnings[0], /Сначала сохраните порядок/);
  const editor = element('product-form');
  editor.events.change();
  const blockedProductSave = event();
  editor.events.submit(blockedProductSave);
  assert.equal(blockedProductSave.blocked, true);
  const leave = event();
  navigation.events.beforeunload(leave);
  assert.equal(leave.blocked, true);
  const save = event({submitter: {hasAttribute: () => false}});
  element('.car-gallery__saved-form').events.submit(save);
  assert.equal(save.blocked, undefined);
  navigation.events.pageshow();
  savedCards = [firstCard, secondCard];
  savedPhotos.events.input();
  assert.equal(element('[data-pending-order]').hidden, true);
  const leaveWithProductChanges = event();
  navigation.events.beforeunload(leaveWithProductChanges);
  assert.equal(leaveWithProductChanges.blocked, true);
  const productSave = event();
  editor.events.submit(productSave);
  assert.equal(productSave.blocked, undefined);
  const leaveAfterSubmit = event();
  navigation.events.beforeunload(leaveAfterSubmit);
  assert.equal(leaveAfterSubmit.blocked, undefined);
  navigation.events.pageshow();
  savedPhotos.append = (...photos) => { savedCards = photos; };
  element('.car-gallery__saved-form').querySelector = selector => element(selector);
  element('[data-save-order]').focus = () => {};
  savedCards = [secondCard, firstCard];
  orderInput.value = '9';
  element('[data-reset-order]').events.click();
  assert.deepEqual(savedCards, [firstCard, secondCard]);
  assert.equal(orderInput.value, '1');
  assert.equal(element('[data-pending-order]').hidden, true);

  const clean = event({target: {closest: () => photoAction}});
  savedPhotos.events.click(clean);
  assert.equal(clean.blocked, undefined);


  element('[data-files]').files = [
    new File(['blue'], 'photo_10.jpg'), new File(['red'], 'photo_2.jpg'),
    new File(['red'], 'photo_11.jpg'), new File(['remove'], 'photo_20.jpg'),
  ];
  element('[data-files]').events.change();
  const cards = element('[data-queue]').children;
  assert.deepEqual(cards.map(c => c.children[1].textContent), ['photo_2.jpg','photo_10.jpg','photo_11.jpg','photo_20.jpg']);
  cards[3].children[4].events.click();
  assert.match(element('[data-summary]').textContent, /Выбрано: 3/);
  await element('[data-start]').events.click();
  assert.deepEqual(calls, ['photo_2.jpg','photo_10.jpg','photo_11.jpg']);
  assert.equal(element('[data-status]').textContent, 'Добавлено: 1, пропущено дублей: 1, ошибок: 1.');
  assert.equal(element('[data-refresh]').hidden, false);
  assert.match(element('[data-sync-status]').textContent, /Тест сбоя обновления/);
  await element('[data-retry]').events.click();
  assert.deepEqual(calls, ['photo_2.jpg','photo_10.jpg','photo_11.jpg','photo_10.jpg']);
  assert.equal(element('[data-status]').textContent, 'Добавлено: 2, пропущено дублей: 1, ошибок: 0.');
  console.log('Queue checks passed: numeric sort, removal, sequential requests, duplicates, partial failure, retry.');
})().catch(error => { console.error(error); process.exitCode = 1; });
