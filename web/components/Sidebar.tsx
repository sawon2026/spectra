"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/cases", label: "Cases" },
  { href: "/investigations", label: "Investigations" },
  { href: "/evidence", label: "Evidence" },
  { href: "/findings", label: "Findings" },
  { href: "/graph", label: "Knowledge Graph" },
  { href: "/timeline", label: "Timeline" },
  { href: "/capabilities", label: "Capabilities" },
  { href: "/reports", label: "Reports" },
  { href: "/providers", label: "AI Providers" },
  { href: "/settings", label: "Settings" },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-surface-border bg-surface-raised flex flex-col">
      <div className="px-4 py-5 border-b border-surface-border">
        <div className="text-lg font-semibold tracking-tight">Spectra</div>
        <div className="text-xs text-slate-400 mt-0.5">Security research</div>
      </div>
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {NAV.map((item) => {
          const active = path === item.href || (item.href !== "/" && path.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded px-3 py-2 text-sm no-underline ${
                active
                  ? "bg-accent-muted text-white"
                  : "text-slate-300 hover:bg-surface hover:text-white"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="px-4 py-3 text-[10px] text-slate-500 border-t border-surface-border">
        PolicyEngine gate active · Offline by default
      </div>
    </aside>
  );
}
