import re
import time
from playwright.sync_api import expect
from helpers import safe_fill, safe_sequential_fill

def test_create_and_publish_geography_create_a_new_geography_and_publish_it(page):
    ts = int(time.time() * 1000)
    page.goto('/posts/entity/geographies/geography/create')
    
    # Fill the 'Name in English ( Slug )' field
    safe_fill(page, re.compile(r'Name in English \( Slug \)'), f'qa-geo-{ts}')
    
    # Fill the 'Display Name' field
    safe_fill(page, 'Name', f'QA Geography {ts}', exact=True)
    
    # Fill the 'Summary' field
    safe_fill(page, 'Summary', f'Summary for QA Geography {ts}')
    
    # Scroll to the Content section and locate the Articles subsection
    add_articles_filter = page.get_by_role('button', name=re.compile(r'Add Filter')).nth(4)
    add_articles_filter.scroll_into_view_if_needed()
    
    # Click '+ Add Filter' under Articles
    add_articles_filter.click()
    
    # Set 'Filter by Field' to 'Geography'
    page.get_by_role('combobox', name=re.compile(r'Filter by Field')).click()
    page.get_by_title('Geography', exact=True).last.click()
    
    # Set 'Match Type' to 'Matches'
    page.get_by_role('combobox', name=re.compile(r'Match Type')).click()
    page.get_by_title('Matches', exact=True).last.click()
    
    # Select the first option available in the 'Value' dropdown
    page.get_by_role('combobox').last.click()
    value_dropdown = page.locator('.ant-select-dropdown').last
    value_dropdown.locator('.ant-select-item-option').first.wait_for(state='visible')
    value_dropdown.locator('.ant-select-item-option').first.click()
    
    # Click 'Publish'
    publish_button = page.get_by_role('button', name='Publish')
    expect(publish_button).to_be_enabled(timeout=5000)
    publish_button.click()
    
    # Verify URL matches /\/posts\/published/
    expect(page).to_have_url(re.compile(r'/posts/published/'), timeout=15000)
