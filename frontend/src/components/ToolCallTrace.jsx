/**
 * components/ToolCallTrace.jsx
 * -----------------------------
 * XAI for the AI itself: shows which tools were called and what they
 * returned before the final answer. Collapsed by default, expandable to
 * reveal the full tool_result JSON. Dark card, subtle border — supporting
 * context, not the main answer.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Terminal } from 'lucide-react';

function summarizeInput(toolCall) {
  const input = toolCall.input || toolCall.args || {};
  try {
    const entries = Object.entries(input);
    if (!entries.length) return '(no input)';
    return entries
      .slice(0, 3)
      .map(([k, v]) => `${k}: ${String(v).slice(0, 40)}`)
      .join('  ');
  } catch {
    return String(input).slice(0, 80);
  }
}

function summarizeOutput(toolCall) {
  const out = toolCall.output ?? toolCall.result ?? toolCall.output_summary;
  if (out === undefined || out === null) return '(no output)';
  if (typeof out === 'string') return out.slice(0, 100);
  if (typeof out === 'object') {
    // Try to build a compact summary from common shapes
    if (Array.isArray(out)) return `${out.length} results`;
    const keys = Object.keys(out);
    if (keys.length <= 3) {
      return keys
        .map((k) => {
          const v = out[k];
          const vs = Array.isArray(v) ? `${v.length} items` : String(v).slice(0, 30);
          return `${k}: ${vs}`;
        })
        .join('  ');
    }
    return `${keys.length} fields`;
  }
  return String(out).slice(0, 100);
}

export default function ToolCallTrace({ toolCalls = [] }) {
  const [openIndex, setOpenIndex] = useState(null);

  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="mb-2 rounded-lg border border-border-subtle bg-bg-panel/60 overflow-hidden">
      <div className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-fg-faint border-b border-border-subtle flex items-center gap-1.5">
        <Terminal className="w-3 h-3" />
        Tool calls ({toolCalls.length})
      </div>
      {toolCalls.map((tc, idx) => {
        const open = openIndex === idx;
        return (
          <div key={idx} className="border-b border-border-subtle last:border-b-0">
            <button
              className="w-full flex items-start gap-2 px-3 py-2 text-left hover:bg-sidebar-hover transition-colors"
              onClick={() => setOpenIndex(open ? null : idx)}
            >
              <span className="mt-0.5 text-fg-faint">
                {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </span>
              <span className="flex-1 min-w-0">
                <span className="block">
                  <code className="text-[11px] font-mono text-primary px-1.5 py-0.5 rounded bg-primary/10">
                    {tc.name || tc.tool || 'tool'}
                  </code>
                </span>
                <span className="block text-[11px] text-fg-muted mt-0.5 font-mono">
                  {summarizeInput(tc)}
                </span>
                {!open && (
                  <span className="block text-[11px] text-fg-faint mt-0.5">
                    → {summarizeOutput(tc)}
                  </span>
                )}
              </span>
            </button>
            {open && (
              <pre className="mx-3 mb-2 px-3 py-2 rounded bg-bg-root text-[10px] font-mono text-fg-muted overflow-x-auto max-h-64 overflow-y-auto">
                {JSON.stringify(tc.output ?? tc.result ?? tc, null, 2)}
              </pre>
            )}
          </div>
        );
      })}
    </div>
  );
}