import csv
from pathlib import Path
from typing import List
from .models import Candidate, Schedule


CANDIDATE_HEADERS = ["email", "name"]
SCHEDULE_HEADERS = ["email", "name", "date", "start_time", "end_time", "meeting_link"]


def read_candidates(path: Path) -> List[Candidate]:
    """Parse CSV file with candidate information.
    
    Expected format:
    email,name
    alice@example.com,Alice Zhang
    bob@example.com,Bob Nguyen
    charlie@example.com,
    
    The name column is optional.
    """
    candidates = []
    
    try:
        with open(path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            if 'email' not in reader.fieldnames:
                raise ValueError("CSV must contain 'email' column")
            
            for row_num, row in enumerate(reader, start=2):
                email = row.get('email', '').strip()
                if not email:
                    continue
                
                name = row.get('name', '').strip() or None
                
                try:
                    candidate = Candidate(email=email, name=name)
                    candidates.append(candidate)
                except Exception as e:
                    raise ValueError(f"Invalid candidate data on row {row_num}: {e}")
    
    except FileNotFoundError:
        raise FileNotFoundError(f"Candidate file not found: {path}")
    except Exception as e:
        raise ValueError(f"Error reading candidate file: {e}")
    
    if not candidates:
        raise ValueError("No valid candidates found in CSV file")
    
    return candidates


def write_schedule(path: Path, schedule: Schedule, meeting_links: dict = None) -> None:
    """Export approved schedule to CSV for auditing/sharing.
    
    Output format:
    email,name,date,start_time,end_time,meeting_link
    alice@example.com,Alice Zhang,2025-06-11,09:00,09:45,https://meet.google.com/abc-defg-hij
    """
    meeting_links = meeting_links or {}
    
    try:
        with open(path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=SCHEDULE_HEADERS)
            writer.writeheader()
            
            for candidate, slot in schedule.candidate_map.items():
                writer.writerow({
                    'email': candidate.email,
                    'name': candidate.name,
                    'date': slot.start.strftime('%Y-%m-%d'),
                    'start_time': slot.start.strftime('%H:%M'),
                    'end_time': slot.end.strftime('%H:%M'),
                    'meeting_link': meeting_links.get(candidate.email, '')
                })
    
    except Exception as e:
        raise ValueError(f"Error writing schedule file: {e}")
