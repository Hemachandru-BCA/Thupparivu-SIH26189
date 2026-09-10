/**
 * frontend/src/state/investigation-context.jsx
 * --------------------------------------------
 * Centralized investigation context for the Thupparivu workstation:
 *
 *  - selectedEntity: currently inspected node/entity
 *  - selectedEvidence: currently inspected evidence record
 *  - selectedHypothesis: currently inspected hypothesis
 *  - activeCase: current case workspace (default CASE-0421)
 *  - activeLayers: active relationship layers for network rendering
 *  - timeRange: [start, end] ISO bounds for temporal filtering
 *  - commandPaletteOpen: boolean
 *  - inspectorOpen: boolean
 *  - bookmarks: list of bookmarked items (entity, hypothesis, evidence, etc.)
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const InvestigationContext = createContext(null);

export const DEFAULT_CASE = {
    id: 'CASE-0421',
    title: 'Operation Sentinel - Multi-Jurisdiction Syndicate',
    classification: 'RESTRICTED // INVESTIGATIVE USE ONLY',
    status: 'ACTIVE',
    priority: 'HIGH',
    jurisdiction: 'State Criminal Investigation Department',
    created_at: '2026-08-01T00:00:00Z',
    dataset: 'Synthetic Investigation 07',
    investigator: 'Analyst S. Ramanujan (ID: S-8902)',
};

export function InvestigationProvider({ children }) {
    const [activeCase, setActiveCase] = useState(DEFAULT_CASE);
    const [selectedEntity, setSelectedEntity] = useState(null);
    const [selectedEvidence, setSelectedEvidence] = useState(null);
    const [selectedHypothesis, setSelectedHypothesis] = useState(null);
    const [inspectorOpen, setInspectorOpen] = useState(true);
    const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
    const [density, setDensity] = useState('compact'); // 'compact' | 'comfortable'

    // Temporal filter state
    const [timeRange, setTimeRange] = useState({
        start: '2025-01-01T00:00:00',
        end: '2025-12-31T23:59:59',
        asOf: '2025-12-31T23:59:59',
    });

    // Relationship layers filter
    const [activeLayers, setActiveLayers] = useState([
        'COMMUNICATION',
        'FINANCIAL',
        'LOCATION',
        'ORGANIZATIONAL',
        'SOCIAL',
    ]);

    // Investigation board / bookmarks
    const [bookmarks, setBookmarks] = useState([
        { id: 'BM-1', type: 'ENTITY', title: 'P000001 (Coordinator Candidate)', refId: 'P000001', note: 'Key bridge across G001/G002' },
        { id: 'BM-2', type: 'HYPOTHESIS', title: 'H-014 Potential Hidden Intermediary', refId: 'H-014', note: 'Cross-community structural hole' },
    ]);

    const toggleBookmark = useCallback((item) => {
        setBookmarks(prev => {
            const exists = prev.some(b => b.refId === item.refId);
            if (exists) {
                return prev.filter(b => b.refId !== item.refId);
            }
            return [...prev, { ...item, id: `BM-${Date.now()}`, added_at: new Date().toISOString() }];
        });
    }, []);

    const isBookmarked = useCallback((refId) => {
        return bookmarks.some(b => b.refId === refId);
    }, [bookmarks]);

    const inspectEntity = useCallback((entity) => {
        setSelectedEntity(entity);
        setSelectedEvidence(null);
        setSelectedHypothesis(null);
        setInspectorOpen(true);
    }, []);

    const inspectEvidence = useCallback((evidence) => {
        setSelectedEvidence(evidence);
        setSelectedEntity(null);
        setSelectedHypothesis(null);
        setInspectorOpen(true);
    }, []);

    const inspectHypothesis = useCallback((hypothesis) => {
        setSelectedHypothesis(hypothesis);
        setSelectedEntity(null);
        setSelectedEvidence(null);
        setInspectorOpen(true);
    }, []);

    const clearInspection = useCallback(() => {
        setSelectedEntity(null);
        setSelectedEvidence(null);
        setSelectedHypothesis(null);
    }, []);

    // Global keyboard shortcuts (Cmd+K, /, I, Esc)
    useEffect(() => {
        function handleKeyDown(e) {
            // Cmd+K or Ctrl+K -> Command palette
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                setCommandPaletteOpen(prev => !prev);
            }
            // / -> Search / Command palette (if not inside an input)
            else if (e.key === '/' && !e.target.closest('input, textarea, select')) {
                e.preventDefault();
                setCommandPaletteOpen(true);
            }
            // I -> Toggle Inspector
            else if (e.key.toLowerCase() === 'i' && !e.target.closest('input, textarea, select') && !e.metaKey && !e.ctrlKey) {
                e.preventDefault();
                setInspectorOpen(prev => !prev);
            }
            // Esc -> Close modals / clear selection
            else if (e.key === 'Escape') {
                if (commandPaletteOpen) {
                    setCommandPaletteOpen(false);
                }
            }
        }
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [commandPaletteOpen]);

    const value = {
        activeCase,
        setActiveCase,
        selectedEntity,
        setSelectedEntity: inspectEntity,
        selectedEvidence,
        setSelectedEvidence: inspectEvidence,
        selectedHypothesis,
        setSelectedHypothesis: inspectHypothesis,
        clearInspection,
        inspectorOpen,
        setInspectorOpen,
        commandPaletteOpen,
        setCommandPaletteOpen,
        density,
        setDensity,
        timeRange,
        setTimeRange,
        activeLayers,
        setActiveLayers,
        bookmarks,
        toggleBookmark,
        isBookmarked,
    };

    return (
        <InvestigationContext.Provider value={value}>
            {children}
        </InvestigationContext.Provider>
    );
}

export function useInvestigation() {
    const ctx = useContext(InvestigationContext);
    if (!ctx) {
        throw new Error('useInvestigation must be used within an InvestigationProvider');
    }
    return ctx;
}
