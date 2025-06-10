"""Custom exceptions for the Interview Scheduler CLI."""


class InterviewSchedulerError(Exception):
    """Base exception for all interview scheduler errors."""
    pass


class ConfigError(InterviewSchedulerError):
    """Raised when there's an issue with configuration."""
    pass


class SchedulingError(InterviewSchedulerError):
    """Raised when scheduling constraints cannot be satisfied."""
    pass


class CalendarError(InterviewSchedulerError):
    """Raised when there's an issue with Google Calendar operations."""
    pass


class EmailError(InterviewSchedulerError):
    """Raised when there's an issue with email operations."""
    pass


class TemplateError(InterviewSchedulerError):
    """Raised when there's an issue with template rendering."""
    pass


class SessionError(InterviewSchedulerError):
    """Raised when there's an issue with session management."""
    pass
