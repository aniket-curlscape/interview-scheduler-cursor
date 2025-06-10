from datetime import date, timedelta, time, datetime
from typing import List, Tuple, Dict, Iterator, Optional
import pytz

from .models import Candidate, Schedule, Slot
from .exceptions import SchedulingError
from .utils.dates import is_business_day, get_timezone


class ScheduleGenerator:
    """Core algorithm for generating interview schedules.
    
    Generates 2 interviews per working day within business hours,
    avoiding lunch break, weekends, and existing calendar events.
    """
    
    DEFAULT_INTERVIEW_LENGTH = timedelta(minutes=45)
    LUNCH_BREAK_START = time(12, 0)
    LUNCH_BREAK_END = time(13, 0)
    DAILY_CAP = 2
    
    def __init__(self, *, tz: str, business_hours: Tuple[time, time], calendar_client=None):
        """Initialize scheduler with timezone and business hours.
        
        Args:
            tz: IANA timezone name (e.g., 'Asia/Kolkata')
            business_hours: Tuple of (start_time, end_time)
            calendar_client: Optional GoogleCalendarClient for checking availability
        """
        self.tz = get_timezone(tz)
        self.start_of_day, self.end_of_day = business_hours
        self.calendar_client = calendar_client
        
        if self.start_of_day >= self.end_of_day:
            raise ValueError("Start of day must be before end of day")
    
    def generate(self, candidates: List[Candidate], window: Tuple[date, date]) -> Schedule:
        """Generate interview schedule for candidates within date window.
        
        Args:
            candidates: List of candidates to schedule
            window: Tuple of (start_date, end_date)
            
        Returns:
            Schedule object with assigned slots
            
        Raises:
            SchedulingError: If not enough capacity for all candidates
        """
        start_date, end_date = window
        
        if start_date > end_date:
            raise ValueError("Start date must be before end date")
        
        if not candidates:
            raise ValueError("No candidates provided")
        
        available_slots = list(self._generate_available_slots(start_date, end_date))
        
        if len(candidates) > len(available_slots):
            required_days = (len(candidates) + self.DAILY_CAP - 1) // self.DAILY_CAP
            available_days = len([d for d in self._date_range(start_date, end_date) 
                                if is_business_day(d)])
            extra_days = required_days - available_days
            
            calendar_note = " (after checking calendar availability)" if self.calendar_client else ""
            
            raise SchedulingError(
                f"Not enough capacity for {len(candidates)} candidates{calendar_note}. "
                f"Found {len(available_slots)} available slots, need {len(candidates)}. "
                f"Please extend the date window, reduce the candidate list, or reschedule existing conflicts."
            )
        
        candidate_map = self._assign(candidates, iter(available_slots))
        
        return Schedule(
            window_start=start_date,
            window_end=end_date,
            slots=available_slots[:len(candidates)],
            candidate_map=candidate_map
        )
    
    def _generate_available_slots(self, start_date: date, end_date: date) -> Iterator[Slot]:
        """Generate all available interview slots within the date range, checking calendar availability."""
        for current_date in self._date_range(start_date, end_date):
            if not is_business_day(current_date):
                continue
            
            daily_slots = list(self._generate_daily_slots(current_date))
            
            # If we have a calendar client, filter out conflicting slots
            if self.calendar_client:
                available_daily_slots = []
                for slot in daily_slots:
                    try:
                        if self.calendar_client.is_time_slot_available(slot):
                            available_daily_slots.append(slot)
                    except Exception as e:
                        # Log the error but continue with the slot (fail-safe approach)
                        print(f"Warning: Could not check calendar availability for slot {slot.start}: {e}")
                        available_daily_slots.append(slot)
                
                for slot in available_daily_slots:
                    yield slot
            else:
                for slot in daily_slots:
                    yield slot
    
    def _generate_slots(self, start_date: date, end_date: date) -> Iterator[Slot]:
        """Generate all available interview slots within the date range."""
        for current_date in self._date_range(start_date, end_date):
            if not is_business_day(current_date):
                continue
            
            slots_for_day = list(self._generate_daily_slots(current_date))
            for slot in slots_for_day:
                yield slot
    
    def _generate_daily_slots(self, date_obj: date) -> Iterator[Slot]:
        """Generate interview slots for a single day."""
        current_time = datetime.combine(date_obj, self.start_of_day)
        current_time = self.tz.localize(current_time)
        
        end_of_day = datetime.combine(date_obj, self.end_of_day)
        end_of_day = self.tz.localize(end_of_day)
        
        slots_generated = 0
        
        while (current_time + self.DEFAULT_INTERVIEW_LENGTH <= end_of_day and 
               slots_generated < self.DAILY_CAP):
            
            slot_end = current_time + self.DEFAULT_INTERVIEW_LENGTH
            
            if self._conflicts_with_lunch(current_time, slot_end):
                lunch_end = datetime.combine(date_obj, self.LUNCH_BREAK_END)
                lunch_end = self.tz.localize(lunch_end)
                current_time = lunch_end
                continue
            
            slot = Slot(start=current_time, end=slot_end)
            yield slot
            
            slots_generated += 1
            
            current_time = slot_end + timedelta(minutes=15)
    
    def _conflicts_with_lunch(self, start: datetime, end: datetime) -> bool:
        """Check if time slot conflicts with lunch break."""
        lunch_start = datetime.combine(start.date(), self.LUNCH_BREAK_START)
        lunch_start = self.tz.localize(lunch_start)
        
        lunch_end = datetime.combine(start.date(), self.LUNCH_BREAK_END)
        lunch_end = self.tz.localize(lunch_end)
        
        return not (end <= lunch_start or start >= lunch_end)
    
    def _assign(self, candidates: List[Candidate], slot_iter: Iterator[Slot]) -> Dict[Candidate, Slot]:
        """Assign candidates to slots in deterministic order."""
        candidate_map = {}
        
        for candidate in candidates:
            try:
                slot = next(slot_iter)
                candidate_map[candidate] = slot
            except StopIteration:
                raise SchedulingError("Ran out of available slots")
        
        return candidate_map
    
    def _date_range(self, start_date: date, end_date: date) -> Iterator[date]:
        """Generate date range from start to end (inclusive)."""
        current = start_date
        while current <= end_date:
            yield current
            current += timedelta(days=1)
