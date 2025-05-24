import os
import time
from datetime import datetime, timedelta
from urllib.parse import quote
from playwright.sync_api import sync_playwright

# List of Nitter instances
nitter_instances = [
    "https://nitter.net/{}",
    "https://nitter.cz/{}",
    "https://nitter.it/{}"
]

def read_usernames(file_path="usernames.txt"):
    """Read usernames from a text file, one per line."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            usernames = [line.strip() for line in f if line.strip()]
        print(f"Read {len(usernames)} usernames from {file_path}: {usernames}")
        return usernames
    except Exception as e:
        print(f"Error reading usernames from {file_path}: {e}")
        return []

def create_screenshot_directory(base_path="scraped/screenshots"):
    """Create a single directory for all screenshots."""
    try:
        os.makedirs(base_path, exist_ok=True)
        print(f"Screenshot directory created or already exists: {base_path}")
    except Exception as e:
        print(f"Error creating screenshot directory: {e}")
    return base_path

def capture_screenshot(url, directory, username):
    """Capture a full-page screenshot and save as PNG."""
    screenshot_png = os.path.join(directory, f"{username}_screenshot.png")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False, args=["--no-sandbox", "--disable-gpu"])
            page = browser.new_page()

            page.on('console', lambda msg: print(f"Console message: {msg.text}"))
            page.on('pageerror', lambda msg: print(f"Page error: {msg}"))

            print(f"Navigating to {url}...")
            page.goto(url, timeout=60000)

            page.wait_for_selector("div.timeline-item", timeout=30000)

            # Scroll to load content
            page.evaluate("""
                async () => {
                    await new Promise(resolve => {
                        let totalHeight = 0;
                        const distance = 100;
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if (totalHeight >= scrollHeight) {
                                clearInterval(timer);
                                resolve();
                            }
                        }, 100);
                    });
                }
            """)

            page.screenshot(path=screenshot_png, full_page=True)
            print(f"Saved screenshot: {screenshot_png}")

            browser.close()

        except Exception as e:
            print(f"Error capturing screenshot for {url}: {e}")
            browser.close()

def main():
    """Process usernames and capture screenshots of their recent tweets."""
    usernames = read_usernames("usernames.txt")

    if not usernames:
        print("No usernames found. Please check usernames.txt.")
        return

    screenshot_dir = create_screenshot_directory()

    # Get yesterday's UTC timestamp
    yesterday = datetime.utcnow() - timedelta(days=1)
    since_time = yesterday.strftime("%Y-%m-%d_%H:%M:%S_UTC")

    for username in usernames:
        print(f"\nProcessing username: {username}")

        # Build search query string
        query = f"search?f=tweets&q=from%3A{username}+since%3A{since_time}&since=&until=&near="
        user_nitter_urls = [instance.format(query) for instance in nitter_instances]

        for url in user_nitter_urls:
            print(f"Trying {url}...")
            capture_screenshot(url, screenshot_dir, username)
            print(f"Completed processing for {username}")
            break  # Use first working Nitter instance

        print("Waiting 20 seconds before processing the next username...")
        time.sleep(30)

if __name__ == "__main__":
    main()
