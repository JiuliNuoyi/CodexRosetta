import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare,
  Sparkles,
  Trash2,
  AlertTriangle,
  ChevronDown,
  Key,
  Cpu,
} from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import type { ChatMessage } from "@/hooks/useChat";

export interface KeyOption {
  name: string;
  provider: string;
  models: string[];
  active: boolean;
}

interface ChatWindowProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  onSend: (message: string) => void;
  onStop: () => void;
  onClear: () => void;
  keys: KeyOption[];
  activeKeyName: string | null;
  onActivateKey: (name: string) => void;
  availableModels: string[];
  selectedModel: string;
  onModelChange: (model: string) => void;
}

export function ChatWindow({
  messages,
  isStreaming,
  error,
  onSend,
  onStop,
  onClear,
  keys,
  activeKeyName,
  onActivateKey,
  availableModels,
  selectedModel,
  onModelChange,
}: ChatWindowProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const activeKey = keys.find((k) => k.name === activeKeyName) || null;
  const noKey = !activeKey;
  const noModels = activeKey && availableModels.length === 0;

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Chat header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-rosetta-border bg-rosetta-surface/50">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-rosetta-gold" />
          <span className="text-sm font-mono text-rosetta-muted">
            Chat Playground
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-rosetta-gold/10 text-rosetta-gold font-mono">
            Streaming
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Key selector */}
          {keys.length > 0 && (
            <div className="relative">
              <select
                value={activeKeyName || ""}
                onChange={(e) => onActivateKey(e.target.value)}
                disabled={isStreaming}
                className="appearance-none pl-7 pr-7 py-1.5 rounded-lg bg-rosetta-card border border-rosetta-border text-xs text-rosetta-text font-mono focus:outline-none focus:border-rosetta-gold/30 disabled:opacity-50 cursor-pointer"
              >
                {keys.map((k) => (
                  <option key={k.name} value={k.name}>
                    {k.name} ({k.provider})
                  </option>
                ))}
              </select>
              <Key className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-rosetta-gold pointer-events-none" />
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-rosetta-muted pointer-events-none" />
            </div>
          )}

          {/* Model selector */}
          {availableModels.length > 0 && (
            <div className="relative">
              <select
                value={selectedModel}
                onChange={(e) => onModelChange(e.target.value)}
                disabled={isStreaming}
                className="appearance-none pl-7 pr-7 py-1.5 rounded-lg bg-rosetta-card border border-rosetta-border text-xs text-rosetta-text font-mono focus:outline-none focus:border-rosetta-gold/30 disabled:opacity-50 cursor-pointer"
              >
                {availableModels.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              <Cpu className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-rosetta-gold pointer-events-none" />
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-rosetta-muted pointer-events-none" />
            </div>
          )}

          {messages.length > 0 && (
            <motion.button
              onClick={onClear}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-rosetta-muted hover:text-rosetta-error hover:bg-rosetta-error/10 transition-colors"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              <Trash2 className="w-3 h-3" />
              Clear
            </motion.button>
          )}
        </div>
      </div>

      {/* Status warning bar */}
      {(noKey || noModels) && (
        <div className="px-6 py-3 border-b border-rosetta-border bg-rosetta-card">
          <div className="max-w-4xl mx-auto flex items-center gap-3">
            <AlertTriangle className="w-4 h-4 text-rosetta-warning flex-shrink-0" />
            {noKey ? (
              <p className="text-xs text-rosetta-warning">
                No API key configured. Go to{" "}
                <a
                  href="/app"
                  className="underline text-rosetta-gold hover:text-rosetta-gold/80"
                >
                  Dashboard
                </a>{" "}
                to add a key before sending messages.
              </p>
            ) : (
              <p className="text-xs text-rosetta-warning">
                Active key has no models configured. Go to{" "}
                <a
                  href="/app"
                  className="underline text-rosetta-gold hover:text-rosetta-gold/80"
                >
                  Dashboard
                </a>{" "}
                to edit the key and add model IDs.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-6 rosetta-noise"
      >
        <div className="max-w-4xl mx-auto space-y-4 relative z-10">
          <AnimatePresence mode="popLayout">
            {messages.length === 0 ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center h-full py-24"
              >
                <motion.div
                  className="w-16 h-16 rounded-2xl bg-gradient-to-br from-rosetta-gold/20 to-rosetta-gold/5 border border-rosetta-gold/10 flex items-center justify-center mb-6"
                  animate={{ y: [0, -5, 0] }}
                  transition={{ duration: 3, repeat: Infinity }}
                >
                  <MessageSquare className="w-7 h-7 text-rosetta-gold" />
                </motion.div>
                <h3 className="text-lg font-semibold text-rosetta-text mb-2">
                  CodexRosetta Playground
                </h3>
                <p className="text-sm text-rosetta-muted text-center max-w-sm">
                  Send a message to test the proxy. Messages are forwarded
                  through the Responses API &rarr; Chat Completions pipeline.
                </p>
                <div className="mt-8 grid grid-cols-2 gap-3 max-w-sm">
                  {[
                    "Explain quantum computing",
                    "Write a Python fibonacci",
                    "What is Rust's borrow checker?",
                    "Compare SQL vs NoSQL",
                  ].map((suggestion, i) => (
                    <motion.button
                      key={suggestion}
                      onClick={() => onSend(suggestion)}
                      disabled={noKey || noModels || !selectedModel}
                      className="px-3 py-2 rounded-lg bg-rosetta-card border border-rosetta-border text-xs text-rosetta-muted hover:text-rosetta-text hover:border-rosetta-gold/20 transition-colors text-left disabled:opacity-30 disabled:cursor-not-allowed"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1 + i * 0.05 }}
                      whileHover={
                        noKey || noModels ? undefined : { scale: 1.02, y: -2 }
                      }
                    >
                      {suggestion}
                    </motion.button>
                  ))}
                </div>
              </motion.div>
            ) : (
              messages.map((msg, i) => (
                <MessageBubble
                  key={i}
                  message={msg}
                  isLast={i === messages.length - 1 && isStreaming}
                />
              ))
            )}
          </AnimatePresence>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mx-auto max-w-md p-3 rounded-lg bg-rosetta-error/10 border border-rosetta-error/20 text-sm text-rosetta-error text-center"
            >
              {error}
            </motion.div>
          )}
        </div>
      </div>

      {/* Input */}
      <ChatInput
        onSend={onSend}
        onStop={onStop}
        isStreaming={isStreaming}
        disabled={noKey || noModels || !selectedModel}
      />
    </div>
  );
}
