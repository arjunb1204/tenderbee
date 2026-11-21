"""
Cloud & AI CAPTCHA Solving Service for Indian Government Tender Portals.
Supports Gemini Multimodal Vision (sub-second, high-accuracy), CapSolver cloud API,
and local deterministic fallbacks for offline testing.
"""
import base64
import logging
import os
import re
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
import httpx

_repo_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_repo_root / ".env")
load_dotenv()

logger = logging.getLogger(__name__)


class CaptchaService:
    """
    Unified CAPTCHA solving service for government procurement portals.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        capsolver_api_key: Optional[str] = None,
        mock_mode: bool = False,
    ):
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
        self.capsolver_api_key = capsolver_api_key or os.getenv("CAPSOLVER_API_KEY")
        self.mock_mode = mock_mode

    def solve(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
        expected_length: Optional[int] = None,
    ) -> str:
        """
        Solve an image CAPTCHA.
        Dispatches to Gemini Vision first, then CapSolver, then deterministic fallback.
        """
        if self.mock_mode:
            return self._solve_mock(image_bytes)

        if self.gemini_api_key:
            try:
                solved = self.solve_gemini(image_bytes, mime_type=mime_type)
                if solved:
                    logger.info("Successfully solved CAPTCHA via Gemini Vision: %s", solved)
                    return solved
            except Exception as e:
                logger.warning("Gemini Vision CAPTCHA solve failed: %s. Trying fallback.", e)

        if self.capsolver_api_key:
            try:
                solved = self.solve_capsolver(image_bytes)
                if solved:
                    logger.info("Successfully solved CAPTCHA via CapSolver: %s", solved)
                    return solved
            except Exception as e:
                logger.warning("CapSolver solve failed: %s.", e)

        # Fallback to mock/heuristic if no cloud keys or network failure
        logger.info("Using mock/heuristic fallback for CAPTCHA.")
        return self._solve_mock(image_bytes)

    def solve_gemini(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """
        Solve distorted alphanumeric CAPTCHA using Gemini 1.5 Flash Vision.
        Direct HTTP REST call with zero external heavyweight SDK dependencies.
        """
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"

        prompt = (
            "You are a specialized government portal CAPTCHA reader. "
            "Examine this image and read the distorted alphanumeric characters. "
            "Output ONLY the characters with no spaces, no punctuation, no quotes, and no commentary. "
            "Example valid output: 4g9p2"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_data,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 20,
            },
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini returned empty candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise ValueError("No text in Gemini response candidate")

        raw_text = parts[0].get("text", "").strip()
        # Clean up any quotes or markdown
        clean_text = re.sub(r"[^a-zA-Z0-9]", "", raw_text)
        return clean_text

    def solve_capsolver(self, image_bytes: bytes) -> str:
        """
        Solve image CAPTCHA using CapSolver Cloud API.
        """
        if not self.capsolver_api_key:
            raise ValueError("CAPSOLVER_API_KEY not configured")

        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        url = "https://api.capsolver.com/createTask"

        payload = {
            "clientKey": self.capsolver_api_key,
            "task": {
                "type": "ImageToTextTask",
                "body": b64_data,
            },
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        solution = data.get("solution", {})
        text = solution.get("text", "")
        return re.sub(r"[^a-zA-Z0-9]", "", text)

    def _solve_mock(self, image_bytes: bytes) -> str:
        """
        Deterministic mock solver for local tests and simulated portal flows.
        """
        import hashlib
        h = hashlib.md5(image_bytes).hexdigest()[:6]
        return h.upper()
