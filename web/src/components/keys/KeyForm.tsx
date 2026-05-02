import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Key, Globe, Eye, EyeOff, Pencil, Cpu, XCircle } from "lucide-react";
import type { KeyEntry } from "@/hooks/useKeys";

export interface KeyFormData {
  name: string;
  key: string;
  provider: string;
  base_url: string;
  models: string[];
  active: boolean;
}

interface KeyFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: KeyFormData) => Promise<void>;
  editKey?: KeyEntry | null;
}

const providers = [
  { value: "openai", label: "OpenAI", url: "https://api.openai.com/v1" },
  {
    value: "anthropic",
    label: "Anthropic",
    url: "https://api.anthropic.com/v1",
  },
  {
    value: "google",
    label: "Google",
    url: "https://generativelanguage.googleapis.com/v1",
  },
  { value: "other", label: "Other", url: "" },
];

export function KeyForm({ isOpen, onClose, onSubmit, editKey }: KeyFormProps) {
  const isEdit = !!editKey;

  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [provider, setProvider] = useState("openai");
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [models, setModels] = useState<string[]>([]);
  const [modelInput, setModelInput] = useState("");
  const [active, setActive] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (editKey) {
      setName(editKey.name);
      setKey("");
      setProvider(editKey.provider);
      setBaseUrl(editKey.base_url);
      setModels(editKey.models);
      setActive(editKey.active);
    } else {
      setName("");
      setKey("");
      setProvider("openai");
      setBaseUrl("https://api.openai.com/v1");
      setModels([]);
      setActive(false);
    }
    setError("");
    setShowKey(false);
  }, [editKey, isOpen]);

  const handleProviderChange = (p: string) => {
    setProvider(p);
    const found = providers.find((x) => x.value === p);
    if (found && found.url) setBaseUrl(found.url);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isEdit && !name.trim()) {
      setError("Name is required");
      return;
    }
    if (!isEdit && !key.trim()) {
      setError("Key is required");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await onSubmit({
        name: name.trim(),
        key: key.trim(),
        provider,
        base_url: baseUrl,
        models,
        active,
      });
      onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />

          <motion.div
            className="relative w-full max-w-lg mx-4 bg-rosetta-surface border border-rosetta-border rounded-2xl shadow-2xl overflow-hidden"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: "spring", bounce: 0.2, duration: 0.5 }}
          >
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-rosetta-gold to-transparent" />

            <div className="flex items-center justify-between p-6 border-b border-rosetta-border">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-rosetta-gold/10 flex items-center justify-center">
                  {isEdit ? (
                    <Pencil className="w-4 h-4 text-rosetta-gold" />
                  ) : (
                    <Key className="w-4 h-4 text-rosetta-gold" />
                  )}
                </div>
                <h2 className="text-lg font-semibold text-rosetta-text">
                  {isEdit ? "Edit API Key" : "Add API Key"}
                </h2>
              </div>
              <motion.button
                onClick={onClose}
                className="p-2 rounded-lg text-rosetta-muted hover:text-rosetta-text hover:bg-rosetta-card transition-colors"
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
              >
                <X className="w-5 h-5" />
              </motion.button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-3 rounded-lg bg-rosetta-error/10 border border-rosetta-error/20 text-sm text-rosetta-error"
                >
                  {error}
                </motion.div>
              )}

              <div>
                <label className="block text-xs font-mono text-rosetta-muted mb-2">
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="my-openai-key"
                  disabled={isEdit}
                  className="w-full px-4 py-2.5 rounded-lg rosetta-terminal-input text-sm text-rosetta-text placeholder:text-rosetta-muted/50 disabled:opacity-50 disabled:cursor-not-allowed"
                />
                {isEdit && (
                  <p className="text-[10px] text-rosetta-muted/60 mt-1 font-mono">
                    Name cannot be changed
                  </p>
                )}
              </div>

              <div>
                <label className="block text-xs font-mono text-rosetta-muted mb-2">
                  Provider
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {providers.map((p) => (
                    <motion.button
                      key={p.value}
                      type="button"
                      onClick={() => handleProviderChange(p.value)}
                      className={`px-3 py-2 rounded-lg text-xs font-mono border transition-colors ${
                        provider === p.value
                          ? "bg-rosetta-gold/10 border-rosetta-gold/30 text-rosetta-gold"
                          : "bg-rosetta-card border-rosetta-border text-rosetta-muted hover:text-rosetta-text"
                      }`}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      {p.label}
                    </motion.button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-rosetta-muted mb-2">
                  <Globe className="w-3 h-3 inline mr-1" />
                  Base URL
                </label>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://api.openai.com/v1"
                  className="w-full px-4 py-2.5 rounded-lg rosetta-terminal-input text-sm text-rosetta-text placeholder:text-rosetta-muted/50"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-rosetta-muted mb-2">
                  <Key className="w-3 h-3 inline mr-1" />
                  API Key
                </label>
                <div className="relative">
                  <input
                    type={showKey ? "text" : "password"}
                    value={key}
                    onChange={(e) => setKey(e.target.value)}
                    placeholder={
                      isEdit
                        ? "Leave empty to keep current key"
                        : "sk-..."
                    }
                    className="w-full px-4 py-2.5 pr-10 rounded-lg rosetta-terminal-input text-sm text-rosetta-text placeholder:text-rosetta-muted/50"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-rosetta-muted hover:text-rosetta-text"
                  >
                    {showKey ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-rosetta-muted mb-2">
                  <Cpu className="w-3 h-3 inline mr-1" />
                  Models
                </label>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {models.map((m) => (
                    <span
                      key={m}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-rosetta-gold/10 border border-rosetta-gold/20 text-xs font-mono text-rosetta-gold"
                    >
                      {m}
                      <button
                        type="button"
                        onClick={() => setModels(models.filter((x) => x !== m))}
                        className="text-rosetta-gold/60 hover:text-rosetta-error transition-colors"
                      >
                        <XCircle className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={modelInput}
                    onChange={(e) => setModelInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        const val = modelInput.trim();
                        if (val && !models.includes(val)) {
                          setModels([...models, val]);
                        }
                        setModelInput("");
                      }
                    }}
                    placeholder="Type model name and press Enter"
                    className="flex-1 px-4 py-2.5 rounded-lg rosetta-terminal-input text-sm text-rosetta-text placeholder:text-rosetta-muted/50"
                  />
                  <motion.button
                    type="button"
                    onClick={() => {
                      const val = modelInput.trim();
                      if (val && !models.includes(val)) {
                        setModels([...models, val]);
                      }
                      setModelInput("");
                    }}
                    className="px-3 py-2.5 rounded-lg bg-rosetta-card border border-rosetta-border text-rosetta-muted text-sm hover:text-rosetta-gold hover:border-rosetta-gold/30 transition-colors"
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    Add
                  </motion.button>
                </div>
                <p className="text-[10px] text-rosetta-muted/60 mt-1 font-mono">
                  Enter model IDs like gpt-4o, claude-3-opus, deepseek-chat
                </p>
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="active"
                  checked={active}
                  onChange={(e) => setActive(e.target.checked)}
                  className="w-4 h-4 rounded border-rosetta-border bg-rosetta-dark accent-rosetta-gold"
                />
                <label
                  htmlFor="active"
                  className="text-sm text-rosetta-muted cursor-pointer"
                >
                  Set as active key immediately
                </label>
              </div>

              <div className="flex gap-3 pt-2">
                <motion.button
                  type="button"
                  onClick={onClose}
                  className="flex-1 px-4 py-2.5 rounded-lg border border-rosetta-border text-rosetta-muted text-sm hover:bg-rosetta-card transition-colors"
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                >
                  Cancel
                </motion.button>
                <motion.button
                  type="submit"
                  disabled={loading}
                  className="flex-1 px-4 py-2.5 rounded-lg bg-rosetta-gold text-rosetta-black font-medium text-sm hover:bg-rosetta-gold-light transition-colors disabled:opacity-50"
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                >
                  {loading
                    ? isEdit
                      ? "Saving..."
                      : "Adding..."
                    : isEdit
                    ? "Save Changes"
                    : "Add Key"}
                </motion.button>
              </div>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
