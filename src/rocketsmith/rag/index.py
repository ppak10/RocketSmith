from typing import Any


def _flatten_metadata(value: Any) -> dict[str, str]:
    """Coerce a metadata value to a flat string-valued dict for ChromaDB.

    Handles three cases:
    - dict  → stringify each value
    - str   → attempt JSON parse, fall back to {"raw": value}
    - other → {"raw": str(value)}
    """
    import json

    if isinstance(value, dict):
        return {k: str(v) for k, v in value.items() if v is not None}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return {k: str(v) for k, v in parsed.items() if v is not None}
        except (json.JSONDecodeError, ValueError):
            pass
        return {"raw": value}
    return {"raw": str(value)}


def index_dataset(
    hf_repo: str,
    collection_name: str,
    id_field: str = "id",
    text_field: str = "document",
    metadata_field: str | None = "metadata",
    metadata_fields: list[str] | None = None,
    subset: str | None = None,
    split: str = "train",
) -> dict[str, Any]:
    """Pull a HuggingFace dataset and upsert it into a ChromaDB collection.

    Supports two metadata layouts:

    1. Pre-structured (default, matches rocketsmith/* datasets):
       A single ``metadata_field`` column holds a dict per row.
       Defaults: id_field="id", text_field="document", metadata_field="metadata".

    2. Flat columns:
       Set ``metadata_field=None`` and pass ``metadata_fields`` as a list of
       column names to collect individually.

    Args:
        hf_repo: HuggingFace dataset repo, e.g. "rocketsmith/RocketReviews".
        collection_name: ChromaDB collection to write into (created if absent).
        id_field: Column used as the unique document ID (default "id").
        text_field: Column whose text gets embedded and searched (default "document").
        metadata_field: Column containing a dict of metadata (default "metadata").
            Set to None to use flat ``metadata_fields`` instead.
        metadata_fields: Flat column names to use as metadata (used when
            metadata_field is None).
        subset: Dataset configuration / subset name, e.g. "reviews", "flights".
            Maps to the ``name`` argument of load_dataset().
        split: Dataset split to load (default "train").

    Returns:
        Dict with "collection", "subset", and "indexed" document count.
    """
    from datasets import load_dataset

    from rocketsmith.rag.client import get_client

    load_kwargs: dict[str, Any] = {"split": split}
    if subset:
        load_kwargs["name"] = subset

    ds = load_dataset(hf_repo, **load_kwargs)

    client = get_client()
    collection = client.get_or_create_collection(collection_name)

    ids, documents, metadatas = [], [], []

    for row in ds:
        ids.append(str(row[id_field]))
        documents.append(str(row[text_field]))

        if metadata_field is not None:
            meta = _flatten_metadata(row.get(metadata_field) or {})
        else:
            meta = {
                k: str(row[k])
                for k in (metadata_fields or [])
                if k in row and row[k] is not None
            }

        metadatas.append(meta)

    # Upsert in batches to stay within ChromaDB memory limits
    batch_size = 500
    for i in range(0, len(ids), batch_size):
        collection.upsert(
            ids=ids[i : i + batch_size],
            documents=documents[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
        )

    return {"collection": collection_name, "subset": subset, "indexed": len(ids)}
