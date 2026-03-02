"""
Debug admin login - check for error messages
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
        
        # Navigate to /admin
        await page.goto(BASE_URL + "/admin")
        await page.wait_for_load_state("networkidle", timeout=15000)
        
        # Enter partner code
        await page.fill("input[placeholder='Partner code']", PARTNER_CODE)
        await page.click("button:has-text('Continue')")
        
        # Wait for email input
        await page.wait_for_selector("input[type='email']", timeout=8000)
        
        # Fill credentials
        await page.fill("input[type='email']", ADMIN_EMAIL)
        await page.fill("input[type='password']", ADMIN_PASSWORD)
        
        await page.screenshot(path="/app/test_reports/iter169_before_submit.jpeg", quality=40, full_page=False)
        
        # Click Sign In
        await page.click("button[type='submit']")
        
        # Wait a bit for response
        await page.wait_for_timeout(3000)
        
        print(f"URL after submit: {page.url}")
        
        await page.screenshot(path="/app/test_reports/iter169_after_submit.jpeg", quality=40, full_page=False)
        
        # Check for error messages
        error_text = await page.evaluate("""
            () => {
                const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"], [class*="Error"]'));
                return errorElements.map(el => el.textContent).join(", ");
            }
        """)
        if error_text:
            print(f"Error messages found: {error_text}")
        
        # Check page content
        content = await page.evaluate("() => document.body.innerText")
        print(f"Page content after submit: {content[:600]}")
        
        # Check localStorage / sessionStorage for auth token
        auth_data = await page.evaluate("""
            () => {
                const keys = Object.keys(localStorage);
                const result = {};
                keys.forEach(k => { result[k] = localStorage.getItem(k); });
                return result;
            }
        """)
        print(f"localStorage keys: {list(auth_data.keys())}")
        
        # Check cookies
        cookies = await context.cookies()
        print(f"Cookies: {[c['name'] for c in cookies]}")
        
        await browser.close()

asyncio.run(debug_login())
