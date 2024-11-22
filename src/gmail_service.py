import os
import pickle
import time
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64
from datetime import datetime
import traceback

# Rest of the code remains the same...

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

# Path to the credentials file and token file
CREDENTIALS_FILE = 'credentials/credentials.json'
TOKEN_FILE = 'token.pickle'

def get_gmail_service():
    """Initialize and return Gmail service"""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            flow.redirect_uri = "http://localhost:8080"
            creds = flow.run_local_server(port=8080)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)
    return service

def get_full_email_content(service, msg_id):
    """Get complete email content including body"""
    try:
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        
        if 'payload' in msg:
            parts = [msg['payload']]
            body = ""
            
            while parts:
                part = parts.pop()
                
                if 'parts' in part:
                    parts.extend(part['parts'])
                
                if 'body' in part and 'data' in part['body']:
                    body += base64.urlsafe_b64decode(part['body']['data']).decode()
            
            return body.strip()
            
        return msg.get('snippet', '')
    except Exception as e:
        print(f"Error getting email content: {str(e)}")
        return None

def fetch_new_emails(service, start_time):
    """Fetch new unread emails"""
    try:
        results = service.users().messages().list(
            userId='me',
            q='is:unread'
        ).execute()
        
        messages = results.get('messages', [])
        new_emails = []
        
        for message in messages:
            msg = service.users().messages().get(
                userId='me', 
                id=message['id'], 
                format='full'
            ).execute()
            
            email_timestamp = int(msg['internalDate']) // 1000
            
            if email_timestamp > start_time:
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'No Sender')
                message_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), None)
                thread_id = msg.get('threadId')

                new_emails.append({
                    'id': message['id'],
                    'sender': sender,
                    'subject': subject,
                    'content': get_full_email_content(service, message['id']),
                    'timestamp': email_timestamp,
                    'threadId': thread_id,
                    'message_id': message_id
                })
        
        return new_emails
    
    except Exception as e:
        print(f"Error fetching emails: {str(e)}")
        traceback.print_exc()
        return []
    
    except Exception as e:
        print(f"Error fetching emails: {str(e)}")
        return []

def send_email_reply(service, to, subject, body_text, thread_id=None, attachment_path=None):
    """Send email reply with optional attachment and maintain threading"""
    try:
        message = MIMEMultipart()
        message['to'] = to
        
        # Don't add 'Re:' if subject already has it
        if not subject.lower().startswith('re:'):
            subject = 'Re: ' + subject
        message['subject'] = subject
        
        # Add In-Reply-To and References headers for threading
        if thread_id:
            # Get the original message to get Message-ID
            original_msg = service.users().messages().get(
                userId='me', 
                id=thread_id, 
                format='metadata',
                metadataHeaders=['Message-ID', 'References']
            ).execute()
            
            headers = original_msg.get('payload', {}).get('headers', [])
            message_id = next((h['value'] for h in headers if h['name'] == 'Message-ID'), None)
            references = next((h['value'] for h in headers if h['name'] == 'References'), '')
            
            if message_id:
                if references:
                    message['References'] = f"{references} {message_id}"
                else:
                    message['References'] = message_id
                message['In-Reply-To'] = message_id

        # Add body
        message.attach(MIMEText(body_text))

        # Add attachment if provided
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as f:
                attachment = MIMEBase('application', 'pdf')
                attachment.set_payload(f.read())
                encoders.encode_base64(attachment)
                attachment.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{os.path.basename(attachment_path)}"'
                )
                message.attach(attachment)

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        message_body = {'raw': raw_message}
        
        # Add threadId to keep messages in the same thread
        if thread_id:
            message_body['threadId'] = thread_id

        service.users().messages().send(userId='me', body=message_body).execute()
        print(f"Email reply sent successfully to {to}")
        return True
    
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        traceback.print_exc()
        return False
        
def mark_as_read(service, message_id):
    """Mark email as read"""
    try:
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        return True
    except Exception as e:
        print(f"Error marking message as read: {str(e)}")
        return False    