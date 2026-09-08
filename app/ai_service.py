"""AI catalogue-content generation, isolated behind a small provider interface.

The rest of the app only ever calls :func:`generate_catalogue_content` and
catches :class:`AiServiceError`. The concrete model call (currently Google
Gemini) lives entirely in this module behind the ``CatalogueContentProvider``
protocol, so swapping to a different provider later means adding one class here
and changing :data:`_provider` — no route or database code has to change.

The API key is read from the ``GEMINI_API_KEY`` environment variable (with
``GOOGLE_API_KEY`` accepted as a fallback). It is never hardcoded and never
logged.
"""

from __future__ import annotations

import os
from typing import Protocol


class AiServiceError(RuntimeError):
    """Raised for any failure while generating catalogue content.

    Wraps provider-specific errors (missing API key, network failure, quota,
    empty response, ...) in one type the callers can catch without importing
    anything provider-specific.
    """


# --- Prompt ---------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a product copywriter for small-business catalogues. Given a "
    "product's name and description, write polished catalogue content as plain "
    "text with these labelled sections:\n"
    "  Headline: a short, catchy title (max 8 words)\n"
    "  Description: 2-3 sentences of vivid, benefit-led marketing copy\n"
    "  Key Features: 3-5 concise bullet points, one per line, each starting "
    "with '- '\n"
    "Do not invent specifications or claims that aren't supported by the input. "
    "Return only the content, no preamble."
)


def _build_prompt(product_name: str, product_description: str | None) -> str:
    description = (product_description or "").strip() or "(no description provided)"
    return (
        f"{_SYSTEM_PROMPT}\n\n"
        f"Product name: {product_name.strip()}\n"
        f"Product description: {description}\n"
    )


# --- Provider interface -------------------------------------------------------

class CatalogueContentProvider(Protocol):
    """Anything that can turn a product name + description into catalogue text."""

    def generate(self, product_name: str, product_description: str | None) -> str:
        ...


class GeminiProvider:
    """``CatalogueContentProvider`` backed by the Google Gemini API.

    The client is configured lazily on first use so importing this module (and
    therefore the whole app) never requires the API key to be present — only an
    actual generation call does.
    """

    _API_KEY_ENV_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    _DEFAULT_MODEL = "gemini-2.5-flash-lite"
    

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or os.getenv("GEMINI_MODEL", self._DEFAULT_MODEL)
        self._model = None  # created on first generate()

    def _api_key(self) -> str:
        for var in self._API_KEY_ENV_VARS:
            value = os.getenv(var)
            if value and value.strip():
                return value.strip()
        raise AiServiceError(
            "Gemini API key is not configured. Set the GEMINI_API_KEY "
            "environment variable."
        )

    def _get_model(self):
        if self._model is None:
            try:
                import google.generativeai as genai
            except ImportError as exc:  # pragma: no cover - dependency missing
                raise AiServiceError(
                    "google-generativeai is not installed."
                ) from exc

            genai.configure(api_key=self._api_key())
            self._model = genai.GenerativeModel(self._model_name)
        return self._model

    def generate(self, product_name: str, product_description: str | None) -> str:
        model = self._get_model()
        prompt = _build_prompt(product_name, product_description)

        try:
            response = model.generate_content(prompt)
        except AiServiceError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalise any SDK/network error
            raise AiServiceError(f"Gemini request failed: {exc}") from exc

        text = _extract_text(response)
        if not text:
            raise AiServiceError("Gemini returned an empty response.")
        return text


def _extract_text(response) -> str:
    """Pull the generated text out of a Gemini response, tolerating shapes."""
    text = getattr(response, "text", None)
    if text and text.strip():
        return text.strip()

    # Fall back to walking candidates/parts if `.text` isn't populated (e.g.
    # when the response was blocked or the SDK version differs).
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if part_text and part_text.strip():
                return part_text.strip()
    return ""


# --- Public API ------------------------------------------------------------

# The single place that decides which provider is in use. Swap this line (and
# add a sibling class above) to move to a different AI backend.
_provider: CatalogueContentProvider = GeminiProvider()


def generate_catalogue_content(
    product_name: str, product_description: str | None
) -> str:
    """Generate catalogue copy for a product.

    Returns the generated text on success. Raises :class:`AiServiceError` for
    every failure mode (missing key, network/SDK error, empty result) so callers
    have exactly one exception type to handle.
    """
    if not product_name or not product_name.strip():
        raise AiServiceError("Product name is required to generate content.")
    return _provider.generate(product_name, product_description)
