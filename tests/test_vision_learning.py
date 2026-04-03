import pytest
import asyncio
import base64
from io import BytesIO
from PIL import Image

from core.vision import _crop_around, _capture_user_click
from core.vision_memory import save_vision_rule, find_vision_rule

@pytest.fixture
def mock_screenshot_b64():
    """Erzeugt ein weisses 1920x1080 Mock-Bild als Base64."""
    img = Image.new("RGB", (1920, 1080), "white")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# 1. Integration Test: The Event Chain Listener
@pytest.mark.asyncio
async def test_capture_user_click_shuts_down():
    import pynput
    from unittest.mock import patch

    with patch("pynput.mouse.Listener") as MockListener:
        # We need to simulate the library behavior.
        # The listener takes an `on_click` callback.
        mock_instance = MockListener.return_value
        mock_instance.__enter__.return_value = mock_instance
        
        # When `join()` is called, we will simulate firing the callback to unblock it!
        def mock_join():
            # Get the callback function that was passed in
            on_click_cb = MockListener.call_args[1]["on_click"]
            
            # Fire the callback (simulating a left click at 500, 500)
            res = on_click_cb(500, 500, pynput.mouse.Button.left, True)
            
            # Check BDD Rule: the callback MUST return False to terminate listener
            assert res is False, "on_click did not return False to stop the listener"
            
            mock_instance.is_alive.return_value = False

        mock_instance.join.side_effect = mock_join

        x, y = await _capture_user_click()

        assert x == 500
        assert y == 500
        assert mock_instance.is_alive() is False


# 2. Crop-Boundary Test (BDD Rule 3)
def test_crop_around_boundary_zero(mock_screenshot_b64):
    """Prüft, ob Klicks ganz am Rand (0,0) nicht in einer OutOfBounds Exception enden."""
    try:
        # Klick auf Pixel (0,0) -> 50x50 crop would mean -25 to +25.
        cropped_b64 = _crop_around(mock_screenshot_b64, 0, 0, size=50)
    except Exception as e:
        pytest.fail(f"Boundary Crop hat eine Exception geworfen: {e}")

    # Validate output size and format
    img_data = base64.b64decode(cropped_b64)
    img = Image.open(BytesIO(img_data))
    
    assert img.size == (50, 50), "Der Crop muss aufgefüllt werden und genau 50x50 sein!"


# 3. ChromaDB Metadata Test
def test_chroma_metadata_limits(mock_screenshot_b64):
    """
    Prüft ob der Base64 String des 50x50 Crops in ChromaDB les- und schreibbar ist,
    ohne Metadaten Limits zu sprengen.
    """
    target = "testTargetBoundary"
    
    # 50x50 Crop generieren
    cropped_b64 = _crop_around(mock_screenshot_b64, 0, 0, size=50)
    
    # 50x50 RGB in JPEG Q85 ist winzig (unter 2KB), was für ChromaDB Metadaten absolut sicher ist.
    byte_size = len(cropped_b64.encode("utf-8"))
    assert byte_size < 10000, f"Der Metadaten-Crop ist zu groß ({byte_size} Bytes), ChromaDB erlaubt gewöhnlich nur kleine Strings!"
    
    # In DB schreiben und lesen
    try:
        save_vision_rule(target, cropped_b64, 0, 0)
        res = find_vision_rule(target)
        
        assert res is not None, "Fehler beim Finden des Eintrags"
        assert res["raw_target"] == target
        assert res["last_known_x"] == 0
        assert res["base64_crop"] == cropped_b64
    except Exception as e:
        pytest.fail(f"ChromaDB Metadata Operation fehlgeschlagen: {e}")

# 4. SSE Success Emit Hook Test
@pytest.mark.asyncio
async def test_succeses_hook_invocation(mock_screenshot_b64):
    """
    Stellt sicher, dass nach erfolgreichem Klick und ChromaDB-Persistenz
    der ON_VISION_LEARNED_SUCCESS Hook getriggert wird für das Web-UI.
    """
    import core.vision
    from core.vision import vision_click
    from unittest.mock import patch, AsyncMock
    
    # Mocking
    mock_success_cb = AsyncMock()
    core.vision.ON_VISION_LEARNED_SUCCESS = mock_success_cb
    
    with patch("core.vision._take_screenshot", return_value=mock_screenshot_b64), \
         patch("core.vision._get_bounding_box", return_value="UNSURE"), \
         patch("core.vision._capture_user_click", return_value=(100, 100)), \
         patch("core.vision.check_sandbox", new_callable=AsyncMock), \
         patch("core.vision_memory.save_vision_rule") as mock_save:
         
        res = await vision_click("Unknown Element")
        
        # Verify persistence and success notification were called
        mock_save.assert_called_once()
        mock_success_cb.assert_awaited_once_with("Unknown Element")
        
        assert "war unsicher" in res
        assert "manuellen Klick eingegriffen" in res
