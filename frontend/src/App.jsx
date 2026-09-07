import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ErrorBoundary } from '@/components/error-boundary';
import { Shell } from '@/components/graph-shell';
import { AnalyticsPage, AuditLogPage, CaseDetailPage, CasesPage, CommunicationsPage, CommunitiesPage, DashboardPage, EntitiesPage, GhostsPage, NetworkPage, PipelinePage, SettingsPage, TimelinePage, TransactionsPage } from '@/pages/graph-pages';
import { ExplorerPage } from '@/pages/explorer-page';
import { DossiersPage, EvidencePage, FindingDetailPage, FindingsPage, SearchPage, SimulationPage } from '@/pages/intelligence-pages';
import NotFound from '@/pages/not-found';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';
const queryClient = new QueryClient();
function Router() {
    return <RoutedErrorBoundary><Shell><Switch>
    <Route path="/" component={DashboardPage}/>
    <Route path="/explorer" component={ExplorerPage}/>
    <Route path="/network" component={ExplorerPage}/>
    {/* legacy radial/SVG explorer kept for reference (Phase H replacement above) */}
    <Route path="/network-legacy" component={NetworkPage}/>
    <Route path="/entities" component={EntitiesPage}/>
    <Route path="/cases" component={CasesPage}/>
    <Route path="/cases/:id" component={CaseDetailPage}/>
    <Route path="/communications" component={CommunicationsPage}/>
    <Route path="/transactions" component={TransactionsPage}/>
    <Route path="/ghosts" component={GhostsPage}/>
    <Route path="/findings" component={FindingsPage}/>
    <Route path="/findings/:id" component={FindingDetailPage}/>
    <Route path="/dossiers" component={DossiersPage}/>
    <Route path="/evidence" component={EvidencePage}/>
    <Route path="/simulation" component={SimulationPage}/>
    <Route path="/search" component={SearchPage}/>
    <Route path="/analytics" component={AnalyticsPage}/>
    <Route path="/communities" component={CommunitiesPage}/>
    <Route path="/timeline" component={TimelinePage}/>
    <Route path="/pipeline" component={PipelinePage}/>
    <Route path="/audit" component={AuditLogPage}/>
    <Route path="/settings" component={SettingsPage}/>
    <Route component={NotFound}/>
  </Switch></Shell></RoutedErrorBoundary>;
}
function RoutedErrorBoundary({ children }) {
    const [location] = useLocation();
    return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}
function App() {
  return <QueryClientProvider client={queryClient}><WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}><Router /></WouterRouter></QueryClientProvider>;
}
export default App;
