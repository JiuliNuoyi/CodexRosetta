import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Settings as SettingsIcon,
  FileText,
  Activity,
  Save,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Terminal,
  ChevronDown,
  Globe,
  Eye,
  EyeOff,
  Key,
  Hash,
  RotateCw,
} from "lucide-react";
import { useSettings } from "@/hooks/useSettings";
import type { SettingsData } from "@/hooks/useSettings";

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];

const SEARCH_PROVIDERS = [
  { value: "duckduckgo", label: "DuckDuckGo", needsKey: true, needsUrl: true, keyOptional: true, urlOptional: true },
  { value: "tavily", label: "Tavily", needsKey: true, needsUrl: false, keyOptional: false, urlOptional: false },
  { value: "brave", label: "Brave", needsKey: true, needsUrl: false, keyOptional: false, urlOptional: false },
  { value: "searxng", label: "SearXNG", needsKey: true, needsUrl: true, keyOptional: true, urlOptional: false },
  { value: "custom", label: "Custom", needsKey: true, needsUrl: true, keyOptional: true, urlOptional: false },
];

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      disabled={disabled}
      className={`
        relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200
        ${checked ? "bg-rosetta-gold" : "bg-rosetta-border"}
        ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
      `}
    >
      <motion.span
        className="inline-block h-4 w-4 rounded-full bg-white shadow-sm"
        animate={{ x: checked ? 22 : 4 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
      />
    </button>
  );
}

export function Settings() {
  const { settings, loading, saving, error, updateSettings } = useSettings();

  const [form, setForm] = useState<SettingsData>({
    LOG_LEVEL: "INFO",
    LOG_UPSTREAM_REQUESTS: false,
    LOG_UPSTREAM_RESPONSES: false,
    DEBUG_LOG_FILE: null,
    WEB_SEARCH_ENABLED: false,
    WEB_SEARCH_PROVIDER: "duckduckgo",
    WEB_SEARCH_BASE_URL: "",
    WEB_SEARCH_API_KEY: "",
    WEB_SEARCH_MAX_RESULTS: 5,
    WEB_SEARCH_MAX_ROUNDS: 3,
  });

  const [saved, setSaved] = useState(false);
  const [logFileInput, setLogFileInput] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);

  useEffect(() => {
    if (settings) {
      setForm(settings);
      setLogFileInput(settings.DEBUG_LOG_FILE || "");
    }
  }, [settings]);

  const debugChanged =
    settings !== null &&
    (form.LOG_LEVEL !== settings.LOG_LEVEL ||
      form.LOG_UPSTREAM_REQUESTS !== settings.LOG_UPSTREAM_REQUESTS ||
      form.LOG_UPSTREAM_RESPONSES !== settings.LOG_UPSTREAM_RESPONSES ||
      (form.DEBUG_LOG_FILE || null) !== settings.DEBUG_LOG_FILE);

  const searchChanged =
    settings !== null &&
    (form.WEB_SEARCH_ENABLED !== settings.WEB_SEARCH_ENABLED ||
      form.WEB_SEARCH_PROVIDER !== settings.WEB_SEARCH_PROVIDER ||
      form.WEB_SEARCH_BASE_URL !== settings.WEB_SEARCH_BASE_URL ||
      (form.WEB_SEARCH_API_KEY !== "***" &&
        form.WEB_SEARCH_API_KEY !== settings.WEB_SEARCH_API_KEY) ||
      form.WEB_SEARCH_MAX_RESULTS !== settings.WEB_SEARCH_MAX_RESULTS ||
      form.WEB_SEARCH_MAX_ROUNDS !== settings.WEB_SEARCH_MAX_ROUNDS);

  const hasChanges = debugChanged || searchChanged;

  const handleSave = async () => {
    const updates: Partial<SettingsData> = {};
    if (debugChanged) {
      updates.LOG_LEVEL = form.LOG_LEVEL;
      updates.LOG_UPSTREAM_REQUESTS = form.LOG_UPSTREAM_REQUESTS;
      updates.LOG_UPSTREAM_RESPONSES = form.LOG_UPSTREAM_RESPONSES;
      updates.DEBUG_LOG_FILE = logFileInput.trim() || null;
    }
    if (searchChanged) {
      updates.WEB_SEARCH_ENABLED = form.WEB_SEARCH_ENABLED;
      updates.WEB_SEARCH_PROVIDER = form.WEB_SEARCH_PROVIDER;
      updates.WEB_SEARCH_BASE_URL = form.WEB_SEARCH_BASE_URL;
      if (form.WEB_SEARCH_API_KEY !== "***") {
        updates.WEB_SEARCH_API_KEY = form.WEB_SEARCH_API_KEY;
      }
      updates.WEB_SEARCH_MAX_RESULTS = form.WEB_SEARCH_MAX_RESULTS;
      updates.WEB_SEARCH_MAX_ROUNDS = form.WEB_SEARCH_MAX_ROUNDS;
    }
    await updateSettings(updates);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const handleReset = () => {
    if (settings) {
      setForm(settings);
      setLogFileInput(settings.DEBUG_LOG_FILE || "");
    }
  };

  const providerInfo = SEARCH_PROVIDERS.find(
    (p) => p.value === form.WEB_SEARCH_PROVIDER
  );

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-48 bg-rosetta-card rounded-lg" />
          <div className="h-64 bg-rosetta-card rounded-xl" />
        </div>
      </div>
    );
  }

  return (
    <motion.div
      className="p-6 space-y-6"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-rosetta-gold/20 to-rosetta-gold/5 border border-rosetta-gold/10 flex items-center justify-center">
            <SettingsIcon className="w-5 h-5 text-rosetta-gold" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-rosetta-text">
              Runtime Settings
            </h1>
            <p className="text-xs text-rosetta-muted font-mono">
              Changes take effect immediately without restart
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {hasChanges && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex items-center gap-2"
            >
              <motion.button
                onClick={handleReset}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-rosetta-border text-xs text-rosetta-muted hover:text-rosetta-text hover:bg-rosetta-card transition-colors"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <RotateCcw className="w-3 h-3" />
                Reset
              </motion.button>
              <motion.button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-rosetta-gold text-rosetta-black text-xs font-medium hover:bg-rosetta-gold-light transition-colors disabled:opacity-50"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <Save className="w-3 h-3" />
                {saving ? "Saving..." : "Save Changes"}
              </motion.button>
            </motion.div>
          )}

          {saved && !hasChanges && (
            <motion.div
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-1.5 text-xs text-rosetta-success"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Saved
            </motion.div>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-3 rounded-lg bg-rosetta-error/10 border border-rosetta-error/20 flex items-center gap-2"
        >
          <AlertCircle className="w-4 h-4 text-rosetta-error flex-shrink-0" />
          <span className="text-sm text-rosetta-error">{error}</span>
        </motion.div>
      )}

      {/* Debug Logging Section */}
      <motion.div
        className="rounded-xl bg-rosetta-surface border border-rosetta-border overflow-hidden"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="px-6 py-4 border-b border-rosetta-border flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-rosetta-gold/10 flex items-center justify-center">
            <Terminal className="w-3.5 h-3.5 text-rosetta-gold" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-rosetta-text">
              Debug Logging
            </h2>
            <p className="text-[11px] text-rosetta-muted font-mono">
              Control log verbosity and output targets
            </p>
          </div>
        </div>

        <div className="divide-y divide-rosetta-border">
          {/* Log Level */}
          <div className="px-6 py-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <Activity className="w-4 h-4 text-rosetta-muted flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-rosetta-text">Log Level</p>
                <p className="text-[11px] text-rosetta-muted font-mono truncate">
                  Minimum severity of log messages to output
                </p>
              </div>
            </div>
            <div className="relative flex-shrink-0">
              <select
                value={form.LOG_LEVEL}
                onChange={(e) =>
                  setForm({ ...form, LOG_LEVEL: e.target.value })
                }
                className="appearance-none pl-3 pr-8 py-1.5 rounded-lg bg-rosetta-card border border-rosetta-border text-xs text-rosetta-text font-mono focus:outline-none focus:border-rosetta-gold/30 cursor-pointer"
              >
                {LOG_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-rosetta-muted pointer-events-none" />
            </div>
          </div>

          {/* Upstream Requests */}
          <div className="px-6 py-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <FileText className="w-4 h-4 text-rosetta-muted flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-rosetta-text">
                  Log Upstream Requests
                </p>
                <p className="text-[11px] text-rosetta-muted font-mono truncate">
                  Log full request body sent to upstream provider
                </p>
              </div>
            </div>
            <Toggle
              checked={form.LOG_UPSTREAM_REQUESTS}
              onChange={(v) =>
                setForm({ ...form, LOG_UPSTREAM_REQUESTS: v })
              }
            />
          </div>

          {/* Upstream Responses */}
          <div className="px-6 py-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <FileText className="w-4 h-4 text-rosetta-muted flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-rosetta-text">
                  Log Upstream Responses
                </p>
                <p className="text-[11px] text-rosetta-muted font-mono truncate">
                  Log full response body received from upstream provider
                </p>
              </div>
            </div>
            <Toggle
              checked={form.LOG_UPSTREAM_RESPONSES}
              onChange={(v) =>
                setForm({ ...form, LOG_UPSTREAM_RESPONSES: v })
              }
            />
          </div>

          {/* Debug Log File */}
          <div className="px-6 py-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <FileText className="w-4 h-4 text-rosetta-muted flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-rosetta-text">Debug Log File</p>
                <p className="text-[11px] text-rosetta-muted font-mono truncate">
                  Path to write debug logs (empty = stdout only)
                </p>
              </div>
            </div>
            <input
              type="text"
              value={logFileInput}
              onChange={(e) => setLogFileInput(e.target.value)}
              placeholder="./debug.log"
              className="w-48 px-3 py-1.5 rounded-lg rosetta-terminal-input text-xs text-rosetta-text placeholder:text-rosetta-muted/50"
            />
          </div>
        </div>
      </motion.div>

      {/* Web Search Section */}
      <motion.div
        className="rounded-xl bg-rosetta-surface border border-rosetta-border overflow-hidden"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <div className="px-6 py-4 border-b border-rosetta-border flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-rosetta-gold/10 flex items-center justify-center">
              <Globe className="w-3.5 h-3.5 text-rosetta-gold" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-rosetta-text">
                Web Search
              </h2>
              <p className="text-[11px] text-rosetta-muted font-mono">
                Enable proxy-intercepted web search for any upstream provider
              </p>
            </div>
          </div>
          <Toggle
            checked={form.WEB_SEARCH_ENABLED}
            onChange={(v) =>
              setForm({ ...form, WEB_SEARCH_ENABLED: v })
            }
          />
        </div>

        <div
          className={`divide-y divide-rosetta-border transition-opacity duration-200 ${
            form.WEB_SEARCH_ENABLED ? "" : "opacity-50 pointer-events-none"
          }`}
        >
          {/* Provider Selection */}
          <div className="px-6 py-4">
            <div className="flex items-center gap-3 mb-3">
              <Globe className="w-4 h-4 text-rosetta-muted flex-shrink-0" />
              <div>
                <p className="text-sm text-rosetta-text">Search Provider</p>
                <p className="text-[11px] text-rosetta-muted font-mono">
                  Service used to execute web searches
                </p>
              </div>
            </div>
            <div className="grid grid-cols-5 gap-2">
              {SEARCH_PROVIDERS.map((p) => (
                <motion.button
                  key={p.value}
                  type="button"
                  onClick={() => {
                    const newProvider = p.value;
                    const newInfo = SEARCH_PROVIDERS.find(x => x.value === newProvider);
                    const updates: Partial<SettingsData> = { WEB_SEARCH_PROVIDER: newProvider };
                    if (newInfo && !newInfo.needsUrl) updates.WEB_SEARCH_BASE_URL = "";
                    if (newInfo && !newInfo.needsKey) updates.WEB_SEARCH_API_KEY = "";
                    setForm({ ...form, ...updates });
                  }}
                  className={`px-3 py-2 rounded-lg text-xs font-mono border transition-colors ${
                    form.WEB_SEARCH_PROVIDER === p.value
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

          {/* Conditional: API Key */}
          <AnimatePresence>
            {providerInfo?.needsKey && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="px-6 py-4 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <Key className="w-4 h-4 text-rosetta-muted flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-rosetta-text">API Key</p>
                <p className="text-[11px] text-rosetta-muted font-mono truncate">
                  {providerInfo.keyOptional ? `Optional for ${providerInfo.label}` : `Required for ${providerInfo.label}`}
                </p>
              </div>
                  </div>
                  <div className="relative w-48">
                    <input
                      type={showApiKey ? "text" : "password"}
                      value={form.WEB_SEARCH_API_KEY}
                      onChange={(e) =>
                        setForm({ ...form, WEB_SEARCH_API_KEY: e.target.value })
                      }
                      placeholder="Enter API key"
                      className="w-full px-3 py-1.5 pr-9 rounded-lg rosetta-terminal-input text-xs text-rosetta-text placeholder:text-rosetta-muted/50"
                    />
                    <button
                      type="button"
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-rosetta-muted hover:text-rosetta-text"
                    >
                      {showApiKey ? (
                        <EyeOff className="w-3.5 h-3.5" />
                      ) : (
                        <Eye className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Conditional: Base URL */}
          <AnimatePresence>
            {providerInfo?.needsUrl && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="px-6 py-4 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <Globe className="w-4 h-4 text-rosetta-muted flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-rosetta-text">Base URL</p>
                <p className="text-[11px] text-rosetta-muted font-mono truncate">
                  {providerInfo.urlOptional
                    ? `Optional remote ${providerInfo.label} API server`
                    : providerInfo.value === "searxng"
                    ? "SearXNG instance URL"
                    : "Custom search API endpoint"}
                </p>
              </div>
                  </div>
                  <input
                    type="text"
                    value={form.WEB_SEARCH_BASE_URL}
                    onChange={(e) =>
                      setForm({ ...form, WEB_SEARCH_BASE_URL: e.target.value })
                    }
                    placeholder={
                      providerInfo.value === "searxng"
                        ? "http://localhost:8080"
                        : providerInfo.value === "duckduckgo"
                        ? "http://remote-server:4479"
                        : "https://api.example.com/search"
                    }
                    className="w-48 px-3 py-1.5 rounded-lg rosetta-terminal-input text-xs text-rosetta-text placeholder:text-rosetta-muted/50"
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Max Results & Max Rounds */}
          <div className="px-6 py-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <Hash className="w-4 h-4 text-rosetta-muted flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-rosetta-text">Max Results</p>
                <p className="text-[11px] text-rosetta-muted font-mono truncate">
                  Number of search results per query
                </p>
              </div>
            </div>
            <input
              type="number"
              min={1}
              max={20}
              value={form.WEB_SEARCH_MAX_RESULTS}
              onChange={(e) =>
                setForm({
                  ...form,
                  WEB_SEARCH_MAX_RESULTS: Math.max(
                    1,
                    Math.min(20, parseInt(e.target.value) || 1)
                  ),
                })
              }
              className="w-20 px-3 py-1.5 rounded-lg rosetta-terminal-input text-xs text-rosetta-text text-center"
            />
          </div>

          <div className="px-6 py-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <RotateCw className="w-4 h-4 text-rosetta-muted flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-rosetta-text">Max Rounds</p>
                <p className="text-[11px] text-rosetta-muted font-mono truncate">
                  Maximum search-then-answer loops per request
                </p>
              </div>
            </div>
            <input
              type="number"
              min={1}
              max={10}
              value={form.WEB_SEARCH_MAX_ROUNDS}
              onChange={(e) =>
                setForm({
                  ...form,
                  WEB_SEARCH_MAX_ROUNDS: Math.max(
                    1,
                    Math.min(10, parseInt(e.target.value) || 1)
                  ),
                })
              }
              className="w-20 px-3 py-1.5 rounded-lg rosetta-terminal-input text-xs text-rosetta-text text-center"
            />
          </div>
        </div>
      </motion.div>

      {/* Info footer */}
      <div className="flex items-center gap-2 px-1">
        <div className="w-1.5 h-1.5 rounded-full bg-rosetta-gold/40" />
        <p className="text-[10px] text-rosetta-muted font-mono">
          Runtime overrides persist until server restart. For permanent changes,
          edit the <span className="text-rosetta-gold">.env</span> file.
        </p>
      </div>
    </motion.div>
  );
}
