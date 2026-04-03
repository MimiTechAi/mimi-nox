"""
◑ MiMi Nox – Vision & Computer Use
core/vision.py

Führt Screenshots und PyAutoGUI-Klicks/-Type Befehle aus.
Nutzbar durch den Agenten.
"""
import base64
import json
import logging
import asyncio
from pathlib import Path

try:
    import mss
    import pyautogui
    from PIL import Image
except ImportError:
    mss = None
    pyautogui = None
    Image = None

import ollama

# ===========================================================================
# Sandbox Exceptions
# ===========================================================================
class SandboxConfirmationRequired(Exception):
    def __init__(self, tool_name: str, args: dict):
        self.tool_name = tool_name
        self.args = args
        super().__init__(f"Sandbox Bestätigung erforderlich für: {tool_name}")

# ===========================================================================
# Internals
# ===========================================================================

def _take_screenshot() -> str:
    """Takes a screenshot using mss and returns it as base64."""
    if mss is None:
        raise RuntimeError("mss Bibliothek nicht installiert.")
    
    with mss.mss() as sct:
        # Monitor 1 (Main)
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        
        # Convert to PIL Image to compress/save to base64
        # MSS returns BGRA. PIL reads mode RGB from 'raw' if we specify BGRX
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
        from io import BytesIO
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


async def _get_bounding_box(b64_image: str, target: str, reference_crop_b64: str | None = None) -> tuple[float, float, float, float] | str | None:
    """
    Fragt Llama 3.2 Vision nach der Bounding Box des Elements.
    Gilt Regel 1: Wenn unsicher, returniert er "UNSURE".
    Gibt es Memory-Erfahrung, wird der referenzierende Crop zur Verfügung gestellt.
    """
    system_prompt = (
        f"Finde das UI-Element '{target}' auf diesem Bild. "
        "Wenn du dir zu unter 95% sicher bist, wo der Button ist, oder wenn es mehrere identische Buttons gibt, "
        "antworte AUSSCHLIESSLICH mit dem Wort 'UNSURE'.\n"
        "Andernfalls gib mir exakt die normierten Bounding-Box-Koordinaten [y_min, x_min, y_max, x_max] "
        "im Format 0.0 bis 1.0 als strict JSON Array zurück. Gib absolut keinen anderen Text aus."
    )
    
    if reference_crop_b64:
        system_prompt += "\nDu hast ein Referenz-Bild für dieses Element erhalten (Bild 2). Nutze es, um die exakte Variante auf Bild 1 zu finden."
    
    images = [b64_image]
    if reference_crop_b64:
        images.append(reference_crop_b64)
    
    import os
    client = ollama.AsyncClient()
    try:
        response = await client.generate(
            model=os.environ.get("MIMI_NOX_VISION_MODEL", os.environ.get("MIMI_NOX_MODEL", "gemma4:e4b")),
            prompt=system_prompt,
            images=images,
            options={"temperature": 0.0}
        )
        
        txt = response["response"].strip()
        if "UNSURE" in txt:
            return "UNSURE"
            
        if txt.startswith("```json"):
            txt = txt.replace("```json", "").replace("```", "").strip()
        elif txt.startswith("```"):
            txt = txt.replace("```", "").strip()
            
        coords = json.loads(txt)
        if isinstance(coords, list) and len(coords) == 4:
            return (float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3]))
        return None
    except Exception as e:
        import logging
        logging.error(f"Vision Parsing Error: {e}")
        raise RuntimeError(f"Lokales Vision Modell nicht bereit oder überlastet: {e}")
        
def _crop_around(b64_image: str, x: int, y: int, size: int = 50) -> str:
    """Erstellt einen 50x50 Bildausschnitt mit OS-Boundary-Padding (Schwarze Pixel)."""
    from PIL import Image
    from io import BytesIO
    
    img_data = base64.b64decode(b64_image)
    img = Image.open(BytesIO(img_data)).convert("RGB")
    width, height = img.size
    
    half = size // 2
    left, top, right, bottom = x - half, y - half, x + half, y + half
    
    cropped = Image.new("RGB", (size, size), (0, 0, 0))
    
    src_left = max(0, left)
    src_top = max(0, top)
    src_right = min(width, right)
    src_bottom = min(height, bottom)
    
    if src_left < src_right and src_top < src_bottom:
        crop_actual = img.crop((src_left, src_top, src_right, src_bottom))
        paste_x = src_left - left
        paste_y = src_top - top
        cropped.paste(crop_actual, (paste_x, paste_y))
        
    buf = BytesIO()
    cropped.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

async def _capture_user_click() -> tuple[int, int]:
    """Sicherer Mouselistener, wirft sich nach erstem Mausklick sofort weg."""
    import pynput
    click_pos = [0, 0]
    ev = asyncio.Event()
    loop = asyncio.get_running_loop()

    def on_click(x, y, button, pressed):
        if pressed and button == pynput.mouse.Button.left:
            click_pos[0], click_pos[1] = int(x), int(y)
            loop.call_soon_threadsafe(ev.set)
            return False # Beendet den Listener sofort
            
    def start_listener():
        with pynput.mouse.Listener(on_click=on_click) as listener:
            listener.join()
            
    await asyncio.to_thread(start_listener)
    await ev.wait()
    return click_pos[0], click_pos[1]


# ===========================================================================
# Tools
# ===========================================================================

# Callback for the TUI / UI to pause and ask for permission
ON_SANDBOX_CONFIRM = None
ON_VISION_LEARNING = None
ON_VISION_LEARNED_SUCCESS = None

async def check_sandbox(tool_name: str, args: dict):
    from os import environ
    # autonomous_mode bypasses confirmation
    is_autonomous = environ.get("MIMI_NOX_AUTONOMOUS_MODE", "0") == "1"
    
    if not is_autonomous:
        if ON_SANDBOX_CONFIRM:
            approved = await ON_SANDBOX_CONFIRM(tool_name, args)
            if not approved:
                raise Exception("Action aborted by User Intervention")
        else:
            raise SandboxConfirmationRequired(tool_name, args)


async def vision_click(target_description: str) -> str:
    """Sucht ein UI Element auf dem primären Monitor und klickt es physisch an."""
    if pyautogui is None or mss is None or Image is None:
        return "[Error: GUI Automation Dependencies (PyAutoGUI, mss, Pillow) sind nicht vollständig importiert.]"

    # 1. BDD Regel: Bestätigung abwarten falls Sandbox an
    await check_sandbox("vision_click", {"target_description": target_description})
    
    # 2. Memory Abfrage
    from core.vision_memory import find_vision_rule, save_vision_rule
    ref_rule = find_vision_rule(target_description)
    ref_b64 =  ref_rule["base64_crop"] if ref_rule else None

    # 3. Screenshot & Modell-Inferenz
    b64_img = await asyncio.to_thread(_take_screenshot)
    coords = await _get_bounding_box(b64_img, target_description, ref_b64)
    
    # 4. BDD Regel 1: Zero-Guessing Policy (HITL Fallback)
    if coords == "UNSURE":
        if ON_VISION_LEARNING:
            await ON_VISION_LEARNING(target_description)
            
        # Listener blockiert asynchron, bis der User physisch in sein UI klickt
        x, y = await _capture_user_click()
        
        # Crop berechnen und lernen (Boundary Safe, BDD Regel 3)
        crop_img_base64 = _crop_around(b64_img, x, y, size=50)
        save_vision_rule(target_description, crop_img_base64, x, y)
        
        if ON_VISION_LEARNED_SUCCESS:
            await ON_VISION_LEARNED_SUCCESS(target_description)
            
        return f"Element '{target_description}' war unsicher. Der Nutzer hat durch seinen manuellen Klick eingegriffen, und das System hat das Bild des Elements für zukünftige Durchläufe gelernt."
        
    # Failsafe wenn Element nicht gefunden
    if not coords:
        return f"Error: Element '{target_description}' nicht gefunden"
        
    y_min, x_min, y_max, x_max = coords
    
    # Skalierung (BDD Regel 4)
    screen_width, screen_height = pyautogui.size()
    
    center_y = y_min + (y_max - y_min) / 2
    center_x = x_min + (x_max - x_min) / 2
    
    absolute_x = int(center_x * screen_width)
    absolute_y = int(center_y * screen_height)
    
    # Physische Ausführung
    try:
        await asyncio.to_thread(pyautogui.moveTo, absolute_x, absolute_y, duration=0.5)
        await asyncio.to_thread(pyautogui.click)
        return f"Klick auf '{target_description}' erfolgreich"
    except pyautogui.FailSafeException:
        # BDD Regel 3: Die menschliche Notbremse
        return "Action aborted by User Intervention"
    except Exception as e:
        return f"Fehler bei Klick: {e}"


async def vision_type(text: str, press_enter: bool = False) -> str:
    """Tippt Text mit der physischen Tastatur an der aktuellen Cursor-Position."""
    if pyautogui is None or mss is None or Image is None:
        return "[Error: GUI Automation Dependencies (PyAutoGUI, mss, Pillow) sind nicht vollständig importiert.]"

    await check_sandbox("vision_type", {"text": text, "press_enter": press_enter})
    
    try:
        await asyncio.to_thread(pyautogui.write, text, interval=0.03)
        if press_enter:
            await asyncio.to_thread(pyautogui.press, "enter")
        return "Text erfolgreich eingetippt."
    except pyautogui.FailSafeException:
        return "Action aborted by User Intervention"
    except Exception as e:
        return f"Fehler beim Tippen: {e}"
