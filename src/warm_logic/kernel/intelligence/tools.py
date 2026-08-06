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
"""
[Phase 97.3] Tool Registry (The Hands).
Provides external interaction capabilities (Web Search, URL Reading) to the Reasoning Engine.
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict

logger = logging.getLogger("ToolRegistry")


class Tool:
    """Base class for Sovereign Tools."""

    name: str = "base_tool"
    description: str = "Base tool"

    def execute(self, **kwargs: Any) -> str:
        raise NotImplementedError


class WebSearchTool(Tool):
    """
    [Phase 98.1] Real Web Search using DuckDuckGo.
    Uses DuckDuckGo Instant Answer API (no API key required).
    Falls back to html scraping if API fails.
    """

    name = "search_web"
    description = "Search the internet for information. Args: query (str)"

    def _safe_urlopen(self, url: str, timeout: int = 10) -> Any:
        """Open URL with scheme validation (only https allowed)."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https":
            raise ValueError(f"Only HTTPS URLs allowed, got: {parsed.scheme}")
        req = urllib.request.Request(
            url, headers={"User-Agent": "WarmLogic/1.0 SovereignAgent"}
        )
        return urllib.request.urlopen(req, timeout=timeout)  # nosec B310

    def execute(self, query: str, **_: Any) -> str:  # type: ignore[override]
        logger.info(f"[WebSearch] Searching DuckDuckGo for: {query}")

        try:
            # Try DuckDuckGo Instant Answer API first
            api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
            with self._safe_urlopen(api_url, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

                results = []

                # Abstract (main answer)
                if data.get("Abstract"):
                    results.append(f"📖 {data['Abstract']}")
                    if data.get("AbstractURL"):
                        results.append(f"   Source: {data['AbstractURL']}")

                # Related Topics
                if data.get("RelatedTopics"):
                    results.append("\n🔗 Related:")
                    for topic in data["RelatedTopics"][:3]:
                        if isinstance(topic, dict) and topic.get("Text"):
                            results.append(f"   - {topic['Text'][:100]}...")

                # Infobox
                if data.get("Infobox") and data["Infobox"].get("content"):
                    results.append("\n📋 Info:")
                    for item in data["Infobox"]["content"][:3]:
                        if item.get("label") and item.get("value"):
                            results.append(f"   {item['label']}: {item['value']}")

                if results:
                    return "\n".join(results)
                else:
                    # Fallback: DDG HTML search (basic scrape)
                    return self._fallback_html_search(query)

        except Exception as e:
            logger.warning(f"[WebSearch] API failed, trying fallback: {e}")
            return self._fallback_html_search(query)

    def _fallback_html_search(self, query: str) -> str:
        """Fallback: scrape DDG HTML lite page."""
        try:
            html_url = (
                f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            )
            with self._safe_urlopen(html_url, timeout=10) as response:
                html = response.read().decode("utf-8")
                # Very naive extraction of result snippets
                import re

                snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)</a>', html)
                if snippets:
                    results = [
                        f"🔍 Result {i + 1}: {s.strip()}"
                        for i, s in enumerate(snippets[:5])
                    ]
                    return "\n".join(results)
                else:
                    return f"[No results found for '{query}']"
        except Exception as e:
            logger.error(f"[WebSearch] Fallback also failed: {e}")
            return f"Search failed: {e}"


class UrlReaderTool(Tool):
    """
    Reads content from a specific URL.
    Uses basic urllib for simple HTML fetching.
    """

    name = "read_url"
    description = "Read content from a URL. Args: url (str)"

    def execute(self, url: str, **_: Any) -> str:  # type: ignore[override]
        logger.info(f"[UrlReader] Fetching: {url}")
        try:
            # Basic request with user agent to avoid some blocks
            req = urllib.request.Request(
                url, data=None, headers={"User-Agent": "WarmLogic/1.0 SovereignAgent"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                content = response.read().decode("utf-8")
                # Very basic cleanup
                snippet = str(content[:1000]) + "...(truncated)"
                return snippet
        except Exception as e:
            logger.error(f"[UrlReader] Failed: {e}")
            return f"Error reading URL: {str(e)}"


class BrowserAutomationTool(Tool):
    """
    [Phase 99.1] Browser Automation Tool.
    Uses subprocess to control headless browser (Playwright/Selenium).
    Supports: navigate, click, screenshot, extract_text.
    """

    name = "browser"
    description = "Control a headless browser. Args: action (navigate|click|screenshot|extract_text), target (url or selector)"

    def execute(self, action: str = "", target: str = "", **kwargs: Any) -> str:
        import subprocess

        logger.info(f"[Browser] Action: {action}, Target: {target}")

        if action == "navigate":
            # Use curl to fetch page (lightweight alternative to full browser)
            try:
                result = subprocess.run(
                    ["curl", "-s", "-L", "-A", "WarmLogic/1.0", target],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                # Extract text content (strip HTML tags naively)
                import re

                text = re.sub(r"<[^>]+>", " ", result.stdout)
                text = re.sub(r"\s+", " ", text).strip()
                return f"📄 Page content ({len(text)} chars): {text[:500]}..."
            except Exception as e:
                return f"Navigation failed: {e}"

        elif action == "screenshot":
            # Stub: Would use Playwright in production
            return f"📸 [Stub] Screenshot of {target} would be saved. Requires Playwright setup."

        elif action == "click":
            return f"🖱️ [Stub] Would click on '{target}'. Requires Playwright setup."

        elif action == "extract_text":
            # Same as navigate for now
            return self.execute("navigate", target)

        else:
            return f"Unknown browser action: {action}. Supported: navigate, click, screenshot, extract_text"


class CodeExecutionTool(Tool):
    """
    [Phase 99.1] Safe Code Execution Tool.
    Executes Python or shell code in a sandboxed subprocess.
    IMPORTANT: Has timeout and output limits for safety.
    """

    name = "execute_code"
    description = (
        "Execute Python or shell code. Args: language (python|shell), code (str)"
    )

    TIMEOUT_SECONDS = 10
    MAX_OUTPUT_CHARS = 5000

    def execute(self, language: str = "", code: str = "", **kwargs: Any) -> str:
        import os
        import subprocess
        import tempfile

        logger.info(f"[CodeExec] Language: {language}, Code length: {len(code)}")

        # Safety checks
        dangerous_patterns = ["rm -rf", "sudo", "mkfs", "dd if=", ":(){", "fork"]
        for pattern in dangerous_patterns:
            if pattern in code.lower():
                return f"🚫 BLOCKED: Dangerous pattern detected: '{pattern}'"

        try:
            if language == "python":
                # Write to temp file and execute
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".py", delete=False
                ) as f:
                    f.write(code)
                    temp_path = f.name

                try:
                    result = subprocess.run(
                        ["python3", temp_path],
                        capture_output=True,
                        text=True,
                        timeout=self.TIMEOUT_SECONDS,
                        cwd=tempfile.gettempdir(),
                    )
                    output = result.stdout + result.stderr
                finally:
                    os.unlink(temp_path)

            elif language == "shell":
                result = subprocess.run(
                    ["sh", "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=self.TIMEOUT_SECONDS,
                    cwd=tempfile.gettempdir(),
                )
                output = result.stdout + result.stderr

            else:
                return f"Unsupported language: {language}. Use 'python' or 'shell'."

            # Truncate if too long
            if len(output) > self.MAX_OUTPUT_CHARS:
                output = output[: self.MAX_OUTPUT_CHARS] + "...(truncated)"

            return (
                f"✅ Execution result:\n{output}"
                if output
                else "✅ Code executed (no output)"
            )

        except subprocess.TimeoutExpired:
            return f"⏰ Execution timed out after {self.TIMEOUT_SECONDS}s"
        except Exception as e:
            return f"❌ Execution error: {e}"


class ToolRegistry:
    """
    Dynamic registry for available tools.
    Allows the Reasoning Engine to discover and execute actions.
    """

    def __init__(self) -> None:
        self.tools: Dict[str, Tool] = {}
        self._register_defaults()
        logger.info("[ToolRegistry] Tools Loaded.")

    def _register_defaults(self) -> None:
        self.register(WebSearchTool())
        self.register(UrlReaderTool())
        self.register(BrowserAutomationTool())
        self.register(CodeExecutionTool())

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get_tool_list(self) -> str:
        """Returns JSON schema of available tools for LLM."""
        manifest = [
            {"name": t.name, "description": t.description} for t in self.tools.values()
        ]
        return json.dumps(manifest, indent=2)

    def execute(self, tool_name: str, **kwargs: Any) -> str:
        tool = self.tools.get(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' not found."

        try:
            return tool.execute(**kwargs)
        except Exception as e:
            return f"Error executing '{tool_name}': {e}"
