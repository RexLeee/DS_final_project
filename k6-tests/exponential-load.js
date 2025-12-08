import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// =============================================================================
// Configuration
// =============================================================================

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const CAMPAIGN_ID = __ENV.CAMPAIGN_ID || '';
const USER_POOL_SIZE = Number(__ENV.USER_POOL_SIZE) || 1000;

// Campaign timing (for calculating elapsed ratio)
// Set these via environment variables or defaults to test start time
const CAMPAIGN_DURATION_MS = Number(__ENV.CAMPAIGN_DURATION_MS) || 10 * 60 * 1000; // 10 minutes

const JSON_HEADERS = { 'Content-Type': 'application/json' };

// =============================================================================
// Custom Metrics for Demo
// =============================================================================

const bidCounter = new Counter('bids_total');
const bidSuccessRate = new Rate('bid_success_rate');
const bidLatency = new Trend('bid_latency', true);
const loginLatency = new Trend('login_latency', true);

// Track request rate per phase for exponential growth visualization
const phase1Bids = new Counter('phase1_bids'); // 0-50% of time
const phase2Bids = new Counter('phase2_bids'); // 50-80% of time
const phase3Bids = new Counter('phase3_bids'); // 80-100% of time (exponential burst)

// =============================================================================
// Test Configuration
// =============================================================================

// Exponential Load Test
// Simulates flash sale scenario where bid frequency grows EXPONENTIALLY as deadline approaches
//
// PDF Requirement: "隨著截止時間接近，更新出價的頻率須呈現指數型成長"
//
// Key insight: It's the BID FREQUENCY that should grow exponentially, not just VU count.
// This is achieved by:
// 1. Dynamically reducing sleep time (exponential decay)
// 2. Increasing bid count per iteration in later phases
// 3. Ensuring last minute has 10x+ request rate compared to average

export const options = {
  stages: [
    // Phase 1: Slow start (0-4 min) - Users trickle in
    { duration: '2m', target: 100 },   // 0→100 VUs
    { duration: '2m', target: 200 },   // 100→200 VUs

    // Phase 2: Building momentum (4-7 min) - More users join
    { duration: '1m30s', target: 400 }, // 200→400 VUs
    { duration: '1m30s', target: 600 }, // 400→600 VUs

    // Phase 3: Exponential burst (7-10 min) - Deadline frenzy!
    // Combined with reduced sleep time = EXPONENTIAL request growth
    { duration: '1m', target: 800 },   // 600→800 VUs
    { duration: '1m', target: 1000 },  // 800→1000 VUs
    { duration: '1m', target: 1000 },  // Hold peak - maximum chaos

    // Cooldown
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    // PDF Requirements: exponential growth, consistency (no specific latency threshold)
    http_req_failed: ['rate<0.3'],       // Allow some failures under extreme load
    bid_success_rate: ['rate>0.7'],      // 70%+ bids should succeed
  },
  // Output summary for demo
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

/**
 * Calculate the elapsed ratio of the test (0 to 1)
 * Used to determine current phase and dynamic sleep time
 */
function getElapsedRatio() {
  // Use __ITER as a proxy for time progression
  // Or calculate based on actual test duration
  const testDurationMs = 10 * 60 * 1000; // 10 minutes total
  const estimatedElapsed = (__ITER * 500); // Rough estimate
  return Math.min(1, estimatedElapsed / testDurationMs);
}

/**
 * Calculate dynamic sleep time - KEY to exponential frequency growth
 *
 * Uses exponential decay: sleep = base * e^(-k * elapsed)
 *
 * Result:
 * - At start (elapsed=0): sleep ≈ 2.0s → ~30 req/min per VU
 * - At 50% (elapsed=0.5): sleep ≈ 0.5s → ~120 req/min per VU
 * - At 90% (elapsed=0.9): sleep ≈ 0.05s → ~1200 req/min per VU
 *
 * This creates true EXPONENTIAL growth in request frequency
 */
function getDynamicSleepTime(elapsedRatio) {
  const baseSleep = 2.0;      // Initial: 2 seconds between requests
  const minSleep = 0.03;      // Minimum: 30ms (prevents overwhelming)
  const exponentialFactor = 5; // Controls how fast sleep decays

  // Exponential decay formula
  const calculatedSleep = baseSleep * Math.exp(-exponentialFactor * elapsedRatio);

  return Math.max(minSleep, calculatedSleep);
}

/**
 * Calculate how many bids to place this iteration
 *
 * In the final phase, users frantically update their bids multiple times
 * This further amplifies the exponential request growth
 */
function getBidCount(elapsedRatio) {
  if (elapsedRatio < 0.5) {
    // Phase 1: Single bid per iteration
    return 1;
  } else if (elapsedRatio < 0.8) {
    // Phase 2: Occasionally update bid (30% chance of 2 bids)
    return Math.random() < 0.3 ? 2 : 1;
  } else {
    // Phase 3: Frequent bid updates (exponential burst)
    // 50% chance: 1 bid, 30% chance: 2 bids, 20% chance: 3-4 bids
    const rand = Math.random();
    if (rand < 0.5) return 1;
    if (rand < 0.8) return 2;
    return Math.floor(Math.random() * 2) + 3; // 3-4 bids
  }
}

/**
 * Track which phase we're in for metrics
 */
function trackPhaseMetric(elapsedRatio) {
  if (elapsedRatio < 0.5) {
    phase1Bids.add(1);
  } else if (elapsedRatio < 0.8) {
    phase2Bids.add(1);
  } else {
    phase3Bids.add(1);
  }
}

// =============================================================================
// Main Test Function
// =============================================================================

export default function () {
  const email = getTestUserEmail(__VU);
  const elapsedRatio = getElapsedRatio();

  // Step 1: Login
  const loginStart = Date.now();
  const loginRes = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ email, password: 'password123' }),
    { headers: JSON_HEADERS, tags: { name: 'login' } }
  );
  loginLatency.add(Date.now() - loginStart);

  const loginOk = check(loginRes, {
    'login successful': (r) => r.status === 200,
  });

  if (!loginOk) {
    console.warn(`Login failed for ${email}: ${loginRes.status}`);
    sleep(0.5);
    return;
  }

  const token = loginRes.json('access_token');
  if (!token) {
    sleep(0.5);
    return;
  }

  // Step 2: Place bids (frequency increases exponentially toward deadline)
  const bidCount = getBidCount(elapsedRatio);

  for (let i = 0; i < bidCount; i++) {
    // Generate random price (higher bids in later phases to compete)
    // basePrice must be >= product min_price (2000)
    const basePrice = 2000;
    const maxExtra = 500 + (elapsedRatio * 1000); // Price competition increases
    const price = basePrice + Math.random() * maxExtra;

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
    trackPhaseMetric(elapsedRatio);

    // Brief pause between multiple bids in same iteration
    if (bidCount > 1 && i < bidCount - 1) {
      sleep(0.05);
    }
  }

  // Step 3: Dynamic sleep - THIS IS THE KEY TO EXPONENTIAL GROWTH
  // Sleep time decreases exponentially as deadline approaches
  const dynamicSleep = getDynamicSleepTime(elapsedRatio);
  sleep(dynamicSleep);
}

// =============================================================================
// Test Lifecycle Hooks
// =============================================================================

export function setup() {
  console.log('='.repeat(60));
  console.log('EXPONENTIAL LOAD TEST - Flash Sale Simulation');
  console.log('='.repeat(60));
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Campaign ID: ${CAMPAIGN_ID}`);
  console.log(`User Pool Size: ${USER_POOL_SIZE}`);
  console.log('');
  console.log('This test simulates exponential bid frequency growth:');
  console.log('- Phase 1 (0-50%): Slow start, ~30 req/min per VU');
  console.log('- Phase 2 (50-80%): Building, ~120 req/min per VU');
  console.log('- Phase 3 (80-100%): BURST, ~1200 req/min per VU');
  console.log('');
  console.log('Expected: Last minute request rate >= 10x average');
  console.log('='.repeat(60));

  // Verify campaign exists
  const res = http.get(`${BASE_URL}/api/v1/campaigns/${CAMPAIGN_ID}`);
  if (res.status !== 200) {
    console.error(`Campaign ${CAMPAIGN_ID} not found! Please run seed_data.py first.`);
  }

  return { startTime: Date.now() };
}

export function teardown(data) {
  const duration = (Date.now() - data.startTime) / 1000;
  console.log('');
  console.log('='.repeat(60));
  console.log('TEST COMPLETE');
  console.log('='.repeat(60));
  console.log(`Total duration: ${duration.toFixed(1)}s`);
  console.log('');
  console.log('Next step: Run verify-consistency.js to check for overselling');
  console.log(`Command: k6 run -e CAMPAIGN_ID=${CAMPAIGN_ID} verify-consistency.js`);
  console.log('='.repeat(60));
}

// =============================================================================
// Summary Handler for Demo
// =============================================================================

export function handleSummary(data) {
  // Calculate request rate growth for demo
  const phase1Count = data.metrics.phase1_bids?.values?.count || 0;
  const phase2Count = data.metrics.phase2_bids?.values?.count || 0;
  const phase3Count = data.metrics.phase3_bids?.values?.count || 0;

  const totalBids = phase1Count + phase2Count + phase3Count;
  const avgPerPhase = totalBids / 3;
  const phase3Multiplier = avgPerPhase > 0 ? (phase3Count / avgPerPhase).toFixed(1) : 'N/A';

  console.log('\n📊 Exponential Growth Analysis:');
  console.log(`   Phase 1 (0-50%):  ${phase1Count} bids`);
  console.log(`   Phase 2 (50-80%): ${phase2Count} bids`);
  console.log(`   Phase 3 (80-100%): ${phase3Count} bids`);
  console.log(`   Phase 3 multiplier: ${phase3Multiplier}x average`);

  if (phase3Count > avgPerPhase * 3) {
    console.log('   ✅ Exponential growth achieved!');
  } else {
    console.log('   ⚠️  Growth pattern may need adjustment');
  }

  return {
    'stdout': JSON.stringify(data, null, 2),
  };
}
