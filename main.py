from __future__ import print_function
import os.path
import base64
from email.message import EmailMessage

import re

from dotenv import load_dotenv
load_dotenv()  # Load .env file
import os
from openai import OpenAI
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OpenAI API key not found.")
client = OpenAI(api_key=api_key)

from bs4 import BeautifulSoup

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

#if modifying these SCOPES, deleter token.json
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# exteracting the email body

def extract_email_body(payload):
    body = None

    # Helper: clean HTML
    def clean_html(html):
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text()

    # Recursively search through parts
    def find_parts(parts):
        nonlocal body
        for part in parts:
            mime_type = part.get('mimeType')
            data = part['body'].get('data')

            if data:
                decoded = base64.urlsafe_b64decode(data).decode("utf-8")

                if mime_type == 'text/plain':
                    body = decoded
                    return
                elif mime_type == 'text/html' and body is None:
                    body = clean_html(decoded)

            if 'parts' in part:
                find_parts(part['parts'])

    if 'parts' in payload:
        find_parts(payload['parts'])
    else:
        data = payload['body'].get('data')
        if data:
            decoded = base64.urlsafe_b64decode(data).decode("utf-8")
            if payload.get('mimeType') == 'text/html':
                body = clean_html(decoded)
            else:
                body = decoded

    return body

#summrize with GPT
def summarize_with_gpt(email_text):
    if not email_text:
        return "No content to summarize."

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages= [
                {"role": "system", "content": "You are a helpful assistant that summarizes emails."},
                {"role": "user", "content": f"Summarize this email in 1-2 sentences:\n\n{email_text}"}
            ],
            max_tokens=100,
            temperature=0.7,
        )

        # return response['choices'][0]['message']['content'].strip()
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ GPT Error: {str(e)}"



def main():
    creds = None

    #load token if exists
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', maxResults=10).execute()
    messages = results.get('messages', [])

    if not messages:
        print('No messages found.')
    else:
        print('Recent messages:\n')
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            headers = msg_data['payload']['headers']

            subject = None
            sender = None

            for header in headers:
                if header['name'] == 'Subject':
                    subject = header['value']
                if header['name'] == 'From':
                    sender = header['value']

            print("📧 Subject:", subject)
            print("👤 From:", sender)

            body = extract_email_body(msg_data['payload'])

            summary = summarize_with_gpt(body)
            print("📄 Summary:", summary)
            print("📝 Body Preview:\n", body[:200].strip() if body else "No body found.")
            print("==============\n")
    print('✅ Finished reading messages.')
