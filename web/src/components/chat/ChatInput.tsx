import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { Send, Square } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}

export function ChatInput({
  onSend,
  onStop,
  isStreaming,
  disabled,
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 160) + "px";
    }
  }, [input]);

  const handleSubmit = () => {
    if (isStreaming) {
      onStop();
      return;
    }
    if (!input.trim() || disabled) return;
    onSend(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t border-rosetta-border bg-rosetta-surface/80 backdrop-blur-sm p-4">
      <div className="max-w-4xl mx-auto">
        <div className="relative flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message..."
              disabled={disabled || isStreaming}
              rows={1}
              className="w-full px-4 py-3 pr-12 rounded-xl bg-rosetta-card border border-rosetta-border text-sm text-rosetta-text placeholder:text-rosetta-muted/50 resize-none focus:outline-none focus:border-rosetta-gold/30 focus:ring-1 focus:ring-rosetta-gold/20 transition-all font-sans"
            />
          </div>

          <motion.button
            onClick={handleSubmit}
            disabled={!isStreaming && (!input.trim() || disabled)}
            className="p-3 rounded-xl bg-rosetta-gold text-rosetta-black disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            {isStreaming ? (
              <Square className="w-4 h-4" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </motion.button>
        </div>

        <p className="text-[10px] text-rosetta-muted/50 mt-2 text-center">
          Press Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
