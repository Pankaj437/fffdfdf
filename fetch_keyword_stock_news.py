import csv
import time
import feedparser
import urllib.parse
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def read_nifty50_companies(csv_file):
    """Read company names and symbols from the Nifty 50 CSV file."""
    companies = []
    try:
        with open(csv_file, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                companies.append({
                    'name': row['Company Name'],
                    'symbol': row['Symbol']
                })
        logger.info(f"Successfully read {len(companies)} companies from {csv_file}")
        return companies
    except FileNotFoundError:
        logger.error(f"CSV file {csv_file} not found")
        return []
    except KeyError as e:
        logger.error(f"Missing expected column in CSV: {e}")
        return []
    except Exception as e:
        logger.error(f"Error reading CSV file: {e}")
        return []

def fetch_news_for_company(company_name, symbol):
    """Fetch news titles for a given company using Google News RSS."""
    try:
        # Encode company name and symbol for URL
        encoded_company = urllib.parse.quote(company_name)
        encoded_symbol = urllib.parse.quote(symbol)
        # Construct Google News RSS URL with company name, symbol, and 'stock' keyword for last 3 hours
        rss_url = f"https://news.google.com/rss/search?q={encoded_company}%20when%3A3h&hl=en-IN&gl=IN&ceid=IN%3Aen"
        logger.info(f"Fetching news for {company_name} ({symbol}) from {rss_url}")

        # Parse RSS feed
        feed = feedparser.parse(rss_url)

        # Collect titles
        titles = []
        if feed.entries:
            print(f"\nNews for {company_name} ({symbol}):")
            for entry in feed.entries:
                titles.append(entry.title)
                # Print news to console
                print(f"Title: {entry.title}")
                print(f"Link: {entry.link}")
                print(f"Published: {entry.published}")
                print("-" * 50)
        else:
            print(f"No news found for {company_name} ({symbol}) in the last 3 hours.")

        return titles
    except Exception as e:
        logger.error(f"Error fetching news for {company_name} ({symbol}): {e}")
        return []

def save_all_news(companies, output_file):
    """Save all companies' news titles to a single text file."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for i, company in enumerate(companies):
                titles = fetch_news_for_company(company['name'], company['symbol'])
                if titles:
                    f.write(f"Stock: {company['name']}\n")
                    for j, title in enumerate(titles, 1):
                        f.write(f"{j}. {title}\n")
                    f.write("\n")  # Add blank line between companies
                else:
                    f.write(f"Stock: {company['name']}\nNo news found.\n\n")

                # Wait for 10 seconds before fetching news for the next company (except for the last one)
                if i < len(companies) - 1:
                    logger.info("Waiting for 10 seconds before next fetch...")
                    time.sleep(10)

        logger.info(f"Saved all news to {output_file}")
    except Exception as e:
        logger.error(f"Error saving to {output_file}: {e}")

def main():
    csv_file = "n0.csv"
    output_file = "all_stock_news.txt"
    companies = read_nifty50_companies(csv_file)

    if not companies:
        logger.error("No companies to process. Exiting.")
        return

    save_all_news(companies, output_file)

if __name__ == "__main__":
    main()
