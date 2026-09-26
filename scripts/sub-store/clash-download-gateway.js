#!/usr/bin/env node
/**
 * 通用订阅下载网关。订阅地址保持原样，不追加 platform/target。
 *
 * Sub-Store 按 User-Agent 选格式。mihomo、Go-http-client、空 UA、网页 diyua
 * 的原样字符串 ShadowRocket 会落到 V2Ray，返回 base64（开头 dmxlc3M = vless）。
 * 内核再解析 proxy-provider 即报 cannot unmarshal !!str into provider.ProxySchema。
 *
 * 只在「没有显式格式参数，且 UA 会被当成 V2Ray」时，把转发给 Sub-Store 的
 * User-Agent 换成 clash-meta，让内核拿到可解析的 YAML。已识别的客户端和
 * 显式 platform/target 保持原样。
 */
'use strict';

const http = require('http');
const { URL } = require('url');

const upstream = new URL(process.env.UPSTREAM || 'http://127.0.0.1:3002');
const port = Number(process.env.PORT || 3001);
const FORCE_UA = 'clash-meta';
const HOP = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'te', 'trailers', 'transfer-encoding', 'upgrade', 'host', 'content-length',
]);

function platformFromUA(ua) {
  const raw = ua || '';
  const lower = raw.toLowerCase();
  if (raw.indexOf('Quantumult%20X') !== -1) return 'QX';
  if (lower.indexOf('egern') !== -1) return 'Egern';
  if (raw.indexOf('Surfboard') !== -1) return 'Surfboard';
  if (raw.indexOf('Surge Mac') !== -1) return 'SurgeMac';
  if (raw.indexOf('Surge') !== -1) return 'Surge';
  if (raw.indexOf('Decar') !== -1 || raw.indexOf('Loon') !== -1) return 'Loon';
  if (raw.indexOf('Shadowrocket') !== -1) return 'Shadowrocket';
  if (raw.indexOf('Stash') !== -1) return 'Stash';
  if (lower === 'meta'
      || (lower.indexOf('clash') !== -1 && lower.indexOf('meta') !== -1)
      || lower.indexOf('clash-verge') !== -1
      || lower.indexOf('flclash') !== -1) return 'ClashMeta';
  if (lower.indexOf('clash') !== -1) return 'Clash';
  if (lower.indexOf('v2ray') !== -1) return 'V2Ray';
  if (lower.indexOf('sing-box') !== -1 || lower.indexOf('singbox') !== -1) return 'sing-box';
  return 'V2Ray';
}

function explicitTarget(pathname, searchParams) {
  if (searchParams.has('platform') || searchParams.has('target')) return true;
  const parts = pathname.split('/').filter(Boolean);
  const i = parts.lastIndexOf('download');
  if (i < 0) return false;
  const rest = parts.slice(i + 1);
  if (rest[0] === 'collection') return rest.length >= 3;
  return rest.length >= 2;
}

function shouldForce(reqUrl, ua) {
  const u = new URL(reqUrl, 'http://gateway.local');
  if (!/\/download(?:\/collection)?\/[^/]+/.test(u.pathname)) return false;
  if (explicitTarget(u.pathname, u.searchParams)) return false;
  return platformFromUA(ua) === 'V2Ray';
}

function headerValue(req, name) {
  const v = req.headers[name.toLowerCase()];
  return Array.isArray(v) ? v[0] : (v || '');
}

const server = http.createServer((req, res) => {
  const ua = headerValue(req, 'user-agent');
  const force = shouldForce(req.url || '/', ua);
  const headers = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (!HOP.has(key.toLowerCase())) headers[key] = value;
  }
  if (force) headers['user-agent'] = FORCE_UA;
  headers.host = upstream.host;

  const out = http.request({
    protocol: upstream.protocol,
    hostname: upstream.hostname,
    port: upstream.port || 80,
    method: req.method,
    path: req.url,
    headers,
  }, (up) => {
    const outHeaders = {};
    for (const [key, value] of Object.entries(up.headers)) {
      if (!HOP.has(key.toLowerCase())) outHeaders[key] = value;
    }
    res.writeHead(up.statusCode || 502, outHeaders);
    up.pipe(res);
  });
  out.on('error', (err) => {
    if (!res.headersSent) {
      res.writeHead(502, { 'content-type': 'text/plain; charset=utf-8' });
    }
    res.end(`download gateway upstream error: ${err.message}\n`);
  });
  req.pipe(out);
});

server.listen(port, '0.0.0.0', () => {
  process.stdout.write(`clash-download-gateway :${port} -> ${upstream.href}\n`);
});
