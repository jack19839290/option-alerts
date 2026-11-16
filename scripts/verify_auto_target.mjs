import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const context=vm.createContext({});
vm.runInContext(fs.readFileSync(new URL('../apps-script/Code.gs',import.meta.url),'utf8'),context);
const writes=[];
const headers=vm.runInContext('APP.AUTO_TARGET_HEADERS',context);
const sheet={getMaxColumns:()=>29,getDataRange:()=>({getValues:()=>[
  headers,[true,'MU',180,360,...Array(20).fill(''),'2026-11-17','["2027-06-17"]','OWNERS',123,'成功']
]}),getLastRow:()=>2,getMaxRows:()=>1000,
getRange:(...range)=>({setValues:values=>writes.push({range,values})})};
context.book={getSheetByName:()=>sheet};
// A web-app invocation has no containing-document lock.
context.LockService={getDocumentLock:()=>null,getScriptLock:()=>({waitLock(){},releaseLock(){}})};
vm.runInContext('getSpreadsheet_=()=>book; formatAutoTargets_=()=>{}; prepareNextRefresh_=()=>{}',context);
context.payload={ticker:'MU',firstEnabled:true,firstDeltaOperator:'≤',firstDeltaThreshold:'.15',
secondEnabled:true,secondDeltaOperator:'≤',secondDeltaThreshold:'.10',
displayType:'CALL',firstOpenInterestMin:'0',secondOpenInterestMin:'0',
secondAnnualReturnOperator:'≤',secondAnnualReturnThreshold:'1',targetEnabled:false};
vm.runInContext('submitAutoTarget(payload)',context);
const write=writes.find(x=>x.range[0]===2);
assert.equal(write.range[3],24,'Do not overwrite cache or ownership columns');
const values=Object.fromEntries(headers.slice(0,24).map((h,i)=>[h,write.values[0][i]]));
assert.equal(values['啟用'],false);
assert.equal(values['顯示類型'],'PUT');
assert.equal(values['第二年化報酬率門檻'],.10);
assert.equal(values['第二年化報酬率條件'],'≥');
assert.equal(values['第一未平倉大於(口)'],500);
assert.equal(values['第二未平倉大於(口)'],500);
console.log('Auto-target server: enforced rules, pause and ownership preservation OK');
