import imaplib
import email
from email.header import decode_header
import json
import os
import re
from datetime import datetime
import google.generativeai as genai

# --- Configuration (replace with your details) ---
IMAP_SERVER = "imap.gmail.com"
EMAIL_ADDRESS = "srihithapulapa1@gmail.com" 
APP_PASSWORD = "my app password" # APP password generated from Google Account

# Path to save the JSON file
JSON_FILE_PATH = "static/emails.json"

# List of keywords to filter emails
FILTER_KEYWORDS = ["Support", "Query", "Request", "Help"]

# Configure the Gemini API with your key
GEMINI_API_KEY = "my api key"  # Genmini API key from google ai studio
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

def classify_email_with_llm(text):
    """
    Uses the Gemini LLM to classify email sentiment and priority.
    """
    prompt = f"""
    Analyze the following email’s subject and body.  

    1. **Sentiment Classification:** Classify as **Positive, Negative, or Neutral**.  
    - **Positive:** appreciation, excitement, constructive requests, congratulations, offers of help.  
    - **Negative:** complaints, issues, dissatisfaction, problems, errors, failures.  
    - **Neutral:** purely informational or factual content.  

    2. **Priority Determination:** Classify as **Urgent or Not urgent**.  
    - **Urgent:** email requires immediate action or affects critical operations, deadlines, or clients.  
    - **Not urgent:** routine, informational, congratulatory, or for future planning.  

    **Do not rely only on keywords. Consider context, tone, and implied urgency.** **Examples:** - **Subject:** “Immediate Help Required: System Outage Affecting Operations”  
    **Body:** “We are currently experiencing a system outage impacting critical operations. Please assist immediately.”  
    **Output:** Sentiment: Negative, Priority: Urgent, AI_Label: System Outage  

    - **Subject:** “Query on Approval: Excited to Start New Project Initiative”  
    **Body:** “I have a question regarding the approval process for our new project. Looking forward to getting started.”  
    **Output:** Sentiment: Positive, Priority: Not urgent, AI_Label: Query on Approval  

    - **Subject:** “Help Needed to Celebrate Team Success in Upcoming Event”  
    **Body:** “We’d love your help in organizing a small celebration for the team’s recent achievement.”  
    **Output:** Sentiment: Positive, Priority: Not urgent, AI_Label: Team Celebration  

    - **Subject:** “Support Needed: Minor Glitches in Reporting Dashboard”  
    **Body:** “Some small glitches have appeared in the dashboard. No major impact, but support would be appreciated.”  
    **Output:** Sentiment: Negative, Priority: Not urgent, AI_Label: Glitch correction in Reporting Dashboard  

    - **Subject:** “Urgent Query Regarding Invoice Discrepancy #4521”  
    **Body:** “I noticed a discrepancy in Invoice #4521 and would appreciate your immediate clarification.”  
    **Output:** Sentiment: Neutral, Priority: Urgent, AI_Label: Invoice Discrepancy  

    **Now classify the following email:** Output Format: Output a single line exactly in this format:
    Sentiment: [Positive/Negative/Neutral], Priority: [Urgent/Not urgent], AI_Label: Request Asked
    Email content:
    Subject: {text[:100]}
    Body: {text[100:2000]}
    """
    try:
        response = model.generate_content(prompt)
        result_string = response.text.strip()
        
        # Parse the string to a dictionary
        parts = result_string.split(', ')
        classification = {
            "sentiment": parts[0].split(': ')[1],
            "priority": parts[1].split(': ')[1],
            "ai_label": parts[2].split(': ')[1]
        }
        return classification
    except Exception as e:
        print(f"LLM classification failed: {e}")
        return {
            "sentiment": "Neutral",
            "priority": "Not urgent",
            "ai_label": "LLM Classification Failed"
        }

def generate_llm_response(subject, body, sentiment, priority):
    """
    Uses the Gemini LLM to generate a draft response based on the email.
    """
    prompt = f"""
    Based on the following email, draft a professional and helpful response. The email is classified as having a sentiment of '{sentiment}' and a priority of '{priority}'.

    Your response should be:
    - Concise and to the point.
    - Acknowledge the user's message.
    - If the priority is 'Urgent', state that you are looking into it immediately.
    - If the sentiment is 'Negative', be apologetic and empathetic.
    - If the sentiment is 'Positive', express gratitude or enthusiasm.
    - End with a professional closing.

    Email Subject: {subject}
    Email Body: {body[:1000]}

    Response:
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"LLM response generation failed: {e}")
        return "Could not generate an automated response."


def clean_text(text):
    """Clean up text to make it suitable for a JSON field."""
    if not isinstance(text, str):
        return ""
    # Remove excessive whitespace and control characters
    cleaned = re.sub(r'\s+', ' ', text).strip()
    return cleaned

def get_emails():
    """Connects to the email server, fetches emails, and returns a list of dictionaries."""
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    try:
        mail.login(EMAIL_ADDRESS, APP_PASSWORD)
    except imaplib.IMAP4.error as e:
        print(f"Login failed. Check your email address and app password. Error: {e}")
        return []

    # Check the result of the select command
    status, messages = mail.select("INBOX")
    if status != 'OK':
        print(f"Failed to select mailbox. Status: {status}")
        mail.logout()
        return []

    # Fetch all emails and reverse the order to get the most recent ones first
    status, messages = mail.search(None, "ALL")
    email_ids = messages[0].split()
    latest_emails = email_ids[-20:] # Fetch more emails to find the 10 relevant ones
    latest_emails.reverse()

    emails_data = []
    
    for email_id in latest_emails:
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        # Decode headers to get readable strings
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding if encoding else "utf-8")
        
        # Check if the email subject contains any of the filter keywords
        if not any(keyword.lower() in subject.lower() for keyword in FILTER_KEYWORDS):
            continue # Skip this email if it doesn't match the filter

        sender, encoding = decode_header(msg.get("From"))[0]
        if isinstance(sender, bytes):
            sender = sender.decode(encoding if encoding else "utf-8")
        
        sender_email = re.search(r'<(.*?)>', sender)
        sender_email = sender_email.group(1) if sender_email else sender

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body = part.get_payload(decode=True).decode()
                    except:
                        body = "Could not decode email body."
                    break
        else:
            try:
                body = msg.get_payload(decode=True).decode()
            except:
                body = "Could not decode email body."

        # Perform classification with the LLM
        combined_text = subject + " " + body
        classification = classify_email_with_llm(combined_text)
        
        # Generate a response based on the classification and content
        llm_response = generate_llm_response(subject, body, classification["sentiment"], classification["priority"])

        date_received_str = msg.get("Date")
        date_obj = email.utils.parsedate_to_datetime(date_received_str)
        date_received = date_obj.isoformat()

        # Create the email dictionary
        emails_data.append({
            "id": int(email_id),
            "sender_email": clean_text(sender_email),
            "subject": clean_text(subject),
            "body": clean_text(body)[:500] + "..." if len(clean_text(body)) > 500 else clean_text(body),
            "date_received": date_received,
            "status": "pending",
            "is_read": False,
            "priority": classification["priority"],
            "sentiment": classification["sentiment"],
            "ai_label": classification["ai_label"],
            "extracted_info": {
                "contact_details": None,
                "request": "A generic request for now."
            },
            "llm_response": llm_response # Add the new field here
        })
        if len(emails_data) >= 10: # Stop after processing 10 filtered emails
            break
            
    mail.logout()
    return emails_data

def update_json_file(data):
    """Writes the given data to a JSON file."""
    directory = os.path.dirname(JSON_FILE_PATH)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    
    with open(JSON_FILE_PATH, "w") as f:
        json.dump(data, f, indent=4)
        print(f"Successfully updated {JSON_FILE_PATH}")

if __name__ == "__main__":
    email_data = get_emails()
    if email_data:
        update_json_file(email_data)