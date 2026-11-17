"use client";

// Load data from the platform API in a client component.
// state.kind tells the page what to render: loading, signed-out (401), error, or ready.

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/utilities/backend_client";

export type ApiState<T> =
  | { kind: "loading" }
  | { kind: "signedOut" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: T };

export function useApi<T>(load: () => Promise<T>, deps: unknown[] = []): ApiState<T> & { reload: () => void } {
  const [state, setState] = useState<ApiState<T>>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    load().then(
      (data) => !cancelled && setState({ kind: "ready", data }),
      (error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) setState({ kind: "signedOut" });
        else setState({ kind: "error", message: error instanceof Error ? error.message : "Something went wrong." });
      },
    );
    return () => {
      cancelled = true;
    };
    // load is recreated each render; the caller's deps decide when to refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt, ...deps]);

  return { ...state, reload };
}
