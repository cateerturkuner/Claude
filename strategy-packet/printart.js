const fs=require('fs'); const { chromium } = require('playwright');
(async () => {
  const body=fs.readFileSync('artifact.html','utf8');
  fs.writeFileSync('art-print.html','<!doctype html><html><head><meta charset="utf-8"></head><body>'+body+'</body></html>');
  const b = await chromium.launch(); const pg = await b.newPage();
  await pg.goto('file://' + process.cwd() + '/art-print.html', { waitUntil: 'networkidle' });
  await pg.pdf({ path: process.argv[2], format: 'Letter', printBackground: true, preferCSSPageSize: true, margin: { top: 0, bottom: 0, left: 0, right: 0 } });
  await b.close();
})();
