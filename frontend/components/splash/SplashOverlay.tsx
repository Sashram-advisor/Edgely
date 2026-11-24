"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import type {
  FormEvent,
  KeyboardEvent as ReactKeyboardEvent,
  MouseEvent as ReactMouseEvent,
} from "react";
import "./splash.css";

/* ------------------------------------------------------------------ */
/* Settings                                                            */
/* ------------------------------------------------------------------ */

// Once a visitor finishes or skips the intro, this flag keeps it from
// appearing again in that browser. Add ?splash to any homepage URL to
// force it back for testing (for example http://localhost:3000/?splash).
const SEEN_KEY = "edgely-splash-seen";

// The choice made on the last screen is saved here so the sign-up or
// onboarding flow can pick it up later. Nothing reads it yet.
const ONBOARDING_KEY = "edgely-onboarding";

const CERTIFICATIONS = ["AWS", "Azure", "PMP", "Scrum", "CISSP"] as const;
type Certification = (typeof CERTIFICATIONS)[number];

type Tone = "light" | "dark" | "lime";
type Step = { tone: Tone; title: string; body: string };

const STEPS: Step[] = [
  {
    tone: "light",
    title: "Find out why you keep missing the same questions.",
    body: "Edgely reads across your answers, spots the pattern behind your mistakes, and explains it at your level.",
  },
  {
    tone: "dark",
    title: "A study plan that rewrites itself when your week does.",
    body: "Miss a session or master a topic early, and the rest of your plan moves with you. No spreadsheets to redo.",
  },
  {
    tone: "light",
    title: "See how ready you are, and when you’ll be ready.",
    body: "Your readiness score updates after every quiz, so you can trust your exam date instead of guessing at it.",
  },
  {
    tone: "lime",
    title: "Start with a 10-minute diagnostic.",
    body: "Choose your certification and exam date. Edgely builds your first study plan from what the diagnostic finds.",
  },
];

// Example content shown in the visuals. Replace with real data later.
const PATTERNS = [
  { label: "Route tables", missed: 7, total: 9 },
  { label: "Security groups", missed: 1, total: 8 },
  { label: "NAT gateways", missed: 1, total: 6 },
];

type PlanState = "done" | "missed" | "added" | "moved" | "planned";
const PLAN: { day: string; title: string; note?: string; badge: string; state: PlanState }[] = [
  { day: "Mon", title: "IAM policies review", badge: "Done", state: "done" },
  { day: "Tue", title: "VPC routing session", badge: "Missed", state: "missed" },
  { day: "Wed", title: "S3 storage classes quiz", note: "+ 10-minute VPC recap", badge: "Added", state: "added" },
  { day: "Thu", title: "VPC routing session", note: "Moved from Tuesday", badge: "Moved", state: "moved" },
  { day: "Fri", title: "Practice exam, networking section", badge: "Planned", state: "planned" },
];

const READINESS = [
  { label: "Wk 1", value: 31 },
  { label: "Wk 2", value: 38 },
  { label: "Wk 3", value: 47 },
  { label: "Wk 4", value: 55 },
  { label: "Wk 5", value: 62 },
  { label: "Now", value: 72, current: true },
  { label: "Wk 7", value: 78, projected: true },
  { label: "Wk 8", value: 84, projected: true },
];
const PASS_LINE = 80;

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/* ------------------------------------------------------------------ */
/* Storage helpers (private browsing can make localStorage throw)      */
/* ------------------------------------------------------------------ */

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage is unavailable, so the overlay will simply show again next visit.
  }
}

// useSyncExternalStore lets the server render "closed" and the browser decide
// on its own, without a hydration mismatch or a setState call inside an effect.
const subscribe = () => () => {};
const shouldShowSplash = () =>
  new URLSearchParams(window.location.search).has("splash") || !safeGet(SEEN_KEY);
const shouldShowOnServer = () => false;

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export default function SplashOverlay() {
  const router = useRouter();
  const shouldShow = useSyncExternalStore(subscribe, shouldShowSplash, shouldShowOnServer);
  const [dismissed, setDismissed] = useState(false);
  const open = shouldShow && !dismissed;

  const [step, setStep] = useState(0);
  const [certification, setCertification] = useState<Certification>("AWS");
  const [examDate, setExamDate] = useState("");

  const dialogRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);

  const finish = useCallback(() => {
    safeSet(SEEN_KEY, "1");
    setDismissed(true);
  }, []);

  // Lock page scroll behind the overlay and give focus back when it closes.
  useEffect(() => {
    if (!open) return;
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [open]);

  // Move focus to the heading whenever the screen changes so screen readers
  // announce the new content.
  useEffect(() => {
    if (open) titleRef.current?.focus();
  }, [open, step]);

  if (!open) return null;

  const current = STEPS[step];
  const isFirst = step === 0;
  const isLast = step === STEPS.length - 1;

  function handleKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      finish();
      return;
    }
    if (event.key !== "Tab") return;

    // Keep Tab and Shift+Tab inside the overlay.
    const dialog = dialogRef.current;
    if (!dialog) return;
    const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (element) => element.offsetParent !== null,
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;

    if (event.shiftKey && (active === first || active === titleRef.current)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function handleStart(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    safeSet(ONBOARDING_KEY, JSON.stringify({ certification, examDate }));
    finish();
    router.push("/register");
  }

  // Clicking the dimmed area outside the dialog counts as skipping the intro.
  function handleBackdropMouseDown(event: ReactMouseEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) finish();
  }

  return (
    <div className="splash-backdrop" onMouseDown={handleBackdropMouseDown}>
      <div
        ref={dialogRef}
        className="splash-overlay"
        data-tone={current.tone}
        role="dialog"
        aria-modal="true"
        aria-labelledby="splash-title"
        onKeyDown={handleKeyDown}
      >
        <div className="splash-top">
          <div className="splash-brand">
            <span className="splash-brand-mark" aria-hidden="true">
              E
            </span>
            <span>Edgely</span>
          </div>
          <button type="button" className="splash-btn splash-btn-ghost" onClick={finish}>
            Skip intro
          </button>
        </div>

        <div className="splash-main" key={step}>
          <div className="splash-copy">
            <h2 id="splash-title" className="splash-title" ref={titleRef} tabIndex={-1}>
              {current.title}
            </h2>
            <p className="splash-body">{current.body}</p>
          </div>

          {step === 0 && <TutorVisual />}
          {step === 1 && <PlanVisual />}
          {step === 2 && <ReadinessVisual />}
          {step === 3 && (
            <StartVisual
              certification={certification}
              onCertification={setCertification}
              examDate={examDate}
              onExamDate={setExamDate}
              onSubmit={handleStart}
              onLogin={finish}
            />
          )}
        </div>

        <div className="splash-bottom">
          <div className="splash-progress">
            <span className="splash-count">
              {step + 1} of {STEPS.length}
            </span>
            <div className="splash-dots" aria-hidden="true">
              {STEPS.map((_, index) => (
                <span key={index} className={index === step ? "splash-dot is-on" : "splash-dot"} />
              ))}
            </div>
          </div>
          <div className="splash-actions">
            {!isFirst && (
              <button
                type="button"
                className="splash-btn splash-btn-ghost"
                onClick={() => setStep(step - 1)}
              >
                Back
              </button>
            )}
            {isLast ? (
              <button type="button" className="splash-btn splash-btn-outline" onClick={finish}>
                Go to homepage
              </button>
            ) : (
              <button
                type="button"
                className="splash-btn splash-btn-primary"
                onClick={() => setStep(step + 1)}
              >
                Next
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Screen visuals                                                      */
/* ------------------------------------------------------------------ */

function TutorVisual() {
  const total = PATTERNS.reduce((sum, row) => sum + row.total, 0);
  return (
    <div className="splash-card">
      <div className="splash-card-head">
        <div className="splash-card-title-row">
          <span className="splash-spark" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round">
              <path d="M12 3l2.2 6.3L21 12l-6.8 2.7L12 21l-2.2-6.3L3 12l6.8-2.7z" />
            </svg>
          </span>
          <span className="splash-card-title">AI tutor</span>
        </div>
        <span className="splash-example">Example conversation</span>
      </div>

      <div className="splash-bubble splash-bubble-user">Why do I keep missing VPC questions?</div>
      <div className="splash-bubble splash-bubble-ai">
        You know the definitions. The misses cluster around route-table scenarios, where a subnet
        has no route to an internet gateway. Let’s work through one together.
      </div>

      <div className="splash-pattern">
        <div className="splash-pattern-title">Pattern across {total} VPC questions</div>
        {PATTERNS.map((row, index) => (
          <div className="splash-pattern-row" key={row.label}>
            <span>{row.label}</span>
            <span className="splash-track">
              <span
                className={index === 0 ? "splash-fill is-strong" : "splash-fill"}
                style={{ width: `${Math.round((row.missed / row.total) * 100)}%` }}
              />
            </span>
            <span className="splash-muted splash-right">
              {row.missed} of {row.total} missed
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function PlanVisual() {
  return (
    <div className="splash-card">
      <div className="splash-card-head">
        <span className="splash-card-heading">Your plan this week</span>
        <span className="splash-example">Example plan</span>
      </div>

      <div className="splash-banner">
        <strong>Plan updated.</strong> You missed Tuesday, so VPC routing moved to Thursday and a
        10-minute recap was added to Wednesday.
      </div>

      <ul className="splash-plan">
        {PLAN.map((row) => (
          <li key={row.day} className={`splash-plan-row is-${row.state}`}>
            <span className="splash-plan-day">{row.day}</span>
            <span className="splash-plan-text">
              <span className="splash-plan-title">{row.title}</span>
              {row.note && <span className="splash-muted splash-small">{row.note}</span>}
            </span>
            <span className={`splash-badge is-${row.state}`}>{row.badge}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ReadinessVisual() {
  return (
    <div className="splash-card">
      <div className="splash-card-head">
        <div className="splash-stack">
          <span className="splash-card-heading">Exam readiness</span>
          <span className="splash-muted splash-small">
            AWS Solutions Architect Associate · exam on Dec 12
          </span>
        </div>
        <span className="splash-pill">72% today</span>
      </div>

      <div
        className="splash-chart"
        role="img"
        aria-label="Bar chart of weekly readiness rising from 31 percent in week 1 to a projected 84 percent in week 8, with a pass-ready line at 80 percent."
      >
        <div className="splash-plot">
          <div className="splash-passline" style={{ bottom: `${PASS_LINE}%` }} />
          <span className="splash-passlabel" style={{ bottom: `calc(${PASS_LINE}% + 6px)` }}>
            Pass-ready: {PASS_LINE}%
          </span>
          <div className="splash-bars">
            {READINESS.map((week) => (
              <div className="splash-bar-col" key={week.label}>
                <span
                  className={week.projected ? "splash-bar is-projected" : "splash-bar"}
                  style={{ height: `${week.value}%` }}
                />
              </div>
            ))}
          </div>
        </div>
        <div className="splash-axis">
          {READINESS.map((week) => (
            <span
              key={week.label}
              className={week.current ? "splash-axis-item is-current" : "splash-axis-item"}
            >
              <span className="splash-axis-value">{week.value}%</span>
              <span>{week.label}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="splash-chart-foot">
        <span>
          On pace to reach 80% by <strong>Dec 3</strong>, nine days before your exam.
        </span>
        <span className="splash-legend splash-muted">
          <span className="splash-legend-item">
            <span className="splash-swatch" />
            Measured
          </span>
          <span className="splash-legend-item">
            <span className="splash-swatch is-projected" />
            Projected
          </span>
        </span>
      </div>
    </div>
  );
}

type StartVisualProps = {
  certification: Certification;
  onCertification: (value: Certification) => void;
  examDate: string;
  onExamDate: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onLogin: () => void;
};

function StartVisual({
  certification,
  onCertification,
  examDate,
  onExamDate,
  onSubmit,
  onLogin,
}: StartVisualProps) {
  return (
    <form className="splash-card splash-form" onSubmit={onSubmit}>
      <fieldset className="splash-fieldset">
        <legend className="splash-legend-text">Which certification are you studying for?</legend>
        <div className="splash-chips">
          {CERTIFICATIONS.map((name) => (
            <button
              key={name}
              type="button"
              className={name === certification ? "splash-chip is-on" : "splash-chip"}
              aria-pressed={name === certification}
              onClick={() => onCertification(name)}
            >
              {name}
            </button>
          ))}
        </div>
      </fieldset>

      <div className="splash-stack">
        <label htmlFor="splash-exam-date" className="splash-legend-text">
          When is your exam?
        </label>
        <input
          id="splash-exam-date"
          type="date"
          className="splash-input"
          value={examDate}
          onChange={(event) => onExamDate(event.target.value)}
        />
        <span className="splash-muted splash-small">Not booked yet? You can set the date later.</span>
      </div>

      <button type="submit" className="splash-btn splash-btn-primary splash-btn-wide">
        Build my learning path
      </button>

      <p className="splash-muted splash-center">
        Already have an account?{" "}
        <Link href="/login" className="splash-link" onClick={onLogin}>
          Log in
        </Link>
      </p>
    </form>
  );
}
