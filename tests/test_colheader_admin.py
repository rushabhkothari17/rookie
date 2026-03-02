"""
Test ColHeader implementation across all 18 admin table sections.
Tests: ColHeader buttons appear in thead, old filter bars gone, sort/filter popover works.
Login flow: partner code -> email/password -> admin panel (with proper redirect wait)
"""
import asyncio
import json
from playwright.async_api import async_playwright

BASE_URL = "https://admin-column-headers.preview.emergentagent.com"
PARTNER_CODE = "automate-accounts"
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

results = {}

async def login_to_admin(page, context):
    """Full login flow: partner code -> email/password -> navigate to admin"""
    await page.goto(BASE_URL + "/admin")
    await page.wait_for_load_state("networkidle", timeout=15000)
    
    # Enter partner code
    await page.fill("input[placeholder='Partner code']", PARTNER_CODE)
    await page.click("button:has-text('Continue')")
    await page.wait_for_selector("input[type='email']", timeout=8000)
    
    # Enter credentials
    await page.fill("input[type='email']", ADMIN_EMAIL)
    await page.fill("input[type='password']", ADMIN_PASSWORD)
    await page.click("button[type='submit']")
    
    # Wait for redirect to /admin (URL changes away from /login)
    try:
        await page.wait_for_url("**/admin", timeout=10000)
        print(f"Redirected to admin: {page.url}")
    except:
        await page.wait_for_timeout(3000)
        print(f"After timeout URL: {page.url}")
    
    await page.wait_for_load_state("networkidle", timeout=10000)
    
    return "/admin" in page.url and "login" not in page.url

async def find_col_header_buttons_in_table(page, expected_labels):
    """Find ColHeader buttons within table header (th elements)"""
    found = []
    missing = []
    
    # Get all th buttons
    th_buttons = await page.query_selector_all("th button")
    th_button_texts = []
    for btn in th_buttons:
        try:
            text = await btn.inner_text()
            is_visible = await btn.is_visible()
            if is_visible:
                th_button_texts.append(text.strip())
        except:
            pass
    
    print(f"  All th button texts: {th_button_texts}")
    
    for label in expected_labels:
        found_label = False
        for text in th_button_texts:
            if label.strip() == text.strip() or label.strip() in text.strip():
                found.append(label)
                found_label = True
                break
        if not found_label:
            missing.append(label)
    
    return found, missing

async def test_colheader_popover(page):
    """Click first ColHeader button and verify popover with sort/filter"""
    th_buttons = await page.query_selector_all("th button")
    if not th_buttons:
        return False, "No th buttons found"
    
    # Find a visible one
    for btn in th_buttons:
        try:
            is_visible = await btn.is_visible()
            if is_visible:
                btn_text = await btn.inner_text()
                await btn.click()
                await page.wait_for_timeout(600)
                
                # Check for popover
                popover = await page.query_selector("[data-radix-popper-content-wrapper]")
                if popover:
                    content = await popover.inner_text()
                    has_sort = "Sort" in content
                    
                    # Close
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(300)
                    return True, f"Popover for '{btn_text.strip()}': Sort={has_sort}, content='{content[:80]}'"
                else:
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(300)
                    return False, f"No popover appeared for '{btn_text.strip()}'"
        except:
            pass
    
    return False, "Could not click any th button"

async def navigate_sidebar(page, label):
    """Navigate using sidebar by exact or partial text"""
    # Get all sidebar links
    candidates = await page.query_selector_all(
        "aside a, aside button, [class*='sidebar'] a, [class*='sidebar'] button, nav > a, nav > div a, nav > div button"
    )
    
    # Try exact match first
    for candidate in candidates:
        try:
            text = await candidate.inner_text()
            if text.strip() == label:
                is_visible = await candidate.is_visible()
                if is_visible:
                    await candidate.click()
                    await page.wait_for_timeout(1500)
                    return True
        except:
            pass
    
    # Try partial match
    for candidate in candidates:
        try:
            text = await candidate.inner_text()
            if label in text.strip() and len(text.strip()) < len(label) + 20:
                is_visible = await candidate.is_visible()
                if is_visible:
                    await candidate.click()
                    await page.wait_for_timeout(1500)
                    return True
        except:
            pass
    
    return False

async def click_subtab(page, label):
    """Click a sub-tab by text"""
    # Try role=tab first
    candidates = await page.query_selector_all("[role='tab']")
    for c in candidates:
        try:
            text = await c.inner_text()
            if text.strip() == label:
                is_visible = await c.is_visible()
                if is_visible:
                    await c.click()
                    await page.wait_for_timeout(800)
                    return True
        except:
            pass
    
    # Try buttons with that text
    candidates = await page.query_selector_all("button")
    for c in candidates:
        try:
            text = await c.inner_text()
            if text.strip() == label:
                is_visible = await c.is_visible()
                if is_visible:
                    await c.click()
                    await page.wait_for_timeout(800)
                    return True
        except:
            pass
    return False

async def check_no_old_filter_bar(page):
    """Check no standalone search inputs with selects outside table"""
    # Old filter bars had flex rows with selects above tables
    selects = await page.evaluate("""
        () => {
            const allSelects = Array.from(document.querySelectorAll('select'));
            const visibleSelectsOutsideTable = allSelects.filter(s => {
                if (!s.offsetParent) return false; // not visible
                let p = s.parentElement;
                while (p) {
                    if (['TABLE', 'THEAD', 'TBODY', 'TR', 'TH', 'TD'].includes(p.tagName)) return false;
                    p = p.parentElement;
                }
                return true;
            });
            return visibleSelectsOutsideTable.length;
        }
    """)
    
    return selects == 0, f"{selects} select elements outside table"

async def run_tab_test(name, page, expected_labels):
    """Run a single tab test"""
    found, missing = await find_col_header_buttons_in_table(page, expected_labels)
    print(f"  Found: {found}")
    print(f"  Missing: {missing}")
    
    # Test popover if any headers found
    popover_ok = False
    popover_msg = "No ColHeaders"
    if found:
        popover_ok, popover_msg = await test_colheader_popover(page)
        print(f"  Popover: {popover_ok} - {popover_msg}")
    else:
        print(f"  No ColHeaders found to test popover")
    
    # Check old filter bar removed
    filter_ok, filter_msg = await check_no_old_filter_bar(page)
    print(f"  No old filter bar: {filter_ok} ({filter_msg})")
    
    passed = len(missing) == 0 and (popover_ok or len(expected_labels) == 0)
    results[name] = {
        "found": found,
        "missing": missing,
        "popover_ok": popover_ok,
        "popover_msg": popover_msg,
        "old_filter_removed": filter_ok,
        "pass": passed
    }
    return passed

async def run_all_tests():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        print("=" * 60)
        print("ColHeader Admin Panel Test Suite - Iteration 169")
        print("=" * 60)
        
        # Login
        logged_in = await login_to_admin(page, context)
        if not logged_in:
            print("CRITICAL: Login failed")
            return
        
        print("Logged in successfully!")
        await page.screenshot(path="/app/test_reports/iter169_04_admin_logged_in.jpeg", quality=40, full_page=False)
        
        content = await page.evaluate("() => document.body.innerText.substring(0, 300)")
        print(f"Admin content: {content}")
        
        # ==== TEST 1: Plans > License Plans ====
        print("\n[1] Plans > License Plans")
        await navigate_sidebar(page, "Plans")
        await page.wait_for_timeout(1000)
        # Try to select License Plans sub-tab if present
        await click_subtab(page, "License Plans")
        await run_tab_test("plans_license_plans", page, ["Plan", "Price", "Orgs", "Status", "Created"])
        await page.screenshot(path="/app/test_reports/iter169_05_license_plans.jpeg", quality=40, full_page=False)
        
        # ==== TEST 2: Plans > One-Time Rates ====
        print("\n[2] Plans > One-Time Rates")
        # Navigate back to Plans if needed
        await navigate_sidebar(page, "Plans")
        await page.wait_for_timeout(500)
        
        # Try different sub-tab names for Rates
        clicked = await click_subtab(page, "One-Time Rates")
        if not clicked:
            clicked = await click_subtab(page, "Rates")
        
        # Check if we need to scroll down for the rates table (Plans page has multiple sections)
        # The rates table might be visible by scrolling
        await page.evaluate("window.scrollTo(0, 600)")
        await page.wait_for_timeout(500)
        
        found_r, missing_r = await find_col_header_buttons_in_table(page, ["Module", "Price / Unit", "Currency", "Status"])
        print(f"  Found: {found_r}, Missing: {missing_r}")
        
        popover_ok_r = False
        if found_r:
            popover_ok_r, msg = await test_colheader_popover(page)
            print(f"  Popover: {popover_ok_r} - {msg}")
        
        filter_ok_r, filter_msg_r = await check_no_old_filter_bar(page)
        print(f"  No old filter bar: {filter_ok_r} ({filter_msg_r})")
        
        await page.screenshot(path="/app/test_reports/iter169_06_rates.jpeg", quality=40, full_page=False)
        results["plans_one_time_rates"] = {
            "found": found_r,
            "missing": missing_r,
            "popover_ok": popover_ok_r,
            "old_filter_removed": filter_ok_r,
            "pass": len(missing_r) == 0
        }
        
        # ==== TEST 3: Plans > Coupons ====
        print("\n[3] Plans > Coupons")
        await navigate_sidebar(page, "Plans")
        await page.wait_for_timeout(500)
        clicked = await click_subtab(page, "Coupons")
        if not clicked:
            await page.evaluate("window.scrollTo(0, 1200)")
            await page.wait_for_timeout(500)
        
        found_c, missing_c = await find_col_header_buttons_in_table(page, ["Code", "Discount", "Applies To", "Expiry", "Uses", "Status"])
        print(f"  Found: {found_c}, Missing: {missing_c}")
        
        popover_ok_c = False
        if found_c:
            popover_ok_c, msg = await test_colheader_popover(page)
            print(f"  Popover: {popover_ok_c} - {msg}")
        
        await page.screenshot(path="/app/test_reports/iter169_07_coupons.jpeg", quality=40, full_page=False)
        results["plans_coupons"] = {
            "found": found_c,
            "missing": missing_c,
            "popover_ok": popover_ok_c,
            "pass": len(missing_c) == 0
        }
        
        # ==== TEST 4: Partner Subscriptions ====
        print("\n[4] Partner Subscriptions")
        nav = await navigate_sidebar(page, "Partner Subscriptions")
        if not nav:
            await navigate_sidebar(page, "Subscriptions")
        
        await run_tab_test("partner_subscriptions", page,
                          ["Sub #", "Partner", "Plan", "Amount", "Interval", "Method", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_08_partner_subs.jpeg", quality=40, full_page=False)
        
        # ==== TEST 5: Partner Orders ====
        print("\n[5] Partner Orders")
        nav = await navigate_sidebar(page, "Partner Orders")
        if not nav:
            await navigate_sidebar(page, "Orders")
        
        await run_tab_test("partner_orders", page,
                          ["Order #", "Partner", "Description", "Amount", "Method", "Status", "Date"])
        await page.screenshot(path="/app/test_reports/iter169_09_partner_orders.jpeg", quality=40, full_page=False)
        
        # ==== TEST 6: Partner Submissions ====
        print("\n[6] Partner Submissions")
        nav = await navigate_sidebar(page, "Partner Submissions")
        await run_tab_test("partner_submissions", page, ["Partner", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_10_partner_subs_tab.jpeg", quality=40, full_page=False)
        
        # ==== TEST 7: Users ====
        print("\n[7] Users")
        await navigate_sidebar(page, "Users")
        await run_tab_test("users", page, ["Name / Email", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_11_users.jpeg", quality=40, full_page=False)
        
        # ==== TEST 8: Customers ====
        print("\n[8] Customers")
        await navigate_sidebar(page, "Customers")
        await run_tab_test("customers", page, ["Name", "Email", "Country", "Status", "Payment Methods"])
        await page.screenshot(path="/app/test_reports/iter169_12_customers.jpeg", quality=40, full_page=False)
        
        # ==== TEST 9: Products > Products ====
        print("\n[9] Products > Products sub-tab")
        await navigate_sidebar(page, "Products")
        await page.wait_for_timeout(500)
        # Check what tabs are available
        tabs = await page.query_selector_all("[role='tab']")
        tab_texts = []
        for t in tabs:
            txt = await t.inner_text()
            tab_texts.append(txt.strip())
        print(f"  Available tabs: {tab_texts}")
        
        await click_subtab(page, "Products")
        await run_tab_test("products_products", page, ["Name", "Category", "Billing", "Price", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_13_products.jpeg", quality=40, full_page=False)
        
        # ==== TEST 10: Products > Categories ====
        print("\n[10] Products > Categories sub-tab")
        await click_subtab(page, "Categories")
        await run_tab_test("products_categories", page, ["Name", "Description", "Products", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_14_products_cats.jpeg", quality=40, full_page=False)
        
        # ==== TEST 11: Products > Promo Codes ====
        print("\n[11] Products > Promo Codes sub-tab")
        clicked = await click_subtab(page, "Promo Codes")
        if not clicked:
            clicked = await click_subtab(page, "Filters")
        await run_tab_test("products_promo_codes", page, ["Code", "Discount", "Applies To", "Expiry", "Usage", "Created", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_15_promo_codes.jpeg", quality=40, full_page=False)
        
        # ==== TEST 12: Products > Terms ====
        print("\n[12] Products > Terms sub-tab")
        await click_subtab(page, "Terms")
        await run_tab_test("products_terms", page, ["Title", "Status", "Created"])
        await page.screenshot(path="/app/test_reports/iter169_16_terms.jpeg", quality=40, full_page=False)
        
        # ==== TEST 13: Subscriptions ====
        print("\n[13] Subscriptions")
        await navigate_sidebar(page, "Subscriptions")
        await run_tab_test("subscriptions", page, ["Sub #", "Customer Email", "Plan", "Amount", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_17_subscriptions.jpeg", quality=40, full_page=False)
        
        # ==== TEST 14: Orders ====
        print("\n[14] Orders")
        await navigate_sidebar(page, "Orders")
        await run_tab_test("orders", page, ["Date", "Order #", "Email", "Method", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_18_orders.jpeg", quality=40, full_page=False)
        
        # ==== TEST 15: Enquiries ====
        print("\n[15] Enquiries")
        await navigate_sidebar(page, "Enquiries")
        await run_tab_test("enquiries", page, ["Date", "Order #", "Customer", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_19_enquiries.jpeg", quality=40, full_page=False)
        
        # ==== TEST 16: Resources ====
        print("\n[16] Resources")
        await navigate_sidebar(page, "Resources")
        await run_tab_test("resources", page, ["Created", "Category", "Title / Visible"])
        await page.screenshot(path="/app/test_reports/iter169_20_resources.jpeg", quality=40, full_page=False)
        
        # ==== TEST 17: Resources > Templates ====
        print("\n[17] Resources > Templates")
        # Check what sub-tabs are available in resources
        tabs_res = await page.query_selector_all("[role='tab']")
        tab_texts_res = [await t.inner_text() for t in tabs_res]
        print(f"  Resources tabs: {[t.strip() for t in tab_texts_res]}")
        
        clicked = await click_subtab(page, "Templates")
        await run_tab_test("resources_templates", page, ["Name", "Category", "Type"])
        await page.screenshot(path="/app/test_reports/iter169_21_res_templates.jpeg", quality=40, full_page=False)
        
        # ==== TEST 18: Resources > Email Templates ====
        print("\n[18] Resources > Email Templates")
        clicked = await click_subtab(page, "Email Templates")
        await run_tab_test("resources_email_templates", page, ["Name", "Subject"])
        await page.screenshot(path="/app/test_reports/iter169_22_email_templates.jpeg", quality=40, full_page=False)
        
        # ==== TEST 19: Resources > Categories ====
        print("\n[19] Resources > Categories")
        clicked = await click_subtab(page, "Categories")
        await run_tab_test("resources_categories", page, ["Name", "Description"])
        await page.screenshot(path="/app/test_reports/iter169_23_res_categories.jpeg", quality=40, full_page=False)
        
        # ==== FINAL SUMMARY ====
        print("\n" + "=" * 60)
        print("FINAL RESULTS SUMMARY")
        print("=" * 60)
        
        total_passed = 0
        total_failed = 0
        failed_tests = []
        
        for name, result in results.items():
            status = "PASS" if result.get("pass", False) else "FAIL"
            if result.get("pass", False):
                total_passed += 1
            else:
                total_failed += 1
                failed_tests.append(name)
            
            print(f"  {status}: {name}")
            if result.get("missing"):
                print(f"    Missing ColHeaders: {result['missing']}")
            if result.get("found"):
                print(f"    Found ColHeaders: {result['found']}")
        
        total = total_passed + total_failed
        print(f"\nPASSED: {total_passed}/{total} ({int(total_passed/total*100) if total else 0}%)")
        if failed_tests:
            print(f"FAILED: {failed_tests}")
        
        # Save results
        with open("/app/test_reports/iter169_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        await browser.close()
        return results

asyncio.run(run_all_tests())
