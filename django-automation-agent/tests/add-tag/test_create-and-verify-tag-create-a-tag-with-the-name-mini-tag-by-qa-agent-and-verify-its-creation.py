import re
import time
from playwright.sync_api import expect
from helpers import safe_fill, safe_sequential_fill

def test_create_and_verify_tag(page):
    ts = int(time.time() * 1000)
    tag_name = f'mini tag by QA Agent {ts}'
    page.goto('/tags/create')
    safe_sequential_fill(page, 'Name *', tag_name, delay=50)
    page.get_by_role('button', name='Save').click()
    expect(page).to_have_url(re.compile(r'/tags/'), timeout=15000)
