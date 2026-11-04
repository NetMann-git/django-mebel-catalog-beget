/* шаг 55: observable async dialog behavior, no browser dependencies. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(process.env.INQUIRY_SCRIPT || path.join(__dirname, '../static/appointments/js/car_inquiry.js'), 'utf8');

function fixture() {
  const listeners = new Map();
  const requests = [];
  let doc;
  function element() {
    const handlers = {};
    return {handlers, disabled:false, textContent:'',
      addEventListener(name, fn) { handlers[name] = fn; },
      emit(name, extra={}) { return handlers[name]?.({preventDefault(){}, target:this, ...extra}); },
      focus() { doc.activeElement = this; }};
  }
  const close = element(), trigger = element(), second = element();
  trigger.href = '/inquiry/1/'; second.href = '/inquiry/1/?type=order';
  const input = element();
  let html = '';
  const content = element();
  content.nodes=[]; content.form=null;
  function form(label) {
    const node = element(), button=element();
    node.label=label; node.button=button; node.error=null;
    node.action='/inquiry/1/'; node.matches=s=>s==='.car-inquiry__form';
    node.querySelector=s=>s==='[type="submit"]'?button:node.error;
    node.append=child=>{node.error=child;};
    return node;
  }
  Object.defineProperty(content,'innerHTML',{get(){return html;},set(v){html=v;content.nodes=[];content.form=v.startsWith('<form')?form(v):null;}});
  Object.defineProperty(content,'textContent',{get(){return html;},set(v){html=v;content.form=null;content.nodes=[];}});
  content.contains=node=>content.form===node;
  content.querySelector=()=>input;
  content.append=(...nodes)=>content.nodes.push(...nodes);
  const modal=element();modal.hidden=true;
  modal.querySelector=()=>close;modal.querySelectorAll=()=>[close,input];
  doc={body:{style:{overflow:'clip'}},activeElement:null,
    addEventListener(name,fn){listeners.set(name,fn);},
    querySelectorAll(){return [trigger,second];},
    getElementById(id){return id==='car-inquiry-modal'?modal:content;},createElement:element};
  vm.runInNewContext(source,{document:doc,AbortController,FormData:class{set(){}},
    fetch(url,options){return new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}));}});
  listeners.get('DOMContentLoaded')();
  const response=(text, status=200)=>({ok:status<400,status,text:async()=>text,json:async()=>({success:true,message:text})});
  async function loaded(label='current') {
    const opening=trigger.emit('click');requests.at(-1).resolve(response('<form>'+label+'</form>'));await opening;return content.form;
  }
  return {doc,modal,content,close,trigger,second,input,requests,response,loaded,
    submit:()=>content.emit('submit',{target:content.form}),
    escape:()=>listeners.get('keydown')({key:'Escape'})};
}

test('closing during GET keeps focus on trigger and ignores late content', async()=>{
  const f=fixture();const opening=f.trigger.emit('click');f.close.emit('click');
  const before=f.content.innerHTML;f.requests[0].resolve(f.response('<form>late</form>'));await opening;
  assert.equal(f.modal.hidden,true);assert.equal(f.content.innerHTML,before);
  assert.equal(f.doc.activeElement,f.trigger);assert.equal(f.doc.body.style.overflow,'clip');
});
test('reopening the same trigger ignores the old GET, even if abort races', async()=>{
  const f=fixture();const old=f.trigger.emit('click');f.close.emit('click');const fresh=f.trigger.emit('click');
  f.requests[1].resolve(f.response('<form>fresh</form>'));await fresh;
  f.requests[0].resolve(f.response('<form>old</form>'));await old;
  assert.equal(f.content.innerHTML,'<form>fresh</form>');assert.equal(f.requests[0].options.signal.aborted,true);
});
test('changing request kind ignores old GET errors', async()=>{
  const f=fixture();const old=f.trigger.emit('click');const fresh=f.second.emit('click');
  f.requests[1].resolve(f.response('<form>order</form>'));await fresh;
  f.requests[0].reject(Error('network'));await old;assert.equal(f.content.innerHTML,'<form>order</form>');
});
for (const outcome of ['success','validation','network']) {
  test('late POST '+outcome+' cannot replace a reopened form', async()=>{
    const f=fixture();await f.loaded();const sending=f.submit();const post=f.requests[1];
    assert.equal(post.options.method,'POST');assert.equal(post.options.signal,undefined);
    f.escape();await f.loaded('new request');const current=f.content.form;
    if(outcome==='network')post.reject(Error('network'));
    else post.resolve(f.response(outcome==='validation'?'<form>old errors</form>':'old success',outcome==='validation'?400:200));
    await sending;assert.equal(f.content.form,current);assert.equal(f.content.innerHTML,'<form>new request</form>');
    assert.equal(current.error,null);assert.equal(current.button.disabled,false);
  });
}
test('current POST success shows confirmation and keeps normal close behavior', async()=>{
  const f=fixture();await f.loaded();const sending=f.submit();f.requests[1].resolve(f.response('Заявка получена'));await sending;
  assert.deepEqual(f.content.nodes.map(n=>n.textContent),['Спасибо!','Заявка получена']);
  assert.equal(f.doc.activeElement,f.close);f.escape();assert.equal(f.doc.activeElement,f.trigger);
});
test('current validation and network failures remain visible and retryable', async()=>{
  const f=fixture();await f.loaded();let sending=f.submit();f.requests[1].resolve(f.response('<form>errors</form>',400));await sending;
  assert.equal(f.content.innerHTML,'<form>errors</form>');sending=f.submit();f.requests[2].reject(Error('network'));await sending;
  assert.equal(f.content.form.button.disabled,false);assert.match(f.content.form.error.textContent,/Не удалось отправить/);
});
