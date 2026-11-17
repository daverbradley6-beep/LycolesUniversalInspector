import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../receiver/cloudflare-worker.js',import.meta.url),'utf8')
  .replace('export default {','globalThis.receiver = {');
const context={Response,URL,TextEncoder,TextDecoder,Date,Promise,Set,Array,JSON,Number,String,crypto};
vm.runInNewContext(source,context);
const store=new Map();
let failMetaOnce=false;
const env={
 INGEST_KEY:'test-ingest-secret',READ_KEY:'test-read-secret',
 REPORTS:{
  async get(k,format){const v=store.get(k);return format==='json'&&v?JSON.parse(v):v??null},
  async put(k,v){
   if(failMetaOnce&&k.endsWith(':meta')){failMetaOnce=false;throw new Error('metadata write failed')}
   store.set(k,v)
  },
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
const invalidUtf8Response=await context.receiver.fetch(new Request(
  'https://example.test/ingest/test-ingest-secret',{
    method:'POST',headers:{'content-type':'application/json'},body:new Uint8Array([0xff])}),env);
assert.equal(invalidUtf8Response.status,400);
assert.equal((await invalidUtf8Response.json()).error,'Invalid UTF-8');

const firstAckResponse=await post(one);
assert.equal(firstAckResponse.status,201);
const firstAck=await firstAckResponse.json();
assert.match(firstAck.sha256,/^[a-f0-9]{64}$/);
store.delete('scan:testscan123:part:1:sha256');
const legacyPartResult=await context.receiver.fetch(new Request(
  'https://example.test/reports/test-read-secret/testscan123/part-1'),env);
assert.equal(legacyPartResult.headers.get('x-lycoles-content-sha256'),null);
assert.equal(store.has('scan:testscan123:part:1:sha256'),false);
const backfillAckResponse=await post(one);
assert.equal(backfillAckResponse.status,200);
const backfillAck=await backfillAckResponse.json();
assert.equal(backfillAck.sha256,firstAck.sha256);
assert.equal(store.get('scan:testscan123:part:1:sha256'),firstAck.sha256);
assert.equal((await post({...one,scanStats:{recorded:99,complete:true}})).status,409);
assert.equal((await post({...two,placeId:123})).status,409);
assert.equal((await post(two)).status,201);
const duplicateAckResponse=await post(two);
assert.equal(duplicateAckResponse.status,200);
const duplicateAck=await duplicateAckResponse.json();
assert.match(duplicateAck.sha256,/^[a-f0-9]{64}$/);
assert.equal(store.get('scan:testscan123:part:2:sha256'),duplicateAck.sha256);
const partResult=await context.receiver.fetch(new Request(
  'https://example.test/reports/test-read-secret/testscan123/part-2'),env);
assert.equal(partResult.headers.get('x-lycoles-content-sha256'),duplicateAck.sha256);

const metadataResult=await context.receiver.fetch(new Request(
  'https://example.test/reports/test-read-secret/testscan123/metadata'),env);
const metadata=await metadataResult.json();
assert.equal(metadata.metadata.scanId,base.scanId);
assert.equal(metadata.metadata.placeId,base.placeId);
assert.equal(metadata.metadata.partCount,base.partCount);

const url='https://example.test/reports/test-read-secret/testscan123/integrity';
const result=await context.receiver.fetch(new Request(url),env);
const integrity=await result.json();
assert.equal(integrity.complete,true);
assert.equal(integrity.placeId,base.placeId);

assert.equal(integrity.indexedObjects,1);
assert.equal(integrity.receivedParts,2);
assert.equal(integrity.duplicateObjectKeys,0);

const retryPart={scanId:'retryscan123',placeId:3623096087,partCount:1,
  partIndex:1,objects:[]};
failMetaOnce=true;
await assert.rejects(post(retryPart),/metadata write failed/);
assert.equal(store.has('scan:retryscan123:part:1'),true);
assert.equal(store.has('scan:retryscan123:meta'),false);
const retryAck=await post(retryPart);
assert.equal(retryAck.status,200);
assert.equal(store.has('scan:retryscan123:meta'),true);
console.log('PASS receiver duplicate, conflict, count and integrity checks');
