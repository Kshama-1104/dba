from typing import Optional
import httpx
from sqlalchemy.orm import Session

from backend.app.services.publication_contract import BasePublicationProvider
from backend.app.services.wordpress_provider import WordPressPublicationProvider


def get_publication_provider(
    db: Session,
    client: Optional[httpx.AsyncClient] = None,
    worker_id: Optional[str] = None,
) -> BasePublicationProvider:
    """
    Return the active BasePublicationProvider implementation.
    Wires WordPressPublicationProvider with database session and optional HTTP client.
    """
    return WordPressPublicationProvider(
        db=db,
        client=client,
        worker_id=worker_id,
    )
