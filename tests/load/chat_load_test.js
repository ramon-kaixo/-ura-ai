import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 10 },   // Ramp up to 10 users
    { duration: '5m', target: 50 },   // Ramp up to 50 users
    { duration: '10m', target: 100 }, // Stay at 100 users
    { duration: '5m', target: 50 },   // Scale down to 50 users
    { duration: '2m', target: 0 },    // Scale down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests must complete below 500ms
    http_req_failed: ['rate<0.1'],     // Error rate must be less than 10%
    errors: ['rate<0.1'],
  },
};

const BASE_URL = 'http://localhost:8000';

export default function () {
  // Health check
  const healthRes = http.get(`${BASE_URL}/v2/health`);
  check(healthRes, {
    'health status is 200': (r) => r.status === 200,
  }) || errorRate.add(1);

  sleep(1);

  // Chat endpoint
  const chatPayload = JSON.stringify({
    message: `Test message ${__VU}-${__ITER}`,
    user_id: `user-${__VU}`,
  });

  const chatParams = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const chatRes = http.post(`${BASE_URL}/v2/chat`, chatPayload, chatParams);
  
  check(chatRes, {
    'chat status is 200': (r) => r.status === 200,
    'chat has response': (r) => r.json('response') !== undefined,
    'chat response time < 500ms': (r) => r.timings.duration < 500,
  }) || errorRate.add(1);

  sleep(Math.random() * 3 + 1); // Random sleep between 1-4 seconds
}

export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'summary.json': JSON.stringify(data),
  };
}
