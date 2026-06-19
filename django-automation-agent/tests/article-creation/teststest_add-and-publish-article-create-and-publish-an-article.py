import re
import time
from playwright.sync_api import expect
from helpers import safe_fill, safe_sequential_fill

def test_create_and_publish_article(page):
    ts = int(time.time() * 1000)
    title = f'QA Article {ts}'
    
    # Step 1: Navigate to the article creation page
    page.goto('/posts/article/create')
    
    # Step 3: Fill the Title field
    safe_sequential_fill(page, 'Title *', title, delay=50)
    
    # Step 4: Fill the English Title (Permalink) field
    safe_fill(page, 'English Title ( Permalink ) *', f'qa-{ts}')
    
    # Step 5: Fill the Summary field with at least 140 characters
    summary_text = 'This is a test summary that is intentionally long enough to meet the minimum character requirement for publishing an article. ' * 2
    safe_fill(page, 'Summary', summary_text[:140])
    
    # Step 6: Fill the Meta Description field with 140 to 170 characters
    meta_description_text = 'This is a test meta description that is intentionally long enough to meet the character requirement for publishing an article.'
    safe_fill(page, 'Meta Description', meta_description_text)
    
    # Step 7: Select the first available Primary Category
    cb = page.get_by_role('combobox', name='Primary Category')
    cb.click()
    cat_option = page.locator('.ant-select-dropdown').last.locator('.ant-select-item-option').first
    cat_option.wait_for(state='visible')
    cat_option.click()
    
    # Step 8: Click the 'Save as Draft' button
    page.get_by_role('button', name='Save as Draft').click()
    
    # Step 9: Expect URL to match /\/posts\/draft/
    expect(page).to_have_url(re.compile(r'/posts/draft'), timeout=15000)
    
    # Step 10: In the row matching the generated title, click 'Edit'
    page.get_by_role('row', name=re.compile(title)).get_by_role('link', name='Edit').click()
    
    # Step 11: Expect URL to match /\/posts\/article\/\d+/
    expect(page).to_have_url(re.compile(r'/posts/article/\d+'), timeout=15000)
    
    # Step 12: Click the 'Publish' button
    page.get_by_role('button', name='Publish').click()
    
    # Step 13: Expect URL to match /\/posts\/published/
    expect(page).to_have_url(re.compile(r'/posts/published'), timeout=15000)

    # Expected assertion: Verify the article with the generated title appears in the published list
    # This step assumes that the published list page is loaded and the article title is visible
    expect(page.get_by_text(title, exact=True)).to_be_visible(timeout=15000)
