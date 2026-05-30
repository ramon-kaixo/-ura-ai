import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '30s', target: 50 },  // Ramp up to 50 users
    { duration: '1m', target: 100 },   // Ramp up to 100 users
    { duration: '2m', target: 200 },   // Ramp up to 200 users
    { duration: '1m', target: 100 },   // Ramp down to 100 users
    { duration: '30s', target: 0 },    // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% of requests must complete below 500ms
    errors: ['rate<0.1'],              // Error rate must be less than 10%
  },
};

const BASE_URL = 'http://localhost:8000';

export default function () {
  // Test chat endpoint
  let chatRes = http.post(`${BASE_URL}/v2/chat`, JSON.stringify({
    message: 'Hello URA',
    user_id: 'test-user',
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
  
  check(chatRes, {
    'chat status is 200': (r) => r.status === 200,
    'chat response time < 500ms': (r) => r.timings.duration < 500,
  }) || errorRate.add(1);
  
  // Test health endpoint
  let healthRes = http.get(`${BASE_URL}/v2/health`);
  
  check(healthRes, {
    'health status is 200': (r) => r.status === 200,
  }) || errorRate.add(1);
  
  sleep(1);
}
