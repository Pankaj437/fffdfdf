import os
import logging

# ==== CONFIGURATION ====
INPUT_NEWS_FILE = "all_stock_news.txt"  # Input file with stock news
OUTPUT_NEWS_FILE = "processed_stock_news.txt"  # Output file with instruction added

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('news_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Instruction to add at the top of the file
INSTRUCTION = """Here is a list of news regarding stocks. Analyze all and find the best and worst news items that can move stock prices."""

def process_news_file():
    """
    Read all_stock_news.txt, add instruction at the top, and save to processed_stock_news.txt.
    """
    try:
        # Read the input file
        if not os.path.exists(INPUT_NEWS_FILE):
            logger.warning(f"Input file {INPUT_NEWS_FILE} not found.")
            return False

        with open(INPUT_NEWS_FILE, 'r', encoding='utf-8') as file:
            content = file.read().strip()
        
        if not content:
            logger.warning(f"Input file {INPUT_NEWS_FILE} is empty.")
            return False

        logger.info(f"Successfully read content from {INPUT_NEWS_FILE}")

        # Combine instruction and content
        output_content = f"{INSTRUCTION}\n\n{content}"

        # Save to output file
        with open(OUTPUT_NEWS_FILE, 'w', encoding='utf-8') as file:
            file.write(output_content)
        
        logger.info(f"Processed content saved to {OUTPUT_NEWS_FILE}")
        return True

    except Exception as e:
        logger.error(f"Error processing news file: {e}")
        return False

def main():
    """
    Main function to process the news file.
    """
    if process_news_file():
        logger.info("News file processing completed successfully.")
    else:
        logger.error("News file processing failed.")

if __name__ == "__main__":
    main()
