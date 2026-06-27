import logging

from llama_index.core import VectorStoreIndex
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.schema import NodeWithScore

from app.config import settings
from app.services.document import get_storage_context, _get_embed_model

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a precise document Q&A assistant. "
    "Answer questions strictly based on the retrieved context. "
    "If the context does not contain enough information to answer, "
    "say 'I could not find relevant information in the uploaded documents.' "
    "Always cite the source page and file name when available. "
    "Be concise and factual."
)

_memory_store: dict[str, ChatMemoryBuffer] = {}
_retriever_store: dict[str, object] = {}
_llm = None
_index = None


def _get_llm():
    global _llm
    if _llm is None:
        from llama_index.llms.deepseek import DeepSeek
        _llm = DeepSeek(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            temperature=0.0,
            max_tokens=4096,
        )
    return _llm


def _get_index() -> VectorStoreIndex:
    global _index
    if _index is None:
        storage_context = get_storage_context()
        embed_model = _get_embed_model()
        _index = VectorStoreIndex(
            nodes=[],
            storage_context=storage_context,
            embed_model=embed_model,
        )
    return _index


def _get_or_create_memory(conversation_id: str) -> ChatMemoryBuffer:
    if conversation_id not in _memory_store:
        _memory_store[conversation_id] = ChatMemoryBuffer.from_defaults(
            token_limit=3900,
        )
    return _memory_store[conversation_id]


def _get_or_create_retriever(conversation_id: str):
    if conversation_id not in _retriever_store:
        index = _get_index()
        _retriever_store[conversation_id] = index.as_retriever(
            similarity_top_k=settings.similarity_top_k
        )
    return _retriever_store[conversation_id]


def _extract_sources(source_nodes: list[NodeWithScore]) -> list[dict]:
    sources = []
    for node in source_nodes:
        metadata = node.node.metadata or {}
        sources.append({
            "text": node.node.text[:500],
            "page": metadata.get("page"),
            "score": float(node.score) if node.score else None,
            "file_name": metadata.get("file_name"),
        })
    return sources


def _build_context_str(nodes: list[NodeWithScore]) -> str:
    context_parts = []
    for i, node in enumerate(nodes):
        metadata = node.node.metadata or {}
        file_name = metadata.get("file_name", "unknown")
        page = metadata.get("page", "unknown")
        context_parts.append(
            f"[Source {i + 1}] (file: {file_name}, page: {page})\n{node.node.text}"
        )
    return "\n\n".join(context_parts)


async def stream_query(
    question: str,
    conversation_id: str,
):
    retriever = _get_or_create_retriever(conversation_id)
    memory = _get_or_create_memory(conversation_id)
    llm = _get_llm()

    # 1. Retrieve relevant nodes from Qdrant
    nodes = await retriever.aretrieve(question)
    logger.info("Retrieved %d nodes for question: %s", len(nodes), question[:100])

    if not nodes:
        yield {"event": "token", "data": "I could not find relevant information in the uploaded documents for your question."}
        yield {"event": "sources", "data": []}
        yield {"event": "done", "data": {"conversation_id": conversation_id}}
        return

    # 2. Build context string from retrieved nodes
    context_str = _build_context_str(nodes)

    # 3. Build chat messages: system + context + history + user question
    messages = [ChatMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT)]

    # Add context as a system message
    context_message = (
        f"Here is the relevant context from the uploaded documents:\n\n"
        f"{context_str}\n\n"
        f"Use this context to answer the user's question. "
        f"If the context is insufficient, say so clearly."
    )
    messages.append(ChatMessage(role=MessageRole.SYSTEM, content=context_message))

    # Add conversation history from memory
    chat_history = memory.get(input=question)
    messages.extend(chat_history)

    # Add the current user question
    messages.append(ChatMessage(role=MessageRole.USER, content=question))

    # 4. Store user message in memory
    await memory.aput(ChatMessage(role=MessageRole.USER, content=question))

    # 5. Stream the LLM response token by token
    full_response = ""
    response = await llm.astream_chat(messages)

    async for chunk in response:
        delta = chunk.delta
        if delta:
            full_response += delta
            yield {"event": "token", "data": delta}

    # 6. Store assistant response in memory
    await memory.aput(ChatMessage(role=MessageRole.ASSISTANT, content=full_response))

    # 7. Yield sources
    sources = _extract_sources(nodes)
    yield {"event": "sources", "data": sources}

    # 8. Yield done
    yield {"event": "done", "data": {"conversation_id": conversation_id}}


def reset_conversation(conversation_id: str) -> None:
    _memory_store.pop(conversation_id, None)
    _retriever_store.pop(conversation_id, None)
