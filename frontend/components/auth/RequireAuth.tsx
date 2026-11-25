"use client";

// A5: client-side route guard.
//
// Why client-side and not Next.js middleware/proxy?
//   The Supabase browser client (utilities/supabase.ts) keeps the session in
//   localStorage, not in a cookie. Code that runs on the server (middleware,
//   server components) therefore cannot see whether the visitor is logged in.
//   The guard has to run in the browser, where the session lives.
//
// Behaviour:
//   1. While the session is being read, render a small "Checking…" placeholder,
//      never the protected page (so nothing private flashes on screen).
//   2. No session  -> router.replace("/login?next=<current path>").
//      `replace` (not `push`) so the Back button does not return to the guarded
//      page and bounce the user to /login again.
//   3. Session     -> render the children.
//   4. If the user signs out in this tab or another tab, Supabase fires
//      SIGNED_OUT and the guard redirects to /login immediately.
//
// Note: this guard is a UX gate, not the security boundary. The real protection
// is the backend: every API call needs a valid Bearer token (A3), so a user who
// bypasses this component still cannot read any data.

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { supabase } from "@/utilities/supabase";
import { loginUrlFor } from "@/utilities/redirect";

type GuardState = "checking" | "allowed" | "redirecting";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [state, setState] = useState<GuardState>("checking");

  useEffect(() => {
    // `active` prevents a state update after the component unmounted
    // (e.g. the user navigated away before getSession() resolved).
    let active = true;

    const sendToLogin = () => {
      if (!active) return;
      setState("redirecting");
      router.replace(loginUrlFor(pathname || "/dashboard"));
    };

    // Step 1: read the stored session once on mount.
    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (!active) return;
        if (data.session) setState("allowed");
        else sendToLogin();
      })
      // A storage/parsing error is treated as "not logged in" (fail closed).
      .catch(sendToLogin);

    // Step 2: react to later changes, e.g. sign-out in another tab or an
    // expired refresh token.
    const { data: subscription } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_OUT" || !session) sendToLogin();
    });

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, [pathname, router]);

  if (state !== "allowed") {
    // Minimal inline styles so this component does not depend on any page CSS.
    return (
      <p role="status" aria-live="polite" style={{ padding: "2rem", textAlign: "center" }}>
        {state === "checking" ? "Checking your session…" : "Redirecting to log in…"}
      </p>
    );
  }

  return <>{children}</>;
}
