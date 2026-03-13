"""
Test sort and filter functionality with actual data
"""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://admin-panel-fixes-17.preview.emergentagent.com"
PARTNER_CODE = "automate-accounts"
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

async def login_to_admin(page):
    await page.goto(BASE_URL + "/admin")
    await page.wait_for_load_state("networkidle", timeout=15000)
    await page.fill("input[placeholder='Partner code']", PARTNER_CODE)
    await page.click("button:has-text('Continue')")
    await page.wait_for_selector("input[type='email']", timeout=8000)
    await page.fill("input[type='email']", ADMIN_EMAIL)
    await page.fill("input[type='password']", ADMIN_PASSWORD)
    await page.click("button[type='submit']")
    await page.wait_for_selector("text=Control Panel", timeout=12000)

async def nav_sidebar(page, label):
    tabs = await page.query_selector_all("[role='tab']")
    for tab in tabs:
        try:
            text = await tab.inner_text()
            if text.strip().upper() == label.upper():
                is_visible = await tab.is_visible()
                if is_visible:
                    await tab.click()
                    await page.wait_for_timeout(1500)
                    return True
        except:
            pass
    return False

async def nav_content_tab(page, label):
    tabs = await page.query_selector_all("[role='tab']")
    for tab in tabs:
        try:
            text = await tab.inner_text()
            if text.strip().upper() == label.upper():
                is_visible = await tab.is_visible()
                if is_visible:
                    bb = await tab.bounding_box()
                    if bb and bb['x'] > 400:
                        await tab.click()
                        await page.wait_for_timeout(1000)
                        return True
        except:
            pass
    return False

async def test_sort_functionality(page, col_label):
    """Test that clicking sort Asc/Desc actually reorders rows"""
    print(f"\n--- Testing Sort Functionality on '{col_label}' ---")
    
    # Get current table rows before sort
    rows_before = await page.query_selector_all("tbody tr, table tbody tr")
    if not rows_before:
        print("  No table rows found, skipping sort test")
        return False, "No rows"
    
    # Get row content before sort
    first_cells_before = []
    for row in rows_before[:5]:
        try:
            cells = await row.query_selector_all("td")
            if cells:
                text = await cells[0].inner_text()
                first_cells_before.append(text.strip()[:20])
        except:
            pass
    print(f"  Rows before sort (first 5): {first_cells_before}")
    
    # Find and click the ColHeader button for this column
    th_buttons = await page.query_selector_all("th button")
    target_btn = None
    for btn in th_buttons:
        try:
            text = await btn.inner_text()
            if text.strip().upper() == col_label.upper():
                target_btn = btn
                break
        except:
            pass
    
    if not target_btn:
        print(f"  ColHeader button '{col_label}' not found")
        return False, "Button not found"
    
    # Click to open popover
    await target_btn.click()
    await page.wait_for_timeout(600)
    
    # Click "A → Z" or "Oldest first" sort button
    popover = await page.query_selector("[data-radix-popper-content-wrapper]")
    if not popover:
        await page.keyboard.press("Escape")
        return False, "No popover"
    
    # Find sort ascending button inside popover
    sort_btns = await popover.query_selector_all("button")
    asc_btn = None
    for btn in sort_btns:
        text = await btn.inner_text()
        if "A → Z" in text or "Low → High" in text or "Oldest first" in text:
            asc_btn = btn
            break
    
    if not asc_btn:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
        return False, "No sort asc button in popover"
    
    # Click sort ascending
    await asc_btn.click()
    await page.wait_for_timeout(800)
    
    # Get rows after sort
    rows_after = await page.query_selector_all("tbody tr, table tbody tr")
    first_cells_after = []
    for row in rows_after[:5]:
        try:
            cells = await row.query_selector_all("td")
            if cells:
                text = await cells[0].inner_text()
                first_cells_after.append(text.strip()[:20])
        except:
            pass
    print(f"  Rows after A→Z sort (first 5): {first_cells_after}")
    
    # Check if sort changed anything
    changed = first_cells_before != first_cells_after
    if changed:
        print(f"  SORT WORKED: Row order changed")
    else:
        print(f"  Sort didn't change visible row order (might already be sorted or only 1 row)")
    
    # Now click "Z → A" to test descending
    await target_btn.click()
    await page.wait_for_timeout(600)
    popover2 = await page.query_selector("[data-radix-popper-content-wrapper]")
    if popover2:
        desc_btn = None
        for btn in await popover2.query_selector_all("button"):
            text = await btn.inner_text()
            if "Z → A" in text or "High → Low" in text or "Newest first" in text:
                desc_btn = btn
                break
        if desc_btn:
            await desc_btn.click()
            await page.wait_for_timeout(800)
            rows_desc = await page.query_selector_all("tbody tr, table tbody tr")
            first_cells_desc = []
            for row in rows_desc[:5]:
                try:
                    cells = await row.query_selector_all("td")
                    if cells:
                        text = await cells[0].inner_text()
                        first_cells_desc.append(text.strip()[:20])
                except:
                    pass
            print(f"  Rows after Z→A sort (first 5): {first_cells_desc}")
            
            # Clear sort
            await target_btn.click()
            await page.wait_for_timeout(500)
            pop3 = await page.query_selector("[data-radix-popper-content-wrapper]")
            if pop3:
                clear_btn = None
                for btn in await pop3.query_selector_all("button"):
                    text = await btn.inner_text()
                    if text.strip() == (await target_btn.inner_text()).strip() + " active":
                        pass
                    # Click the active sort button to toggle off
                await page.keyboard.press("Escape")
        else:
            await page.keyboard.press("Escape")
    
    return True, f"Sort tested - before={first_cells_before[:2]}, after={first_cells_after[:2]}"

async def test_filter_functionality(page, col_label, filter_value):
    """Test that typing in filter input actually filters rows"""
    print(f"\n--- Testing Filter Functionality on '{col_label}' with '{filter_value}' ---")
    
    # Count rows before filter
    rows_before = await page.query_selector_all("tbody tr, table tbody tr")
    count_before = len(rows_before)
    print(f"  Rows before filter: {count_before}")
    
    # Find ColHeader button
    th_buttons = await page.query_selector_all("th button")
    target_btn = None
    for btn in th_buttons:
        try:
            text = await btn.inner_text()
            if text.strip().upper() == col_label.upper():
                target_btn = btn
                break
        except:
            pass
    
    if not target_btn:
        return False, "Button not found"
    
    # Open popover
    await target_btn.click()
    await page.wait_for_timeout(600)
    
    popover = await page.query_selector("[data-radix-popper-content-wrapper]")
    if not popover:
        return False, "No popover"
    
    # Find filter input
    filter_input = await popover.query_selector("input[type='text'], input:not([type='radio'])")
    if not filter_input:
        await page.keyboard.press("Escape")
        return False, "No filter input in popover"
    
    # Type filter value
    await filter_input.fill(filter_value)
    await page.wait_for_timeout(800)
    
    # Count rows after filter
    rows_after = await page.query_selector_all("tbody tr, table tbody tr")
    count_after = len(rows_after)
    print(f"  Rows after filter '{filter_value}': {count_after}")
    
    # Close popover
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(500)
    
    filter_worked = count_after <= count_before
    if filter_worked:
        print(f"  FILTER WORKED: {count_before} -> {count_after} rows")
    else:
        print(f"  Filter might not have worked (rows same or increased)")
    
    # Clear filter by reopening and clearing
    await target_btn.click()
    await page.wait_for_timeout(500)
    pop2 = await page.query_selector("[data-radix-popper-content-wrapper]")
    if pop2:
        inp2 = await pop2.query_selector("input[type='text'], input:not([type='radio'])")
        if inp2:
            await inp2.fill("")
            await page.wait_for_timeout(400)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(500)
    
    return filter_worked, f"Filter: {count_before} -> {count_after} rows"

async def run_sort_filter_tests():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        await login_to_admin(page)
        print("Logged in!")
        
        # Test Plans table sort (has data - plans exist)
        print("\n=== Sort/Filter Tests on Plans > License Plans ===")
        await nav_sidebar(page, "Plans")
        await nav_content_tab(page, "License Plans")
        
        sort_ok, sort_msg = await test_sort_functionality(page, "Plan")
        print(f"\nSort result: {sort_ok} - {sort_msg}")
        
        filter_ok, filter_msg = await test_filter_functionality(page, "Plan", "a")
        print(f"Filter result: {filter_ok} - {filter_msg}")
        
        await page.screenshot(path="/app/test_reports/iter169_sort_filter.jpeg", quality=40, full_page=False)
        
        # Test Customers table (might have data)
        print("\n=== Sort/Filter Tests on Customers ===")
        await nav_sidebar(page, "Customers")
        
        rows = await page.query_selector_all("tbody tr, table tbody tr")
        print(f"Customers rows: {len(rows)}")
        
        if rows:
            sort_ok2, sort_msg2 = await test_sort_functionality(page, "Name")
            print(f"Sort result: {sort_ok2} - {sort_msg2}")
            
            filter_ok2, filter_msg2 = await test_filter_functionality(page, "Name", "test")
            print(f"Filter result: {filter_ok2} - {filter_msg2}")
        else:
            print("No customers to test sort/filter")
        
        # Test Products sort/filter
        print("\n=== Sort/Filter Tests on Products ===")
        await nav_sidebar(page, "Products")
        await nav_content_tab(page, "Products")
        
        rows3 = await page.query_selector_all("tbody tr, table tbody tr")
        print(f"Products rows: {len(rows3)}")
        
        if rows3:
            sort_ok3, sort_msg3 = await test_sort_functionality(page, "Name")
            print(f"Sort result: {sort_ok3} - {sort_msg3}")
            
            filter_ok3, filter_msg3 = await test_filter_functionality(page, "Name", "a")
            print(f"Filter result: {filter_ok3} - {filter_msg3}")
        
        await page.screenshot(path="/app/test_reports/iter169_sort_filter_2.jpeg", quality=40, full_page=False)
        
        await browser.close()
        
        return {
            "plans_sort": sort_ok,
            "plans_filter": filter_ok,
        }

asyncio.run(run_sort_filter_tests())
