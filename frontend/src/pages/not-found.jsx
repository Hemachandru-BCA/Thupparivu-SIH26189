import { Link } from 'wouter';
import { AlertCircle, ArrowLeft } from 'lucide-react';

export default function NotFound() {
    return (
        <div className="h-full flex items-center justify-center p-6 bg-bg-root">
            <div className="tp-panel max-w-md w-full p-6 text-center space-y-4">
                <div className="w-10 h-10 rounded bg-red-bg border border-red/30 flex items-center justify-center mx-auto text-red">
                    <AlertCircle size={20} />
                </div>
                <div>
                    <h1 className="text-[15px] font-semibold text-fg-primary mb-1">
                        404 — VIEW NOT FOUND
                    </h1>
                    <p className="text-[11px] text-fg-muted">
                        The requested analytical workspace does not exist in this investigation profile.
                    </p>
                </div>
                <Link href="/">
                    <button className="tp-btn tp-btn-primary text-[10px] gap-1.5 mx-auto">
                        <ArrowLeft size={11} /> Return to Investigation Desk
                    </button>
                </Link>
            </div>
        </div>
    );
}

