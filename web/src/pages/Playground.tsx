import { useEffect } from "react";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { useChat } from "@/hooks/useChat";
import { useKeys } from "@/hooks/useKeys";

export function Playground() {
  const {
    messages,
    isStreaming,
    error,
    selectedModel,
    setSelectedModel,
    streamChat,
    stop,
    clear,
  } = useChat();

  const { keys, activateKey } = useKeys();

  const activeKey = keys.find((k) => k.active) || null;
  const availableModels = activeKey?.models || [];

  useEffect(() => {
    if (
      availableModels.length > 0 &&
      !availableModels.includes(selectedModel)
    ) {
      setSelectedModel(availableModels[0]);
    }
  }, [availableModels, selectedModel, setSelectedModel]);

  return (
    <ChatWindow
      messages={messages}
      isStreaming={isStreaming}
      error={error}
      onSend={streamChat}
      onStop={stop}
      onClear={clear}
      keys={keys.map((k) => ({
        name: k.name,
        provider: k.provider,
        models: k.models,
        active: k.active,
      }))}
      activeKeyName={activeKey?.name || null}
      onActivateKey={activateKey}
      availableModels={availableModels}
      selectedModel={selectedModel}
      onModelChange={setSelectedModel}
    />
  );
}
