from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.knowledge import KnowledgeDocumentStatus


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    title: str
    original_filename: str
    content_type: str
    description: Optional[str] = None
    status: KnowledgeDocumentStatus
    processing_error: Optional[str] = None
    chunk_count: Optional[int] = 0
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentListResponse(BaseModel):
    total: int
    documents: List[KnowledgeDocumentResponse]


class KnowledgeChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    chunk_index: int
    content: str
    token_count: Optional[int] = None
    created_at: datetime


class KnowledgeRetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of relevant chunks to retrieve")
    document_ids: Optional[List[int]] = Field(default=None, description="Optional filter to specific document IDs")


class RetrievedChunkItem(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    content: str
    similarity_score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")


class KnowledgeRetrievalResponse(BaseModel):
    query: str
    total_results: int
    results: List[RetrievedChunkItem]
