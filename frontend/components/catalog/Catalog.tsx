"use client";

// F1: browse active certifications, enroll, and manage my enrollments.
// Every value on this page comes from GET /certifications and GET /enrollments/me.

import { useState } from "react";
import Link from "next/link";
import shell from "../dashboard/Dashboard.module.css";
import styles from "./Catalog.module.css";
import { Icon } from "../workspace/Icon";
import WorkspaceShell, { StatusPanel } from "../workspace/WorkspaceShell";
import { useApi } from "@/hooks/useApi";
import { ApiError, certificationsApi, enrollmentsApi, usersApi } from "@/utilities/backend_client";
import { formatDate } from "@/utilities/format";
import type { Certification, Enrollment, EnrollmentStatus } from "@/types/learning";

const OPEN: EnrollmentStatus[] = ["active", "paused"];

type Draft = { certification: Certification; goal: string; deadline: string; hours: string };

export default function Catalog() {
  const state = useApi(() =>
    Promise.all([usersApi.me(), certificationsApi.list(), enrollmentsApi.mine()]).then(([user, certifications, enrollments]) => ({
      user,
      certifications,
      enrollments,
    })),
  );
  const [draft, setDraft] = useState<Draft | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmAbandon, setConfirmAbandon] = useState<Enrollment | null>(null);

  if (state.kind !== "ready") {
    return (
      <WorkspaceShell title="Certifications" user={null}>
        <StatusPanel kind={state.kind} message={state.kind === "error" ? state.message : undefined} onRetry={state.reload} />
      </WorkspaceShell>
    );
  }

  const { user, certifications, enrollments } = state.data;
  const openByCert = new Map(enrollments.filter((e) => OPEN.includes(e.status)).map((e) => [e.certification_id, e]));

  const submitEnroll = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!draft) return;
    setSaving(true);
    setFormError(null);
    try {
      const created = await enrollmentsApi.create({
        certification_id: draft.certification.id,
        goal: draft.goal.trim() || null,
        deadline: draft.deadline || null,
        weekly_study_hours: draft.hours ? Number(draft.hours) : null,
      });
      setDraft(null);
      setNotice(`You're enrolled in ${created.certification_name}.`);
      state.reload();
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "Could not enroll. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const changeStatus = async (enrollment: Enrollment, status: EnrollmentStatus) => {
    setBusyId(enrollment.id);
    setNotice(null);
    try {
      await enrollmentsApi.update(enrollment.id, { status });
      state.reload();
    } catch (error) {
      setNotice(error instanceof ApiError ? error.message : "Could not update the enrollment.");
    } finally {
      setBusyId(null);
      setConfirmAbandon(null);
    }
  };

  return (
    <WorkspaceShell title="Certifications" user={user}>
      <section className={styles.intro}>
        <div className={shell.eyebrow}><span className={shell.eyebrowLine} /> LEARNING CATALOGUE</div>
        <h1>Choose what to study</h1>
        <p>Enroll in a certification and the AI Tutor will focus its answers on that material.</p>
      </section>

      {notice && (
        <div className={styles.notice} role="status">
          <span>{notice}</span>
          <Link href="/dashboard">Go to dashboard <Icon name="arrow" size={14} /></Link>
        </div>
      )}

      <h2 className={styles.sectionTitle}>My enrollments</h2>
      {enrollments.length === 0 ? (
        <div className={`${shell.card} ${styles.empty}`}>You haven&apos;t enrolled in anything yet. Pick a certification below.</div>
      ) : (
        <div className={styles.enrollments}>
          {enrollments.map((e) => {
            const busy = busyId === e.id;
            const open = OPEN.includes(e.status);
            return (
              <article key={e.id} className={`${shell.card} ${styles.enrollment}`}>
                <div className={styles.enrollmentMain}>
                  <strong>{e.certification_name}</strong>
                  <div className={styles.enrollmentMeta}>
                    {e.deadline && <span><Icon name="calendar" size={13} /> Target {formatDate(e.deadline)}</span>}
                    {e.weekly_study_hours != null && <span><Icon name="clock" size={13} /> {e.weekly_study_hours} h / week</span>}
                    {e.goal && <span><Icon name="target" size={13} /> {e.goal}</span>}
                    <span>Enrolled {formatDate(e.created_at)}</span>
                  </div>
                </div>
                <span className={`${styles.status} ${styles[`status_${e.status}`]}`}>{e.status}</span>
                {open && (
                  <div className={styles.actions}>
                    {e.status === "active" ? (
                      <button className={styles.action} disabled={busy} onClick={() => changeStatus(e, "paused")}><Icon name="pause" size={13} /> Pause</button>
                    ) : (
                      <button className={styles.action} disabled={busy} onClick={() => changeStatus(e, "active")}><Icon name="play" size={13} /> Resume</button>
                    )}
                    <button className={styles.action} disabled={busy} onClick={() => changeStatus(e, "completed")}><Icon name="check" size={13} /> Completed</button>
                    <button className={`${styles.action} ${styles.danger}`} disabled={busy} onClick={() => setConfirmAbandon(e)}>Abandon</button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}

      <h2 className={styles.sectionTitle}>Available certifications</h2>
      {certifications.length === 0 ? (
        <div className={`${shell.card} ${styles.empty}`}>No certifications are open for enrollment yet.</div>
      ) : (
        <div className={styles.catalog}>
          {certifications.map((c) => {
            const current = openByCert.get(c.id);
            return (
              <article key={c.id} className={`${shell.card} ${styles.cert}`}>
                <h3>{c.name}</h3>
                <span className={styles.slug}>{c.slug}</span>
                <p>{c.description ?? "No description yet."}</p>
                <div className={styles.certFoot}>
                  {current ? (
                    <span className={`${styles.status} ${styles[`status_${current.status}`]}`}>{current.status === "active" ? "Enrolled" : "Paused"}</span>
                  ) : (
                    <button className={styles.enrollButton} onClick={() => { setFormError(null); setDraft({ certification: c, goal: "", deadline: "", hours: "" }); }}>
                      <Icon name="plus" size={15} /> Enroll
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {draft && (
        <div className={shell.modalOverlay} onMouseDown={(e) => { if (e.target === e.currentTarget && !saving) setDraft(null); }}>
          <section className={shell.modal} role="dialog" aria-modal="true" aria-labelledby="enroll-title">
            <div className={shell.modalHeader}>
              <span className={shell.modalIcon}><Icon name="book" /></span>
              <button onClick={() => setDraft(null)} aria-label="Close" disabled={saving}><Icon name="close" /></button>
            </div>
            <h2 id="enroll-title">Enroll in {draft.certification.name}</h2>
            <p>All fields are optional. You can change them later.</p>
            <form onSubmit={submitEnroll} className={styles.formGrid}>
              <label htmlFor="enroll-goal">Your goal</label>
              <input id="enroll-goal" maxLength={2000} placeholder="e.g. Pass before March" value={draft.goal} onChange={(e) => setDraft({ ...draft, goal: e.target.value })} />
              <label htmlFor="enroll-deadline">Target exam date</label>
              <input id="enroll-deadline" type="date" value={draft.deadline} onChange={(e) => setDraft({ ...draft, deadline: e.target.value })} />
              <label htmlFor="enroll-hours">Study hours per week</label>
              <input id="enroll-hours" type="number" min="0.25" max="168" step="0.25" placeholder="e.g. 6" value={draft.hours} onChange={(e) => setDraft({ ...draft, hours: e.target.value })} />
              <p className={styles.hint}>Across all your open enrollments the total can&apos;t exceed 168 hours.</p>
              {formError && <div className={styles.error} role="alert">{formError}</div>}
              <div className={shell.modalActions}>
                <button type="button" className={shell.cancelButton} onClick={() => setDraft(null)} disabled={saving}>Cancel</button>
                <button type="submit" className={shell.confirmButton} disabled={saving}>{saving ? "Enrolling…" : "Enroll"}</button>
              </div>
            </form>
          </section>
        </div>
      )}

      {confirmAbandon && (
        <div className={shell.modalOverlay} onMouseDown={(e) => { if (e.target === e.currentTarget) setConfirmAbandon(null); }}>
          <section className={shell.modal} role="dialog" aria-modal="true" aria-labelledby="abandon-title">
            <h2 id="abandon-title">Abandon {confirmAbandon.certification_name}?</h2>
            <p>This closes the enrollment for good. You can enroll again later, which starts a new one; this one stays in your history.</p>
            <div className={shell.modalActions}>
              <button className={shell.cancelButton} onClick={() => setConfirmAbandon(null)}>Keep it</button>
              <button className={shell.confirmButton} disabled={busyId === confirmAbandon.id} onClick={() => changeStatus(confirmAbandon, "abandoned")}>Abandon</button>
            </div>
          </section>
        </div>
      )}
    </WorkspaceShell>
  );
}
