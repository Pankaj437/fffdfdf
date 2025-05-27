import os
import smtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

# ==== CONFIGURATION ====
EMAIL_USER = os.getenv('EMAIL_USER')  # Your Gmail (e.g., example@gmail.com)
EMAIL_PASS = os.getenv('EMAIL_PASS')  # Gmail App Password
EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)  # Send to self if not set
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('gemini_email.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Set API Key for Gemini
os.environ['GOOGLE_API_KEY'] = GEMINI_API_KEY

try:
    client = genai.Client()
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    client = None

MODEL_ID = "gemini-2.5-flash-preview-05-20"
today = datetime.now().strftime("%Y-%m-%d")

def fetch_and_clean_pulse():
    try:
        url = "https://pulse.zerodha.com/"
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove scripts and styles
        for tag in soup(['script', 'style']):
            tag.decompose()

        text = soup.get_text(separator=' ', strip=True)
        text = ' '.join(text.split())  # Collapse whitespace
        return text
    except Exception as e:
        logger.error(f"Failed to fetch or clean Pulse: {e}")
        return None

def summarize_with_gemini(html_text):
    prompt = f"""
You are a financial analyst. The following is raw HTML text extracted from Pulse (Zerodha's financial news feed). Summarize the top 5 most relevant financial news stories involving Indian companies today. Focus on impactful developments like M&A, funding, government policy, regulatory changes, or significant market moves.

Keep the summary clean, accurate, and useful for a market investor or trader. Use markdown format in a table like:

| Title | Summary | Source |
|-------|---------|--------|

If no relevant stories are found, explain that too. Below is the text:

\"\"\"{html_text[:15000]}\"\"\"
"""

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=GenerateContentConfig(
                tools=[Tool(google_search=GoogleSearch())],
                thinking_config=genai.types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=1024
                ),
                response_modalities=["TEXT"]
            )
        )
        full_text = ""
        for part in response.candidates[0].content.parts:
            if part.text:
                full_text += part.text.strip() + "\n"
        return full_text
    except Exception as e:
        logger.error(f"Gemini summarization failed: {e}")
        return f"Gemini summarization error: {e}"

def send_email(body_text):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"Pulse Zerodha News Summary - {today}"

    msg.attach(MIMEText(body_text, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
        logger.info("Email sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        return False

def main():
    if not client:
        logger.error("Gemini client not initialized.")
        return

    logger.info("Fetching Pulse Zerodha content...")
    pulse_text = fetch_and_clean_pulse()
    if not pulse_text:
        send_email("Failed to fetch or clean data from Pulse Zerodha.")
        return

    logger.info("Sending content to Gemini for summarization...")
    summary = summarize_with_gemini(pulse_text)

    logger.info("Sending summary email...")
    if not send_email(summary):
        logger.error("Summary email failed to send.")

if __name__ == "__main__":
    main()
