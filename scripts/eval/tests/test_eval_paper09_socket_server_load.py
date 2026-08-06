import json
import os
import subprocess
from pathlib import Path


def test_socket_server_load_script_writes_json(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "eval" / "eval_paper09_socket_server_load.py"

    run_id = f"_test_socket_server_load_{os.getpid()}"
    out_dir = tmp_path / "out"

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    subprocess.check_call(
        [
            str(repo_root / ".venv" / "bin" / "python"),
            str(script),
            "--run-id",
            run_id,
            "--out-root",
            str(out_dir),
            "--repeats",
            "1",
            "--conns",
            "2",
            "--payload-bytes",
            "1024",
            "--warmup-msgs-per-conn",
            "1",
            "--msgs-per-conn",
            "3",
            "--rate-hz",
            "200.0",
            "--apis",
            "recv_only,set_bytesvec",
        ],
        cwd=str(repo_root),
        env=env,
    )

    out_path = out_dir / "bridge_eval" / run_id / "socket_server_load_telemetry.json"
    assert out_path.exists()

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "metadata" in payload
    assert "results" in payload
    assert {r["api"] for r in payload["results"]} == {"recv_only", "set_bytesvec"}
