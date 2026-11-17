# Edgely frontend

Next.js app for the Edgely learner experience.

```bash
npm ci
npm run dev      # http://localhost:3000
npm run build
npm run lint
```

The API URL defaults to `http://localhost:8000`; override it with
`NEXT_PUBLIC_API_URL` in `frontend/.env.local`.

## Pages

| Route | What it shows | API calls |
|---|---|---|
| `/` | Landing page; the header shows **Dashboard** when signed in | – |
| `/login`, `/register`, `/forgot-password`, `/reset-password` | Sign-in forms | Supabase Auth (in progress) |
| `/dashboard` | Exam goal, readiness, topic mastery, weekly goal, recent enrollments | `GET /users/me`, `PATCH /users/me`, `GET /enrollments/me`, `GET /tutor/me/context` |
| `/certifications` | Catalogue, enroll, pause / resume / complete / abandon | `GET /certifications`, `GET /enrollments/me`, `POST /enrollments`, `PATCH /enrollments/{id}` |

The request and response shapes are in
[docs/api/m1-contract.md](../docs/api/m1-contract.md).

## Calling the API

Use `utilities/backend_client.ts` for every platform call. It:

- sends `Authorization: Bearer <Supabase access token>`;
- on the first call of a brand-new account, runs `POST /users/me` once and
  retries (the backend answers 403 until the platform user exists);
- throws `ApiError` with the backend's message and HTTP status.

The token comes from whatever is registered with `setAccessTokenProvider()`.
The sign-in work registers the Supabase session there once:

```ts
setAccessTokenProvider(async () =>
  (await supabase.auth.getSession()).data.session?.access_token ?? null);
```

Until that lands, every call returns 401 and the pages show a "Please sign in"
panel.

### Local testing before sign-in exists

In development only, put a Supabase access token for a test account in
`frontend/.env.local`:

```
NEXT_PUBLIC_DEV_ACCESS_TOKEN=<access token>
```

It is ignored in production builds. `.env*` files are git-ignored; never commit
a token.

## Build note

`next.config.ts` enables `cacheComponents`, so pages are prerendered at build
time. Don't call `new Date()` (or `Math.random()`) during a component's first
render; read the clock after the API responds or via `useSyncExternalStore`
with a server snapshot, as `components/workspace/WorkspaceShell.tsx` does.
