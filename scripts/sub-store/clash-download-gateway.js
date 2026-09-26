#!/usr/bin/env node
/**
 * 通用订阅下载网关。订阅地址保持原样，不追加 platform/target。
 *
 * Sub-Store 按 User-Agent 选格式。mihomo、Go-http-client、空 UA、网页 diyua
 * 的原样字符串 ShadowRocket 会落到 V2Ray，返回 base64（开头 dmxlc3M = vless）。
 * 内核再解析 proxy-provider 即报 cannot unmarshal !!str into provider.ProxySchema。
 *
 * 没有显式格式参数时，把未知 UA 和被误判为普通 Clash 的 Party 客户端 UA
 * 换成 clash-meta，让 Meta/mihomo 内核拿到完整节点 YAML。
 * 其他已识别的客户端和显式 platform/target 保持原样。
 */
'use strict';

const http = require('http');
const https = require('https');
const { URL } = require('url');

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
  return null;
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
  if (!/\/download(?:\/collection)?\/[^/]+\/?$/.test(u.pathname)) return false;
  if (explicitTarget(u.pathname, u.searchParams)) return false;
  // ClashParty/2.0.3 会被上游当作普通 Clash，丢失 AnyTLS/Hysteria2 等节点。
  if (/^(?:clash[ -]?party|mihomo[ -]?party)(?:\/|$)/i.test(ua || '')) return true;
  return platformFromUA(ua) === null;
}

function headerValue(req, name) {
  const v = req.headers[name.toLowerCase()];
  return Array.isArray(v) ? v[0] : (v || '');
}

function createGateway({ upstream = 'http://127.0.0.1:3002', timeoutMs = 30000 } = {}) {
  upstream = new URL(upstream);
  if (!['http:', 'https:'].includes(upstream.protocol)) {
    throw new Error('UPSTREAM must use http or https');
  }
  const transport = upstream.protocol === 'https:' ? https : http;
  return http.createServer((req, res) => {
    const ua = headerValue(req, 'user-agent');
    let force;
    try {
      force = ['GET', 'HEAD'].includes(req.method) && shouldForce(req.url || '/', ua);
    } catch {
      res.writeHead(400, { 'content-type': 'text/plain; charset=utf-8' });
      res.end('invalid download URL\n');
      return;
    }
    const headers = {};
    for (const [key, value] of Object.entries(req.headers)) {
      if (!HOP.has(key.toLowerCase())) headers[key] = value;
    }
    if (force) headers['user-agent'] = 'clash-meta';
    headers.host = upstream.host;

    const out = transport.request({
      protocol: upstream.protocol,
      hostname: upstream.hostname,
      port: upstream.port || (upstream.protocol === 'https:' ? 443 : 80),
      method: req.method,
      path: req.url,
      headers,
    }, (up) => {
      const outHeaders = {};
      for (const [key, value] of Object.entries(up.headers)) {
        if (!HOP.has(key.toLowerCase())) outHeaders[key] = value;
      }
      res.writeHead(up.statusCode || 502, outHeaders);
      up.on('error', (err) => res.destroy(err));
      up.on('aborted', () => res.destroy());
      up.pipe(res);
    });
    let timedOut = false;
    out.setTimeout(timeoutMs, () => {
      timedOut = true;
      out.destroy(new Error('upstream timeout'));
    });
    out.on('error', (err) => {
      if (res.destroyed) return;
      if (res.headersSent) {
        res.destroy(err);
        return;
      }
      res.writeHead(timedOut ? 504 : 502, { 'content-type': 'text/plain; charset=utf-8' });
      res.end(`download gateway upstream error: ${err.message}\n`);
    });
    req.on('aborted', () => out.destroy());
    req.on('error', (err) => out.destroy(err));
    res.on('close', () => {
      if (!res.writableEnded) out.destroy();
    });
    req.pipe(out);
  });
}

if (require.main === module) {
  const upstream = process.env.UPSTREAM || 'http://127.0.0.1:3002';
  const port = Number(process.env.PORT || 3001);
  createGateway({ upstream }).listen(port, '0.0.0.0', () => {
    process.stdout.write(`clash-download-gateway :${port} -> ${upstream}\n`);
  });
}

module.exports = { createGateway, shouldForce };
