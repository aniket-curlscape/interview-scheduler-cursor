import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional
import time

from .models import Candidate, Slot
from .exceptions import EmailError


class EmailSender:
    """SMTP email sender for interview invitations."""
    
    SUBJECT_FMT = "Interview Invitation - {date} at {time}"
    
    def __init__(self, host: str, port: int, user: str, password: str):
        """Initialize SMTP email sender.
        
        Args:
            host: SMTP server hostname
            port: SMTP server port
            user: SMTP username
            password: SMTP password/app password
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sender_addr = user
        self._smtp = None
        
        self._connect()
        self._disconnect()
    
    def _connect(self) -> None:
        """Establish SMTP connection."""
        try:
            context = ssl.create_default_context()
            
            # Use appropriate connection method based on port
            if self.port == 465:
                # Direct SSL connection for port 465
                self._smtp = smtplib.SMTP_SSL(self.host, self.port, context=context)
            else:
                # STARTTLS connection for port 587 and others
                self._smtp = smtplib.SMTP(self.host, self.port)
                self._smtp.starttls(context=context)
            
            self._smtp.login(self.user, self.password)
        except smtplib.SMTPAuthenticationError:
            raise EmailError("SMTP authentication failed. Please check your credentials.")
        except Exception as e:
            raise EmailError(f"Failed to connect to SMTP server: {e}")
    
    def _disconnect(self) -> None:
        """Close SMTP connection."""
        if self._smtp:
            try:
                self._smtp.quit()
            except Exception:
                pass
            finally:
                self._smtp = None
    
    def send(self, *, candidate: Candidate, body: str, subject: Optional[str] = None, 
             calendar_link: str, html_body: Optional[str] = None) -> None:
        """Send email invitation to candidate.
        
        Args:
            candidate: Candidate information
            body: Email body text
            subject: Optional custom subject line
            calendar_link: Link to calendar event
            html_body: Optional HTML version of email body
            
        Raises:
            EmailError: If email sending fails
        """
        if not self._smtp:
            self._connect()
        
        try:
            msg = EmailMessage()
            msg["From"] = self.sender_addr
            msg["To"] = candidate.email
            
            if subject:
                msg["Subject"] = subject
            else:
                msg["Subject"] = f"Interview Invitation - {candidate.name}"
            
            msg.set_content(body)
            
            if html_body:
                msg.add_alternative(html_body, subtype="html")
            
            self._smtp.send_message(msg)
            
            time.sleep(0.7)  # ~90 emails per minute max
            
        except smtplib.SMTPException as e:
            raise EmailError(f"Failed to send email to {candidate.email}: {e}")
        except Exception as e:
            raise EmailError(f"Unexpected error sending email to {candidate.email}: {e}")
    
    def send_batch(self, emails: list) -> dict:
        """Send multiple emails with error tracking.
        
        Args:
            emails: List of email data dicts
            
        Returns:
            Dict with success/failure counts and failed emails
        """
        results = {
            "sent": 0,
            "failed": 0,
            "errors": []
        }
        
        self._connect()
        
        try:
            for email_data in emails:
                try:
                    self.send(**email_data)
                    results["sent"] += 1
                except EmailError as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "email": email_data["candidate"].email,
                        "error": str(e)
                    })
        finally:
            self._disconnect()
        
        return results
    
    def test_connection(self) -> bool:
        """Test SMTP connection."""
        try:
            self._connect()
            self._disconnect()
            return True
        except Exception:
            return False
    
    @classmethod
    def create_gmail_sender(cls, email: str, app_password: str) -> 'EmailSender':
        """Create EmailSender configured for Gmail.
        
        Args:
            email: Gmail address
            app_password: Gmail app password
            
        Returns:
            Configured EmailSender instance
        """
        return cls(
            host="smtp.gmail.com",
            port=587,  # Using STARTTLS port
            user=email,
            password=app_password
        )
