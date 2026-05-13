"""
NEXUS Screen Understanding — OCR + Vision model analysis.

Provides screen understanding capabilities:
  - Screenshot capture and analysis
  - OCR text extraction (with Tesseract fallback)
  - Vision model analysis (GPT-4V, Claude Vision, Gemini Vision)
  - UI element detection (buttons, inputs, labels)
  - Text region localization

All OCR and vision dependencies are lazy-imported to gracefully
handle missing installations.

Usage:
    from nexus.computer.screen_understanding import ScreenUnderstanding

    su = ScreenUnderstanding()
    text = await su.extract_text()
    elements = await su.detect_ui_elements()
    analysis = await su.analyze_with_vision("What is on the screen?")
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import NexusError

logger = logging.getLogger(__name__)


# ── Exceptions ─────────────────────────────────────────────────────

class ScreenUnderstandingError(NexusError):
    """Raised when a screen understanding operation fails."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="SCREEN_UNDERSTANDING_ERROR", details=details)


# ── Data Structures ────────────────────────────────────────────────

@dataclass
class TextRegion:
    """A region of text detected on screen."""
    text: str
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": round(self.confidence, 3),
            "center": self.center,
        }


@dataclass
class UIElementDetection:
    """A detected UI element on screen."""
    element_type: str  # button, input, label, link, checkbox, etc.
    text: str = ""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0
    attributes: dict[str, str] = field(default_factory=dict)

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_type": self.element_type,
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": round(self.confidence, 3),
            "center": self.center,
            "attributes": self.attributes,
        }


@dataclass
class VisionAnalysis:
    """Result of vision model analysis."""
    description: str
    elements: list[UIElementDetection] = field(default_factory=list)
    text_found: list[str] = field(default_factory=list)
    actions_suggested: list[str] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    confidence: float = 0.0


# ── Screen Understanding ──────────────────────────────────────────

class ScreenUnderstanding:
    """
    Screen understanding via OCR + Vision models.

    Provides:
      - Screenshot capture and analysis
      - OCR text extraction (Tesseract with fallback)
      - Vision model analysis (GPT-4V, Claude Vision, Gemini)
      - UI element detection
      - Text region localization

    All OCR/vision dependencies are lazy-imported to handle
    the case where they are not installed.

    Usage:
        su = ScreenUnderstanding()
        text = await su.extract_text()
        elements = await su.detect_ui_elements()
        analysis = await su.analyze_with_vision("What is on the screen?")
    """

    def __init__(self):
        self.settings = get_settings()
        self._last_screenshot_path: Optional[str] = None
        self._ocr_available: Optional[bool] = None
        self._analysis_count: int = 0

    # ── Screenshot Capture ────────────────────────────────────────

    async def capture_screenshot(
        self,
        region: Optional[tuple[int, int, int, int]] = None,
    ) -> str:
        """
        Capture a screenshot and return the file path.

        Args:
            region: Optional (left, top, width, height) crop region.

        Returns:
            Path to the saved screenshot.
        """
        try:
            import pyautogui

            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()

            path = tempfile.mktemp(suffix=".png", prefix="nexus_screen_")
            screenshot.save(path)
            self._last_screenshot_path = path
            return path

        except ImportError:
            logger.error("pyautogui not available for screenshot capture")
            return ""
        except Exception as e:
            logger.error("Screenshot capture failed: %s", e)
            return ""

    def _screenshot_to_base64(self, image_path: str) -> str:
        """Convert a screenshot to base64 for API transmission."""
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception as e:
            logger.error("Base64 conversion failed: %s", e)
            return ""

    # ── OCR Text Extraction ───────────────────────────────────────

    def _check_ocr_available(self) -> bool:
        """Check if OCR (Tesseract) is available."""
        if self._ocr_available is None:
            try:
                import pytesseract  # noqa: F401
                from PIL import Image  # noqa: F401
                self._ocr_available = True
            except ImportError:
                self._ocr_available = False
        return self._ocr_available

    async def extract_text(
        self,
        image_path: Optional[str] = None,
        lang: str = "eng",
    ) -> str:
        """
        Extract text from the screen using OCR.

        Args:
            image_path: Path to image (default: capture new screenshot).
            lang: Language for OCR (default: English).

        Returns:
            Extracted text string.
        """
        # Get or capture image
        if not image_path:
            if not self._last_screenshot_path:
                image_path = await self.capture_screenshot()
            else:
                image_path = self._last_screenshot_path

        if not image_path or not Path(image_path).exists():
            return ""

        # Try Tesseract OCR
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang=lang)
            return text.strip()

        except ImportError:
            logger.warning("pytesseract/Pillow not available, trying fallback OCR")
        except Exception as e:
            logger.warning("Tesseract OCR failed: %s, trying fallback", e)

        # Fallback: Use vision model for OCR
        return await self._vision_ocr(image_path)

    async def extract_text_regions(
        self,
        image_path: Optional[str] = None,
    ) -> list[TextRegion]:
        """
        Extract text regions with their locations.

        Args:
            image_path: Path to image (default: capture new screenshot).

        Returns:
            List of TextRegion objects with location info.
        """
        if not image_path:
            image_path = await self.capture_screenshot()

        if not image_path or not Path(image_path).exists():
            return []

        try:
            import pytesseract
            from PIL import Image

            image = Image.open(image_path)
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

            regions = []
            for i in range(len(data["text"])):
                text = data["text"][i].strip()
                if not text:
                    continue

                confidence = float(data["conf"][i])
                if confidence < 30:  # Skip low-confidence detections
                    continue

                regions.append(TextRegion(
                    text=text,
                    x=int(data["left"][i]),
                    y=int(data["top"][i]),
                    width=int(data["width"][i]),
                    height=int(data["height"][i]),
                    confidence=confidence / 100.0,
                ))

            return regions

        except ImportError:
            logger.warning("pytesseract not available for text region extraction")
            return []
        except Exception as e:
            logger.error("Text region extraction failed: %s", e)
            return []

    async def _vision_ocr(self, image_path: str) -> str:
        """
        Use a vision model as fallback OCR.

        Args:
            image_path: Path to the image.

        Returns:
            Extracted text from the vision model.
        """
        try:
            from nexus.llm.router import LLMRouter, TaskComplexity

            b64 = self._screenshot_to_base64(image_path)
            if not b64:
                return ""

            # Use the LLM router with a vision-capable model
            router = LLMRouter()

            # Try vision providers in order
            for provider in ["openai", "anthropic", "gemini"]:
                try:
                    messages = [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Extract all visible text from this screenshot. Return only the text content, preserving the general layout.",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{b64[:10000]}"  # Truncate for safety
                                    },
                                },
                            ],
                        }
                    ]

                    response = await router.complete(
                        messages=messages,
                        provider=provider,
                        temperature=0.1,
                        max_tokens=4096,
                    )
                    return response.content

                except Exception:
                    continue

            return ""

        except Exception as e:
            logger.error("Vision OCR failed: %s", e)
            return ""

    # ── Vision Model Analysis ─────────────────────────────────────

    async def analyze_with_vision(
        self,
        query: str,
        image_path: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> VisionAnalysis:
        """
        Analyze the screen using a vision model.

        Args:
            query: What to look for or analyze.
            image_path: Path to image (default: capture new screenshot).
            provider: Specific vision provider to use.

        Returns:
            VisionAnalysis with the model's interpretation.
        """
        self._analysis_count += 1

        if not image_path:
            image_path = await self.capture_screenshot()

        if not image_path or not Path(image_path).exists():
            return VisionAnalysis(description="No screenshot available")

        b64 = self._screenshot_to_base64(image_path)
        if not b64:
            return VisionAnalysis(description="Failed to encode screenshot")

        # Try vision-capable providers
        vision_providers = [provider] if provider else ["openai", "anthropic", "gemini"]

        for prov in vision_providers:
            try:
                from nexus.llm.router import LLMRouter

                router = LLMRouter()

                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"{query}\n\n"
                                    "Additionally, please identify:\n"
                                    "1. Any UI elements (buttons, inputs, labels, links)\n"
                                    "2. Any visible text content\n"
                                    "3. Suggested actions the user might want to take\n\n"
                                    "Format your response as:\n"
                                    "DESCRIPTION: [your description]\n"
                                    "ELEMENTS: [list of UI elements with types]\n"
                                    "TEXT: [visible text]\n"
                                    "ACTIONS: [suggested actions]"
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{b64[:10000]}"
                                },
                            },
                        ],
                    }
                ]

                response = await router.complete(
                    messages=messages,
                    provider=prov,
                    temperature=0.3,
                    max_tokens=4096,
                )

                # Parse the structured response
                content = response.content
                analysis = self._parse_vision_response(content, prov, response.model)
                return analysis

            except Exception as e:
                logger.warning("Vision analysis with %s failed: %s", prov, e)
                continue

        return VisionAnalysis(description="Vision analysis failed — no provider available")

    def _parse_vision_response(self, content: str, provider: str, model: str) -> VisionAnalysis:
        """Parse a structured vision model response."""
        description = ""
        elements: list[UIElementDetection] = []
        text_found: list[str] = []
        actions_suggested: list[str] = []

        lines = content.split("\n")
        current_section = "description"

        for line in lines:
            line_lower = line.lower().strip()
            if line_lower.startswith("description:"):
                description = line.split(":", 1)[1].strip()
                current_section = "description"
            elif line_lower.startswith("elements:"):
                current_section = "elements"
                element_text = line.split(":", 1)[1].strip()
                if element_text:
                    elements.append(UIElementDetection(
                        element_type="unknown",
                        text=element_text,
                        confidence=0.5,
                    ))
            elif line_lower.startswith("text:"):
                current_section = "text"
                text_content = line.split(":", 1)[1].strip()
                if text_content:
                    text_found.append(text_content)
            elif line_lower.startswith("actions:"):
                current_section = "actions"
                action_text = line.split(":", 1)[1].strip()
                if action_text:
                    actions_suggested.append(action_text)
            else:
                if current_section == "description" and not description:
                    description += line + " "
                elif current_section == "elements" and line.strip().startswith(("-", "*", "•")):
                    elements.append(UIElementDetection(
                        element_type="unknown",
                        text=line.strip().lstrip("-*• ").strip(),
                        confidence=0.5,
                    ))
                elif current_section == "text" and line.strip().startswith(("-", "*", "•")):
                    text_found.append(line.strip().lstrip("-*• ").strip())
                elif current_section == "actions" and line.strip().startswith(("-", "*", "•")):
                    actions_suggested.append(line.strip().lstrip("-*• ").strip())

        # If no structured parsing worked, use the full content as description
        if not description:
            description = content.strip()

        return VisionAnalysis(
            description=description.strip(),
            elements=elements,
            text_found=text_found,
            actions_suggested=actions_suggested,
            model=model,
            provider=provider,
        )

    # ── UI Element Detection ──────────────────────────────────────

    async def detect_ui_elements(
        self,
        image_path: Optional[str] = None,
    ) -> list[UIElementDetection]:
        """
        Detect UI elements on the screen.

        Uses a combination of OCR and vision model analysis
        to identify buttons, inputs, labels, and other UI elements.

        Args:
            image_path: Path to image (default: capture new screenshot).

        Returns:
            List of UIElementDetection objects.
        """
        # First try accessibility-based detection via GUI controller
        try:
            from nexus.computer.gui_control import GUIController
            gui = GUIController()
            ui_elements = await gui.get_ui_elements()

            if ui_elements:
                return [
                    UIElementDetection(
                        element_type=el.role or "unknown",
                        text=el.name or el.text,
                        x=el.x,
                        y=el.y,
                        width=el.width,
                        height=el.height,
                        confidence=0.8,
                        attributes={"clickable": str(el.is_clickable), "editable": str(el.is_editable)},
                    )
                    for el in ui_elements
                ]
        except Exception:
            pass

        # Fallback: Use OCR + vision for UI detection
        if not image_path:
            image_path = await self.capture_screenshot()

        # Get text regions via OCR
        text_regions = await self.extract_text_regions(image_path)

        # Convert text regions to UI elements with heuristic classification
        elements = []
        for region in text_regions:
            element_type = self._classify_text_region(region.text)
            elements.append(UIElementDetection(
                element_type=element_type,
                text=region.text,
                x=region.x,
                y=region.y,
                width=region.width,
                height=region.height,
                confidence=region.confidence * 0.7,  # Lower confidence for heuristic
            ))

        return elements

    def _classify_text_region(self, text: str) -> str:
        """
        Classify a text region as a UI element type based on heuristics.

        Args:
            text: The text content.

        Returns:
            Element type string.
        """
        text_lower = text.lower().strip()

        # Button indicators
        if text_lower in ("ok", "cancel", "submit", "save", "delete", "close",
                          "apply", "yes", "no", "accept", "reject", "confirm"):
            return "button"

        # Common button patterns
        if len(text) < 30 and text.isupper():
            return "button"

        # Label patterns (ends with colon)
        if text.endswith(":"):
            return "label"

        # Link patterns
        if text_lower.startswith("http") or text_lower.startswith("www."):
            return "link"

        # Input field indicators
        if text_lower in ("", "...", "enter text", "type here", "search"):
            return "input"

        # Default: label
        return "label"

    # ── Find Text on Screen ──────────────────────────────────────

    async def find_text(
        self,
        search_text: str,
        image_path: Optional[str] = None,
    ) -> list[TextRegion]:
        """
        Find specific text on the screen.

        Args:
            search_text: Text to search for.
            image_path: Path to image (default: capture new screenshot).

        Returns:
            List of TextRegion objects matching the search text.
        """
        regions = await self.extract_text_regions(image_path)
        search_lower = search_text.lower()

        return [
            region for region in regions
            if search_lower in region.text.lower()
        ]

    # ── Statistics ────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get screen understanding statistics."""
        return {
            "ocr_available": self._check_ocr_available(),
            "last_screenshot": self._last_screenshot_path,
            "analysis_count": self._analysis_count,
            "vision_providers": ["openai", "anthropic", "gemini"],
        }
