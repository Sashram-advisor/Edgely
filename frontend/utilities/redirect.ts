// Helpers for the "send me back where I was after login" flow (A5).
//
// The route guard (components/auth/RequireAuth.tsx) sends an unauthenticated
// visitor to `/login?next=<the page they wanted>`. After a successful login,
// LoginForm reads `next` and navigates there.
//
// `next` comes from the URL, so an attacker could craft
// `/login?next=https://evil.example` to bounce a freshly logged-in user to a
// phishing page (an "open redirect"). safeNextPath() only accepts paths that
// stay on this site.

/** Where to go after login when `next` is missing or unsafe. */
export const DEFAULT_AFTER_LOGIN = "/dashboard";

/**
 * Return `raw` if it is a same-site path, otherwise DEFAULT_AFTER_LOGIN.
 *
 * Accepted:  "/dashboard", "/tutor?x=1"
 * Rejected:  null, "", "dashboard" (no leading slash), "//evil.example"
 *            (protocol-relative URL), "/\\evil.example" (browsers treat "\" as
 *            "/"), "https://evil.example", and the auth pages themselves (to
 *            avoid a login -> login loop).
 */
export function safeNextPath(raw: string | null | undefined): string {
  if (!raw) return DEFAULT_AFTER_LOGIN;
  // Must be a path on this origin: exactly one leading "/" and no backslash
  // tricks right after it.
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) {
    return DEFAULT_AFTER_LOGIN;
  }
  // Never bounce back into the auth pages after logging in.
  const authPages = ["/login", "/register", "/forgot-password", "/reset-password"];
  if (authPages.some((page) => raw === page || raw.startsWith(`${page}?`) || raw.startsWith(`${page}/`))) {
    return DEFAULT_AFTER_LOGIN;
  }
  return raw;
}

/** Build the login URL that remembers the page the visitor wanted. */
export function loginUrlFor(path: string): string {
  return `/login?next=${encodeURIComponent(path)}`;
}
