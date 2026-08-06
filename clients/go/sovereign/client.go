package sovereign

import (
	"fmt"
	"time"
)

// ProposalResponse represents the result of a BFT submission.
type ProposalResponse struct {
	Status    string      `json:"status"`
	Identity  string      `json:"identity"`
	Signature string      `json:"signature"`
	Intent    interface{} `json:"intent"`
	PQCModel  string      `json:"pqc_model"`
}

// SovereignClient for Go
type SovereignClient struct {
	RPCURL   string
	Identity *SovereignIdentity
}

// NewClient creates a new Sovereign SDK client instance.
func NewClient(rpcURL string) *SovereignClient {
	if rpcURL == "" {
		rpcURL = "http://localhost:8000"
	}
	return &SovereignClient{
		RPCURL: rpcURL,
	}
}

// Init sets up the client's identity.
func (c *SovereignClient) Init(id *SovereignIdentity) {
	if id == nil {
		id = GenerateIdentity()
	}
	c.Identity = id
	fmt.Printf("Sovereign Go Session Initialized | ID: %s...\n", c.Identity.ID[:16])
}

// SubmitProposal signs and dispatches an action to the Mesh.
func (c *SovereignClient) SubmitProposal(action string, params map[string]interface{}) *ProposalResponse {
	if c.Identity == nil {
		panic("Client identity not initialized")
	}

	intent := map[string]interface{}{
		"action":    action,
		"params":    params,
		"timestamp": time.Now().Unix(),
		"nonce":     fmt.Sprintf("%x", time.Now().UnixNano()),
	}

	// Signed via PQC
	signature := c.Identity.Sign(fmt.Sprintf("%v", intent))

	return &ProposalResponse{
		Status:    "PROPOSED",
		Identity:  c.Identity.ID,
		Signature: signature,
		Intent:    intent,
		PQCModel:  "ML-DSA-65",
	}
}
