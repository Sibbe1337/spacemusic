// Local review only: prevent this preview from sending real leads or analytics.
import http from 'node:http';
import {serve} from './funnel-support.mjs';
const upstream=await serve(process.argv[2]);
const proxy=http.createServer(async(req,res)=>{
  res.setHeader('X-Robots-Tag','noindex, nofollow');
  res.setHeader('Cache-Control','no-store');
  res.setHeader('Content-Security-Policy',"default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self'; frame-src 'none'; form-action 'none'; base-uri 'self'; object-src 'none'");
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405);res.end('Preview is read-only');return;}
  try{
    const r=await fetch(upstream.origin+req.url);res.statusCode=r.status;
    res.setHeader('Content-Type',r.headers.get('content-type')||'text/plain');
    res.end(req.method==='HEAD'?undefined:Buffer.from(await r.arrayBuffer()));
  }catch{res.writeHead(502);res.end('Preview unavailable');}
});
proxy.listen(0,'127.0.0.1',()=>console.log(`Preview: http://127.0.0.1:${proxy.address().port}/guides/music-catalog-valuation-2026/`));
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>{proxy.close();upstream.close();});
