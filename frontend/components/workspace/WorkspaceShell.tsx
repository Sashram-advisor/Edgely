"use client";

// The signed-in layout: sidebar navigation, top bar and account menu.
// Used by /dashboard and /certifications so both look like one workspace.

import { useState, useSyncExternalStore, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "../dashboard/Dashboard.module.css";
import { Icon, type IconName } from "./Icon";
import type { PlatformUser } from "@/types/learning";

const navigation: { label: string; href: string; icon: IconName }[] = [
  { label: "Overview", href: "/dashboard", icon: "grid" },
  { label: "Certifications", href: "/certifications", icon: "book" },
  { label: "AI Tutor", href: "/tutor", icon: "sparkle" },
  { label: "Practice", href: "/quiz", icon: "check" },
];

export function initials(name: string | undefined | null): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

const noSubscribe = () => () => {};

function monthLabel(): string {
  return new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

export default function WorkspaceShell({
  title,
  user,
  children,
}: {
  title: string;
  user: PlatformUser | null;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const [mobileNav, setMobileNav] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);
  // The clock is read in the browser only: Next prerenders this page, and a
  // build-time date would be wrong (and is rejected by the cacheComponents build).
  const month = useSyncExternalStore(noSubscribe, monthLabel, () => "");

  return (
    <div className={styles.app}>
      {mobileNav && <button className={styles.mobileScrim} onClick={() => setMobileNav(false)} aria-label="Close navigation" />}
      <aside className={`${styles.sidebar} ${mobileNav ? styles.sidebarOpen : ""}`}>
        <div className={styles.brand}>
          <span className={styles.brandGlyph}>✳</span>
          <span>edgely<span className={styles.brandDot}>.</span></span>
          <button className={styles.closeMobile} onClick={() => setMobileNav(false)} aria-label="Close sidebar"><Icon name="close" /></button>
        </div>
        <div className={styles.sidebarCaption}>YOUR WORKSPACE</div>
        <nav className={styles.nav} aria-label="Learner navigation">
          {navigation.map((item) => (
            <Link
              key={item.href}
              className={`${styles.navLink} ${pathname === item.href ? styles.activeNav : ""}`}
              href={item.href}
              aria-current={pathname === item.href ? "page" : undefined}
              onClick={() => setMobileNav(false)}
            >
              <Icon name={item.icon} size={19} />
              {item.label}
              {pathname === item.href && <span className={styles.activeDot} />}
            </Link>
          ))}
        </nav>
        <div className={styles.sideSpacer} />
        <div className={styles.tutorPromo}>
          <div className={styles.promoStars}>✦ <span>✳</span></div>
          <div className={styles.promoTitle}>A little help goes a long way.</div>
          <p>Ask your AI Tutor whenever you get stuck.</p>
          <Link href="/tutor" className={styles.promoButton}>Ask AI Tutor <Icon name="arrow" size={16} /></Link>
        </div>
        <div className={styles.accountWrap}>
          {accountOpen && (
            <div className={styles.accountMenu} role="menu">
              <button role="menuitem" onClick={() => { setAccountOpen(false); setSignOutOpen(true); }}>
                <Icon name="logout" size={17} /> Sign Out
              </button>
            </div>
          )}
          <button className={styles.accountButton} aria-expanded={accountOpen} aria-haspopup="menu" onClick={() => setAccountOpen(!accountOpen)}>
            <span className={styles.avatar}>{initials(user?.display_name)}</span>
            <span className={styles.accountLabel}>
              <strong>{user?.display_name ?? "My Account"}</strong>
              <small>{user?.email ?? "Learner profile"}</small>
            </span>
            <Icon name="chevron" size={16} />
          </button>
        </div>
      </aside>

      <div className={styles.mainColumn}>
        <header className={styles.topbar}>
          <div className={styles.topbarLeft}>
            <button className={styles.menuButton} onClick={() => setMobileNav(true)} aria-label="Open navigation"><Icon name="menu" /></button>
            <span className={styles.breadcrumb}>My Workspace</span>
            <span className={styles.breadcrumbSlash}>/</span>
            <strong>{title}</strong>
          </div>
          <div className={styles.topbarRight}>
            <span className={styles.todayBadge}><Icon name="calendar" size={15} /> {month}</span>
            <button className={styles.headerAvatar} onClick={() => setAccountOpen(!accountOpen)} title="Account options">{initials(user?.display_name)}</button>
          </div>
        </header>
        <main className={styles.content}>{children}</main>
      </div>

      {signOutOpen && (
        <div className={styles.modalOverlay} onMouseDown={(e) => { if (e.target === e.currentTarget) setSignOutOpen(false); }}>
          <section className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="signout-title">
            <div className={styles.modalHeader}>
              <span className={styles.modalIcon}><Icon name="logout" /></span>
              <button onClick={() => setSignOutOpen(false)} aria-label="Close"><Icon name="close" /></button>
            </div>
            <h2 id="signout-title">Sign out of Edgely?</h2>
            <p>Sign-out arrives with the Supabase sign-in work. For now, close this tab to end your session.</p>
            <div className={styles.modalActions}>
              <button className={styles.confirmButton} onClick={() => setSignOutOpen(false)}>Got it</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

// Full-width message for signed-out / error states inside the shell.
export function StatusPanel({ kind, message, onRetry }: { kind: "signedOut" | "error" | "loading"; message?: string; onRetry?: () => void }) {
  if (kind === "loading") {
    return <section className={styles.card} style={{ padding: 28 }} aria-busy="true"><p className={styles.cardDescription} style={{ margin: 0 }}>Loading…</p></section>;
  }
  if (kind === "signedOut") {
    return (
      <section className={styles.card} style={{ padding: 28 }}>
        <div className={styles.cardHeading}><h2>Please sign in</h2></div>
        <p className={styles.cardDescription}>Your session has ended or you are not signed in yet.</p>
        <Link className={styles.heroButton} href="/login">Go to sign in <Icon name="arrow" size={16} /></Link>
      </section>
    );
  }
  return (
    <section className={styles.card} style={{ padding: 28 }} role="alert">
      <div className={styles.cardHeading}><h2>Something went wrong</h2></div>
      <p className={styles.cardDescription}>{message}</p>
      {onRetry && <button className={styles.subtleButton} onClick={onRetry}>Try again</button>}
    </section>
  );
}
