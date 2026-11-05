const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../static/products/js/wishlist.js'),'utf8');
function setup(){const events={},attrs={},state=new Set(),label={textContent:''};let response={},removed=false;
const heart={querySelector:()=>({tagName:'svg'}),set textContent(v){throw Error('SVG overwritten with '+v)}};
const button={dataset:{url:'/wishlist/toggle/1/'},querySelector:s=>s==='.heart'?heart:label,closest:()=>null,setAttribute:(k,v)=>attrs[k]=v,classList:{add:k=>state.add(k),remove:k=>state.delete(k)}};
const card={querySelector:()=>button,remove(){removed=true}};
const clear={dataset:{url:'/wishlist/clear/'}};
const doc={addEventListener:(n,f)=>events[n]=f,querySelector:()=>null,querySelectorAll:()=>[],getElementById:id=>id==='clear-wishlist'?clear:id==='wishlist-grid'?{querySelectorAll:()=>[card]}:null};
vm.runInNewContext(code,{document:doc,fetch:()=>Promise.resolve({json:()=>Promise.resolve(response)}),getCookie:()=>'',console});events.DOMContentLoaded();
return{button,attrs,state,label,setResponse:r=>response=r,removed:()=>removed,async click(clear=false){events.click({target:{id:clear?'clear-wishlist':'',closest:s=>clear?null:s==='.wishlist-btn'?button:null},preventDefault(){},stopPropagation(){}});await new Promise(setImmediate);}};}
test('toggle keeps vector heart while updating label and pressed state',async()=>{const h=setup();h.setResponse({is_favorite:true,count:1});await h.click();assert.equal(h.attrs['aria-pressed'],'true');assert.equal(h.label.textContent,'В избранном');h.setResponse({is_favorite:false,count:0});await h.click();assert.equal(h.attrs['aria-pressed'],'false');assert.equal(h.label.textContent,'В избранное');});
test('clear keeps vector heart and resets accessible state',async()=>{const h=setup();h.setResponse({success:true});await h.click(true);assert.equal(h.attrs['aria-pressed'],'false');assert.equal(h.label.textContent,'В избранное');assert.equal(h.removed(),true);});
