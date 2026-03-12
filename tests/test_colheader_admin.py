"""
Final comprehensive ColHeader test - all 18+ admin table sections.
Key fixes applied:
1. Case-insensitive comparison (CSS uppercase)
2. Sidebar items have role='tab' -> use nav_to for sidebar navigation
3. Plans sub-tabs: click by text within tablist
4. Products sub-tabs: click by text within tablist
5. Resources sub-tabs: prefer content-area tabs over sidebar tabs (x>400)
6. Partner Submissions: empty state - note that table only renders with data
7. Subscriptions: Amount/Tax/Currency use plain <th> not ColHeader (bug to report)
"""
import asyncio
import json
from playwright.async_api import async_playwright

BASE_URL = "https://partner-onboarding-1.preview.emergentagent.com"
PARTNER_CODE = "automate-accounts"
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

results = {}
bugs_found = []

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
    print(f"Logged in - URL: {page.url}")

async def get_th_button_texts(page):
    """Get visible th button texts (case-insensitive aware)"""
    th_buttons = await page.query_selector_all("th button")
    texts = []
    for btn in th_buttons:
        try:
            text = await btn.inner_text()
            is_visible = await btn.is_visible()
            if is_visible and text.strip():
                texts.append(text.strip())
        except:
            pass
    return texts

async def find_col_headers(page, expected_labels):
    """Case-insensitive match against th button texts"""
    th_texts = await get_th_button_texts(page)
    print(f"  th button texts: {th_texts}")
    
    found = []
    missing = []
    for label in expected_labels:
        found_it = any(label.upper() == t.upper() for t in th_texts)
        if found_it:
            found.append(label)
        else:
            missing.append(label)
    return found, missing

async def test_popover_on_first_button(page):
    """Click first th button and verify Sort+Filter popover"""
    th_buttons = await page.query_selector_all("th button")
    for btn in th_buttons:
        try:
            is_visible = await btn.is_visible()
            if not is_visible:
                continue
            btn_text = await btn.inner_text()
            await btn.click()
            await page.wait_for_timeout(700)
            popover = await page.query_selector("[data-radix-popper-content-wrapper]")
            if popover and await popover.is_visible():
                content = await popover.inner_text()
                has_sort = "SORT" in content.upper()
                has_filter = "FILTER" in content.upper()
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(400)
                return True, f"'{btn_text.strip()}': Sort={has_sort}, Filter={has_filter}"
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
        except:
            pass
    return False, "No popover"

async def nav_sidebar(page, label):
    """Navigate via sidebar (role='tab' items)"""
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
    """
    Click a sub-tab within the main content area (x > 400 to avoid sidebar).
    Used for: Plans sub-tabs, Products sub-tabs, Resources sub-tabs.
    """
    tabs = await page.query_selector_all("[role='tab']")
    content_tabs = []
    
    for tab in tabs:
        try:
            text = await tab.inner_text()
            if text.strip().upper() == label.upper():
                is_visible = await tab.is_visible()
                if is_visible:
                    bb = await tab.bounding_box()
                    if bb and bb['x'] > 400:  # content area, not sidebar
                        content_tabs.append((tab, bb['x'], bb['y']))
        except:
            pass
    
    if content_tabs:
        # Click the first content area tab
        await content_tabs[0][0].click()
        await page.wait_for_timeout(1000)
        return True
    
    # Fallback: try any visible tab with this label
    for tab in tabs:
        try:
            text = await tab.inner_text()
            if text.strip().upper() == label.upper():
                is_visible = await tab.is_visible()
                if is_visible:
                    await tab.click()
                    await page.wait_for_timeout(1000)
                    return True
        except:
            pass
    return False

async def run_test(name, page, expected_labels, extra_notes=""):
    """Run a single tab test"""
    found, missing = await find_col_headers(page, expected_labels)
    print(f"  Found: {found}")
    print(f"  Missing: {missing}")
    
    popover_ok = False
    popover_msg = "No ColHeaders found"
    if found:
        popover_ok, popover_msg = await test_popover_on_first_button(page)
        print(f"  Popover: {popover_ok} - {popover_msg}")
    
    passed = len(missing) == 0
    results[name] = {
        "found": found,
        "missing": missing,
        "popover_ok": popover_ok,
        "popover_msg": popover_msg,
        "pass": passed,
        "notes": extra_notes
    }
    return passed

async def run_all_tests():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        print("=" * 60)
        print("ColHeader Admin Panel Test Suite - Iteration 169 (Final)")
        print("=" * 60)
        
        await login_to_admin(page)
        await page.screenshot(path="/app/test_reports/iter169_04_admin.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [1] Plans > License Plans
        # ============================================================
        print("\n[1] Plans > License Plans")
        await nav_sidebar(page, "Plans")
        # Plans page has sub-tabs: License Plans, One-Time Rates, Coupons, Coupon Usage
        await nav_content_tab(page, "License Plans")
        
        await run_test("plans_license_plans", page, ["Plan", "Price", "Orgs", "Status", "Created"])
        await page.screenshot(path="/app/test_reports/iter169_05_plans.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [2] Plans > One-Time Rates
        # ============================================================
        print("\n[2] Plans > One-Time Rates")
        await nav_content_tab(page, "One-Time Rates")
        
        await run_test("plans_one_time_rates", page, ["Module", "Price / Unit", "Currency", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_06_rates.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [3] Plans > Coupons
        # ============================================================
        print("\n[3] Plans > Coupons")
        await nav_content_tab(page, "Coupons")
        
        await run_test("plans_coupons", page, ["Code", "Discount", "Applies To", "Expiry", "Uses", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_07_coupons.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [4] Partner Subscriptions
        # ============================================================
        print("\n[4] Partner Subscriptions")
        await nav_sidebar(page, "Partner Subscriptions")
        
        await run_test("partner_subscriptions", page,
                      ["Sub #", "Partner", "Plan", "Amount", "Interval", "Method", "Status", "Next Billing", "Expiry"])
        await page.screenshot(path="/app/test_reports/iter169_08_psubs.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [5] Partner Orders
        # ============================================================
        print("\n[5] Partner Orders")
        await nav_sidebar(page, "Partner Orders")
        
        await run_test("partner_orders", page,
                      ["Order #", "Partner", "Description", "Amount", "Method", "Status", "Date"])
        await page.screenshot(path="/app/test_reports/iter169_09_porders.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [6] Partner Submissions
        # ============================================================
        print("\n[6] Partner Submissions")
        await nav_sidebar(page, "Partner Submissions")
        await page.wait_for_timeout(1000)
        
        # Default filter is 'pending' - if no pending submissions, table is empty
        # Try switching to 'all' to see if table renders
        th_texts = await get_th_button_texts(page)
        if not th_texts:
            print("  Table is empty state (no pending submissions) - trying 'all' status")
            # The statusFilter state is internal, but we can check the empty state
            # The ColHeader IS in the code but only shows when displayItems.length > 0
            # This is expected behavior - verified from code review
            results["partner_submissions"] = {
                "found": [],
                "missing": ["Partner", "Type", "Status"],
                "popover_ok": False,
                "pass": False,
                "notes": "Table renders empty state (no pending submissions). ColHeader IS in code (lines 155-160 of PartnerSubmissionsTab.tsx) but only renders when displayItems.length > 0. This is a conditional rendering issue."
            }
        else:
            await run_test("partner_submissions", page, ["Partner", "Status"])
        
        await page.screenshot(path="/app/test_reports/iter169_10_submissions.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [7] Users
        # ============================================================
        print("\n[7] Users")
        await nav_sidebar(page, "Users")
        
        await run_test("users", page, ["Name / Email", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_11_users.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [8] Customers
        # ============================================================
        print("\n[8] Customers")
        await nav_sidebar(page, "Customers")
        
        await run_test("customers", page, ["Name", "Email", "Country", "Status", "Payment Methods"])
        await page.screenshot(path="/app/test_reports/iter169_12_customers.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [9] Products > Products
        # ============================================================
        print("\n[9] Products > Products")
        await nav_sidebar(page, "Products")
        await page.wait_for_timeout(500)
        await nav_content_tab(page, "Products")  # Products sub-tab within Products page
        
        await run_test("products_products", page, ["Name", "Category", "Billing", "Price", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_13_products.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [10] Products > Categories
        # ============================================================
        print("\n[10] Products > Categories")
        await nav_content_tab(page, "Categories")
        
        await run_test("products_categories", page, ["Name", "Description", "Products", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_14_prod_cats.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [11] Products > Promo Codes
        # ============================================================
        print("\n[11] Products > Promo Codes")
        await nav_content_tab(page, "Promo Codes")
        
        await run_test("products_promo_codes", page, ["Code", "Discount", "Applies To", "Expiry", "Usage", "Created", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_15_promo.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [12] Products > Terms
        # ============================================================
        print("\n[12] Products > Terms")
        await nav_content_tab(page, "Terms")
        
        await run_test("products_terms", page, ["Title", "Status", "Created"])
        await page.screenshot(path="/app/test_reports/iter169_16_terms.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [13] Subscriptions
        # ============================================================
        print("\n[13] Subscriptions")
        await nav_sidebar(page, "Subscriptions")
        await page.wait_for_timeout(1000)
        
        # Check all th elements (including non-ColHeader ones)
        ths = await page.query_selector_all("th")
        all_th_texts = []
        for th in ths:
            try:
                text = await th.inner_text()
                is_visible = await th.is_visible()
                if is_visible and text.strip():
                    all_th_texts.append(text.strip())
            except:
                pass
        print(f"  All th texts (incl. non-ColHeader): {all_th_texts}")
        
        # Note: Amount, Tax, Currency use plain <th> not ColHeader (code lines 310-312)
        # Only test columns that actually have ColHeader
        th_btn_texts = await get_th_button_texts(page)
        print(f"  ColHeader th button texts: {th_btn_texts}")
        
        # Test what the task says should have ColHeader
        expected_with_colheader = ["Created", "Sub #", "Processor ID", "Customer Email", "Plan", "Renewal", "Start", "Contract End", "Payment", "Status"]
        expected_missing_colheader = ["Amount", "Tax", "Currency"]
        
        found, missing = await find_col_headers(page, expected_with_colheader)
        print(f"  Found ColHeaders: {found}")
        print(f"  Missing from expected-with-ColHeader: {missing}")
        
        # Check if Amount/Tax/Currency have plain th (confirmed bug)
        amount_has_th = any("AMOUNT" == t.upper() for t in all_th_texts)
        tax_has_th = any("TAX" == t.upper() for t in all_th_texts)
        currency_has_th = any("CURRENCY" == t.upper() for t in all_th_texts)
        print(f"  Amount has plain <th> (not ColHeader): {amount_has_th}")
        print(f"  Tax has plain <th> (not ColHeader): {tax_has_th}")
        print(f"  Currency has plain <th> (not ColHeader): {currency_has_th}")
        
        if amount_has_th and tax_has_th and currency_has_th:
            bugs_found.append({
                "tab": "Subscriptions",
                "issue": "Amount, Tax, Currency columns use plain <th> instead of ColHeader (SubscriptionsTab.tsx lines 310-312)",
                "severity": "MEDIUM",
                "expected": "ColHeader with sort/filter on Amount, Tax, Currency columns",
                "actual": "Plain <th> elements without sort/filter functionality"
            })
        
        popover_ok, popover_msg = await test_popover_on_first_button(page)
        print(f"  Popover: {popover_ok} - {popover_msg}")
        
        results["subscriptions"] = {
            "found": found,
            "missing": missing,
            "extra_plain_th": {"Amount": amount_has_th, "Tax": tax_has_th, "Currency": currency_has_th},
            "popover_ok": popover_ok,
            "pass": len(missing) == 0,
            "notes": "Amount/Tax/Currency are plain <th> elements, not ColHeader. Bug reported."
        }
        await page.screenshot(path="/app/test_reports/iter169_17_subs.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [14] Orders
        # ============================================================
        print("\n[14] Orders")
        await nav_sidebar(page, "Orders")
        
        await run_test("orders", page, ["Date", "Order #", "Email", "Product(s)", "Sub #", "Processor ID", "Pay Date", "Method", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_18_orders.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [15] Enquiries
        # ============================================================
        print("\n[15] Enquiries")
        await nav_sidebar(page, "Enquiries")
        
        await run_test("enquiries", page, ["Date", "Order #", "Customer", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_19_enquiries.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [16] Resources (articles/content)
        # ============================================================
        print("\n[16] Resources")
        await nav_sidebar(page, "Resources")
        await nav_content_tab(page, "Resources")  # Click Resources sub-tab within Resources page
        
        await run_test("resources", page, ["Created", "Category", "Title / Visible"])
        await page.screenshot(path="/app/test_reports/iter169_20_resources.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [17] Resources > Templates
        # ============================================================
        print("\n[17] Resources > Templates")
        await nav_content_tab(page, "Templates")
        
        await run_test("resources_templates", page, ["Name", "Category", "Type"])
        await page.screenshot(path="/app/test_reports/iter169_21_res_tpls.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [18] Resources > Email Templates
        # ============================================================
        print("\n[18] Resources > Email Templates")
        # Need to click Email Templates in content area (x>400), not sidebar (x≈224)
        clicked = await nav_content_tab(page, "Email Templates")
        if not clicked:
            print("  Could not find content-area Email Templates tab")
        
        th_texts = await get_th_button_texts(page)
        print(f"  th button texts: {th_texts}")
        
        if not th_texts:
            print("  No th buttons - might be empty state or wrong tab clicked")
            # Let's try loading the email templates data - the table shows "No email templates found"
            # even with empty state it should render th elements
            # Try scrolling to find the table
            content = await page.evaluate("() => document.body.innerText.substring(0, 400)")
            print(f"  Page content: {content[:200]}")
        
        found_et, missing_et = await find_col_headers(page, ["Name", "Subject"])
        popover_ok_et = False
        if found_et:
            popover_ok_et, msg = await test_popover_on_first_button(page)
            print(f"  Popover: {popover_ok_et} - {msg}")
        
        results["resources_email_templates"] = {
            "found": found_et,
            "missing": missing_et,
            "popover_ok": popover_ok_et,
            "pass": len(missing_et) == 0
        }
        await page.screenshot(path="/app/test_reports/iter169_22_email_tpls.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # [19] Resources > Categories
        # ============================================================
        print("\n[19] Resources > Categories")
        # Need to click Categories in content area, not sidebar
        clicked = await nav_content_tab(page, "Categories")
        if not clicked:
            print("  Could not find content-area Categories tab")
        
        th_texts_cat = await get_th_button_texts(page)
        print(f"  th button texts: {th_texts_cat}")
        
        found_rc, missing_rc = await find_col_headers(page, ["Name", "Description"])
        popover_ok_rc = False
        if found_rc:
            popover_ok_rc, msg = await test_popover_on_first_button(page)
            print(f"  Popover: {popover_ok_rc} - {msg}")
        
        results["resources_categories"] = {
            "found": found_rc,
            "missing": missing_rc,
            "popover_ok": popover_ok_rc,
            "pass": len(missing_rc) == 0
        }
        await page.screenshot(path="/app/test_reports/iter169_23_res_cats.jpeg", quality=40, full_page=False)
        
        # ============================================================
        # FINAL SUMMARY
        # ============================================================
        print("\n" + "=" * 60)
        print("FINAL RESULTS SUMMARY")
        print("=" * 60)
        
        passed_count = 0
        failed_count = 0
        failed_list = []
        
        for name, result in results.items():
            status = "PASS" if result.get("pass") else "FAIL"
            if result.get("pass"):
                passed_count += 1
            else:
                failed_count += 1
                failed_list.append(name)
            
            extra = ""
            if result.get("popover_ok") and result.get("pass"):
                extra = " [popover OK]"
            print(f"  {status}: {name}{extra}")
            if result.get("missing"):
                print(f"    Missing: {result['missing']}")
        
        if bugs_found:
            print("\n--- BUGS FOUND ---")
            for bug in bugs_found:
                print(f"  BUG [{bug['severity']}]: {bug['tab']} - {bug['issue']}")
        
        total = passed_count + failed_count
        pct = int(passed_count / total * 100) if total else 0
        print(f"\nPASSED: {passed_count}/{total} ({pct}%)")
        if failed_list:
            print(f"FAILED: {failed_list}")
        
        # Save results
        with open("/app/test_reports/iter169_results.json", "w") as f:
            json.dump({
                "results": results,
                "bugs": bugs_found,
                "summary": {
                    "passed": passed_count,
                    "failed": failed_count,
                    "total": total,
                    "pass_rate": f"{pct}%"
                }
            }, f, indent=2)
        
        await browser.close()

asyncio.run(run_all_tests())
