// k6 load script — HTTP hot paths + WebSocket, using seeded JWTs.
//
//   BASE_URL=http://localhost:8000 k6 run --vus 200 --duration 3m scripts/load/k6_http_ws.js
//   ramp:  k6 run --stage 1m:200 --stage 3m:1000 --stage 1m:0 scripts/load/k6_http_ws.js
//
// Reads scripts/load/tokens.json (from seed_load_data.py). Each virtual user picks a
// token, hits the dashboard + a rotating analytics endpoint, and opens a WebSocket.

import http from 'k6/http';
import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { SharedArray } from 'k6/data';

const BASE = __ENV.BASE_URL || 'http://localhost:8000';
const WS_BASE = BASE.replace(/^http/, 'ws');

const tokens = new SharedArray('tokens', () => JSON.parse(open('./tokens.json')));

const errRate = new Rate('app_errors');
const apiLatency = new Trend('api_latency_ms', true);

// Rotating GET endpoints (the heavy analytics ones flagged in Q3 + the dashboard).
const ENDPOINTS = [
  '/api/analytics/dashboard-stats',
  '/api/analytics/overview',
  '/api/analytics/performance',
  '/api/analytics/risk-metrics',
  '/api/analytics/quality-breakdown',
  '/api/analytics/behaviour-cost',
  '/api/risk/alerts',
];

export const options = {
  thresholds: {
    app_errors: ['rate<0.01'],          // < 1% errors
    api_latency_ms: ['p(95)<2000'],     // p95 under 2s — tighten to your SLO
  },
};

export default function () {
  const t = tokens[Math.floor(Math.random() * tokens.length)];
  const params = { headers: { Authorization: `Bearer ${t.token}` } };

  // 1) dashboard on every iteration
  let r = http.get(`${BASE}/api/analytics/dashboard-stats`, params);
  apiLatency.add(r.timings.duration);
  errRate.add(r.status >= 400);
  check(r, { 'dashboard 200': (x) => x.status === 200 });

  // 2) a rotating analytics endpoint
  const ep = ENDPOINTS[Math.floor(Math.random() * ENDPOINTS.length)];
  r = http.get(`${BASE}${ep}`, params);
  apiLatency.add(r.timings.duration);
  errRate.add(r.status >= 400);

  // 3) open a WebSocket briefly (fan-out / connection-ceiling test, B6/B7)
  const url = `${WS_BASE}/api/ws/prices?token=${encodeURIComponent(t.token)}`;
  ws.connect(url, {}, (socket) => {
    socket.on('open', () => socket.setTimeout(() => socket.close(), 3000));
    socket.on('error', () => errRate.add(1));
  });

  sleep(Math.random() * 2 + 1); // 1-3s think time
}
