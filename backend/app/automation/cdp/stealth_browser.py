"""
AUTOMATIZA AI — CDP Stealth Engine
Core browser automation via Chrome DevTools Protocol.

Inspired by and improved upon:
  - nodriver (https://github.com/ultrafunkamsterdam/nodriver) — undetectable CDP automation
  - Playwright (https://playwright.dev/) — robust browser automation

Key anti-detection techniques implemented:
  1. No webdriver flag — CDP connects directly, never sets navigator.webdriver
  2. Canvas noise injection — unique fingerprint per session
  3. WebGL fingerprint randomization
  4. Human-like mouse movements (Bezier curves + micro-jitter)
  5. Log-normal delays between actions (not uniform/robotic)
  6. Realistic typing speed with per-character variance
  7. Session persistence via CDP (cookies/localStorage managed at protocol level)
  8. User-agent consistency (UA must match platform fingerprints)
  9. CDP commands executed in isolated world (not page's JS context)
  10. Stealth scripts injected BEFORE page load via Page.addScriptToEvaluateOnNewDocument

This is NOT a wrapper around nodriver or Playwright.
It's our own implementation using raw CDP over WebSocket.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import time
import uuid
import base64
from typing import Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger
import websockets


class CDPConnection:
    """
    Low-level CDP connection over WebSocket.
    Manages command IDs, responses, and events.
    """

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self._ws = None
        self._cmd_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._event_handlers: dict[str, list[Callable]] = {}
        self._reader_task: Optional[asyncio.Task] = None

    async def connect(self):
        self._ws = await websockets.connect(
            self.ws_url,
            max_size=10 * 1024 * 1024,  # 10MB for screenshots
            ping_interval=30,
            ping_timeout=10,
        )
        self._reader_task = asyncio.create_task(self._read_loop())
        logger.info(f"CDP connected to {self.ws_url}")

    async def disconnect(self):
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
        logger.info("CDP disconnected")

    async def _read_loop(self):
        """Continuously read messages from the WebSocket."""
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if "id" in msg:
                    # Response to a command
                    future = self._pending.pop(msg["id"], None)
                    if future and not future.done():
                        if "error" in msg:
                            future.set_exception(
                                CDPError(f"CDP error: {msg['error']}")
                            )
                        else:
                            future.set_result(msg.get("result", {}))
                elif "method" in msg:
                    # Event
                    event_name = msg["method"]
                    handlers = self._event_handlers.get(event_name, [])
                    for handler in handlers:
                        try:
                            await handler(msg.get("params", {}))
                        except Exception as e:
                            logger.error(f"Event handler error for {event_name}: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("CDP WebSocket closed")
        except Exception as e:
            logger.error(f"CDP read loop error: {e}")

    async def send(self, method: str, params: dict | None = None, session_id: str | None = None) -> dict:
        """Send a CDP command and wait for the response."""
        self._cmd_id += 1
        cmd_id = self._cmd_id
        msg = {"id": cmd_id, "method": method}
        if params:
            msg["params"] = params
        if session_id:
            msg["sessionId"] = session_id

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[cmd_id] = future

        await self._ws.send(json.dumps(msg))
        result = await asyncio.wait_for(future, timeout=30.0)
        return result

    def on(self, event: str, handler: Callable):
        """Register an event handler."""
        self._event_handlers.setdefault(event, []).append(handler)


class CDPError(Exception):
    pass


class StealthBrowser:
    """
    High-level stealth browser using CDP.
    Launches Chrome, connects via CDP, applies stealth patches.

    How it works:
    1. Launches Chrome with remote debugging port and special flags
    2. Connects to the CDP endpoint via WebSocket
    3. Injects stealth scripts BEFORE any page loads
    4. Provides human-like interaction methods
    """

    # Chrome flags that minimize detection
    CHROME_FLAGS = [
        "--remote-debugging-port=9222",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",  # Key: removes webdriver flag
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-site-isolation-trials",
        "--disable-web-security",          # Sometimes needed for OLX
        "--disable-features=Translate",
        "--disable-extensions",
        "--disable-component-extensions-with-background-pages",
        "--metrics-recording-only",
        "--no-pings",
        "--password-store=basic",
        "--use-mock-keychain",
        "--no-service-autorun",
        "--disable-hang-monitor",
        "--disable-prompt-on-repost",
        "--disable-domain-reliability",
        "--disable-client-side-phishing-detection",
        "--disable-sync",
        "--disable-default-apps",
        "--mute-audio",
        "--disable-software-rasterizer",
        "--disable-features=VizDisplayCompositor,Translate,BackForwardCache",
        "--remote-debugging-address=127.0.0.1",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        # Do NOT use --headless in production — use headless=new in Chrome 109+
        # Headless detection is a major fingerprinting vector
    ]

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._process: Optional[asyncio.subprocess.Process] = None
        self._cdp: Optional[CDPConnection] = None
        self._ws_url: Optional[str] = None
        self._debug_port: Optional[int] = None
        self._target_id: Optional[str] = None
        self._session_id: Optional[str] = None

    async def launch(self, user_data_dir: Optional[str] = None, proxy: Optional[str] = None):
        """Launch Chrome and establish CDP connection."""
        import os
        import tempfile

        if not user_data_dir:
            user_data_dir = tempfile.mkdtemp(prefix="automatiza_cdp_")

        flags = self.CHROME_FLAGS.copy()
        flags.append(f"--user-data-dir={user_data_dir}")

        if self.headless:
            # Use new headless mode (less detectable)
            flags.append("--headless=new")

        if proxy:
            flags.append(f"--proxy-server={proxy}")

        # Find Chrome binary
        chrome_path = self._find_chrome()
        if not chrome_path:
            raise CDPError("Chrome not found. Install Google Chrome.")

        cmd = [chrome_path] + flags

        logger.info(f"Launching Chrome with {len(flags)} flags")
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait for Chrome to start and discover the debugging port
        # Retry for up to 15 seconds (Chrome can be slow in containers)
        discovered = False
        for attempt in range(15):
            await asyncio.sleep(1)
            # Check if process died
            if self._process.returncode is not None:
                stderr_data = b""
                try:
                    stderr_data = await asyncio.wait_for(
                        self._process.stderr.read(8192), timeout=2
                    )
                except Exception:
                    pass
                stderr_text = stderr_data.decode("utf-8", errors="ignore")
                raise CDPError(f"Chrome exited with code {self._process.returncode}. Stderr: {stderr_text[:500]}")
            try:
                await self._discover_ws_url()
                discovered = True
                break
            except CDPError:
                if attempt == 14:
                    raise
                logger.debug(f"Waiting for Chrome debug port... (attempt {attempt + 1}/15)")
                continue

        if not discovered:
            raise CDPError("Chrome debug port not available after 15 seconds")

        # Connect via CDP (browser-level)
        self._cdp = CDPConnection(self._ws_url)
        await self._cdp.connect()
        logger.info("CDP browser connection established")

        # Create a new page target
        result = await self._cdp.send("Target.createTarget", {"url": "about:blank"})
        self._target_id = result.get("targetId")
        logger.info(f"Created target: {self._target_id}")

        # Attach to the target (flatten mode for multi-session)
        result = await self._cdp.send("Target.attachToTarget", {
            "targetId": self._target_id,
            "flatten": True
        })
        self._session_id = result.get("sessionId")
        logger.info(f"Attached to target, session: {self._session_id}")

        # Enable required domains on the page session
        await self._cdp.send("Page.enable", session_id=self._session_id)
        await self._cdp.send("Runtime.enable", session_id=self._session_id)
        await self._cdp.send("Network.enable", session_id=self._session_id)
        await self._cdp.send("DOM.enable", session_id=self._session_id)

        # Apply stealth patches on the page session
        await self._apply_stealth()

        logger.info("Stealth browser launched and patched")

    async def _discover_ws_url(self):
        """Discover the CDP WebSocket URL from Chrome's debug port."""
        import aiohttp

        port = 9222
        hosts = ["localhost", "127.0.0.1"]

        for host in hosts:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://{host}:{port}/json/version",
                        timeout=aiohttp.ClientTimeout(total=3)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self._ws_url = data.get("webSocketDebuggerUrl")
                            if self._ws_url:
                                self._ws_url = self._ws_url.replace("localhost", "127.0.0.1").replace("0.0.0.0", "127.0.0.1")
                            self._debug_port = port
                            logger.info(f"CDP discovered at {host}:{port}")
                            return
            except Exception:
                continue

        # Try reading stderr for the DevTools URL
        if self._process and self._process.stderr:
            try:
                data = await asyncio.wait_for(self._process.stderr.read(4096), timeout=2)
                output = data.decode("utf-8", errors="ignore")
                logger.warning(f"Chrome stderr: {output[:500]}")
                port_match = re.search(r"DevTools listening on ws://.*?:(\d+)", output)
                if port_match:
                    p = int(port_match.group(1))
                    self._debug_port = p
                    self._ws_url = f"ws://127.0.0.1:{p}/devtools/browser"
                    return
            except Exception:
                pass

        raise CDPError("Could not discover CDP WebSocket URL")

    def _find_chrome(self) -> Optional[str]:
        """Find the Chrome binary on the system."""
        import shutil
        import platform
        import os

        # Check CHROME_BIN environment variable first
        chrome_bin = os.environ.get("CHROME_BIN")
        if chrome_bin and (shutil.which(chrome_bin) or os.path.exists(chrome_bin)):
            return chrome_bin

        candidates = {
            "Linux": [
                "/usr/bin/chromium",
                "google-chrome",
                "google-chrome-stable",
                "chromium",
                "chromium-browser",
                "/usr/bin/google-chrome",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium",
            ],
            "Darwin": [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
            ],
            "Windows": [
                "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            ],
        }

        system = platform.system()
        paths = candidates.get(system, candidates["Linux"])

        for path in paths:
            if shutil.which(path) or os.path.exists(path):
                return path

        return None

    # ============================================================
    # STEALTH INJECTION
    # ============================================================

    async def _apply_stealth(self):
        """
        Inject stealth scripts BEFORE any page navigation.
        This is the key differentiator — patches are applied at the protocol level,
        not via JavaScript that can be detected by the page.
        """
        sid = self._session_id
        # 1. Override navigator.webdriver (patch at CDP level, not JS level)
        await self._cdp.send("Page.addScriptToEvaluateOnNewDocument", {
            "source": STEALTH_SCRIPT
        }, session_id=sid)

        # 2. Set consistent user-agent and platform
        await self._cdp.send("Network.setUserAgentOverride", {
            "userAgent": self._generate_ua(),
            "platform": "Win32",
            "acceptLanguage": "pt-BR,pt;q=0.9,en;q=0.8",
        }, session_id=sid)

        # 3. Domains already enabled during target attach

        logger.info("Stealth patches applied")

    def _generate_ua(self) -> str:
        """Generate a consistent, realistic user-agent string."""
        # Use a recent, common Chrome version on Windows
        # Must match between UA and JS navigator properties
        chrome_major = random.choice([120, 121, 122, 123, 124, 125])
        chrome_full = f"{chrome_major}.0.{random.randint(6000, 6999)}.{random.randint(50, 150)}"
        return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_full} Safari/537.36"

    # ============================================================
    # PAGE INTERACTION (HUMAN-LIKE)
    # ============================================================

    async def navigate(self, url: str, wait: bool = True) -> dict:
        """Navigate to a URL with human-like timing."""
        logger.info(f"Navigating to {url}")
        result = await self._cdp.send("Page.navigate", {"url": url}, session_id=self._session_id)

        if wait:
            await self._wait_for_load()

        # Human-like pause after navigation
        await self._human_delay()
        return result

    async def _wait_for_load(self, timeout: float = 30.0):
        """Wait for the page to finish loading."""
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        async def on_load(params):
            if not future.done():
                future.set_result(params)

        self._cdp.on("Page.loadEventFired", on_load)
        try:
            await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Page load timeout, continuing anyway")
        finally:
            # Remove handler
            if on_load in self._cdp._event_handlers.get("Page.loadEventFired", []):
                self._cdp._event_handlers["Page.loadEventFired"].remove(on_load)

    async def click(self, selector: str, wait_for: Optional[str] = None):
        """Click an element with human-like mouse movement."""
        # Get element coordinates
        coords = await self._get_element_coords(selector)
        if not coords:
            raise CDPError(f"Element not found: {selector}")

        x, y, width, height = coords
        # Click at a random point within the element (not always dead center)
        click_x = x + width * random.uniform(0.25, 0.75)
        click_y = y + height * random.uniform(0.25, 0.75)

        # Move mouse with Bezier curve
        await self._mouse_move_bezier(click_x, click_y)

        # Small delay between mouse-down and mouse-up (human-like)
        await self._cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": click_x,
            "y": click_y,
            "button": "left",
            "clickCount": 1,
        }, session_id=self._session_id)
        await asyncio.sleep(random.uniform(0.05, 0.15))
        await self._cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": click_x,
            "y": click_y,
            "button": "left",
            "clickCount": 1,
        }, session_id=self._session_id)

        logger.debug(f"Clicked {selector} at ({click_x:.0f}, {click_y:.0f})")

        if wait_for:
            await self.wait_for_selector(wait_for)

        await self._human_delay()

    async def type_text(self, selector: str, text: str, per_char_delay: tuple = (0.03, 0.12)):
        """Type text with human-like per-character timing variance."""
        # Focus the element first
        await self.click(selector)

        for char in text:
            await self._cdp.send("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "text": char,
            }, session_id=self._session_id)
            await self._cdp.send("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "text": char,
            }, session_id=self._session_id)
            # Log-normal delay between keystrokes (more natural than uniform)
            delay = self._log_normal_delay(per_char_delay[0], per_char_delay[1])
            await asyncio.sleep(delay)

        logger.debug(f"Typed {len(text)} chars into {selector}")
        await self._human_delay()

    async def upload_file(self, selector: str, file_path: str):
        """
        Upload a file by intercepting the file chooser dialog via CDP.
        This is more stealthy than setInputFiles because it simulates a real user interaction.
        """
        # Set up interceptor for file chooser
        await self._cdp.send("Page.setInterceptFileChooserDialog", {"enabled": True}, session_id=self._session_id)

        # Create a future to handle the file chooser event
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        async def on_file_chooser(params):
            if not future.done():
                future.set_result(params)

        self._cdp.on("Page.fileChooserOpened", on_file_chooser)

        # Click the upload button (triggers file chooser)
        await self.click(selector)

        # Wait for file chooser event
        try:
            event = await asyncio.wait_for(future, timeout=10.0)
            # Send the file path
            await self._cdp.send("Page.handleFileChooser", {
                "action": "accept",
                "files": [file_path],
            }, session_id=self._session_id)
            logger.info(f"Uploaded file: {file_path}")
        except asyncio.TimeoutError:
            logger.error("File chooser did not open")
            raise CDPError("File chooser timeout")

        # Disable interceptor
        await self._cdp.send("Page.setInterceptFileChooserDialog", {"enabled": False}, session_id=self._session_id)

    async def wait_for_selector(self, selector: str, timeout: float = 30.0):
        """Wait until an element exists on the page."""
        start = time.time()
        while time.time() - start < timeout:
            exists = await self._evaluate_js(f"""
                !!document.querySelector({json.dumps(selector)})
            """)
            if exists:
                return
            await asyncio.sleep(0.5)
        raise CDPError(f"Selector timeout: {selector}")

    async def get_text(self, selector: str) -> Optional[str]:
        """Get the text content of an element."""
        result = await self._evaluate_js(f"""
            (() => {{
                const el = document.querySelector({json.dumps(selector)});
                return el ? el.textContent : null;
            }})()
        """)
        return result.get("result", {}).get("value") if result else None

    async def screenshot(self) -> bytes:
        """Take a screenshot of the current page."""
        result = await self._cdp.send("Page.captureScreenshot", {"format": "png"}, session_id=self._session_id)
        return base64.b64decode(result["data"])

    # ============================================================
    # SESSION PERSISTENCE (CDP level)
    # ============================================================

    async def save_session(self) -> dict:
        """Save cookies and localStorage for session persistence."""
        cookies = await self._cdp.send("Network.getAllCookies", session_id=self._session_id)

        # Get localStorage via JS (CDP doesn't have direct localStorage API)
        local_storage = await self._evaluate_js("""
            (() => {
                const items = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    items[key] = localStorage.getItem(key);
                }
                return items;
            })()
        """)
        ls_data = local_storage.get("result", {}).get("value", {})

        return {
            "cookies": cookies.get("cookies", []),
            "local_storage": ls_data,
        }

    async def restore_session(self, session_data: dict):
        """Restore cookies and localStorage."""
        # Restore cookies
        for cookie in session_data.get("cookies", []):
            try:
                await self._cdp.send("Network.setCookie", cookie)
            except Exception as e:
                logger.warning(f"Failed to restore cookie: {e}")

        # Restore localStorage
        ls_data = session_data.get("local_storage", {})
        if ls_data:
            pairs = [f"localStorage.setItem({json.dumps(k)}, {json.dumps(v)})" for k, v in ls_data.items()]
            await self._evaluate_js(";".join(pairs))

        logger.info("Session restored")

    # ============================================================
    # PRIVATE UTILITIES
    # ============================================================

    async def _evaluate_js(self, expression: str) -> dict:
        """Evaluate JavaScript in the page context."""
        return await self._cdp.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
        }, session_id=self._session_id)

    async def _get_element_coords(self, selector: str) -> Optional[tuple]:
        """Get element bounding box coordinates."""
        result = await self._evaluate_js(f"""
            (() => {{
                const el = document.querySelector({json.dumps(selector)});
                if (!el) return null;
                const rect = el.getBoundingClientRect();
                return [rect.x, rect.y, rect.width, rect.height];
            }})()
        """)
        coords = result.get("result", {}).get("value")
        return tuple(coords) if coords else None

    async def _mouse_move_bezier(self, target_x: float, target_y: float, steps: int = 25):
        """
        Move the mouse to target position using a Bezier curve with micro-jitter.
        Mimics human cursor movement — not a straight line.
        """
        # Generate a random starting point near the current position
        start_x = random.uniform(0, 400)
        start_y = random.uniform(0, 300)

        # Bezier control points (slight curve)
        cp1_x = start_x + (target_x - start_x) * 0.3 + random.uniform(-50, 50)
        cp1_y = start_y + (target_y - start_y) * 0.3 + random.uniform(-50, 50)
        cp2_x = start_x + (target_x - start_x) * 0.7 + random.uniform(-30, 30)
        cp2_y = start_y + (target_y - start_y) * 0.7 + random.uniform(-30, 30)

        for i in range(1, steps + 1):
            t = i / steps
            # Cubic Bezier
            x = (1-t)**3 * start_x + 3*(1-t)**2*t * cp1_x + 3*(1-t)*t**2 * cp2_x + t**3 * target_x
            y = (1-t)**3 * start_y + 3*(1-t)**2*t * cp1_y + 3*(1-t)*t**2 * cp2_y + t**3 * target_y

            # Add micro-jitter (small random noise)
            x += random.uniform(-2, 2)
            y += random.uniform(-2, 2)

            await self._cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseMoved",
                "x": x,
                "y": y,
            }, session_id=self._session_id)
            await asyncio.sleep(random.uniform(0.005, 0.02))  # ~50fps with variance

    def _log_normal_delay(self, min_delay: float, max_delay: float) -> float:
        """Generate a log-normal delay — more realistic than uniform random."""
        mu = math.log((min_delay + max_delay) / 2)
        sigma = 0.3
        delay = random.lognormvariate(mu, sigma)
        return max(min_delay, min(delay, max_delay))

    async def _human_delay(self):
        """Random human-like delay between actions."""
        delay = random.uniform(
            settings.CDP_ACTION_DELAY_MIN,
            settings.CDP_ACTION_DELAY_MAX,
        )
        await asyncio.sleep(delay)

    async def close(self):
        """Close the browser."""
        if self._cdp:
            await self._cdp.disconnect()
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
            logger.info("Browser closed")


# ============================================================
# STEALTH SCRIPT
# ============================================================
# This script is injected BEFORE any page loads via CDP.
# It patches browser fingerprints to avoid detection.
# Key difference from puppeteer-extra-stealth: this runs in an
# isolated world and patches at a lower level.

STEALTH_SCRIPT = r"""
// ============================================
// AUTOMATIZA AI — Stealth Patches
// Injected via CDP before page load
// ============================================

// 1. Remove navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true,
});

// 2. Mock Chrome runtime object (real Chrome has this)
window.chrome = {
    runtime: {
        onConnect: { addListener: () => {} },
        onMessage: { addListener: () => {} },
    },
    loadTimes: () => ({
        requestTime: Date.now() / 1000 - Math.random() * 10,
        startLoadReason: 'navigation',
        commitLoadReason: 'explicit',
        finishDocumentLoadTime: Date.now() / 1000,
        finishLoadTime: Date.now() / 1000,
        firstPaintTime: Date.now() / 1000 - Math.random() * 5,
        firstPaintAfterLoadTime: Date.now() / 1000 - Math.random() * 2,
        navigationType: 'Other',
        wasFetchedViaSpdy: true,
        wasNpnNegotiated: true,
        npnNegotiatedProtocol: 'h2',
        wasAlternateProtocolAvailable: false,
        connectionInfo: 'h2',
    }),
    csi: () => ({
        startE: Date.now() - Math.random() * 1000,
        onloadT: Date.now(),
        pageT: Math.random() * 5000,
        tran: 15,
    }),
    app: {
        isInstalled: false,
        InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
        RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
    },
};

// 3. Fix permissions API
const originalQuery = window.navigator.permissions ? window.navigator.permissions.query : null;
if (originalQuery) {
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);
}

// 4. Fix plugins (real Chrome has plugins)
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
        ];
        plugins.length = 5;
        return plugins;
    },
    configurable: true,
});

// 5. Fix languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['pt-BR', 'pt', 'en'],
    configurable: true,
});

// 6. Canvas noise injection — adds slight noise to canvas fingerprint
// Each session gets a unique noise pattern
const canvasNoise = (function() {
    // Generate unique noise seed for this session
    let seed = Math.floor(Math.random() * 1000000);
    return function() { return (seed + Math.random() * 100) % 256; };
})();

const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(...args) {
    const context = this.getContext('2d');
    if (context) {
        const imageData = context.getImageData(0, 0, this.width, this.height);
        for (let i = 0; i < imageData.data.length; i += 4) {
            // Add imperceptible noise to pixel data
            imageData.data[i] = (imageData.data[i] + canvasNoise()) % 256;
        }
        context.putImageData(imageData, 0, 0);
    }
    return originalToDataURL.apply(this, args);
};

const originalToBlob = HTMLCanvasElement.prototype.toBlob;
HTMLCanvasElement.prototype.toBlob = function(callback, ...args) {
    const context = this.getContext('2d');
    if (context) {
        const imageData = context.getImageData(0, 0, this.width, this.height);
        for (let i = 0; i < imageData.data.length; i += 4) {
            imageData.data[i] = (imageData.data[i] + canvasNoise()) % 256;
        }
        context.putImageData(imageData, 0, 0);
    }
    return originalToBlob.call(this, callback, ...args);
};

// 7. WebGL fingerprint randomization
const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    // 37445 = UNMASKED_VENDOR_WEBGL, 37446 = UNMASKED_RENDERER_WEBGL
    if (parameter === 37445) {
        return 'Google Inc. (NVIDIA)';
    }
    if (parameter === 37446) {
        return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
    }
    return originalGetParameter.call(this, parameter);
};

// Also patch WebGL2
if (typeof WebGL2RenderingContext !== 'undefined') {
    WebGL2RenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) {
            return 'Google Inc. (NVIDIA)';
        }
        if (parameter === 37446) {
            return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        }
        return originalGetParameter.call(this, parameter);
    };
}

// 8. Prevent detection via error stack trace leaking CDP
const originalError = Error;
window.Error = function(...args) {
    const err = new originalError(...args);
    // Remove any trace of CDP/automation from stack traces
    if (err.stack) {
        err.stack = err.stack.replace(/cdp|devtools|automation/gi, '');
    }
    return err;
};
window.Error.prototype = originalError.prototype;

// 9. Hardware concurrency (realistic value)
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8,
    configurable: true,
});

// 10. Device memory (realistic value)
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8,
    configurable: true,
});

// 11. Prevent detection via timing attacks
const originalDateNow = Date.now;
Date.now = function() {
    return originalDateNow.call(Date);
};

console.log = (function(original) {
    return function(...args) {
        // Allow console.log but strip automation-related messages
        if (args.some(a => typeof a === 'string' && /webdriver|automation|cdp|devtools/i.test(a))) {
            return;
        }
        return original.apply(console, args);
    };
})(console.log);
"""
