import { createRoot } from 'react-dom/client';
import App from './App';
import { ErrorBoundary } from '@/components/error-boundary';
import { ToastProvider } from '@/components/ui';
import { setBaseUrl } from '@/api/client';
import './index.css';
// Light theme — no dark class needed

// Same-origin by default (Vite dev server proxies /api → local backend).
// Override with VITE_API_BASE_URL / VITE_API_URL when deployed.
const apiBase = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '';
setBaseUrl(apiBase);

createRoot(document.getElementById('root'), {
    // Keeps caught errors off reportError(), which would raise the dev overlay.
    onCaughtError: (error, errorInfo) => {
        console.error(error, errorInfo.componentStack);
    },
}).render(<ErrorBoundary>
    <ToastProvider>
        <App />
    </ToastProvider>
</ErrorBoundary>);
