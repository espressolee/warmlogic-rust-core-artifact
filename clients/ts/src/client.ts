import { SovereignIdentity } from './identity';

export interface ProposalResponse {
    status: string;
    identity: string;
    signature: string;
    intent: any;
    pqc_model: string;
}

/**
 * SovereignClient for TypeScript
 * Polyglot entry point for the Sovereign Mesh.
 */
export class SovereignClient {
    private rpcUrl: string;
    public identity: SovereignIdentity | null = null;

    constructor(rpcUrl: string = "http://localhost:8000") {
        this.rpcUrl = rpcUrl;
    }

    /**
     * Initializes the client with a new or existing identity.
     */
    public async init(identity?: SovereignIdentity): Promise<void> {
        if (identity) {
            this.identity = identity;
        } else {
            this.identity = await SovereignIdentity.generate();
        }
        console.log(`Sovereign TS Session Initialized | ID: ${this.identity.id.substring(0, 16)}...`);
    }

    /**
     * Submits a signed proposal to the Sovereign Mesh.
     */
    public async submitProposal(action: string, params: any): Promise<ProposalResponse> {
        if (!this.identity) {
            throw new Error("Client not initialized. Call init() first.");
        }

        const intent = {
            action,
            params,
            timestamp: Date.now() / 1000,
            nonce: Math.random().toString(16).substring(2, 10)
        };

        const payload = JSON.stringify(intent);
        const signature = await this.identity.sign(payload);

        // MOCK: In a real mesh, we POST to the RPC gateway
        // const resp = await axios.post(`${this.rpcUrl}/submit`, { ... });

        return {
            status: "PROPOSED",
            identity: this.identity.id,
            signature: signature,
            intent: intent,
            pqc_model: "ML-DSA-65"
        };
    }
}
