from openai import OpenAI
import time
import json
import requests
import os
from datetime import datetime
from typing import Dict, Any, Union
from config import OPENAI_API_KEY, ASSISTANT_ID, CERTIFICATE_API_URL

class AssistantManager:
    # Constants
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.assistant_id = ASSISTANT_ID
        self.certificate_url = CERTIFICATE_API_URL
        # Store active threads: email -> thread_id
        self.email_threads: Dict[str, str] = {}
        print("Available methods:", dir(self))

    def get_or_create_thread(self, email: str) -> str:
        """Get existing thread or create new one for email"""
        if email in self.email_threads:
            print(f"Using existing thread for {email}: {self.email_threads[email]}")
            return self.email_threads[email]
        
        thread = self.client.beta.threads.create()
        self.email_threads[email] = thread.id
        print(f"Created new thread for {email}: {thread.id}")
        return thread.id

    def _generate_certificate(self, name: str, user_id: str, subject: str) -> Dict[str, Any]:
        """Generate or update certificate using the certificate API"""
        try:
            print(f"\nGENERATING CERTIFICATE")
            print(f"Name: {name}")
            print(f"User ID: {user_id}")
            print(f"Subject: {subject}")
            
            data = {
                "today": datetime.now().strftime("%Y-%m-%d"),
                "name": name,
                "userId": user_id,
                "subject": subject,
                "sample": True,
                "excellence": True,
                "preExcellence": False,
                "type": "pdf",
                "finalCertificate": True
            }
            
            print(f"Making API request to: {self.certificate_url}")
            
            response = requests.post(
                url=self.certificate_url,
                json=data,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                os.makedirs('certificates', exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"certificates/certificate_{name.replace(' ', '_')}_{timestamp}.pdf"
                
                with open(filename, 'wb') as f:
                    f.write(response.content)
                
                return {
                    "status": "success",
                    "message": "Certificate generated successfully",
                    "file_path": filename
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error generating certificate: {response.status_code}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Exception in certificate generation: {str(e)}"
            }

    def process_message(self, email: str, message_content: str) -> str:
        """Process a message from a user and return appropriate response"""
        try:
            print(f"\n{'='*50}")
            print("PROCESSING EMAIL")
            print(f"From: {email}")
            print(f"Content: {message_content}")
            
            thread_id = self.get_or_create_thread(email)
            
            message = self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=message_content
            )
            print(f"Added message to thread: {message.id}")

            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=self.assistant_id
            )
            print(f"Started assistant run: {run.id}")

            response = self._wait_for_run(thread_id, run.id)
            print(f"\nASSISTANT RESPONSE")
            print(response)
            return response
            
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            print(error_msg)
            return error_msg

    def _wait_for_run(self, thread_id: str, run_id: str) -> Union[str, Dict[str, str]]:
        """Wait for assistant run to complete and handle any function calls"""
        while True:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            print(f"Run status: {run.status}")

            if run.status == "completed":
                # Get and return assistant's response
                messages = self.client.beta.threads.messages.list(thread_id=thread_id)
                for msg in reversed(messages.data):
                    if msg.role == "assistant":
                        return msg.content[0].text.value

            elif run.status == "requires_action":
                print("\nPROCESSING FUNCTION CALLS")
                try:
                    available_functions = {
                        "generate_certificate": self._generate_certificate
                    }
                    
                    tool_calls = run.required_action.submit_tool_outputs.tool_calls
                    tool_outputs = []

                    for tool_call in tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        print(f"Function called: {function_name}")
                        print(f"Arguments: {function_args}")
                        
                        if function_name in available_functions:
                            function_response = available_functions[function_name](**function_args)
                            if function_response['status'] == 'success':
                                response_dict = {
                                    'message': (
                                        "Hello,\n\n"
                                        "I'm pleased to inform you that your certificate has been successfully "
                                        "generated with the updated name. I have attached the updated certificate "
                                        "to this email for your reference.\n\n"
                                        "Best regards,\nProgramming Hub Support"
                                    ),
                                    'file_path': function_response['file_path']
                                }
                                tool_outputs.append({
                                    "tool_call_id": tool_call.id,
                                    "output": json.dumps(function_response)
                                })
                                print(f"Function response: {function_response}")
                                
                                # Submit outputs back to assistant
                                self.client.beta.threads.runs.submit_tool_outputs(
                                    thread_id=thread_id,
                                    run_id=run_id,
                                    tool_outputs=tool_outputs
                                )
                                print("Submitted function outputs to assistant")
                                
                                # Return dict with message and file path
                                return response_dict
                            else:
                                error_msg = (
                                    "Hello,\n\n"
                                    "I apologize, but there was an error generating your certificate. "
                                    f"Error details: {function_response['message']}\n\n"
                                    "Please try again or contact support if the issue persists.\n\n"
                                    "Best regards,\nProgramming Hub Support"
                                )
                                return error_msg

                except Exception as e:
                    error_msg = f"Error processing function call: {str(e)}"
                    print(error_msg)
                    return error_msg

            elif run.status in ["failed", "cancelled", "expired"]:
                error_msg = f"Run failed with status: {run.status}"
                print(error_msg)
                return error_msg

            time.sleep(1)