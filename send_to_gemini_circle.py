import os
import smtplib
import logging
from google import genai
from google.genai.types import GenerateContentConfig
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ==== CONFIGURATION ====
EMAIL_USER = os.getenv('EMAIL_USER')  # Your email (e.g., example@gmail.com)
EMAIL_PASS = os.getenv('EMAIL_PASS')  # Your email app password
EMAIL_TO = os.getenv('EMAIL_TO', EMAIL_USER)  # Recipient (default to self)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_FILE = "processed_stock_news.txt"  # Path to news file

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

# Read news file content
def read_news_file():
    """
    Read the entire content of all_stock_news.txt as a string.
    Returns:
        str: File content or error message if file not found.
    """
    try:
        if os.path.exists(NEWS_FILE):
            with open(NEWS_FILE, 'r', encoding='utf-8') as file:
                content = file.read().strip()
            logger.info(f"Loaded news content from {NEWS_FILE}")
            return content if content else "No news titles available from the provided file."
        else:
            logger.warning(f"News file {NEWS_FILE} not found.")
            return "No news titles available from the provided file."
    except Exception as e:
        logger.error(f"Error reading news file: {e}")
        return f"Error reading news file: {str(e)}"

# Read news file content to use as the prompt
today = datetime.now().strftime("%Y-%m-%d")
news_prompt = read_news_file()

def send_email(response_text):
    """
    Send an email with the Gemini response or error message.
    Args:
        response_text (str): Response from news file analysis or error message.
    Returns:
        bool: True if email sent successfully, False otherwise.
    """
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"Indian Corporate News Analysis - {today}"

    body = f"=== Indian Corporate News Analysis ===\n\n"
    body += f"**Best News Item from File**\n{response_text}\n\n"
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
    Main function to query Gemini API with news file content and send response via email.
    """
    if not client:
        error_msg = "Failed to initialize Gemini client. Check API key and network."
        logger.error(error_msg)
        send_email(error_msg)
        return

    try:
        # Query Gemini API with news file content
        logger.info("Querying Gemini API for news file analysis...")
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=news_prompt,
            config=GenerateContentConfig(
                thinking_config=genai.types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=10000
                ),
                response_modalities=["TEXT"]
            )
        )

        # Extract response
        response_text = ""
        for part in response.candidates[0].content.parts:
            if not part.text:
                continue
            if part.thought:
                response_text += f"Thought summary:\n{part.text}\n\n"
            else:
                response_text += f"Answer:\n{part.text}\n\n"

        # Send email with response
        if send_email(response_text):
            logger.info("Corporate news analysis report emailed successfully.")
        else:
            logger.error("Failed to send corporate news analysis report.")

    except Exception as e:
        error_msg = f"Error querying Gemini API: {str(e)}"
        logger.error(error_msg)
        send_email(error_msg)

if __name__ == "__main__":
    main()
