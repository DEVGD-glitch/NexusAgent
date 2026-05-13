"""
NEXUS Email & Calendar — Email and calendar integration via MCP Google.

Supports:
  - EmailClient: send/receive emails, search emails
  - CalendarClient: create, list, update, delete calendar events
  - Integration with the notification system
  - httpx-based API calls
  - Support for Gmail API and CalDAV
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

import httpx

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailProvider(str, Enum):
    """Email service provider."""
    GMAIL = "gmail"
    CALDAV = "caldav"
    SMTP = "smtp"


class CalendarProvider(str, Enum):
    """Calendar service provider."""
    GOOGLE = "google"
    CALDAV = "caldav"


@dataclass
class EmailMessage:
    """An email message."""
    message_id: str = ""
    thread_id: str = ""
    from_addr: str = ""
    to_addr: str = ""
    subject: str = ""
    body: str = ""
    body_html: str = ""
    date: str = ""
    labels: list[str] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    unread: bool = True
    starred: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "from": self.from_addr,
            "to": self.to_addr,
            "subject": self.subject,
            "body": self.body[:5000],
            "date": self.date,
            "labels": self.labels,
            "unread": self.unread,
            "starred": self.starred,
        }


@dataclass
class CalendarEvent:
    """A calendar event."""
    event_id: str = ""
    title: str = ""
    description: str = ""
    location: str = ""
    start_time: str = ""  # ISO 8601
    end_time: str = ""    # ISO 8601
    timezone: str = "UTC"
    attendees: list[str] = field(default_factory=list)
    reminders: list[dict[str, Any]] = field(default_factory=list)
    recurrence: str = ""
    status: str = "confirmed"  # confirmed, tentative, cancelled
    organizer: str = ""
    color_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "timezone": self.timezone,
            "attendees": self.attendees,
            "status": self.status,
            "organizer": self.organizer,
        }

    def to_google_event(self) -> dict[str, Any]:
        """Convert to Google Calendar API event format."""
        event: dict[str, Any] = {
            "summary": self.title,
            "description": self.description,
            "location": self.location,
        }

        if self.start_time:
            event["start"] = {
                "dateTime": self.start_time,
                "timeZone": self.timezone,
            }
        if self.end_time:
            event["end"] = {
                "dateTime": self.end_time,
                "timeZone": self.timezone,
            }
        if self.attendees:
            event["attendees"] = [
                {"email": addr} for addr in self.attendees
            ]
        if self.reminders:
            event["reminders"] = {
                "useDefault": False,
                "overrides": self.reminders,
            }

        return event


@dataclass
class EmailSearchResult:
    """Result of an email search."""
    messages: list[EmailMessage] = field(default_factory=list)
    total_count: int = 0
    query: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages": [m.to_dict() for m in self.messages],
            "total_count": self.total_count,
            "query": self.query,
        }


class EmailClient:
    """
    Email management client.

    Supports sending and receiving emails via:
      - Gmail API (primary, via OAuth2)
      - SMTP fallback for sending
      - IMAP fallback for reading

    Usage:
        client = EmailClient()
        await client.send("user@example.com", "Hello", "Hi there!")
        results = await client.search("important project")
    """

    GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(
        self,
        provider: EmailProvider = EmailProvider.GMAIL,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
    ):
        """
        Initialize the EmailClient.

        Args:
            provider: Email provider to use.
            access_token: OAuth2 access token for Gmail API.
            refresh_token: OAuth2 refresh token for Gmail API.
            smtp_host: SMTP server hostname (for SMTP provider).
            smtp_port: SMTP server port.
            smtp_username: SMTP username.
            smtp_password: SMTP password or app-specific password.
        """
        self.settings = get_settings()
        self.provider = provider
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_username = smtp_username
        self._smtp_password = smtp_password

    def is_available(self) -> bool:
        """Check if the email client is properly configured."""
        if self.provider == EmailProvider.GMAIL:
            return bool(self._access_token)
        elif self.provider == EmailProvider.SMTP:
            return bool(self._smtp_username and self._smtp_password)
        return False

    def _get_headers(self) -> dict[str, str]:
        """Get authorization headers for Gmail API."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def _gmail_api_call(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """Make a Gmail API call."""
        url = f"{self.GMAIL_API_BASE}{path}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    response = await client.get(
                        url, params=params, headers=self._get_headers(),
                    )
                elif method == "POST":
                    response = await client.post(
                        url, json=data, headers=self._get_headers(),
                    )
                elif method == "PUT":
                    response = await client.put(
                        url, json=data, headers=self._get_headers(),
                    )
                elif method == "DELETE":
                    response = await client.delete(
                        url, headers=self._get_headers(),
                    )
                else:
                    return None

                if response.status_code in (200, 204):
                    if response.status_code == 204:
                        return {"status": "success"}
                    return response.json()
                else:
                    logger.error(
                        "Gmail API error: HTTP %d — %s",
                        response.status_code,
                        response.text[:300],
                    )
                    return None

        except Exception as e:
            logger.error("Gmail API call failed: %s", e)
            return None

    # ── Send Email ───────────────────────────────────────────────────

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Send an email.

        Args:
            to: Recipient email address.
            subject: Email subject.
            body: Plain text body.
            body_html: Optional HTML body.
            cc: CC recipients.
            bcc: BCC recipients.
            reply_to: Reply-To address.

        Returns:
            Dict with send status and message ID.
        """
        if self.provider == EmailProvider.GMAIL and self._access_token:
            return await self._send_gmail(to, subject, body, body_html, cc, bcc, reply_to)
        elif self.provider == EmailProvider.SMTP:
            return await self._send_smtp(to, subject, body, body_html, cc, bcc, reply_to)
        else:
            return {"status": "error", "message": "Email client not configured"}

    async def _send_gmail(
        self,
        to: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send email via Gmail API."""
        # Construct MIME message
        msg = MIMEMultipart("alternative")
        msg["to"] = to
        msg["subject"] = subject
        if cc:
            msg["cc"] = cc
        if bcc:
            msg["bcc"] = bcc
        if reply_to:
            msg["Reply-To"] = reply_to

        msg.attach(MIMEText(body, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        # Encode for Gmail API
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

        result = await self._gmail_api_call(
            "POST",
            "/messages/send",
            data={"raw": raw_message},
        )

        if result:
            logger.info("Email sent to %s (id=%s)", to, result.get("id", ""))
            return {
                "status": "sent",
                "message_id": result.get("id", ""),
                "thread_id": result.get("threadId", ""),
            }

        return {"status": "error", "message": "Failed to send email via Gmail API"}

    async def _send_smtp(
        self,
        to: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send email via SMTP."""
        try:
            import aiosmtplib

            msg = MIMEMultipart("alternative")
            msg["From"] = self._smtp_username
            msg["To"] = to
            msg["Subject"] = subject
            if cc:
                msg["Cc"] = cc

            msg.attach(MIMEText(body, "plain"))
            if body_html:
                msg.attach(MIMEText(body_html, "html"))

            recipients = [to]
            if cc:
                recipients.extend(cc.split(","))
            if bcc:
                recipients.extend(bcc.split(","))

            await aiosmtplib.send(
                msg,
                hostname=self._smtp_host,
                port=self._smtp_port,
                username=self._smtp_username,
                password=self._smtp_password,
                use_tls=True,
            )

            logger.info("Email sent to %s via SMTP", to)
            return {"status": "sent", "message_id": ""}

        except ImportError:
            return {"status": "error", "message": "aiosmtplib not installed. Run: pip install aiosmtplib"}
        except Exception as e:
            logger.error("SMTP send error: %s", e)
            return {"status": "error", "message": str(e)}

    # ── Read/Search Emails ───────────────────────────────────────────

    async def get_inbox(
        self,
        max_results: int = 20,
        label: str = "INBOX",
    ) -> list[EmailMessage]:
        """
        Get emails from inbox.

        Args:
            max_results: Maximum number of emails to return.
            label: Gmail label to filter by.

        Returns:
            List of EmailMessage objects.
        """
        if self.provider != EmailProvider.GMAIL or not self._access_token:
            logger.warning("Inbox access requires Gmail API with access token")
            return []

        # List message IDs
        result = await self._gmail_api_call(
            "GET",
            "/messages",
            params={
                "maxResults": max_results,
                "labelIds": [label],
            },
        )

        if not result or "messages" not in result:
            return []

        # Fetch each message
        messages: list[EmailMessage] = []
        for msg_ref in result["messages"]:
            msg_data = await self._gmail_api_call(
                "GET",
                f"/messages/{msg_ref['id']}",
                params={"format": "full"},
            )
            if msg_data:
                email = self._parse_gmail_message(msg_data)
                if email:
                    messages.append(email)

        return messages

    async def search(
        self,
        query: str,
        max_results: int = 20,
    ) -> EmailSearchResult:
        """
        Search emails using Gmail query syntax.

        Args:
            query: Gmail search query (e.g., "from:user@example.com subject:project").
            max_results: Maximum number of results.

        Returns:
            EmailSearchResult with matching messages.
        """
        if self.provider != EmailProvider.GMAIL or not self._access_token:
            return EmailSearchResult(query=query)

        result = await self._gmail_api_call(
            "GET",
            "/messages",
            params={
                "q": query,
                "maxResults": max_results,
            },
        )

        if not result or "messages" not in result:
            return EmailSearchResult(query=query)

        messages: list[EmailMessage] = []
        for msg_ref in result["messages"]:
            msg_data = await self._gmail_api_call(
                "GET",
                f"/messages/{msg_ref['id']}",
                params={"format": "full"},
            )
            if msg_data:
                email = self._parse_gmail_message(msg_data)
                if email:
                    messages.append(email)

        return EmailSearchResult(
            messages=messages,
            total_count=result.get("resultSizeEstimate", len(messages)),
            query=query,
        )

    async def get_email(self, message_id: str) -> Optional[EmailMessage]:
        """
        Get a specific email by ID.

        Args:
            message_id: Gmail message ID.

        Returns:
            EmailMessage or None.
        """
        result = await self._gmail_api_call(
            "GET",
            f"/messages/{message_id}",
            params={"format": "full"},
        )
        if result:
            return self._parse_gmail_message(result)
        return None

    async def mark_read(self, message_id: str) -> bool:
        """Mark an email as read."""
        result = await self._gmail_api_call(
            "POST",
            f"/messages/{message_id}/modify",
            data={
                "removeLabelIds": ["UNREAD"],
            },
        )
        return result is not None

    async def mark_unread(self, message_id: str) -> bool:
        """Mark an email as unread."""
        result = await self._gmail_api_call(
            "POST",
            f"/messages/{message_id}/modify",
            data={
                "addLabelIds": ["UNREAD"],
            },
        )
        return result is not None

    async def star(self, message_id: str) -> bool:
        """Star an email."""
        result = await self._gmail_api_call(
            "POST",
            f"/messages/{message_id}/modify",
            data={
                "addLabelIds": ["STARRED"],
            },
        )
        return result is not None

    async def trash(self, message_id: str) -> bool:
        """Move an email to trash."""
        result = await self._gmail_api_call(
            "POST",
            f"/messages/{message_id}/trash",
        )
        return result is not None

    # ── Gmail Parsing ────────────────────────────────────────────────

    def _parse_gmail_message(self, data: dict[str, Any]) -> Optional[EmailMessage]:
        """Parse a Gmail API message response into an EmailMessage."""
        try:
            headers = {}
            payload = data.get("payload", {})
            for header in payload.get("headers", []):
                headers[header["name"].lower()] = header["value"]

            # Extract body
            body = self._extract_gmail_body(payload)
            labels = data.get("labelIds", [])

            return EmailMessage(
                message_id=data.get("id", ""),
                thread_id=data.get("threadId", ""),
                from_addr=headers.get("from", ""),
                to_addr=headers.get("to", ""),
                subject=headers.get("subject", ""),
                body=body,
                date=headers.get("date", ""),
                labels=labels,
                unread="UNREAD" in labels,
                starred="STARRED" in labels,
            )
        except Exception as e:
            logger.error("Error parsing Gmail message: %s", e)
            return None

    def _extract_gmail_body(self, payload: dict[str, Any]) -> str:
        """Extract the text body from a Gmail message payload."""
        # Check for simple body
        if "body" in payload and "data" in payload["body"]:
            try:
                return base64.urlsafe_b64decode(
                    payload["body"]["data"]
                ).decode("utf-8", errors="replace")
            except Exception:
                pass

        # Check for multipart body
        parts = payload.get("parts", [])
        for part in parts:
            mime_type = part.get("mimeType", "")
            if mime_type == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    try:
                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    except Exception:
                        continue

        # Fallback: try first part with data
        for part in parts:
            data = part.get("body", {}).get("data", "")
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                except Exception:
                    continue

        return ""


class CalendarClient:
    """
    Calendar management client.

    Supports managing calendar events via:
      - Google Calendar API (primary, via OAuth2)
      - CalDAV (fallback)

    Usage:
        client = CalendarClient()
        event = await client.create_event(
            title="Team Meeting",
            start_time="2025-01-15T10:00:00",
            end_time="2025-01-15T11:00:00",
        )
        events = await client.list_events(days=7)
    """

    GOOGLE_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3/calendars/primary"

    def __init__(
        self,
        provider: CalendarProvider = CalendarProvider.GOOGLE,
        access_token: Optional[str] = None,
        calendar_id: str = "primary",
        caldav_url: Optional[str] = None,
    ):
        """
        Initialize the CalendarClient.

        Args:
            provider: Calendar provider to use.
            access_token: OAuth2 access token for Google Calendar API.
            calendar_id: Google Calendar ID (default: "primary").
            caldav_url: CalDAV server URL.
        """
        self.settings = get_settings()
        self.provider = provider
        self._access_token = access_token
        self._calendar_id = calendar_id
        self._caldav_url = caldav_url

    def is_available(self) -> bool:
        """Check if the calendar client is properly configured."""
        if self.provider == CalendarProvider.GOOGLE:
            return bool(self._access_token)
        elif self.provider == CalendarProvider.CALDAV:
            return bool(self._caldav_url)
        return False

    def _get_headers(self) -> dict[str, str]:
        """Get authorization headers for Google Calendar API."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def _google_api_call(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """Make a Google Calendar API call."""
        base = f"https://www.googleapis.com/calendar/v3/calendars/{self._calendar_id}"
        url = f"{base}{path}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    response = await client.get(
                        url, params=params, headers=self._get_headers(),
                    )
                elif method == "POST":
                    response = await client.post(
                        url, json=data, headers=self._get_headers(),
                    )
                elif method == "PUT":
                    response = await client.put(
                        url, json=data, headers=self._get_headers(),
                    )
                elif method == "DELETE":
                    response = await client.delete(
                        url, headers=self._get_headers(),
                    )
                else:
                    return None

                if response.status_code in (200, 204):
                    if response.status_code == 204:
                        return {"status": "success"}
                    return response.json()
                else:
                    logger.error(
                        "Google Calendar API error: HTTP %d — %s",
                        response.status_code,
                        response.text[:300],
                    )
                    return None

        except Exception as e:
            logger.error("Google Calendar API call failed: %s", e)
            return None

    # ── Event CRUD ───────────────────────────────────────────────────

    async def create_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
        timezone: str = "UTC",
        attendees: Optional[list[str]] = None,
        reminders: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Create a calendar event.

        Args:
            title: Event title/summary.
            start_time: Start time in ISO 8601 format.
            end_time: End time in ISO 8601 format.
            description: Event description.
            location: Event location.
            timezone: Timezone (default: UTC).
            attendees: List of attendee email addresses.
            reminders: List of reminder dicts (e.g., [{"method": "popup", "minutes": 10}]).

        Returns:
            Dict with created event details.
        """
        event = CalendarEvent(
            title=title,
            description=description,
            location=location,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone,
            attendees=attendees or [],
            reminders=reminders or [],
        )

        event_data = event.to_google_event()

        if self.provider == CalendarProvider.GOOGLE and self._access_token:
            result = await self._google_api_call(
                "POST",
                "/events",
                data=event_data,
            )

            if result:
                logger.info("Calendar event created: %s (id=%s)", title, result.get("id", ""))
                return {
                    "status": "created",
                    "event_id": result.get("id", ""),
                    "html_link": result.get("htmlLink", ""),
                    "title": title,
                }

            return {"status": "error", "message": "Failed to create event via Google Calendar API"}

        elif self.provider == CalendarProvider.CALDAV:
            return await self._create_caldav_event(event)

        return {"status": "error", "message": "Calendar client not configured"}

    async def list_events(
        self,
        days: int = 7,
        max_results: int = 25,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
    ) -> list[CalendarEvent]:
        """
        List upcoming calendar events.

        Args:
            days: Number of days to look ahead.
            max_results: Maximum number of events to return.
            time_min: Minimum time in ISO 8601 (overrides days).
            time_max: Maximum time in ISO 8601 (overrides days).

        Returns:
            List of CalendarEvent objects.
        """
        from datetime import datetime, timedelta, timezone as tz

        if not time_min:
            time_min = datetime.now(tz.utc).isoformat()
        if not time_max:
            time_max = (
                datetime.now(tz.utc) + timedelta(days=days)
            ).isoformat()

        if self.provider == CalendarProvider.GOOGLE and self._access_token:
            result = await self._google_api_call(
                "GET",
                "/events",
                params={
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "maxResults": max_results,
                    "singleEvents": True,
                    "orderBy": "startTime",
                },
            )

            if result and "items" in result:
                return [
                    self._parse_google_event(item)
                    for item in result["items"]
                ]

        return []

    async def get_event(self, event_id: str) -> Optional[CalendarEvent]:
        """
        Get a specific calendar event by ID.

        Args:
            event_id: Google Calendar event ID.

        Returns:
            CalendarEvent or None.
        """
        result = await self._google_api_call(
            "GET",
            f"/events/{event_id}",
        )
        if result:
            return self._parse_google_event(result)
        return None

    async def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Update an existing calendar event.

        Args:
            event_id: Event ID to update.
            title: New title (if provided).
            description: New description (if provided).
            start_time: New start time (if provided).
            end_time: New end time (if provided).
            location: New location (if provided).
            attendees: New attendee list (if provided).

        Returns:
            Dict with update status.
        """
        # Get existing event first
        existing = await self._google_api_call(
            "GET",
            f"/events/{event_id}",
        )

        if not existing:
            return {"status": "error", "message": "Event not found"}

        # Update fields
        if title is not None:
            existing["summary"] = title
        if description is not None:
            existing["description"] = description
        if start_time is not None:
            existing["start"] = {
                "dateTime": start_time,
                "timeZone": existing.get("start", {}).get("timeZone", "UTC"),
            }
        if end_time is not None:
            existing["end"] = {
                "dateTime": end_time,
                "timeZone": existing.get("end", {}).get("timeZone", "UTC"),
            }
        if location is not None:
            existing["location"] = location
        if attendees is not None:
            existing["attendees"] = [{"email": addr} for addr in attendees]

        result = await self._google_api_call(
            "PUT",
            f"/events/{event_id}",
            data=existing,
        )

        if result:
            logger.info("Calendar event updated: %s", event_id)
            return {"status": "updated", "event_id": event_id}

        return {"status": "error", "message": "Failed to update event"}

    async def delete_event(self, event_id: str) -> dict[str, Any]:
        """
        Delete a calendar event.

        Args:
            event_id: Event ID to delete.

        Returns:
            Dict with deletion status.
        """
        result = await self._google_api_call(
            "DELETE",
            f"/events/{event_id}",
        )

        if result:
            logger.info("Calendar event deleted: %s", event_id)
            return {"status": "deleted", "event_id": event_id}

        return {"status": "error", "message": "Failed to delete event"}

    # ── CalDAV Support ───────────────────────────────────────────────

    async def _create_caldav_event(self, event: CalendarEvent) -> dict[str, Any]:
        """Create an event via CalDAV."""
        try:
            import caldav

            client = caldav.DAVClient(url=self._caldav_url)
            principal = client.principal()
            calendar = principal.calendars()[0]

            # Generate iCal format
            ical = self._event_to_ical(event)
            calendar.save_event(ical)

            logger.info("CalDAV event created: %s", event.title)
            return {"status": "created", "title": event.title}

        except ImportError:
            return {
                "status": "error",
                "message": "caldav library not installed. Run: pip install caldav",
            }
        except Exception as e:
            logger.error("CalDAV event creation error: %s", e)
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _event_to_ical(event: CalendarEvent) -> str:
        """Convert a CalendarEvent to iCal format."""
        # Generate a unique ID
        uid = f"nexus-{hash(event.title + event.start_time)}@nexus"

        return (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//NEXUS//EN\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            f"DTSTART:{event.start_time.replace('-', '').replace(':', '').replace('+', 'T')}\r\n"
            f"DTEND:{event.end_time.replace('-', '').replace(':', '').replace('+', 'T')}\r\n"
            f"SUMMARY:{event.title}\r\n"
            f"DESCRIPTION:{event.description}\r\n"
            f"LOCATION:{event.location}\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )

    # ── Parsing ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_google_event(data: dict[str, Any]) -> CalendarEvent:
        """Parse a Google Calendar API event into a CalendarEvent."""
        start = data.get("start", {})
        end = data.get("end", {})

        attendees = [
            att.get("email", "")
            for att in data.get("attendees", [])
            if att.get("email")
        ]

        return CalendarEvent(
            event_id=data.get("id", ""),
            title=data.get("summary", ""),
            description=data.get("description", ""),
            location=data.get("location", ""),
            start_time=start.get("dateTime", start.get("date", "")),
            end_time=end.get("dateTime", end.get("date", "")),
            timezone=start.get("timeZone", "UTC"),
            attendees=attendees,
            status=data.get("status", "confirmed"),
            organizer=data.get("organizer", {}).get("email", ""),
        )

    # ── Notification Integration ─────────────────────────────────────

    async def get_upcoming_reminders(self, minutes: int = 60) -> list[dict[str, Any]]:
        """
        Get events starting within the specified time window.

        Useful for notification integration.

        Args:
            minutes: Minutes to look ahead.

        Returns:
            List of upcoming event dicts.
        """
        events = await self.list_events(days=1)
        now = time.time()
        cutoff = now + (minutes * 60)

        upcoming = []
        for event in events:
            if event.start_time:
                try:
                    # Parse ISO 8601 start time
                    from datetime import datetime
                    start_dt = datetime.fromisoformat(
                        event.start_time.replace("Z", "+00:00")
                    )
                    start_ts = start_dt.timestamp()
                    if now <= start_ts <= cutoff:
                        upcoming.append(event.to_dict())
                except (ValueError, TypeError):
                    continue

        return upcoming
