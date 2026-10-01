import json
import logging
import httpx
from typing import Dict, Any, Optional
from backend.app.services.publication_contract import (
    BasePublicationProvider,
    PublicationContract,
    PublicationResult,
)

logger = logging.getLogger(__name__)

class WebflowPublicationProvider(BasePublicationProvider):
    """
    Publishes approved blog content to a Webflow CMS collection.
    """

    def __init__(self, api_key: str, site_id: str, collection_id: str):
        self.api_key = api_key
        self.site_id = site_id
        self.collection_id = collection_id
        self.base_url = "https://api.webflow.com/v2"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    async def publish(self, contract: PublicationContract) -> PublicationResult:
        try:
            # Prepare Webflow CMS item payload
            # Webflow requires field names to match the collection schema precisely.
            # We assume a standard blog post schema with 'name', 'slug', 'post-body'
            
            slug = contract.title.lower().replace(" ", "-")
            slug = "".join(c for c in slug if c.isalnum() or c == "-")
            
            payload = {
                "isArchived": False,
                "isDraft": False,
                "fieldData": {
                    "name": contract.title,
                    "slug": slug,
                    "post-body": contract.content_markdown,  # Webflow supports rich text or raw HTML
                }
            }

            url = f"{self.base_url}/collections/{self.collection_id}/items"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )

                if response.status_code in (200, 201, 202):
                    data = response.json()
                    item_id = data.get("id")
                    
                    # Webflow v2 requires publishing the item explicitly after creation
                    publish_url = f"{self.base_url}/collections/{self.collection_id}/items/publish"
                    publish_response = await client.post(
                        publish_url,
                        headers=self.headers,
                        json={"itemIds": [item_id]}
                    )
                    
                    if publish_response.status_code in (200, 201, 202):
                        return PublicationResult(
                            success=True,
                            external_reference=item_id,
                            published_url=f"https://api.webflow.com/cms/item/{item_id}",
                        )
                    else:
                        return PublicationResult(
                            success=False,
                            is_transient_error=False,
                            error_code="WEBFLOW_PUBLISH_FAILED",
                            error_message=f"Created item but failed to publish: {publish_response.text}"
                        )

                # Handle specific HTTP errors
                if response.status_code in (401, 403):
                    return PublicationResult(
                        success=False,
                        is_transient_error=False,
                        error_code="WEBFLOW_AUTH_ERROR",
                        error_message="Invalid Webflow API Key or insufficient permissions.",
                    )
                
                if response.status_code == 429:
                    return PublicationResult(
                        success=False,
                        is_transient_error=True,
                        error_code="WEBFLOW_RATE_LIMIT",
                        error_message="Webflow API rate limit exceeded.",
                    )

                return PublicationResult(
                    success=False,
                    is_transient_error=True if response.status_code >= 500 else False,
                    error_code=f"WEBFLOW_HTTP_{response.status_code}",
                    error_message=response.text,
                )

        except httpx.RequestError as e:
            logger.error(f"Network error publishing to Webflow: {e}")
            return PublicationResult(
                success=False,
                is_transient_error=True,
                error_code="WEBFLOW_NETWORK_ERROR",
                error_message=str(e),
            )
        except Exception as e:
            logger.exception(f"Unexpected error publishing to Webflow: {e}")
            return PublicationResult(
                success=False,
                is_transient_error=False,
                error_code="WEBFLOW_UNKNOWN_ERROR",
                error_message=str(e),
            )
