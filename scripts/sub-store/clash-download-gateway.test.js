'use strict';

const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { test } = require('node:test');
const { createGateway, shouldForce } = require('./clash-download-gateway');

const DOWNLOAD = '/backend/download/collection/%E8%81%9A%E5%90%88';

async function listen(t, server) {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise((resolve) => {
    server.close(resolve);
    server.closeAllConnections();
  }));
  return `http://127.0.0.1:${server.address().port}`;
}

function request(url, { ua = 'mihomo/1.19', method = 'GET', body } = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request(url, { method, headers: { 'user-agent': ua } }, (res) => {
      let data = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => { data += chunk; });
      res.on('error', reject);
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: data }));
    });
    req.on('error', reject);
    req.setTimeout(2000, () => req.destroy(new Error('test request timeout')));
    req.end(body);
  });
}

test('fallback and Party clients get full Meta YAML without changing the general subscription URL', async (t) => {
  const received = [];
  const upstream = await listen(t, http.createServer((req, res) => {
    received.push({ url: req.url, ua: req.headers['user-agent'] });
    const yaml = /^clash/.test(req.headers['user-agent']);
    res.writeHead(200, { 'content-type': yaml ? 'text/yaml' : 'text/plain', 'subscription-userinfo': 'upload=0; download=1' });
    const nodes = req.headers['user-agent'] === 'clash-meta'
      ? '  - name: fixture-anytls\n    type: anytls\n  - name: fixture-hy2\n    type: hysteria2\n'
      : '  - name: fixture-trojan\n    type: trojan\n';
    res.end(yaml ? `proxies:\n${nodes}` : 'dmxlc3M6Ly9maXh0dXJl');
  }));
  const gateway = await listen(t, createGateway({ upstream }));
  for (const ua of ['mihomo/1.19', 'Go-http-client/1.1', 'ShadowRocket', '', 'Mozilla/5.0',
    'ClashParty/2.0.3', 'clash-party/2.0.3', 'MihomoParty/1.8.0']) {
    const path = `${DOWNLOAD}?flag=%E4%B8%AD%E6%96%87`;
    const result = await request(gateway + path, { ua });
    assert.equal(result.status, 200);
    assert.match(result.body, /^proxies:\n/);
    assert.match(result.body, /type: anytls/);
    assert.match(result.body, /type: hysteria2/);
    assert.equal(result.headers['subscription-userinfo'], 'upload=0; download=1');
    assert.deepEqual(received.at(-1), { url: path, ua: 'clash-meta' });
  }
});

test('explicit formats, known clients, API requests and request bodies pass through', async (t) => {
  const upstream = await listen(t, http.createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      res.setHeader('content-type', 'application/json');
      res.end(JSON.stringify({ ua: req.headers['user-agent'], url: req.url, method: req.method, body }));
    });
  }));
  const gateway = await listen(t, createGateway({ upstream }));
  for (const ua of ['mihomo/1.19', 'ClashParty/2.0.3', 'ClashMetaForAndroid/2.11.32.Meta']) {
    for (const suffix of ['?target=ClashMeta', '?platform=ClashMeta', '/ClashMeta', '?target=V2Ray']) {
      const result = JSON.parse((await request(gateway + DOWNLOAD + suffix, { ua })).body);
      assert.equal(result.ua, ua);
      assert.equal(result.url, DOWNLOAD + suffix);
    }
  }
  for (const ua of ['ClashForWindows/0.20.39', 'clash-meta', 'ClashMetaForAndroid/2.11.32.Meta',
    'v2rayN', 'Shadowrocket/2.2.0', 'Surge', 'sing-box/1.11', 'Stash/2.6']) {
    const result = JSON.parse((await request(gateway + DOWNLOAD, { ua })).body);
    assert.equal(result.ua, ua);
  }
  const apiResult = JSON.parse((await request(gateway + '/backend/api/utils/env')).body);
  assert.equal(apiResult.ua, 'mihomo/1.19');
  const post = JSON.parse((await request(gateway + DOWNLOAD, { method: 'POST', body: 'fixture body' })).body);
  assert.deepEqual(post, { ua: 'mihomo/1.19', url: DOWNLOAD, method: 'POST', body: 'fixture body' });
});

test('only download routes without an explicit format are rewritten', () => {
  for (const path of [DOWNLOAD, `${DOWNLOAD}/`, '/backend/download/single-subscription']) {
    assert.equal(shouldForce(path, 'mihomo'), true, path);
  }
  for (const path of ['/backend/api/collections', '/download', `${DOWNLOAD}/preview/extra`, `${DOWNLOAD}/ClashMeta`, '/backend/download/name/ClashMeta']) {
    assert.equal(shouldForce(path, 'mihomo'), false, path);
  }
});

test('upstream HTTP errors remain errors rather than successful subscription responses', async (t) => {
  const upstream = await listen(t, http.createServer((req, res) => {
    res.writeHead(503, { 'retry-after': '60' });
    res.end('temporarily unavailable');
  }));
  const gateway = await listen(t, createGateway({ upstream }));
  const result = await request(gateway + DOWNLOAD);
  assert.equal(result.status, 503);
  assert.equal(result.headers['retry-after'], '60');
  assert.equal(result.body, 'temporarily unavailable');
});

test('an unresponsive upstream returns a bounded 504 response', async (t) => {
  const upstream = await listen(t, http.createServer(() => {}));
  const gateway = await listen(t, createGateway({ upstream, timeoutMs: 50 }));
  const result = await request(gateway + DOWNLOAD);
  assert.equal(result.status, 504);
  assert.match(result.body, /upstream timeout/);
});

test('upstream reset before headers returns 502', async (t) => {
  const upstream = await listen(t, http.createServer((req) => req.socket.destroy()));
  const gateway = await listen(t, createGateway({ upstream }));
  assert.equal((await request(gateway + DOWNLOAD)).status, 502);
});

test('an incomplete upstream response terminates rather than hanging or appending an error to YAML', async (t) => {
  const upstream = await listen(t, http.createServer((req, res) => {
    res.writeHead(200, { 'content-type': 'text/yaml', 'content-length': '1000' });
    res.write('proxies:\n');
    setImmediate(() => res.destroy());
  }));
  const gateway = await listen(t, createGateway({ upstream }));
  await assert.rejects(request(gateway + DOWNLOAD), /aborted|socket hang up/);
});
