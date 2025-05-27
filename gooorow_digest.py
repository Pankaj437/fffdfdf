import os
import smtplib
import logging
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ==== CONFIGURATION ====
EMAIL_USER = os.getenv('EMAIL_USER')  # Your email (e.g., example@gmail.com)
EMAIL_PASS = os.getenv('EMAIL_PASS')  # Your email app password
EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)  # Recipient (default to self)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
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

# Set your Gemini API key
os.environ['GOOGLE_API_KEY'] = GEMINI_API_KEY  # Replace with actual key or export it

try:
    client = genai.Client()
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    client = None

MODEL_ID = "gemini-2.5-flash-preview-05-20"  # Updated to a standard model ID

# Insert today's date into the prompt dynamically
today = datetime.now().strftime("%Y-%m-%d")

prompt = f"""
You are a financial news analyst tasked with identifying recent high-impact corporate news in India, focusing on company deals, mergers and acquisitions (M&A), and funding announcements. Use only information available through Google Search from the last 24 hours and prioritize relevance and credibility.

Search for:
- Indian companies announcing major deals (e.g., contracts, partnerships, or joint ventures)
- Companies involved in mergers or acquisitions (domestic or cross-border)
- Companies announcing new funding rounds (e.g., venture capital, private equity, or debt financing)
- Significant corporate developments (e.g., government-backed initiatives, regulatory approvals for deals)

Constraints:
- Focus on mid-cap and large-cap companies (market cap > ₹500 Cr)
- Exclude minor deals or funding rounds (e.g., < ₹100 Cr)
- Output only if the news is credible and reported by reliable sources (e.g., Moneycontrol, Economic Times, Mint, BloombergQuint, Business Standard, CNBC TV18)
- If insufficient fresh data is found, list the top 3 sectors with recent deal or funding activity instead

Format output in a markdown table like:

| Company | Type | Details | News Date | Source |
|---------|------|---------|-----------|--------|
| Example Ltd | M&A | Acquired XYZ for ₹1,200 Cr | May 22 | Economic Times |

If no relevant data is found, provide a brief explanation and list the top 3 sectors with recent activity.
"""

def send_email(response_text, queries=None, grounding=None):
    """
    Send an email with the Gemini response or error message as the email body.
    Args:
        response_text (str): The response text from Gemini API or error message.
        queries (list, optional): List of search queries used.
        grounding (list, optional): List of grounding metadata (sources).
    Returns:
        bool: True if email sent successfully, False otherwise.
    """
    # Create email
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"Indian Corporate News Analysis - {today}"

    # Email body
    body = f"=== Indian Corporate News Analysis ===\n\n{response_text}\n\n"
    if queries:
        body += "Search Queries Used:\n"
        for q in queries:
            body += f"- {q}\n"
    if grounding:
        body += "\nSources:\n"
        for site in grounding:
            body += f"- {site.web.title}\n"
    msg.attach(MIMEText(body, 'plain'))

    # Send email
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
    Main function to query Gemini API and send response via email.
    """
    if not client:
        error_msg = "Failed to initialize Gemini client. Check API key and network."
        logger.error(error_msg)
        send_email(error_msg)
        return

    try:
        # Define Google Search tool
        google_search_tool = Tool(google_search=GoogleSearch())

        # Query Gemini API
        logger.info("Querying Gemini API...")
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=GenerateContentConfig(
                tools=[google_search_tool],
                thinking_config=genai.types.ThinkingConfig(
                    include_thoughts=True,  # Enable thinking
                    thinking_budget=1024    # Set thinking budget
                ),
                response_modalities=["TEXT"]
            )
        )

        # Log the raw response for debugging
        logger.debug(f"Raw API response: {response}")

        # Extract response and metadata
        response_text = ""
        for part in response.candidates[0].content.parts:
            if not part.text:
                continue
            if part.thought:
                response_text += f"Thought summary:\n{part.text}\n\n"
            else:
                response_text += f"Answer:\n{part.text}\n\n"

        try:
            queries = response.candidates[0].grounding_metadata.web_search_queries if response.candidates else []
            grounding = response.candidates[0].grounding_metadata.grounding_chunks if response.candidates else []
        except (AttributeError, IndexError) as e:
            logger.warning(f"Grounding metadata not available: {e}")
            queries = []
            grounding = []

        # Send email with response
        if send_email(response_text, queries, grounding):
            logger.info("Corporate news analysis report emailed successfully.")
        else:
            logger.error("Failed to send corporate news analysis report.")

    except Exception as e:
        error_msg = f"Error querying Gemini API: {str(e)}"
        logger.error(error_msg)
        send_email(error_msg)

if __name__ == "__main__":
    main()
