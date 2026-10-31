// Lycoles Universal Inspector v11.0.0 — multipart ingest and integrity receiver.
// Cloudflare KV binding: REPORTS; secrets: INGEST_KEY, READ_KEY.
// Deploy this Worker separately; a GitHub commit does not deploy Cloudflare.
const TTL = 60 * 60 * 24 * 30;
const respond = (value, status=200) => new Response(JSON.stringify(value), {
  status, headers: {"content-type":"application/json","cache-control":"no-store"}
});
const validId = s => typeof s==="string" && /^[a-zA-Z0-9_-]{8,100}$/.test(s);
async function inspect(env, scanId, partCount) {
  const rows = await Promise.all(Array.from({length:partCount},(_,i)=>
    env.REPORTS.get("scan:"+scanId+":part:"+(i+1),"json")));
  const missing = [], seen = new Set(), duplicates = [];
  let totalObjects=0, uniqueObjects=0, metadata=null, interactionEvents=0, identityErrors=[];
  rows.forEach((part,i)=>{
    if(!part) {missing.push(i+1);return;}
    if(part.scanId!==scanId || part.partIndex!==i+1 || part.partCount!==partCount)
      identityErrors.push(i+1);
    if(!metadata && part.scanStats) metadata=part;
    if(Array.isArray(part.interactionHistoryChunk)) interactionEvents+=part.interactionHistoryChunk.length;
    for(const obj of part.objects||[]) {
      totalObjects++;
      const key=String(obj.path||"")+"#"+String(obj.scanOrdinal||"");
      if(seen.has(key)) {if(duplicates.length<25) duplicates.push(key);}
      else {seen.add(key);uniqueObjects++;}
    }
  });
  const expected=metadata?.scanStats?.recorded ?? metadata?.scanStats?.recordedObjects ?? null;
  const complete=missing.length===0 && identityErrors.length===0
    && !!metadata && metadata.scanStats.complete===true
    && expected!==null && expected===totalObjects
    && uniqueObjects===totalObjects;
  return {scanId,partCount,receivedParts:partCount-missing.length,missingParts:missing,
    indexedObjects:totalObjects,uniqueObjectKeys:uniqueObjects,duplicateObjectKeys:totalObjects-uniqueObjects,
    identityErrors,
    duplicateExamples:duplicates,expectedObjects:expected,interactionHistoryEvents:interactionEvents,
    complete,integrityStatus:!complete?"incomplete":duplicates.length?"duplicates-detected":"verified",
    note:"Object uniqueness uses path plus scanOrdinal; client-visible evidence is not server proof."};
}
export default {
 async fetch(request,env) {
  const url=new URL(request.url), p=url.pathname.split("/").filter(Boolean);
  if(!env.REPORTS||!env.INGEST_KEY||!env.READ_KEY) return respond({error:"Receiver not configured"},503);
  if(request.method==="POST"&&p[0]==="ingest"&&p.length===2) {
   if(p[1]!==env.INGEST_KEY) return respond({error:"Unauthorized"},401);
   const body=await request.text();
   if(new TextEncoder().encode(body).length>150000) return respond({error:"Too large"},413);
   let part;try{part=JSON.parse(body)}catch{return respond({error:"Invalid JSON"},400)}
   if(!part||!Number.isInteger(part.placeId)||!Array.isArray(part.objects)) return respond({error:"Invalid report"},400);
   if(!validId(part.scanId)||!Number.isInteger(part.partIndex)||!Number.isInteger(part.partCount)
      ||part.partCount<1||part.partCount>2000||part.partIndex<1||part.partIndex>part.partCount)
      return respond({error:"Invalid multipart identity"},400);
   const id=part.scanId+":"+part.partIndex;
   const key="scan:"+part.scanId+":part:"+part.partIndex;
   const previousMeta=await env.REPORTS.get("scan:"+part.scanId+":meta","json");
   if(previousMeta && (previousMeta.placeId!==part.placeId || previousMeta.partCount!==part.partCount))
      return respond({error:"Conflicting scan metadata"},409);
   const previous=await env.REPORTS.get(key,"json");
   if(previous && (previous.placeId!==part.placeId || previous.partCount!==part.partCount))
      return respond({error:"Conflicting part identity"},409);
   if(previous) {
     if(JSON.stringify(previous)!==JSON.stringify(part))
       return respond({error:"Conflicting duplicate part"},409);
     return respond({ok:true,id,scanId:part.scanId,partIndex:part.partIndex,
       partCount:part.partCount,receivedObjects:part.objects.length,duplicate:true},200);
   }
   await env.REPORTS.put(key,body,{expirationTtl:TTL});
   const metaKey="scan:"+part.scanId+":meta";
   const meta={scanId:part.scanId,placeId:part.placeId,version:part.version,
    gameName:part.gameName,partCount:part.partCount,receivedAt:new Date().toISOString()};
   await env.REPORTS.put(metaKey,JSON.stringify(meta),{expirationTtl:TTL});
   return respond({ok:true,id,scanId:part.scanId,partIndex:part.partIndex,
     partCount:part.partCount,receivedObjects:part.objects.length},201);
  }
  if(request.method==="GET"&&p[0]==="reports"&&p[1]===env.READ_KEY) {
   if(p.length===4 && p[3]==="integrity") {
    const meta=await env.REPORTS.get("scan:"+p[2]+":meta","json");
    if(!meta)return respond({error:"Scan not found"},404);
    return respond(await inspect(env,p[2],meta.partCount));
   }
   if(p.length===4 && p[3]==="manifest") {
    const meta=await env.REPORTS.get("scan:"+p[2]+":meta","json");
    if(!meta)return respond({error:"Scan not found"},404);
    return respond({metadata:meta,integrity:await inspect(env,p[2],meta.partCount)});
   }
   if(p.length===4 && /^part-[0-9]+$/.test(p[3])) {
    const part=await env.REPORTS.get("scan:"+p[2]+":part:"+Number(p[3].slice(5)));
    return part?new Response(part,{headers:{"content-type":"application/json","cache-control":"no-store"}}):respond({error:"Part not found"},404);
   }
   if(p.length===3) {
    const meta=await env.REPORTS.get("scan:"+p[2]+":meta","json");
    if(meta)return respond({metadata:meta,integrity:await inspect(env,p[2],meta.partCount)});
    const legacy=await env.REPORTS.get("report:"+p[2]);
    return legacy?new Response(legacy,{headers:{"content-type":"application/json"}}):respond({error:"Not found"},404);
   }
   const list=await env.REPORTS.list({prefix:"scan:",limit:1000});
   const scans=list.keys.filter(x=>x.name.endsWith(":meta")).map(x=>x.name.slice(5,-5));
   return respond({scans,hasMore:!list.list_complete});
  }
  return respond({error:"Not found"},404);
 }
};
