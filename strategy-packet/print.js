const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const pg = await b.newPage();
  await pg.goto('file://' + process.cwd() + '/packet.html', { waitUntil: 'networkidle' });
  await pg.pdf({ path: process.argv[2], format: 'Letter', printBackground: true, preferCSSPageSize: true, margin: { top: 0, bottom: 0, left: 0, right: 0 } });
  await b.close();
})();
