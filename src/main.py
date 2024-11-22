import time
from datetime import datetime
import json
import os
import traceback
from gmail_service import (
    get_gmail_service, 
    fetch_new_emails, 
    send_email_reply, 
    mark_as_read
)
from assistant_manager import AssistantManager
from utils import setup_logging, log_message, log_error

def process_email(service, email_data, assistant_manager):
    """Process a single email and send a response."""
    try:
        message_id = email_data['id']
        sender = email_data['sender']
        subject = email_data['subject']
        content = email_data['content']
        thread_id = email_data.get('threadId')

        log_message(f"\n{'='*50}")
        log_message("EMAIL PROCESSING")
        log_message(f"From: {sender}")
        log_message(f"Subject: {subject}")
        
        # Get response using AssistantManager
        assistant_response = assistant_manager.process_message(
            email=sender,
            message_content=content
        )
        
        # Handle different response types
        attachment_path = None
        if isinstance(assistant_response, dict):
            response_text = assistant_response.get('message', '')
            attachment_path = assistant_response.get('file_path')
            print(f"Got attachment path: {attachment_path}")
            
            # Check if file exists
            if attachment_path and os.path.exists(attachment_path):
                print(f"PDF file exists at: {attachment_path}")
            else:
                print(f"PDF file not found at: {attachment_path}")
        else:
            response_text = assistant_response

        if send_email_reply(
            service=service,
            to=sender,
            subject=subject,
            body_text=response_text,
            thread_id=thread_id,
            attachment_path=attachment_path
        ):
            log_message(f"Successfully sent reply to {sender}")
            mark_as_read(service, message_id)
        else:
            log_error(f"Failed to send reply to {sender}")
            
    except Exception as e:
        log_error(f"Error processing email: {str(e)}")
        traceback.print_exc()  # Add full error trace

def main():
    setup_logging()
    log_message("\n" + "="*50)
    log_message("STARTING EMAIL MONITORING SERVICE")
    
    try:
        # Initialize services
        log_message("Initializing Gmail service...")
        service = get_gmail_service()
        
        log_message("Initializing Assistant Manager...")
        assistant_manager = AssistantManager()
        
        start_time = int(time.time())
        log_message(f"Service started at: {datetime.fromtimestamp(start_time)}")
        
        # Continuous monitoring loop
        while True:
            try:
                log_message("\nChecking for new emails...")
                # Fetch new emails
                new_emails = fetch_new_emails(service, start_time)
                
                if new_emails:
                    log_message(f"Found {len(new_emails)} new emails")
                    
                    # Process each new email
                    for email_data in new_emails:
                        process_email(service, email_data, assistant_manager)
                else:
                    log_message("No new emails found")
                
                # Wait before checking for new emails again
                log_message("Waiting for 60 seconds before next check...")
                time.sleep(60)
                
            except Exception as e:
                log_error(f"Error in processing cycle: {str(e)}")
                time.sleep(60)
                
    except KeyboardInterrupt:
        log_message("\nService stopped by user")
    except Exception as e:
        log_error(f"Critical error in main service: {str(e)}")
    finally:
        log_message("\nEmail monitoring service stopped")

if __name__ == '__main__':
    main()