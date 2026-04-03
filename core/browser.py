"""core/browser.py - Playwright Headless Browser Agent"""
import asyncio
import base64
from playwright.async_api import async_playwright, Page, Browser, Playwright
from core.vision import _get_bounding_box

class PlaywrightBrowserManager:
    def __init__(self):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._lock = asyncio.Lock()

    async def _ensure_page(self) -> Page:
        async with self._lock:
            if not self._playwright:
                self._playwright = await async_playwright().start()
            if not self._browser:
                # Use Chromium
                self._browser = await self._playwright.chromium.launch(headless=True)
            if not self._page:
                context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                self._page = await context.new_page()
            return self._page

    async def go(self, url: str) -> str:
        if not url.startswith("http"):
            url = f"https://{url}"
        page = await self._ensure_page()
        # Bevor wir neu laden, fangen wir Fehler elegant ab
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)  # Render buffer
        except Exception as e:
            return f"Fehler beim Laden von {url}: {e}"
            
        return await self.get_text()

    async def get_text(self) -> str:
        page = await self._ensure_page()
        try:
            text = await page.evaluate("document.body.innerText")
            if not text:
                return "Kein sichtbarer Text."
            if len(text) > 15000:
                text = text[:15000] + "\n\n... [Seiten-Text auf 15.000 Zeichen gekürzt]"
            return text
        except Exception as e:
            return f"Konnte Text nicht lesen: {e}"

    async def screenshot(self) -> str:
        page = await self._ensure_page()
        img_bytes = await page.screenshot(type="jpeg", quality=80)
        return base64.b64encode(img_bytes).decode("utf-8")

    async def click(self, target_description: str) -> str:
        page = await self._ensure_page()
        b64_img = await self.screenshot()
        
        coords = await _get_bounding_box(b64_img, target_description)
        if not coords or coords == "UNSURE":
             return f"Fehler: Objekt '{target_description}' nicht auf dem Browser-Bildschirm gefunden."
             
        y_min, x_min, y_max, x_max = coords
        center_y_norm = y_min + (y_max - y_min) / 2
        center_x_norm = x_min + (x_max - x_min) / 2
        
        viewport = page.viewport_size
        width = viewport["width"] if viewport else 1280
        height = viewport["height"] if viewport else 800
        
        abs_x = center_x_norm * width
        abs_y = center_y_norm * height
        
        await page.mouse.move(abs_x, abs_y)
        await page.mouse.click(abs_x, abs_y)
        await asyncio.sleep(2) 
        
        return "Klick erfolgreich ausgeführt."

    async def type_text(self, text: str) -> str:
        page = await self._ensure_page()
        await page.keyboard.type(text, delay=20)
        await asyncio.sleep(1)
        return f"Text '{text}' eingetippt."
        
    async def press(self, key: str) -> str:
        page = await self._ensure_page()
        await page.keyboard.press(key)
        await asyncio.sleep(1)
        return f"Taste '{key}' gedrückt."

# Singleton Instance
browser_manager = PlaywrightBrowserManager()
