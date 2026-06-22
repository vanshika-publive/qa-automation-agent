import re
import time
from playwright.sync_api import expect
from helpers import safe_fill, safe_sequential_fill


def test_publish_and_delete_article(page):
    """Create an article, publish it directly, then delete it from the Published list.

    Verified live on publisher 'OdishaTv - Khabar' (2026-06-22). Articles on this
    publisher publish in ONE step from the create page — there is NO
    Save-as-Draft -> /posts/draft -> Edit -> Publish detour. Deletion is done from
    the Published list via the per-row kebab menu -> Delete -> confirm dialog.
    """
    ts = int(time.time() * 1000)
    title = f'QA Article {ts}'

    # --- Create ---
    page.goto('/posts/article/create')

    # Only the asterisk (required) fields are needed. Credits auto-fills with the
    # logged-in user, so it does not need to be set explicitly.
    safe_sequential_fill(page, 'Title *', title, delay=50)          # React-controlled
    safe_fill(page, 'English Title ( Permalink ) *', f'qa-{ts}')

    # Primary Category — pick the first live option (list is virtualized and the
    # available categories vary per publisher, so never hardcode a name).
    cb = page.get_by_role('combobox', name='Primary Category')
    cb.click()
    option = page.locator('.ant-select-dropdown').last.locator('.ant-select-item-option').first
    option.wait_for(state='visible')
    option.click()

    # --- Publish directly ---
    # The Publish button enables only AFTER the form's async validation settles
    # (the permalink check fires on blur). It is briefly disabled right after the
    # fields are filled, so wait for it to be enabled rather than clicking at once.
    publish = page.get_by_role('button', name='Publish')
    expect(publish).to_be_enabled(timeout=15000)
    publish.click()

    # --- The article now appears in the Published list ---
    page.goto('/posts/published?page_type=Article&ptype=Article&create=article')
    row = page.get_by_role('row', name=re.compile(re.escape(title)))
    expect(row.first).to_be_visible(timeout=15000)

    # --- Delete via the row's kebab (more-actions) dropdown ---
    # The kebab is an icon-only button with no accessible name; scope to the row and
    # target it by class (documented Ant Design exception, like button.publisher-switcher).
    row.first.locator('.published-action-dropdown').click()
    # The menu renders in an Ant Design portal; pick the open (non-hidden) one.
    menu = page.locator('.ant-dropdown:not(.ant-dropdown-hidden)').last
    menu.get_by_role('menuitem', name='Delete').click()

    # --- Confirm the deletion ---
    page.get_by_role('dialog', name='Delete Article').get_by_role('button', name='Delete').click()

    # --- Verify it is gone from the Published list ---
    expect(page.get_by_role('row', name=re.compile(re.escape(title)))).to_have_count(0, timeout=15000)
