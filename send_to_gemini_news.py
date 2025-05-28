import os
import smtplib
import logging
from google import genai
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ==== CONFIGURATION ====
EMAIL_USER = os.getenv('EMAIL_USER')  # Your email (e.g., example@gmail.com)
EMAIL_PASS = os.getenv('EMAIL_PASS')  # Your email app password
EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)  # Recipient (default to self)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_FILE = "all_stock_news.txt"  # Input file from news fetching script

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gemini_email.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set Gemini API key
os.environ['GOOGLE_API_KEY'] = GEMINI_API_KEY

try:
    client = genai.Client()
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    client = None

MODEL_ID = "gemini-2.5-flash-preview-05-20"

# Insert today's date into the prompt
today = datetime.now().strftime("%Y-%m-%d")

def read_news_file(file_path):
    """Read the news titles from the input file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            news_content = f.read()
        logger.info(f"Successfully read news from {file_path}")
        return news_content
    except FileNotFoundError:
        logger.error(f"News file {file_path} not found")
        return ""
    except Exception as e:
        logger.error(f"Error reading news file: {e}")
        return ""

prompt = f"""
You are a financial news analyst tasked with identifying the most impactful corporate news for Indian companies from a provided list of news titles, focusing on company deals, mergers and acquisitions (M&A), and funding announcements. The news titles are from the last 24 hours and cover 500 Indian stocks (mid-cap and large-cap, market cap > ₹500 Cr).

Input news titles:
```
{{news_content}}
```

Instructions:
- Analyze the provided news titles to identify high-impact corporate news related to:
  - Major deals (e.g., contracts, partnerships, joint ventures)
  - Mergers or acquisitions (domestic or cross-border)
  - New funding rounds (e.g., venture capital, private equity, debt financing > ₹100 Cr)
  - Significant corporate developments (e.g., government-backed initiatives, regulatory approvals)
- Exclude minor deals or funding rounds (< ₹100 Cr) and generic market updates (e.g., "Stock market rises").
- If no high-impact news is found, list the top 3 sectors with recent deal or funding activity based on the titles.
- Format output in a markdown table:

| Company | Type | Details | News Date |
|---------|------|---------|-----------|
| Example Ltd | M&A | Acquired XYZ for ₹1,200 Cr | {today} |

- If insufficient data, provide a brief explanation and list the top 3 sectors.
- Assume all titles are from reliable sources (e.g., Moneycontrol, Economic Times).
- Limit the table to the top 5 most impactful news items to keep the output concise.
"""

def send_email(response_text):
    """
    Send an email with the Gemini response or error message.
    Args:
        response_text (str): The response text from Gemini API or error message.
    Returns:
        bool: True if email sent successfully, False otherwise.
    """
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"Indian Stock News Analysis - {today}"

    body = f"=== Indian Stock News Analysis ===\n\n{response_text}\n"
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
        logger.info("Email sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

def main():
    """
    Main function to read news file, query Gemini API, and send response via email.
    """
    if not client:
        error_msg = "Failed to initialize Gemini client. Check API key and network."
        logger.error(error_msg)
        send_email(error_msg)
        return

    # Read news titles from file
    news_content = read_news_file(NEWS_FILE)
    if not news_content:
        error_msg = f"Failed to read news file {NEWS_FILE}."
        logger.error(error_msg)
        send_email(error_msg)
        return

    # Insert news content into prompt
    full_prompt = prompt.replace("{{news_content}}", news_content)

    try:
        # Query Gemini API
        logger.info("Querying Gemini API...")
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=full_prompt,
            config=genai.types.GenerateContentConfig(
                response_modalities=["TEXT"]
            )
        )

        # Extract response
        response_text = ""
        for part in response.candidates[0].content.parts:
            if part.text:
                response_text += part.text

        if not response_text:
            response_text = "No relevant news found by Gemini."

        # Send email with response
        if send_email(response_text):
            logger.info("Stock news analysis emailed successfully.")
        else:
            logger.error("Failed to send stock news analysis report.")

    except Exception as e:
        error_msg = f"Error querying Gemini API: {str(e)}"
        logger.error(error_msg)
        send_email(error_msg)

if __name__ == "__main__":
    main()
