"""
Browser automation utilities using Playwright.
Includes anti-detection measures for web automation.
"""
from playwright.sync_api import sync_playwright, Page, Browser, Playwright

# Try to import stealth plugin if available
try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False


class BrowserManager:
    """
    Manages Playwright browser instance with anti-detection measures.
    """

    def __init__(self, headless=False):
        self.headless = headless
        self.playwright: Playwright = None
        self.browser: Browser = None
        self.context = None
        self.page: Page = None
        self.is_remote = False

    def setup(self, remote_url=None):
        """
        Initialize browser - local or remote via Browserless.io.

        Args:
            remote_url: WebSocket URL for remote browser (e.g., Browserless.io)
                        If None, launches local browser.

        Returns:
            Page object
        """
        self.playwright = sync_playwright().start()

        if remote_url:
            # Connect to remote browser (Browserless.io)
            self.is_remote = True
            self.browser = self.playwright.chromium.connect_over_cdp(remote_url)
            # Use existing context from remote browser
            self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        else:
            # Launch local browser with stealth options
            self.is_remote = False
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--window-size=1920,1080',
                ]
            )

            # Create context with custom user agent
            self.context = self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                java_script_enabled=True,
            )

            self.page = self.context.new_page()

            # Apply stealth if available (local only)
            if HAS_STEALTH:
                stealth_sync(self.page)

            # Remove webdriver property (local only)
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

        # Set default timeout (equivalent to WebDriverWait 20 seconds)
        self.page.set_default_timeout(20000)

        return self.page

    def close(self):
        """Clean up browser resources."""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def __enter__(self):
        """Context manager entry."""
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def find_element_with_fallback(page: Page, selectors: list, timeout: int = 5000):
    """
    Try multiple selectors until one succeeds.

    Args:
        page: Playwright page object
        selectors: List of CSS/XPath selectors
        timeout: Timeout per selector attempt in milliseconds

    Returns:
        Locator if found, None otherwise
    """
    for selector in selectors:
        try:
            locator = page.locator(selector)
            locator.wait_for(timeout=timeout, state='visible')
            if locator.count() > 0:
                return locator
        except Exception:
            continue
    return None


def scroll_to_bottom(page: Page, max_scrolls: int = 10, wait_time: int = 2000):
    """
    Scroll to bottom of page to load dynamic content.

    Args:
        page: Playwright page object
        max_scrolls: Maximum number of scroll attempts
        wait_time: Wait time between scrolls in milliseconds
    """
    last_height = page.evaluate("document.body.scrollHeight")

    for _ in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(wait_time)

        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    # Scroll back to top
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(1000)


def create_browser(headless=False, remote_url=None):
    """
    Factory function to create a browser manager.

    Args:
        headless: Run in headless mode (default: False for debugging)
        remote_url: WebSocket URL for remote browser (e.g., Browserless.io)

    Returns:
        BrowserManager instance (call .setup() to initialize)
    """
    manager = BrowserManager(headless=headless)
    if remote_url:
        manager.setup(remote_url=remote_url)
    return manager
