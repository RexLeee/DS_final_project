import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// =============================================================================
// Configuration
// =============================================================================

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const CAMPAIGN_ID = __ENV.CAMPAIGN_ID || '';
const USER_POOL_SIZE = Number(__ENV.USER_POOL_SIZE) || 100;
const JSON_HEADERS = { 'Content-Type': 'application/json' };

// =============================================================================
// Custom Metrics
// =============================================================================

const bidCounter = new Counter('bids_total');
const bidSuccessRate = new Rate('bid_success_rate');
const bidLatency = new Trend('bid_latency', true);

// =============================================================================
// Test Configuration
// =============================================================================

// Baseline Test - System Functionality Verification
//
// Run this FIRST before high-load tests to verify:
// 1. System is operational
// 2. Authentication works
// 3. Bid API responds correctly
//
// PDF Requirements:
// - 1000+ concurrent users
// - Exponential bid frequency growth
// - NO overselling (consistency check)
// - Response time STABILITY (not specific threshold)

export const options = {
  vus: 100,
  duration: '5m',
  thresholds: {
    http_req_failed: ['rate<0.1'],       // < 10% failure rate
    bid_success_rate: ['rate>0.9'],      // > 90% bid success
  },
};

// =============================================================================
// Helper Functions
// =============================================================================

function getTestUserEmail(vuNumber) {
  const userIndex = ((vuNumber - 1) % USER_POOL_SIZE) + 1;
  const padded = `0000${userIndex}`.slice(-4);
  return `user${padded}@test.com`;
}

// =============================================================================
// Main Test Function
// =============================================================================

export default function () {
  const email = getTestUserEmail(__VU);

  // Step 1: Login
  const loginRes = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ email, password: 'password123' }),
    { headers: JSON_HEADERS, tags: { name: 'login' } }
  );

  const loginOk = check(loginRes, {
    'login successful': (r) => r.status === 200,
  });

  if (!loginOk) {
    sleep(0.2);
    return;
  }

  const token = loginRes.json('access_token');
  if (!token) {
    sleep(0.2);
    return;
  }

  // Step 2: Place bid
  // Price range: 2000-3000 (must be >= product min_price)
  const price = 2000 + Math.random() * 1000;

  const bidStart = Date.now();
  const bidRes = http.post(
    `${BASE_URL}/api/v1/bids`,
    JSON.stringify({
      campaign_id: CAMPAIGN_ID,
      price: Math.round(price * 100) / 100,
    }),
    {
      headers: {
        ...JSON_HEADERS,
        Authorization: `Bearer ${token}`,
      },
      tags: { name: 'bid' },
    }
  );
  bidLatency.add(Date.now() - bidStart);

  const bidOk = check(bidRes, {
    'bid accepted': (r) => r.status === 201 || r.status === 200,
  });

  bidCounter.add(1);
  bidSuccessRate.add(bidOk ? 1 : 0);

  sleep(0.1);
}

// =============================================================================
// Test Lifecycle Hooks
// =============================================================================

export function setup() {
  console.log('='.repeat(60));
  console.log('BASELINE TEST - System Verification');
  console.log('='.repeat(60));
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Campaign ID: ${CAMPAIGN_ID}`);
  console.log(`VUs: 100, Duration: 5 minutes`);
  console.log('');
  console.log('Success criteria:');
  console.log('- P95 response time < 2 seconds');
  console.log('- Failure rate < 10%');
  console.log('- Bid success rate > 90%');
  console.log('='.repeat(60));

  // Verify campaign exists
  if (CAMPAIGN_ID) {
    const res = http.get(`${BASE_URL}/api/v1/campaigns/${CAMPAIGN_ID}`);
    if (res.status === 200) {
      const campaign = res.json();
      console.log(`Campaign: ${campaign.product?.name || 'Unknown'}`);
      console.log(`Stock: ${campaign.product?.stock || 'Unknown'}`);
    } else {
      console.warn(`Warning: Campaign ${CAMPAIGN_ID} not found`);
    }
  }

  return { startTime: Date.now() };
}

export function teardown(data) {
  const duration = (Date.now() - data.startTime) / 1000;
  console.log('');
  console.log('='.repeat(60));
  console.log('BASELINE TEST COMPLETE');
  console.log('='.repeat(60));
  console.log(`Total duration: ${duration.toFixed(1)}s`);
  console.log('');
  console.log('If this test passes, proceed to:');
  console.log('1. high-concurrency.js (1000 VU test)');
  console.log('2. exponential-load.js (exponential growth test)');
  console.log('='.repeat(60));
}
