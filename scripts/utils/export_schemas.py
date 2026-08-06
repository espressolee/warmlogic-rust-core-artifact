import json
import os
import sys

# Internal Mock Classes to replicate Rust structs for Schema Generation
# In a real pipeline, we would use `schemars` in Rust to export these automatically.
# Here we manually define them to satisfy the submission requirement.


def generate_schemas():
    schemas = {}

    schemas["Intent"] = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "action": {"type": "string"},
            "risk_score": {"type": "integer", "minimum": 0},
            "payload": {
                "type": "string",
                "contentMediaType": "application/octet-stream",
            },
        },
        "required": ["id", "action", "risk_score"],
    }

    schemas["Decision"] = {
        "oneOf": [
            {"type": "string", "const": "Allow"},
            {
                "type": "object",
                "properties": {
                    "Veto": {
                        "type": "object",
                        "properties": {"reason": {"type": "string"}},
                        "required": ["reason"],
                    }
                },
                "required": ["Veto"],
            },
        ]
    }

    schemas["AuditBlock"] = {
        "type": "object",
        "properties": {
            "timestamp": {"type": "integer"},
            "intent_id": {"type": "string"},
            "payload_hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "prev_root": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        },
        "required": ["timestamp", "intent_id", "payload_hash"],
    }

    # Save Schema File
    os.makedirs("spec/schema/audit", exist_ok=True)
    out_path = "spec/schema/audit/tee_run_bundle_v1.schema.json"
    with open(out_path, "w") as f:
        json.dump(schemas, f, indent=2)

    print(f"Schema exported to {out_path}")


if __name__ == "__main__":
    generate_schemas()
