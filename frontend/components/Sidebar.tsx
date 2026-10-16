"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";

const LINKS = [
  { href: "/projects", label: "Projects" },
  { href: "/sources", label: "Sources" },
  { href: "/messages", label: "Messages" },
  { href: "/requirements", label: "Requirements" },
  { href: "/test-cases", label: "Test Cases" },
  { href: "/tasks", label: "Tasks" },
  { href: "/repository", label: "Repository" },
  { href: "/traceability", label: "Traceability" },
  { href: "/analysis", label: "Analysis" },
  { href: "/reports", label: "Reports" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-white/10 bg-zinc-900/60">
      <Link href="/projects" className="flex items-center gap-2.5 px-5 py-5">
        <ShieldIcon />
        <span className="text-lg font-semibold tracking-tight">ReqGuard</span>
      </Link>

      <nav className="flex-1 space-y-0.5 px-3">
        {LINKS.map((link) => {
          const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`block rounded-lg px-3 py-2 text-sm transition ${
                active
                  ? "bg-indigo-500/15 font-medium text-indigo-200"
                  : "text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>

      <BackendStatus />
    </aside>
  );
}

// Shows whether the backend /health endpoint answers (checks lib/api.ts works).
function BackendStatus() {
  const [state, setState] = useState<"checking" | "online" | "offline">("checking");

  useEffect(() => {
    getHealth()
      .then(() => setState("online"))
      .catch(() => setState("offline"));
  }, []);

  const color = { checking: "bg-zinc-500", online: "bg-emerald-400", offline: "bg-rose-400" }[state];

  return (
    <div className="flex items-center gap-2 border-t border-white/10 px-5 py-4 text-xs text-zinc-500">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      Backend {state}
    </div>
  );
}

function ShieldIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Z" fill="#F59E0B" />
      <path d="m8.5 12 2.5 2.5 4.5-5" stroke="#18181B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
