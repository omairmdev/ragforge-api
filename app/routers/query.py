import json
import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.models import QueryRequest
from app.services.retrieval import stream_query, reset_conversation

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query")
async def query(
    request: QueryRequest,
):
    async def event_generator():
        try:
            async for event in stream_query(
                question=request.question,
                conversation_id=request.conversation_id,
            ):
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"]),
                }
        except Exception as e:
            logger.exception("Error during query streaming")
            yield {
                "event": "error",
                "data": json.dumps({"detail": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.post("/conversation/reset")
async def reset_conversation_endpoint(
    conversation_id: str,
):
    reset_conversation(conversation_id)
    return {"status": "ok", "conversation_id": conversation_id}
