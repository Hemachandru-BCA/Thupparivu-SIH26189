import React, { Suspense, lazy } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ErrorBoundary } from '@/components/error-boundary';
import { AppShell } from '@/components/app-shell';
import { InvestigationProvider } from '@/state/investigation-context';
import { AuthProvider, useAuth } from '@/state/auth-context';
import LoginPage from '@/components/login-page';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';

/* ── Route-level code splitting: each workspace loads on demand ── */
const InvestigationDesk = lazy(() => import('@/pages/workspace/investigation-desk'));
const NetworkWorkspace = lazy(() => import('@/pages/workspace/network-workspace'));
const EntitiesWorkspace = lazy(() => import('@/pages/workspace/entities-workspace'));
const CasesWorkspace = lazy(() => import('@/pages/workspace/cases-workspace'));
const EvidenceWorkspace = lazy(() => import('@/pages/workspace/evidence-workspace'));
const HypothesesWorkspace = lazy(() => import('@/pages/workspace/hypotheses-workspace'));
const FindingDetailPage = lazy(() => import('@/pages/workspace/finding-detail-workspace'));
const AnomaliesWorkspace = lazy(() => import('@/pages/workspace/anomalies-workspace'));
const TimelineWorkspace = lazy(() => import('@/pages/workspace/timeline-workspace'));
const AnalyticsWorkspace = lazy(() => import('@/pages/workspace/analytics-workspace'));
const SimulationWorkspace = lazy(() => import('@/pages/workspace/simulation-workspace'));
const CommunitiesWorkspace = lazy(() => import('@/pages/workspace/communities-workspace'));
const PipelineWorkspace = lazy(() => import('@/pages/workspace/pipeline-workspace'));
const AuditWorkspace = lazy(() => import('@/pages/workspace/audit-workspace'));
const ReportsWorkspace = lazy(() => import('@/pages/workspace/reports-workspace'));
const SettingsWorkspace = lazy(() => import('@/pages/workspace/settings-workspace'));
const CopilotPage = lazy(() => import('@/pages/CopilotPage'));
const FinancialWorkspace = lazy(() => import('@/pages/workspace/financial-workspace'));
const GapsWorkspace = lazy(() => import('@/pages/workspace/gaps-workspace'));
const CrossCaseWorkspace = lazy(() => import('@/pages/workspace/crosscase-workspace'));
const ModelsWorkspace = lazy(() => import('@/pages/workspace/models-workspace'));
const EntityAnalysisWorkspace = lazy(() => import('@/pages/workspace/entity-analysis-workspace'));
const BookmarksWorkspace = lazy(() => import('@/pages/workspace/bookmarks-workspace'));
const P1AnalysisWorkspace = lazy(() => import('@/pages/workspace/p1-analysis-workspace'));
const GeospatialWorkspace = lazy(() => import('@/pages/workspace/geospatial-workspace'));
const NLQueryWorkspace = lazy(() => import('@/pages/workspace/nl-query-workspace'));
const NextBestActionWorkspace = lazy(() => import('@/pages/workspace/next-best-action-workspace'));
const CaseSimilarityWorkspace = lazy(() => import('@/pages/workspace/case-similarity-workspace'));
const JudgeDemoWalkthrough = lazy(() => import('@/pages/workspace/demo-walkthrough'));
const NotFound = lazy(() => import('@/pages/not-found'));

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 30 * 1000,
            refetchOnWindowFocus: false,
            retry: 1,
        },
    },
});

function PageLoading() {
    return (
        <div className="flex items-center justify-center min-h-[40vh]">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
    );
}

function Router() {
    return <RoutedErrorBoundary><AppShell>
        <Suspense fallback={<PageLoading />}>
            <Switch>
                <Route path="/" component={InvestigationDesk} />
                <Route path="/network" component={NetworkWorkspace} />
                <Route path="/entities" component={EntitiesWorkspace} />
                <Route path="/cases" component={CasesWorkspace} />
                <Route path="/cases/:id" component={CasesWorkspace} />
                <Route path="/ghosts" component={AnomaliesWorkspace} />
                <Route path="/findings" component={HypothesesWorkspace} />
                <Route path="/findings/:id" component={FindingDetailPage} />
                <Route path="/dossiers" component={ReportsWorkspace} />
                <Route path="/dossiers/:id" component={ReportsWorkspace} />
                <Route path="/evidence" component={EvidenceWorkspace} />
                <Route path="/simulation" component={SimulationWorkspace} />
                <Route path="/analytics" component={AnalyticsWorkspace} />
                <Route path="/communities" component={CommunitiesWorkspace} />
                <Route path="/timeline" component={TimelineWorkspace} />
                <Route path="/pipeline" component={PipelineWorkspace} />
                <Route path="/audit" component={AuditWorkspace} />
                <Route path="/settings" component={SettingsWorkspace} />
                {/* New intelligence workspaces */}
                <Route path="/financial" component={FinancialWorkspace} />
                <Route path="/copilot" component={CopilotPage} />
                <Route path="/gaps" component={GapsWorkspace} />
                <Route path="/cross-case" component={CrossCaseWorkspace} />
                <Route path="/entity/:id" component={EntityAnalysisWorkspace} />
                <Route path="/bookmarks" component={BookmarksWorkspace} />
                <Route path="/p1-analysis" component={P1AnalysisWorkspace} />
                <Route path="/geospatial" component={GeospatialWorkspace} />
                <Route path="/nl-query" component={NLQueryWorkspace} />
                <Route path="/next-best" component={NextBestActionWorkspace} />
                <Route path="/case-similarity" component={CaseSimilarityWorkspace} />
                <Route path="/models" component={ModelsWorkspace} />
                <Route path="/judge" component={JudgeDemoWalkthrough} />
                {/* Legacy */}
                <Route path="/explorer" component={NetworkWorkspace} />
                <Route path="/search" component={EvidenceWorkspace} />
                <Route component={NotFound} />
            </Switch>
        </Suspense>
    </AppShell></RoutedErrorBoundary>;
}

function RoutedErrorBoundary({ children }) {
    const [location] = useLocation();
    return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function App() {
    return (
        <QueryClientProvider client={queryClient}>
            <WouterRouter>
                <InvestigationProvider>
                    <Router />
                </InvestigationProvider>
            </WouterRouter>
        </QueryClientProvider>
    );
}

function AuthGate() {
    const { loading, token, user, demoMode } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-zinc-950 text-white">
                <div className="text-center">
                    <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                    <p className="text-sm text-zinc-400">Loading…</p>
                </div>
            </div>
        );
    }

    // In demo mode or when a token exists, show the main app.
    if (demoMode || token || user) {
        return <App />;
    }

    return <LoginPage />;
}

export default function Root() {
    return (
        <AuthProvider>
            <AuthGate />
        </AuthProvider>
    );
}