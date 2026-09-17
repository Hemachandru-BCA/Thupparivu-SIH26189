/**
 * pages/CopilotPage.jsx
 * ---------------------
 * Investigation Copilot — full-page layout:
 *   left column (240px) = tool list sidebar grouped by category
 *   main column        = CopilotChat
 */

import React, { useState, useEffect } from 'react';
import { Sparkles, Loader } from 'lucide-react';
import CopilotChat from '@/components/CopilotChat';
import { getTools } from '@/api/copilot';

const CATEGORY_LABELS = {
  search: 'SEARCH',
  graph: 'GRAPH',
  evidence: 'EVIDENCE',
  financial: 'FINANCIAL',
  simulation: 'SIMULATION',
  other: 'TOOLS',
};

export default function CopilotPage() {
  const [tools, setTools] = useState([]);
  const [onInsert, setOnInsert] = useState(null);
  const [loading, setLoading] = useState(true);
  const [grouped, setGrouped] = useState({});

  useEffect(() => {
    getTools()
      .then((data) => {
        const list = Array.isArray(data) ? data : data.tools || [];
        setTools(list);

        // Group by category
        const groups = {};
        list.forEach((t) => {
          const cat = t.category || 'other';
          if (!groups[cat]) groups[cat] = [];
          groups[cat].push(t);
        });
        setGrouped(groups);
      })
      .finally(() => setLoading(false));
  }, []);

  // Callback passed to CopilotChat to insert a template query into the input.
  // We use a tiny event bridge since CopilotChat owns its input state.
  const insertTemplateInto = (fn) => setOnInsert(() => fn);

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="px-5 py-4 border-b border-border-subtle shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-primary" />
          <h1 className="text-lg font-semibold text-fg-primary">Investigation Copilot</h1>
        </div>
        <p className="text-sm text-fg-muted mt-0.5">
          Ask questions about the network in plain English.
        </p>
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        {/* Tool sidebar */}
        <aside className="w-60 border-r border-border-subtle shrink-0 overflow-y-auto bg-bg-secondary/40 hidden md:block">
          <div className="px-4 py-3 text-[10px] font-mono uppercase tracking-wider text-fg-faint border-b border-border-subtle">
            Available tools ({tools.length})
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-8 text-fg-faint">
              <Loader className="w-4 h-4 animate-spin" />
            </div>
          ) : (
            Object.entries(CATEGORY_LABELS).map(([cat, label]) => {
              const items = grouped[cat] || [];
              if (!items.length) return null;
              return (
                <div key={cat} className="px-3 py-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-fg-faint mb-1.5">
                    {label}
                  </div>
                  <div className="flex flex-col gap-1">
                    {items.map((t, i) => (
                      <button
                        key={i}
                        className="text-left px-2 py-1.5 rounded text-[11px] text-fg-muted hover:text-fg-primary hover:bg-sidebar-hover transition-colors font-mono"
                        onClick={() => onInsert?.(t)}
                        title={t.description || t.name}
                      >
                        {t.name}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </aside>

        {/* Chat column */}
        <main className="flex-1 min-w-0">
          <CopilotChat onInsert={(fn) => insertTemplateInto(fn)} />
        </main>
      </div>
    </div>
  );
}