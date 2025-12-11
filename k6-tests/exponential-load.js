import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { htmlReport } from 'https://raw.githubusercontent.com/benc-uk/k6-reporter/main/dist/bundle.js';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.1/index.js';

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
// Custom Metrics for Demo
// =============================================================================

const bidCounter = new Counter('bids_total');
const bidSuccessRate = new Rate('bid_success_rate');
const bidLatency = new Trend('bid_latency', true);
const loginLatency = new Trend('login_latency', true);

// Per-stage metrics for exponential growth visualization
const stage1BidLatency = new Trend('stage1_bid_latency', true);
const stage2BidLatency = new Trend('stage2_bid_latency', true);
const stage3BidLatency = new Trend('stage3_bid_latency', true);
const stage1Bids = new Counter('stage1_bids');
const stage2Bids = new Counter('stage2_bids');
const stage3Bids = new Counter('stage3_bids');
const stage1Success = new Rate('stage1_success_rate');
const stage2Success = new Rate('stage2_success_rate');
const stage3Success = new Rate('stage3_success_rate');

// Stage timing configuration (cumulative seconds from test start)
const STAGE_BOUNDARIES = {
  stage1End: 4 * 60,      // 0-4 min: Phase 1 (0→200 VUs)
  stage2End: 7 * 60,      // 4-7 min: Phase 2 (200→600 VUs)
  stage3End: 10 * 60,     // 7-10 min: Phase 3 (600→1000 VUs)
};

// Helper to determine current stage
function getCurrentStage(elapsedSeconds) {
  if (elapsedSeconds < STAGE_BOUNDARIES.stage1End) return 1;
  if (elapsedSeconds < STAGE_BOUNDARIES.stage2End) return 2;
  return 3;
}

// Dynamic sleep time - decreases as deadline approaches (exponential frequency growth)
// PDF Requirement: "隨著截止時間接近，更新出價的頻率須呈現指數型成長"
function getDynamicSleepTime(stage) {
  switch(stage) {
    case 1: return 1.0;   // Phase 1: Slow bidding (1 bid/sec per VU)
    case 2: return 0.4;   // Phase 2: Medium bidding (2.5 bids/sec per VU)
    case 3: return 0.15;  // Phase 3: Frantic bidding (6.7 bids/sec per VU)
    default: return 0.5;
  }
}


// =============================================================================
// Test Configuration
// =============================================================================

// Load Test for Flash Sale Simulation
// PDF Requirement: "模擬至少 1000 個 concurrent users 同時對同一商品進行競標與搶購"
// PDF Requirement: "隨著截止時間接近，更新出價的頻率須呈現指數型成長"
//
// EXPONENTIAL GROWTH achieved through: VU increase × Sleep decrease
// - Phase 1 (0-4 min): 200 VUs × 1.0 req/s = ~200 RPS (baseline)
// - Phase 2 (4-7 min): 600 VUs × 2.5 req/s = ~1500 RPS (7.5x growth)
// - Phase 3 (7-10 min): 1000 VUs × 6.7 req/s = ~6700 RPS (33x growth)

export const options = {
  setupTimeout: '600s',  // 10 minutes - needed for 1000 users pre-login
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
    http_req_failed: ['rate<0.1'],       // Allow up to 10% failures
    bid_success_rate: ['rate>0.85'],     // 85%+ bids should succeed
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
      sleep(0.1);
      return;
    }
  } else {
    // Legacy mode: login on every iteration (not recommended for high concurrency)
    const email = getTestUserEmail(__VU);

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

    token = loginRes.json('access_token');
    if (!token) {
      sleep(0.5);
      return;
    }
  }

  // Step 2: Place a bid
  // Generate random price - basePrice must be >= product min_price (2000)
  const basePrice = 2000;
  const maxExtra = 1000;
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

  const latency = Date.now() - bidStart;
  bidCounter.add(1);
  bidSuccessRate.add(bidOk ? 1 : 0);

  // Track per-stage metrics
  const elapsedSeconds = (Date.now() - data.startTime) / 1000;
  const currentStage = getCurrentStage(elapsedSeconds);

  if (currentStage === 1) {
    stage1BidLatency.add(latency);
    stage1Bids.add(1);
    stage1Success.add(bidOk ? 1 : 0);
  } else if (currentStage === 2) {
    stage2BidLatency.add(latency);
    stage2Bids.add(1);
    stage2Success.add(bidOk ? 1 : 0);
  } else {
    stage3BidLatency.add(latency);
    stage3Bids.add(1);
    stage3Success.add(bidOk ? 1 : 0);
  }

  // Step 3: Dynamic sleep - decreases as deadline approaches
  // Combined with VU growth = EXPONENTIAL request frequency increase
  const sleepTime = getDynamicSleepTime(currentStage);
  sleep(sleepTime);
}

// =============================================================================
// Test Lifecycle Hooks
// =============================================================================

export function setup() {
  console.log('='.repeat(60));
  console.log('LOAD TEST - Flash Sale Simulation');
  console.log('='.repeat(60));
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Campaign ID: ${CAMPAIGN_ID}`);
  console.log(`User Pool Size: ${USER_POOL_SIZE}`);
  console.log(`Pre-login mode: ${PRE_LOGIN ? 'ENABLED (recommended)' : 'DISABLED'}`);
  console.log('');
  console.log('Exponential Growth Strategy (VUs × Frequency):');
  console.log('- Phase 1 (0-4 min): 0→200 VUs × 1.0 req/s = ~200 RPS');
  console.log('- Phase 2 (4-7 min): 200→600 VUs × 2.5 req/s = ~1500 RPS');
  console.log('- Phase 3 (7-10 min): 600→1000 VUs × 6.7 req/s = ~6700 RPS');
  console.log('');
  console.log('Output files (generated after test):');
  console.log('- k6-report-latest.html  (Web UI report)');
  console.log('- k6-results.json        (Raw data for analysis)');
  console.log('='.repeat(60));

  // Verify campaign exists
  const res = http.get(`${BASE_URL}/api/v1/campaigns/${CAMPAIGN_ID}`);
  if (res.status !== 200) {
    console.error(`Campaign ${CAMPAIGN_ID} not found! Please run seed_data.py first.`);
  }

  // Pre-fetch tokens for all users in setup phase
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
  console.log('TEST COMPLETE');
  console.log('='.repeat(60));
  console.log(`Total duration: ${duration.toFixed(1)}s`);
  console.log('');
  console.log('Next steps:');
  console.log('1. Review the Scalability Test Results above');
  console.log('2. Check GCP Console for auto-scaling metrics');
  console.log('3. Run consistency verification:');
  console.log(`   k6 run -e CAMPAIGN_ID=${CAMPAIGN_ID} verify-consistency.js`);
  console.log('='.repeat(60));
}

// =============================================================================
// Summary Handler for Demo
// =============================================================================

export function handleSummary(data) {
  const totalBids = data.metrics.bids_total?.values?.count || 0;
  const successRate = data.metrics.bid_success_rate?.values?.rate || 0;
  const failRate = data.metrics.http_req_failed?.values?.rate || 0;

  // HTTP request duration metrics (Response Time)
  const httpDuration = data.metrics.http_req_duration?.values || {};
  const bidLatencyMetrics = data.metrics.bid_latency?.values || {};

  // Request throughput
  const httpReqs = data.metrics.http_reqs?.values || {};
  const iterations = data.metrics.iterations?.values || {};

  // VUs info
  const vus = data.metrics.vus?.values || {};
  const vusMax = data.metrics.vus_max?.values || {};

  console.log('\n');
  console.log('='.repeat(70));
  console.log('                    SCALABILITY TEST RESULTS');
  console.log('='.repeat(70));

  // === 1. Load Test Overview ===
  console.log('\n[1] Load Test Overview');
  console.log('-'.repeat(70));
  console.log(`   Total Bids Submitted:    ${totalBids}`);
  console.log(`   Total HTTP Requests:     ${httpReqs.count || 0}`);
  console.log(`   Total Iterations:        ${iterations.count || 0}`);
  console.log(`   Max Concurrent VUs:      ${vusMax.max || vus.max || 1000}`);

  // === 2. Response Time Stability (Scalability Key Metric) ===
  console.log('\n[2] Response Time Stability (Scalability Indicator)');
  console.log('-'.repeat(70));
  console.log('   HTTP Request Duration (all requests):');
  console.log(`      Average:    ${(httpDuration.avg || 0).toFixed(2)} ms`);
  console.log(`      Median:     ${(httpDuration.med || 0).toFixed(2)} ms`);
  console.log(`      Min:        ${(httpDuration.min || 0).toFixed(2)} ms`);
  console.log(`      Max:        ${(httpDuration.max || 0).toFixed(2)} ms`);
  console.log(`      p(90):      ${(httpDuration['p(90)'] || 0).toFixed(2)} ms`);
  console.log(`      p(95):      ${(httpDuration['p(95)'] || 0).toFixed(2)} ms`);
  console.log(`      p(99):      ${(httpDuration['p(99)'] || 0).toFixed(2)} ms`);

  console.log('\n   Bid API Latency (bid requests only):');
  console.log(`      Average:    ${(bidLatencyMetrics.avg || 0).toFixed(2)} ms`);
  console.log(`      Median:     ${(bidLatencyMetrics.med || 0).toFixed(2)} ms`);
  console.log(`      p(90):      ${(bidLatencyMetrics['p(90)'] || 0).toFixed(2)} ms`);
  console.log(`      p(95):      ${(bidLatencyMetrics['p(95)'] || 0).toFixed(2)} ms`);
  console.log(`      p(99):      ${(bidLatencyMetrics['p(99)'] || 0).toFixed(2)} ms`);

  // Response time stability assessment
  const p99 = httpDuration['p(99)'] || 0;
  const avg = httpDuration.avg || 1;
  const stabilityRatio = p99 / avg;
  let stabilityStatus = '';
  if (stabilityRatio < 3) {
    stabilityStatus = 'EXCELLENT - Response time very stable under load';
  } else if (stabilityRatio < 5) {
    stabilityStatus = 'GOOD - Response time relatively stable';
  } else if (stabilityRatio < 10) {
    stabilityStatus = 'FAIR - Some response time variance under peak load';
  } else {
    stabilityStatus = 'POOR - High variance, may need optimization';
  }
  console.log(`\n   Stability Assessment: ${stabilityStatus}`);
  console.log(`   (p99/avg ratio: ${stabilityRatio.toFixed(2)}x)`);

  // === 3. Throughput ===
  console.log('\n[3] Throughput');
  console.log('-'.repeat(70));
  console.log(`   Request Rate:     ${(httpReqs.rate || 0).toFixed(2)} req/s`);
  console.log(`   Iteration Rate:   ${(iterations.rate || 0).toFixed(2)} iter/s`);

  // === 3.5 Exponential Growth - Per-Stage Metrics ===
  console.log('\n[3.5] Exponential Growth - Per-Stage Analysis');
  console.log('-'.repeat(70));
  console.log('   Demonstrating request frequency increases with VU count:\n');

  // Stage 1 metrics
  const stage1Latency = data.metrics.stage1_bid_latency?.values || {};
  const stage1BidCount = data.metrics.stage1_bids?.values?.count || 0;
  const stage1SuccessRate = data.metrics.stage1_success_rate?.values?.rate || 0;
  const stage1Duration = 4 * 60; // 4 minutes
  const stage1RPS = stage1BidCount / stage1Duration;

  // Stage 2 metrics
  const stage2Latency = data.metrics.stage2_bid_latency?.values || {};
  const stage2BidCount = data.metrics.stage2_bids?.values?.count || 0;
  const stage2SuccessRate = data.metrics.stage2_success_rate?.values?.rate || 0;
  const stage2Duration = 3 * 60; // 3 minutes
  const stage2RPS = stage2BidCount / stage2Duration;

  // Stage 3 metrics
  const stage3Latency = data.metrics.stage3_bid_latency?.values || {};
  const stage3BidCount = data.metrics.stage3_bids?.values?.count || 0;
  const stage3SuccessRate = data.metrics.stage3_success_rate?.values?.rate || 0;
  const stage3Duration = 3 * 60; // 3 minutes (including cooldown)
  const stage3RPS = stage3BidCount / stage3Duration;

  console.log('   ┌─────────────────────────────────────────────────────────────────┐');
  console.log('   │  Stage      │  VUs      │  Bids    │  RPS     │  Avg RT  │ Success │');
  console.log('   ├─────────────────────────────────────────────────────────────────┤');
  console.log(`   │  Phase 1    │  0→200    │  ${String(stage1BidCount).padStart(6)} │  ${stage1RPS.toFixed(1).padStart(6)} │  ${(stage1Latency.avg || 0).toFixed(0).padStart(5)}ms │  ${(stage1SuccessRate * 100).toFixed(1).padStart(5)}% │`);
  console.log(`   │  Phase 2    │  200→600  │  ${String(stage2BidCount).padStart(6)} │  ${stage2RPS.toFixed(1).padStart(6)} │  ${(stage2Latency.avg || 0).toFixed(0).padStart(5)}ms │  ${(stage2SuccessRate * 100).toFixed(1).padStart(5)}% │`);
  console.log(`   │  Phase 3    │  600→1000 │  ${String(stage3BidCount).padStart(6)} │  ${stage3RPS.toFixed(1).padStart(6)} │  ${(stage3Latency.avg || 0).toFixed(0).padStart(5)}ms │  ${(stage3SuccessRate * 100).toFixed(1).padStart(5)}% │`);
  console.log('   └─────────────────────────────────────────────────────────────────┘');

  // Calculate growth ratios
  const rpsGrowth12 = stage1RPS > 0 ? (stage2RPS / stage1RPS) : 0;
  const rpsGrowth23 = stage2RPS > 0 ? (stage3RPS / stage2RPS) : 0;
  const rpsGrowthTotal = stage1RPS > 0 ? (stage3RPS / stage1RPS) : 0;

  console.log('\n   RPS Growth Analysis:');
  console.log(`      Phase 1 → Phase 2:  ${rpsGrowth12.toFixed(2)}x increase`);
  console.log(`      Phase 2 → Phase 3:  ${rpsGrowth23.toFixed(2)}x increase`);
  console.log(`      Overall Growth:     ${rpsGrowthTotal.toFixed(2)}x (Phase 1 → Phase 3)`);

  // Response time stability across stages
  console.log('\n   Response Time by Stage (p95):');
  console.log(`      Phase 1 (low load):    ${(stage1Latency['p(95)'] || 0).toFixed(0)} ms`);
  console.log(`      Phase 2 (medium load): ${(stage2Latency['p(95)'] || 0).toFixed(0)} ms`);
  console.log(`      Phase 3 (peak load):   ${(stage3Latency['p(95)'] || 0).toFixed(0)} ms`);

  const rtIncrease = stage1Latency['p(95)'] > 0
    ? ((stage3Latency['p(95)'] || 0) / stage1Latency['p(95)']).toFixed(2)
    : 'N/A';
  console.log(`      RT increase under load: ${rtIncrease}x`);

  // === 4. Success Rate ===
  console.log('\n[4] Success Rate');
  console.log('-'.repeat(70));
  console.log(`   Bid Success Rate:     ${(successRate * 100).toFixed(2)}%`);
  console.log(`   HTTP Failure Rate:    ${(failRate * 100).toFixed(2)}%`);

  // === 5. Scalability Notes ===
  console.log('\n[5] Scalability Verification (Manual Check Required)');
  console.log('-'.repeat(70));
  console.log('   To verify auto-scaling behavior, check the following:');
  console.log('');
  console.log('   GCP Cloud Run / GKE:');
  console.log('   - GCP Console > Cloud Run > Service > Metrics');
  console.log('   - Or: GCP Console > Kubernetes Engine > Workloads > Metrics');
  console.log('   - Check: Instance count, CPU utilization, Memory usage');
  console.log('');
  console.log('   Key metrics to observe:');
  console.log('   - CPU usage increase triggers auto-scaling');
  console.log('   - Container/Pod count increases with load');
  console.log('   - Response time remains stable despite load increase');
  console.log('');
  console.log('   Commands for real-time monitoring:');
  console.log('   - kubectl get hpa -w              (watch HPA scaling)');
  console.log('   - kubectl top pods                (CPU/Memory usage)');
  console.log('   - gcloud run services describe <service>');

  console.log('\n' + '='.repeat(70));
  console.log('                         END OF REPORT');
  console.log('='.repeat(70) + '\n');

  // Generate HTML report for Web UI viewing
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const htmlFileName = `k6-report-${timestamp}.html`;

  console.log(`\n📄 HTML Report generated: ${htmlFileName}`);
  console.log('   Open in browser to view interactive results!\n');

  // Generate custom HTML with RPS growth chart
  const customHtmlReport = generateCustomHtmlReport(data);

  return {
    [htmlFileName]: htmlReport(data, {
      title: 'Flash Sale Load Test - Scalability Report',
    }),
    'k6-report-latest.html': customHtmlReport,
    'k6-results.json': JSON.stringify(data, null, 2),
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
  };
}

// =============================================================================
// Custom HTML Report Generator with Charts
// =============================================================================

function generateCustomHtmlReport(data) {
  // Extract metrics
  const stage1Latency = data.metrics.stage1_bid_latency?.values || {};
  const stage2Latency = data.metrics.stage2_bid_latency?.values || {};
  const stage3Latency = data.metrics.stage3_bid_latency?.values || {};

  const stage1BidCount = data.metrics.stage1_bids?.values?.count || 0;
  const stage2BidCount = data.metrics.stage2_bids?.values?.count || 0;
  const stage3BidCount = data.metrics.stage3_bids?.values?.count || 0;

  const stage1Success = (data.metrics.stage1_success_rate?.values?.rate || 0) * 100;
  const stage2Success = (data.metrics.stage2_success_rate?.values?.rate || 0) * 100;
  const stage3Success = (data.metrics.stage3_success_rate?.values?.rate || 0) * 100;

  // Calculate RPS for each stage
  const stage1RPS = stage1BidCount / (4 * 60);
  const stage2RPS = stage2BidCount / (3 * 60);
  const stage3RPS = stage3BidCount / (3 * 60);

  // Overall metrics
  const totalBids = data.metrics.bids_total?.values?.count || 0;
  const overallSuccessRate = (data.metrics.bid_success_rate?.values?.rate || 0) * 100;
  const httpDuration = data.metrics.http_req_duration?.values || {};
  const httpReqs = data.metrics.http_reqs?.values || {};

  return `<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Flash Sale Load Test - Scalability Report</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      color: #eee;
      min-height: 100vh;
      padding: 20px;
    }
    .container { max-width: 1400px; margin: 0 auto; }
    h1 {
      text-align: center;
      font-size: 2.5em;
      margin-bottom: 10px;
      background: linear-gradient(90deg, #00d4ff, #00ff88);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .subtitle { text-align: center; color: #888; margin-bottom: 30px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
    .card {
      background: rgba(255,255,255,0.05);
      border-radius: 16px;
      padding: 24px;
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.1);
    }
    .card h3 { color: #00d4ff; margin-bottom: 16px; font-size: 1.2em; }
    .metric { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.1); }
    .metric:last-child { border-bottom: none; }
    .metric-value { font-weight: bold; color: #00ff88; }
    .chart-container { background: rgba(255,255,255,0.05); border-radius: 16px; padding: 24px; margin-bottom: 20px; }
    .chart-container h3 { color: #00d4ff; margin-bottom: 20px; }
    .chart-wrapper { position: relative; height: 300px; }
    .two-charts { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    @media (max-width: 900px) { .two-charts { grid-template-columns: 1fr; } }
    table { width: 100%; border-collapse: collapse; margin-top: 16px; }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
    th { color: #00d4ff; font-weight: 600; }
    .success { color: #00ff88; }
    .warning { color: #ffaa00; }
    .badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.85em;
      font-weight: bold;
    }
    .badge-success { background: rgba(0,255,136,0.2); color: #00ff88; }
    .badge-warning { background: rgba(255,170,0,0.2); color: #ffaa00; }
    .badge-error { background: rgba(255,68,68,0.2); color: #ff4444; }
    .growth-indicator { font-size: 1.5em; color: #00ff88; }
  </style>
</head>
<body>
  <div class="container">
    <h1>⚡ Flash Sale Load Test Report</h1>
    <p class="subtitle">Scalability & Exponential Growth Analysis</p>

    <!-- Summary Cards -->
    <div class="grid">
      <div class="card">
        <h3>📊 Overview</h3>
        <div class="metric"><span>Total Bids</span><span class="metric-value">${totalBids.toLocaleString()}</span></div>
        <div class="metric"><span>Total HTTP Requests</span><span class="metric-value">${(httpReqs.count || 0).toLocaleString()}</span></div>
        <div class="metric"><span>Max VUs</span><span class="metric-value">1,000</span></div>
        <div class="metric"><span>Test Duration</span><span class="metric-value">~10.5 min</span></div>
      </div>
      <div class="card">
        <h3>✅ Success Rate</h3>
        <div class="metric"><span>Overall Bid Success</span><span class="metric-value ${overallSuccessRate >= 85 ? 'success' : 'warning'}">${overallSuccessRate.toFixed(1)}%</span></div>
        <div class="metric"><span>Phase 1 Success</span><span class="metric-value">${stage1Success.toFixed(1)}%</span></div>
        <div class="metric"><span>Phase 2 Success</span><span class="metric-value">${stage2Success.toFixed(1)}%</span></div>
        <div class="metric"><span>Phase 3 Success</span><span class="metric-value">${stage3Success.toFixed(1)}%</span></div>
      </div>
      <div class="card">
        <h3>⏱️ Response Time</h3>
        <div class="metric"><span>Average</span><span class="metric-value">${(httpDuration.avg || 0).toFixed(0)} ms</span></div>
        <div class="metric"><span>Median (p50)</span><span class="metric-value">${(httpDuration.med || 0).toFixed(0)} ms</span></div>
        <div class="metric"><span>p95</span><span class="metric-value">${(httpDuration['p(95)'] || 0).toFixed(0)} ms</span></div>
        <div class="metric"><span>p99</span><span class="metric-value">${(httpDuration['p(99)'] || 0).toFixed(0)} ms</span></div>
      </div>
      <div class="card">
        <h3>📈 RPS Growth</h3>
        <div class="metric"><span>Phase 1 RPS</span><span class="metric-value">${stage1RPS.toFixed(1)}</span></div>
        <div class="metric"><span>Phase 2 RPS</span><span class="metric-value">${stage2RPS.toFixed(1)}</span></div>
        <div class="metric"><span>Phase 3 RPS</span><span class="metric-value">${stage3RPS.toFixed(1)}</span></div>
        <div class="metric"><span>Total Growth</span><span class="growth-indicator">${(stage1RPS > 0 ? stage3RPS/stage1RPS : 0).toFixed(1)}x ↑</span></div>
      </div>
    </div>

    <!-- RPS Growth Chart -->
    <div class="chart-container">
      <h3>📈 RPS Exponential Growth Curve</h3>
      <div class="chart-wrapper">
        <canvas id="rpsChart"></canvas>
      </div>
    </div>

    <!-- Two Charts Side by Side -->
    <div class="two-charts">
      <div class="chart-container">
        <h3>⏱️ Response Time by Phase</h3>
        <div class="chart-wrapper">
          <canvas id="rtChart"></canvas>
        </div>
      </div>
      <div class="chart-container">
        <h3>📊 Bid Count by Phase</h3>
        <div class="chart-wrapper">
          <canvas id="bidChart"></canvas>
        </div>
      </div>
    </div>

    <!-- Detailed Table -->
    <div class="card">
      <h3>📋 Per-Phase Detailed Metrics</h3>
      <table>
        <thead>
          <tr>
            <th>Phase</th>
            <th>VU Range</th>
            <th>Duration</th>
            <th>Bids</th>
            <th>RPS</th>
            <th>Avg RT</th>
            <th>p95 RT</th>
            <th>Success Rate</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Phase 1</td>
            <td>0 → 200</td>
            <td>4 min</td>
            <td>${stage1BidCount.toLocaleString()}</td>
            <td>${stage1RPS.toFixed(1)}</td>
            <td>${(stage1Latency.avg || 0).toFixed(0)} ms</td>
            <td>${(stage1Latency['p(95)'] || 0).toFixed(0)} ms</td>
            <td><span class="badge ${stage1Success >= 85 ? 'badge-success' : 'badge-warning'}">${stage1Success.toFixed(1)}%</span></td>
          </tr>
          <tr>
            <td>Phase 2</td>
            <td>200 → 600</td>
            <td>3 min</td>
            <td>${stage2BidCount.toLocaleString()}</td>
            <td>${stage2RPS.toFixed(1)}</td>
            <td>${(stage2Latency.avg || 0).toFixed(0)} ms</td>
            <td>${(stage2Latency['p(95)'] || 0).toFixed(0)} ms</td>
            <td><span class="badge ${stage2Success >= 85 ? 'badge-success' : 'badge-warning'}">${stage2Success.toFixed(1)}%</span></td>
          </tr>
          <tr>
            <td>Phase 3</td>
            <td>600 → 1000</td>
            <td>3 min</td>
            <td>${stage3BidCount.toLocaleString()}</td>
            <td>${stage3RPS.toFixed(1)}</td>
            <td>${(stage3Latency.avg || 0).toFixed(0)} ms</td>
            <td>${(stage3Latency['p(95)'] || 0).toFixed(0)} ms</td>
            <td><span class="badge ${stage3Success >= 85 ? 'badge-success' : 'badge-warning'}">${stage3Success.toFixed(1)}%</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Test Result -->
    <div class="card" style="margin-top: 20px; text-align: center;">
      <h3>🎯 Test Result</h3>
      <p style="font-size: 2em; margin: 20px 0;">
        ${overallSuccessRate >= 85
          ? '<span class="badge badge-success" style="font-size: 1em; padding: 10px 30px;">✅ PASSED</span>'
          : '<span class="badge badge-error" style="font-size: 1em; padding: 10px 30px;">❌ FAILED</span>'}
      </p>
      <p style="color: #888;">Threshold: bid_success_rate > 85%</p>
    </div>
  </div>

  <script>
    // RPS Growth Chart
    new Chart(document.getElementById('rpsChart'), {
      type: 'line',
      data: {
        labels: ['Start', 'Phase 1 (2min)', 'Phase 1 (4min)', 'Phase 2 (5.5min)', 'Phase 2 (7min)', 'Phase 3 (8min)', 'Phase 3 (9min)', 'Peak (10min)'],
        datasets: [{
          label: 'RPS (Requests per Second)',
          data: [0, ${(stage1RPS * 0.5).toFixed(1)}, ${stage1RPS.toFixed(1)}, ${(stage1RPS + (stage2RPS - stage1RPS) * 0.5).toFixed(1)}, ${stage2RPS.toFixed(1)}, ${(stage2RPS + (stage3RPS - stage2RPS) * 0.33).toFixed(1)}, ${(stage2RPS + (stage3RPS - stage2RPS) * 0.66).toFixed(1)}, ${stage3RPS.toFixed(1)}],
          borderColor: '#00ff88',
          backgroundColor: 'rgba(0, 255, 136, 0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 6,
          pointHoverRadius: 8
        }, {
          label: 'VUs (Virtual Users)',
          data: [0, 50, 200, 400, 600, 700, 850, 1000],
          borderColor: '#00d4ff',
          backgroundColor: 'rgba(0, 212, 255, 0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 6,
          pointHoverRadius: 8,
          yAxisID: 'y1'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        scales: {
          y: {
            type: 'linear',
            position: 'left',
            title: { display: true, text: 'RPS', color: '#00ff88' },
            grid: { color: 'rgba(255,255,255,0.1)' },
            ticks: { color: '#00ff88' }
          },
          y1: {
            type: 'linear',
            position: 'right',
            title: { display: true, text: 'VUs', color: '#00d4ff' },
            grid: { drawOnChartArea: false },
            ticks: { color: '#00d4ff' }
          },
          x: {
            grid: { color: 'rgba(255,255,255,0.1)' },
            ticks: { color: '#888' }
          }
        },
        plugins: {
          legend: { labels: { color: '#eee' } }
        }
      }
    });

    // Response Time Chart
    new Chart(document.getElementById('rtChart'), {
      type: 'bar',
      data: {
        labels: ['Phase 1 (0-200 VUs)', 'Phase 2 (200-600 VUs)', 'Phase 3 (600-1000 VUs)'],
        datasets: [{
          label: 'Avg Response Time (ms)',
          data: [${(stage1Latency.avg || 0).toFixed(0)}, ${(stage2Latency.avg || 0).toFixed(0)}, ${(stage3Latency.avg || 0).toFixed(0)}],
          backgroundColor: 'rgba(0, 212, 255, 0.7)',
          borderRadius: 8
        }, {
          label: 'p95 Response Time (ms)',
          data: [${(stage1Latency['p(95)'] || 0).toFixed(0)}, ${(stage2Latency['p(95)'] || 0).toFixed(0)}, ${(stage3Latency['p(95)'] || 0).toFixed(0)}],
          backgroundColor: 'rgba(255, 170, 0, 0.7)',
          borderRadius: 8
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            title: { display: true, text: 'Response Time (ms)', color: '#888' },
            grid: { color: 'rgba(255,255,255,0.1)' },
            ticks: { color: '#888' }
          },
          x: {
            grid: { color: 'rgba(255,255,255,0.1)' },
            ticks: { color: '#888' }
          }
        },
        plugins: { legend: { labels: { color: '#eee' } } }
      }
    });

    // Bid Count Chart
    new Chart(document.getElementById('bidChart'), {
      type: 'doughnut',
      data: {
        labels: ['Phase 1', 'Phase 2', 'Phase 3'],
        datasets: [{
          data: [${stage1BidCount}, ${stage2BidCount}, ${stage3BidCount}],
          backgroundColor: ['#00d4ff', '#00ff88', '#ffaa00'],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: '#eee', padding: 20 }
          }
        }
      }
    });
  </script>
</body>
</html>`;
}
