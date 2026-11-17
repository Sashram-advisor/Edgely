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

The body is optional:

| Field | Type | Notes |
|---|---|---|
| `display_name` | string, max 255, optional | Used only when the user is created. A later call never renames an existing user; use `PATCH /users/me`. |

Unknown fields are ignored (`user_id` in a body has no effect).

Provisioning runs in one transaction:

1. `INSERT INTO users (...) ON CONFLICT (external_auth_id) DO UPDATE SET email = ... RETURNING id`
   - the stored email is refreshed only when the token carries one
2. `INSERT INTO learner_profiles (user_id) ... ON CONFLICT (user_id) DO NOTHING`
3. commit, then read the joined row

Rules:

- `external_auth_id` is the upsert key. `users.email` is **not unique** and must
  never be a conflict target.
- A custom `display_name` is never overwritten by a later login.
- `role` is always `learner` on creation; the token cannot set it.
- If the token has no email, a deterministic placeholder
  `<sub>@unknown.invalid` is stored for a **new** user (`users.email` is
  `NOT NULL`). An existing user's real email is never replaced by it.
- Name of a new user: `display_name` from the body, else the email local part.

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
If the user has no `learner_profiles` row yet (for example a seeded user), it is
created before the profile fields are written.

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

## Catalog and enrollment (Workstream B)

Code: `routes/certifications.py`, `routes/enrollments.py`,
`services/enrollment_service.py`. Errors use the same `{"detail": "..."}` shape.

| Endpoint | Body | Success | Errors |
|---|---|---|---|
| `GET /certifications` | - | `200` list | `401` |
| `GET /enrollments/me` | - | `200` list | `401`, `403` |
| `POST /enrollments` | `certification_id`, `goal?`, `deadline?`, `weekly_study_hours?` | `201` enrollment | `401`, `403`, `409`, `422` |
| `PATCH /enrollments/{id}` | `status?`, `goal?`, `deadline?`, `weekly_study_hours?` | `200` enrollment | `401`, `403`, `404`, `422` |

`GET /certifications` needs a valid token but not a platform user, so a learner
can browse before `POST /users/me`.

### Certification object

```json
{ "id": 1, "name": "AWS Cloud Practitioner", "slug": "aws-ccp", "description": "..." }
```

Only `is_active` certifications are listed, ordered by name.

### Enrollment object

```json
{
  "id": 12,
  "certification_id": 1,
  "certification_name": "AWS Cloud Practitioner",
  "certification_slug": "aws-ccp",
  "status": "active",
  "goal": "Pass in March",
  "deadline": "2027-03-01",
  "weekly_study_hours": 6.5,
  "created_at": "2026-11-17T14:02:11"
}
```

`GET /enrollments/me` returns all of the caller's enrollments, newest first,
including completed and abandoned ones.

### Fields

| Field | Type | Notes |
|---|---|---|
| `certification_id` | integer > 0 | Must be an active certification, else `422` |
| `status` | `active` \| `paused` \| `completed` \| `abandoned` | PATCH only; `null` is rejected |
| `goal` | string, max 2000, or `null` | `null` clears it on PATCH |
| `deadline` | `YYYY-MM-DD` or `null` | `null` clears it on PATCH |
| `weekly_study_hours` | number > 0 and <= 168, 2 decimals, or `null` | `null` clears it on PATCH |

Unknown fields are rejected with `422` (`user_id` in a body is never accepted).
A new enrollment always starts as `active`.

### Rules

- **Status changes:** `active` <-> `paused`; `active` or `paused` ->
  `completed` or `abandoned`. `completed` and `abandoned` are final - any PATCH
  to them is `422`. To study the same certification again, `POST` a new
  enrollment; the old row stays as history.
- **One open enrollment per certification:** a second `active` or `paused`
  enrollment for the same certification is `409`. It comes from the partial
  unique index `enrollments_one_open_per_cert` (`INSERT ... ON CONFLICT DO
  NOTHING`), not a read-then-write check.
- **Weekly hours:** across the learner's open enrollments the total is at most
  168. Over that is `422`; the database trigger
  `enrollments_check_total_hours` is the backstop.
- **Ownership:** another learner's enrollment id is `404`, never `403`, so ids
  cannot be probed.
- **Tutor scope:** the tutor only counts `active` enrollments. A learner whose
  only enrollment is `paused` gets `403 NotEnrolled` from `/tutor/*`.

---

## Out of scope for M1

- Admin reads (`GET /users/{id}`), role management, account deletion.
- Email/name synchronisation back to Supabase Auth.
