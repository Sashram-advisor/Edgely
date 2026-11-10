import type { ReactNode } from "react";
import Link from "next/link";
import "./auth.css";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="auth-page">
      <aside className="auth-side">
        <Link className="auth-brand" href="/" aria-label="Edgely home">
          <span className="auth-brand-mark" aria-hidden="true">
            E
          </span>
          <span>Edgely</span>
        </Link>
        <div className="auth-side-copy">
          <p className="auth-side-title">
            Know what to study, and why it matters.
          </p>
          <ul>
            <li>An AI tutor that explains things at your level</li>
            <li>A study plan that adjusts to your progress</li>
            <li>A readiness score that shows where you stand</li>
          </ul>
        </div>
      </aside>
      <main className="auth-main">
        <Link className="auth-brand auth-brand-mobile" href="/" aria-label="Edgely home">
          <span className="auth-brand-mark" aria-hidden="true">
            E
          </span>
          <span>Edgely</span>
        </Link>
        <div className="auth-card">{children}</div>
      </main>
    </div>
  );
}
