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
***mainly focus on latest news***
You are an expert AI financial news analyst. Your task is to analyze the provided HTML content from pulse.zerodha.com, a financial news aggregator.
Your goal is to extract key information and present it in a concise, structured, and email-friendly plain text summary.
Focus ONLY on the main news articles and summaries presented. IGNORE navigation bars, sidebars, advertisements, footers, disclaimers, and any non-article content.

Please structure your analysis into the following sections, using the exact header format shown (e.g., "=== Key Themes ==="):

1.  === Overall Market Pulse ===
    *   Provide a brief (1-2 sentence) overview of the general market sentiment (e.g., Bullish 📈, Bearish 📉, Mixed/Neutral 📊) as suggested by the headlines and summaries.
    *   Mention any major indices or market drivers if prominent.

2.  === Key Themes (2-4) ===
    *   Identify 2-4 dominant topics or recurring themes across the news items (e.g., "RBI Policy Impact," "Sectoral Rally in IT," "Global Inflation Concerns").
    *   For each theme, provide a 1-2 sentence explanation.
    *   Use a relevant emoji for each theme if appropriate.

3.  === Top News Highlights (Max 5) ===
    *   Select up to 5 of the most significant or impactful news items.
    *   For each item:
        -   Provide a concise summary (1-2 sentences).
        -   Indicate its sentiment (e.g., Positive 📈, Negative 📉, Neutral 📰).
        -   If a specific company or stock is the primary subject, mention it.

4.  === Significant Stock Mentions ===
    *   Identify 1-5 stocks prominently featured for significant positive news (e.g., strong earnings, new contract, positive outlook). Briefly state the news and use 📈.
    *   Identify 1-5 stocks prominently featured for significant negative news (e.g., poor results, investigation, downgrade). Briefly state the news and use 📉.
    *   If no specific stocks are clearly highlighted for major movements, state "No specific stocks prominently featured for major gains/losses."

5.  === Named Entities Spotlight (3-5) ===
    *   Extract 3-5 key named entities (companies, organizations, key persons if mentioned significantly) that are central to the day's news.
    *   For each, provide a brief (1 phrase or sentence) context of their relevance in today's news.

6.  === Potential Implications for Investors (1-3 points) ===
    *   Based on the overall news, briefly outline 1-3 potential implications or things investors might consider (e.g., "Increased volatility expected in banking stocks," "Potential opportunities in renewable energy sector").

IMPORTANT FORMATTING INSTRUCTIONS:
*   Use plain text exclusively.
*   Use the exact section headers as specified above (e.g., "=== Overall Market Pulse ===").
*   Use bullet points ("- ") for lists within sections.
*   Use emojis sparingly and appropriately as suggested to enhance readability.
*   Ensure the entire response is a single block of text ready for an email body.
*   Do NOT use markdown code blocks (like \`\`\`json ... \`\`\` or \`\`\`text ... \`\`\`).
*   Be concise and human-readable.


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
                    thinking_budget=10000
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
