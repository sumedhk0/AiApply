"""
Test script for Playwright browser automation.
Verifies that Playwright is properly installed and configured.
"""

from browser_utils import BrowserManager, create_browser


def test_playwright():
    """Test Playwright browser initialization and basic navigation."""
    print("=" * 60)
    print("Playwright Browser Test")
    print("=" * 60)

    manager = None
    try:
        print("\n1. Initializing Playwright browser...")
        manager = create_browser(headless=False)
        page = manager.setup()
        print("   ✓ Browser initialized successfully")

        print("\n2. Navigating to Google...")
        page.goto("https://www.google.com")
        print(f"   ✓ Successfully navigated to: {page.url}")
        print(f"   ✓ Page title: {page.title()}")

        print("\n3. Testing page interaction...")
        # Wait for search input
        search_input = page.locator("textarea[name='q'], input[name='q']").first
        if search_input.is_visible():
            print("   ✓ Found search input")

        print("\n4. Browser info:")
        # Get browser version from context
        browser_version = page.context.browser.version
        print(f"   ✓ Browser version: {browser_version}")

        print("\n" + "=" * 60)
        print("All tests passed! Playwright is working correctly.")
        print("=" * 60)

        print("\nClosing browser in 5 seconds...")
        page.wait_for_timeout(5000)

    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        print("\nTroubleshooting steps:")
        print("1. Run: pip install playwright")
        print("2. Run: playwright install chromium")
        print("3. Make sure no other browser instances are blocking")
        raise

    finally:
        if manager:
            manager.close()
            print("Browser closed successfully.")


def test_llm_client():
    """Test OpenRouter LLM client."""
    print("\n" + "=" * 60)
    print("OpenRouter LLM Client Test")
    print("=" * 60)

    try:
        from llm_client import get_client

        print("\n1. Initializing LLM client...")
        client = get_client()
        print("   ✓ Client initialized successfully")
        print(f"   ✓ Model: {client.model}")

        print("\n2. Testing API call...")
        response = client.create_message("Say 'Hello, World!' and nothing else.", max_tokens=50)
        print(f"   ✓ Response: {response}")

        print("\n" + "=" * 60)
        print("LLM client test passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ LLM test failed with error: {str(e)}")
        print("\nTroubleshooting steps:")
        print("1. Check your .env file has OPENROUTER_API_KEY set")
        print("2. Verify your API key is valid at https://openrouter.ai")
        raise


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--llm":
        test_llm_client()
    elif len(sys.argv) > 1 and sys.argv[1] == "--all":
        test_playwright()
        test_llm_client()
    else:
        test_playwright()
