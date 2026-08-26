"""Read-only helpers for presenting persisted three-level document chunks."""
from typing import Any


DISPLAY_FIELDS = (
    "chunk_id",
    "parent_chunk_id",
    "root_chunk_id",
    "chunk_level",
    "chunk_idx",
    "page_number",
    "text",
)


def merge_document_chunks(
    parent_chunks: list[dict[str, Any]],
    leaf_chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return de-duplicated display fields, ordered by page then chunk position."""
    chunks_by_id: dict[str, dict[str, Any]] = {}
    for source in [*parent_chunks, *leaf_chunks]:
        chunk_id = str(source.get("chunk_id") or "").strip()
        if not chunk_id:
            continue
        chunks_by_id[chunk_id] = {
            field: source.get(field, "")
            for field in DISPLAY_FIELDS
        }
        chunks_by_id[chunk_id]["chunk_level"] = int(source.get("chunk_level", 0) or 0)
        chunks_by_id[chunk_id]["chunk_idx"] = int(source.get("chunk_idx", 0) or 0)
        chunks_by_id[chunk_id]["page_number"] = int(source.get("page_number", 0) or 0)

    return sorted(
        chunks_by_id.values(),
        key=lambda item: (
            item["page_number"],
            item["chunk_idx"],
            item["chunk_level"],
            item["chunk_id"],
        ),
    )
