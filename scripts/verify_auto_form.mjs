import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';

const browser = await chromium.launch({headless: true, channel: 'chrome'});
try {
  const page = await browser.newPage({viewport: {width: 390, height: 844}});
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.addInitScript(() => {
    window.savedPayloads=[];
    window.google={script:{run:{
      withSuccessHandler(success){return {
        withFailureHandler(failure){return {
          getAutoTarget(ticker){setTimeout(()=>success(ticker==='MU'?{
            '啟用':true,'第一門檻啟用':true,'第二門檻啟用':true,'Email通知':true,
            '第一Delta條件':'≤','第一Delta門檻':.12,'第一Bid-Ask價差條件':'',
            '第一Bid-Ask價差門檻':'','第一年化報酬率條件':'≥','第一年化報酬率門檻':.08,
            '第二Delta條件':'≤','第二Delta門檻':.09,'第二Bid-Ask價差條件':'≤',
            '第二Bid-Ask價差門檻':.15,'備註':'existing'
          }:null),20)},
          submitAutoTarget(payload){window.savedPayloads.push(payload);setTimeout(()=>success({message:'已儲存'}),20)}
        }}
      }}
    }}};
  });
  await page.goto(new URL('../apps-script/AutoIndex.html',import.meta.url).href);
  const ticker = page.locator('#tickerInput');
  await ticker.fill('MU');
  await page.locator('#targetHint').filter({hasText:'已帶出'}).waitFor();
  assert.equal(await page.locator('[name=firstAnnualReturnThreshold]').inputValue(),'8');
  assert.equal(await page.locator('[name=secondSpreadThreshold]').inputValue(),'15');
  await page.locator('[name=firstDeltaThreshold]').fill('0.13');
  await page.locator('#submitButton').click();
  await page.locator('#status.ok').waitFor();
  let saved=await page.evaluate(()=>window.savedPayloads);
  assert.equal(saved.length,1);
  assert.equal(saved[0].firstDeltaThreshold,'0.13');
  assert.equal(saved[0].secondEnabled,true);
  await ticker.fill('NEW');
  await page.locator('#targetHint').filter({hasText:'新標的'}).waitFor();
  assert.equal(await page.locator('[name=firstDeltaThreshold]').inputValue(),'0.15');
  assert.equal(await page.locator('body').evaluate(e=>e.scrollWidth>window.innerWidth),false);
  await page.locator('[name=targetEnabled]').uncheck();
  await page.locator('#submitButton').click();
  await page.waitForFunction(()=>window.savedPayloads.length===2);
  await page.locator('#status.ok').waitFor();
  saved=await page.evaluate(()=>window.savedPayloads);
  assert.equal(saved[1].targetEnabled,false);
  await fs.mkdir(new URL('../outputs/auto-form/', import.meta.url),{recursive:true});
  await page.screenshot({path:fileURLToPath(new URL('../outputs/auto-form/mobile.png',import.meta.url)),fullPage:true});
  await page.setViewportSize({width:820,height:920});
  await page.screenshot({path:fileURLToPath(new URL('../outputs/auto-form/desktop.png',import.meta.url)),fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('Auto form: saved settings, percentage conversion, PUT-only flow, pause, mobile overflow OK');
} finally {await browser.close()}
