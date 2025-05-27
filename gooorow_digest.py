import os
import requests
import json
import smtplib
from email.mime.text import MIMEText
import base64
import google.generativeai as genai
import logging
import time
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_TO = os.getenv('EMAIL_TO', 'enormouspan@gmail.com')  # Default to provided email

# Validate environment variables
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY is not set in environment variables.")
    exit(1)
if not EMAIL_USER or not EMAIL_PASS:
    logger.error("EMAIL_USER or EMAIL_PASS is not set in environment variables.")
    exit(1)

# Initialize Gemini client
try:
    client = genai.Client()  # API key is automatically loaded from GEMINI_API_KEY
    logger.info("Initialized Gemini client with API key")
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    exit(1)

# Gemini model
MODEL_ID = "gemini-1.5-flash"

def fetch_digest_and_summarize_with_email():
    summary = ""
    error_message = ""

    try:
        # Step 1: Fetch the latest daily digest from Groww CMS API
        url = "https://cmsapi.groww.in/api/v1/dailydigests?_limit=1&_start=0"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Origin": "https://groww.in",
            "Connection": "keep-alive",
            "Referer": "https://groww.in/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Priority": "u=0",
            "TE": "trailers"
        }
        logger.info("Fetching data from Groww CMS API")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch Groww CMS API: HTTP {response.status_code}")

        json_content = response.json()
        if not json_content or len(json_content) == 0:
            raise Exception("No digest data returned from Groww CMS API.")

        digest_content = json.dumps(json_content[0])  # Use the first digest item
        logger.info("Successfully fetched digest data")

        # Step 2: Send JSON content to Gemini API with retry logic
        gemini_response = send_json_to_gemini_with_retry(digest_content)
        logger.info("Received response from Gemini API")

        # Step 3: Extract and format summary
        if gemini_response.text:
            summary = gemini_response.text
            logger.info(f"Gemini response: {summary[:100]}...")  # Log first 100 chars for debugging
            # Remove markdown code blocks and clean up
            summary = summary.replace("```json\n", "").replace("```", "").strip()
            
            # Try parsing as JSON for structured formatting
            try:
                json_response = json.loads(summary)
                summary = json.dumps(json_response, indent=2)
            except ValueError:
                pass  # Use cleaned text as-is if not JSON

            # Format summary for email
            summary = format_summary_for_email(summary)
        else:
            error_message = "No analysis returned by Gemini API."

    except Exception as e:
        error_message = f"Error: {str(e)}"
        logger.error(error_message)

    # Step 4: Send email with summary or error
    subject = "Groww Daily Digest" if summary else "Groww Digest Analysis Failed"
    body = f"Groww Daily Digest Analysis\n\n{summary}" if summary else f"Failed to generate analysis.\nError: {error_message}"
    send_email(EMAIL_TO, subject, body)
    logger.info(f"Email sent with subject: {subject}")

def format_summary_for_email(summary):
    # Split the summary into sections based on headers (e.g., ## Key Themes)
    sections = [s for s in summary.split("## ") if s.strip()]
    formatted = ""

    for section in sections:
        # Clean up markdown and format for plain text
        cleaned_section = (section.replace("**", "")
                          .replace("*", "-")
                          .replace("^- ", "  - ")
                          .replace("\n\s*\n", "\n\n")
                          .strip())
        
        section_title = cleaned_section.split("\n")[0]
        cleaned_section = cleaned_section.replace(section_title, "").strip()
        formatted += f"=== {section_title} ===\n\n{cleaned_section}\n\n"

    return formatted

def send_json_to_gemini_with_retry(json_content, max_retries=3, delay=5):
    prompt = """*** Please take your time to think critically and respond with accuracy, as this is my primary goal ***
You are an expert AI financial news analyst tasked with analyzing the JSON content from the Groww CMS API, which contains the Groww Daily Digest, a summary of financial market updates, news, and stock movements.

Your goal is to extract key information from the JSON data and present it in a concise, structured, and email-friendly plain text summary. Focus ONLY on the main content, such as market updates (e.g., sensex, nifty, top_gainers, top_losers, about_market), news articles (news field), and stock updates. IGNORE metadata (e.g., id, slug, date) unless it directly relates to the news context (e.g., date of the digest). Parse any embedded HTML in fields like top_gainers, top_losers, or news.description to extract text content.

Please structure your analysis into the following sections, using the exact header format shown (e.g., "=== Key Themes ==="):

1.  === Overall Market Pulse ===
    *   Provide a brief (1-2 sentence) overview of the general market sentiment (e.g., Bullish 📈, Bearish 📉, Mixed/Neutral 📊) based on fields like about_market, sensex, nifty, and top_gainers/top_losers.
    *   Mention major indices (e.g., Sensex, Nifty) or market drivers (e.g., sector performance) if prominent.

2.  === Key Themes (2-4) ===
    *   Identify 2-4 dominant topics or recurring themes across the digest (e.g., "RBI Dividend Payout," "FMCG Sector Rally," "Global Market Trends").
    *   For each theme, provide a 1-2 sentence explanation based on news, stock updates, or market data.
    *   Use a relevant emoji for each theme if appropriate.

3.  === Top News Highlights (Max 5) ===
    *   Select up to 5 of the most significant or impactful news items from the news and stock_updates fields.
    *   For each item:
        -   Provide a concise summary (1-2 sentences).
        -   Indicate its sentiment (e.g., Positive 📈, Negative 📉, Neutral 📰).
        -   If a specific company or stock is the primary subject, mention it.

4.  === Significant Stock Mentions ===
    *   Identify 1-5 stocks from top_gainers, top_losers, or news/stock_updates with significant positive news (e.g., strong earnings, bonus issue). Briefly state the news and use 📈.
    *   Identify 1-5 stocks with significant negative news (e.g., price drop, poor results). Briefly state the news and use 📉.
    *   If no specific stocks are highlighted for major movements, state "No specific stocks prominently featured for major gains/losses."

5.  === Named Entities Spotlight (3-5) ===
    *   Extract 3-5 key named entities (companies, organizations, or key persons) from news, stock_updates, top_gainers, or top_losers that are central to the digest.
    *   For each, provide a brief (1 phrase or sentence) context of their relevance.

6.  === Potential Implications for Investors (1-3 points) ===
    *   Based on the digest, outline 1-3 potential implications or considerations for investors (e.g., "Monitor FMCG stocks for continued momentum," "Caution advised for pharma stocks due to declines").

IMPORTANT FORMATTING INSTRUCTIONS:
*   Use plain text exclusively.
*   Use the exact section headers as specified above (e.g., "=== Overall Market Pulse ===").
*   Use bullet points ("- ") for lists within sections.
*   Use emojis sparingly and appropriately to enhance readability.
*   Ensure the entire response is a single block of text ready for an email body.
*   Do NOT use markdown code blocks (like ```json ... ``` or ```text ... ```).
*   Be concise and human-readable, targeting 200-400 words total.
*   If the JSON includes HTML (e.g., in top_gainers or news.description), extract the text content and ignore formatting tags.
"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Sending JSON content to Gemini API (Attempt {attempt + 1}/{max_retries})")
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=[
                    {"mime_type": "text/plain", "data": prompt.encode('utf-8')},
                    {"mime_type": "application/json", "data": base64.b64encode(json_content.encode()).decode()}
                ]
            )
            return response
        except Exception as e:
            logger.error(f"Gemini API attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                raise Exception(f"Gemini API failed after {max_retries} attempts: {e}")

def send_email(to_address, subject, body):
    msg = MIMEText(body)
    msg['From'] = EMAIL_USER
    msg['To'] = to_address
    msg['Subject'] = subject

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, to_address, msg.as_string())
        logger.info("Email sent successfully")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

if __name__ == "__main__":
    fetch_digest_and_summarize_with_email()
