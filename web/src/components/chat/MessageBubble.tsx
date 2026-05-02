import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/hooks/useChat";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MessageBubbleProps {
  message: ChatMessage;
  isLast: boolean;
}

export function MessageBubble({ message, isLast }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      className={cn("flex gap-3 max-w-[85%]", isUser ? "ml-auto flex-row-reverse" : "")}
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: "spring", bounce: 0.15, duration: 0.4 }}
    >
      {!isUser && (
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-rosetta-gold to-rosetta-gold-dim flex items-center justify-center flex-shrink-0 mt-1">
          <span className="text-[10px] font-mono font-bold text-rosetta-black">
            R
          </span>
        </div>
      )}

      <div
        className={cn(
          "rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-rosetta-gold/15 text-rosetta-text border border-rosetta-gold/20 rounded-tr-md"
            : "bg-rosetta-card text-rosetta-text border border-rosetta-border rounded-tl-md"
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none prose-p:my-1 prose-pre:bg-rosetta-dark prose-pre:border prose-pre:border-rosetta-border prose-code:text-rosetta-gold prose-a:text-rosetta-gold prose-headings:text-rosetta-text">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content || (isLast ? "..." : "")}
            </ReactMarkdown>
            {isLast && message.content && (
              <motion.span
                className="inline-block w-2 h-4 bg-rosetta-gold ml-0.5"
                animate={{ opacity: [1, 0] }}
                transition={{ duration: 0.8, repeat: Infinity }}
              />
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-7 h-7 rounded-lg bg-rosetta-border flex items-center justify-center flex-shrink-0 mt-1">
          <span className="text-[10px] font-mono font-bold text-rosetta-muted">
            U
          </span>
        </div>
      )}
    </motion.div>
  );
}
