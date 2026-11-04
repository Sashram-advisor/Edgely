"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Dashboard.module.css";


type IconName = "grid" | "book" | "calendar" | "check" | "chart" | "sparkle" | "settings" | "bell" | "chevron" | "arrow" | "menu" | "close" | "clock" | "target" | "bolt" | "trophy" | "bookmark" | "search" | "user" | "logout" | "edit" | "play" | "shield";

function Icon({ name, size = 20, strokeWidth = 1.8 }: { name: IconName; size?: number; strokeWidth?: number }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const paths: Record<IconName, React.ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    book: <><path d="M12 7c-2.5-1.9-5.5-2-9-1v13c3.5-1 6.5-.9 9 1 2.5-1.9 5.5-2 9-1V6c-3.5-1-6.5-.9-9 1Z"/><path d="M12 7v13"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/></>,
    check: <><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></>,
    chart: <><path d="M4 20V4M4 20h17M8 16l4-5 3 2 5-7"/></>,
    sparkle: <><path d="m12 2 2.3 7.7L22 12l-7.7 2.3L12 22l-2.3-7.7L2 12l7.7-2.3L12 2Z"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M9.5 2.8 8.8 5a8 8 0 0 0-2 1.2L4.5 5.7 3 8.3l1.6 1.8a8 8 0 0 0 0 3.8L3 15.7l1.5 2.6 2.3-.5A8 8 0 0 0 8.8 19l.7 2.2h3L13.2 19a8 8 0 0 0 2-1.2l2.3.5 1.5-2.6-1.6-1.8a8 8 0 0 0 0-3.8L19 8.3l-1.5-2.6-2.3.5a8 8 0 0 0-2-1.2l-.7-2.2h-3Z"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
    chevron: <path d="m6 9 6 6 6-6"/>, arrow: <><path d="M5 12h14m-6-6 6 6-6 6"/></>,
    menu: <path d="M4 7h16M4 12h16M4 17h16"/>, close: <path d="M5 5 19 19M19 5 5 19"/>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    target: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></>,
    bolt: <path d="M13 2 5 13h6l-1 9 9-12h-6l0-8Z"/>,
    trophy: <><path d="M8 3h8v9a4 4 0 0 1-8 0V3ZM8 5H4v3a4 4 0 0 0 4 4M16 5h4v3a4 4 0 0 1-4 4M12 16v4m-5 1h10"/></>,
    bookmark: <path d="M6 3h12v18l-6-4-6 4V3Z"/>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    logout: <><path d="M10 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5M13 8l4 4-4 4m4-4H8"/></>,
    edit: <><path d="M4 20h4l11-11-4-4L4 16v4ZM13 7l4 4"/></>,
    play: <path d="m9 5 10 7-10 7V5Z"/>,
    shield: <><path d="m12 2 8 4v6c0 5-3 8-8 10-5-2-8-5-8-10V6l8-4Z"/><path d="m8 12 3 3 5-6"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" {...common}>{paths[name]}</svg>;
}

const navigation: { label: string; href: string; icon: IconName }[] = [
  { label: "Overview", href: "/dashboard", icon: "grid" },
  { label: "AI Tutor", href: "/tutor", icon: "sparkle" },
  { label: "Study Plan", href: "/study-plan", icon: "calendar" },
  { label: "Practice", href: "/quiz", icon: "check" },
  { label: "Progress", href: "/progress", icon: "chart" },
];

const days = [
  { day: "Mon", date: 2 }, { day: "Tue", date: 3 }, { day: "Wed", date: 4 },
  { day: "Thu", date: 5 }, { day: "Fri", date: 6 }, { day: "Sat", date: 7 }, { day: "Sun", date: 8 },
];

const topics = [
  { name: "Cloud Fundamentals", score: 86, color: "green" },
  { name: "Security & Identity", score: 72, color: "green" },
  { name: "Networking", score: 58, color: "amber" },
  { name: "Cost Optimization", score: 43, color: "amber" },
];

const activity = [
  { icon: "check" as IconName, title: "Cloud Architecture Practice", meta: "Practice quiz · 12 questions", time: "Today", score: "83%" },
  { icon: "book" as IconName, title: "Introduction to IAM", meta: "Lesson completed", time: "Yesterday", score: "+40 XP" },
  { icon: "trophy" as IconName, title: "One-week learning streak", meta: "Achievement unlocked", time: "Oct 30", score: "7 days" },
];

export default function Dashboard() {
  const pathname = usePathname();
  const [mobileNav, setMobileNav] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [goalOpen, setGoalOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);
  const [selectedDay, setSelectedDay] = useState(4);
  const [weeklyGoal, setWeeklyGoal] = useState(5);
  const [draftGoal, setDraftGoal] = useState("5");
  const [lessonDone, setLessonDone] = useState(false);
  const [noticeRead, setNoticeRead] = useState(false);
  const [coachOpen, setCoachOpen] = useState(false);
  const [coachMessage, setCoachMessage] = useState("");
  const [coachQuestion, setCoachQuestion] = useState("");

  const openGoal = () => { setDraftGoal(String(weeklyGoal)); setGoalOpen(true); };
  const submitGoal = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const next = Number(draftGoal);
    if (Number.isInteger(next) && next >= 1 && next <= 14) { setWeeklyGoal(next); setGoalOpen(false); }
  };

  return (
    <div className={styles.app}>
      {mobileNav && <button className={styles.mobileScrim} onClick={() => setMobileNav(false)} aria-label="Close navigation" />}
      <aside className={`${styles.sidebar} ${mobileNav ? styles.sidebarOpen : ""}`}>
        <div className={styles.brand}><span className={styles.brandGlyph}>✳</span><span>edgely<span className={styles.brandDot}>.</span></span><button className={styles.closeMobile} onClick={() => setMobileNav(false)} aria-label="Close sidebar"><Icon name="close" /></button></div>
        <div className={styles.sidebarCaption}>YOUR WORKSPACE</div>
        <nav className={styles.nav} aria-label="Learner navigation">
          {navigation.map((item) => <Link key={item.href} className={`${styles.navLink} ${pathname === item.href ? styles.activeNav : ""}`} href={item.href} onClick={() => setMobileNav(false)}><Icon name={item.icon} size={19}/>{item.label}{pathname === item.href && <span className={styles.activeDot} />}</Link>)}
        </nav>
        <div className={styles.sideSpacer} />
        <div className={styles.tutorPromo}><div className={styles.promoStars}>✦ <span>✳</span></div><div className={styles.promoTitle}>A little help goes a long way.</div><p>Ask your AI Tutor whenever you get stuck.</p><Link href="/tutor" className={styles.promoButton}>Ask AI Tutor <Icon name="arrow" size={16}/></Link></div>
        <div className={styles.accountWrap}>
          {accountOpen && <div className={styles.accountMenu} role="menu"><Link role="menuitem" href="/profile"><Icon name="user" size={17}/> My Profile</Link><Link role="menuitem" href="/settings"><Icon name="settings" size={17}/> Settings</Link><button role="menuitem" onClick={() => {setAccountOpen(false);setSignOutOpen(true);}}><Icon name="logout" size={17}/> Sign Out</button></div>}
          <button className={styles.accountButton} aria-expanded={accountOpen} aria-haspopup="menu" onClick={() => setAccountOpen(!accountOpen)}><span className={styles.avatar}>KT</span><span className={styles.accountLabel}><strong>My Account</strong><small>Learner profile</small></span><Icon name="chevron" size={16}/></button>
        </div>
      </aside>

      <div className={styles.mainColumn}>
        <header className={styles.topbar}>
          <div className={styles.topbarLeft}><button className={styles.menuButton} onClick={() => setMobileNav(true)} aria-label="Open navigation"><Icon name="menu" /></button><span className={styles.breadcrumb}>My Workspace</span><span className={styles.breadcrumbSlash}>/</span><strong>Overview</strong></div>
          <div className={styles.topbarRight}>
            <span className={styles.todayBadge}><Icon name="calendar" size={15}/> November 2026</span>
            <div className={styles.notificationWrap}><button className={styles.iconButton} onClick={() => {setNotificationsOpen(!notificationsOpen);setAccountOpen(false);}} aria-expanded={notificationsOpen} aria-label="Notifications"><Icon name="bell" size={20}/>{!noticeRead && <span className={styles.noticeDot} />}</button>
              {notificationsOpen && <div className={styles.notificationPanel}><div className={styles.notificationHead}><strong>Notifications</strong><button onClick={() => {setNoticeRead(true);setNotificationsOpen(false);}}>Mark all read</button></div><div className={styles.notificationRow}><span className={styles.notificationEmoji}>✦</span><div><strong>Your next lesson is ready</strong><p>Keep your learning streak going today.</p><small>Just now</small></div></div><div className={styles.notificationRow}><span className={styles.notificationEmoji}>✓</span><div><strong>Nice work on your quiz!</strong><p>You scored 83% in Cloud Architecture.</p><small>Yesterday</small></div></div></div>}
            </div>
            <button className={styles.headerAvatar} onClick={() => setAccountOpen(!accountOpen)} title="Account options">KT</button>
          </div>
        </header>

        <main className={styles.content}>
          <section className={styles.intro} aria-label="Welcome">
            <div><div className={styles.eyebrow}><span className={styles.eyebrowLine}/> YOUR LEARNING SPACE</div><h1>Good to see you again <span className={styles.wave}>✳</span></h1><p>One step closer to the certification you&apos;re working toward.</p></div>
            <div className={styles.streak}><div className={styles.streakIcon}><Icon name="bolt" size={19}/></div><div><strong>7 day streak</strong><span>Keep your momentum!</span></div></div>
          </section>

          <section className={styles.hero} aria-label="Learning motivation"><div className={styles.heroContent}><span className={styles.heroLabel}>YOUR JOURNEY, YOUR PACE</span><h2>Small steps today.<br/><em>Big things tomorrow.</em></h2><p>Keep showing up. Every lesson brings you closer to your goal.</p><Link href="/study-plan" className={styles.heroButton}>View my study plan <Icon name="arrow" size={17}/></Link></div><div className={styles.heroArtwork} aria-hidden="true"><div className={styles.orbOuter}><div className={styles.orbMid}><div className={styles.orbInner}>✳</div></div></div><span className={styles.heroStar1}>✦</span><span className={styles.heroStar2}>✧</span><span className={styles.heroStar3}>✳</span></div></section>

          <div className={styles.sectionHeading}><div><span className={styles.sectionKicker}>AT A GLANCE</span><h2>Your progress</h2></div><Link href="/progress" className={styles.textLink}>Full progress report <Icon name="arrow" size={16}/></Link></div>
          <section className={styles.metrics} aria-label="Progress overview">
            <article className={`${styles.card} ${styles.metricCard}`}><div className={styles.cardIcon}><Icon name="book" size={21}/></div><div className={styles.metricTop}><span>Learning progress</span><Icon name="arrow" size={17}/></div><strong className={styles.metricNumber}>68<span>%</span></strong><p>Course modules completed</p><div className={styles.progressTrack}><span style={{width:"68%"}}/></div><div className={styles.metricFoot}><span>17 of 25 lessons</span><span>8 to go</span></div></article>
            <article className={`${styles.card} ${styles.readinessCard}`}><div className={styles.readinessCopy}><div className={styles.cardIcon}><Icon name="target" size={21}/></div><span className={styles.metricTop}>Exam readiness</span><strong>Getting closer!</strong><p>Your knowledge is growing every day.</p><Link href="/progress" className={styles.smallLink}>View breakdown <Icon name="arrow" size={15}/></Link></div><div className={styles.readinessRing} role="img" aria-label="Exam readiness 74 percent"><div><strong>74<span>%</span></strong><small>READY</small></div></div></article>
            <article className={`${styles.card} ${styles.examCard}`}><div className={styles.cardIcon}><Icon name="shield" size={21}/></div><div className={styles.metricTop}><span>Your exam goal</span><Icon name="target" size={17}/></div><strong className={styles.examName}>AWS Cloud Practitioner</strong><span className={styles.examCode}>CLF-C02</span><div className={styles.examFooter}><span><Icon name="calendar" size={16}/> Target: Dec 15, 2026</span><span className={styles.examTag}>On track</span></div></article>
          </section>

          <div className={styles.dashboardGrid}>
            <div className={styles.leftStack}>
              <section className={`${styles.card} ${styles.planner}`} aria-labelledby="planner-heading"><div className={styles.cardHeading}><div><span className={styles.sectionKicker}>YOUR ROUTINE</span><h2 id="planner-heading">This week&apos;s study plan</h2></div><button className={styles.subtleButton} onClick={openGoal}><Icon name="edit" size={15}/> Edit goal</button></div><div className={styles.days} aria-label="Select a study day">{days.map(d=><button key={d.date} onClick={()=>setSelectedDay(d.date)} className={`${styles.day} ${selectedDay===d.date?styles.dayActive:""}`} aria-pressed={selectedDay===d.date}><span>{d.day}</span><strong>{d.date}</strong><i/></button>)}</div><div className={styles.studyGoal}><span><Icon name="target" size={17}/> Weekly goal</span><strong>{weeklyGoal} study sessions</strong></div><div className={styles.lessonCard}><div className={styles.lessonIcon}><Icon name={lessonDone?"check":"play"} size={20}/></div><div className={styles.lessonBody}><span className={styles.lessonTag}>{lessonDone?"COMPLETED":"UP NEXT"} · {selectedDay===4?"TODAY":`NOV ${selectedDay}`}</span><h3>{lessonDone?"Great work! Lesson complete":"Cloud Security Essentials"}</h3><p>{lessonDone?"You've made progress toward your certification.":"Understand the shared responsibility model"}</p><span className={styles.lessonDuration}><Icon name="clock" size={15}/> 25 min lesson</span></div><button className={styles.continueButton} onClick={()=>setLessonDone(!lessonDone)}>{lessonDone?"Undo":"Mark done"}<Icon name={lessonDone?"edit":"arrow"} size={16}/></button></div><div className={styles.plannerBottom}><span>{lessonDone?"Your progress has been updated in this demo.":"A little progress is still progress."}</span><Link href="/study-plan">Full study plan <Icon name="arrow" size={15}/></Link></div></section>

              <section className={`${styles.card} ${styles.topics}`} aria-labelledby="topics-heading"><div className={styles.cardHeading}><div><span className={styles.sectionKicker}>KNOW YOUR STRENGTHS</span><h2 id="topics-heading">Topic performance</h2></div><Link className={styles.textLink} href="/progress">View insights <Icon name="arrow" size={16}/></Link></div><p className={styles.cardDescription}>See what you&apos;ve mastered and what could use another look.</p><div className={styles.topicRows}>{topics.map(topic=><div className={styles.topicRow} key={topic.name}><div className={styles.topicLabels}><strong>{topic.name}</strong><span>{topic.score}%</span></div><div className={styles.topicTrack}><span className={topic.color === "amber"?styles.topicAmber:styles.topicGreen} style={{width:`${topic.score}%`}}/></div></div>)}</div><div className={styles.topicHint}><span>✳</span><p><strong>Your focus:</strong> Give Cost Optimization a little extra attention this week.</p></div></section>
            </div>

            <div className={styles.rightStack}>
              <section className={`${styles.coachCard}`} aria-labelledby="coach-heading"><div className={styles.coachHeading}><span className={styles.coachIcon}><Icon name="sparkle" size={22}/></span><span className={styles.onlinePill}><i/> ALWAYS HERE</span></div><div className={styles.coachKicker}>YOUR LEARNING COMPANION</div><h2 id="coach-heading">A question? <em>Ask away.</em></h2><p>Stuck on a topic or need some motivation? Your AI Coach is here to help you move forward.</p><div className={styles.chatDemo}><div className={styles.chatQuestion}>How does cloud security work?</div><div className={styles.chatAnswer}><span>✳</span><p>Think of it like protecting your own home: different layers help keep everything safe.</p></div></div>{coachOpen && <form className={styles.coachInline} onSubmit={e=>{e.preventDefault();setCoachQuestion(coachMessage.trim());setCoachMessage("");}}><label htmlFor="coach-message">Ask a question (demo)</label><div><input id="coach-message" placeholder="Type your question..." value={coachMessage} onChange={e=>setCoachMessage(e.target.value)} /><button type="submit" aria-label="Submit example question"><Icon name="arrow" size={18}/></button></div>{coachQuestion && <p className={styles.coachDemoNote}>You asked: “{coachQuestion}” — AI responses will be connected by the AI team.</p>}</form>}<button className={styles.coachAction} onClick={()=>setCoachOpen(!coachOpen)}>{coachOpen?"Close chat preview":"Chat with AI Coach"}<Icon name="arrow" size={17}/></button></section>
              <section className={`${styles.card} ${styles.activity}`} aria-labelledby="activity-heading"><div className={styles.cardHeading}><div><span className={styles.sectionKicker}>YOUR MOMENTUM</span><h2 id="activity-heading">Recent activity</h2></div></div><div className={styles.activityList}>{activity.map(a=><div className={styles.activityItem} key={a.title}><span className={styles.activityIcon}><Icon name={a.icon} size={18}/></span><div className={styles.activityCopy}><strong>{a.title}</strong><span>{a.meta}</span><small>{a.time}</small></div><span className={styles.activityScore}>{a.score}</span></div>)}</div><Link href="/progress" className={styles.activityLink}>See all activity <Icon name="arrow" size={15}/></Link></section>
            </div>
          </div>
          <footer className={styles.footer}><span>Edgely · Learn smarter. Certify faster.</span><span>Dashboard preview · Sample data</span></footer>
        </main>
      </div>

      {goalOpen && <div className={styles.modalOverlay} onMouseDown={(e)=>{if(e.target===e.currentTarget)setGoalOpen(false)}}><section className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="goal-title"><div className={styles.modalHeader}><span className={styles.modalIcon}><Icon name="target"/></span><button onClick={()=>setGoalOpen(false)} aria-label="Close"><Icon name="close"/></button></div><h2 id="goal-title">Set your weekly study goal</h2><p>How many study sessions would you like to complete each week?</p><form onSubmit={submitGoal}><label htmlFor="weekly-goal">Sessions per week</label><input id="weekly-goal" autoFocus type="number" min="1" max="14" step="1" value={draftGoal} onChange={e=>setDraftGoal(e.target.value)} required/><div className={styles.modalActions}><button type="button" className={styles.cancelButton} onClick={()=>setGoalOpen(false)}>Cancel</button><button type="submit" className={styles.confirmButton}>Save goal</button></div></form></section></div>}
      {signOutOpen && <div className={styles.modalOverlay} onMouseDown={(e)=>{if(e.target===e.currentTarget)setSignOutOpen(false)}}><section className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="signout-title"><div className={styles.modalHeader}><span className={styles.modalIcon}><Icon name="logout"/></span><button onClick={()=>setSignOutOpen(false)} aria-label="Close"><Icon name="close"/></button></div><h2 id="signout-title">Sign out of Edgely?</h2><p>This is a frontend preview. Real sign-out will be connected when authentication is implemented.</p><div className={styles.modalActions}><button className={styles.cancelButton} onClick={()=>setSignOutOpen(false)}>Cancel</button><button className={styles.confirmButton} onClick={()=>setSignOutOpen(false)}>Got it</button></div></section></div>}
    </div>
  );
}
