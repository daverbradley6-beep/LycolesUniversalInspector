// Cloudflare Worker receiver for Lycoles Universal Inspector.
// Bind a KV namespace named REPORTS and configure INGEST_KEY and READ_KEY secrets.
// POST /ingest/<INGEST_KEY> accepts a JSON report.
// GET /reports/<READ_KEY> returns recent report metadata; GET /reports/<READ_KEY>/<id> returns one report.
// Never commit secrets or reports to the public repository.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const parts = url.pathname.split("/").filter(Boolean);
    const json = (data, status = 200) => new Response(JSON.stringify(data), {
      status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }
    });
    if (!env.REPORTS || !env.INGEST_KEY || !env.READ_KEY) return json({error:"Receiver not configured"},503);
    if (request.method === "POST" && parts[0] === "ingest" && parts.length === 2) {
      if (parts[1] !== env.INGEST_KEY) return json({error:"Unauthorized"},401);
      if (Number(request.headers.get("content-length") || 0) > 150000) return json({error:"Too large"},413);
      const body = await request.text();
      if (body.length > 150000) return json({error:"Too large"},413);
      let report;
      try { report = JSON.parse(body); } catch { return json({error:"Invalid JSON"},400); }
      if (!report || typeof report !== "object" || !Number.isInteger(report.placeId) || !Array.isArray(report.objects)) {
        return json({error:"Invalid report"},400);
      }
      const id = Date.now().toString(36) + "-" + crypto.randomUUID();
      await env.REPORTS.put("report:" + id, JSON.stringify({receivedAt:new Date().toISOString(),report}), {expirationTtl: 60*60*24*30});
      return json({ok:true,id},201);
    }
    if (request.method === "GET" && parts[0] === "reports" && parts[1] === env.READ_KEY) {
      if (parts.length === 3) {
        const stored = await env.REPORTS.get("report:" + parts[2]);
        return stored ? new Response(stored,{headers:{"Content-Type":"application/json","Cache-Control":"no-store"}}) : json({error:"Not found"},404);
      }
      const list = await env.REPORTS.list({prefix:"report:",limit:100});
      return json({reports:list.keys.map(x=>x.name.slice(7)),hasMore:!list.list_complete});
    }
    return json({error:"Not found"},404);
  }
};
