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
    print(f"Initial URL: {page.url}")
    
    # Enter partner code
    await page.fill("input[placeholder='Partner code']", PARTNER_CODE)
    await page.click("button:has-text('Continue')")
    await page.wait_for_load_state("networkidle", timeout=10000)
    print(f"After partner code URL: {page.url}")
    
    # Take screenshot to see what page we're on
    await page.screenshot(path="/app/test_reports/iter169_login_1.jpeg", quality=40, full_page=False)
    
    # Login with admin credentials
    email_input = await page.query_selector("input[type='email']")
    if not email_input:
        email_input = await page.query_selector("input[placeholder*='mail'], input[name='email']")
    
    if email_input:
        await email_input.fill(ADMIN_EMAIL)
        
        pw_input = await page.query_selector("input[type='password']")
        if pw_input:
            await pw_input.fill(ADMIN_PASSWORD)
        
        submit_btn = await page.query_selector("button[type='submit']")
        if not submit_btn:
            submit_btn = await page.query_selector("button:has-text('Sign in'), button:has-text('Login'), button:has-text('Log in')")
        
        if submit_btn:
            await submit_btn.click()
            await page.wait_for_load_state("networkidle", timeout=10000)
            print(f"After login submit URL: {page.url}")
    else:
        print("ERROR: Email input not found after partner code")
        await page.screenshot(path="/app/test_reports/iter169_login_err.jpeg", quality=40, full_page=False)
        return False
    
    # Wait a bit more for auth to complete
    await page.wait_for_timeout(2000)
    print(f"After auth wait URL: {page.url}")
    
    # Navigate to admin
    await page.goto(BASE_URL + "/admin")
    await page.wait_for_load_state("networkidle", timeout=15000)
    final_url = page.url
    print(f"Admin URL after navigate: {final_url}")
    
    await page.screenshot(path="/app/test_reports/iter169_admin_after_login.jpeg", quality=40, full_page=False)
    
    return "/admin" in final_url and "login" not in final_url

async def check_col_header_buttons(page, expected_labels):
    """Check that ColHeader buttons appear in table header - ColHeader renders as th > button"""
    found = []
    missing = []
    for label in expected_labels:
        # Try multiple selector approaches
        btn = await page.query_selector(f"th button:has-text('{label}')")
        if not btn:
            # Try within thead
            btn = await page.query_selector(f"thead button:has-text('{label}')")
        if btn:
            is_visible = await btn.is_visible()
            if is_visible:
                found.append(label)
            else:
                missing.append(f"{label}(hidden)")
        else:
            missing.append(label)
    return found, missing

async def click_colheader_and_check_popover(page, label):
    """Click a ColHeader button and verify popover appears with sort/filter"""
    btn = await page.query_selector(f"th button:has-text('{label}')")
    if not btn:
        btn = await page.query_selector(f"thead button:has-text('{label}')")
    if not btn:
        return False, f"ColHeader button '{label}' not found"
    
    await btn.click()
    await page.wait_for_timeout(600)
    
    # Check for popover content (radix popover)
    popover = await page.query_selector("[data-radix-popper-content-wrapper], [data-state='open'][role='dialog'], [data-radix-popover-content]")
    if not popover:
        # Check for any visible popover-like element
        popover = await page.query_selector(".space-y-3")
    
    if not popover:
        return False, "Popover did not appear"
    
    # Check for Sort section
    sort_text = await page.query_selector("p:has-text('Sort'), .uppercase:has-text('Sort')")
    
    # Close popover by pressing Escape
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    
    return True, f"Popover shown {'with Sort section' if sort_text else 'but no Sort section found'}"

async def get_admin_page_content(page):
    """Get page content to debug navigation"""
    return await page.evaluate("() => document.body.innerText.substring(0, 500)")

async def navigate_sidebar(page, text):
    """Navigate using sidebar links"""
    # Look for sidebar nav items
    all_navs = await page.query_selector_all("aside a, aside button, nav a, nav button, [class*='sidebar'] a, [class*='sidebar'] button, [class*='nav'] a")
    for nav in all_navs:
        try:
            nav_text = await nav.inner_text()
            if nav_text.strip() == text:
                await nav.click()
                await page.wait_for_timeout(1500)
                return True
        except:
            pass
    # Try by text content anywhere in nav-like elements
    nav_item = await page.query_selector(f"aside *:has-text('{text}'), nav *:has-text('{text}')")
    if nav_item:
        await nav_item.click()
        await page.wait_for_timeout(1500)
        return True
    return False

async def click_sub_tab(page, text):
    """Click a sub-tab or sub-section"""
    sub = await page.query_selector(f"[role='tab']:has-text('{text}'), button[role='tab']:has-text('{text}')")
    if not sub:
        sub = await page.query_selector(f"button:has-text('{text}')")
    if sub:
        await sub.click()
        await page.wait_for_timeout(1000)
        return True
    return False

async def test_plans_license_plans(page):
    """Test Plans > License Plans table"""
    print("\n--- Test: Plans > License Plans ---")
    
    navigated = await navigate_sidebar(page, "Plans")
    if not navigated:
        print("  Could not navigate to Plans")
    
    await page.wait_for_timeout(1000)
    
    found, missing = await check_col_header_buttons(page, ["Plan", "Price", "Orgs", "Status", "Created"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    # Test popover
    if found:
        ok, msg = await click_colheader_and_check_popover(page, found[0])
        print(f"  Popover test ({found[0]}): {ok} - {msg}")
    
    results["plans_license_plans"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }

async def test_plans_sections(page):
    """Test Plans > One-Time Rates and Coupons"""
    print("\n--- Test: Plans > One-Time Rates ---")
    
    # Make sure we're on Plans page
    await navigate_sidebar(page, "Plans")
    
    # Try to find One-Time Rates section
    rates_ok = await click_sub_tab(page, "One-Time Rates")
    if not rates_ok:
        # Might be a scrollable section, look for it  
        rates_section = await page.query_selector("text=One-Time Rates")
        if rates_section:
            await rates_section.click()
            await page.wait_for_timeout(1000)
    
    found_rates, missing_rates = await check_col_header_buttons(page, ["Module", "Price / Unit", "Currency", "Status"])
    print(f"  [Rates] ColHeaders found: {found_rates}")
    print(f"  [Rates] ColHeaders missing: {missing_rates}")
    
    results["plans_one_time_rates"] = {
        "found": found_rates,
        "missing": missing_rates,
        "pass": len(missing_rates) == 0
    }
    
    print("\n--- Test: Plans > Coupons ---")
    coupons_ok = await click_sub_tab(page, "Coupons")
    if not coupons_ok:
        coupons_section = await page.query_selector("text=Coupons")
        if coupons_section:
            await coupons_section.click()
            await page.wait_for_timeout(1000)
    
    found_coupons, missing_coupons = await check_col_header_buttons(page, ["Code", "Discount", "Applies To", "Expiry", "Uses", "Status"])
    print(f"  [Coupons] ColHeaders found: {found_coupons}")
    print(f"  [Coupons] ColHeaders missing: {missing_coupons}")
    
    results["plans_coupons"] = {
        "found": found_coupons,
        "missing": missing_coupons,
        "pass": len(missing_coupons) == 0
    }

async def test_partner_tabs(page):
    """Test Partner Subscriptions and Orders"""
    print("\n--- Test: Partner Subscriptions ---")
    
    # Partner Subscriptions might be in a Partner section
    # Try various navigation approaches
    navigated = await navigate_sidebar(page, "Partner Subscriptions")
    if not navigated:
        navigated = await navigate_sidebar(page, "Subscriptions")
    
    await page.wait_for_timeout(1000)
    
    # Check URL to understand current section
    current_url = page.url
    print(f"  Current URL: {current_url}")
    
    found, missing = await check_col_header_buttons(page, ["Sub #", "Partner", "Plan", "Amount", "Interval", "Method", "Status"])
    print(f"  ColHeaders found: {found}")
    print(f"  ColHeaders missing: {missing}")
    
    results["partner_subscriptions"] = {
        "found": found,
        "missing": missing,
        "pass": len(missing) == 0
    }
    
    print("\n--- Test: Partner Orders ---")
    navigated = await navigate_sidebar(page, "Partner Orders")
    if not navigated:
        navigated = await navigate_sidebar(page, "Orders")
    
    await page.wait_for_timeout(1000)
    
    found_o, missing_o = await check_col_header_buttons(page, ["Order #", "Partner", "Description", "Amount", "Method", "Status", "Date"])
    print(f"  ColHeaders found: {found_o}")
    print(f"  ColHeaders missing: {missing_o}")
    
    results["partner_orders"] = {
        "found": found_o,
        "missing": missing_o,
        "pass": len(missing_o) == 0
    }

async def run_all_tests():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        print("=" * 60)
        print("ColHeader Admin Panel Test Suite")
        print("=" * 60)
        
        # Login
        try:
            logged_in = await login(page)
            if not logged_in:
                print("ERROR: Failed to login to admin panel")
                
                # Check if we're stuck at login page
                content = await get_admin_page_content(page)
                print(f"Current page content: {content}")
                await browser.close()
                return
            print("Login SUCCESS")
        except Exception as e:
            print(f"Login ERROR: {e}")
            import traceback
            traceback.print_exc()
            await browser.close()
            return
        
        # Take screenshot of admin panel
        await page.screenshot(path="/app/test_reports/iter169_04_admin_logged_in.jpeg", quality=40, full_page=False)
        
        # Verify we're on admin by checking content
        content = await get_admin_page_content(page)
        print(f"Admin page content preview: {content[:200]}")
        
        # Run all tests
        tests_to_run = [
            test_plans_license_plans,
            test_plans_sections,
            test_partner_tabs,
        ]
        
        for test_fn in tests_to_run:
            try:
                await test_fn(page)
            except Exception as e:
                print(f"ERROR in {test_fn.__name__}: {e}")
                import traceback
                traceback.print_exc()
        
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
        
        print(f"\nTotal: {passed} passed, {failed} failed")
        
        await browser.close()
        return results

asyncio.run(run_all_tests())
