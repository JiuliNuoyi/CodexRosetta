import { useState } from "react";
import { motion } from "framer-motion";
import { KeyList } from "@/components/keys/KeyList";
import { KeyForm } from "@/components/keys/KeyForm";
import type { KeyFormData } from "@/components/keys/KeyForm";
import { useKeys } from "@/hooks/useKeys";
import type { KeyEntry } from "@/hooks/useKeys";

export function Dashboard() {
  const { keys, loading, addKey, updateKey, deleteKey, activateKey } = useKeys();
  const [formOpen, setFormOpen] = useState(false);
  const [editKey, setEditKey] = useState<KeyEntry | null>(null);

  const handleFormSubmit = async (data: KeyFormData) => {
    if (editKey) {
      const fields: Record<string, string | boolean | string[]> = {};
      if (data.provider !== editKey.provider) fields.provider = data.provider;
      if (data.base_url !== editKey.base_url) fields.base_url = data.base_url;
      if (data.key) fields.key = data.key;
      if (data.active !== editKey.active) fields.active = data.active;
      const modelsChanged =
        data.models.length !== editKey.models.length ||
        data.models.some((m, i) => m !== editKey.models[i]);
      if (modelsChanged) fields.models = data.models;
      await updateKey(editKey.name, fields);
    } else {
      await addKey(data);
    }
  };

  const handleEdit = (key: KeyEntry) => {
    setEditKey(key);
    setFormOpen(true);
  };

  const handleAdd = () => {
    setEditKey(null);
    setFormOpen(true);
  };

  const handleClose = () => {
    setFormOpen(false);
    setEditKey(null);
  };

  return (
    <motion.div
      className="p-6"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          {
            label: "Total Keys",
            value: keys.length,
            color: "text-rosetta-gold",
          },
          {
            label: "Active",
            value: keys.filter((k) => k.active).length,
            color: "text-rosetta-success",
          },
          {
            label: "Providers",
            value: new Set(keys.map((k) => k.provider)).size,
            color: "text-rosetta-text",
          },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            className="p-4 rounded-xl bg-rosetta-surface border border-rosetta-border"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
          >
            <p className="text-xs font-mono text-rosetta-muted mb-1">
              {stat.label}
            </p>
            <p className={`text-2xl font-mono font-bold ${stat.color}`}>
              {stat.value}
            </p>
          </motion.div>
        ))}
      </div>

      {/* Key List */}
      <div className="rounded-xl bg-rosetta-surface border border-rosetta-border p-6">
        <KeyList
          keys={keys}
          loading={loading}
          onActivate={activateKey}
          onDelete={deleteKey}
          onAdd={handleAdd}
          onEdit={handleEdit}
        />
      </div>

      <KeyForm
        isOpen={formOpen}
        onClose={handleClose}
        onSubmit={handleFormSubmit}
        editKey={editKey}
      />
    </motion.div>
  );
}
