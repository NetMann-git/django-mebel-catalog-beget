/* Exercises the shipped gallery scripts: originals load only in the large viewer. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Element {
  constructor() {
    this.dataset = {}; this.events = {}; this.children = []; this.style = {};
    this.classes = new Set();
    this.classList = {add: x => this.classes.add(x), remove: x => this.classes.delete(x), contains: x => this.classes.has(x)};
  }
  addEventListener(name, fn) { this.events[name] = fn; }
  appendChild(child) { this.children.push(child); }
  set innerHTML(value) { this.children = []; }
  get innerHTML() { return ''; }
  focus() {}
  closest() { return this; }
  click() { this.events.click?.({stopPropagation() {}, target: this}); }
}
function productGallery(count) {
  const nodes = new Map();
  const el = key => { if (!nodes.has(key)) nodes.set(key, new Element()); return nodes.get(key); };
  const main = el('main-image'); main.src = '/preview-1.webp'; main.alt = 'Furniture';
  main.dataset = {full: '/original-1.jpg', thumb: '/thumb-1.webp'};
  const thumbs = count > 1 ? [1,2].map(i => {
    const node = new Element(); node.src = `/thumb-${i}.webp`; node.alt = 'Furniture';
    node.dataset = {full: `/original-${i}.jpg`, preview: `/preview-${i}.webp`}; return node;
  }) : [];
  const doc = {
    body: {style: {}}, activeElement: new Element(),
    getElementById: el, createElement: () => new Element(),
    querySelectorAll: selector => selector === '.gallery-thumb-vertical' ? thumbs : [],
    querySelector: selector => selector === '.gallery-thumb-vertical.active' ? null : el(selector),
    addEventListener: (name, fn) => { if (name === 'DOMContentLoaded') fn(); },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/products/js/product_gallery.js'), 'utf8'), {document: doc});
  assert.equal(main.src, '/preview-1.webp');
  assert.equal(el('lightbox-image').src, undefined);
  if (count > 1) { el('next-image-btn').click(); assert.equal(main.src, '/preview-2.webp'); }
  main.click();
  assert.equal(el('lightbox-image').src, `/original-${count > 1 ? 2 : 1}.jpg`);
  assert.deepEqual(el('lightbox-thumbs').children.map(i => i.src), count > 1 ? ['/thumb-1.webp','/thumb-2.webp'] : []);
  el('.lightbox-close').click();
  assert.equal(main.src, `/preview-${count > 1 ? 2 : 1}.webp`);
}
productGallery(1); productGallery(2);
function reviewGallery() {
  const nodes = new Map();
  const el = key => { if (!nodes.has(key)) nodes.set(key, new Element()); return nodes.get(key); };
  el('review-lightbox').querySelector = el;
  const links = [1,2].map(i => {
    const link = new Element(); link.href = `/review-original-${i}.jpg`;
    link.querySelector = () => ({src: `/review-thumb-${i}.webp`}); return link;
  });
  const doc = {body:{style:{}}, getElementById: el, createElement: () => new Element(), querySelectorAll: () => links,
    addEventListener: (name,fn) => { if (name === 'DOMContentLoaded') fn(); }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/products/js/review_lightbox.js'), 'utf8'), {document: doc});
  assert.equal(el('review-lightbox-image').src, undefined);
  links[0].events.click({preventDefault(){}});
  assert.equal(el('review-lightbox-image').src, '/review-original-1.jpg');
  assert.deepEqual(el('review-lightbox-thumbs').children.map(i => i.src), ['/review-thumb-1.webp','/review-thumb-2.webp']);
}
reviewGallery();
console.log('Gallery image sizes: one/multiple product photos, navigation, close, review thumbnails — OK');
