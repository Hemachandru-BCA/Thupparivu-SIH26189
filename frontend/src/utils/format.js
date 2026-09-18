// src/utils/format.js — canonical location for display-format helpers
// Previously lived in app-shell.jsx; re-exported from there for back-compat.

export function formatNumber(n) {
    if (n == null || isNaN(n)) return '—';
    return Number(n).toLocaleString();
}

export function formatTimestamp(ts) {
    if (!ts) return '—';
    try {
        const d = new Date(ts);
        return (
            d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) +
            ' · ' +
            d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
        );
    } catch {
        return String(ts);
    }
}

export function formatShortDate(ts) {
    if (!ts) return '—';
    return new Date(ts).toLocaleDateString();
}
