import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const [beforePath,afterPath]=process.argv.slice(2);
const before=JSON.parse(await readFile(beforePath,'utf8'));
const after=JSON.parse(await readFile(afterPath,'utf8'));
const result=[];
for(const current of after) {
  assert.equal(current.runs.length,3);
  const baseline=before.find(item=>item.page===current.page);
  if(!baseline) {result.push({page:current.page,newPage:true,medianLcp:Math.round(current.medianLcp)});continue;}
  assert.equal(baseline.runs.length,3);
  assert.equal(baseline.runs[0].lighthouse,current.runs[0].lighthouse);
  for(const key of ['formFactor','throttlingMethod','throttling','screenEmulation']) assert.deepEqual(baseline.runs[0].settings[key],current.runs[0].settings[key],`Different test conditions: ${key}`);
  const delta=current.medianLcp-baseline.medianLcp, percent=100*delta/baseline.medianLcp;
  assert(!(delta>250 && percent>10),`Investigate before publication: ${current.page} LCP +${delta}ms / ${percent}%`);
  result.push({page:current.page,beforeMs:Math.round(baseline.medianLcp),afterMs:Math.round(current.medianLcp),deltaMs:Math.round(delta),deltaPercent:Math.round(percent*10)/10});
}
console.log(JSON.stringify({threshold:'Regression must exceed both 10% and 250ms',passed:true,result}));
