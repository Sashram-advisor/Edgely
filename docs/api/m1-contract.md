# M1 contract — identity and access (Workstream A)

Status: **frozen for Milestone 1.** Field names and error codes change only by PR.

Owner: Workstream A. Consumers: Workstream B (catalog/enrollment) and Workstream C
(bootstrap script, tests). If this file and the code disagree, the code is wrong.

---

## Authentication

Every endpoint below requires a Supabase access token:

```
Authorization: Bearer <supabase-access-token>
```

The token is verified in `app/core/auth_provider.py` (HS256 shared secret or
ES256/RS256 via JWKS). The `sub` claim is the external identity. No endpoint
accepts a user id from the body or query string.

| Situation | Status | Body |
|---|---|---|
| Missing/invalid/expired token | `401` | `{"detail": "..."}` |
| Valid token, but no `users` row yet | `403` | `{"detail": "No platform user exists for this login"}` |
| Valid token and row exists | `200` / `201` | see below |

`403` is not a bug: the client is expected to call `POST /users/me` once, then
retry the original request.

---

## Shared dependency

```python
# app/core/dependencies.py
async def current_user_id(
    auth: AuthenticatedUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> int: ...
```

Implementation: `SELECT id FROM users WHERE external_auth_id = :auth_id`.
Returns `int`. Raises `HTTPException(403, "No platform user exists for this login")`
when the row is missing. This is the **only** supported way for a route to learn
who the caller is; do not re-query `external_auth_id` in a route.

---

## Endpoints

### `POST /users/me` — provision (idempotent)

No request body is required. If sent, unknown fields are ignored (`user_id` in a
body has no effect).

Provisioning runs in one transaction:

1. `INSERT INTO users (...) ON CONFLICT (external_auth_id) DO UPDATE SET email = EXCLUDED.email RETURNING id`
2. `INSERT INTO learner_profiles (user_id) ... ON CONFLICT (user_id) DO NOTHING`
3. commit, then read the joined row

Rules:

- `external_auth_id` is the upsert key. `users.email` is **not unique** and must
  never be a conflict target.
- A custom `display_name` is never overwritten by a later login.
- `role` is always `learner` on creation; the token cannot set it.
- If the token has no email, a deterministic placeholder
  `<sub>@unknown.invalid` is stored (`users.email` is `NOT NULL`).
- If the token has no name, the email local part is used.

Response `200`:

```json
{
  "id": 7,
  "external_auth_id": "auth-abc",
  "display_name": "maya",
  "email": "maya@example.com",
  "role": "learner",
  "created_at": "2026-11-12T14:02:11",
  "target_certification_id": null,
  "exam_date": null,
  "weekly_study_hours": null,
  "experience_level": null
}
```

### `GET /users/me`

Returns the same object. `403` if not provisioned.

### `PATCH /users/me`

Body: any subset of the fields below. Unknown fields are rejected with `422`
(`extra="forbid"`), so a typo fails loudly.

| Field | Type | Notes |
|---|---|---|
| `display_name` | string, 1–255 after trimming | `null` is rejected (`users.display_name` is `NOT NULL`) |
| `exam_date` | `YYYY-MM-DD` or `null` | `null` clears the date |
| `weekly_study_hours` | integer 0–168 or `null` | `null` clears the value |
| `experience_level` | `beginner` \| `intermediate` \| `advanced` \| `null` | `null` clears the value |

Omitted fields keep their current value (`exclude_unset`). An empty body is a
no-op returning the current row. All changes are committed in one transaction.

Response `200`: the refreshed user object.
`422`: validation failure. `403`: not provisioned.

---

## Database invariants relied on

| Table | Invariant | Why it matters |
|---|---|---|
| `users` | `external_auth_id` UNIQUE | upsert key |
| `users` | `email` NOT NULL, not unique | fallback needed; never an identity key |
| `users` | `display_name` NOT NULL | PATCH rejects null |
| `learner_profiles` | `user_id` PK/FK | idempotent profile creation |

No `updated_at` column exists in the schema; the API does not expose one.

---

## Out of scope for M1

- Admin reads (`GET /users/{id}`), role management, account deletion.
- Email/name synchronisation back to Supabase Auth.
- Enrollment and certification endpoints (Workstream B).
