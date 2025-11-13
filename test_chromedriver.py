"""
Simple test script to verify ChromeDriver is working properly.
"""
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def test_chromedriver():
    """Test ChromeDriver setup and basic functionality."""
    print("Testing ChromeDriver setup...")
    print("=" * 50)

    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')

    driver = None

    try:
        # Install and get ChromeDriver path
        print("\n1. Installing ChromeDriver...")
        driver_path = ChromeDriverManager().install()
        print(f"   ChromeDriver installed at: {driver_path}")

        # Create driver instance
        print("\n2. Creating Chrome driver instance...")
        driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
        print("   Chrome driver created successfully!")

        # Get version info
        capabilities = driver.capabilities
        print(f"\n3. Version Information:")
        print(f"   Chrome version: {capabilities.get('browserVersion', 'Unknown')}")
        print(f"   ChromeDriver version: {capabilities.get('chrome', {}).get('chromedriverVersion', 'Unknown').split()[0]}")

        # Test navigation
        print("\n4. Testing navigation...")
        driver.get("https://www.google.com")
        print(f"   Successfully navigated to: {driver.current_url}")
        print(f"   Page title: {driver.title}")

        print("\n" + "=" * 50)
        print("SUCCESS: ChromeDriver is working correctly!")
        print("=" * 50)
        return True

    except Exception as e:
        print(f"\n" + "=" * 50)
        print(f"ERROR: ChromeDriver test failed!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print("=" * 50)
        print("\nTroubleshooting steps:")
        print("1. Update Chrome browser to the latest version")
        print("2. Run: pip install --upgrade selenium webdriver-manager")
        print("3. Clear cache: python -c \"import shutil, os; shutil.rmtree(os.path.expanduser('~/.wdm'), ignore_errors=True)\"")
        print("4. Restart your computer if the issue persists")
        return False

    finally:
        if driver:
            driver.quit()
            print("\nChrome driver closed.")

if __name__ == "__main__":
    test_chromedriver()
