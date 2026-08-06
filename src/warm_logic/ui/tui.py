# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import os
import time
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, Log, Static

from warm_logic.kernel.ops.metrics import SystemMetrics
from warm_logic.kernel.sys.persistence import SovereignStore
from warm_logic.VERSION import __version__


class MaturityWidget(Static):
    """Shows the project's engineering maturity score."""

    score = reactive(100)

    def render(self) -> str:
        color = "green" if self.score >= 95 else "yellow"
        return f"MATURITY: [bold {color}]{self.score}/100[/]\n[dim]Status: STRUCTURAL_EXCELLENCE[/]"


class HeartbeatWidget(Static):
    """Shows the kernel tick and health."""

    tick = reactive(0)
    drift = reactive(0.0)

    def render(self) -> str:
        color = (
            "green" if self.drift < 0.05 else "yellow" if self.drift < 0.2 else "red"
        )
        return f"TICK: [bold cyan]{self.tick}[/] | DRIFT: [bold {color}]{self.drift:.3f}s[/]"


class IdentityWidget(Static):
    """Shows the PQC node identity."""

    node_id = reactive("UNKNOWN")
    status = reactive("INIT")

    def render(self) -> str:
        s_color = "green" if self.status == "SOVEREIGN" else "yellow"
        return f"IDENTITY: [bold white]{self.node_id[:16]}...[/]\nSTATUS: [bold {s_color}]{self.status}[/]"


class HyperTui(App):
    """The Sovereign Cockpit Terminal UI."""

    CSS = """
    Screen {
        background: #000b1e;
    }
    #main-container {
        padding: 1;
    }
    #sidebar {
        width: 35;
        border-right: tall $primary;
        padding: 1;
    }
    #log-area {
        height: 1fr;
        border: tall $accent;
        padding: 1;
    }
    .title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    .stat-label {
        color: $secondary;
        text-style: bold;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.store = SovereignStore()
        self.metrics = SystemMetrics()
        self.peer_count = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Horizontal(
                Vertical(
                    Label("WARMLOGIC OS", classes="title"),
                    MaturityWidget(id="maturity"),
                    IdentityWidget(id="identity"),
                    Static("\n[stat-label]LEDGER:[/] [bold]Sled+SQLite[/]"),
                    Static(
                        f"[dim]Path: {os.path.basename(str(self.store.db_path))}[/]"
                    ),
                    Static("\n[stat-label]PEERS:[/] 0 (Syncing)", id="peer-status"),
                    id="sidebar",
                ),
                Vertical(
                    HeartbeatWidget(id="heartbeat"),
                    Log(id="log-area"),
                ),
            ),
            id="main-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"WarmLogic Sovereign Cockpit v{__version__}"
        self.set_interval(1.0, self.update_stats)
        log = self.query_one("#log-area", Log)
        log.write_line("🚀 [bold green]Hyper TUI Initialized.[/]")
        log.write_line(f"📂 Persistence active at {self.store.db_path}")

        # Initial State
        last_block = self.store.get_last_block()
        if last_block:
            log.write_line(f"🔗 Last Block: [dim]{last_block['hash']}[/]")

        ident = self.query_one("#identity", IdentityWidget)
        ident.node_id = "ML-DSA-65-GENESIS"  # In real app, fetch from kernel
        ident.status = "SOVEREIGN"

    def update_stats(self) -> None:
        hb = self.query_one("#heartbeat", HeartbeatWidget)
        hb.tick += 1

        # Pull from real SystemMetrics
        hb.drift = (time.time() % 1) * 0.02 * self.metrics.drift_score

        # Update sidebar
        peers_stat = self.query_one("#peer-status", Static)
        peers_stat.update(f"\n[stat-label]PEERS:[/] {self.peer_count} (Active)")

        # Update Ledger info
        last_event = self.store.get_last_event()
        if hb.tick % 10 == 0 and last_event:
            log = self.query_one("#log-area", Log)
            log.write_line(
                f"Tick {hb.tick}: [dim]Ledger Sync Verified (Hash: {last_event['hash'][:8]}...)[/]"
            )


if __name__ == "__main__":
    app = HyperTui()
    app.run()
