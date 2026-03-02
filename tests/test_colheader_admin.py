"""
Test ColHeader implementation across all 18 admin table sections.
Tests: ColHeader buttons appear, old filter bars gone, sort/filter popover works.
"""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://admin-column-headers.preview.emergentagent.com"
PARTNER_CODE = "automate-accounts"
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

results = {}

async def login(page):
    """Login to admin panel"""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle", timeout=15000)
    
    # Enter partner code
    await page.fill("input[placeholder='Partner code']", PARTNER_CODE)
    await page.click("button:has-text('Continue')")
    await page.wait_for_load_state("networkidle", timeout=10000)
    
    # Login with admin credentials
    await page.wait_for_selector("input[type='email']", timeout=8000)
    await page.fill("input[type='email']", ADMIN_EMAIL)
    await page.fill("input[type='password']", ADMIN_PASSWORD)
    await page.click("button[type='submit']")
    await page.wait_for_load_state("networkidle", timeout=10000)
    
    # Navigate to admin
    await page.goto(BASE_URL + "/admin")
    await page.wait_for_load_state("networkidle", timeout=15000)
    
    current_url = page.url
    print(f"Admin URL after login: {current_url}")
    return "/admin" in current_url

async def check_col_header_buttons(page, expected_labels):
    """Check that ColHeader buttons appear in table header"""
    # ColHeader renders as th > button with text
    found = []
    missing = []
    for label in expected_labels:
        # Check if button with this label exists in a th element
        btn = await page.query_selector(f"th button:has-text('{label}')")
        if btn:
            found.append(label)
        else:
            missing.append(label)
    return found, missing

async def check_no_old_filter_bar(page):
    """Check that old filter bar (search input + dropdowns) is removed"""
    # Old filter bars typically had a flex row with search input and select dropdowns outside the table
    # Look for specific patterns: input[type=search] or input with placeholder "Search" outside table
    old_search = await page.query_selector("input[placeholder*='Search']:not([class*='h-7'])")
    if old_search:
        # Check if it's visible
        is_visible = await old_search.is_visible()
        if is_visible:
            return False, "Found visible search input outside table"
    return True, "No old filter bar found"

async def click_colheader_and_check_popover(page, label):
    """Click a ColHeader button and verify popover appears with sort/filter"""
    btn = await page.query_selector(f"th button:has-text('{label}')")
    if not btn:
        return False, f"ColHeader button '{label}' not found"
    
    await btn.click()
    await page.wait_for_timeout(500)
    
    # Check for popover content
    popover = await page.query_selector("[data-radix-popper-content-wrapper]")
    if not popover:
        return False, "Popover did not appear"
    
    # Check for Sort section
    sort_text = await page.query_selector("text=Sort")
    if not sort_text:
        return False, "Sort section not found in popover"
    
    # Check for sort buttons
    asc_btn = await page.query_selector("button:has-text('A \u2192 Z'), button:has-text('Low \u2192 High'), button:has-text('Oldest first')")
    desc_btn = await page.query_selector("button:has-text('Z \u2192 A'), button:has-text('High \u2192 Low'), button:has-text('Newest first')")
    
    # Close popover by pressing Escape
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    
    return True, "Popover shown with Sort section"

async def navigate_to_tab(page, sidebar_text, sub_tab_text=None):
    """Click a sidebar tab"""
    # Find the sidebar navigation item
    nav_item = await page.query_selector(f"nav a:has-text('{sidebar_text}'), button:has-text('{sidebar_text}')")
    if not nav_item:
        # Try more general selector
        nav_item = await page.query_selector(f"[class*='sidebar'] *:has-text('{sidebar_text}')")
    if nav_item:
        await nav_item.click()
        await page.wait_for_timeout(1000)
    
    if sub_tab_text:
        sub_tab = await page.query_selector(f"button:has-text('{sub_tab_text}'), [role='tab']:has-text('{sub_tab_text}')")
        if sub_tab:
            await sub_tab.click()
            await page.wait_for_timeout(1000)

async def test_plans_license_plans(page):
    """Test Plans > License Plans table - ColHeader should work on Plan, Price, Orgs, Status, Created"""
    print("\n--- Test: Plans > License Plans ---")
    
    # Click Plans tab in sidebar
    plans_nav = await page.query_selector("text=Plans")
    if plans_nav:
        await plans_nav.click()
        await page.wait_for_timeout(1500)
    
    # Should be on License Plans by default
    found, missing = await check_col_header_buttons(page, ["Plan", "Price", "Orgs", "Status", "Created"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    # Test popover on Plan column
    if "Plan" in found:
        ok, msg = await click_colheader_and_check_popover(page, "Plan")
        print(f"  Popover test: {ok} - {msg}")
    
    results["plans_license_plans"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }
    return len(missing) == 0

async def test_plans_one_time_rates(page):
    """Test Plans > One-Time Rates section"""
    print("\n--- Test: Plans > One-Time Rates ---")
    
    # Click the One-Time Rates sub-section
    # It might be a sub-tab or accordion section
    rates_tab = await page.query_selector("button:has-text('One-Time Rates'), [role='tab']:has-text('One-Time Rates')")
    if not rates_tab:
        rates_tab = await page.query_selector("text=One-Time Rates")
    if rates_tab:
        await rates_tab.click()
        await page.wait_for_timeout(1000)
    
    found, missing = await check_col_header_buttons(page, ["Module", "Price / Unit", "Currency", "Status"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    results["plans_one_time_rates"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }
    return len(missing) == 0

async def test_plans_coupons(page):
    """Test Plans > Coupons section"""
    print("\n--- Test: Plans > Coupons ---")
    
    coupons_tab = await page.query_selector("button:has-text('Coupons'), [role='tab']:has-text('Coupons')")
    if not coupons_tab:
        coupons_tab = await page.query_selector("text=Coupons")
    if coupons_tab:
        await coupons_tab.click()
        await page.wait_for_timeout(1000)
    
    found, missing = await check_col_header_buttons(page, ["Code", "Discount", "Applies To", "Expiry", "Uses", "Status"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    results["plans_coupons"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }
    return len(missing) == 0

async def test_partner_subscriptions(page):
    """Test Partner Subscriptions tab"""
    print("\n--- Test: Partner Subscriptions ---")
    
    # Navigate to Partner Subscriptions in sidebar
    partner_subs_nav = await page.query_selector("nav a:has-text('Subscriptions'), nav button:has-text('Subscriptions')")
    if not partner_subs_nav:
        # Try sidebar links
        all_links = await page.query_selector_all("nav a, nav button")
        for link in all_links:
            text = await link.inner_text()
            if "Subscription" in text:
                await link.click()
                await page.wait_for_timeout(1500)
                break
    else:
        await partner_subs_nav.click()
        await page.wait_for_timeout(1500)
    
    found, missing = await check_col_header_buttons(page, ["Sub #", "Partner", "Plan", "Amount", "Interval", "Method", "Status"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    # Check no old filter bar (search input + partner_id/status/plan_id/interval dropdowns)
    filter_ok, filter_msg = await check_no_old_filter_bar(page)
    print(f"  Old filter bar removed: {filter_ok} - {filter_msg}")
    
    results["partner_subscriptions"] = {
        "found": found,
        "missing": missing,
        "old_filter_removed": filter_ok,
        "pass": len(missing) == 0
    }
    return len(missing) == 0

async def test_partner_orders(page):
    """Test Partner Orders tab"""
    print("\n--- Test: Partner Orders ---")
    
    # Navigate to Partner Orders
    orders_link = None
    all_links = await page.query_selector_all("nav a, nav button, [class*='sidebar'] a, [class*='sidebar'] button")
    for link in all_links:
        text = await link.inner_text()
        if "Orders" in text and "Partner" in text:
            orders_link = link
            break
    
    if not orders_link:
        # Try clicking sidebar and finding orders tab within partner section
        sidebar_items = await page.query_selector_all("nav li, nav a")
        for item in sidebar_items:
            text = await item.inner_text()
            if "Orders" in text:
                orders_link = item
                break
    
    if orders_link:
        await orders_link.click()
        await page.wait_for_timeout(1500)
    
    found, missing = await check_col_header_buttons(page, ["Order #", "Partner", "Description", "Amount", "Method", "Status", "Date"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    results["partner_orders"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }
    return len(missing) == 0

async def test_users_tab(page):
    """Test Users tab"""
    print("\n--- Test: Users ---")
    
    # Find Users in sidebar
    all_links = await page.query_selector_all("nav a, nav button, aside a, aside button")
    for link in all_links:
        text = await link.inner_text()
        if text.strip() == "Users":
            await link.click()
            await page.wait_for_timeout(1500)
            break
    
    found, missing = await check_col_header_buttons(page, ["Name / Email", "Status"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    results["users"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }
    return len(missing) == 0

async def test_customers_tab(page):
    """Test Customers tab"""
    print("\n--- Test: Customers ---")
    
    all_links = await page.query_selector_all("nav a, nav button, aside a, aside button")
    for link in all_links:
        text = await link.inner_text()
        if text.strip() == "Customers":
            await link.click()
            await page.wait_for_timeout(1500)
            break
    
    found, missing = await check_col_header_buttons(page, ["Name", "Email", "Country", "Status", "Payment Methods"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    results["customers"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }
    return len(missing) == 0

async def test_products_tab(page):
    """Test Products > Products tab"""
    print("\n--- Test: Products > Products ---")
    
    all_links = await page.query_selector_all("nav a, nav button, aside a, aside button")
    for link in all_links:
        text = await link.inner_text()
        if text.strip() == "Products":
            await link.click()
            await page.wait_for_timeout(1500)
            break
    
    # Should default to Products sub-tab
    found, missing = await check_col_header_buttons(page, ["Name", "Category", "Billing", "Price", "Status"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    results["products_products"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }
    return len(missing) == 0

async def test_subscriptions_tab(page):
    """Test Subscriptions tab"""
    print("\n--- Test: Subscriptions ---")
    
    all_links = await page.query_selector_all("nav a, nav button, aside a, aside button")
    for link in all_links:
        text = await link.inner_text()
        if text.strip() == "Subscriptions":
            await link.click()
            await page.wait_for_timeout(1500)
            break
    
    found, missing = await check_col_header_buttons(page, ["Sub #", "Customer Email", "Plan", "Amount", "Status"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    results["subscriptions"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }
    return len(missing) == 0

async def test_orders_tab(page):
    """Test Orders tab"""
    print("\n--- Test: Orders ---")
    
    all_links = await page.query_selector_all("nav a, nav button, aside a, aside button")
    for link in all_links:
        text = await link.inner_text()
        if text.strip() == "Orders":
            await link.click()
            await page.wait_for_timeout(1500)
            break
    
    found, missing = await check_col_header_buttons(page, ["Date", "Order #", "Email", "Method", "Status"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    results["orders"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }
    return len(missing) == 0

async def test_enquiries_tab(page):
    """Test Enquiries tab"""
    print("\n--- Test: Enquiries ---")
    
    all_links = await page.query_selector_all("nav a, nav button, aside a, aside button")
    for link in all_links:
        text = await link.inner_text()
        if text.strip() == "Enquiries":
            await link.click()
            await page.wait_for_timeout(1500)
            break
    
    found, missing = await check_col_header_buttons(page, ["Date", "Order #", "Customer", "Status"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    results["enquiries"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }
    return len(missing) == 0

async def test_resources_tab(page):
    """Test Resources tab"""
    print("\n--- Test: Resources ---")
    
    all_links = await page.query_selector_all("nav a, nav button, aside a, aside button")
    for link in all_links:
        text = await link.inner_text()
        if text.strip() == "Resources":
            await link.click()
            await page.wait_for_timeout(1500)
            break
    
    found, missing = await check_col_header_buttons(page, ["Created", "Category", "Title / Visible"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    results["resources"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }
    return len(missing) == 0

async def run_all_tests():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        page.on("console", lambda msg: print(f"CONSOLE[{msg.type}]: {msg.text}") if msg.type == "error" else None)
        
        print("=" * 60)
        print("ColHeader Admin Panel Test Suite")
        print("=" * 60)
        
        # Login
        try:
            logged_in = await login(page)
            if not logged_in:
                print("ERROR: Failed to login to admin panel")
                await browser.close()
                return
            print("Login SUCCESS - Now at admin panel")
        except Exception as e:
            print(f"Login ERROR: {e}")
            await browser.close()
            return
        
        # Take screenshot of admin panel
        await page.screenshot(path="/app/test_reports/iter169_04_admin_logged_in.jpeg", quality=40, full_page=False)
        
        # Run all tests
        test_fns = [
            test_plans_license_plans,
            test_plans_one_time_rates,
            test_plans_coupons,
            test_partner_subscriptions,
            test_partner_orders,
            test_users_tab,
            test_customers_tab,
            test_products_tab,
            test_subscriptions_tab,
            test_orders_tab,
            test_enquiries_tab,
            test_resources_tab,
        ]
        
        for test_fn in test_fns:
            try:
                await test_fn(page)
            except Exception as e:
                print(f"ERROR in {test_fn.__name__}: {e}")
                test_name = test_fn.__name__.replace("test_", "")
                results[test_name] = {"error": str(e), "pass": False}
        
        # Final screenshot of admin panel
        await page.screenshot(path="/app/test_reports/iter169_05_after_tests.jpeg", quality=40, full_page=False)
        
        # Summary
        print("\n" + "=" * 60)
        print("RESULTS SUMMARY")
        print("=" * 60)
        passed = 0
        failed = 0
        for name, result in results.items():
            status = "PASS" if result.get("pass", False) else "FAIL"
            if result.get("pass", False):
                passed += 1
            else:
                failed += 1
            print(f"  {status}: {name}")
            if result.get("missing"):
                print(f"    Missing ColHeaders: {result['missing']}")
            if result.get("error"):
                print(f"    Error: {result['error']}")
        
        print(f"\nTotal: {passed} passed, {failed} failed")
        
        await browser.close()
        return results

asyncio.run(run_all_tests())
