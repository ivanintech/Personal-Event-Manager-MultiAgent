# Directory: yt-agentic-rag/app/agents/tools/email_tool.py

"""
Email Tool - Send Emails via SMTP (configurable).
"""

import logging
import smtplib
from email.message import EmailMessage
from typing import Dict, Any

from .base import BaseTool
from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class EmailTool(BaseTool):
    """
    Tool for sending emails via SMTP (provider-agnostic: Gmail/Outlook/etc.).
    """
    
    @property
    def name(self) -> str:
        """Tool name matching TOOL_DEFINITIONS."""
        return "send_email"
    
    @property
    def description(self) -> str:
        """Human-readable description."""
        return "Send an email via SMTP"
    
    async def execute(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send an email.
        
        Args:
            to: Recipient email address
            subject: Email subject line
            body: Email body content (plain text)
            **kwargs: Additional arguments (ignored)
            
        Returns:
            Dict with success status and message details or error
        """
        # Validate required parameters
        is_valid, missing = self.validate_params(
            required=['to', 'subject', 'body'],
            provided={'to': to, 'subject': subject, 'body': body}
        )
        
        if not is_valid:
            return self._error_response(
                f"Missing required parameters: {', '.join(missing)}"
            )
        
        try:
            settings = get_settings()
            host = settings.smtp_host
            port = settings.smtp_port
            user = settings.smtp_user
            pwd = settings.smtp_pass
            sender = settings.smtp_from or user
            use_tls = settings.smtp_use_tls

            # Validate SMTP config
            if not host or not port or not user or not pwd or not sender:
                return self._error_response("SMTP config incompleta: revisa SMTP_HOST/PORT/USER/PASS/FROM")

            msg = EmailMessage()
            msg["To"] = to
            msg["From"] = sender
            msg["Subject"] = subject
            msg.set_content(body)

            if use_tls:
                with smtplib.SMTP(host, port) as server:
                    server.starttls()
                    server.login(user, pwd)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host, port) as server:
                    server.login(user, pwd)
                    server.send_message(msg)

            logger.info(f"Email sent via SMTP: To='{to}', Subject='{subject}'")
            return self._success_response(
                {
                    "to": to,
                    "subject": subject,
                    "from": sender,
                    "smtp_host": host,
                }
            )
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            return self._error_response(
                f"Failed to send email: {str(e)}"
            )


# Global tool instance
email_tool = EmailTool()

