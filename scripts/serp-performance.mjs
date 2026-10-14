import {spawn} from 'node:child_process';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {serve} from './funnel-support.mjs';
const [before,after]=process.argv.slice(2),results=[];
const root='marketing/serp-20261008/performance';await mkdir(root,{recursive:true});
for(const page of ['/calculator/','/guides/music-catalog-valuation-2026/']){
  const pair={page};
  for(const [label,directory]of [['before',before],['after',after]]){
    const server=await serve(directory),runs=[];
    try{for(let i=0;i<3;i++){
      const report=`${root}/${label}-${page.replaceAll('/','_')}-${i+1}.json`;
      await new Promise((resolve,reject)=>{
        const child=spawn('npx',['--yes','lighthouse@13.4.1',server.origin+page,'--only-categories=performance','--chrome-flags=--headless=new','--output=json',`--output-path=${report}`,'--blocked-url-patterns=*plausible.io/*,*typeform.com/*,*formspree.io/*,*google-analytics.com/*,*fonts.googleapis.com/*,*fonts.gstatic.com/*','--quiet'],{stdio:'inherit'});
        child.on('error',reject);child.on('exit',c=>c===0?resolve():reject(Error(`Lighthouse ${c}`)));
      });
      const r=JSON.parse(await readFile(report,'utf8'));if(r.runtimeError)throw Error(JSON.stringify(r.runtimeError));
      runs.push({lcp:r.audits['largest-contentful-paint'].numericValue,cls:r.audits['cumulative-layout-shift'].numericValue,score:r.categories.performance.score,version:r.lighthouseVersion,settings:r.configSettings});
    }}finally{server.close();}
    pair[label]={runs,medianLcp:runs.map(r=>r.lcp).sort((a,b)=>a-b)[1]};
  }
  pair.deltaMs=pair.after.medianLcp-pair.before.medianLcp;pair.deltaPercent=pair.deltaMs/pair.before.medianLcp*100;
  pair.regression=pair.deltaMs>250&&pair.deltaPercent>10;results.push(pair);
  console.log(JSON.stringify({page,before:pair.before.medianLcp,after:pair.after.medianLcp,regression:pair.regression}));
  await writeFile(root+'/summary.json',JSON.stringify(results,null,2)+'\n');
}
if(results.some(r=>r.regression))process.exitCode=1;
