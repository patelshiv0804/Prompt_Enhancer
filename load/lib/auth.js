/**
 * One login for the whole test run.
 *
 * WHY setup() AND NOT PER-VU LOGIN
 * --------------------------------
 * POST /api/v1/auth/login is guarded by `sensitive_rate_limiter` — 5 requests
 * per 60 seconds per (path, client IP) [app/middleware/rate_limit.py:112]. Every
 * VU shares the k6 container's IP, so a per-VU or per-iteration login would trip
 * that limiter within the first second and the run would measure the limiter
 * instead of the application. k6's setup() runs exactly once and its return value
 * is handed to every VU, which is the natural fit: one token, shared.
 *
 * The token is a JWT, so sharing it costs nothing at the server — it is verified
 * per request, never looked up.
 */
import http from 'k6/http';
import { fail } from 'k6';

import { API, EMAIL, PASSWORD } from './config.js';

/** The login endpoint takes an OAuth2 password grant: form-encoded, not JSON. */
export function login() {
  const response = http.post(
    `${API}/auth/login`,
    { username: EMAIL, password: PASSWORD },
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, tags: { name: 'POST /auth/login' } },
  );

  // Aborting in setup() is the right failure mode: without a token every
  // subsequent check would report a 401 and the run would look like an
  // application fault rather than a missing fixture. The two causes need
  // different fixes, so they get different messages.
  if (response.status === 429) {
    fail(
      'login was rate-limited (429) before the run could start. /auth/login allows ' +
        '5 requests per 60s per (path, IP) and that budget is hardcoded, so the ' +
        'loadtest profile does not raise it. rate-limit.js deliberately spends the ' +
        'whole budget: run it last, or wait 60s. Docker hands the next k6 container ' +
        'the same bridge IP, so a fresh container does not get a fresh bucket.',
    );
  }
  if (response.status !== 200) {
    // This account exists only in prompt_enhancer_test — scripts/ensure_test_user.py
    // upserts it there and the development database has no row for it. A 401 here
    // therefore usually means the API is still pointed at the dev database.
    fail(
      `login as ${EMAIL} failed with ${response.status}: ${String(response.body).slice(0, 200)}\n` +
        'Is the API pointed at the test database, and has scripts/bootstrap_test_db.sh run?\n' +
        'Switching profiles needs `up -d web`, not just `run k6` — see docker-compose.loadtest.yml.',
    );
  }

  const token = response.json('access_token');
  if (!token) fail('login returned 200 but no access_token');
  return token;
}

/** Bearer auth. get_current_user_id accepts the header or the cookie; the header
 *  avoids depending on k6's per-VU cookie jar behaviour. */
export function authHeaders(token) {
  return { Authorization: `Bearer ${token}` };
}

/** Convenience: a tagged GET with auth applied. */
export function authedGet(token, path, name) {
  return http.get(`${API}${path}`, {
    headers: authHeaders(token),
    tags: { name: name || `GET ${path}` },
  });
}
