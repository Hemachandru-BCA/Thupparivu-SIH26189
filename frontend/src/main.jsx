import { createRoot } from 'react-dom/client';
import App from './App';
import { ErrorBoundary } from '@/components/error-boundary';
import { setBaseUrl } from '@/api/client';
import './index.css';
document.documentElement.classList.add('dark');

const DEFAULT_API_URL = 'https://thupparivu-sih26189-ahalya-private-production.up.railway.app';
const apiBase = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || DEFAULT_API_URL;
setBaseUrl(apiBase);

createRoot(document.getElementById('root'), {
    // Keeps caught errors off reportError(), which would raise the dev overlay.
    onCaughtError: (error, errorInfo) => {
        console.error(error, errorInfo.componentStack);
    },
}).render(<ErrorBoundary>
    <App />
</ErrorBoundary>);
