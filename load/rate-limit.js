/**
 * rate-limit.js — proves the limiter still fires.
 *
 * The capacity scripts raise the coarse global limit to 100000 so that the
 * limiter is not what they measure. That leaves a gap: nothing would notice if
 * limiting stopped working altogether. This script closes it.
 *
 *   docker compose -f docker-compose.yml -f docker-compose.loadtest.yml \
 *     run --rm k6 run /scripts/rate-limit.js
 *
 * WHAT IS BEING PROBED
 * --------------------
 * POST /api/v1/auth/login carries `Depends(sensitive_rate_limiter)` — 5 requests
 * per 60s per (path, client IP), constructed with those numbers **hardcoded** at
 * [app/middleware/rate_limit.py:112] and attached unconditionally at
 * [app/api/v1/auth.py:74]. Neither RATE_LIMIT_ENABLED nor RATE_LIMIT_MAX_REQUESTS
 * affects it; those configure only the coarse global RateLimitMiddleware
 * [app/main.py:76-81]. So this script gives the same answer under either compose
 * profile, and the loadtest override cannot mask a regression here.
 *
 * The limiter is a dependency, so it runs *before* the handler: requests inside
 * the budget reach the handler and come back 401, requests over it are rejected
 * with 429 and the handler never runs. That difference is the assertion.
 *
 * Credentials are for an account that does not exist, so this never touches the
 * real test user, and there is no failed-attempt counter in AuthService.login to
 * trip.
 *
 * >>> RUN THIS LAST. <<<
 * The limiter's state is a module-level dict with a 60s sliding window, so once
 * this script has spent the budget, /auth/login from this IP keeps answering 429
 * for up to a minute. A fresh `compose run` does not escape it — Docker hands the
 * next k6 container the same bridge address. smoke.js and read-heavy.js log in
 * during setup() and abort the whole run on a non-200, so running either within
 * 60s of this fails for a reason that is not a defect. (Verified: smoke.js exits
 * 107 with "login was rate-limited" when run immediately after this script.)
 *
 * WHY "at least one 429" AND NOT "the 6th request is a 429"
 * --------------------------------------------------------
 * That dict is per *process*, so with N uvicorn workers the effective budget is
 * N x 5 and the OS decides which worker sees each request. Asserting an exact
 * index would fail on any stack with WEB_CONCURRENCY > 1. The effective budget is
 * reported as a metric instead — read `first_429_at_request` in the summary and
 * compare it against the worker count.
 */
import http from 'k6/http';
import { check } from 'k6';
import { Counter, Gauge } from 'k6/metrics';

import { API } from './lib/config.js';

/** How many logins to attempt. Must exceed 5 x WEB_CONCURRENCY to see a 429. */
const ATTEMPTS = Number(__ENV.LOAD_ATTEMPTS || 15);

const firstRejectionAt = new Gauge('first_429_at_request');
const rejected = new Counter('rate_limited_responses');
const allowed = new Counter('allowed_responses');

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    checks: ['rate==1.00'],
    // Every response is an expected 401 or 429 (see responseCallback below), so
    // anything counted as failed here is a genuine transport or 5xx fault.
    http_req_failed: ['rate==0.00'],
    rate_limited_responses: ['count>0'],
  },
};

export default function () {
  // 401 and 429 are both expected outcomes; without this every request would be
  // counted as failed and http_req_failed would be meaningless.
  const expected = http.expectedStatuses(401, 429);

  let firstRejection = 0;
  let authenticated = 0;
  const unexpected = [];

  for (let i = 1; i <= ATTEMPTS; i += 1) {
    const response = http.post(
      `${API}/auth/login`,
      { username: 'ratelimit-probe@promptiq.test', password: 'not-a-real-password' },
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        tags: { name: 'POST /auth/login (limiter probe)' },
        responseCallback: expected,
      },
    );

    if (response.status === 429) {
      rejected.add(1);
      if (firstRejection === 0) firstRejection = i;
    } else if (response.status === 401) {
      allowed.add(1);
    } else {
      if (response.status === 200) authenticated += 1;
      unexpected.push(`#${i} -> ${response.status}`);
    }
  }

  // 0 means "never rejected", which the rate_limited_responses threshold already
  // catches; recording it anyway keeps the gauge present in every summary.
  firstRejectionAt.add(firstRejection);

  check(null, {
    'the limiter rejected at least one request with 429': () => firstRejection > 0,
    'every other response was the expected 401': () => unexpected.length === 0,
    // A wrong-credentials login must never succeed, limiter or not.
    'no probe was ever authenticated': () => authenticated === 0,
  });

  if (firstRejection === 0) {
    console.error(
      `No 429 in ${ATTEMPTS} login attempts against ${API}/auth/login. Either the ` +
        'route dependency was removed, or the budget is larger than the attempt ' +
        'count because the API runs multiple workers — the limiter state is ' +
        'per-process, so raise LOAD_ATTEMPTS above 5 x WEB_CONCURRENCY.',
    );
  } else {
    console.log(
      `first 429 at request #${firstRejection} of ${ATTEMPTS} — effective budget ` +
        `${firstRejection - 1} requests/60s (5 per uvicorn worker)`,
    );
  }
  if (unexpected.length) console.error(`unexpected statuses: ${unexpected.join(', ')}`);
}
