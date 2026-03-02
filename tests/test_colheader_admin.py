"""
Test ColHeader implementation across all 18 admin table sections.
Key fixes:
- Case-insensitive comparison (ColHeader uses CSS uppercase)
- Sidebar items have role='tab' (not aside links)
- Proper wait for admin panel to load
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
    """Full login flow with proper wait for admin panel"""
    await page.goto(BASE_URL + "/admin")
    await page.wait_for_load_state("networkidle", timeout=15000)
    
    # Partner code
    await page.fill("input[placeholder='Partner code']", PARTNER_CODE)
    await page.click("button:has-text('Continue')")
    await page.wait_for_selector("input[type='email']", timeout=8000)
    
    # Admin credentials
    await page.fill("input[type='email']", ADMIN_EMAIL)
    await page.fill("input[type='password']", ADMIN_PASSWORD)
    await page.click("button[type='submit']")
    
    # Wait for admin panel to load (wait for "Control Panel" text or sidebar nav item)
    try:
        await page.wait_for_selector("text=Control Panel", timeout=12000)
        print("Admin panel loaded - found 'Control Panel'")
    except:
        await page.wait_for_timeout(4000)
        print("Using timeout fallback for admin load")
    
    final_url = page.url
    print(f"Final URL: {final_url}")
    content = await page.evaluate("() => document.body.innerText.substring(0, 200)")
    print(f"Admin content: {content}")
    
    return "login" not in final_url or "Control Panel" in content

async def find_col_headers(page, expected_labels):
    """
    Find ColHeader buttons in th elements - case insensitive comparison
    ColHeader CSS class 'uppercase' makes innerText uppercase in browsers
    """
    # Get all th button texts
    th_buttons = await page.query_selector_all("th button")
    th_texts = []
    for btn in th_buttons:
        try:
            text = await btn.inner_text()
            is_visible = await btn.is_visible()
            if is_visible:
                th_texts.append(text.strip())
        except:
            pass
    
    print(f"  th button texts: {th_texts}")
    
    found = []
    missing = []
    for label in expected_labels:
        found_it = False
        for text in th_texts:
            # Case-insensitive comparison - CSS uppercase affects innerText
            if label.upper() == text.upper() or label.upper() in text.upper():
                found.append(label)
                found_it = True
                break
        if not found_it:
            missing.append(label)
    
    return found, missing

async def test_popover(page):
    """Click first visible th button and verify popover with Sort section"""
    th_buttons = await page.query_selector_all("th button")
    
    for btn in th_buttons:
        try:
            is_visible = await btn.is_visible()
            if not is_visible:
                continue
            
            btn_text = await btn.inner_text()
            await btn.click()
            await page.wait_for_timeout(700)
            
            # Check for Radix popover
            popover = await page.query_selector("[data-radix-popper-content-wrapper]")
            if popover and await popover.is_visible():
                content = await popover.inner_text()
                has_sort = "SORT" in content.upper() or "Sort" in content
                has_filter = "FILTER" in content.upper() or "Filter" in content
                
                # Check for specific sort buttons
                asc_btn = await popover.query_selector("button")
                
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(400)
                return True, f"'{btn_text.strip()}': Sort={has_sort}, Filter={has_filter}, preview='{content[:60]}'"
            
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
        except Exception as e:
            pass
    
    return False, "No popover found on any th button"

async def nav_to(page, label):
    """Navigate via sidebar - sidebar items have role='tab'"""
    # Try role='tab' items first (they are the sidebar items)
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
    
    # Try regular a/button links
    links = await page.query_selector_all("a, button")
    for link in links:
        try:
            text = await link.inner_text()
            if text.strip().upper() == label.upper():
                is_visible = await link.is_visible()
                if is_visible:
                    await link.click()
                    await page.wait_for_timeout(1500)
                    return True
        except:
            pass
    
    return False

async def check_no_old_filter_bar(page):
    """Check no standalone search/select filter bars outside tables"""
    select_count = await page.evaluate("""
        () => {
            const allSelects = Array.from(document.querySelectorAll('select'));
            return allSelects.filter(s => {
                if (!s.offsetParent) return false;
                let p = s.parentElement;
                while (p) {
                    if (['TABLE','THEAD','TBODY','TR','TH','TD'].includes(p.tagName)) return false;
                    p = p.parentElement;
                }
                return true;
            }).length;
        }
    """)
    return select_count == 0, f"{select_count} selects outside table"

async def run_test(name, page, expected_labels, do_popover=True):
    """Run test for a specific tab"""
    found, missing = await find_col_headers(page, expected_labels)
    print(f"  Found: {found}")
    print(f"  Missing: {missing}")
    
    popover_ok = False
    popover_msg = "Skipped"
    if do_popover and found:
        popover_ok, popover_msg = await test_popover(page)
        print(f"  Popover: {popover_ok} - {popover_msg}")
    
    filter_ok, filter_msg = await check_no_old_filter_bar(page)
    print(f"  No old filter bar: {filter_ok} ({filter_msg})")
    
    passed = len(missing) == 0
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
        ok = await login_to_admin(page)
        if not ok:
            print("CRITICAL: Login failed")
            return
        
        print("Login OK!")
        await page.screenshot(path="/app/test_reports/iter169_04_admin.jpeg", quality=40, full_page=False)
        
        # Get available sidebar items
        tabs = await page.query_selector_all("[role='tab']")
        tab_texts = []
        for t in tabs:
            try:
                text = await t.inner_text()
                if text.strip():
                    tab_texts.append(text.strip())
            except:
                pass
        print(f"Sidebar tabs: {tab_texts}")
        
        # ==== [1] Plans > License Plans ====
        print("\n[1] Plans > License Plans")
        await nav_to(page, "Plans")
        await page.wait_for_timeout(500)
        # Check if there are sub-tabs for Plans
        subtabs = await page.query_selector_all("[role='tabpanel'] [role='tab'], .tab-list [role='tab']")
        print(f"  Plans sub-tabs: {[await t.inner_text() for t in subtabs]}")
        
        await run_test("plans_license_plans", page, ["Plan", "Price", "Orgs", "Status", "Created"])
        await page.screenshot(path="/app/test_reports/iter169_05_plans.jpeg", quality=40, full_page=False)
        
        # ==== [2] Plans > One-Time Rates ====
        print("\n[2] Plans > One-Time Rates")
        # The rates table is on the same Plans page, scroll to it
        await page.evaluate("window.scrollTo(0, 800)")
        await page.wait_for_timeout(500)
        
        found_r, missing_r = await find_col_headers(page, ["Module", "Price / Unit", "Currency", "Status"])
        print(f"  Found: {found_r}, Missing: {missing_r}")
        
        # Try scrolling to find rates section
        if missing_r:
            await page.evaluate("window.scrollTo(0, 1500)")
            await page.wait_for_timeout(500)
            found_r, missing_r = await find_col_headers(page, ["Module", "Price / Unit", "Currency", "Status"])
            print(f"  After scroll - Found: {found_r}, Missing: {missing_r}")
        
        popover_ok_r = False
        if found_r:
            popover_ok_r, msg = await test_popover(page)
            print(f"  Popover: {popover_ok_r} - {msg}")
        
        results["plans_one_time_rates"] = {
            "found": found_r, "missing": missing_r,
            "popover_ok": popover_ok_r,
            "pass": len(missing_r) == 0
        }
        await page.screenshot(path="/app/test_reports/iter169_06_rates.jpeg", quality=40, full_page=False)
        
        # ==== [3] Plans > Coupons ====
        print("\n[3] Plans > Coupons")
        # Scroll further for coupons
        await page.evaluate("window.scrollTo(0, 2500)")
        await page.wait_for_timeout(500)
        
        found_c, missing_c = await find_col_headers(page, ["Code", "Discount", "Applies To", "Expiry", "Uses", "Status"])
        print(f"  Found: {found_c}, Missing: {missing_c}")
        
        if missing_c:
            await page.evaluate("window.scrollTo(0, 3500)")
            await page.wait_for_timeout(500)
            found_c, missing_c = await find_col_headers(page, ["Code", "Discount", "Applies To", "Expiry", "Uses", "Status"])
            print(f"  After scroll - Found: {found_c}, Missing: {missing_c}")
        
        popover_ok_c = False
        if found_c:
            popover_ok_c, msg = await test_popover(page)
            print(f"  Popover: {popover_ok_c} - {msg}")
        
        results["plans_coupons"] = {
            "found": found_c, "missing": missing_c,
            "popover_ok": popover_ok_c,
            "pass": len(missing_c) == 0
        }
        await page.screenshot(path="/app/test_reports/iter169_07_coupons.jpeg", quality=40, full_page=False)
        
        # ==== [4] Partner Subscriptions ====
        print("\n[4] Partner Subscriptions")
        await nav_to(page, "Partner Subscriptions")
        await run_test("partner_subscriptions", page, 
                      ["Sub #", "Partner", "Plan", "Amount", "Interval", "Method", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_08_partner_subs.jpeg", quality=40, full_page=False)
        
        # ==== [5] Partner Orders ====
        print("\n[5] Partner Orders")
        await nav_to(page, "Partner Orders")
        await run_test("partner_orders", page,
                      ["Order #", "Partner", "Description", "Amount", "Method", "Status", "Date"])
        await page.screenshot(path="/app/test_reports/iter169_09_partner_orders.jpeg", quality=40, full_page=False)
        
        # ==== [6] Partner Submissions ====
        print("\n[6] Partner Submissions")
        await nav_to(page, "Partner Submissions")
        await run_test("partner_submissions", page, ["Partner", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_10_submissions.jpeg", quality=40, full_page=False)
        
        # ==== [7] Users ====
        print("\n[7] Users")
        await nav_to(page, "Users")
        await run_test("users", page, ["Name / Email", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_11_users.jpeg", quality=40, full_page=False)
        
        # ==== [8] Customers ====
        print("\n[8] Customers")
        await nav_to(page, "Customers")
        await run_test("customers", page, ["Name", "Email", "Country", "Status", "Payment Methods"])
        await page.screenshot(path="/app/test_reports/iter169_12_customers.jpeg", quality=40, full_page=False)
        
        # ==== [9] Products > Products ====
        print("\n[9] Products > Products")
        await nav_to(page, "Products")
        await page.wait_for_timeout(500)
        # Click Products sub-tab if available
        await nav_to(page, "Products")  # might click sub-tab within Products section
        await run_test("products_products", page, ["Name", "Category", "Billing", "Price", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_13_products.jpeg", quality=40, full_page=False)
        
        # ==== [10] Products > Categories ====
        print("\n[10] Products > Categories")
        await nav_to(page, "Categories")
        await run_test("products_categories", page, ["Name", "Description", "Products", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_14_prod_cats.jpeg", quality=40, full_page=False)
        
        # ==== [11] Products > Promo Codes ====
        print("\n[11] Products > Promo Codes")
        await nav_to(page, "Promo Codes")
        if not results.get("products_promo_codes"):
            await nav_to(page, "Filters")
        await run_test("products_promo_codes", page, ["Code", "Discount", "Applies To", "Expiry", "Usage", "Created", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_15_promo_codes.jpeg", quality=40, full_page=False)
        
        # ==== [12] Products > Terms ====
        print("\n[12] Products > Terms")
        await nav_to(page, "Terms")
        await run_test("products_terms", page, ["Title", "Status", "Created"])
        await page.screenshot(path="/app/test_reports/iter169_16_terms.jpeg", quality=40, full_page=False)
        
        # ==== [13] Subscriptions ====
        print("\n[13] Subscriptions")
        await nav_to(page, "Subscriptions")
        await run_test("subscriptions", page, ["Sub #", "Customer Email", "Plan", "Amount", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_17_subs.jpeg", quality=40, full_page=False)
        
        # ==== [14] Orders ====
        print("\n[14] Orders")
        await nav_to(page, "Orders")
        await run_test("orders", page, ["Date", "Order #", "Email", "Method", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_18_orders.jpeg", quality=40, full_page=False)
        
        # ==== [15] Enquiries ====
        print("\n[15] Enquiries")
        await nav_to(page, "Enquiries")
        await run_test("enquiries", page, ["Date", "Order #", "Customer", "Status"])
        await page.screenshot(path="/app/test_reports/iter169_19_enquiries.jpeg", quality=40, full_page=False)
        
        # ==== [16] Resources ====
        print("\n[16] Resources")
        await nav_to(page, "Resources")
        await run_test("resources", page, ["Created", "Category", "Title / Visible"])
        await page.screenshot(path="/app/test_reports/iter169_20_resources.jpeg", quality=40, full_page=False)
        
        # Check Resources sub-tabs
        res_tabs = await page.query_selector_all("[role='tab']")
        res_tab_texts = []
        for t in res_tabs:
            try:
                text = await t.inner_text()
                if text.strip():
                    res_tab_texts.append(text.strip())
            except:
                pass
        print(f"  Resources sub-tabs visible: {res_tab_texts[-10:]}")  # last 10
        
        # ==== [17] Resources > Templates ====
        print("\n[17] Resources > Templates")
        await nav_to(page, "Templates")
        await run_test("resources_templates", page, ["Name", "Category", "Type"])
        await page.screenshot(path="/app/test_reports/iter169_21_templates.jpeg", quality=40, full_page=False)
        
        # ==== [18] Resources > Email Templates ====
        print("\n[18] Resources > Email Templates")
        await nav_to(page, "Email Templates")
        await run_test("resources_email_templates", page, ["Name", "Subject"])
        await page.screenshot(path="/app/test_reports/iter169_22_email_tpls.jpeg", quality=40, full_page=False)
        
        # ==== [19] Resources > Categories ====
        print("\n[19] Resources > Categories")
        await nav_to(page, "Categories")
        await run_test("resources_categories", page, ["Name", "Description"])
        await page.screenshot(path="/app/test_reports/iter169_23_res_cats.jpeg", quality=40, full_page=False)
        
        # ==== SUMMARY ====
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
            print(f"  {status}: {name}")
            if result.get("missing"):
                print(f"    Missing: {result['missing']}")
            if result.get("found"):
                print(f"    Found: {result['found']}")
            if result.get("popover_ok"):
                print(f"    Popover: OK - {result.get('popover_msg', '')[:60]}")
        
        total = passed_count + failed_count
        print(f"\nPASSED: {passed_count}/{total} ({int(passed_count/total*100) if total else 0}%)")
        if failed_list:
            print(f"FAILED: {failed_list}")
        
        with open("/app/test_reports/iter169_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        await browser.close()

asyncio.run(run_all_tests())
