import RequireAuth from "../../components/auth/RequireAuth";
import Dashboard from "../../components/dashboard/Dashboard";

// A5: the dashboard is only for logged-in learners. RequireAuth checks the
// Supabase session in the browser and redirects to /login?next=/dashboard when
// there is none. This page itself stays a server component; only the guard and
// the Dashboard are client components.
export default function DashboardPage() {
  return (
    <main>
      <RequireAuth>
        <Dashboard />
      </RequireAuth>
    </main>
  );
}
