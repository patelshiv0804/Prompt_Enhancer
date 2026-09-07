/**
 * Shared configuration for every k6 script in this directory.
 *
 * Everything is env-driven so one script can be pointed at a different target,
 * VU count or duration without editing it. Defaults describe the local docker
 * stack running under docker-compose.loadtest.yml, where k6 joins the compose
 * network and reaches the API as `web`.
 *
 * SAFETY: LOAD_BASE_URL must point at a stack whose DATABASE_URL is the *test*
 * database. Load traffic authenticates as a real account and mutates rows; the
 * development database is read-only for the whole test suite, and the loadtest
 * compose override is what redirects the API away from it.
 */

export const BASE_URL = (__ENV.LOAD_BASE_URL || 'http://web:8000').replace(/\/+$/, '');
export const API = `${BASE_URL}/api/v1`;

/**
 * The account scripts/ensure_test_user.py upserts into the test database. Cloned
 * users carry bcrypt hashes of unknown plaintext, so this is the only account
 * that can actually log in.
 */
export const EMAIL = __ENV.LOAD_EMAIL || 'test@promptiq.test';
export const PASSWORD = __ENV.LOAD_PASSWORD || 'TestPassword123!';

/** Capacity knobs, read by read-heavy.js. */
export const VUS = Number(__ENV.LOAD_VUS || 10);
export const DURATION = __ENV.LOAD_DURATION || '30s';
export const RAMP = __ENV.LOAD_RAMP || '10s';

/**
 * Standard summary tags. `name` is what splits http_req_duration per endpoint in
 * the summary; without it k6 folds every URL into one aggregate and a slow
 * endpoint hides behind fast ones.
 */
export function tagged(name, extra = {}) {
  return { tags: { name, ...extra } };
}
