import pathlib
import yaml
import os
from typing import Dict, Any, Optional
from appdirs import user_config_dir
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from pathlib import Path

from .exceptions import ConfigError


CONFIG_DIR = Path.home() / ".config" / "interview-scheduler"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def get_calendar_service():
    """Get Google Calendar service with proper authentication."""
    config = ConfigManager()
    creds = config.get_google_credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


class ConfigManager:
    """Manages configuration and credentials for the interview scheduler."""
    
    CONFIG_PATH = pathlib.Path(user_config_dir("interview-scheduler")) / "config.yml"
    CREDENTIALS_PATH = pathlib.Path(user_config_dir("interview-scheduler")) / "credentials.json"
    TOKEN_PATH = pathlib.Path(user_config_dir("interview-scheduler")) / "token.json"
    
    SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/gmail.send'
    ]
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.load()
    
    def load(self) -> None:
        """Load configuration from file."""
        if self.CONFIG_PATH.exists():
            try:
                with open(self.CONFIG_PATH, 'r') as f:
                    self._data = yaml.safe_load(f) or {}
            except Exception as e:
                raise ConfigError(f"Failed to load config: {e}")
    
    def save(self) -> None:
        """Save configuration to file."""
        try:
            with open(self.CONFIG_PATH, 'w') as f:
                yaml.safe_dump(self._data, f, default_flow_style=False)
            os.chmod(self.CONFIG_PATH, 0o600)
        except Exception as e:
            raise ConfigError(f"Failed to save config: {e}")
    
    def get_google_credentials(self) -> Credentials:
        """Get Google OAuth credentials, refreshing if necessary."""
        creds = None
        
        if self.TOKEN_PATH.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.TOKEN_PATH), self.SCOPES)
            except Exception:
                pass
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None
            
            if not creds:
                if not self.CREDENTIALS_PATH.exists():
                    raise ConfigError(
                        "Google credentials not found. Please run 'interview-scheduler init' first."
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.CREDENTIALS_PATH), self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            with open(self.TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
            os.chmod(self.TOKEN_PATH, 0o600)
        
        return creds
    
    def set_google_credentials(self, credentials_content: str) -> None:
        """Set Google OAuth client credentials."""
        try:
            with open(self.CREDENTIALS_PATH, 'w') as f:
                f.write(credentials_content)
            os.chmod(self.CREDENTIALS_PATH, 0o600)
        except Exception as e:
            raise ConfigError(f"Failed to save Google credentials: {e}")
    
    def get_smtp_settings(self) -> Dict[str, Any]:
        """Get SMTP settings."""
        return self._data.get('smtp', {})
    
    def set_smtp_settings(self, host: str, port: int, user: str, app_password: str) -> None:
        """Set SMTP settings."""
        self._data['smtp'] = {
            'host': host,
            'port': port,
            'user': user,
            'password': app_password
        }
        self.save()
    
    def get_timezone(self) -> str:
        """Get configured timezone."""
        return self._data.get('timezone', 'Asia/Kolkata')
    
    def set_timezone(self, tz_name: str) -> None:
        """Set timezone."""
        self._data['timezone'] = tz_name
        self.save()
    
    def get_business_hours(self) -> tuple[str, str]:
        """Get business hours as (start, end) time strings."""
        hours = self._data.get('business_hours', {'start': '09:00', 'end': '18:00'})
        return hours['start'], hours['end']
    
    def set_business_hours(self, start: str, end: str) -> None:
        """Set business hours."""
        self._data['business_hours'] = {'start': start, 'end': end}
        self.save()
    
    def is_configured(self) -> bool:
        """Check if basic configuration is complete."""
        return (
            self.CREDENTIALS_PATH.exists() and
            'timezone' in self._data and
            'business_hours' in self._data
        )
