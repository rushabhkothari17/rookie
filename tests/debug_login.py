"""
Debug navigation for failing tabs
"""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://platform-health-scan.preview.emergentagent.com"
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

async def nav_to(page, label):
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

async def debug_plans_subtabs(page):
    """Debug the Plans sub-tabs navigation"""
    print("\n=== DEBUG: Plans Sub-tabs ===")
    await nav_to(page, "Plans")
    await page.wait_for_timeout(1000)
    
    # Get ALL role='tab' elements on the page
    tabs = await page.query_selector_all("[role='tab']")
    print(f"Total [role='tab'] elements: {len(tabs)}")
    for tab in tabs:
        try:
            text = await tab.inner_text()
            is_visible = await tab.is_visible()
            parent_class = await page.evaluate("(el) => el.parentElement?.className || ''", tab)
            print(f"  tab: '{text.strip()}', visible={is_visible}, parent_class={parent_class[:50]}")
        except Exception as e:
            print(f"  Error reading tab: {e}")
    
    # Get all buttons that might be sub-tabs
    buttons = await page.query_selector_all("button")
    plan_buttons = []
    for btn in buttons:
        try:
            text = await btn.inner_text()
            if text.strip() in ["License Plans", "One-Time Rates", "Coupons", "Coupon Usage"]:
                is_visible = await btn.is_visible()
                plan_buttons.append((text.strip(), is_visible))
        except:
            pass
    print(f"Plans sub-tab buttons: {plan_buttons}")
    
    # Try clicking "One-Time Rates" via button 
    clicked = False
    for btn in buttons:
        try:
            text = await btn.inner_text()
            if text.strip() == "One-Time Rates":
                is_visible = await btn.is_visible()
                if is_visible:
                    print(f"Clicking 'One-Time Rates' button...")
                    await btn.click()
                    await page.wait_for_timeout(1000)
                    clicked = True
                    break
        except:
            pass
    
    if clicked:
        # Get th buttons now
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
        print(f"After clicking One-Time Rates - th buttons: {th_texts}")
    
    await page.screenshot(path="/app/test_reports/iter169_debug_plans.jpeg", quality=40, full_page=False)

async def debug_partner_submissions(page):
    """Debug Partner Submissions tab"""
    print("\n=== DEBUG: Partner Submissions ===")
    await nav_to(page, "Partner Submissions")
    await page.wait_for_timeout(1000)
    
    content = await page.evaluate("() => document.body.innerText.substring(0, 500)")
    print(f"Page content: {content}")
    
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
    print(f"th buttons: {th_texts}")
    
    # Also check for any table headers (th elements without buttons)
    ths = await page.query_selector_all("th")
    th_all_texts = []
    for th in ths:
        try:
            text = await th.inner_text()
            is_visible = await th.is_visible()
            if is_visible and text.strip():
                th_all_texts.append(text.strip())
        except:
            pass
    print(f"All th elements: {th_all_texts}")
    
    await page.screenshot(path="/app/test_reports/iter169_debug_submissions.jpeg", quality=40, full_page=False)

async def debug_products_subtabs(page):
    """Debug Products sub-tabs"""
    print("\n=== DEBUG: Products Sub-tabs ===")
    await nav_to(page, "Products")
    await page.wait_for_timeout(1000)
    
    # Look for sub-tabs within Products
    all_visible_tabs = await page.query_selector_all("[role='tab']")
    visible_tab_texts = []
    for tab in all_visible_tabs:
        try:
            text = await tab.inner_text()
            is_visible = await tab.is_visible()
            if is_visible:
                visible_tab_texts.append(text.strip())
        except:
            pass
    print(f"All visible [role='tab']: {visible_tab_texts}")
    
    # Look for Promo Codes / Terms buttons
    buttons = await page.query_selector_all("button")
    for btn in buttons:
        try:
            text = await btn.inner_text()
            if text.strip() in ["Products", "Categories", "Promo Codes", "Terms", "Filters"]:
                is_visible = await btn.is_visible()
                print(f"  Product sub-tab button: '{text.strip()}', visible={is_visible}")
        except:
            pass
    
    # Try clicking "Promo Codes"
    promo_clicked = False
    for btn in buttons:
        try:
            text = await btn.inner_text()
            if text.strip() == "Promo Codes":
                is_visible = await btn.is_visible()
                if is_visible:
                    print("Clicking 'Promo Codes'...")
                    await btn.click()
                    await page.wait_for_timeout(1000)
                    promo_clicked = True
                    break
        except:
            pass
    
    if not promo_clicked:
        print("Promo Codes button not found as visible button, trying Filters sidebar")
        await nav_to(page, "Filters")
        await page.wait_for_timeout(1000)
    
    th_buttons = await page.query_selector_all("th button")
    th_texts = [await btn.inner_text() for btn in th_buttons if await btn.is_visible()]
    print(f"After Promo Codes nav - th buttons: {th_texts}")
    
    await page.screenshot(path="/app/test_reports/iter169_debug_promo.jpeg", quality=40, full_page=False)

async def debug_resources_subtabs(page):
    """Debug Resources sub-tabs"""
    print("\n=== DEBUG: Resources Sub-tabs ===")
    await nav_to(page, "Resources")
    await page.wait_for_timeout(1000)
    
    # Get the Resources page's tab structure
    content = await page.evaluate("() => document.body.innerText.substring(0, 300)")
    print(f"Resources page content: {content}")
    
    # Get all visible tabs
    all_tabs = await page.query_selector_all("[role='tab']")
    visible_res_tabs = []
    for tab in all_tabs:
        try:
            text = await tab.inner_text()
            is_visible = await tab.is_visible()
            if is_visible and text.strip():
                visible_res_tabs.append(text.strip())
        except:
            pass
    print(f"Visible tabs while on Resources: {visible_res_tabs}")
    
    # Find the "Email Templates" tab that belongs to Resources (not Settings)
    # Resources sub-tabs should appear near the top of the Resources page
    # Settings Email Templates is a separate sidebar item
    
    # Try clicking "Email Templates" - need to find the right one
    tabs = await page.query_selector_all("[role='tab']")
    et_tabs = []
    for tab in tabs:
        try:
            text = await tab.inner_text()
            if "email template" in text.lower():
                is_visible = await tab.is_visible()
                bounding = await tab.bounding_box()
                et_tabs.append((text.strip(), is_visible, bounding))
        except:
            pass
    print(f"Email Template tabs: {et_tabs}")
    
    # Click the first visible Email Templates tab
    for tab in tabs:
        try:
            text = await tab.inner_text()
            if "email template" in text.lower():
                is_visible = await tab.is_visible()
                if is_visible:
                    print(f"Clicking 'Email Templates' tab...")
                    await tab.click()
                    await page.wait_for_timeout(1000)
                    break
        except:
            pass
    
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
    print(f"After Email Templates - th buttons: {th_texts}")
    
    await page.screenshot(path="/app/test_reports/iter169_debug_email_tpls.jpeg", quality=40, full_page=False)

async def debug_subscriptions_amount(page):
    """Debug Subscriptions tab - check for Amount column"""
    print("\n=== DEBUG: Subscriptions - Amount column ===")
    await nav_to(page, "Subscriptions")
    await page.wait_for_timeout(1000)
    
    # Get ALL th elements
    ths = await page.query_selector_all("th")
    th_all = []
    for th in ths:
        try:
            text = await th.inner_text()
            is_visible = await th.is_visible()
            if is_visible and text.strip():
                th_all.append(text.strip())
        except:
            pass
    print(f"All th texts: {th_all}")
    
    th_buttons = await page.query_selector_all("th button")
    th_btn_texts = []
    for btn in th_buttons:
        try:
            text = await btn.inner_text()
            is_visible = await btn.is_visible()
            if is_visible:
                th_btn_texts.append(text.strip())
        except:
            pass
    print(f"th button texts: {th_btn_texts}")
    
    await page.screenshot(path="/app/test_reports/iter169_debug_subs.jpeg", quality=40, full_page=False)

async def run_debug():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        await login_to_admin(page)
        print("Logged in!")
        
        await debug_plans_subtabs(page)
        await debug_partner_submissions(page)
        await debug_products_subtabs(page)
        await debug_resources_subtabs(page)
        await debug_subscriptions_amount(page)
        
        await browser.close()

asyncio.run(run_debug())
