import logging
from typing import List, Optional
from pydantic import BaseModel
from backend.app.models.user import User

logger = logging.getLogger(__name__)

class NotificationMessage(BaseModel):
    subject: str
    body: str
    recipient_email: str
    in_app_message: Optional[str] = None

class NotificationService:
    """
    Handles sending emails and in-app notifications.
    Currently implements a mock provider logging to stdout,
    ready to be swapped with SendGrid/AWS SES.
    """

    @classmethod
    def send_email(cls, message: NotificationMessage) -> bool:
        """Send an email notification."""
        # TODO: Implement SendGrid/SES integration here
        logger.info(f"EMAIL SENT TO {message.recipient_email} | SUBJECT: {message.subject} | BODY: {message.body}")
        return True

    @classmethod
    def send_in_app(cls, user_id: int, message: str) -> bool:
        """Send an in-app notification."""
        # TODO: Implement database insertion to a notifications table or Websocket push
        logger.info(f"IN-APP NOTIFICATION TO USER {user_id}: {message}")
        return True

    @classmethod
    def notify_reviewers_of_new_draft(cls, company_name: str, reviewers: List[User], blog_title: str):
        for reviewer in reviewers:
            msg = NotificationMessage(
                subject=f"New Blog Draft Requires Review: {blog_title}",
                body=f"Hello {reviewer.name},\n\nA new blog draft '{blog_title}' has been submitted for review in the {company_name} workspace.\nPlease log in to review and approve.",
                recipient_email=reviewer.email,
                in_app_message=f"New blog draft submitted: {blog_title}"
            )
            cls.send_email(msg)
            cls.send_in_app(reviewer.id, msg.in_app_message)
            
    @classmethod
    def notify_admin_of_access_request(cls, admin: User, requester_name: str, role_requested: str):
        msg = NotificationMessage(
            subject=f"New Access Request: {role_requested.upper()}",
            body=f"Hello {admin.name},\n\n{requester_name} has requested {role_requested} access to your workspace.\nPlease log in to your dashboard to approve or reject the request.",
            recipient_email=admin.email,
            in_app_message=f"{requester_name} requested {role_requested} access."
        )
        cls.send_email(msg)
        cls.send_in_app(admin.id, msg.in_app_message)
