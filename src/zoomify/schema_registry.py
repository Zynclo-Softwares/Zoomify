"""Business schema registry and image-metadata detection (placeholder).

Images may carry metadata ``structure-zoomify:<schema_id>`` (e.g.
``structure-zoomify:acme-sld-v1``). When present — and ``structured`` is not
disabled — Zoomify should fetch the registered schema and configure the LLM for
structured output (Phase 2 extract). That pipeline is not implemented yet;
this module validates ids and documents the intended flow.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

METADATA_KEY = "structure-zoomify"

# Placeholder registry — replace with DB / Zynclo-delivered schemas per customer.
PLACEHOLDER_SCHEMAS: dict[str, dict] = {
    "acme-sld-v1": {
        "title": "Acme electrical single-line diagram",
        # TODO: json_schema, entity definitions, zoom hints from Zynclo onboarding
    },
}


@dataclass(frozen=True)
class SchemaResolution:
    """How the backend should format the final LLM response."""

    schema_id: str | None
    structured: bool
    source: str  # "none" | "metadata" | "param"


def read_schema_from_image(img: Image.Image) -> str | None:
    """Return schema id from image metadata, if tagged.

    TODO: implement readers for PNG tEXt/iTXt, JPEG EXIF UserComment, XMP, etc.
    Expected value format: ``structure-zoomify:acme-sld-v1`` or bare id after key.
    """
    _ = img
    return None


def validate_schema_id(schema_id: str) -> bool:
    """Return True when ``schema_id`` is registered and well-formed."""
    if not schema_id or not schema_id.strip():
        return False
    if len(schema_id) > 128:
        return False
    if any(c.isspace() for c in schema_id):
        return False
    return schema_id in PLACEHOLDER_SCHEMAS


def resolve_schema(
    *,
    schema_param: str | None,
    image: Image.Image | None,
    structured: bool = True,
) -> SchemaResolution:
    """Pick structured vs free-text mode and which schema applies.

    Priority when ``structured`` is True:
      1. Explicit ``schema`` request field (API / UI override)
      2. Image metadata ``structure-zoomify:<id>``
      3. Unstructured text response

    When ``structured`` is False, always unstructured even if metadata exists.
    """
    if not structured:
        return SchemaResolution(schema_id=None, structured=False, source="none")

    if schema_param:
        sid = schema_param.strip()
        if not validate_schema_id(sid):
            raise ValueError(f"Unknown or invalid schema id: {sid!r}")
        return SchemaResolution(schema_id=sid, structured=True, source="param")

    if image is not None:
        meta_id = read_schema_from_image(image)
        if meta_id:
            if not validate_schema_id(meta_id):
                raise ValueError(f"Image metadata schema not registered: {meta_id!r}")
            return SchemaResolution(schema_id=meta_id, structured=True, source="metadata")

    return SchemaResolution(schema_id=None, structured=False, source="none")


def apply_schema_to_agent_config(resolution: SchemaResolution) -> dict:
    """Placeholder hook for structured LLM output configuration.

    TODO: When ``resolution.structured`` and ``resolution.schema_id`` are set:
      - Load schema from PLACEHOLDER_SCHEMAS / customer registry
      - After zoom tool loop, run Phase 2 ``response_format=json_schema`` extract
      - Return JSON matching the Zynclo business schema

    For now returns metadata only; agent still produces free-text answers.
    """
    return {
        "structured": resolution.structured,
        "schema_id": resolution.schema_id,
        "source": resolution.source,
        # "response_format": ...  # future
    }
