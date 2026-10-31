import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../receiver/cloudflare-worker.js',import.meta.url),'utf8')
  .replace('export default {','globalThis.receiver = {');
const context={Response,URL,TextEncoder,Date,Promise,Set,Array,JSON,Number,String};
vm.runInNewContext(source,context);
const store=new Map();
const env={
 INGEST_KEY:'test-ingest-secret',READ_KEY:'test-read-secret',
 REPORTS:{
  async get(k,format){const v=store.get(k);return format==='json'&&v?JSON.parse(v):v??null},
  async put(k,v){store.set(k,v)},
  async list(){return {keys:[],list_complete:true}}
 }
};
async function post(part){
 return context.receiver.fetch(new Request('https://example.test/ingest/test-ingest-secret',{
   method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(part)}),env)
}
const base={scanId:'testscan123',placeId:3623096087,partCount:2,objects:[]};
const one={...base,partIndex:1,scanStats:{recorded:1,complete:true}};
const two={...base,partIndex:2,objects:[{path:'Workspace.Part',class:'Part'}]};
assert.equal((await post(one)).status,201);
assert.equal((await post(one)).status,200);
assert.equal((await post({...one,scanStats:{recorded:99,complete:true}})).status,409);
assert.equal((await post({...two,placeId:123})).status,409);
assert.equal((await post(two)).status,201);
const url='https://example.test/reports/test-read-secret/testscan123/integrity';
const result=await context.receiver.fetch(new Request(url),env);
const integrity=await result.json();
assert.equal(integrity.complete,true);
assert.equal(integrity.indexedObjects,1);
assert.equal(integrity.receivedParts,2);
assert.equal(integrity.duplicateObjectKeys,0);
console.log('PASS receiver duplicate, conflict, count and integrity checks');
