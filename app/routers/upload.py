import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, status

from app.models import UploadResponse
from app.services.document import process_and_store_pdf, get_qdrant_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    try:
        result = await process_and_store_pdf(file_bytes, file.filename)
        return UploadResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Error processing PDF upload")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process PDF: {e}",
        )


@router.get("/collections")
async def list_collections():
    client = get_qdrant_client()
    collections = client.get_collections().collections
    result = []
    for col in collections:
        info = client.get_collection(col.name)
        points = client.scroll(
            collection_name=col.name,
            limit=100,
            with_payload=True,
            with_vectors=False,
        )
        chunks = []
        for point in points[0]:
            payload = point.payload or {}
            text = payload.get("text", "")
            metadata = payload.get("metadata", {})
            chunks.append({
                "id": str(point.id),
                "text": text[:200] + "..." if len(text) > 200 else text,
                "file_name": metadata.get("file_name"),
                "page": metadata.get("page"),
            })
        result.append({
            "collection": col.name,
            "points_count": info.points_count,
            "chunks": chunks,
        })
    return result


@router.get("/collections/{collection_name}")
async def get_collection(collection_name: str):
    client = get_qdrant_client()
    try:
        info = client.get_collection(collection_name)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{collection_name}' not found",
        )
    points = client.scroll(
        collection_name=collection_name,
        limit=100,
        with_payload=True,
        with_vectors=False,
    )
    chunks = []
    for point in points[0]:
        payload = point.payload or {}
        text = payload.get("text", "")
        metadata = payload.get("metadata", {})
        chunks.append({
            "id": str(point.id),
            "text": text,
            "file_name": metadata.get("file_name"),
            "page": metadata.get("page"),
        })
    return {
        "collection": collection_name,
        "points_count": info.points_count,
        "chunks": chunks,
    }
