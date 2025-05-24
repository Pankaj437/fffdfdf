import os
import pathlib
import logging
from google import genai
from google.genai import types

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Directories
BASE_DIR = os.path.expanduser("~/twitter/scraped/screenshots")
RESPONSE_DIR = os.path.join(BASE_DIR, "gemini_analysis")
os.makedirs(RESPONSE_DIR, exist_ok=True)

# Get Gemini API key from environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable not set!")
    exit(1)

# Initialize Gemini client
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
    logger.info("Initialized Gemini client")
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    exit(1)

# Your prompt to analyze screenshots/PDFs
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
    """Send a screenshot or PDF file to Gemini API and save the response."""
    ext = os.path.splitext(file_path)[1].lower()
    mime_type = "application/pdf" if ext == ".pdf" else "image/png"

    try:
        logger.info(f"Sending file {file_path} for analysis...")
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-04-17",
            contents=[
                types.Part.from_bytes(
                    data=pathlib.Path(file_path).read_bytes(),
                    mime_type=mime_type
                ),
                types.Part(text=PROMPT)
            ]
        )
        result_text = response.text or "No response received."
    except Exception as e:
        result_text = f"Error during Gemini analysis: {str(e)}"
        logger.error(result_text)

    # Save response to file
    output_path = os.path.join(RESPONSE_DIR, f"{username}_analysis.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result_text)
    logger.info(f"Saved analysis result to {output_path}")

def main():
    # Process all PNG and PDF files in screenshots directory
    for filename in os.listdir(BASE_DIR):
        if filename.endswith(".png") or filename.endswith(".pdf"):
            full_path = os.path.join(BASE_DIR, filename)
            if os.path.isfile(full_path):
                username = filename.split("_screenshot")[0]
                logger.info(f"Processing file {filename} for user {username}")
                analyze_file(full_path, username)
    logger.info("All files processed.")

if __name__ == "__main__":
    main()
