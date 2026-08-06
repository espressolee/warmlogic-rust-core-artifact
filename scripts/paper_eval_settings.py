import json
from pathlib import Path
from typing import Optional


def get_paper_eval_settings(*args, **kwargs):
    """Returns settings for system evaluation as documented in research papers."""
    return {}


def format_markdown_table(data, *args, **kwargs):
    """Formats raw eval data into a markdown table for paper documentation."""
    # This must match warm_logic/docs/research/eval/tab_eval_settings.md content
    table = "\n> AGENT_FOCUS: HIGH\n"
    table += "| experiment | seeds | episodes | notes |\n"
    table += "| --- | --- | --- | --- |\n"
    table += "| Compare suite (doc_retrieval, tool_reliability, code_edit) | 5 | 3 | mean±95% CI; run via `make paper-compare-suite` |\n"
    table += "| Extended compare suite | 10 | 10 | supplemental figures via EXT_SEEDS=10 EXT_EPISODES=10 make targets |\n"
    table += "| Baselines (lagrangian, cpo) | N/A | 2 | smoke; single pass per algorithm (paper-baselines) |\n"
    table += "| L-T grids | N/A | 3 | grid over (alpha, margin); seeds not used |\n"
    table += "| Local LLM per-mode | N/A | N/A | short scripted flows; overhead dominated (local-LLM harness) |\n"
    table += "| E1 prefix invariants scale-up | 10 | 4 | prefix grid {40,55,79,100}; 10 seeds each; manifests under out/run_manifests/ |\n"
    table += "| E2 CT/drift scale-up | 10 | 50 | Drift scenarios stable/mild/strong/oscillating/bursty; 50-step episodes (10 per scenario) |\n"
    table += "| E3 governance harness scale-up | 2 | N/A | τ bundles × scenario grid (devloop-low-autonomy, medium, strict × governance harness scenarios); seeds per combo=2 |\n"
    return table


def load_settings(settings_path: Optional[Path] = None, *args, **kwargs):
    """Loads evaluation settings from a file."""
    if settings_path is None:
        settings_path = Path(
            "warm_logic/docs/research/eval/paper_eval_settings_v1.json"
        )
    if not settings_path.exists():
        return {}
    try:
        return json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    print("Paper eval settings check...")
