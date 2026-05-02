import { motion, AnimatePresence } from "framer-motion";
import {
  Key,
  Plus,
  Trash2,
  CheckCircle2,
  Circle,
  Copy,
  Server,
  Loader2,
  Pencil,
  Cpu,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { KeyEntry } from "@/hooks/useKeys";

interface KeyListProps {
  keys: KeyEntry[];
  loading: boolean;
  onActivate: (name: string) => void;
  onDelete: (name: string) => void;
  onAdd: () => void;
  onEdit: (key: KeyEntry) => void;
}

export function KeyList({
  keys,
  loading,
  onActivate,
  onDelete,
  onAdd,
  onEdit,
}: KeyListProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-rosetta-gold animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-rosetta-text flex items-center gap-2">
            <Key className="w-5 h-5 text-rosetta-gold" />
            API Keys
          </h2>
          <p className="text-sm text-rosetta-muted mt-1">
            Manage your upstream API keys
          </p>
        </div>
        <motion.button
          onClick={onAdd}
          className="flex items-center gap-2 px-4 py-2 bg-rosetta-gold text-rosetta-black rounded-lg font-medium text-sm hover:bg-rosetta-gold-light transition-colors"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <Plus className="w-4 h-4" />
          Add Key
        </motion.button>
      </div>

      <AnimatePresence mode="popLayout">
        {keys.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-12 text-rosetta-muted"
          >
            <Key className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No keys configured</p>
          </motion.div>
        ) : (
          <div className="space-y-3">
            {keys.map((key, index) => (
              <motion.div
                key={key.name}
                layout
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: -10 }}
                transition={{
                  type: "spring",
                  bounce: 0.15,
                  delay: index * 0.05,
                }}
                className={cn(
                  "relative rounded-xl border p-4 transition-colors group",
                  key.active
                    ? "bg-rosetta-card border-rosetta-gold/30 rosetta-glow"
                    : "bg-rosetta-surface border-rosetta-border hover:border-rosetta-border/80"
                )}
              >
                {key.active && (
                  <motion.div
                    className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-rosetta-gold to-transparent rounded-t-xl"
                    layoutId="key-active-bar"
                  />
                )}

                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-mono font-semibold text-sm text-rosetta-text truncate">
                        {key.name}
                      </h3>
                      {key.active ? (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-rosetta-gold/15 text-rosetta-gold text-[10px] font-mono">
                          <CheckCircle2 className="w-3 h-3" />
                          ACTIVE
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-rosetta-muted/10 text-rosetta-muted text-[10px] font-mono">
                          <Circle className="w-3 h-3" />
                          INACTIVE
                        </span>
                      )}
                    </div>

                    <div className="space-y-1.5 text-xs">
                      <div className="flex items-center gap-2 text-rosetta-muted">
                        <span className="w-16 text-rosetta-muted/60">
                          Provider
                        </span>
                        <span className="font-mono text-rosetta-text">
                          {key.provider}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-rosetta-muted">
                        <span className="w-16 text-rosetta-muted/60">
                          Endpoint
                        </span>
                        <span className="font-mono text-rosetta-text truncate">
                          {key.base_url}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-rosetta-muted">
                        <span className="w-16 text-rosetta-muted/60">Key</span>
                        <span className="font-mono text-rosetta-text flex items-center gap-1">
                          {key.key_masked}
                          <button
                            onClick={() =>
                              navigator.clipboard.writeText(key.key_masked)
                            }
                            className="opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <Copy className="w-3 h-3" />
                          </button>
                        </span>
                      </div>
                      {key.models.length > 0 && (
                        <div className="flex items-center gap-2 text-rosetta-muted">
                          <span className="w-16 text-rosetta-muted/60 flex items-center gap-1">
                            <Cpu className="w-3 h-3" />
                            Models
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {key.models.map((m) => (
                              <span
                                key={m}
                                className="px-1.5 py-0.5 rounded bg-rosetta-gold/10 text-rosetta-gold text-[10px] font-mono"
                              >
                                {m}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1 ml-4">
                    <motion.button
                      onClick={() => onEdit(key)}
                      className="p-2 rounded-lg text-rosetta-muted hover:text-rosetta-gold hover:bg-rosetta-gold/10 transition-colors"
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.9 }}
                      title="Edit"
                    >
                      <Pencil className="w-4 h-4" />
                    </motion.button>
                    {!key.active && (
                      <motion.button
                        onClick={() => onActivate(key.name)}
                        className="p-2 rounded-lg text-rosetta-muted hover:text-rosetta-gold hover:bg-rosetta-gold/10 transition-colors"
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        title="Activate"
                      >
                        <Server className="w-4 h-4" />
                      </motion.button>
                    )}
                    <motion.button
                      onClick={() => onDelete(key.name)}
                      className="p-2 rounded-lg text-rosetta-muted hover:text-rosetta-error hover:bg-rosetta-error/10 transition-colors"
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.9 }}
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </motion.button>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
