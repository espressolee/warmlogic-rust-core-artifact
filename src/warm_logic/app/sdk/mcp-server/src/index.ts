#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
    CallToolRequestSchema,
    ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import fs from "fs";
import { fileURLToPath } from "url";
import path from "path";
import Ajv from "ajv";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ajv = new Ajv();
const PACKS_ROOT = path.resolve(__dirname, "../../../../packs");

interface Pack {
    name: string;
    schema?: any;
}

class WarmLogicServer {
    private server: Server;
    private packs: Map<string, Pack> = new Map();

    constructor() {
        this.server = new Server(
            {
                name: "warmlogic-mcp-server",
                version: "1.0.0",
            },
            {
                capabilities: {
                    tools: {},
                },
            }
        );

        this.loadPacks();
        this.setupHandlers();

        // Error handling
        this.server.onerror = (error) => console.error("[MCP Error]", error);
        process.on("SIGINT", async () => {
            await this.server.close();
            process.exit(0);
        });
    }

    private loadPacks() {
        if (!fs.existsSync(PACKS_ROOT)) {
            console.warn(`[Warn] Packs root not found: ${PACKS_ROOT}`);
            return;
        }

        const entries = fs.readdirSync(PACKS_ROOT, { withFileTypes: true });
        for (const entry of entries) {
            if (entry.isDirectory()) {
                const packName = entry.name;
                const schemaPath = path.join(PACKS_ROOT, packName, "evidence_schema.json");

                let schema = undefined;
                if (fs.existsSync(schemaPath)) {
                    try {
                        schema = JSON.parse(fs.readFileSync(schemaPath, "utf-8"));
                    } catch (e) {
                        console.error(`[Error] Failed to load schema for ${packName}: ${e}`);
                    }
                }

                this.packs.set(packName, { name: packName, schema });
            }
        }
    }

    private setupHandlers() {
        this.server.setRequestHandler(ListToolsRequestSchema, async () => {
            return {
                tools: [
                    {
                        name: "check_veto",
                        description: "Validate if an action is allowed by WarmLogic Vertical Packs based on provided evidence.",
                        inputSchema: {
                            type: "object",
                            properties: {
                                action: {
                                    type: "string",
                                    description: "The action to perform (e.g., limit_change, k8s_delete)",
                                },
                                evidence: {
                                    type: "object",
                                    description: "The JSON evidence object containing approvals or tokens.",
                                },
                            },
                            required: ["action", "evidence"],
                        },
                    },
                ],
            };
        });

        this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
            if (request.params.name !== "check_veto") {
                throw new Error("Unknown tool");
            }

            const { action, evidence } = request.params.arguments as any;

            // Determine target pack (Simple Heuristic same as Python implementation)
            let targetPack = "";
            if (["limit_change", "account_freeze"].includes(action)) targetPack = "finance";
            if (["k8s_delete", "db_drop_table", "breakglass"].includes(action)) targetPack = "ops";

            if (!this.packs.has(targetPack)) {
                // If no pack matches, default to Allow (Soft Fail) or error depending on policy.
                // For MCP, we'll return implicit allow if no governance applies.
                return {
                    content: [
                        {
                            type: "text",
                            text: JSON.stringify({ allowed: true, reason: "no_governance_policy_found" }),
                        },
                    ],
                };
            }

            const pack = this.packs.get(targetPack)!;

            // 1. Schema Validation
            if (pack.schema) {
                const validate = ajv.compile(pack.schema);
                const valid = validate(evidence);
                if (!valid) {
                    const errors = validate.errors?.map(e => `${e.instancePath} ${e.message}`).join(", ");
                    return {
                        content: [{ type: "text", text: JSON.stringify({ allowed: false, reason: `Schema Violation: ${errors}` }) }],
                        isError: true,
                    };
                }
            }

            // 2. Logic Validation (Simple Re-impl)
            if (targetPack === "ops" && evidence.operation_type === "breakglass") {
                if (!evidence.breakglass_token?.approved_by) {
                    return {
                        content: [{ type: "text", text: JSON.stringify({ allowed: false, reason: "Breakglass token requires approval" }) }],
                        isError: true,
                    };
                }
            }

            return {
                content: [
                    {
                        type: "text",
                        text: JSON.stringify({ allowed: true, reason: "validated_by_warmlogic" }),
                    },
                ],
            };
        });
    }

    async run() {
        const transport = new StdioServerTransport();
        await this.server.connect(transport);
        console.error("WarmLogic MCP Server running on stdio");
    }
}

const server = new WarmLogicServer();
server.run().catch(console.error);
