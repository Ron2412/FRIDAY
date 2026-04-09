import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_calendar_service():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('data/credentials/token.json'):
        creds = Credentials.from_authorized_user_file('data/credentials/token.json', SCOPES)
        
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('data/credentials/credentials.json'):
                print("[Calendar Error] credentials.json not found in data/credentials/ directory.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                'data/credentials/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('data/credentials/token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"[Calendar Error] Could not construct service: {e}")
        return None

def get_today_events():
    """
    Fetches events from the user's primary calendar for the remainder of today.
    Returns a formatted string summary.
    """
    service = get_calendar_service()
    if not service:
        return "System Context: User wants to know about calendar, but calendar is not configured. Ask them to set it up."

    try:
        now = datetime.datetime.utcnow()
        # end of day today
        end_of_day = now.replace(hour=23, minute=59, second=59)
        
        now_str = now.isoformat() + 'Z'  # 'Z' indicates UTC time
        end_str = end_of_day.isoformat() + 'Z'

        events_result = service.events().list(
            calendarId='primary', 
            timeMin=now_str,
            timeMax=end_str,
            maxResults=10, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        if not events:
            return "System Context: The user has no upcoming events for the rest of today."

        context_lines = ["System Context: The user has the following events today:"]
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'Untitled Event')
            # simplify parsing format
            context_lines.append(f"- {summary} at {start}")
            
        return "\n".join(context_lines)

    except Exception as e:
        print(f"[Calendar API Error] {e}")
        return "System Context: An error occurred while retrieving the calendar."

if __name__ == "__main__":
    print(get_today_events())
