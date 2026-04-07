from mcp.server.fastmcp import FastMCP


def register_rag_reference(app: FastMCP):
    from typing import Any, Literal, Union

    from rocketsmith.mcp.types import ToolError, ToolSuccess
    from rocketsmith.mcp.utils import tool_error, tool_success

    @app.tool(
        title="RAG Reference",
        description=(
            "Index HuggingFace datasets into ChromaDB or search indexed collections. "
            "Use 'index' to pull a dataset from HuggingFace and store it locally. "
            "Use 'search' to run a semantic query over an indexed collection. "
            "Use 'collections' to list what is currently indexed and how many documents each holds. "
            "Defaults (id_field, text_field, metadata_field) match the rocketsmith/* dataset schema."
        ),
        structured_output=True,
    )
    async def rag_reference(
        action: Literal["index", "search", "collections"],
        # --- index params ---
        hf_repo: str | None = None,
        collection: str | None = None,
        subset: str | None = None,
        id_field: str = "id",
        text_field: str = "document",
        metadata_field: str | None = "metadata",
        metadata_fields: list[str] | None = None,
        split: str = "train",
        # --- search params ---
        query: str | None = None,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> Union[ToolSuccess[list[dict] | dict], ToolError]:
        """Query or index RAG reference collections backed by ChromaDB.

        Actions:
            index:       Pull a HuggingFace dataset and index it into a named ChromaDB
                         collection. Idempotent — re-running upserts without duplicating.
                         Required: hf_repo, collection.
                         Optional: subset (dataset configuration, e.g. "reviews"),
                           id_field (default "id"), text_field (default "document"),
                           metadata_field (default "metadata" — a single dict column),
                           metadata_fields (flat column list, used when metadata_field=None),
                           split (default "train").
            search:      Semantic search over an indexed collection. Returns the closest
                         matching documents with their metadata and similarity distance.
                         Required: collection, query.
                         Optional: n_results (default 5), where (metadata filter dict).
            collections: List all indexed collections and their document counts.

        Args:
            action: One of 'index', 'search', 'collections'.
            hf_repo: HuggingFace dataset repo ID, e.g. "rocketsmith/RocketReviews".
            collection: ChromaDB collection name to write into or search against.
            subset: Dataset configuration name, e.g. "reviews", "flights", "designs".
            id_field: Column used as the unique document ID (default "id").
            text_field: Column whose text gets embedded and searched (default "document").
            metadata_field: Column containing a per-row metadata dict (default "metadata").
                Set to None to use flat metadata_fields instead.
            metadata_fields: Flat column names to collect as metadata (used when
                metadata_field is None).
            split: Dataset split to load (default "train").
            query: Natural language search query.
            n_results: Number of results to return (default 5).
            where: Optional ChromaDB metadata filter, e.g. {"manufacturer_name": "Estes"}.
        """
        try:
            from rocketsmith.rag.client import get_client

            client = get_client()

            if action == "collections":
                cols = client.list_collections()
                return tool_success(
                    [{"name": c.name, "count": c.count()} for c in cols]
                )

            if action == "index":
                if not hf_repo:
                    return tool_error(
                        "'index' action requires: hf_repo",
                        "MISSING_ARGUMENT",
                    )
                if not collection:
                    return tool_error(
                        "'index' action requires: collection",
                        "MISSING_ARGUMENT",
                    )

                from rocketsmith.rag.index import index_dataset

                result = index_dataset(
                    hf_repo=hf_repo,
                    collection_name=collection,
                    id_field=id_field,
                    text_field=text_field,
                    metadata_field=metadata_field,
                    metadata_fields=metadata_fields,
                    subset=subset,
                    split=split,
                )
                return tool_success(result)

            if action == "search":
                if not collection:
                    return tool_error(
                        "'search' action requires: collection",
                        "MISSING_ARGUMENT",
                    )
                if not query:
                    return tool_error(
                        "'search' action requires: query",
                        "MISSING_ARGUMENT",
                    )

                col = client.get_collection(collection)
                results = col.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where or None,
                )

                docs = results["documents"][0]
                ids = results["ids"][0]
                distances = (results.get("distances") or [[None] * len(docs)])[0]
                metas = (results.get("metadatas") or [[{}] * len(docs)])[0]

                return tool_success(
                    [
                        {
                            "id": ids[i],
                            "text": docs[i],
                            "distance": distances[i],
                            "metadata": metas[i],
                        }
                        for i in range(len(docs))
                    ]
                )

        except Exception as e:
            return tool_error(
                f"rag_reference {action} failed: {e}",
                "RAG_ERROR",
                action=action,
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = rag_reference
