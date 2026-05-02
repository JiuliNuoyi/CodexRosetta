import { motion } from "framer-motion";
import { Key, MessageSquare, Settings as SettingsIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface SidebarProps {
  activePage: "keys" | "chat" | "settings";
  onNavigate: (page: "keys" | "chat" | "settings") => void;
}

const navItems = [
  { id: "keys" as const, label: "API Keys", icon: Key },
  { id: "chat" as const, label: "Playground", icon: MessageSquare },
  { id: "settings" as const, label: "Settings", icon: SettingsIcon },
];

function StormIcon() {
  return (
    <div className="relative w-9 h-9 flex items-center justify-center">
      <svg
        viewBox="0 0 40 40"
        className="w-9 h-9"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="sg1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#e8c878" stopOpacity="1" />
            <stop offset="100%" stopColor="#d4a853" stopOpacity="0.7" />
          </linearGradient>
          <linearGradient id="sg2" x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#d4a853" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#8b7340" stopOpacity="0.5" />
          </linearGradient>
          <linearGradient id="sg3" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#d4a853" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#8b7340" stopOpacity="0.5" />
          </linearGradient>
        </defs>

        {/* Top-left → center */}
        <path
          d="M 4 4 C 10 6, 14 12, 20 20"
          stroke="url(#sg1)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />

        {/* Top-right → center */}
        <path
          d="M 36 4 C 30 6, 26 12, 20 20"
          stroke="url(#sg2)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />

        {/* Bottom-left → center */}
        <path
          d="M 4 36 C 10 34, 14 28, 20 20"
          stroke="url(#sg3)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />

        {/* Bottom-right → center */}
        <path
          d="M 36 36 C 30 34, 26 28, 20 20"
          stroke="url(#sg2)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />

        {/* Center */}
        <circle cx="20" cy="20" r="2" fill="#d4a853" />
      </svg>

      <div className="absolute inset-0 rounded-full bg-rosetta-gold/8 blur-sm -z-10" />
    </div>
  );
}

export function Sidebar({ activePage, onNavigate }: SidebarProps) {
  return (
    <aside className="fixed left-0 top-0 bottom-0 w-64 bg-rosetta-surface border-r border-rosetta-border flex flex-col z-50">
      {/* Logo */}
      <div className="p-6 border-b border-rosetta-border">
        <div className="flex items-center gap-3">
          <StormIcon />
          <div className="flex flex-col">
            <span className="font-mono text-[10px] text-rosetta-muted tracking-[0.25em] uppercase leading-none">
              Codex
            </span>
            <span className="font-mono font-bold text-rosetta-gold text-base tracking-[0.15em] uppercase leading-tight rosetta-glow-text">
              Rosetta
            </span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => {
          const isActive = activePage === item.id;
          return (
            <motion.button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={cn(
                "w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors relative overflow-hidden",
                isActive
                  ? "text-rosetta-gold"
                  : "text-rosetta-muted hover:text-rosetta-text hover:bg-rosetta-card"
              )}
              whileHover={{ x: 2 }}
              whileTap={{ scale: 0.98 }}
            >
              {isActive && (
                <motion.div
                  layoutId="sidebar-active"
                  className="absolute inset-0 bg-rosetta-card border border-rosetta-gold/20 rounded-lg"
                  transition={{ type: "spring", bounce: 0.15, duration: 0.5 }}
                />
              )}
              <item.icon className="w-4 h-4 relative z-10" />
              <span className="relative z-10">{item.label}</span>
              {isActive && (
                <motion.div
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-rosetta-gold rounded-r-full"
                  layoutId="sidebar-indicator"
                />
              )}
            </motion.button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-rosetta-border">
        <p className="text-[10px] text-rosetta-muted font-mono text-center">
          v0.1.0 · Proxy Server
        </p>
      </div>
    </aside>
  );
}
