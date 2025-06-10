from dataclasses import dataclass
from datetime import datetime, date, time
from typing import List, Dict, Optional


@dataclass(frozen=True)
class Candidate:
    """Represents a candidate for interview scheduling."""
    email: str
    name: Optional[str] = None
    
    def __post_init__(self):
        if self.name is None:
            object.__setattr__(self, 'name', self.email.split("@")[0])


@dataclass
class Slot:
    """Represents a time slot for an interview."""
    start: datetime
    end: datetime
    
    def __post_init__(self):
        if self.start >= self.end:
            raise ValueError("Start time must be before end time")


@dataclass
class Schedule:
    """Represents a complete interview schedule."""
    window_start: date
    window_end: date
    slots: List[Slot]
    candidate_map: Dict[Candidate, Slot]
    
    def __post_init__(self):
        if self.window_start > self.window_end:
            raise ValueError("Window start must be before window end")
        
        if len(self.candidate_map) != len(self.slots):
            raise ValueError("Number of candidates must match number of slots")
