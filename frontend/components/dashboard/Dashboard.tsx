"use client";

// F3: the learner dashboard. Every number and name on it comes from the API:
//   GET /users/me           -> name, weekly study hours, profile exam date
//   GET /enrollments/me     -> exam goal, certification counts, recent activity
//   GET /tutor/me/context   -> topic performance and readiness (mastery per exam domain)
// Nothing is sample data. Where the API has no data yet, the card says so.

import { useState } from "react";
import Link from "next/link";
import styles from "./Dashboard.module.css";
import { Icon, type IconName } from "../workspace/Icon";
import WorkspaceShell, { StatusPanel } from "../workspace/WorkspaceShell";
import { formatDate } from "@/utilities/format";
import { useApi } from "@/hooks/useApi";
import { ApiError, enrollmentsApi, tutorApi, usersApi } from "@/utilities/backend_client";
import type { Enrollment, LearnerContext, PlatformUser } from "@/types/learning";

type DashboardData = {
  user: PlatformUser;
  enrollments: Enrollment[];
  // null when the tutor is unavailable; the rest of the dashboard still works.
  context: LearnerContext | null;
};

async function loadDashboard(): Promise<DashboardData> {
  const [user, enrollments] = await Promise.all([usersApi.me(), enrollmentsApi.mine()]);
  const context = await tutorApi.context().catch((error: unknown) => {
    if (error instanceof ApiError && error.status === 401) throw error;
    return null;
  });
  return { user, enrollments, context };
}

function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] || name;
}

function daysUntil(isoDate: string): number {
  const [y, m, d] = isoDate.slice(0, 10).split("-").map(Number);
  const target = new Date(y, m - 1, d);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

function currentWeek(): { day: string; date: number; isToday: boolean }[] {
  const today = new Date();
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return {
      day: d.toLocaleDateString("en-US", { weekday: "short" }),
      date: d.getDate(),
      isToday: d.toDateString() === today.toDateString(),
    };
  });
}

// The certification the dashboard focuses on: the profile's target if it is
// actively enrolled, otherwise the most recent active enrollment.
function primaryEnrollment(user: PlatformUser, enrollments: Enrollment[]): Enrollment | null {
  const active = enrollments.filter((e) => e.status === "active");
  return active.find((e) => e.certification_id === user.target_certification_id) ?? active[0] ?? null;
}

const activityIcon: Record<Enrollment["status"], IconName> = {
  active: "book",
  paused: "clock",
  completed: "trophy",
  abandoned: "close",
};

export default function Dashboard() {
  const state = useApi(loadDashboard);
  // null = today. Dates are only computed in the "ready" branch, which renders
  // in the browser after the API answers, never during the build's prerender.
  const [pickedDay, setSelectedDay] = useState<number | null>(null);
  const [goalOpen, setGoalOpen] = useState(false);
  const [draftHours, setDraftHours] = useState("");
  const [goalError, setGoalError] = useState<string | null>(null);
  const [savingGoal, setSavingGoal] = useState(false);

  if (state.kind !== "ready") {
    return (
      <WorkspaceShell title="Overview" user={null}>
        <StatusPanel kind={state.kind} message={state.kind === "error" ? state.message : undefined} onRetry={state.reload} />
      </WorkspaceShell>
    );
  }

  const { user, enrollments, context } = state.data;
  const primary = primaryEnrollment(user, enrollments);
  const counts = {
    active: enrollments.filter((e) => e.status === "active").length,
    paused: enrollments.filter((e) => e.status === "paused").length,
    completed: enrollments.filter((e) => e.status === "completed").length,
  };
  const targetDate = primary?.deadline ?? user.exam_date;
  const daysLeft = targetDate ? daysUntil(targetDate) : null;

  // Topic mastery for the focused certification (context lists weakest first).
  const domains = (context?.domain_progress ?? []).filter((d) => !primary || d.certification_id === primary.certification_id);
  const readiness = domains.length ? Math.round(domains.reduce((sum, d) => sum + d.mastery_score, 0) / domains.length) : null;
  const weakest = domains[0] ?? null;
  const topics = [...domains].sort((a, b) => b.mastery_score - a.mastery_score).slice(0, 5);

  const week = currentWeek();
  const selectedDay = pickedDay ?? week.find((d) => d.isToday)?.date;
  const recent = enrollments.slice(0, 4);

  const openGoal = () => {
    setDraftHours(user.weekly_study_hours != null ? String(user.weekly_study_hours) : "");
    setGoalError(null);
    setGoalOpen(true);
  };
  const submitGoal = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const hours = draftHours === "" ? null : Number(draftHours);
    if (hours != null && (!Number.isInteger(hours) || hours < 0 || hours > 168)) {
      setGoalError("Enter a whole number of hours from 0 to 168.");
      return;
    }
    setSavingGoal(true);
    try {
      await usersApi.update({ weekly_study_hours: hours });
      setGoalOpen(false);
      state.reload();
    } catch (error) {
      setGoalError(error instanceof ApiError ? error.message : "Could not save your goal.");
    } finally {
      setSavingGoal(false);
    }
  };

  return (
    <WorkspaceShell title="Overview" user={user}>
      <section className={styles.intro} aria-label="Welcome">
        <div>
          <div className={styles.eyebrow}><span className={styles.eyebrowLine} /> YOUR LEARNING SPACE</div>
          <h1>Good to see you, {firstName(user.display_name)} <span className={styles.wave}>✳</span></h1>
          <p>{primary ? `One step closer to ${primary.certification_name}.` : "Choose a certification to get started."}</p>
        </div>
      </section>

      <section className={styles.hero} aria-label="Learning motivation">
        <div className={styles.heroContent}>
          <span className={styles.heroLabel}>YOUR JOURNEY, YOUR PACE</span>
          <h2>Small steps today.<br /><em>Big things tomorrow.</em></h2>
          <p>Keep showing up. Every session brings you closer to your goal.</p>
          {primary ? (
            <Link href="/tutor" className={styles.heroButton}>Study with the AI Tutor <Icon name="arrow" size={17} /></Link>
          ) : (
            <Link href="/certifications" className={styles.heroButton}>Choose a certification <Icon name="arrow" size={17} /></Link>
          )}
        </div>
        <div className={styles.heroArtwork} aria-hidden="true"><div className={styles.orbOuter}><div className={styles.orbMid}><div className={styles.orbInner}>✳</div></div></div><span className={styles.heroStar1}>✦</span><span className={styles.heroStar2}>✧</span><span className={styles.heroStar3}>✳</span></div>
      </section>

      <div className={styles.sectionHeading}><div><span className={styles.sectionKicker}>AT A GLANCE</span><h2>Your progress</h2></div><Link href="/certifications" className={styles.textLink}>Manage certifications <Icon name="arrow" size={16} /></Link></div>
      <section className={styles.metrics} aria-label="Progress overview">
        <article className={`${styles.card} ${styles.metricCard}`}>
          <div className={styles.cardIcon}><Icon name="book" size={21} /></div>
          <div className={styles.metricTop}><span>Studying now</span></div>
          <strong className={styles.metricNumber}>{counts.active}</strong>
          <p>{counts.active === 1 ? "Active certification" : "Active certifications"}</p>
          <div className={styles.metricFoot}><span>{counts.paused} paused</span><span>{counts.completed} completed</span></div>
        </article>

        <article className={`${styles.card} ${styles.readinessCard}`}>
          <div className={styles.readinessCopy}>
            <div className={styles.cardIcon}><Icon name="target" size={21} /></div>
            <span className={styles.metricTop}>Exam readiness</span>
            <strong>{readiness == null ? "No results yet" : readiness >= 70 ? "Getting closer!" : "Keep building"}</strong>
            <p>{readiness == null ? "Readiness appears once you have practice results." : "Average mastery across your exam topics."}</p>
          </div>
          <div
            className={styles.readinessRing}
            role="img"
            aria-label={readiness == null ? "Exam readiness not available yet" : `Exam readiness ${readiness} percent`}
            style={{ background: `conic-gradient(#a2cc70 0deg ${(readiness ?? 0) * 3.6}deg,#e1e9d6 ${(readiness ?? 0) * 3.6}deg 360deg)` }}
          >
            <div><strong>{readiness ?? "–"}{readiness != null && <span>%</span>}</strong><small>READY</small></div>
          </div>
        </article>

        <article className={`${styles.card} ${styles.examCard}`}>
          <div className={styles.cardIcon}><Icon name="shield" size={21} /></div>
          <div className={styles.metricTop}><span>Your exam goal</span><Icon name="target" size={17} /></div>
          {primary ? (
            <>
              <strong className={styles.examName}>{primary.certification_name}</strong>
              <span className={styles.examCode}>{primary.certification_slug}</span>
              <div className={styles.examFooter}>
                <span><Icon name="calendar" size={16} /> {targetDate ? `Target: ${formatDate(targetDate)}` : "No target date set"}</span>
                {daysLeft != null && <span className={styles.examTag}>{daysLeft >= 0 ? `${daysLeft} days left` : "Date passed"}</span>}
              </div>
            </>
          ) : (
            <>
              <strong className={styles.examName}>No certification yet</strong>
              <div className={styles.examFooter}><Link href="/certifications" className={styles.smallLink}>Browse certifications <Icon name="arrow" size={15} /></Link></div>
            </>
          )}
        </article>
      </section>

      <div className={styles.dashboardGrid}>
        <div className={styles.leftStack}>
          <section className={`${styles.card} ${styles.planner}`} aria-labelledby="planner-heading">
            <div className={styles.cardHeading}>
              <div><span className={styles.sectionKicker}>YOUR ROUTINE</span><h2 id="planner-heading">This week</h2></div>
              <button className={styles.subtleButton} onClick={openGoal}><Icon name="edit" size={15} /> Edit goal</button>
            </div>
            <div className={styles.days} aria-label="This week">
              {week.map((d) => (
                <button key={d.date} onClick={() => setSelectedDay(d.date)} className={`${styles.day} ${selectedDay === d.date ? styles.dayActive : ""}`} aria-pressed={selectedDay === d.date} aria-label={d.isToday ? `${d.day} ${d.date}, today` : `${d.day} ${d.date}`}>
                  <span>{d.day}</span><strong>{d.date}</strong>{d.isToday && <i />}
                </button>
              ))}
            </div>
            <div className={styles.studyGoal}>
              <span><Icon name="target" size={17} /> Weekly goal</span>
              <strong>{user.weekly_study_hours != null ? `${user.weekly_study_hours} study hours` : "Not set"}</strong>
            </div>
            <div className={styles.lessonCard}>
              <div className={styles.lessonIcon}><Icon name={primary ? "sparkle" : "book"} size={20} /></div>
              <div className={styles.lessonBody}>
                <span className={styles.lessonTag}>UP NEXT</span>
                {primary ? (
                  <>
                    <h3>{weakest ? `Review ${weakest.name}` : `Study ${primary.certification_name}`}</h3>
                    <p>{weakest ? `Your weakest topic right now (${Math.round(weakest.mastery_score)}% mastery).` : "Ask the AI Tutor to walk you through the first topic."}</p>
                  </>
                ) : (
                  <>
                    <h3>Choose your first certification</h3>
                    <p>Enrolling tells the tutor which material to use.</p>
                  </>
                )}
              </div>
              <Link className={styles.continueButton} href={primary ? "/tutor" : "/certifications"}>{primary ? "Ask tutor" : "Browse"}<Icon name="arrow" size={16} /></Link>
            </div>
          </section>

          <section className={`${styles.card} ${styles.topics}`} aria-labelledby="topics-heading">
            <div className={styles.cardHeading}><div><span className={styles.sectionKicker}>KNOW YOUR STRENGTHS</span><h2 id="topics-heading">Topic performance</h2></div></div>
            {topics.length === 0 ? (
              <p className={styles.cardDescription}>
                {context == null ? "Topic results are unavailable right now." : "Your topic results appear here after your first practice questions."}
              </p>
            ) : (
              <>
                <p className={styles.cardDescription}>Mastery per exam topic{primary ? ` for ${primary.certification_name}` : ""}.</p>
                <div className={styles.topicRows}>
                  {topics.map((topic) => (
                    <div className={styles.topicRow} key={`${topic.certification_id}-${topic.name}`}>
                      <div className={styles.topicLabels}><strong>{topic.name}</strong><span>{Math.round(topic.mastery_score)}%</span></div>
                      <div className={styles.topicTrack}><span className={topic.mastery_score < 60 ? styles.topicAmber : styles.topicGreen} style={{ width: `${Math.min(100, Math.max(0, topic.mastery_score))}%` }} /></div>
                    </div>
                  ))}
                </div>
                {weakest && <div className={styles.topicHint}><span>✳</span><p><strong>Your focus:</strong> give {weakest.name} a little extra attention this week.</p></div>}
              </>
            )}
          </section>
        </div>

        <div className={styles.rightStack}>
          <section className={styles.coachCard} aria-labelledby="coach-heading">
            <div className={styles.coachHeading}><span className={styles.coachIcon}><Icon name="sparkle" size={22} /></span><span className={styles.onlinePill}><i /> ALWAYS HERE</span></div>
            <div className={styles.coachKicker}>YOUR LEARNING COMPANION</div>
            <h2 id="coach-heading">A question? <em>Ask away.</em></h2>
            <p>Stuck on a topic? The AI Tutor answers from your certification&apos;s material and shows its sources.</p>
            <Link className={styles.coachAction} href="/tutor">Chat with the AI Tutor<Icon name="arrow" size={17} /></Link>
          </section>

          <section className={`${styles.card} ${styles.activity}`} aria-labelledby="activity-heading">
            <div className={styles.cardHeading}><div><span className={styles.sectionKicker}>YOUR MOMENTUM</span><h2 id="activity-heading">Recent enrollments</h2></div></div>
            {recent.length === 0 ? (
              <p className={styles.cardDescription}>Nothing yet. Enroll in a certification to get started.</p>
            ) : (
              <div className={styles.activityList}>
                {recent.map((e) => (
                  <div className={styles.activityItem} key={e.id}>
                    <span className={styles.activityIcon}><Icon name={activityIcon[e.status]} size={18} /></span>
                    <div className={styles.activityCopy}><strong>{e.certification_name}</strong><span>Enrolled {formatDate(e.created_at)}</span></div>
                    <span className={styles.activityScore}>{e.status}</span>
                  </div>
                ))}
              </div>
            )}
            <Link href="/certifications" className={styles.activityLink}>All certifications <Icon name="arrow" size={15} /></Link>
          </section>
        </div>
      </div>
      <footer className={styles.footer}><span>Edgely · Learn smarter. Certify faster.</span></footer>

      {goalOpen && (
        <div className={styles.modalOverlay} onMouseDown={(e) => { if (e.target === e.currentTarget && !savingGoal) setGoalOpen(false); }}>
          <section className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="goal-title">
            <div className={styles.modalHeader}><span className={styles.modalIcon}><Icon name="target" /></span><button onClick={() => setGoalOpen(false)} aria-label="Close"><Icon name="close" /></button></div>
            <h2 id="goal-title">Set your weekly study goal</h2>
            <p>How many hours would you like to study each week? Leave it empty to clear the goal.</p>
            <form onSubmit={submitGoal}>
              <label htmlFor="weekly-goal">Hours per week</label>
              <input id="weekly-goal" autoFocus type="number" min="0" max="168" step="1" value={draftHours} onChange={(e) => setDraftHours(e.target.value)} />
              {goalError && <p role="alert" style={{ color: "#8d3f22" }}>{goalError}</p>}
              <div className={styles.modalActions}>
                <button type="button" className={styles.cancelButton} onClick={() => setGoalOpen(false)} disabled={savingGoal}>Cancel</button>
                <button type="submit" className={styles.confirmButton} disabled={savingGoal}>{savingGoal ? "Saving…" : "Save goal"}</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </WorkspaceShell>
  );
}
