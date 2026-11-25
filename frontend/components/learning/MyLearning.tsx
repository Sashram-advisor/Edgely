"use client";

import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

import { awards, courses, days, duration, schedule } from "./data";
import styles from "./learning.module.css";

const tabs = ["My Courses", "Study Plan", "Completed"] as const;
const filters = ["In progress", "All", "Not started"] as const;

type Tab = (typeof tabs)[number];
type Filter = (typeof filters)[number];
type Course = (typeof courses)[number];

type StudyGoal = {
  hours: number;
  sessions: number;
  days: string[];
};

const defaultGoal: StudyGoal = {
  hours: 6,
  sessions: 5,
  days: ["Mon", "Tue", "Wed", "Fri", "Sat"],
};

const storageKey = "edgely.learning.demo.v1";

function Dial({
  value,
  label,
  fraction = 1,
}: {
  value: string;
  label: string;
  fraction?: number;
}) {
  const angle = Math.min(1, Math.max(0, fraction)) * 360;

  return (
    <div
      className={styles.dial}
      style={{ "--angle": `${angle}deg` } as CSSProperties}
    >
      <div>
        <strong>{value}</strong>
        <small>{label}</small>
      </div>
    </div>
  );
}

function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    dialog?.showModal();

    return () => {
      dialog?.close();
    };
  }, []);

  return (
    <dialog
      ref={dialogRef}
      className={styles.modal}
      aria-labelledby="learning-dialog-title"
      onCancel={onClose}
    >
      <header>
        <h2 id="learning-dialog-title">{title}</h2>
        <button type="button" aria-label="Close" onClick={onClose}>
          ×
        </button>
      </header>

      {children}
    </dialog>
  );
}

function LessonTracker({ course }: { course: Course }) {
  return (
    <div className={styles.tracker}>
      <b>Lesson progress</b>

      <div
        className={styles.segments}
        role="meter"
        aria-label={`${course.name} lessons completed`}
        aria-valuemin={0}
        aria-valuemax={course.lessons.length}
        aria-valuenow={course.initial}
      >
        {course.lessons.map((lesson, index) => (
          <i key={lesson} data-done={index < course.initial} />
        ))}
      </div>

      <div className={styles.counts}>
        <span>{course.initial} completed</span>
        <span>{course.lessons.length - course.initial} to go</span>
      </div>
    </div>
  );
}

function isStudyGoal(value: unknown): value is StudyGoal {
  if (!value || typeof value !== "object") return false;

  const goal = value as Partial<StudyGoal>;

  return (
    typeof goal.hours === "number" &&
    Number.isInteger(goal.hours) &&
    goal.hours >= 1 &&
    goal.hours <= 80 &&
    typeof goal.sessions === "number" &&
    Number.isInteger(goal.sessions) &&
    goal.sessions >= 1 &&
    goal.sessions <= 14 &&
    Array.isArray(goal.days) &&
    goal.days.length > 0 &&
    goal.days.every((day) => days.includes(day))
  );
}

export default function MyLearning() {
  const [activeTab, setActiveTab] = useState<Tab>("My Courses");
  const [activeFilter, setActiveFilter] = useState<Filter>("In progress");
  const [search, setSearch] = useState("");
  const [selectedDay, setSelectedDay] = useState<number | null>(null);

  const [goal, setGoal] = useState<StudyGoal>(defaultGoal);
  const [draftGoal, setDraftGoal] = useState<StudyGoal | null>(null);

  const [completedSessions, setCompletedSessions] = useState<string[]>(
    schedule.slice(0, 2).map((session) => session.title)
  );

  const [storageReady, setStorageReady] = useState(false);

  const [preview, setPreview] = useState<{
    title: string;
    content: ReactNode;
  } | null>(null);

  useEffect(() => {
  function readTabFromUrl() {
    const tab = new URLSearchParams(window.location.search).get("tab");

    if (tab === "plan") {
      setActiveTab("Study Plan");
    } else if (tab === "completed") {
      setActiveTab("Completed");
    } else {
      setActiveTab("My Courses");
    }
  }

  window.addEventListener("popstate", readTabFromUrl);

  const timer = window.setTimeout(() => {
    readTabFromUrl();

    try {
      const saved = JSON.parse(
        localStorage.getItem(storageKey) || "null"
      );

      if (isStudyGoal(saved?.goal)) {
        setGoal(saved.goal);
      }

      if (Array.isArray(saved?.done)) {
        const savedTitles: unknown[] = saved.done;

        setCompletedSessions(
          schedule
            .filter((session) => savedTitles.includes(session.title))
            .map((session) => session.title)
        );
      }
    } catch {
      // Use the sample defaults when browser storage is unavailable.
    }

    setStorageReady(true);
  }, 0);

  return () => {
    window.clearTimeout(timer);
    window.removeEventListener("popstate", readTabFromUrl);
  };
}, []);

  useEffect(() => {
    if (!storageReady) return;

    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({
          goal,
          done: completedSessions,
        })
      );
    } catch {
      // Changes still work during the current visit.
    }
  }, [goal, completedSessions, storageReady]);

  function switchTab(tab: Tab) {
    const url = new URL(window.location.href);

    if (tab === "My Courses") {
      url.searchParams.delete("tab");
    } else {
      url.searchParams.set(
        "tab",
        tab === "Study Plan" ? "plan" : "completed"
      );
    }

    window.history.pushState(null, "", url);
    setActiveTab(tab);
  }

  function toggleSession(title: string) {
    setCompletedSessions((current) =>
      current.includes(title)
        ? current.filter((item) => item !== title)
        : [...current, title]
    );
  }

  function showCourse(course: Course) {
    setPreview({
      title: course.name,
      content: (
        <>
          <LessonTracker course={course} />

          <ol>
            {course.lessons.map((lesson, index) => (
              <li key={lesson}>
                {lesson}
                {index < course.initial ? " ✓" : ""}
              </li>
            ))}
          </ol>
        </>
      ),
    });
  }

  function showNextLesson(course: Course) {
    setPreview({
      title: course.lessons[course.initial],
      content: (
        <>
          <p>{course.name}</p>
          <p>
            Lesson {course.initial + 1} of {course.lessons.length}
          </p>
          <p>The full lesson screen is coming next.</p>
        </>
      ),
    });
  }

  const visibleCourses = courses.filter((course) => {
    const matchesSearch = course.name
      .toLowerCase()
      .includes(search.trim().toLowerCase());

    const matchesStatus =
      activeFilter === "All" ||
      (activeFilter === "Not started"
        ? course.initial === 0
        : course.initial > 0);

    return matchesSearch && matchesStatus;
  });

  // Includes 215 minutes of earlier sample study activity.
  const studiedMinutes =
    215 +
    schedule
      .filter((session) => completedSessions.includes(session.title))
      .reduce((total, session) => total + session.minutes, 0);

  const goalMinutes = goal.hours * 60;
  const goalFraction = studiedMinutes / goalMinutes;

  const visibleSessions = schedule.filter((session) =>
    selectedDay === null
      ? !completedSessions.includes(session.title)
      : session.day === selectedDay
  );

  return (
    <div className={styles.page}>
      <header>
        <small>YOUR LEARNING SPACE</small>
        <h1>My Learning</h1>
        <p>
          Pick up where you left off and make room for your next milestone.
        </p>
      </header>

      <nav className={styles.tabs} aria-label="My Learning sections">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            aria-pressed={activeTab === tab}
            onClick={() => switchTab(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>

      {activeTab === "My Courses" && (
        <>
          <section className={styles.hero}>
            <div>
              <small>YOUR CURRENT LESSON</small>
              <h2>VPC fundamentals</h2>
              <p>
                AWS Solutions Architect Associate · Subnets &amp; routing
                · 25 min
              </p>
            </div>

            <button
              className={styles.lime}
              onClick={() => showNextLesson(courses[0])}
            >
              Continue Learning →
            </button>

            <Dial value="7" label="day streak" />
          </section>

          <label className={styles.search}>
            <input
              type="search"
              aria-label="Search your courses"
              placeholder="Search your courses"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>

          <div className={styles.filters} aria-label="Course status">
            {filters.map((filter) => (
              <button
                key={filter}
                aria-pressed={activeFilter === filter}
                onClick={() => setActiveFilter(filter)}
              >
                {filter}
              </button>
            ))}
          </div>

          {visibleCourses.map((course) => (
            <article key={course.id} className={styles.course}>
              <div>
                <small>{course.provider.toUpperCase()}</small>
                <h3>{course.name}</h3>

                <p>
                  {course.initial ? "Next lesson" : "First lesson"} ·{" "}
                  {course.lessons[course.initial]}
                </p>

                <div className={styles.actions}>
                  <button
                    className={styles.lime}
                    onClick={() => showNextLesson(course)}
                  >
                    {course.initial ? "Continue Learning" : "Start Course"} →
                  </button>

                  <button
                    className={styles.dark}
                    onClick={() => showCourse(course)}
                  >
                    View Course
                  </button>
                </div>
              </div>

              <LessonTracker course={course} />
            </article>
          ))}

          {visibleCourses.length === 0 && (
            <p role="status">No courses match your search and filter.</p>
          )}
        </>
      )}

      {activeTab === "Study Plan" && (
        <>
          <section className={styles.hero}>
            <Dial
              value={`${Math.round(goalFraction * 100)}%`}
              label="weekly goal"
              fraction={goalFraction}
            />

            <div>
              <small>YOUR WEEKLY GOAL</small>
              <h2>
                {duration(studiedMinutes)} of {goal.hours} hours
              </h2>
              <p>
                {goalFraction >= 1
                  ? "Weekly goal reached"
                  : `${duration(goalMinutes - studiedMinutes)} to go this week`}
              </p>
            </div>

            <button
              className={styles.lime}
              onClick={() =>
                setDraftGoal({ ...goal, days: [...goal.days] })
              }
            >
              Edit study goals
            </button>
          </section>

          <section className={styles.calendar}>
            <h3>November 9–15, 2026</h3>

            <div className={styles.days}>
              {days.map((day, index) => {
                const sessions = schedule.filter(
                  (session) => session.day === index
                );

                const minutes = sessions.reduce(
                  (total, session) => total + session.minutes,
                  0
                );

                const allComplete =
                  sessions.length > 0 &&
                  sessions.every((session) =>
                    completedSessions.includes(session.title)
                  );

                return (
                  <button
                    key={day}
                    aria-pressed={selectedDay === index}
                    data-highlight={(selectedDay ?? 1) === index}
                    onClick={() =>
                      setSelectedDay(selectedDay === index ? null : index)
                    }
                  >
                    <small>{day.toUpperCase()}</small>
                    <strong>{9 + index}</strong>
                    <span>
                      {sessions.length === 0
                        ? "Rest day"
                        : allComplete
                          ? "✓ Done"
                          : `${minutes} min`}
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <div className={styles.planGrid}>
            <section className={styles.card}>
              <h3>
                {selectedDay === null
                  ? "Your next sessions"
                  : `${days[selectedDay]} sessions`}
              </h3>

              <p>Recommended focus · VPC &amp; networking</p>

              {visibleSessions.map((session) => (
                <label className={styles.session} key={session.title}>
                  <span>
                    <small>
                      {days[session.day]} · {session.minutes} min
                    </small>
                    <b>{session.title}</b>
                  </span>

                  <input
                    type="checkbox"
                    aria-label={`Mark ${session.title} complete`}
                    checked={completedSessions.includes(session.title)}
                    onChange={() => toggleSession(session.title)}
                  />
                </label>
              ))}

              {visibleSessions.length === 0 && (
                <p>
                  {selectedDay === null
                    ? "All scheduled sessions complete."
                    : "No sessions scheduled."}
                </p>
              )}

              {selectedDay !== null && (
                <button onClick={() => setSelectedDay(null)}>
                  Show upcoming sessions
                </button>
              )}
            </section>

            <section className={styles.card}>
              <h3>This week</h3>

              <h2>
                {completedSessions.length} of {goal.sessions} sessions
              </h2>

              <progress
                aria-label="Weekly sessions completed"
                value={Math.min(completedSessions.length, goal.sessions)}
                max={goal.sessions}
              />

              {completedSessions.map((title) => (
                <p key={title}>✓ {title}</p>
              ))}

              <p>
                {Math.max(0, goal.sessions - completedSessions.length)}{" "}
                sessions to go
              </p>
            </section>
          </div>
        </>
      )}

      {activeTab === "Completed" && (
        <>
          <section className={styles.hero}>
            <Dial value="2" label="courses" />

            <div>
              <small>YOUR MILESTONES</small>
              <h2>Look how far you’ve come.</h2>
              <p>14 lessons completed · 7h 25m of learning</p>
            </div>
          </section>

          <h3>Finished courses</h3>

          <div className={styles.finished}>
            {awards.map((award) => (
              <article className={styles.award} key={award.name}>
                <small>✓ COMPLETED</small>
                <h3>{award.name}</h3>
                <p>Completed {award.date}</p>
                <b>Study time · {duration(award.minutes)}</b>
                <p>
                  {award.count} of {award.count} lessons complete
                </p>

                <div className={styles.medal}>
                  <div>
                    <small>ACHIEVEMENT UNLOCKED</small>
                    <strong>{award.award}</strong>
                  </div>
                </div>

                <button
                  className={styles.dark}
                  onClick={() =>
                    setPreview({
                      title: award.name,
                      content: (
                        <p>
                          You completed all {award.count} lessons on{" "}
                          {award.date}, studied for{" "}
                          {duration(award.minutes)}, and earned the{" "}
                          {award.award} achievement.
                        </p>
                      ),
                    })
                  }
                >
                  View Course
                </button>
              </article>
            ))}
          </div>
        </>
      )}

      {preview && (
        <Modal title={preview.title} onClose={() => setPreview(null)}>
          {preview.content}
        </Modal>
      )}

      {draftGoal && (
        <Modal
          title="Edit study goals"
          onClose={() => setDraftGoal(null)}
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();

              if (isStudyGoal(draftGoal)) {
                setGoal(draftGoal);
                setDraftGoal(null);
              }
            }}
          >
            <label>
              Weekly study hours
              <input
                required
                type="number"
                min="1"
                max="80"
                step="1"
                value={draftGoal.hours || ""}
                onChange={(event) =>
                  setDraftGoal({
                    ...draftGoal,
                    hours: Number(event.target.value),
                  })
                }
              />
            </label>

            <label>
              Sessions per week
              <input
                required
                type="number"
                min="1"
                max="14"
                step="1"
                value={draftGoal.sessions || ""}
                onChange={(event) =>
                  setDraftGoal({
                    ...draftGoal,
                    sessions: Number(event.target.value),
                  })
                }
              />
            </label>

            <fieldset>
              <legend>Preferred study days</legend>

              {days.map((day) => (
                <label key={day}>
                  <input
                    type="checkbox"
                    checked={draftGoal.days.includes(day)}
                    onChange={(event) =>
                      setDraftGoal({
                        ...draftGoal,
                        days: event.target.checked
                          ? [...draftGoal.days, day]
                          : draftGoal.days.filter((item) => item !== day),
                      })
                    }
                  />
                  {day}
                </label>
              ))}
            </fieldset>

            <div className={styles.actions}>
              <button
                type="submit"
                className={styles.lime}
                disabled={draftGoal.days.length === 0}
              >
                Save goals
              </button>

              <button type="button" onClick={() => setDraftGoal(null)}>
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}