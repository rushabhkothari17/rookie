"""
Test ColHeader implementation across all 18 admin table sections.
Tests: ColHeader buttons appear in thead, old filter bars gone, sort/filter popover works.
Login flow: partner code -> email/password -> admin panel
"""
import asyncio
import json
from playwright.async_api import async_playwright

BASE_URL = "https://admin-column-headers.preview.emergentagent.com"
PARTNER_CODE = "automate-accounts"
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

results = {}

async def login_to_admin(page):
    """Full login flow: partner code -> email/password -> navigate to admin"""
    # Navigate to /admin which redirects to login
    await page.goto(BASE_URL + "/admin")
    await page.wait_for_load_state("networkidle", timeout=15000)
    print(f"Redirected to: {page.url}")
    
    # Step 1: Enter partner code
    await page.fill("input[placeholder='Partner code']", PARTNER_CODE)
    await page.click("button:has-text('Continue')")
    
    # Wait for email input to appear
    await page.wait_for_selector("input[type='email']", timeout=8000)
    print("Partner code accepted, email form shown")
    
    # Step 2: Enter credentials
    await page.fill("input[type='email']", ADMIN_EMAIL)
    await page.fill("input[type='password']", ADMIN_PASSWORD)
    await page.click("button[type='submit']")  # "Sign In" button
    
    # Wait for navigation after successful login
    await page.wait_for_load_state("networkidle", timeout=15000)
    print(f"After login URL: {page.url}")
    
    # Should be at /admin now
    if "/admin" in page.url and "login" not in page.url:
        print("SUCCESS: Logged in to admin panel!")
        return True
    
    # If not, might need to navigate explicitly
    await page.goto(BASE_URL + "/admin")
    await page.wait_for_load_state("networkidle", timeout=15000)
    print(f"After navigate to /admin: {page.url}")
    
    return "/admin" in page.url and "login" not in page.url

async def find_col_header_buttons_in_thead(page, expected_labels):
    """Find ColHeader buttons within table header (thead/th elements)"""
    found = []
    missing = []
    
    for label in expected_labels:
        # ColHeader renders as th > Popover > PopoverTrigger > button
        # The button is inside th element
        btn = None
        
        # Try exact text match in th buttons
        candidates = await page.query_selector_all("th button")
        for candidate in candidates:
            try:
                text = await candidate.inner_text()
                if label.strip() in text.strip() or text.strip() in label.strip():
                    is_visible = await candidate.is_visible()
                    if is_visible:
                        btn = candidate
                        break
            except:
                pass
        
        if btn:
            found.append(label)
        else:
            missing.append(label)
    
    return found, missing

async def click_first_colheader_popover(page):
    """Click first available ColHeader button and verify popover"""
    th_buttons = await page.query_selector_all("th button")
    if not th_buttons:
        return False, "No th buttons found"
    
    first_btn = th_buttons[0]
    btn_text = await first_btn.inner_text()
    await first_btn.click()
    await page.wait_for_timeout(600)
    
    # Check for popover with Sort section
    # Radix popover shows as [data-radix-popper-content-wrapper]
    popover_wrapper = await page.query_selector("[data-radix-popper-content-wrapper]")
    if not popover_wrapper:
        return False, f"Popover not found for '{btn_text}'"
    
    # Check for sort section text
    popover_content = await popover_wrapper.inner_text()
    has_sort = "Sort" in popover_content
    has_filter = "Filter" in popover_content
    
    # Close popover
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    
    return True, f"Popover for '{btn_text.strip()}': Sort={has_sort}, Filter={has_filter}"

async def check_old_filter_bar_removed(page):
    """Check that standalone filter bars with selects/inputs outside tables are gone"""
    # Old filter bars were flex rows with search inputs + select dropdowns above the table
    # They typically had: div.flex > input[type=text/search] + select elements
    # But we need to be careful not to flag the ColHeader popover inputs
    
    # Check for standalone select elements (old filter dropdowns) - outside table
    selects_outside_table = await page.evaluate("""
        () => {
            const selects = Array.from(document.querySelectorAll('select'));
            return selects.filter(s => {
                // Check if select is outside a table
                let parent = s.parentElement;
                while (parent) {
                    if (parent.tagName === 'TABLE' || parent.tagName === 'THEAD' || parent.tagName === 'TBODY') {
                        return false;
                    }
                    parent = parent.parentElement;
                }
                return s.offsetParent !== null; // visible
            }).map(s => ({ name: s.name, id: s.id, class: s.className }));
        }
    """)
    
    if selects_outside_table:
        return False, f"Found {len(selects_outside_table)} select(s) outside table: {selects_outside_table}"
    
    return True, "No old select filter bars found outside tables"

async def navigate_to_sidebar_item(page, label):
    """Navigate using the sidebar by text label"""
    # Find sidebar links/buttons by text
    candidates = await page.query_selector_all("aside a, aside button, [class*='sidebar'] a, [class*='sidebar'] button, nav a")
    for candidate in candidates:
        try:
            text = await candidate.inner_text()
            if text.strip() == label:
                await candidate.click()
                await page.wait_for_timeout(1500)
                return True
        except:
            pass
    
    # Broader match
    for candidate in candidates:
        try:
            text = await candidate.inner_text()
            if label in text and len(text.strip()) < len(label) + 10:
                await candidate.click()
                await page.wait_for_timeout(1500)
                return True
        except:
            pass
    
    return False

async def click_tab(page, label):
    """Click a tab or sub-tab element"""
    tab = await page.query_selector(f"[role='tab']:has-text('{label}'), button[role='tab']:has-text('{label}')")
    if tab:
        await tab.click()
        await page.wait_for_timeout(1000)
        return True
    
    # Broader search
    candidates = await page.query_selector_all("[role='tab'], button")
    for candidate in candidates:
        try:
            text = await candidate.inner_text()
            if text.strip() == label:
                is_visible = await candidate.is_visible()
                if is_visible:
                    await candidate.click()
                    await page.wait_for_timeout(1000)
                    return True
        except:
            pass
    return False

async def get_sidebar_items(page):
    """Get all sidebar navigation items"""
    items = []
    candidates = await page.query_selector_all("aside a, aside button, [class*='sidebar'] a, [class*='sidebar'] button")
    for c in candidates:
        try:
            text = await c.inner_text()
            if text.strip():
                items.append(text.strip())
        except:
            pass
    return list(set(items))

# ---- TAB TEST FUNCTIONS ----

async def run_test(name, page, expected_labels, screenshot_path=None):
    """Generic test runner for a tab"""
    found, missing = await find_col_header_buttons_in_thead(page, expected_labels)
    print(f"  Found: {found}")
    print(f"  Missing: {missing}")
    
    # Test popover if we found any ColHeaders
    popover_ok = False
    popover_msg = "No ColHeaders to test"
    if found:
        popover_ok, popover_msg = await click_first_colheader_popover(page)
        print(f"  Popover: {popover_ok} - {popover_msg}")
    
    # Check old filter bar removed
    filter_ok, filter_msg = await check_old_filter_bar_removed(page)
    print(f"  Old filter bar removed: {filter_ok} - {filter_msg}")
    
    if screenshot_path:
        await page.screenshot(path=screenshot_path, quality=40, full_page=False)
    
    results[name] = {
        "found": found,
        "missing": missing,
        "popover_ok": popover_ok,
        "old_filter_removed": filter_ok,
        "pass": len(missing) == 0 and popover_ok
    }
    return len(missing) == 0

async def run_all_tests():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        print("=" * 60)
        print("ColHeader Admin Panel Test Suite - Iteration 169")
        print("=" * 60)
        
        # Login
        logged_in = await login_to_admin(page)
        if not logged_in:
            print("CRITICAL: Could not log in to admin panel!")
            await page.screenshot(path="/app/test_reports/iter169_login_fail.jpeg", quality=40, full_page=False)
            await browser.close()
            return
        
        await page.screenshot(path="/app/test_reports/iter169_04_admin_logged_in.jpeg", quality=40, full_page=False)
        
        # Check what sidebar items are available
        sidebar_items = await get_sidebar_items(page)
        print(f"Sidebar items: {sidebar_items}")
        
        # ==== TEST 1: Plans > License Plans ====
        print("\n--- [1] Plans > License Plans ---")
        await navigate_to_sidebar_item(page, "Plans")
        # Default view should show License Plans
        await page.wait_for_timeout(1000)
        
        # Check if we need to click a Plans sub-tab
        license_plans_tab = await page.query_selector("[role='tab']:has-text('License Plans'), [role='tab']:has-text('Plans')")
        if license_plans_tab:
            await license_plans_tab.click()
            await page.wait_for_timeout(500)
        
        await run_test("plans_license_plans", page, ["Plan", "Price", "Orgs", "Status", "Created"],
                      "/app/test_reports/iter169_05_plans_license.jpeg")
        
        # ==== TEST 2: Plans > One-Time Rates ====
        print("\n--- [2] Plans > One-Time Rates ---")
        # Try to find One-Time Rates section (could be a tab, accordion, or section within Plans)
        rates_clicked = await click_tab(page, "One-Time Rates")
        if not rates_clicked:
            # Try to scroll to it or find it as a section
            rates_heading = await page.query_selector("text=One-Time Rates")
            if rates_heading:
                await rates_heading.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
        
        found_rates, missing_rates = await find_col_header_buttons_in_thead(page, ["Module", "Price / Unit", "Currency", "Status"])
        print(f"  Found: {found_rates}")
        print(f"  Missing: {missing_rates}")
        
        if found_rates:
            popover_ok, popover_msg = await click_first_colheader_popover(page)
            print(f"  Popover: {popover_ok} - {popover_msg}")
        
        await page.screenshot(path="/app/test_reports/iter169_06_plans_rates.jpeg", quality=40, full_page=False)
        
        results["plans_one_time_rates"] = {
            "found": found_rates,
            "missing": missing_rates,
            "pass": len(missing_rates) == 0
        }
        
        # ==== TEST 3: Plans > Coupons ====
        print("\n--- [3] Plans > Coupons ---")
        coupons_clicked = await click_tab(page, "Coupons")
        if not coupons_clicked:
            await navigate_to_sidebar_item(page, "Plans")
        
        await run_test("plans_coupons", page, ["Code", "Discount", "Applies To", "Expiry", "Uses", "Status"],
                      "/app/test_reports/iter169_07_plans_coupons.jpeg")
        
        # ==== TEST 4: Partner Subscriptions ====
        print("\n--- [4] Partner Subscriptions ---")
        nav_ok = await navigate_to_sidebar_item(page, "Partner Subscriptions")
        if not nav_ok:
            nav_ok = await navigate_to_sidebar_item(page, "Subscriptions")
        
        await run_test("partner_subscriptions", page, 
                      ["Sub #", "Partner", "Plan", "Amount", "Interval", "Method", "Status", "Next Billing", "Expiry"],
                      "/app/test_reports/iter169_08_partner_subs.jpeg")
        
        # ==== TEST 5: Partner Orders ====
        print("\n--- [5] Partner Orders ---")
        nav_ok = await navigate_to_sidebar_item(page, "Partner Orders")
        if not nav_ok:
            nav_ok = await navigate_to_sidebar_item(page, "Orders")
        
        await run_test("partner_orders", page,
                      ["Order #", "Partner", "Description", "Amount", "Method", "Status", "Date"],
                      "/app/test_reports/iter169_09_partner_orders.jpeg")
        
        # ==== TEST 6: Partner Submissions ====
        print("\n--- [6] Partner Submissions ---")
        nav_ok = await navigate_to_sidebar_item(page, "Partner Submissions")
        if not nav_ok:
            nav_ok = await navigate_to_sidebar_item(page, "Submissions")
        
        await run_test("partner_submissions", page,
                      ["Partner", "Type", "Status"],
                      "/app/test_reports/iter169_10_partner_submissions.jpeg")
        
        # ==== TEST 7: Users ====
        print("\n--- [7] Users ---")
        await navigate_to_sidebar_item(page, "Users")
        
        await run_test("users", page, ["Name / Email", "Status"],
                      "/app/test_reports/iter169_11_users.jpeg")
        
        # ==== TEST 8: Customers ====
        print("\n--- [8] Customers ---")
        await navigate_to_sidebar_item(page, "Customers")
        
        await run_test("customers", page, ["Name", "Email", "Country", "Status", "Payment Methods"],
                      "/app/test_reports/iter169_12_customers.jpeg")
        
        # ==== TEST 9: Products > Products ====
        print("\n--- [9] Products > Products ---")
        await navigate_to_sidebar_item(page, "Products")
        await page.wait_for_timeout(500)
        await click_tab(page, "Products")
        
        await run_test("products_products", page, ["Name", "Category", "Billing", "Price", "Status"],
                      "/app/test_reports/iter169_13_products.jpeg")
        
        # ==== TEST 10: Products > Categories ====
        print("\n--- [10] Products > Categories ---")
        await click_tab(page, "Categories")
        
        await run_test("products_categories", page, ["Name", "Description", "Products", "Status"],
                      "/app/test_reports/iter169_14_categories.jpeg")
        
        # ==== TEST 11: Products > Promo Codes ====
        print("\n--- [11] Products > Promo Codes ---")
        await click_tab(page, "Promo Codes")
        
        await run_test("products_promo_codes", page, ["Code", "Discount", "Applies To", "Expiry", "Usage", "Created", "Status"],
                      "/app/test_reports/iter169_15_promo_codes.jpeg")
        
        # ==== TEST 12: Products > Terms ====
        print("\n--- [12] Products > Terms ---")
        await click_tab(page, "Terms")
        
        await run_test("products_terms", page, ["Title", "Status", "Created"],
                      "/app/test_reports/iter169_16_terms.jpeg")
        
        # ==== TEST 13: Subscriptions ====
        print("\n--- [13] Subscriptions ---")
        await navigate_to_sidebar_item(page, "Subscriptions")
        
        await run_test("subscriptions", page,
                      ["Sub #", "Customer Email", "Plan", "Amount", "Status"],
                      "/app/test_reports/iter169_17_subscriptions.jpeg")
        
        # ==== TEST 14: Orders ====
        print("\n--- [14] Orders ---")
        await navigate_to_sidebar_item(page, "Orders")
        
        await run_test("orders", page,
                      ["Date", "Order #", "Email", "Method", "Status"],
                      "/app/test_reports/iter169_18_orders.jpeg")
        
        # ==== TEST 15: Enquiries ====
        print("\n--- [15] Enquiries ---")
        await navigate_to_sidebar_item(page, "Enquiries")
        
        await run_test("enquiries", page, ["Date", "Order #", "Customer", "Status"],
                      "/app/test_reports/iter169_19_enquiries.jpeg")
        
        # ==== TEST 16: Resources ====
        print("\n--- [16] Resources ---")
        await navigate_to_sidebar_item(page, "Resources")
        
        await run_test("resources", page, ["Created", "Category", "Title / Visible"],
                      "/app/test_reports/iter169_20_resources.jpeg")
        
        # ==== TEST 17: Resources > Templates ====
        print("\n--- [17] Resources > Templates ---")
        await click_tab(page, "Templates")
        
        await run_test("resources_templates", page, ["Name", "Category", "Type"],
                      "/app/test_reports/iter169_21_resources_templates.jpeg")
        
        # ==== TEST 18: Resources > Email Templates ====
        print("\n--- [18] Resources > Email Templates ---")
        await click_tab(page, "Email Templates")
        
        await run_test("resources_email_templates", page, ["Name", "Subject"],
                      "/app/test_reports/iter169_22_email_templates.jpeg")
        
        # ==== TEST 19: Resources > Categories ====
        print("\n--- [19] Resources > Categories ---")
        await click_tab(page, "Categories")
        
        await run_test("resources_categories", page, ["Name", "Description"],
                      "/app/test_reports/iter169_23_res_categories.jpeg")
        
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
        
        print(f"\nPASSED: {total_passed} / {total_passed + total_failed}")
        print(f"FAILED: {failed_tests}")
        
        # Save results to JSON
        with open("/app/test_reports/iter169_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        await browser.close()
        return results

asyncio.run(run_all_tests())
