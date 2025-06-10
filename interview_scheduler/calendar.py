from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
import time
import uuid
from typing import Optional, List, Tuple
from pathlib import Path
from datetime import datetime

from .models import Slot, Candidate
from .exceptions import CalendarError
from .template_manager import TemplateEngine
from .utils.dates import datetime_to_rfc3339


class GoogleCalendarClient:
    """Google Calendar API client for creating interview events."""
    
    EVENT_SUMMARY_FMT = "Interview with {name}"
    
    def __init__(self, credentials: Credentials):
        """Initialize Google Calendar client.
        
        Args:
            credentials: Google OAuth2 credentials
        """
        try:
            self.service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
            
            # Initialize template engine for rich event descriptions
            template_dir = Path(__file__).parent / "templates"
            self.template_engine = TemplateEngine(template_dir)
            
        except Exception as e:
            raise CalendarError(f"Failed to initialize Google Calendar client: {e}")
    
    def get_busy_times(self, time_min: datetime, time_max: datetime, 
                      calendar_id: str = "primary") -> List[Tuple[datetime, datetime]]:
        """Get busy time periods from Google Calendar.
        
        Args:
            time_min: Start datetime for the query
            time_max: End datetime for the query
            calendar_id: Calendar ID to check (default: "primary")
            
        Returns:
            List of (start, end) datetime tuples representing busy periods
            
        Raises:
            CalendarError: If freebusy query fails
        """
        try:
            # Convert datetime objects to RFC3339 format for the API
            time_min_str = datetime_to_rfc3339(time_min)
            time_max_str = datetime_to_rfc3339(time_max)
            
            body = {
                "timeMin": time_min_str,
                "timeMax": time_max_str,
                "items": [{"id": calendar_id}]
            }
            
            freebusy_result = self.service.freebusy().query(body=body).execute()
            
            busy_periods = []
            calendar_busy = freebusy_result.get("calendars", {}).get(calendar_id, {})
            
            for busy_period in calendar_busy.get("busy", []):
                start_str = busy_period["start"]
                end_str = busy_period["end"]
                
                # Parse RFC3339 datetime strings back to datetime objects
                start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                
                busy_periods.append((start_dt, end_dt))
            
            return busy_periods
            
        except HttpError as e:
            if e.resp.status == 401:
                raise CalendarError("Authentication failed. Please run 'interview-scheduler init' to re-authenticate.")
            elif e.resp.status == 403:
                raise CalendarError("Insufficient permissions to access calendar. Please check your Google Calendar API permissions.")
            else:
                raise CalendarError(f"Failed to query calendar availability: {e}")
        except Exception as e:
            raise CalendarError(f"Unexpected error querying calendar availability: {e}")
    
    def is_time_slot_available(self, slot: Slot, calendar_id: str = "primary") -> bool:
        """Check if a specific time slot is available (not conflicting with existing events).
        
        Args:
            slot: Time slot to check
            calendar_id: Calendar ID to check (default: "primary")
            
        Returns:
            True if the slot is available, False if it conflicts with existing events
            
        Raises:
            CalendarError: If availability check fails
        """
        try:
            busy_periods = self.get_busy_times(slot.start, slot.end, calendar_id)
            
            # Check if the slot overlaps with any busy period
            for busy_start, busy_end in busy_periods:
                # Two time periods overlap if one starts before the other ends
                if slot.start < busy_end and slot.end > busy_start:
                    return False
            
            return True
            
        except CalendarError:
            raise
        except Exception as e:
            raise CalendarError(f"Unexpected error checking slot availability: {e}")

    def create_event(self, *, slot: Slot, candidate: Candidate, 
                    organizer_email: Optional[str] = None) -> str:
        """Create calendar event for interview.
        
        Args:
            slot: Interview time slot
            candidate: Candidate information  
            organizer_email: Optional organizer email (not used in new flow)
            
        Returns:
            Google Meet link or event HTML link
            
        Raises:
            CalendarError: If event creation fails
        """
        event_body = self._build_event_body(slot, candidate)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                event = self.service.events().insert(
                    calendarId="primary",
                    body=event_body,
                    conferenceDataVersion=1,  # Required for automatic Meet link generation
                    sendUpdates="all"         # Google sends emails to all attendees
                ).execute()
                
                return event.get("hangoutLink") or event["htmlLink"]
                
            except HttpError as e:
                if e.resp.status == 403 and "quota" in str(e).lower():
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        time.sleep(wait_time)
                        continue
                    else:
                        raise CalendarError("Google Calendar quota exceeded. Please try again later.")
                elif e.resp.status == 401:
                    raise CalendarError("Authentication failed. Please run 'interview-scheduler init' to re-authenticate.")
                else:
                    raise CalendarError(f"Failed to create calendar event: {e}")
            except Exception as e:
                raise CalendarError(f"Unexpected error creating calendar event: {e}")
        
        raise CalendarError("Failed to create calendar event after multiple retries")
    
    def _build_event_body(self, slot: Slot, candidate: Candidate) -> dict:
        """Build event body for Google Calendar API."""
        attendees = [{"email": candidate.email}]
        
        # Use template engine to create rich event description
        try:
            # Create a temporary meeting link placeholder that will be replaced
            temp_meeting_link = "https://meet.google.com/[auto-generated]"
            
            # Render the email template for event description
            event_description = self.template_engine.render(
                "email_template.txt",
                candidate=candidate,
                slot=slot,
                meeting_link=temp_meeting_link
            )
            
            # Remove the subject line from the template since it's not needed in event description
            if event_description.startswith("Subject:"):
                lines = event_description.split('\n')
                # Find the first non-empty line after subject and start from there
                start_idx = 1
                while start_idx < len(lines) and lines[start_idx].strip() == "":
                    start_idx += 1
                event_description = '\n'.join(lines[start_idx:])
                
        except Exception as e:
            # Fallback to simple description if template rendering fails
            duration_minutes = int((slot.end - slot.start).total_seconds() / 60)
            event_description = f"""Interview scheduled with {candidate.name} ({candidate.email}).

Duration: {duration_minutes} minutes
Meeting Link: Will be generated automatically

Please join the meeting at the scheduled time."""
        
        event_body = {
            "summary": self.EVENT_SUMMARY_FMT.format(name=candidate.name),
            "description": event_description,
            "start": {
                "dateTime": datetime_to_rfc3339(slot.start),
                "timeZone": str(slot.start.tzinfo),
            },
            "end": {
                "dateTime": datetime_to_rfc3339(slot.end),
                "timeZone": str(slot.end.tzinfo),
            },
            "attendees": attendees,
            "conferenceData": {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"}
                }
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 24 * 60},  # 1 day before
                    {"method": "popup", "minutes": 15},       # 15 minutes before
                ],
            },
        }
        
        return event_body
    
    def test_connection(self) -> bool:
        """Test Google Calendar API connection."""
        try:
            self.service.calendarList().list(maxResults=1).execute()
            return True
        except Exception:
            return False
