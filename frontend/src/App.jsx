import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ErrorBoundary } from '@/components/error-boundary';
import { AppShell } from '@/components/app-shell';
import { InvestigationProvider } from '@/state/investigation-context';
import InvestigationDesk from '@/pages/workspace/investigation-desk';
import NetworkWorkspace from '@/pages/workspace/network-workspace';
import EntitiesWorkspace from '@/pages/workspace/entities-workspace';
import EvidenceWorkspace from '@/pages/workspace/evidence-workspace';
import HypothesesWorkspace from '@/pages/workspace/hypotheses-workspace';
import FindingDetailPage from '@/pages/workspace/finding-detail-workspace';
import AnomaliesWorkspace from '@/pages/workspace/anomalies-workspace';
import TimelineWorkspace from '@/pages/workspace/timeline-workspace';
import AnalyticsWorkspace from '@/pages/workspace/analytics-workspace';
import SimulationWorkspace from '@/pages/workspace/simulation-workspace';
import CommunitiesWorkspace from '@/pages/workspace/communities-workspace';
import PipelineWorkspace from '@/pages/workspace/pipeline-workspace';
import AuditWorkspace from '@/pages/workspace/audit-workspace';
import ReportsWorkspace from '@/pages/workspace/reports-workspace';
import CasesWorkspace from '@/pages/workspace/cases-workspace';
import SettingsWorkspace from '@/pages/workspace/settings-workspace';
import FinancialWorkspace from '@/pages/workspace/financial-workspace';
import GapsWorkspace from '@/pages/workspace/gaps-workspace';
import CrossCaseWorkspace from '@/pages/workspace/crosscase-workspace';
import ModelsWorkspace from '@/pages/workspace/models-workspace';
import NotFound from '@/pages/not-found';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 30 * 1000,
            refetchOnWindowFocus: false,
            retry: 1,
        },
    },
});

function Router() {
    return <RoutedErrorBoundary><AppShell><Switch>
    <Route path="/" component={InvestigationDesk}/>
    <Route path="/network" component={NetworkWorkspace}/>
    <Route path="/entities" component={EntitiesWorkspace}/>
    <Route path="/cases" component={CasesWorkspace}/>
    <Route path="/cases/:id" component={CasesWorkspace}/>
    <Route path="/ghosts" component={AnomaliesWorkspace}/>
    <Route path="/findings" component={HypothesesWorkspace}/>
    <Route path="/findings/:id" component={FindingDetailPage}/>
    <Route path="/dossiers" component={ReportsWorkspace}/>
    <Route path="/dossiers/:id" component={ReportsWorkspace}/>
    <Route path="/evidence" component={EvidenceWorkspace}/>
    <Route path="/simulation" component={SimulationWorkspace}/>
    <Route path="/analytics" component={AnalyticsWorkspace}/>
    <Route path="/communities" component={CommunitiesWorkspace}/>
    <Route path="/timeline" component={TimelineWorkspace}/>
    <Route path="/pipeline" component={PipelineWorkspace}/>
    <Route path="/audit" component={AuditWorkspace}/>
    <Route path="/settings" component={SettingsWorkspace}/>
    {/* New intelligence workspaces */}
    <Route path="/financial" component={FinancialWorkspace}/>
    <Route path="/gaps" component={GapsWorkspace}/>
    <Route path="/cross-case" component={CrossCaseWorkspace}/>
    <Route path="/models" component={ModelsWorkspace}/>
    {/* Legacy */}
    <Route path="/explorer" component={NetworkWorkspace}/>
    <Route path="/search" component={EvidenceWorkspace}/>
    <Route component={NotFound}/>
  </Switch></AppShell></RoutedErrorBoundary>;
}

function RoutedErrorBoundary({ children }) {
    const [location] = useLocation();
    return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <InvestigationProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
      </InvestigationProvider>
    </QueryClientProvider>
  );
}

export default App;
