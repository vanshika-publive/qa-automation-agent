import re
import time
from playwright.sync_api import expect
from helpers import safe_fill, safe_sequential_fill

def test_delete_article_flow_delete_an_article_from_the_draft_list(page):
    ts = int(time.time() * 1000)
    title = f'QA Article {ts}'
    
    # Step 1: Navigate to article creation page
    page.goto('/posts/article/create')
    
    # Step 2: Generate a unique title using a millisecond timestamp
    # Already done above
    
    # Step 3: Enter the generated title into the Title field
    safe_sequential_fill(page, 'Title *', title, delay=50)
    
    # Step 4: Enter the permalink
    safe_fill(page, 'English Title ( Permalink ) *', f'qa-{ts}')
    
    # Step 5: Select the first live option for Primary Category
    cb = page.get_by_role('combobox', name='Primary Category')
    cb.click()
    cat_option = page.locator('.ant-select-dropdown').last.locator('.ant-select-item-option').first
    cat_option.wait_for(state='visible')
    cat_option.click()
    
    # Step 6: Save as Draft
    page.get_by_role('button', name='Save as Draft').click()
    
    # Step 7: Expect URL to match /posts/draft
    expect(page).to_have_url(re.compile(r'/posts/draft'), timeout=15000)
    
    # Step 8: Navigate to draft list
    page.goto('/posts/draft')
    
    # Step 9: Discard the article
    page.get_by_role('row', name=re.compile(title)).get_by_role('button', name='Discard').click()
    
    # Step 10: Confirm the deletion
    page.get_by_role('dialog', name='Discard Article').get_by_role('button', name='Discard').click()
    
    # Expected assertion: Verify the article is no longer visible in the draft list
    expect(page.get_by_role('row', name=re.compile(title))).not_to_be_visible(timeout=15000)
