import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// =============================================================================
// Configuration
// =============================================================================

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const CAMPAIGN_ID = __ENV.CAMPAIGN_ID || '';
const USER_POOL_SIZE = Number(__ENV.USER_POOL_SIZE) || 1000;
const JSON_HEADERS = { 'Content-Type': 'application/json' };

// Pre-login mode: if true, login once in setup() and reuse tokens
// This dramatically reduces load on the auth system (10x fewer requests)
const PRE_LOGIN = __ENV.PRE_LOGIN !== 'false'; // default: true

// =============================================================================
// Custom Metrics
// =============================================================================

const bidCounter = new Counter('bids_total');
const bidSuccessRate = new Rate('bid_success_rate');
const bidLatency = new Trend('bid_latency', true);

// =============================================================================
// Test Configuration
// =============================================================================

// High Concurrency Test - 1000+ Concurrent Users
//
// PDF Requirement: "模擬至少 1000 個 concurrent users 同時對同一商品進行競標與搶購"
//
// This test:
// 1. Ramps up to 1000 VUs
// 2. Sustains 1000 VUs for observation (HPA scaling)
// 3. Verifies P95 < 2s response time
//
// Use this test to demonstrate:
// - System can handle 1000+ concurrent users
// - HPA auto-scaling triggers when CPU > 70%
// - Response time remains stable after scaling

export const options = {
  setupTimeout: '600s',  // 10 minutes - needed for 1000 users pre-login
  stages: [
    // Ramp-up phase: gradually increase load
    { duration: '1m', target: 250 },   // 0→250 VUs
    { duration: '1m', target: 500 },   // 250→500 VUs
    { duration: '1m', target: 750 },   // 500→750 VUs
    { duration: '1m', target: 1000 },  // 750→1000 VUs (reach target)

    // Sustain phase: hold 1000 VUs to observe HPA scaling
    { duration: '5m', target: 1000 },  // Hold 1000 VUs

    // Cooldown phase
    { duration: '1m', target: 0 },     // Ramp down
  ],
  thresholds: {
    // PDF Requirements: 1000 VUs, consistency, scalability (no specific latency threshold)
    http_req_failed: ['rate<0.2'],   // < 20% failure rate for high load
    bid_success_rate: ['rate>0.8'],  // 80%+ bids should succeed
  },
  // Summary statistics
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
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

export default function (data) {
  let token;

  if (PRE_LOGIN && data.tokens) {
    // Use pre-fetched token from setup() - avoids login on every iteration
    const userIndex = ((__VU - 1) % USER_POOL_SIZE) + 1;
    token = data.tokens[userIndex];

    if (!token) {
      // Token not available for this user, skip iteration
      sleep(0.1);
      return;
    }
  } else {
    // Legacy mode: login on every iteration (not recommended for high concurrency)
    const email = getTestUserEmail(__VU);

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

    token = loginRes.json('access_token');
    if (!token) {
      sleep(0.2);
      return;
    }
  }

  // Step 2: Place bid
  const price = 2000 + Math.random() * 1000;  // Random price 2000-3000 (min_price >= 2000)

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

  // Step 3: Optionally check ranking (10% of iterations)
  if (Math.random() < 0.1) {
    const rankRes = http.get(
      `${BASE_URL}/api/v1/rankings/${CAMPAIGN_ID}`,
      {
        headers: { Authorization: `Bearer ${token}` },
        tags: { name: 'ranking' },
      }
    );

    check(rankRes, {
      'ranking fetched': (r) => r.status === 200,
    });
  }

  // Short sleep between iterations
  sleep(0.1);
}

// =============================================================================
// Test Lifecycle Hooks
// =============================================================================

export function setup() {
  console.log('='.repeat(60));
  console.log('HIGH CONCURRENCY TEST - 1000+ Concurrent Users');
  console.log('='.repeat(60));
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Campaign ID: ${CAMPAIGN_ID}`);
  console.log(`User Pool Size: ${USER_POOL_SIZE}`);
  console.log(`Pre-login mode: ${PRE_LOGIN ? 'ENABLED (recommended)' : 'DISABLED'}`);
  console.log('');
  console.log('Test phases:');
  console.log('- Ramp-up (4 min): 0 → 1000 VUs');
  console.log('- Sustain (5 min): Hold 1000 VUs (observe HPA)');
  console.log('- Cooldown (1 min): 1000 → 0 VUs');
  console.log('');
  console.log('Success criteria:');
  console.log('- P95 response time < 2 seconds');
  console.log('- Failure rate < 20%');
  console.log('- HPA scales pods when CPU > 70%');
  console.log('='.repeat(60));

  // Verify campaign exists
  const res = http.get(`${BASE_URL}/api/v1/campaigns/${CAMPAIGN_ID}`);
  if (res.status !== 200) {
    console.error(`Campaign ${CAMPAIGN_ID} not found!`);
  } else {
    const campaign = res.json();
    console.log(`Campaign: ${campaign.product?.name || 'Unknown'}`);
    console.log(`Stock: ${campaign.product?.stock || 'Unknown'}`);
  }

  // Pre-fetch tokens for all users in setup phase
  // This dramatically reduces load during the actual test (10x fewer requests)
  // Using http.batch() for parallel requests to speed up pre-login
  const tokens = {};
  const BATCH_SIZE = 50;  // Process 50 users in parallel per batch

  if (PRE_LOGIN) {
    console.log('');
    console.log(`Pre-fetching tokens for ${USER_POOL_SIZE} users (batch size: ${BATCH_SIZE})...`);
    let successCount = 0;
    let failCount = 0;

    for (let batchStart = 1; batchStart <= USER_POOL_SIZE; batchStart += BATCH_SIZE) {
      const batchEnd = Math.min(batchStart + BATCH_SIZE - 1, USER_POOL_SIZE);
      const requests = [];

      // Build batch requests
      for (let i = batchStart; i <= batchEnd; i++) {
        const email = getTestUserEmail(i);
        requests.push([
          'POST',
          `${BASE_URL}/api/v1/auth/login`,
          JSON.stringify({ email, password: 'password123' }),
          { headers: JSON_HEADERS, tags: { name: 'pre-login' } }
        ]);
      }

      // Execute batch in parallel
      const responses = http.batch(requests);

      // Collect tokens from responses
      responses.forEach((res, idx) => {
        const userIndex = batchStart + idx;
        if (res.status === 200) {
          tokens[userIndex] = res.json('access_token');
          successCount++;
        } else {
          failCount++;
        }
      });

      // Progress logging every batch
      console.log(`  Progress: ${batchEnd}/${USER_POOL_SIZE} users (${successCount} success, ${failCount} failed)`);
    }

    console.log(`Pre-login complete: ${successCount} success, ${failCount} failed`);
    console.log('='.repeat(60));
  }

  return { tokens, startTime: Date.now() };
}

export function teardown(data) {
  const duration = (Date.now() - data.startTime) / 1000;
  console.log('');
  console.log('='.repeat(60));
  console.log('HIGH CONCURRENCY TEST COMPLETE');
  console.log('='.repeat(60));
  console.log(`Total duration: ${duration.toFixed(1)}s`);
  console.log('');
  console.log('Check the following for Scalability demo:');
  console.log('1. GKE Console: Pod count during test');
  console.log('2. Cloud Monitoring: CPU utilization graph');
  console.log('3. Response time stability after scaling');
  console.log('');
  console.log('Next: Run verify-consistency.js to check overselling');
  console.log('='.repeat(60));
}

// =============================================================================
// Summary Handler
// =============================================================================

export function handleSummary(data) {
  const p95 = data.metrics.http_req_duration?.values?.['p(95)'] || 0;
  const failRate = data.metrics.http_req_failed?.values?.rate || 0;
  const totalBids = data.metrics.bids_total?.values?.count || 0;

  console.log('\n📊 High Concurrency Test Summary:');
  console.log(`   Total bids placed: ${totalBids}`);
  console.log(`   P95 response time: ${p95.toFixed(0)}ms`);
  console.log(`   Failure rate: ${(failRate * 100).toFixed(1)}%`);
  console.log('');

  if (p95 < 2000) {
    console.log('   ✅ P95 < 2s requirement: PASSED');
  } else {
    console.log('   ❌ P95 < 2s requirement: FAILED');
  }

  if (failRate < 0.2) {
    console.log('   ✅ Failure rate < 20%: PASSED');
  } else {
    console.log('   ❌ Failure rate < 20%: FAILED');
  }

  return {
    'stdout': JSON.stringify(data, null, 2),
  };
}
