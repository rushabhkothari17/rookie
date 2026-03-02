"""
Debug script for admin login flow - with better waits
"""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://admin-column-headers.preview.emergentagent.com"
PARTNER_CODE = "automate-accounts"
ADMIN_EMAIL = "admin@automateaccounts.local"
ADMIN_PASSWORD = "ChangeMe123!"

async def debug_login():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        page.on("console", lambda msg: print(f"CONSOLE[{msg.type}]: {msg.text}"))
        
        # Navigate to /admin first
        print("Navigating to /admin...")
        await page.goto(BASE_URL + "/admin")
        await page.wait_for_load_state("networkidle", timeout=15000)
        print(f"URL: {page.url}")
        
        # Enter partner code
        await page.fill("input[placeholder='Partner code']", PARTNER_CODE)
        await page.screenshot(path="/app/test_reports/iter169_debug_1.jpeg", quality=40, full_page=False)
        
        # Click continue
        await page.click("button:has-text('Continue')")
        
        # Wait for email input to appear
        try:
            await page.wait_for_selector("input[type='email'], input[placeholder*='mail'], input[name='email']", timeout=8000)
            print("Email input appeared!")
        except Exception as e:
            print(f"Email input not found: {e}")
            await page.wait_for_timeout(2000)
        
        await page.screenshot(path="/app/test_reports/iter169_debug_2.jpeg", quality=40, full_page=False)
        print(f"URL after Continue: {page.url}")
        
        # Check ALL visible inputs
        all_inputs = await page.query_selector_all("input")
        print(f"Number of inputs: {len(all_inputs)}")
        for inp in all_inputs:
            inp_type = await inp.get_attribute("type")
            inp_placeholder = await inp.get_attribute("placeholder")
            inp_name = await inp.get_attribute("name")
            is_visible = await inp.is_visible()
            print(f"  Input: type={inp_type}, placeholder={inp_placeholder}, name={inp_name}, visible={is_visible}")
        
        # Check all buttons
        all_buttons = await page.query_selector_all("button")
        for btn in all_buttons:
            btn_text = await btn.inner_text()
            btn_type = await btn.get_attribute("type")
            is_visible = await btn.is_visible()
            print(f"  Button: text='{btn_text}', type={btn_type}, visible={is_visible}")
        
        # Check full page text
        full_text = await page.evaluate("() => document.body.innerText")
        print(f"Full page text: {full_text[:800]}")
        
        await browser.close()

asyncio.run(debug_login())
