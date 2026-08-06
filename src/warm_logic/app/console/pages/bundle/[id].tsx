import { Archive, ArrowLeft, CheckCircle, FileText, XCircle } from 'lucide-react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';

interface BundleData {
    meta: {
        format: string;
        created_at: string;
        integrity_hash: string;
        sovereign_version: string;
    };
    evidence: {
        event_id: string;
        description: string;
        category: string;
        severity: string;
        context: any;
        actor: { name: string; role: string };
    };
}

export default function BundleInspector() {
    const router = useRouter();
    const { id } = router.query;
    const [bundle, setBundle] = useState<BundleData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (id) {
            // In a real implementation, we would fetch from /api/bundle/[id]
            // For this prototype, we simulate fetching or link directly if implemented.
            // Assuming API exists:
            fetch(`/api/bundle/${id}`)
                .then(res => res.json())
                .then(data => {
                    if (data.bundle) setBundle(data.bundle);
                    setLoading(false);
                }).catch(() => setLoading(false));
        }
    }, [id]);

    if (loading) return <div className="min-h-screen bg-black text-gray-400 p-10 font-mono">Loading Bundle {id}...</div>;
    if (!bundle) return <div className="min-h-screen bg-black text-red-500 p-10 font-mono">Bundle not found or API unavailable.</div>;

    return (
        <div className="min-h-screen bg-black text-gray-200 font-sans">
            <Head>
                <title>Bundle Inspector | {id}</title>
            </Head>

            <div className="max-w-4xl mx-auto p-6">
                <Link href="/" className="flex items-center gap-2 text-gray-500 hover:text-white mb-8 transition-colors">
                    <ArrowLeft className="w-4 h-4" /> Back to Cockpit
                </Link>

                <header className="mb-10 border-b border-gray-800 pb-6">
                    <div className="flex items-center gap-3 mb-2">
                        <Archive className="w-8 h-8 text-blue-500" />
                        <h1 className="text-2xl font-bold text-white font-mono break-all">{id}</h1>
                    </div>
                    <div className="flex gap-4 text-xs font-mono text-gray-500 uppercase">
                        <span>Format: {bundle.meta.format}</span>
                        <span>•</span>
                        <span>Ver: {bundle.meta.sovereign_version}</span>
                        <span>•</span>
                        <span className="text-green-500 flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" /> Sealed
                        </span>
                    </div>
                </header>

                <section className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
                    <div className="bg-gray-900 border border-gray-800 p-6 rounded-lg">
                        <h3 className="text-gray-500 text-xs font-bold uppercase mb-4 flex items-center gap-2">
                            <CheckCircle className="w-4 h-4 text-green-500" /> Integrity Proof
                        </h3>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-xs text-gray-600 mb-1">Bundle Hash (SHA-256)</label>
                                <code className="block bg-black p-3 rounded text-xs text-yellow-500 font-mono break-all">
                                    {bundle.meta.integrity_hash}
                                </code>
                            </div>
                            <div>
                                <label className="block text-xs text-gray-600 mb-1">Timestamp</label>
                                <div className="font-mono text-sm">{bundle.meta.created_at}</div>
                            </div>
                        </div>
                    </div>

                    <div className="bg-gray-900 border border-gray-800 p-6 rounded-lg">
                        <h3 className="text-gray-500 text-xs font-bold uppercase mb-4 flex items-center gap-2">
                            <XCircle className="w-4 h-4 text-red-500" /> Refusal Reason
                        </h3>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-xs text-gray-600 mb-1">Actor</label>
                                <div className="font-mono text-sm">{bundle.evidence.actor.name} ({bundle.evidence.actor.role})</div>
                            </div>
                            <div>
                                <label className="block text-xs text-gray-600 mb-1">Description</label>
                                <div className="text-red-400 font-medium">{bundle.evidence.description}</div>
                            </div>
                            <div className="flex gap-2">
                                <span className="bg-red-900/30 text-red-500 px-2 py-1 rounded text-xs border border-red-900/50">
                                    {bundle.evidence.category}
                                </span>
                                <span className="bg-orange-900/30 text-orange-500 px-2 py-1 rounded text-xs border border-orange-900/50">
                                    {bundle.evidence.severity}
                                </span>
                            </div>
                        </div>
                    </div>
                </section>

                <section>
                    <h3 className="text-gray-500 text-xs font-bold uppercase mb-4 flex items-center gap-2">
                        <FileText className="w-4 h-4 text-gray-400" /> Evidence Context
                    </h3>
                    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
                        <pre className="p-6 text-xs text-gray-300 font-mono overflow-auto max-h-96">
                            {JSON.stringify(bundle.evidence.context, null, 2)}
                        </pre>
                    </div>
                </section>
            </div>
        </div>
    );
}
