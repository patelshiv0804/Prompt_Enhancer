import http from 'k6/http';
import { check, group, sleep } from 'k6';
import exec from 'k6/execution';

const BASE_URL = __ENV.LOAD_BASE_URL || 'http://localhost:8000';
const EMAIL = __ENV.LOAD_EMAIL || 'loadtest@example.com';
const PASSWORD = __ENV.LOAD_PASSWORD || 'LoadTestPassword123!';
const INCLUDE_LLM = (__ENV.LOAD_INCLUDE_LLM || 'false').toLowerCase() === 'true';
const PROMPT = __ENV.LOAD_PROMPT || 'Write a concise product announcement for an AI prompt optimization app.';

export const options = {
  scenarios: {
    steady_profile_traffic: {
      executor: 'constant-vus',
      vus: Number(__ENV.LOAD_VUS || 5),
      duration: __ENV.LOAD_DURATION || '1m',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<1000'],
    checks: ['rate>0.95'],
  },
};

function jsonHeaders(token) {
  return {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  };
}

function registerLoadUser() {
  return http.post(
    `${BASE_URL}/api/v1/auth/register`,
    JSON.stringify({
      email: EMAIL,
      password: PASSWORD,
      display_name: 'Load Test User',
    }),
    jsonHeaders()
  );
}

function loginLoadUser() {
  return http.post(
    `${BASE_URL}/api/v1/auth/login`,
    `username=${encodeURIComponent(EMAIL)}&password=${encodeURIComponent(PASSWORD)}`,
    {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    }
  );
}

export function setup() {
  const health = http.get(`${BASE_URL}/api/health/liveness`);
  check(health, {
    'api is live before load starts': response => response.status === 200,
  });

  const register = registerLoadUser();
  check(register, {
    'load user exists or was created': response => [200, 201, 400, 409].includes(response.status),
  });

  const login = loginLoadUser();
  check(login, {
    'load user can sign in': response => response.status === 200 && !!response.json('access_token'),
  });

  return {
    token: login.json('access_token'),
  };
}

export default function (data) {
  const token = data.token;

  group('health', () => {
    const response = http.get(`${BASE_URL}/api/health/liveness`);
    check(response, {
      'liveness is healthy': r => r.status === 200,
    });
  });

  group('authenticated profile', () => {
    const response = http.get(`${BASE_URL}/api/v1/profile/me`, jsonHeaders(token));
    check(response, {
      'profile loads for signed-in user': r => r.status === 200,
    });
  });

  if (INCLUDE_LLM && exec.scenario.iterationInTest % 5 === 0) {
    group('optional llm analysis', () => {
      const response = http.post(
        `${BASE_URL}/api/v1/analyze`,
        JSON.stringify({ prompt: PROMPT }),
        jsonHeaders(token)
      );
      check(response, {
        'analysis accepts prompt': r => r.status === 200,
      });
    });
  }

  sleep(1);
}
