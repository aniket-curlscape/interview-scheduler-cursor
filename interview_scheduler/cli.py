#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from datetime import date, time
from typing import Optional, Dict, Any

import typer
from rich.console import Console
from rich.traceback import install

from . import __version__
from .config import ConfigManager
from .csv_utils import read_candidates, write_schedule
from .scheduler import ScheduleGenerator
from .calendar import GoogleCalendarClient
from .models import Schedule
from .exceptions import (
    InterviewSchedulerError, ConfigError, SchedulingError, 
    CalendarError
)
from .utils.dates import parse_date, parse_business_hours
from .utils.prompts import (
    console, print_success, print_error, print_warning, print_info,
    prompt_text, prompt_confirm, prompt_choice, display_schedule_table,
    display_step, print_divider
)

install(show_locals=True)

app = typer.Typer(
    name="interview-scheduler",
    help="CLI tool for scheduling interviews with Google Calendar integration",
    add_completion=False,
)

SESSION_FILE = Path.home() / ".interview-scheduler-session.json"


class SessionManager:
    """Manages session state for step-back/forward navigation."""
    
    def __init__(self, session_file: Path = None):
        self.session_file = session_file or SESSION_FILE
        self.data: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> None:
        """Load session from file."""
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}
    
    def save(self) -> None:
        """Save session to file."""
        try:
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.session_file, 'w') as f:
                json.dump(self.data, f, indent=2, default=str)
        except Exception as e:
            print_error(f"Failed to save session: {e}")
    
    def clear(self) -> None:
        """Clear session data."""
        self.data = {}
        if self.session_file.exists():
            self.session_file.unlink()
    
    def get(self, key: str, default=None):
        """Get session value."""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set session value and save."""
        self.data[key] = value
        self.save()


session = SessionManager(SESSION_FILE)


class BackAction(Exception):
    """Exception to handle step-back navigation."""
    pass


def handle_errors(func):
    """Decorator to handle common exceptions."""
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            print_warning("\nOperation cancelled by user")
            session.save()
            raise typer.Exit(1)
        except BackAction:
            print_info("Going back to previous step...")
            return
        except InterviewSchedulerError as e:
            print_error(str(e))
            raise typer.Exit(1)
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            raise typer.Exit(1)
    return wrapper


@app.command()
@handle_errors
def init():
    """Initialize configuration for first-time setup."""
    print_info("Welcome to Interview Scheduler CLI!")
    print_info("This wizard will help you configure the application.")
    print_divider()
    
    config = ConfigManager()
    
    if config.is_configured():
        if not prompt_confirm("Configuration already exists. Reconfigure?", default=False):
            print_success("Using existing configuration.")
            return
    
    display_step(1, 3, "Setting up timezone and business hours")
    
    timezone = prompt_text("Enter your timezone", default="Asia/Kolkata")
    config.set_timezone(timezone)
    
    business_hours = prompt_text("Enter business hours (HH:MM-HH:MM)", default="09:00-18:00")
    try:
        start_time, end_time = parse_business_hours(business_hours)
        config.set_business_hours(start_time.strftime("%H:%M"), end_time.strftime("%H:%M"))
    except ValueError as e:
        print_error(f"Invalid business hours: {e}")
        raise typer.Exit(1)
    
    display_step(2, 3, "Setting up Google Calendar credentials")
    
    print_info("You need to provide Google OAuth credentials for Calendar access.")
    print_info("1. Go to https://console.cloud.google.com/")
    print_info("2. Create a new project or select existing one")
    print_info("3. Enable Google Calendar API")
    print_info("4. Create OAuth 2.0 credentials (Desktop application)")
    print_info("5. Download the credentials JSON file")
    
    creds_path = prompt_text("Enter path to Google credentials JSON file")
    creds_file = Path(creds_path).expanduser()
    
    if not creds_file.exists():
        print_error(f"Credentials file not found: {creds_file}")
        raise typer.Exit(1)
    
    try:
        with open(creds_file, 'r') as f:
            creds_content = f.read()
        config.set_google_credentials(creds_content)
        print_success("Google credentials saved successfully!")
    except Exception as e:
        print_error(f"Failed to read credentials file: {e}")
        raise typer.Exit(1)
    
    display_step(3, 3, "Testing configuration")
    
    try:
        creds = config.get_google_credentials()
        calendar_client = GoogleCalendarClient(creds)
        if calendar_client.test_connection():
            print_success("Google Calendar connection test passed!")
        else:
            print_warning("Google Calendar test failed - please check credentials")
    except Exception as e:
        print_warning(f"Google Calendar test failed: {e}")
    
    print_divider()
    print_success("Configuration completed successfully!")
    print_info("You can now use 'interview-scheduler schedule' to create schedules.")
    print_info("Then use 'interview-scheduler send' to create calendar events.")


@app.command()
@handle_errors
def schedule(
    csv_file: Path = typer.Argument(..., help="Path to CSV file with candidate emails"),
    start: str = typer.Option(..., "--start", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., "--end", help="End date (YYYY-MM-DD)"),
    business_hours: str = typer.Option("09:00-18:00", "--business-hours", help="Business hours (HH:MM-HH:MM)")
):
    """Generate interview schedule from CSV file."""
    config = ConfigManager()
    
    if not config.is_configured():
        print_error("Configuration not found. Please run 'interview-scheduler init' first.")
        raise typer.Exit(1)
    
    display_step(1, 3, "Loading candidates from CSV")
    
    try:
        candidates = read_candidates(csv_file)
        print_success(f"Loaded {len(candidates)} candidates")
    except Exception as e:
        print_error(f"Failed to read candidates: {e}")
        raise typer.Exit(1)
    
    display_step(2, 3, "Generating interview schedule")
    
    try:
        start_date = parse_date(start)
        end_date = parse_date(end)
        
        # Use configured business hours if none specified, otherwise use command line parameter
        if business_hours == "09:00-18:00":  # Default value, use config
            config_start, config_end = config.get_business_hours()
            start_time, end_time = parse_business_hours(f"{config_start}-{config_end}")
            print_info(f"Using configured business hours: {config_start}-{config_end}")
        else:  # Custom value provided, use it and update config
            start_time, end_time = parse_business_hours(business_hours)
            config.set_business_hours(start_time.strftime("%H:%M"), end_time.strftime("%H:%M"))
            print_info(f"Using custom business hours: {business_hours}")
        
        # Initialize calendar client for availability checking
        try:
            creds = config.get_google_credentials()
            calendar_client = GoogleCalendarClient(creds)
            print_info("Calendar availability checking enabled")
        except Exception as e:
            print_warning(f"Calendar client initialization failed: {e}")
            print_warning("Proceeding without calendar availability checking")
            calendar_client = None
        
        scheduler = ScheduleGenerator(
            tz=config.get_timezone(),
            business_hours=(start_time, end_time),
            calendar_client=calendar_client
        )
        
        schedule_obj = scheduler.generate(candidates, (start_date, end_date))
        print_success(f"Generated schedule with {len(schedule_obj.slots)} interview slots")
        
    except SchedulingError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Failed to generate schedule: {e}")
        raise typer.Exit(1)
    
    display_step(3, 3, "Reviewing generated schedule")
    
    display_schedule_table(schedule_obj)
    
    if not prompt_confirm("Approve this schedule?", default=True):
        print_info("Schedule not approved. Exiting.")
        raise typer.Exit(0)
    
    session.set("schedule", {
        "candidates": [{"email": c.email, "name": c.name} for c in candidates],
        "slots": [{"start": s.start.isoformat(), "end": s.end.isoformat()} for s in schedule_obj.slots],
        "candidate_map": {c.email: {"start": s.start.isoformat(), "end": s.end.isoformat()} 
                         for c, s in schedule_obj.candidate_map.items()},
        "window_start": schedule_obj.window_start.isoformat(),
        "window_end": schedule_obj.window_end.isoformat()
    })
    
    session.set("step", "schedule_approved")
    
    print_success("Schedule approved and saved!")
    print_info("Next step: Run 'interview-scheduler send' to create calendar events.")


@app.command()
@handle_errors
def send():
    """Create calendar events and send invitations for approved schedule."""
    config = ConfigManager()
    
    if not config.is_configured():
        print_error("Configuration not found. Please run 'interview-scheduler init' first.")
        raise typer.Exit(1)
    
    if session.get("step") != "schedule_approved":
        print_error("No approved schedule found. Please run 'interview-scheduler schedule' first.")
        raise typer.Exit(1)
    
    schedule_data = session.get("schedule")
    if not schedule_data:
        print_error("Schedule data not found. Please run 'interview-scheduler schedule' first.")
        raise typer.Exit(1)
    
    from datetime import datetime
    from .models import Candidate, Slot
    
    print_info("Creating calendar events with automatic Google Calendar invitations.")
    print_info("Candidates will receive emails from calendar-invites-noreply@google.com")
    print_divider()
    
    if not prompt_confirm("Proceed with creating calendar events?", default=True):
        print_info("Calendar event creation cancelled.")
        raise typer.Exit(0)
    
    display_step(1, 2, "Creating calendar events and sending invitations")
    
    try:
        creds = config.get_google_credentials()
        calendar_client = GoogleCalendarClient(creds)
        
        meeting_links = {}
        event_results = {"created": 0, "failed": 0, "errors": []}
        
        for candidate_data in schedule_data["candidates"]:
            candidate = Candidate(email=candidate_data["email"], name=candidate_data["name"])
            slot_data = schedule_data["candidate_map"][candidate.email]
            slot = Slot(
                start=datetime.fromisoformat(slot_data["start"]),
                end=datetime.fromisoformat(slot_data["end"])
            )
            
            try:
                meeting_link = calendar_client.create_event(
                    slot=slot,
                    candidate=candidate
                )
                meeting_links[candidate.email] = meeting_link
                event_results["created"] += 1
                print_info(f"✓ Created calendar event for {candidate.name or candidate.email}")
                
            except Exception as e:
                event_results["failed"] += 1
                event_results["errors"].append({
                    "email": candidate.email,
                    "error": str(e)
                })
                print_error(f"✗ Failed to create calendar event for {candidate.email}: {e}")
                meeting_links[candidate.email] = "TBD"
        
        session.set("meeting_links", meeting_links)
        session.set("event_results", event_results)
        
    except Exception as e:
        print_error(f"Calendar event creation failed: {e}")
        raise typer.Exit(1)
    
    display_step(2, 2, "Exporting schedule")
    
    output_file = Path("interview_schedule.csv")
    try:
        from .models import Schedule
        
        candidates = [Candidate(email=c["email"], name=c["name"]) for c in schedule_data["candidates"]]
        slots = [Slot(start=datetime.fromisoformat(s["start"]), end=datetime.fromisoformat(s["end"])) 
                for s in schedule_data["slots"]]
        candidate_map = {}
        for c in candidates:
            slot_data = schedule_data["candidate_map"][c.email]
            candidate_map[c] = Slot(
                start=datetime.fromisoformat(slot_data["start"]),
                end=datetime.fromisoformat(slot_data["end"])
            )
        
        schedule_obj = Schedule(
            window_start=datetime.fromisoformat(schedule_data["window_start"]).date(),
            window_end=datetime.fromisoformat(schedule_data["window_end"]).date(),
            slots=slots,
            candidate_map=candidate_map
        )
        
        write_schedule(output_file, schedule_obj, meeting_links)
        print_success(f"Schedule exported to {output_file}")
        
    except Exception as e:
        print_warning(f"Failed to export schedule: {e}")
    
    print_divider()
    print_success(f"Process completed!")
    print_info(f"Calendar events created: {event_results['created']}")
    print_info("Candidates will receive email invitations from Google Calendar")
    if event_results['failed'] > 0:
        print_warning(f"Calendar events failed: {event_results['failed']}")
        for error in event_results['errors']:
            print_error(f"  {error['email']}: {error['error']}")
    
    session.set("step", "completed")


@app.command()
@handle_errors
def resume():
    """Resume interrupted session."""
    current_step = session.get("step")
    
    if not current_step:
        print_info("No session to resume.")
        return
    
    print_info(f"Resuming session at step: {current_step}")
    
    if current_step == "schedule_approved":
        print_info("You have an approved schedule. Run 'interview-scheduler send' to proceed.")
    elif current_step == "completed":
        print_success("Previous session was completed successfully!")
        
        event_results = session.get("event_results", {})
        if event_results:
            print_info(f"Calendar events created: {event_results.get('created', 0)}")
            if event_results.get('failed', 0) > 0:
                print_warning(f"Calendar events failed: {event_results['failed']}")
    else:
        print_info(f"Unknown step: {current_step}")


@app.command()
@handle_errors
def reset():
    """Clear session state."""
    if session.get("step"):
        if prompt_confirm("This will clear all session data. Continue?", default=False):
            session.clear()
            print_success("Session cleared successfully!")
        else:
            print_info("Reset cancelled.")
    else:
        print_info("No session data to clear.")


def version_callback(value: bool):
    if value:
        console.print("Interview Scheduler CLI v0.1.0")
        raise typer.Exit(0)

@app.callback()
def main(
    version: Optional[bool] = typer.Option(None, "--version", "-v", callback=version_callback, help="Show version and exit")
):
    """Interview Scheduler CLI - Schedule interviews with Google Calendar integration."""
    pass


if __name__ == "__main__":
    app()
