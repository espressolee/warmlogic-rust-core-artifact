import { AlertTriangle, Lock, Shield } from 'lucide-react';
import Head from 'next/head';
import { useEffect, useState } from 'react';

interface RefusalEvent {
    event_id: string;
    created_at: string;
    category: string;
    severity: string;
    description: string;
    context: any;
}

export default function Dashboard() {
    const [events, setEvents] = useState<RefusalEvent[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch('/api/spine')
            .then(res => res.json())
            .then(data => {
                setEvents(data.events || []);
                setLoading(false);
            });
    }, []);

    return (
        <div className="min-h-screen bg-black text-gray-200 font-sans selection:bg-red-900">
            <Head>
                <title>Sovereign Audit Cockpit | WarmLogic</title>
            </Head>

            <div className="max-w-6xl mx-auto p-6">
                <header className="mb-10 border-b border-gray-800 pb-6 flex justify-between items-center">
                    <div>
                        <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
                            <Shield className="w-8 h-8 text-red-500" />
                            Sovereign Refusal Engine
                        </h1>
                        <p className="text-gray-500 mt-2 font-mono text-sm">
                            EVIDENCE-CONSTRAINED EXECUTION KERNEL // ERA 30
                        </p>
                    </div>
                    <div className="flex gap-4">
                        <div className="bg-gray-900 border border-gray-800 px-4 py-2 rounded text-xs font-mono text-gray-400">
                            STATUS: <span className="text-green-500">ACTIVE</span>
                        </div>
                        <div className="bg-gray-900 border border-gray-800 px-4 py-2 rounded text-xs font-mono text-gray-400">
                            ENCLAVE: <span className="text-green-500">BOUND</span>
                        </div>
                    </div>
                </header>

                <main>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
                        <StatCard label="Total Refusals" value={events.length} icon={<AlertTriangle className="text-red-500" />} />
                        <StatCard label="Critical Blocks" value={events.filter(e => e.severity === 'critical').length} icon={<Lock className="text-orange-500" />} />
                        <StatCard label="Active Caps" value={5} icon={<Shield className="text-green-500" />} />
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-10">
                        <div>
                            <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                                <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
                                Refusal Ledger (Live)
                            </h2>

                            <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
                                {loading ? (
                                    <div className="p-8 text-center font-mono text-gray-500">Loading Matrix...</div>
                                ) : events.length === 0 ? (
                                    <div className="p-8 text-center font-mono text-gray-500">No refusals recorded.</div>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-left bg-gray-950">
                                            <thead className="bg-gray-900 text-gray-400 font-mono text-xs uppercase">
                                                <tr>
                                                    <th className="px-6 py-3">Severity</th>
                                                    <th className="px-6 py-3">Reason</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-800">
                                                {events.slice(0, 5).map(event => (
                                                    <tr key={event.event_id} className="hover:bg-gray-900/50 transition-colors">
                                                        <td className="px-6 py-4">
                                                            <span className={`px-2 py-1 rounded text-xs font-bold uppercase ${event.severity === 'critical' ? 'bg-red-900/30 text-red-400 border border-red-900' :
                                                                'bg-gray-800 text-gray-400'
                                                                }`}>
                                                                {event.severity}
                                                            </span>
                                                        </td>
                                                        <td className="px-6 py-4 text-sm text-gray-200">
                                                            {event.description}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div>
                            <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                                <Shield className="w-5 h-5 text-green-500" />
                                Capability Monitor (AEM)
                            </h2>
                            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 font-mono text-xs">
                                <div className="space-y-4">
                                    <CapabilityRow name="READ_LEDGER" granted={true} />
                                    <CapabilityRow name="WRITE_LEDGER" granted={true} />
                                    <CapabilityRow name="MINT_TOKEN" granted={false} />
                                    <CapabilityRow name="MESH_SYNC" granted={true} />
                                    <CapabilityRow name="EXECUTE_GOVERNANCE" granted={false} />
                                </div>
                                <div className="mt-6 pt-6 border-t border-gray-800 text-gray-500">
                                    JIT GRANTS ACTIVE: <span className="text-white">3</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </main>
            </div>
        </div>
    );
}

function CapabilityRow({ name, granted }: { name: string, granted: boolean }) {
    return (
        <div className="flex justify-between items-center">
            <span className={granted ? 'text-gray-300' : 'text-gray-600'}>{name}</span>
            <span className={granted ? 'text-green-500' : 'text-red-900'}>
                {granted ? '[GRANTED]' : '[LOCKED]'}
            </span>
        </div>
    );
}

function StatCard({ label, value, icon }: { label: string, value: number, icon: any }) {
    return (
        <div className="bg-gray-900 border border-gray-800 p-6 rounded-lg flex items-center justify-between">
            <div>
                <p className="text-gray-500 text-sm font-mono uppercase mb-1">{label}</p>
                <p className="text-3xl font-bold text-white font-mono">{value}</p>
            </div>
            <div className="p-3 bg-gray-800/50 rounded-lg">
                {icon}
            </div>
        </div>
    );
}
