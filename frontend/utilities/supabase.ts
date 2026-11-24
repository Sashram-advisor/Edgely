"use client";

// Single Supabase browser client for the whole app.
//
// The backend does NOT issue logins; Supabase Auth owns them (routes/authentication.py
// stays empty on purpose). The frontend signs the user in here and then sends the
// resulting access token to the FastAPI backend as `Authorization: Bearer <token>`.

import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  // Fail loudly in dev so a missing frontend/.env.local is not a silent 401 maze.
  throw new Error(
    "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and " +
      "NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local (see .env.local.example).",
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
});
