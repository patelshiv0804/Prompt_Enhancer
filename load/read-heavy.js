/**
 * read-heavy.js — capacity for the list endpoints the dashboard actually calls.
 *
 * Ramps to LOAD_VUS and holds, exercising the six reads a signed-in user
 * generates while browsing: profile, settings, style profiles, their prompt list,
 * the template catalogue and the model catalogue. No LLM, no writes — this
 * isolates FastAPI + asyncpg + Postgres, which is the part that has to scale
 * before anything else matters.
 *
 *   LOAD_VUS=25 LOAD_DURATION=1m docker compose \
 *     -f docker-compose.yml -f docker-compose.loadtest.yml run --rm k6 \
 *     run /scripts/read-heavy.js
 *
 * READING THE RESULT
 * ------------------
 * `name` tags alone do NOT split the end-of-test summary — k6 only materialises a
 * per-tag sub-metric when a threshold names it. The per-endpoint entries below
 * exist for that reason: they turn the summary into one line per endpoint so a
 * blown aggregate can be attributed instead of guessed at.
 *
 * Only the aggregate p(95) is an SLO. The per-endpoint ceilings are deliberately
 * loose — they catch an endpoint falling off a cliff, not slow drift — because
 * tightening them without a baseline per deployment shape would just encode this
 * one laptop's numbers as a requirement.
 *
 * Expect the two heavy ones to sit well above /profile/me: the template list joins
 * ai_models, and the prompt list runs a COUNT before its page query. That ordering
 * is visible in a warm 10-VU run (templates 11.7ms > prompts 9.1ms > profile
 * 7.9ms p(95)).
 *
 * At higher VU counts, read the first endpoint of the iteration with suspicion.
 * A fixed think time keeps every VU in lockstep, so whichever request opens the
 * iteration absorbs the queueing delay of the whole herd. With a flat sleep(1) at
 * 25 VUs, /profile/me measured p(95)=695ms against 307ms for the (intrinsically
 * slower) template list; swapping in the randomised sleep at the bottom of the
 * default function brought it to 473ms vs 322ms and lifted throughput from 64 to
 * 77 req/s. Jitter reduces the effect, it does not remove it.
 *
 * RECORD THE WORKER COUNT WITH ANY NUMBER FROM THIS SCRIPT. The in-process rate
 * limiter and the connection pool are both per uvicorn worker
 * ([app/middleware/rate_limit.py:33], db_pool_size=5), so throughput and the
 * effective limit scale with WEB_CONCURRENCY. A p(95) measured at one worker says
 * nothing about a deployment running four.
 */
import { check, group, sleep } from 'k6';
import http from 'k6/http';

import { API, DURATION, RAMP, VUS, tagged } from './lib/config.js';
import { authHeaders, authedGet, login } from './lib/auth.js';

export const options = {
  scenarios: {
    // Cold start is not capacity. The first traffic after a container restart
    // pays for an empty SQLAlchemy pool (5 fresh asyncpg connections), an empty
    // asyncpg statement cache and a cold Postgres buffer cache for this
    // database. Measured on a 1-worker stack, the same 10-VU run came out at
    // p(95)=803ms cold and p(95)=10ms warm — so without this stage the script
    // reports a capacity failure that is really a restart artifact.
    warmup: {
      executor: 'constant-vus',
      vus: 2,
      duration: '5s',
      gracefulStop: '1s',
      // Excluded from the latency SLO by the scenario tag on the threshold below.
      // Errors and failed checks are still gated globally: a 500 while warming up
      // is a defect wherever it happens.
    },
    browsing: {
      executor: 'ramping-vus',
      startVUs: 1,
      startTime: '7s',
      stages: [
        { duration: RAMP, target: VUS },
        { duration: DURATION, target: VUS },
        { duration: RAMP, target: 0 },
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    // A read path that errors at all under load is a defect, not a capacity
    // limit; 1% leaves room for the ramp-down cancelling an in-flight request.
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],

    // The SLO. Scoped to the measured scenario so warm-up samples cannot mask a
    // real regression or manufacture a fake one.
    'http_req_duration{scenario:browsing}': ['p(95)<800'],

    // Attribution, not SLO — see the header. These exist so the summary prints a
    // row per endpoint; the ceiling is loose on purpose.
    'http_req_duration{name:GET /profile/me,scenario:browsing}': ['p(95)<3000'],
    'http_req_duration{name:GET /settings,scenario:browsing}': ['p(95)<3000'],
    'http_req_duration{name:GET /styles,scenario:browsing}': ['p(95)<3000'],
    'http_req_duration{name:GET /prompts/,scenario:browsing}': ['p(95)<3000'],
    'http_req_duration{name:GET /templates/,scenario:browsing}': ['p(95)<3000'],
    'http_req_duration{name:GET /ai-models/,scenario:browsing}': ['p(95)<3000'],
  },
};

export function setup() {
  return { token: login() };
}

export default function (data) {
  const { token } = data;

  group('dashboard shell', () => {
    check(authedGet(token, '/profile/me', 'GET /profile/me'), {
      'profile 200': (r) => r.status === 200,
    });
    check(authedGet(token, '/settings', 'GET /settings'), {
      'settings 200': (r) => r.status === 200,
    });
  });

  group('user data', () => {
    check(authedGet(token, '/styles', 'GET /styles'), {
      'styles 200': (r) => r.status === 200,
    });
    // page_size 20 is the API default and what the frontend history view sends.
    check(authedGet(token, '/prompts/?page=1&page_size=20', 'GET /prompts/'), {
      'prompts 200': (r) => r.status === 200,
    });
  });

  group('catalogue', () => {
    const templates = http.get(`${API}/templates/?limit=20&offset=0`, {
      headers: authHeaders(token),
      ...tagged('GET /templates/'),
    });
    check(templates, { 'templates 200': (r) => r.status === 200 });

    const models = http.get(`${API}/ai-models/`, {
      headers: authHeaders(token),
      ...tagged('GET /ai-models/'),
    });
    check(models, { 'ai-models 200': (r) => r.status === 200 });
  });

  // Think time. Without it each VU is a closed loop hammering as fast as the
  // server answers, which measures the server's ceiling but tells you nothing
  // about how many *users* it supports.
  //
  // Randomised rather than a flat sleep(1): a constant think time leaves every VU
  // synchronised for the whole run, so the first request of each iteration eats
  // the queueing delay of all the others and looks slow for a reason that has
  // nothing to do with that endpoint. Jitter spreads arrivals out, which is also
  // closer to what real users do. Mean is still ~1s, so VU count remains roughly
  // comparable to concurrent users.
  sleep(0.5 + Math.random());
}
