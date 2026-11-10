"use client";

import Link from "next/link";
import { useState } from "react";
import "./homepage.css";

export default function HomePage() {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <>
<header className={menuOpen ? "site-header open" : "site-header"}>
<a className="brand" href="#top" aria-label="Edgely home">
<span className="brand-mark" aria-hidden="true">E</span>
<span>Edgely</span>
</a>
<button className="menu-btn" aria-label="Open menu" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? "✕" : "☰"}</button>
<nav className="nav" aria-label="Main navigation" onClick={() => setMenuOpen(false)}>
<a href="#features">Features</a>
<a href="#how">How it works</a>
<a href="#paths">Certification paths</a>
<a href="#about">About</a>
</nav>
<div className="header-actions">
<Link className="text-link" href="/login">Log in</Link>
<Link className="btn btn-dark btn-small" href="/register">Get started</Link>
</div>
</header>
<main id="top">
<section className="hero shell">
<div className="hero-copy">
<div className="eyebrow"><span className="dot"></span> AI-powered certification prep</div>
<h1>Turn your study time into <em>real progress.</em></h1>
<p className="hero-lead">
          Meet an AI tutor, coach, and assessor that learns how you learn — then builds a study path around your goals, weak areas, and exam date.
        </p>
<div className="hero-actions">
<Link className="btn btn-accent" href="/register">Start your learning path</Link>
<a className="btn btn-ghost" href="#how">See how it works <span aria-hidden="true">→</span></a>
</div>
<div className="trust-row" aria-label="Platform highlights">
<div><strong>Adaptive</strong><span>Study plans</span></div>
<div><strong>24/7</strong><span>AI tutoring</span></div>
<div><strong>Focused</strong><span>Weakness tracking</span></div>
</div>
</div>
<div className="hero-visual" aria-label="Preview of learner dashboard">
<div className="blob blob-a"></div>
<div className="blob blob-b"></div>
<div className="app-window">
<div className="window-bar">
<div className="window-dots"><span></span><span></span><span></span></div>
<span className="window-label">Learner dashboard</span>
<div className="avatar">KT</div>
</div>
<div className="app-body">
<aside className="app-sidebar">
<div className="mini-logo">E</div>
<span className="side-active">⌂</span>
<span>◫</span>
<span>✦</span>
<span>◌</span>
</aside>
<div className="dashboard">
<div className="dash-head">
<div>
<p className="micro">GOOD EVENING, KHANG</p>
<h2>Ready for today’s session?</h2>
</div>
<span className="pill">AWS SAA</span>
</div>
<div className="dash-grid">
<article className="readiness-card">
<div className="card-top"><span>Readiness score</span><span>+8% this week</span></div>
<div className="score-wrap">
<div className="score-ring"><span>72%</span></div>
<div>
<strong>On track</strong>
<p>Keep focusing on networking and resilience.</p>
</div>
</div>
</article>
<article className="streak-card">
<span className="card-kicker">STUDY STREAK</span>
<div className="streak-number">6 <small>days</small></div>
<div className="week-dots" aria-label="Study activity this week">
<span className="done">M</span><span className="done">T</span><span className="done">W</span><span className="done">T</span><span className="done">F</span><span className="done">S</span><span>S</span>
</div>
</article>
<article className="plan-card">
<div className="card-top"><span>Today’s learning plan</span><a href="#get-started">View plan</a></div>
<div className="task"><span className="task-icon">01</span><div><strong>VPC Fundamentals</strong><small>20 min · Concept review</small></div><span>›</span></div>
<div className="task"><span className="task-icon">02</span><div><strong>Security Groups Quiz</strong><small>10 questions · Adaptive</small></div><span>›</span></div>
<div className="task"><span className="task-icon">03</span><div><strong>Ask your AI Tutor</strong><small>Clarify your weakest topic</small></div><span>›</span></div>
</article>
<article className="coach-card">
<span className="spark">✦</span>
<div>
<span className="card-kicker">AI COACH</span>
<p>“Your networking score improved 11%. Let’s reinforce VPC routing before moving on.”</p>
<button type="button">Continue session →</button>
</div>
</article>
</div>
</div>
</div>
</div>
</div>
</section>
<section className="path-strip shell" id="paths">
<span>Prepare for certifications across</span>
<div className="path-logos" aria-label="Supported certification categories">
<strong>AWS</strong><strong>Azure</strong><strong>PMP</strong><strong>Scrum</strong><strong>CISSP</strong><strong>+ more</strong>
</div>
</section>
<section className="section shell" id="features">
<div className="section-heading split-heading">
<div>
<p className="eyebrow plain">BUILT AROUND YOUR PROGRESS</p>
<h2>More than a chatbot.<br />A learning system that adapts.</h2>
</div>
<p>
          Instead of sending every learner through the same course, Edgely uses your goals, assessment results, and learning history to decide what you should focus on next.
        </p>
</div>
<div className="feature-grid">
<article className="feature feature-large feature-dark">
<div className="feature-icon">✦</div>
<div>
<p className="feature-number">01</p>
<h3>AI Tutor + Coach</h3>
<p>Ask questions naturally, get explanations at your level, and receive coaching when your progress slows down.</p>
</div>
<div className="chat-demo">
<div className="chat-bubble user">Why do I keep missing VPC questions?</div>
<div className="chat-bubble ai"><span>✦</span> You understand the definitions, but route-table scenarios are still difficult. Let’s work through one visually.</div>
</div>
</article>
<article className="feature">
<div className="feature-icon soft">◎</div>
<p className="feature-number">02</p>
<h3>Knowledge assessment</h3>
<p>Start with a diagnostic so the platform knows what you already understand and what needs attention.</p>
<div className="meter"><span style={{ width: "68%" }}></span></div>
<div className="meter-label"><span>Current level</span><strong>68%</strong></div>
</article>
<article className="feature">
<div className="feature-icon soft">↗</div>
<p className="feature-number">03</p>
<h3>Adaptive study plan</h3>
<p>Your plan changes when you improve, miss sessions, or struggle with a topic — so your time stays focused.</p>
<div className="mini-plan">
<span className="checked">✓</span><span>IAM review</span><small>Done</small>
<span>2</span><span>VPC routing</span><small>Today</small>
<span>3</span><span>Resilience quiz</span><small>Tomorrow</small>
</div>
</article>
<article className="feature feature-wide">
<div>
<div className="feature-icon soft">◫</div>
<p className="feature-number">04</p>
<h3>Practice that finds patterns</h3>
<p>Adaptive quizzes and exam-style practice help the platform identify recurring weaknesses instead of treating every wrong answer the same.</p>
</div>
<div className="topic-chart" aria-label="Example strength chart">
<div><span>IAM</span><i><b style={{ width: "90%" }}></b></i><strong>90%</strong></div>
<div><span>S3</span><i><b style={{ width: "82%" }}></b></i><strong>82%</strong></div>
<div><span>VPC</span><i><b style={{ width: "48%" }}></b></i><strong>48%</strong></div>
<div><span>EC2</span><i><b style={{ width: "71%" }}></b></i><strong>71%</strong></div>
</div>
</article>
<article className="feature feature-accent">
<div className="feature-icon">⌁</div>
<p className="feature-number">05</p>
<h3>Readiness you can understand</h3>
<p>See how your knowledge is changing over time, which areas are improving, and where you should focus before exam day.</p>
<div className="big-stat"><strong>72%</strong><span>exam readiness</span></div>
</article>
</div>
</section>
<section className="section shell how" id="how">
<div className="section-heading centered">
<p className="eyebrow plain">ONE CONTINUOUS LEARNING LOOP</p>
<h2>Study with direction, not guesswork.</h2>
<p>Every action helps the platform understand you better and personalize what happens next.</p>
</div>
<div className="steps">
<article><span>01</span><h3>Choose your goal</h3><p>Select the certification you’re preparing for and tell us your exam date and experience.</p></article>
<article><span>02</span><h3>Measure your starting point</h3><p>Take a short diagnostic so the AI can identify current strengths and knowledge gaps.</p></article>
<article><span>03</span><h3>Follow your adaptive plan</h3><p>Learn with the AI tutor, complete practice activities, and focus on the areas that matter most.</p></article>
<article><span>04</span><h3>Improve continuously</h3><p>Your assessments update your readiness score and automatically reshape your study plan.</p></article>
</div>
</section>
<section className="section shell" id="about">
<div className="why-card">
<div>
<p className="eyebrow light">WHY AGENTIC LEARNING?</p>
<h2>Your learning platform should do more than answer questions.</h2>
</div>
<div className="why-copy">
<p>Traditional prep tools give you content. Generic AI gives you answers. Edgely connects tutoring, assessment, planning, and progress so the system can act on what it learns about you.</p>
<a className="btn btn-light" href="#get-started">Explore the experience →</a>
</div>
</div>
</section>
<section className="cta shell" id="get-started">
<div>
<p className="eyebrow plain">YOUR NEXT CERTIFICATION STARTS HERE</p>
<h2>Know what to study.<br />Know why it matters.</h2>
</div>
<div>
<p>Build a personalized learning path around your goals and turn every study session into measurable progress.</p>
<Link className="btn btn-dark" href="/register">Create your learning path</Link>
</div>
</section>
</main>
<footer className="footer shell">
<a className="brand" href="#top"><span className="brand-mark">E</span><span>Edgely</span></a>
<p>Agentic AI-powered certification learning.</p>
<div><a href="#features">Features</a><a href="#paths">Paths</a><a href="#about">About</a></div>
</footer>
    </>
  );
}
