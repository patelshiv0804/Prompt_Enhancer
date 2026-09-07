/**
 * smoke.js — correctness gate, not a capacity test.
 *
 * One VU, one iteration, every read endpoint the capacity scripts will hammer.
 * Run it first: if a path is wrong or a response envelope has changed, that shows
 * up here as a named failed check instead of as a wall of 404s in a ramped run.
 *
 *   bash scripts/bootstrap_test_db.sh
 *   docker compose -f docker-compose.yml -f docker-compose.loadtest.yml up -d web
 *   docker compose -f docker-compose.yml -f docker-compose.loadtest.yml \
 *     run --rm k6 run /scripts/smoke.js
 *
 * The `up -d web` is not optional — `compose run` will reuse a `web` container
 * that is already up on the *development* database. docker-compose.loadtest.yml
 * explains why at length. Run order for the tier: smoke, read-heavy, rate-limit
 * last (it spends the login budget for 60s).
 *
 * Thresholds are absolute on purpose — a smoke run with any failed check is a
 * broken smoke run, and k6 exits non-zero so CI can gate on it.
 *
 * NOT covered here: GET /health and /health/readiness. Both call the LLM
 * provider's health_check() and the embedding model, so they reach Mistral over
 * the network and would measure a third party rather than this application.
 * /health/liveness is the cheap probe and is the one used throughout.
 */
import http from 'k6/http';
import { check, group } from 'k6';

import { API, tagged } from './lib/config.js';
import { authHeaders, authedGet, login } from './lib/auth.js';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    checks: ['rate==1.00'],
    http_req_failed: ['rate==0.00'],
  },
};

export function setup() {
  return { token: login() };
}

/** PaginatedResponse envelope from app/schemas/common.py. */
function isPaginated(response) {
  const body = response.json();
  return (
    body !== null &&
    body.success === true &&
    Array.isArray(body.data) &&
    typeof body.page === 'number' &&
    typeof body.page_size === 'number'
  );
}

export default function (data) {
  const { token } = data;

  group('health', () => {
    const response = http.get(`${API}/health/liveness`, tagged('GET /health/liveness'));
    check(response, {
      'liveness 200': (r) => r.status === 200,
      'liveness reports healthy': (r) => r.json('status') === 'healthy',
    });
  });

  group('unauthenticated access is refused', () => {
    // expectedStatuses keeps this deliberate 401 out of http_req_failed; without
    // it the threshold above would flag the suite's own negative control.
    const response = http.get(`${API}/prompts/`, {
      ...tagged('GET /prompts/ (no auth)'),
      responseCallback: http.expectedStatuses(401),
    });
    check(response, { 'prompts without a token is 401': (r) => r.status === 401 });
  });

  group('authenticated reads', () => {
    const profile = authedGet(token, '/profile/me', 'GET /profile/me');
    check(profile, {
      'profile 200': (r) => r.status === 200,
      'profile has an id': (r) => !!r.json('id'),
    });

    const settings = authedGet(token, '/settings', 'GET /settings');
    check(settings, { 'settings 200': (r) => r.status === 200 });

    const styles = authedGet(token, '/styles', 'GET /styles');
    check(styles, {
      'styles 200': (r) => r.status === 200,
      'styles is a list': (r) => Array.isArray(r.json()),
    });

    const prompts = authedGet(token, '/prompts/?page=1&page_size=5', 'GET /prompts/');
    check(prompts, {
      'prompts 200': (r) => r.status === 200,
      'prompts is a paginated envelope': isPaginated,
    });
  });

  group('catalogue reads', () => {
    // Both of these are readable without a token today; sending one anyway keeps
    // the smoke run representative of what the frontend actually does.
    const templates = http.get(`${API}/templates/?limit=5`, {
      headers: authHeaders(token),
      ...tagged('GET /templates/'),
    });
    check(templates, {
      'templates 200': (r) => r.status === 200,
      'templates is a paginated envelope': isPaginated,
      // Asserted as an invariant, never as a count: the test database is a clone
      // of dev and its row counts drift.
      'templates returns at least one row': (r) => r.json('data').length > 0,
    });

    const models = http.get(`${API}/ai-models/`, {
      headers: authHeaders(token),
      ...tagged('GET /ai-models/'),
    });
    check(models, {
      'ai-models 200': (r) => r.status === 200,
      'ai-models is a paginated envelope': isPaginated,
    });
  });
}
