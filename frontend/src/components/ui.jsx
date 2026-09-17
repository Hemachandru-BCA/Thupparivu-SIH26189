/* =============================================================================
   SENTINELGRAPH — Shared UI Component Library
   Enterprise investigation platform primitives.
   All styling via CSS custom properties from index.css token system.
============================================================================= */

import React, { createContext, useContext, useState, useCallback, useRef, useEffect, forwardRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, ChevronRight, X, Search, AlertTriangle, Info, CheckCircle2, XCircle, Clock, Loader2, ChevronUp, MoreHorizontal } from 'lucide-react';

/* ---------------------------------------------------------------------------
   TOKENS — imported from index.css; components reference hsl(var(--xxx))
   via Tailwind classes or inline styles.
--------------------------------------------------------------------------- */

/* ---------------------------------------------------------------------------
   STATUS LABEL
   Semantic status indicator. Always conveys meaning through text + color.
--------------------------------------------------------------------------- */
const STATUS_STYLES = {
  observed:   { bg: 'bg-green-bg',   text: 'text-green',   border: 'border-green/30',  label: 'OBSERVED' },
  inferred:   { bg: 'bg-blue-bg',    text: 'text-blue',    border: 'border-blue/30',   label: 'INFERRED' },
  unknown:    { bg: 'bg-[hsl(220,6%,18%)]', text: 'text-fg-muted', border: 'border-border-default', label: 'UNKNOWN' },
  contradicted: { bg: 'bg-red-bg',   text: 'text-red',     border: 'border-red/30',    label: 'CONTRADICTED' },
  simulated:  { bg: 'bg-purple-bg',  text: 'text-purple',  border: 'border-purple/30', label: 'SIMULATED' },
  hypothesis: { bg: 'bg-amber-bg',   text: 'text-amber',   border: 'border-amber/30',  label: 'HYPOTHESIS' },
  draft:      { bg: 'bg-amber-bg',   text: 'text-amber',   border: 'border-amber/30',  label: 'DRAFT' },
  active:     { bg: 'bg-green-bg',   text: 'text-green',   border: 'border-green/30',  label: 'ACTIVE' },
  complete:   { bg: 'bg-green-bg',   text: 'text-green',   border: 'border-green/30',  label: 'COMPLETE' },
  running:    { bg: 'bg-blue-bg',    text: 'text-blue',    border: 'border-blue/30',   label: 'RUNNING' },
  queued:     { bg: 'bg-[hsl(220,6%,18%)]', text: 'text-fg-muted', border: 'border-border-default', label: 'QUEUED' },
  failed:     { bg: 'bg-red-bg',     text: 'text-red',     border: 'border-red/30',    label: 'FAILED' },
  high:       { bg: 'bg-red-bg',     text: 'text-red',     border: 'border-red/30',    label: 'HIGH' },
  medium:     { bg: 'bg-amber-bg',   text: 'text-amber',   border: 'border-amber/30',  label: 'MEDIUM' },
  low:        { bg: 'bg-green-bg',   text: 'text-green',   border: 'border-green/30',  label: 'LOW' },
};

export function StatusLabel({ status, className = '' }) {
  const s = STATUS_STYLES[status?.toLowerCase()] || STATUS_STYLES.unknown;
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide rounded ${s.bg} ${s.text} ${s.border} border ${className}`}>
      {s.label}
    </span>
  );
}

/* ---------------------------------------------------------------------------
   STATE MARKER — visual + text cue for observed/inferred/unknown
--------------------------------------------------------------------------- */
const STATE_MARKERS = {
  observed:   { icon: CheckCircle2, className: 'text-green' },
  inferred:   { icon: Info,        className: 'text-blue' },
  unknown:    { icon: Info,        className: 'text-fg-muted' },
  contradicted:{ icon: XCircle,    className: 'text-red' },
  hypothesis: { icon: AlertTriangle, className: 'text-amber' },
  simulated:  { icon: Clock,       className: 'text-purple' },
};

export function StateMarker({ state, showLabel = true, className = '' }) {
  const s = STATE_MARKERS[state?.toLowerCase()] || STATE_MARKERS.unknown;
  const Icon = s.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] ${s.className} ${className}`}>
      <Icon size={12} />
      {showLabel && <span className="uppercase font-medium tracking-wide">{state || 'UNKNOWN'}</span>}
    </span>
  );
}

/* ---------------------------------------------------------------------------
   CONFIDENCE BREAKDOWN
   Decomposed confidence visualization as horizontal bar segments.
--------------------------------------------------------------------------- */
export function ConfidenceBreakdown({ components = {}, className = '' }) {
  const entries = Object.entries(components);
  if (!entries.length) return null;
  return (
    <div className={`space-y-1.5 ${className}`}>
      {entries.map(([key, value]) => {
        const pct = Math.round((value || 0) * 100);
        return (
          <div key={key} className="flex items-center gap-2">
            <span className="text-[11px] text-fg-secondary w-28 truncate" title={key}>
              {key.replace(/_/g, ' ')}
            </span>
            <div className="flex-1 h-1.5 bg-[hsl(220,10%,16%)] rounded-sm overflow-hidden">
              <div
                className="h-full bg-blue rounded-sm transition-all duration-base"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-[10px] text-fg-muted font-mono w-8 text-right">{pct}%</span>
          </div>
        );
      })}
    </div>
  );
}

/* ---------------------------------------------------------------------------
   OBJECT ID — monospace technical identifier
--------------------------------------------------------------------------- */
export function ObjectId({ id, className = '' }) {
  return (
    <span className={`font-mono text-[11px] text-fg-muted ${className}`} title={id}>
      {id}
    </span>
  );
}

/* ---------------------------------------------------------------------------
   TIMESTAMP — consistent date display
--------------------------------------------------------------------------- */
export function Timestamp({ value, className = '' }) {
  if (!value) return <span className="text-fg-faint text-[11px]">—</span>;
  let display;
  try {
    const d = new Date(value);
    display = `${d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })} · ${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`;
  } catch {
    display = String(value);
  }
  return <time className={`text-[11px] text-fg-secondary ${className}`} dateTime={value}>{display}</time>;
}

/* ---------------------------------------------------------------------------
   NOTICE BANNER — reusable disclaimer / hypothesis / simulation notice
--------------------------------------------------------------------------- */
const BANNER_STYLES = {
  info:    { bg: 'bg-blue-bg',    border: 'border-blue/30',    icon: Info,         iconClass: 'text-blue' },
  warning: { bg: 'bg-amber-bg',   border: 'border-amber/30',   icon: AlertTriangle, iconClass: 'text-amber' },
  error:   { bg: 'bg-red-bg',     border: 'border-red/30',     icon: XCircle,      iconClass: 'text-red' },
  success: { bg: 'bg-green-bg',   border: 'border-green/30',   icon: CheckCircle2, iconClass: 'text-green' },
  hypothesis: { bg: 'bg-amber-bg', border: 'border-amber/30', icon: AlertTriangle, iconClass: 'text-amber' },
  simulation: { bg: 'bg-purple-bg', border: 'border-purple/30', icon: AlertTriangle, iconClass: 'text-purple' },
  draft:   { bg: 'bg-amber-bg',   border: 'border-amber/30',   icon: Clock,        iconClass: 'text-amber' },
};

export function NoticeBanner({ variant = 'info', title, children, className = '', dismissible = false, onDismiss }) {
  const s = BANNER_STYLES[variant] || BANNER_STYLES.info;
  const Icon = s.icon;
  return (
    <div className={`flex items-start gap-2 px-3 py-2 ${s.bg} ${s.border} border rounded-sm text-[12px] ${className}`}>
      <Icon size={14} className={`${s.iconClass} shrink-0 mt-0.5`} />
      <div className="flex-1 min-w-0">
        {title && <div className="font-semibold text-fg-primary mb-0.5">{title}</div>}
        <div className="text-fg-secondary">{children}</div>
      </div>
      {dismissible && (
        <button onClick={onDismiss} className="text-fg-faint hover:text-fg-primary p-0.5 shrink-0" aria-label="Dismiss">
          <X size={12} />
        </button>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------------------
   BUTTON
--------------------------------------------------------------------------- */
const BUTTON_VARIANTS = {
  primary:   'bg-primary text-primary-fg hover:bg-primary-hover border-transparent',
  secondary: 'bg-[hsl(220,10%,16%)] text-fg-primary border-border-default hover:bg-[hsl(220,10%,20%)]',
  quiet:     'bg-transparent text-fg-secondary border-transparent hover:bg-[hsl(220,10%,12%)] hover:text-fg-primary',
  destructive:'bg-red-bg text-red border-red/30 hover:bg-red/20',
  ghost:     'bg-transparent text-fg-muted border-transparent hover:text-fg-primary hover:bg-[hsl(220,10%,12%)]',
};

export const Button = forwardRef(function Button({
  variant = 'secondary', size = 'md', children, className = '', disabled, ...props
}, ref) {
  const sizeClasses = {
    sm: 'h-6 px-2 text-[11px] gap-1',
    md: 'h-7 px-3 text-[12px] gap-1.5',
    lg: 'h-8 px-4 text-[13px] gap-2',
  };
  return (
    <button
      ref={ref}
      disabled={disabled}
      className={`inline-flex items-center justify-center font-medium rounded-sm border transition-colors duration-fast cursor-pointer
        ${BUTTON_VARIANTS[variant] || BUTTON_VARIANTS.secondary}
        ${sizeClasses[size] || sizeClasses.md}
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${className}`}
      {...props}
    >
      {children}
    </button>
  );
});

/* ---------------------------------------------------------------------------
   INPUT
--------------------------------------------------------------------------- */
export const Input = forwardRef(function Input({ className = '', ...props }, ref) {
  return (
    <input
      ref={ref}
      className={`h-7 px-2.5 text-[12px] bg-[hsl(220,13%,10%)] border border-border-default rounded-sm text-fg-primary
        placeholder:text-fg-faint focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30
        transition-colors duration-fast ${className}`}
      {...props}
    />
  );
});

/* ---------------------------------------------------------------------------
   SELECT
--------------------------------------------------------------------------- */
export function Select({ value, onChange, options = [], className = '', placeholder }) {
  return (
    <select
      value={value || ''}
      onChange={e => onChange?.(e.target.value)}
      className={`h-7 px-2.5 text-[12px] bg-[hsl(220,13%,10%)] border border-border-default rounded-sm text-fg-primary
        focus:outline-none focus:border-primary cursor-pointer appearance-none
        ${className}`}
      style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%23666'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 8px center' }}
    >
      {placeholder && <option value="">{placeholder}</option>}
      {options.map(o => (
        <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>
      ))}
    </select>
  );
}

/* ---------------------------------------------------------------------------
   TABS
--------------------------------------------------------------------------- */
export function Tabs({ tabs, active, onChange, className = '' }) {
  return (
    <div className={`flex border-b border-border-default ${className}`} role="tablist">
      {tabs.map(t => (
        <button
          key={t.value ?? t}
          role="tab"
          aria-selected={active === (t.value ?? t)}
          onClick={() => onChange(t.value ?? t)}
          className={`px-3 h-8 text-[12px] font-medium transition-colors border-b-2 -mb-px cursor-pointer
            ${active === (t.value ?? t)
              ? 'border-primary text-fg-primary'
              : 'border-transparent text-fg-muted hover:text-fg-secondary hover:border-border-strong'}`}
        >
          {t.label ?? t}
        </button>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------------------
   DRAWER
   Right-side contextual inspector. 380–440px.
--------------------------------------------------------------------------- */
export function Drawer({ open, onClose, title, width = 400, children, footer }) {
  if (!open) return null;
  return createPortal(
    <>
      <div className="fixed inset-0 bg-black/40 z-50" onClick={onClose} />
      <div
        className="fixed top-0 right-0 bottom-0 bg-bg-panel border-l border-border-default z-50 flex flex-col overflow-hidden animate-in"
        style={{ width: `${width}px`, maxWidth: '90vw' }}
      >
        <div className="flex items-center justify-between h-10 px-3 border-b border-border-default shrink-0">
          <h3 className="text-[13px] font-semibold text-fg-primary truncate">{title}</h3>
          <button onClick={onClose} className="text-fg-faint hover:text-fg-primary p-0.5 cursor-pointer" aria-label="Close">
            <X size={14} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3">{children}</div>
        {footer && <div className="border-t border-border-default px-3 py-2 shrink-0">{footer}</div>}
      </div>
    </>,
    document.body
  );
}

/* ---------------------------------------------------------------------------
   DIALOG / MODAL
--------------------------------------------------------------------------- */
export function Dialog({ open, onClose, title, children, footer, width = 480 }) {
  if (!open) return null;
  return createPortal(
    <>
      <div className="fixed inset-0 bg-black/50 z-50" onClick={onClose} />
      <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
        <div
          className="bg-bg-panel border border-border-default rounded-sm shadow-lg flex flex-col max-h-[80vh]"
          style={{ width: `${width}px`, maxWidth: '95vw' }}
          onClick={e => e.stopPropagation()}
        >
          <div className="flex items-center justify-between h-10 px-4 border-b border-border-default shrink-0">
            <h3 className="text-[13px] font-semibold text-fg-primary">{title}</h3>
            <button onClick={onClose} className="text-fg-faint hover:text-fg-primary p-0.5 cursor-pointer" aria-label="Close">
              <X size={14} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 text-[13px] text-fg-secondary">{children}</div>
          {footer && <div className="border-t border-border-default px-4 py-2 flex justify-end gap-2 shrink-0">{footer}</div>}
        </div>
      </div>
    </>,
    document.body
  );
}

/* ---------------------------------------------------------------------------
   TABLE — reusable data grid foundation
--------------------------------------------------------------------------- */
export function DataGrid({ columns = [], rows = [], onRowClick, emptyMessage = 'No data available', className = '', compact = true }) {
  const rowH = compact ? 'h-8' : 'h-10';
  if (!rows.length) {
    return (
      <div className={`text-center py-8 text-[12px] text-fg-muted ${className}`}>
        {emptyMessage}
      </div>
    );
  }
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full text-[12px]">
        <thead>
          <tr className="border-b border-border-default">
            {columns.map((col, i) => (
              <th
                key={col.key || i}
                className={`text-left font-medium text-fg-muted uppercase tracking-wide px-3 ${rowH} ${col.align === 'right' ? 'text-right' : ''}`}
                style={col.width ? { width: col.width } : undefined}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr
              key={row.id || ri}
              onClick={onRowClick ? () => onRowClick(row, ri) : undefined}
              className={`border-b border-border-subtle hover:bg-[hsl(220,10%,10%)] transition-colors
                ${onRowClick ? 'cursor-pointer' : ''}`}
            >
              {columns.map((col, ci) => (
                <td key={col.key || ci} className={`px-3 ${rowH} ${col.align === 'right' ? 'text-right font-mono' : ''} ${col.mono ? 'font-mono' : ''} text-fg-primary truncate max-w-[200px]`}>
                  {col.render ? col.render(row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------------------------------------------------------------------------
   LOADING STATE — contextual, not generic
--------------------------------------------------------------------------- */
export function LoadingState({ message = 'Loading…', className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center py-12 gap-3 ${className}`}>
      <Loader2 size={20} className="text-fg-muted animate-spin" />
      <p className="text-[12px] text-fg-secondary">{message}</p>
    </div>
  );
}

/* ---------------------------------------------------------------------------
   EMPTY STATE
--------------------------------------------------------------------------- */
export function EmptyState({ title, description, action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center py-12 gap-2 text-center ${className}`}>
      <div className="text-[13px] font-medium text-fg-primary">{title}</div>
      {description && <p className="text-[12px] text-fg-muted max-w-md">{description}</p>}
      {action}
    </div>
  );
}

/* ---------------------------------------------------------------------------
   ERROR STATE
--------------------------------------------------------------------------- */
export function ErrorState({ title = 'Unable to load', message, retry, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center py-12 gap-3 text-center ${className}`}>
      <XCircle size={20} className="text-red" />
      <div className="text-[13px] font-medium text-fg-primary">{title}</div>
      {message && <p className="text-[12px] text-fg-muted max-w-md">{message}</p>}
      {retry && (
        <button onClick={retry} className="text-[12px] text-primary hover:text-primary-hover cursor-pointer">
          Retry
        </button>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------------------
   METADATA GROUP — compact definition list
--------------------------------------------------------------------------- */
export function MetadataGroup({ items = [], className = '', horizontal = false }) {
  if (horizontal) {
    return (
      <div className={`flex flex-wrap gap-x-4 gap-y-1 ${className}`}>
        {items.map(({ label, value }, i) => (
          <span key={i} className="text-[11px]">
            <span className="text-fg-faint uppercase tracking-wide">{label}</span>
            <span className="text-fg-secondary ml-1.5">{value ?? '—'}</span>
          </span>
        ))}
      </div>
    );
  }
  return (
    <dl className={`space-y-1 ${className}`}>
      {items.map(({ label, value, mono }, i) => (
        <div key={i} className="flex items-baseline gap-2">
          <dt className="text-[10px] text-fg-faint uppercase tracking-wide w-24 shrink-0">{label}</dt>
          <dd className={`text-[12px] text-fg-primary ${mono ? 'font-mono' : ''} truncate`}>{value ?? '—'}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ---------------------------------------------------------------------------
   SECTION HEADER — consistent section dividers
--------------------------------------------------------------------------- */
export function SectionHeader({ label, action, className = '' }) {
  return (
    <div className={`flex items-center justify-between border-b border-border-subtle pb-1 mb-2 ${className}`}>
      <h4 className="text-[11px] font-semibold text-fg-muted uppercase tracking-wide">{label}</h4>
      {action}
    </div>
  );
}

/* ---------------------------------------------------------------------------
   PAGE HEADER — consistent page headers
--------------------------------------------------------------------------- */
export function PageHeader({ title, subtitle, breadcrumbs, actions, metadata, className = '' }) {
  return (
    <div className={`px-6 pt-4 pb-3 border-b border-border-default bg-bg-surface ${className}`}>
      {breadcrumbs && (
        <div className="flex items-center gap-1 text-[11px] text-fg-faint mb-1.5">
          {breadcrumbs.map((b, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span className="text-fg-faint">/</span>}
              {b.href ? (
                <a href={b.href} className="hover:text-fg-secondary transition-colors">{b.label}</a>
              ) : (
                <span className="text-fg-secondary">{b.label}</span>
              )}
            </React.Fragment>
          ))}
        </div>
      )}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[18px] font-semibold text-fg-primary leading-tight">{title}</h1>
          {subtitle && <p className="text-[12px] text-fg-secondary mt-0.5">{subtitle}</p>}
          {metadata && <div className="mt-1">{metadata}</div>}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
   FILTER BAR — compact filter controls
--------------------------------------------------------------------------- */
export function FilterBar({ children, activeCount = 0, onClearAll, className = '' }) {
  return (
    <div className={`flex items-center gap-2 px-4 py-2 border-b border-border-subtle bg-bg-surface ${className}`}>
      <span className="text-[11px] text-fg-faint uppercase tracking-wide shrink-0">Filters</span>
      <div className="flex items-center gap-2 flex-1 overflow-x-auto">{children}</div>
      {activeCount > 0 && onClearAll && (
        <button onClick={onClearAll} className="text-[11px] text-primary hover:text-primary-hover shrink-0 cursor-pointer">
          Clear all ({activeCount})
        </button>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------------------
   TOOLBAR — page toolbar
--------------------------------------------------------------------------- */
export function Toolbar({ left, right, className = '' }) {
  return (
    <div className={`flex items-center justify-between gap-3 px-4 py-2 border-b border-border-subtle ${className}`}>
      <div className="flex items-center gap-2 min-w-0 flex-1">{left}</div>
      <div className="flex items-center gap-2 shrink-0">{right}</div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
   EMPTY GRAPH STATE
--------------------------------------------------------------------------- */
export function EmptyGraphState({ action }) {
  return (
    <EmptyState
      title="No network loaded"
      description="Build or select a graph artifact to begin exploration."
      action={action}
    />
  );
}

/* ---------------------------------------------------------------------------
   COMPACT METRIC — inline metric display
--------------------------------------------------------------------------- */
export function CompactMetric({ label, value, className = '' }) {
  return (
    <div className={`flex items-baseline gap-1.5 ${className}`}>
      <span className="text-[10px] text-fg-faint uppercase tracking-wide">{label}</span>
      <span className="text-[13px] font-semibold text-fg-primary font-mono">{value ?? '—'}</span>
    </div>
  );
}

/* ---------------------------------------------------------------------------
   INLINE TAG — compact inline label
--------------------------------------------------------------------------- */
export function Tag({ children, className = '' }) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0 text-[10px] font-medium bg-[hsl(220,10%,16%)] text-fg-secondary border border-border-default rounded-sm ${className}`}>
      {children}
    </span>
  );
}
