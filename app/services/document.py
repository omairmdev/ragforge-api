import os
import tempfile
import logging

from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, AsyncQdrantClient

from app.config import settings

logger = logging.getLogger(__name__)


def _qdrant_kwargs() -> dict:
    kwargs: dict = {"url": settings.qdrant_url}
    if settings.qdrant_api_key:
        kwargs["api_key"] = settings.qdrant_api_key
    return kwargs


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(**_qdrant_kwargs())


def get_async_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(**_qdrant_kwargs())


def get_vector_store() -> QdrantVectorStore:
    client = get_qdrant_client()
    aclient = get_async_qdrant_client()
    return QdrantVectorStore(
        client=client,
        aclient=aclient,
        collection_name=settings.qdrant_collection,
    )


def get_storage_context() -> StorageContext:
    vector_store = get_vector_store()
    return StorageContext.from_defaults(vector_store=vector_store)


def get_or_create_index() -> VectorStoreIndex:
    storage_context = get_storage_context()
    embed_model = _get_embed_model()
    return VectorStoreIndex(
        nodes=[],
        storage_context=storage_context,
        embed_model=embed_model,
    )


def _get_embed_model():
    from llama_index.embeddings.openai import OpenAIEmbedding
    return OpenAIEmbedding(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )


async def process_and_store_pdf(file_bytes: bytes, file_name: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, file_name)
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        reader = SimpleDirectoryReader(
            input_dir=tmp_dir,
            required_exts=[".pdf"],
        )
        documents = reader.load_data()

        if not documents:
            raise ValueError(f"No text could be extracted from {file_name}")

        for i, doc in enumerate(documents):
            doc.metadata["file_name"] = file_name
            if "page" not in doc.metadata or doc.metadata.get("page") is None:
                doc.metadata["page"] = i + 1

        splitter = SentenceSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        nodes = splitter.get_nodes_from_documents(documents)

        storage_context = get_storage_context()
        embed_model = _get_embed_model()

        index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=embed_model,
            show_progress=False,
        )

        logger.info(
            "Stored %d chunks from %s into Qdrant collection '%s'",
            len(nodes),
            file_name,
            settings.qdrant_collection,
        )

        return {
            "file_name": file_name,
            "chunks_created": len(nodes),
            "collection": settings.qdrant_collection,
        }
