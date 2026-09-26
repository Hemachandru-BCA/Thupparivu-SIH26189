import { Component, } from 'react';
function toError(value) {
    if (value instanceof Error) {
        return value;
    }
    if (typeof value === 'string') {
        return new Error(value);
    }
    try {
        return new Error(JSON.stringify(value));
    }
    catch {
        return new Error(String(value));
    }
}
function DefaultFallback({ error, resetError }) {
    return (
        <div className="min-h-screen w-full flex items-center justify-center bg-bg-root p-6">
            <div className="max-w-lg w-full text-center">
                <div className="w-12 h-12 rounded bg-red-bg border border-red/30 flex items-center justify-center mx-auto mb-4">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-red">
                        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                </div>
                <h1 className="text-[16px] font-semibold text-fg-primary">
                    Component error
                </h1>
                <p className="mt-2 text-[13px] text-fg-secondary">
                    This panel hit an unexpected error. The rest of the workstation is still running.
                </p>
                {import.meta.env.DEV ? (
                    <pre className="mt-4 overflow-x-auto rounded border border-border-default bg-bg-elevated p-3 text-left text-[11px] font-mono text-fg-secondary whitespace-pre-wrap">
                        {error.message || String(error)}
                    </pre>
                ) : null}
                <button
                    type="button"
                    onClick={resetError}
                    className="mt-5 rounded border border-border-default bg-bg-elevated hover:bg-bg-hover px-4 py-2 text-[13px] text-fg-primary transition-colors cursor-pointer"
                >
                    Retry
                </button>
            </div>
        </div>
    );
}
export class ErrorBoundary extends Component {
    state = { error: null };
    static getDerivedStateFromError(error) {
        return { error: toError(error) };
    }
    componentDidCatch(error, info) {
        console.error('ErrorBoundary caught an error:', toError(error), info.componentStack);
    }
    componentDidUpdate(prevProps) {
        if (this.state.error !== null &&
            prevProps.resetKey !== this.props.resetKey) {
            this.resetError();
        }
    }
    resetError = () => {
        this.setState({ error: null });
    };
    render() {
        const { error } = this.state;
        if (error === null) {
            return this.props.children;
        }
        const Fallback = this.props.FallbackComponent ?? DefaultFallback;
        return <Fallback error={error} resetError={this.resetError}/>;
    }
}
