import os
import pathlib
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import google.generativeai as genai
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Directories
BASE_DIR = os.path.expanduser("scraped/screenshots")
RESPONSE_DIR = os.path.join(BASE_DIR, "gemini_analysis")
os.makedirs(RESPONSE_DIR, exist_ok=True)

# Load environment variables for Gemini and Email
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)

if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY is not set in environment variables.")
    exit(1)
if not EMAIL_USER or not EMAIL_PASS:
    logger.error("EMAIL_USER or EMAIL_PASS is not set in environment variables.")
    exit(1)

# Initialize Gemini client
try:
    genai.configure(api_key=GEMINI_API_KEY)
    client = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
    logger.info("Initialized Gemini client with API key")
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    exit(1)

# Gemini prompt (unchanged)
PROMPT = """
You are an expert social media and financial analyst tasked with evaluating a screenshot or PDF of a Twitter profile's recent posts (captured via Nitter) to identify any "juicy news"—significant, attention-grabbing, or impactful information that could influence markets, public perception, or investor sentiment. The screenshot/PDF contains tweets from a specific Twitter account, including text, images, and metadata (e.g., dates, likes). The analysis is for posts captured on May 13, 2025.

For the provided screenshot/PDF, perform the following steps:

1. Identify Juicy News:
   - Determine if there is any "juicy news" (e.g., major announcements, financial updates, leadership changes, scandals, product launches, or market-moving events).
   - Summarize the key details of the news (e.g., tweet content, company/person involved, date, and any metrics like stock price mentions or event specifics).

2. Assess Impact (if Juicy News is Found):
   - Explain the potential impact on:
     - **Stock Price**: If the account is related to a company (e.g., NSEIndia, moneycontrolcom), predict the likely direction (positive, negative, neutral) and magnitude (high, moderate, low) of the stock price movement, with a confidence level (e.g., 80%).
     - **Sector/Market**: Assess if the news could influence the broader market or sector (e.g., financial sector for NSEIndia, tech for elonmusk).
     - **Public Sentiment**: Evaluate how the news might affect public or investor perception (e.g., excitement, concern, trust).
   - Provide a cause-and-effect mechanism linking the news to its impact (e.g., how a tweet about a new product could boost stock prices).
   - Identify risks or uncertainties (e.g., unverified claims, market overreaction).

3. No Juicy News:
   - If no significant news is found, state this clearly and briefly explain why (e.g., tweets are routine updates, lack market relevance).

Output Format:
- Juicy News: [Yes/No]
- Details: [Summarize the news or explain why none was found, 100–200 words]
- Impact (if applicable):
  - Stock Price: [Direction, magnitude, confidence level, explanation]
  - Sector/Market: [Influence, explanation]
  - Public Sentiment: [Effect, explanation]
  - Risks/Uncertainties: [Any concerns or limitations]
- Username: [The Twitter handle analyzed, e.g., NSEIndia]

Constraints:
- Base your analysis solely on the provided screenshot/PDF content.
- Avoid speculative assumptions; rely on explicit tweet details and logical inferences.
- Assume the tweets are from May 2025, with potential impact on the next trading day (May 14, 2025).
- If the screenshot/PDF is unclear or lacks context, note this as a limitation.
"""

def analyze_file(file_path, username):
    ext = os.path.splitext(file_path)[1].lower()
    mime_type = "application/pdf" if ext == ".pdf" else "image/png"
    try:
        logger.info(f"Sending {file_path} for Gemini analysis")
        content = [
            {"mime_type": mime_type, "data": pathlib.Path(file_path).read_bytes()},
            {"text": PROMPT}
        ]
        response = client.generate_content(content)
        result_text = response.text or "No response received."
    except Exception as e:
        result_text = f"Error: {str(e)}"
        logger.error(f"Failed to analyze {file_path}: {e}")

    out_path = os.path.join(RESPONSE_DIR, f"{username}_analysis.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result_text)
    logger.info(f"Saved Gemini response to {out_path}")

def send_email_with_attachments():
    today = datetime.today()
    date_str = today.strftime("%Y-%m-%d")

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"Gemini Twitter Analysis Reports - {date_str}"

    body = f"""Dear Recipient,

Attached are the Gemini analysis reports for Twitter screenshots/PDFs processed on {date_str}.

Please review the attached files for detailed social media financial insights.

Best regards,
Automated Gemini Analysis System
"""
    msg.attach(MIMEText(body, 'plain'))

    # Attach all Gemini analysis txt files
    gemini_files = list(Path(RESPONSE_DIR).glob("*.txt"))
    if not gemini_files:
        logger.warning("No Gemini analysis files found to attach.")

    for file_path in gemini_files:
        try:
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
            msg.attach(part)
            logger.info(f"Attached file {file_path}")
        except Exception as e:
            logger.error(f"Failed to attach {file_path}: {e}")

    # Send email via SMTP SSL (Gmail example)
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
        logger.info(f"✅ Email sent successfully with {len(gemini_files)} attachments.")
    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")

def main():
    # Analyze all screenshots/PDFs in BASE_DIR (not subfolders)
    for filename in os.listdir(BASE_DIR):
        if not (filename.lower().endswith(".png") or filename.lower().endswith(".pdf")):
            continue
        full_path = os.path.join(BASE_DIR, filename)
        if not os.path.isfile(full_path):
            continue
        username = filename.split("_screenshot")[0]
        logger.info(f"Processing file {filename} for username {username}")
        analyze_file(full_path, username)

    logger.info("All Gemini analyses completed.")
    send_email_with_attachments()

if __name__ == "__main__":
    main()
