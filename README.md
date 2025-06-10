# Interview Scheduler CLI

A command-line tool for scheduling interviews with automatic Google Calendar integration and native email notifications.

## Features

- Import candidate lists from CSV
- Generate 2-per-day interview schedules within specified date windows
- Create Google Calendar events with Meet links
- Native Google Calendar email notifications (no SMTP required!)
- Candidates receive invites from calendar-invites-noreply@google.com
- Session resumption and step-back/forward navigation
- Configurable business hours and timezone support

## Installation

```bash
pip install -e .
```

## Quick Start

1. Initialize configuration:
```bash
interview-scheduler init
```

2. Schedule interviews:
```bash
interview-scheduler schedule candidates.csv --start 2025-06-10 --end 2025-06-20
```

3. Create calendar events and send invitations:
```bash
interview-scheduler send
```

## CSV Format

Create a CSV file with candidate information:

```csv
email,name
alice@example.com,Alice Zhang
bob@example.com,Bob Nguyen
charlie@example.com,
```

The `name` column is optional - if not provided, it will be derived from the email address.

## Configuration

The tool stores configuration in `~/.config/interview-scheduler/config.yml` including:

- Google Calendar credentials (OAuth2)
- Timezone preferences  
- Business hours

**Note:** No SMTP configuration required! Email notifications are sent natively by Google Calendar.

## Email Delivery Benefits

Using Google Calendar's native email system provides several advantages:

- **Better Deliverability**: Emails come from `calendar-invites-noreply@google.com` with Google's SPF, DKIM, and DMARC authentication
- **No "Unknown Sender" Warnings**: Recipients won't see security warnings in Gmail
- **Simplified Setup**: No need to configure SMTP servers or app passwords
- **Automatic Meet Links**: Google Meet links are automatically generated and included
- **Built-in Reminders**: Standard calendar reminders (1 day and 15 minutes before)

## Commands

- `init` - First-run configuration wizard (Google Calendar credentials only)
- `schedule` - Generate interview schedule from CSV
- `send` - Create calendar events with automatic email notifications
- `resume` - Resume interrupted session
- `reset` - Clear session state

## Demo

![Demo GIF](demo.gif)

## License

MIT License
