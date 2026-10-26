"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Overview", kbd: "1", icon: "◈" },
  { href: "/swarm", label: "Swarm Control", kbd: "7", icon: "⬡" },
  { href: "/verify", label: "Trust Verify", kbd: "8", icon: "✓" },
  { href: "/sessions", label: "Sessions", kbd: "2", icon: "◷" },
  { href: "/metakeys", label: "MetaKeys", kbd: "3", icon: "⚿" },
  { href: "/routing", label: "Model routing", kbd: "4", icon: "⇉" },
  { href: "/audit", label: "Audit log", kbd: "5", icon: "☰" },
  { href: "/settings", label: "Settings", kbd: "6", icon: "⚙" },
];

export default function Sidebar() {
  const path = usePathname() || "/";
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark" aria-hidden>◎</div>
        <div>
          <div className="brand-name">MuseBreak</div>
          <div className="brand-tag">Two gates. One trusted session.</div>
        </div>
      </div>
      <nav className="nav">
        {NAV.map((n) => {
          const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
          return (
            <Link key={n.href} href={n.href} className={active ? "active" : ""}>
              <span className="ico">{n.icon}</span>
              {n.label}
              <span className="kbd">⌘ {n.kbd}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
