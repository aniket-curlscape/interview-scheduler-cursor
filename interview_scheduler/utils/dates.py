from datetime import datetime, date, time, timedelta
from typing import Tuple, Iterator
import pytz
from dateutil import parser


def parse_date(date_str: str) -> date:
    """Parse date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        try:
            return parser.parse(date_str).date()
        except Exception:
            raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")


def parse_time(time_str: str) -> time:
    """Parse time string in HH:MM format."""
    try:
        return datetime.strptime(time_str, '%H:%M').time()
    except ValueError:
        raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM")


def parse_business_hours(hours_str: str) -> Tuple[time, time]:
    """Parse business hours string like '09:00-18:00'."""
    try:
        start_str, end_str = hours_str.split('-')
        start_time = parse_time(start_str.strip())
        end_time = parse_time(end_str.strip())
        
        if start_time >= end_time:
            raise ValueError("Start time must be before end time")
        
        return start_time, end_time
    except ValueError as e:
        if "not enough values to unpack" in str(e):
            raise ValueError(f"Invalid business hours format: {hours_str}. Expected HH:MM-HH:MM")
        raise


def get_timezone(tz_name: str) -> pytz.BaseTzInfo:
    """Get timezone object from name."""
    try:
        return pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        raise ValueError(f"Unknown timezone: {tz_name}")


def is_business_day(date_obj: date) -> bool:
    """Check if date is a business day (Monday-Friday)."""
    return date_obj.weekday() < 5


def date_range(start_date: date, end_date: date) -> Iterator[date]:
    """Generate date range from start to end (inclusive)."""
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def datetime_to_rfc3339(dt: datetime) -> str:
    """Convert datetime to RFC3339 format for Google Calendar API."""
    return dt.isoformat()


def validate_date_range(start: date, end: date) -> None:
    """Validate that date range is reasonable."""
    if start > end:
        raise ValueError("Start date must be before end date")
    
    if start < date.today():
        raise ValueError("Start date cannot be in the past")
    
    if (end - start).days > 365:
        raise ValueError("Date range cannot exceed 365 days")
