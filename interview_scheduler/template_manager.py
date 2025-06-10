from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound
from pathlib import Path
from typing import List

from .models import Candidate, Slot
from .exceptions import TemplateError


class TemplateEngine:
    """Manages email templates using Jinja2."""
    
    def __init__(self, template_dir: Path):
        """Initialize template engine with template directory."""
        self.template_dir = Path(template_dir)
        
        if not self.template_dir.exists():
            raise TemplateError(f"Template directory not found: {template_dir}")
        
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            keep_trailing_newline=True,
        )
    
    def list_templates(self) -> List[str]:
        """List available template files."""
        templates = []
        for file_path in self.template_dir.glob("*.txt"):
            templates.append(file_path.name)
        for file_path in self.template_dir.glob("*.html"):
            templates.append(file_path.name)
        return sorted(templates)
    
    def render(self, template_name: str, *, candidate: Candidate, slot: Slot, meeting_link: str) -> str:
        """Render template with candidate and slot information.
        
        Args:
            template_name: Name of template file
            candidate: Candidate information
            slot: Interview slot details
            meeting_link: Google Meet or calendar link
            
        Returns:
            Rendered template content
            
        Raises:
            TemplateError: If template not found or rendering fails
        """
        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound:
            raise TemplateError(f"Template not found: {template_name}")
        
        context = {
            "name": candidate.name or candidate.email.split("@")[0],
            "email": candidate.email,
            "date": slot.start.strftime("%Y-%m-%d"),
            "time": slot.start.strftime("%H:%M %Z"),
            "start_time": slot.start.strftime("%H:%M"),
            "end_time": slot.end.strftime("%H:%M"),
            "timezone": str(slot.start.tzinfo),
            "meeting_link": meeting_link,
            "duration_minutes": int((slot.end - slot.start).total_seconds() / 60),
        }
        
        try:
            return template.render(**context)
        except Exception as e:
            raise TemplateError(f"Failed to render template {template_name}: {e}")
    
    def validate_template(self, template_name: str) -> bool:
        """Validate that template exists and can be loaded."""
        try:
            self.env.get_template(template_name)
            return True
        except TemplateNotFound:
            return False
        except Exception:
            return False
