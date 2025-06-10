from typing import Any, List, Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.text import Text


console = Console()


def print_success(message: str) -> None:
    """Print success message in green."""
    console.print(f"✅ {message}", style="green")


def print_error(message: str) -> None:
    """Print error message in red."""
    console.print(f"❌ {message}", style="red")


def print_warning(message: str) -> None:
    """Print warning message in yellow."""
    console.print(f"⚠️  {message}", style="yellow")


def print_info(message: str) -> None:
    """Print info message in blue."""
    console.print(f"ℹ️  {message}", style="blue")


def prompt_text(message: str, default: Optional[str] = None, hide_input: bool = False) -> str:
    """Prompt for text input."""
    return Prompt.ask(message, default=default, password=hide_input)


def prompt_confirm(message: str, default: bool = True) -> bool:
    """Prompt for yes/no confirmation."""
    return Confirm.ask(message, default=default)


def prompt_choice(message: str, choices: List[str], default: Optional[str] = None) -> str:
    """Prompt for choice from list."""
    return Prompt.ask(message, choices=choices, default=default)


def display_schedule_table(schedule, meeting_links: dict = None) -> None:
    """Display schedule in a formatted table."""
    meeting_links = meeting_links or {}
    
    table = Table(title="Interview Schedule")
    table.add_column("Candidate", style="cyan")
    table.add_column("Email", style="blue")
    table.add_column("Date", style="green")
    table.add_column("Time", style="yellow")
    table.add_column("Meeting Link", style="magenta")
    
    for candidate, slot in schedule.candidate_map.items():
        meeting_link = meeting_links.get(candidate.email, "TBD")
        if len(meeting_link) > 50:
            meeting_link = meeting_link[:47] + "..."
        
        table.add_row(
            candidate.name or "N/A",
            candidate.email,
            slot.start.strftime('%Y-%m-%d'),
            f"{slot.start.strftime('%H:%M')} - {slot.end.strftime('%H:%M')}",
            meeting_link
        )
    
    console.print(table)


def display_panel(title: str, content: str, style: str = "blue") -> None:
    """Display content in a panel."""
    console.print(Panel(content, title=title, border_style=style))


def display_step(step_num: int, total_steps: int, description: str) -> None:
    """Display current step progress."""
    progress = f"[{step_num}/{total_steps}]"
    console.print(f"\n{progress} {description}", style="bold blue")


def print_divider() -> None:
    """Print a visual divider."""
    console.print("─" * 60, style="dim")
