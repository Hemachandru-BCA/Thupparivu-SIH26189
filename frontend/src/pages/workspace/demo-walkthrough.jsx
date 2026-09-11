import React, { useState } from 'react';
import { Link, useLocation } from 'wouter';
import { 
    Sparkles, ChevronRight, Play, CheckCircle2, ShieldCheck, 
    Network as NetworkIcon, Users, FileText, FileArchive, ArrowRight, Zap 
} from 'lucide-react';

const STEPS = [
    {
        id: 1,
        title: "1. Global Network Overview",
        desc: "See the exact scale of the data: 13k+ entities and 24k+ relationships processed from disparate sources into one cohesive knowledge graph.",
        action: "OPEN NETWORK",
        link: "/network",
        icon: NetworkIcon,
        color: "text-blue",
        bg: "bg-blue/10"
    },
    {
        id: 2,
        title: "2. The 'Hidden Coordinator'",
        desc: "The system identifies a 'Ghost Node' connecting distinct criminal communities using purely structural and temporal graph signals. This is highly probable in drug/financial syndicates.",
        action: "VIEW GHOSTS",
        link: "/ghosts",
        icon: Sparkles,
        color: "text-purple",
        bg: "bg-purple/10"
    },
    {
        id: 3,
        title: "3. Transparent Evidence Chain",
        desc: "Examine a high-priority entity. Notice the 6-part signal breakdown and the 5-stage trace proving the system hasn't hallucinated. We mandate grounded evidence.",
        action: "EXPLORE ENTITY 360",
        link: "/entity/E-102",  // Example entity
        icon: ShieldCheck,
        color: "text-green",
        bg: "bg-green/10"
    },
    {
        id: 4,
        title: "4. Temporal Replay & Diff",
        desc: "Scrub backwards in time to see exactly how and when this criminal structure formed. Detect communication bursts before known incidents.",
        action: "OPEN TIMELINE REPLAY",
        link: "/timeline",
        icon: Play,
        color: "text-amber",
        bg: "bg-amber/10"
    },
    {
        id: 5,
        title: "5. Counterfactual 'What-If?'",
        desc: "Run a live graph simulation: What happens if we remove the key coordinator? Discover fragmentation impacts and hidden secondary lieutenants.",
        action: "RUN SIMULATION",
        link: "/simulation",
        icon: Zap,
        color: "text-primary",
        bg: "bg-primary/10"
    },
    {
        id: 6,
        title: "6. Court-Ready Export",
        desc: "Export an entire investigation dossier pack. All insights are stamped 'DRAFT FOR HUMAN REVIEW' and explicitly bounded by structured data constraints.",
        action: "GENERATE DOSSIER",
        link: "/dossiers",
        icon: FileArchive,
        color: "text-teal",
        bg: "bg-teal/10"
    }
];

export default function JudgeDemoWalkthrough() {
    const [, setLocation] = useLocation();

    return (
        <div className="h-full overflow-y-auto p-4 md:p-8 max-w-[900px] mx-auto animate-fade-in">
            <div className="tp-panel p-8 bg-bg-surface border-primary/30 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-8 opacity-5">
                    <Sparkles size={180} />
                </div>
                
                <div className="flex items-center gap-3 mb-4 text-primary relative z-10">
                    <Sparkles size={24} />
                    <h1 className="text-[24px] font-bold tracking-tight text-fg-primary">
                        Evaluation Walkthrough
                    </h1>
                </div>

                <div className="text-[13px] text-fg-secondary leading-relaxed max-w-[600px] mb-6 relative z-10">
                    Welcome to the <strong>SentinelGraph AI</strong> evaluation environment.<br/><br/>
                    This sandbox contains a pre-computed synthetic dataset (Seed 42) featuring <strong>13,146 entities</strong> and <strong>23,982 relationships</strong>. To fully evaluate the AI-powered intelligence engine, please follow this guided 3-4 minute interactive tour.
                </div>

                <div className="flex items-center gap-3">
                    <button 
                        onClick={() => setLocation('/network')}
                        className="tp-btn tp-btn-primary h-9 px-4 gap-2"
                    >
                        START TOUR <ArrowRight size={14} />
                    </button>
                </div>
            </div>

            <div className="mt-8 space-y-4">
                <div className="text-[10px] font-mono text-fg-faint mb-2">TOUR ITINERARY (6 STEPS)</div>
                {STEPS.map((step) => (
                    <div key={step.id} className="tp-panel p-4 flex flex-col md:flex-row gap-4 items-start md:items-center hover:bg-bg-hover transition-colors">
                        <div className={`w-10 h-10 shrink-0 rounded-full flex items-center justify-center ${step.bg} ${step.color} border border-border-subtle`}>
                            <step.icon size={18} />
                        </div>
                        <div className="flex-1">
                            <div className="text-[14px] font-bold text-fg-primary mb-1">{step.title}</div>
                            <div className="text-[12px] text-fg-secondary leading-relaxed">{step.desc}</div>
                        </div>
                        <Link href={step.link}>
                            <button className={`tp-btn h-8 px-3 shrink-0 ${step.color.replace('text', 'text')} bg-bg-surface border border-border-subtle hover:border-primary`}>
                                {step.action} <ChevronRight size={12} />
                            </button>
                        </Link>
                    </div>
                ))}
            </div>

            <div className="mt-8 pt-8 border-t border-border-subtle text-center space-y-2">
                <div className="text-[10px] font-mono text-fg-faint uppercase tracking-widest">
                    CORE SYSTEM PRINCIPLES
                </div>
                <div className="flex justify-center gap-4 text-[11px] font-mono text-fg-secondary">
                    <span className="flex items-center gap-1"><CheckCircle2 size={12} className="text-green" /> STRICT EVIDENCE PROVENANCE</span>
                    <span className="flex items-center gap-1"><CheckCircle2 size={12} className="text-purple" /> DETERMINISTIC GRAPH SIGNALS</span>
                    <span className="flex items-center gap-1"><CheckCircle2 size={12} className="text-blue" /> NO FABRICATED GUILT CLAIMS</span>
                </div>
            </div>
        </div>
    );
}