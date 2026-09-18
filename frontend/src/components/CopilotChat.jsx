/**
 * components/CopilotChat.jsx
 * --------------------------
 * Chat interface for the Investigation Copilot.
 *
 * Design: investigative assistant, not chatbot.  Professional and clinical.
 * Every response shows tool calls (XAI) before the final answer.
 * Entity mentions are rendered as clickable chips that navigate to the
 * network explorer with the node highlighted.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation } from 'wouter';
import { Send, AlertTriangle, Info } from 'lucide-react';
import { askCopilot, getDemoQueries } from '@/api/copilot';
import ToolCallTrace from './ToolCallTrace';

// ---------------------------------------------------------------------------
// Entity chip: renders [E-xxxx ↗] and navigates to /network?highlight=<id>
// ---------------------------------------------------------------------------
function NodeChip({ id }) {
  const [, navigate] = useLocation();
  return (
    <button
      className="inline-flex items-center gap-0.5 mx-0.5 px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[11px] font-mono hover:bg-primary/20 transition-colors cursor-pointer"
      title={`Open ${id} in Network Canvas`}
      onClick={() => navigate(`/network?highlight=${id}`)}
    >
      {id} ↗
    </button>
  );
}

// ---------------------------------------------------------------------------
// Renders answer text with entity chip links
// ---------------------------------------------------------------------------
function AnswerText({ text }) {
  if (!text) return null;
  // Match E-[a-f0-9]{16} patterns in the text
  const ENTITY_SPLIT = /(E-[0-9a-f]{16})/;
  const ENTITY_TEST  = /^E-[0-9a-f]{16}$/;
  const parts = text.split(ENTITY_SPLIT);
  return (
    <div className="text-sm text-fg-primary leading-relaxed whitespace-pre-wrap">
      {parts.map((part, i) => {
        if (ENTITY_TEST.test(part)) {
          return <NodeChip key={i} id={part} />;
        }
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confidence badge
// ---------------------------------------------------------------------------
function ConfidenceBadge({ confidence }) {
  if (confidence === undefined || confidence === null) return null;
  let cls = 'bg-blue-bg text-blue';
  if (confidence < 0.4) cls = 'bg-amber-bg text-amber';
  else if (confidence >= 0.7) cls = 'bg-green-bg text-green';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono ${cls}`}>
      confidence: {(confidence * 100).toFixed(0)}%
    </span>
  );
}

// ---------------------------------------------------------------------------
// Single message bubble
// ---------------------------------------------------------------------------
function MessageBubble({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[85%] rounded-xl px-4 py-3 ${
          isUser
            ? 'bg-primary/20 text-fg-primary'
            : 'bg-bg-panel border border-border-subtle'
        }`}
      >
        {isUser ? (
          <p className="text-sm">{msg.content}</p>
        ) : (
          <>
            {/* Tool call trace — collapsed */}
            {msg.tools_used && msg.tools_used.length > 0 && (
              <ToolCallTrace toolCalls={msg.tools_used} />
            )}

            {/* Answer */}
            <AnswerText text={msg.content} />

            {/* Confidence */}
            {msg.confidence !== undefined && (
              <div className="mt-2">
                <ConfidenceBadge confidence={msg.confidence} />
              </div>
            )}

            {/* Warnings */}
            {msg.warnings && msg.warnings.length > 0 && (
              <div className="mt-2 flex flex-col gap-1">
                {msg.warnings.map((w, i) => (
                  <div key={i} className="flex items-start gap-1.5 text-[11px] text-amber">
                    <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Timestamp */}
            <div className="mt-1 text-[10px] text-fg-faint font-mono">
              {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Demo query card
// ---------------------------------------------------------------------------
function DemoCard({ query, description, onClick }) {
  return (
    <button
      onClick={() => onClick(query)}
      className="text-left p-3 rounded-lg border border-border-subtle bg-bg-panel hover:bg-sidebar-hover hover:border-primary/30 transition-all group"
    >
      <p className="text-sm text-fg-primary group-hover:text-primary transition-colors">
        "{query}"
      </p>
      {description && (
        <p className="text-[11px] text-fg-faint mt-1">{description}</p>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Main CopilotChat
// ---------------------------------------------------------------------------
export default function CopilotChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [demoQueries, setDemoQueries] = useState([]);
  const [sessionId] = useState(() => crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`);
  const scrollRef = useRef(null);

  // Load demo queries on mount
  useEffect(() => {
    getDemoQueries()
      .then((data) => setDemoQueries(Array.isArray(data) ? data : data.queries || []))
      .catch(() => {});
  }, []);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const sendMessage = useCallback(
    async (text) => {
      const query = (text || input).trim();
      if (!query || loading) return;

      const userMsg = { role: 'user', content: query, timestamp: new Date().toISOString() };
      setMessages((prev) => [...prev, userMsg]);
      setInput('');
      setLoading(true);

      try {
        const res = await askCopilot(query, sessionId);
        const assistantMsg = {
          role: 'assistant',
          content: res.answer || 'No response generated.',
          tools_used: res.tools_used || [],
          tool_results: res.tool_results || [],
          confidence: res.confidence,
          warnings: res.warnings || [],
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `Error: ${err.message || 'Failed to reach the copilot.'}`,
            timestamp: new Date().toISOString(),
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [input, loading, sessionId],
  );

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4">
        {/* Empty state: show demo cards */}
        {messages.length === 0 && demoQueries.length > 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-6">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-fg-primary">Ask a question</h3>
              <p className="text-sm text-fg-muted mt-1">
                Ask questions about the network in plain English.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-xl w-full">
              {demoQueries.slice(0, 4).map((dq, i) => (
                <DemoCard
                  key={i}
                  query={dq.query || dq}
                  description={dq.description}
                  onClick={(q) => sendMessage(q)}
                />
              ))}
            </div>
            <div className="flex items-center gap-1 text-[10px] text-fg-faint">
              <Info className="w-3 h-3" />
              Responses include tool-call traces for full transparency.
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}

        {/* Loading indicator */}
        {loading && (
          <div className="flex justify-start mb-4">
            <div className="px-4 py-3 rounded-xl bg-bg-panel border border-border-subtle">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
                <span className="text-sm text-fg-muted">Thinking…</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-border-subtle px-4 py-3">
        <div className="flex gap-2 max-w-3xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the network… (Ctrl+Enter to send)"
            className={`flex-1 bg-bg-root border border-border-subtle rounded-lg px-3 py-2 text-sm text-fg-primary placeholder:text-fg-faint focus:outline-none focus:border-primary/50 transition-colors`}
            disabled={loading}
          />
          <button
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary/80 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
          >
            <Send className="w-4 h-4" />
            Send
          </button>
        </div>
      </div>
    </div>
  );
}