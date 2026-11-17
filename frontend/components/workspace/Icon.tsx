// Inline SVG icons shared by the learner workspace pages.

import type { ReactNode } from "react";

export type IconName = "grid" | "book" | "calendar" | "check" | "chart" | "sparkle" | "settings" | "bell" | "chevron" | "arrow" | "menu" | "close" | "clock" | "target" | "bolt" | "trophy" | "bookmark" | "search" | "user" | "logout" | "edit" | "play" | "shield" | "plus" | "pause";

export function Icon({ name, size = 20, strokeWidth = 1.8 }: { name: IconName; size?: number; strokeWidth?: number }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const paths: Record<IconName, ReactNode> = {
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
    plus: <path d="M12 5v14M5 12h14"/>,
    pause: <path d="M9 5v14M15 5v14"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" {...common}>{paths[name]}</svg>;
}
