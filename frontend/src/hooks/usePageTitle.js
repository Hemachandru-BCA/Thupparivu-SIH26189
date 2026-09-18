// src/hooks/usePageTitle.js — workspace-level document.title override
import { useEffect } from 'react';

export function usePageTitle(title) {
    useEffect(() => {
        if (!title) return;
        const prev = document.title;
        document.title = `${title} — Thupparivu`;
        return () => {
            document.title = prev;
        };
    }, [title]);
}
