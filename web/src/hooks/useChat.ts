import { useState, useRef, useCallback } from "react";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const abortRef = useRef<AbortController | null>(null);

  const streamChat = useCallback(
    async (userMessage: string, model?: string) => {
      const modelToUse = model || selectedModel;
      if (!modelToUse) {
        setError("No model selected. Please configure models on your active key in Dashboard.");
        return;
      }

      const userMsg: ChatMessage = { role: "user", content: userMessage };
      const assistantMsg: ChatMessage = { role: "assistant", content: "" };
      const newMessages = [...messages, userMsg, assistantMsg];
      setMessages(newMessages);
      setIsStreaming(true);
      setError(null);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch("/v1/responses", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: modelToUse,
            input: userMessage,
            stream: true,
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          let errorMsg = `HTTP ${res.status}`;
          if (res.status === 401 || res.status === 403) {
            errorMsg = "API Key invalid or not configured. Please check your key in Dashboard.";
          } else if (res.status === 404) {
            errorMsg = "Endpoint not found. Is the backend server running?";
          } else if (res.status >= 500) {
            errorMsg = "Upstream server error. Check your provider and key settings.";
          } else {
            try {
              const body = await res.json();
              errorMsg = body?.error?.message || body?.detail || errorMsg;
            } catch {}
          }
          throw new Error(errorMsg);
        }

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop()!;

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const data = line.slice(6).trim();
            if (data === "[DONE]") continue;

            try {
              const event = JSON.parse(data);
              if (event.type === "response.output_text.delta" && event.delta) {
                assistantMsg.content += event.delta;
                setMessages([...newMessages.slice(0, -1), { ...assistantMsg }]);
              } else if (event.type === "response.completed") {
                const output = event.response?.output || [];
                for (const item of output) {
                  if (item.type === "message" && item.content) {
                    for (const c of item.content) {
                      if (c.type === "output_text" && c.text) {
                        assistantMsg.content = c.text;
                        setMessages([...newMessages.slice(0, -1), { ...assistantMsg }]);
                      }
                    }
                  }
                }
              } else if (event.type === "response.error") {
                throw new Error(event.error?.message || "Stream error");
              }
            } catch (e: unknown) {
              if (e instanceof SyntaxError) continue;
              throw e;
            }
          }
        }
      } catch (e: unknown) {
        if (e instanceof Error && e.name === "AbortError") return;
        setError(e instanceof Error ? e.message : "Unknown error");
        setMessages(messages);
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [messages, selectedModel]
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const clear = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isStreaming,
    error,
    selectedModel,
    setSelectedModel,
    streamChat,
    stop,
    clear,
  };
}
