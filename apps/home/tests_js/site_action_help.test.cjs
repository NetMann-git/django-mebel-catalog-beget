const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/home/js/site-action-help.js'), 'utf8');
function setup() {
    const events = {}, controls = [];
    let hint, observer;
    function element(kind, text, attrs = {}) {
        const classes = new Set(kind === 'compare' ? ['compare-btn'] : kind === 'wishlist' ? ['wishlist-btn'] : []);
        const node = {
            dataset: {}, textContent: text, style: {}, isConnected: true, disabled: false,
            parentElement: {open: false}, classList: {contains: key => classes.has(key), add: key => classes.add(key)},
            hasAttribute: key => Object.hasOwn(attrs, key),
            getAttribute: key => Object.hasOwn(attrs, key) ? attrs[key] : null,
            setAttribute: (key, value) => {attrs[key] = String(value);},
            removeAttribute: key => {delete attrs[key];},
            getBoundingClientRect: () => kind === 'hint' ? {width:300,height:100} : {left:350,top:500,bottom:544},
            contains: other => other === node,
            closest: selector => selector.includes('[hidden]') ? (attrs.hidden ? node : null) : node,
            matches: selector => selector === '.compare-btn' ? kind === 'compare' :
                selector === '.wishlist-btn' ? kind === 'wishlist' : selector === 'a[href]' ? kind === 'link' :
                selector === 'summary' ? kind === 'summary' : false,
        };
        return node;
    }
    const document = {
        createElement() {hint = element('hint', '');return hint;},
        body:{appendChild(node) {controls.push(node);}},
        addEventListener(name, callback) {events[name] = callback;}
    };
    class MutationObserver {constructor(callback) {observer = callback;} observe() {} disconnect() {}}
    vm.runInNewContext(source, {document, MutationObserver, URL,
        location:{href:'https://lustrid.test/catalog/',origin:'https://lustrid.test'},
        window:{innerWidth:375,innerHeight:844,addEventListener(){}},
        clearTimeout(){},setTimeout(callback){callback();return 1;}});
    events.DOMContentLoaded();
    return {element, events, get hint(){return hint;}, changed(){observer();},
        focus(node){events.focusin({target:node});}};
}
test('comparison state is explained and existing accessible description survives Escape', () => {
    const h = setup(), b = h.element('compare','Добавить к сравнению',{'aria-describedby':'existing'});
    h.focus(b); assert.match(h.hint.textContent,/Добавить это изделие/);
    assert.equal(b.getAttribute('aria-describedby'),'existing site-action-help');
    h.events.keydown({key:'Escape'});
    assert.equal(h.hint.hidden,true);assert.equal(b.getAttribute('aria-describedby'),'existing');
});
test('late comparison response refreshes the visible explanation', () => {
    const h=setup(), b=h.element('compare','Добавить к сравнению');h.focus(b);
    b.classList.add('active');h.changed();assert.match(h.hint.textContent,/Убрать это изделие/);
});
test('AJAX-created control needs no separate initialization', () => {
    const h=setup(), first=h.element('link','Каталог',{href:'/catalog/'});h.focus(first);
    h.events['catalog:updated']();assert.equal(h.hint.hidden,true);
    const replacement=h.element('wishlist','В избранное');h.focus(replacement);
    assert.match(h.hint.textContent,/Сохранить это изделие в избранном/);
});
test('private data is not read from input values or URL query parameters', () => {
    const h=setup(), a=h.element('link','Каталог',{href:'/catalog/?q=secret-value'});h.focus(a);
    assert.doesNotMatch(h.hint.textContent,/secret-value/);
});
test('tooltip is clamped inside a narrow viewport', () => {
    const h=setup(), a=h.element('link','Контакты',{href:'/contacts/'});h.focus(a);
    assert.equal(h.hint.style.left,'63px');assert.equal(h.hint.style.top,'554px');
});
test('native title is restored and duplicate native tooltip is suppressed', () => {
    const h=setup(), b=h.element('button','Действие',{title:'Подробное описание действия'});h.focus(b);
    assert.equal(b.getAttribute('title'),null);assert.equal(h.hint.textContent,'Подробное описание действия');
    h.events.keydown({key:'Escape'});assert.equal(b.getAttribute('title'),'Подробное описание действия');
});
test('disabled and hidden controls do not get an interactive tooltip', () => {
    const h=setup(), b=h.element('button','Действие');b.disabled=true;h.focus(b);assert.equal(h.hint.hidden,true);
    const hidden=h.element('button','Скрыто',{hidden:'true'});h.focus(hidden);assert.equal(h.hint.hidden,true);
});
test('external link hint describes the actual target instead of promising a local action', () => {
    const h=setup(), a=h.element('link','Telegram',{href:'https://t.me/example'});h.focus(a);
    assert.match(h.hint.textContent,/внешний ресурс/);assert.match(h.hint.textContent,/Telegram/);
});

test('login link explains opening a form rather than submitting credentials', () => {
    const h=setup(), a=h.element('link','Войти',{href:'/users/login/'});h.focus(a);
    assert.match(h.hint.textContent,/Открыть форму входа/);
});
test('download explains file transfer rather than navigation', () => {
    const h=setup(), a=h.element('link','Прайс',{href:'/price.pdf',download:''});h.focus(a);
    assert.match(h.hint.textContent,/Скачать файл/);
});

test('touch activation does not cover the next control with a focus tooltip', () => {
    const h=setup(), b=h.element('compare','Добавить к сравнению');
    h.events.pointerdown({pointerType:'touch',target:b});h.focus(b);assert.equal(h.hint.hidden,true);
    h.events.keydown({key:'Tab'});h.focus(b);assert.equal(h.hint.hidden,false);
});
