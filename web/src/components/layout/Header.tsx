import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Activity, Wifi, WifiOff } from "lucide-react";

export function Header() {
  const [health, setHealth] = useState<"ok" | "error" | "loading">("loading");

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch("/health");
        setHealth(res.ok ? "ok" : "error");
      } catch {
        setHealth("error");
      }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-14 border-b border-rosetta-border bg-rosetta-surface/80 backdrop-blur-sm flex items-center justify-between px-6 sticky top-0 z-40">
      <div className="flex items-center gap-4">
        <motion.div
          className="flex items-center gap-2"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Activity className="w-4 h-4 text-rosetta-muted" />
          <span className="text-xs font-mono text-rosetta-muted">
            {new Date().toLocaleDateString("zh-CN", {
              year: "numeric",
              month: "2-digit",
              day: "2-digit",
            })}
          </span>
        </motion.div>
      </div>

      <motion.div
        className="flex items-center gap-2"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        {health === "ok" ? (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-rosetta-success/10 border border-rosetta-success/20">
            <Wifi className="w-3 h-3 text-rosetta-success" />
            <span className="text-xs font-mono text-rosetta-success">
              Connected
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-rosetta-success animate-pulse" />
          </div>
        ) : health === "error" ? (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-rosetta-error/10 border border-rosetta-error/20">
            <WifiOff className="w-3 h-3 text-rosetta-error" />
            <span className="text-xs font-mono text-rosetta-error">
              Disconnected
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-rosetta-muted/10 border border-rosetta-border">
            <span className="w-1.5 h-1.5 rounded-full bg-rosetta-muted animate-pulse" />
            <span className="text-xs font-mono text-rosetta-muted">
              Checking...
            </span>
          </div>
        )}
      </motion.div>
    </header>
  );
}
