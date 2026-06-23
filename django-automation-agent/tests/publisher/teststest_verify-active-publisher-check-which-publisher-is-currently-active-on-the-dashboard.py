import re
import time
from playwright.sync_api import expect
from helpers import safe_fill, safe_sequential_fill


def test_verify_active_publisher_check_which_publisher_is_currently_active_on_the_dashboard(page):
    ts = int(time.time() * 1000)
    # Navigate to the dashboard homepage
    page.goto('https://betadashboard.thepublive.com/v2')
    
    # Locate the active publisher information on the dashboard
    active_publisher = page.get_by_text('Crictoday', exact=True)
    
    # Verify the active publisher is displayed as 'Crictoday'
    expect(active_publisher).to_be_visible(timeout=15000)
