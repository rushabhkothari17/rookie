"""
Debug script for admin login flow
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
        
        # Navigate to /admin first
        print("Navigating to /admin...")
        await page.goto(BASE_URL + "/admin")
        await page.wait_for_load_state("networkidle", timeout=15000)
        print(f"URL after /admin: {page.url}")
        
        await page.screenshot(path="/app/test_reports/iter169_debug_1.jpeg", quality=40, full_page=False)
        
        content = await page.evaluate("() => document.body.innerText.substring(0, 400)")
        print(f"Page content: {content}")
        
        # Check all inputs
        inputs = await page.query_selector_all("input")
        for inp in inputs:
            inp_type = await inp.get_attribute("type")
            inp_placeholder = await inp.get_attribute("placeholder")
            inp_name = await inp.get_attribute("name")
            print(f"Input: type={inp_type}, placeholder={inp_placeholder}, name={inp_name}")
        
        # Enter partner code
        code_input = await page.query_selector("input[placeholder='Partner code']")
        if code_input:
            print("Found partner code input, filling...")
            await code_input.fill(PARTNER_CODE)
            
            # Find continue button
            cont_btn = await page.query_selector("button:has-text('Continue')")
            if cont_btn:
                await cont_btn.click()
                await page.wait_for_load_state("networkidle", timeout=10000)
                print(f"URL after Continue: {page.url}")
                
                await page.screenshot(path="/app/test_reports/iter169_debug_2.jpeg", quality=40, full_page=False)
                
                content2 = await page.evaluate("() => document.body.innerText.substring(0, 400)")
                print(f"Page content after partner code: {content2}")
                
                # Check inputs again
                inputs2 = await page.query_selector_all("input")
                for inp in inputs2:
                    inp_type = await inp.get_attribute("type")
                    inp_placeholder = await inp.get_attribute("placeholder")
                    inp_name = await inp.get_attribute("name")
                    print(f"Input: type={inp_type}, placeholder={inp_placeholder}, name={inp_name}")
                
                # Try to find email input
                email_inp = await page.query_selector("input[type='email']")
                if email_inp:
                    print("Found email input!")
                    await email_inp.fill(ADMIN_EMAIL)
                    pw_inp = await page.query_selector("input[type='password']")
                    if pw_inp:
                        await pw_inp.fill(ADMIN_PASSWORD)
                    
                    # Find submit button
                    btns = await page.query_selector_all("button")
                    for btn in btns:
                        btn_text = await btn.inner_text()
                        btn_type = await btn.get_attribute("type")
                        print(f"Button: text={btn_text}, type={btn_type}")
                    
                    submit = await page.query_selector("button[type='submit']")
                    if submit:
                        await submit.click()
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        print(f"URL after login: {page.url}")
                        
                        await page.screenshot(path="/app/test_reports/iter169_debug_3.jpeg", quality=40, full_page=False)
                        
                        # Navigate to admin
                        await page.goto(BASE_URL + "/admin")
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        print(f"URL at admin: {page.url}")
                        
                        await page.screenshot(path="/app/test_reports/iter169_debug_4.jpeg", quality=40, full_page=False)
                        
                        content3 = await page.evaluate("() => document.body.innerText.substring(0, 600)")
                        print(f"Admin page content: {content3}")
                else:
                    print("ERROR: No email input found after partner code!")
        else:
            print("ERROR: No partner code input found!")
        
        await browser.close()

asyncio.run(debug_login())
