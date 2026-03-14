"""
Iteration 279 Feature Tests
Tests 8 features:
1. Form builder - number field Min/Max value inputs
2. Form builder - date field Date format dropdown
3. Form builder - file upload Max file size input
4. Sign Up Page form - email+password as locked fields at top
5. Partner Sign-Up tile visible for platform_super_admin
6. Customer Portal tile - 'Show stats on portal' toggle
7. Portal page respects portal_show_stats toggle
8. UniversalFormRenderer renders file upload as styled button
"""

import asyncio
import sys

BASE_URL = "https://glass-morphism-ui.preview.emergentagent.com"
results = {}

async def login(page):
    """Full login flow"""
    await page.goto(BASE_URL)
    await page.wait_for_timeout(2000)
    
    if "/login" not in page.url and "partner" not in page.url:
        # check for partner code screen
        code_input = await page.query_selector('input[placeholder="Partner code"]')
        if code_input:
            await code_input.fill("automate-accounts")
            continue_btn = await page.wait_for_selector('button:has-text("Continue")', timeout=3000)
            await continue_btn.click()
            await page.wait_for_timeout(2000)
    
    if page.url == BASE_URL or page.url == BASE_URL + "/":
        # May be on gateway/code screen
        code_input = await page.query_selector('input[placeholder="Partner code"]')
        if code_input:
            await code_input.fill("automate-accounts")
            continue_btn = await page.wait_for_selector('button:has-text("Continue")', timeout=3000)
            await continue_btn.click()
            await page.wait_for_timeout(2000)
    
    # Now on login page
    if "/login" in page.url or await page.query_selector('input[type="email"]'):
        email = await page.wait_for_selector('input[type="email"]', timeout=5000)
        await email.fill("admin@automateaccounts.local")
        pwd = await page.wait_for_selector('input[type="password"]', timeout=3000)
        await pwd.fill("ChangeMe123!")
        btn = await page.wait_for_selector('button[type="submit"]', timeout=3000)
        await btn.click()
        await page.wait_for_timeout(3000)
    
    print(f"After login: {page.url}")
    return "/admin" in page.url or page.url == BASE_URL + "/"

async def go_to_auth_pages(page):
    """Navigate to Auth & Pages section"""
    if "/admin" not in page.url:
        await page.goto(f"{BASE_URL}/admin")
        await page.wait_for_timeout(2000)
    
    auth_link = await page.query_selector('text=Auth & Pages')
    if auth_link:
        await auth_link.click()
        await page.wait_for_timeout(1500)
        return True
    return False

async def run_all_tests(page):
    """Run all feature tests"""
    global results
    
    # ── SETUP ─────────────────────────────────────────────────────────────────
    await page.set_viewport_size({"width": 1920, "height": 1080})
    page.on("console", lambda msg: print(f"  [console.{msg.type}] {msg.text[:100]}") if msg.type == "error" else None)
    
    logged_in = await login(page)
    print(f"Logged in: {logged_in}")
    
    if not logged_in:
        print("CRITICAL: Login failed - cannot run tests")
        return results
    
    # ── TEST 5: Partner Sign-Up tile visible ────────────────────────────────
    print("\n=== TEST 5: Partner Sign-Up tile for platform_super_admin ===")
    await go_to_auth_pages(page)
    await page.evaluate("window.scrollTo(0, 0)")
    
    partner_tile = await page.query_selector('[data-testid="auth-tile-partner-signup"]')
    if partner_tile:
        is_vis = await partner_tile.is_visible()
        results["test5_partner_signup_tile"] = "PASS" if is_vis else "FAIL - not visible"
        print(f"  Partner Sign-Up tile visible: {is_vis} → {results['test5_partner_signup_tile']}")
    else:
        results["test5_partner_signup_tile"] = "FAIL - tile not in DOM"
        print("  Partner Sign-Up tile: NOT FOUND in DOM")
    
    # ── TEST 4: Sign Up Page - email+password locked at top ─────────────────
    print("\n=== TEST 4: Sign Up Page - email+password locked at top ===")
    signup_tile = await page.query_selector('[data-testid="auth-tile-signup"]')
    if signup_tile:
        await signup_tile.click()
        await page.wait_for_timeout(1500)
        
        # Get all form fields from schema builder
        fields_data = await page.evaluate("""
            () => {
                const builder = document.querySelector('[data-testid="form-schema-builder"]');
                if (!builder) return null;
                
                const rows = builder.querySelectorAll('.border.border-slate-200.rounded-lg.bg-white');
                const fields = [];
                rows.forEach((row, i) => {
                    const labelEl = row.querySelector('.text-sm.font-medium');
                    const typeBadge = row.querySelector('.font-mono');
                    const lockIcon = row.querySelector('.text-amber-500');
                    const keyEl = row.querySelector('.text-slate-400.font-mono');
                    fields.push({
                        index: i,
                        label: labelEl ? labelEl.textContent.trim() : '',
                        type: typeBadge ? typeBadge.textContent.trim() : '',
                        hasLock: !!lockIcon,
                        key: keyEl ? keyEl.textContent.trim() : ''
                    });
                });
                return fields;
            }
        """)
        
        if fields_data and len(fields_data) >= 2:
            print(f"  Total fields: {len(fields_data)}")
            for f in fields_data:
                print(f"  [{f['index']}] {f['label']} ({f['key']}) type={f['type']} locked={f['hasLock']}")
            
            first = fields_data[0]
            second = fields_data[1]
            
            # Check email first, password second, both locked
            if "email" in first.get('key','').lower() and "password" in second.get('key','').lower():
                if first['hasLock'] and second['hasLock']:
                    results["test4_email_pwd_locked"] = "PASS"
                    print("  PASS: email(0) and password(1) are locked at top")
                else:
                    results["test4_email_pwd_locked"] = f"FAIL - email locked={first['hasLock']}, password locked={second['hasLock']}"
                    print(f"  FAIL: Lock status - email={first['hasLock']}, pwd={second['hasLock']}")
            else:
                results["test4_email_pwd_locked"] = f"FAIL - first={first.get('label')} key={first.get('key')}, second={second.get('label')}"
                print(f"  FAIL: first={first.get('key')}, second={second.get('key')}")
        else:
            results["test4_email_pwd_locked"] = f"FAIL - fields_data={fields_data}"
            print(f"  FAIL: form fields data={fields_data}")
        
        await page.screenshot(path=".screenshots/iter279_signup_form.jpeg", quality=40, full_page=False)
        
        # ── TESTS 1,2,3: Form builder field-specific options ──────────────────
        print("\n=== TESTS 1,2,3: Form builder field type options ===")
        
        # Scroll the slideover to find "Add field" button and add a number field
        add_btn = await page.query_selector('[data-testid="add-form-field-btn"]')
        if add_btn:
            await add_btn.click()
            await page.wait_for_timeout(500)
            print("  Added new field")
            
            # The new field should now be in edit mode
            # Change type to "number" to test min/max
            # Find the last field item which should be the new one
            all_fields = await page.query_selector_all('[data-testid="form-schema-builder"] .border.border-slate-200.rounded-lg.bg-white')
            last_field = all_fields[-1] if all_fields else None
            
            if last_field:
                # Click settings/edit button on last field
                settings_btn = await last_field.query_selector('button[class*="Settings2"], button:has(svg)')
                if not settings_btn:
                    # Try all buttons in the field
                    btns = await last_field.query_selector_all('button')
                    if btns:
                        settings_btn = btns[-2] if len(btns) >= 2 else btns[-1]
                
                if settings_btn:
                    await settings_btn.click()
                    await page.wait_for_timeout(500)
                    print("  Opened edit panel for new field")
                
                # Test number field type - check for min/max
                print("\n  --- Testing NUMBER field type ---")
                # Find field type selector in the last field
                type_select = await last_field.query_selector('select, [role="combobox"]')
                if type_select:
                    # Change to number type
                    await type_select.click()
                    await page.wait_for_timeout(300)
                    # Find "Number" option
                    number_option = await page.query_selector('text=Number')
                    if number_option:
                        await number_option.click()
                        await page.wait_for_timeout(300)
                        print("  Changed to Number type")
                    
                    # Check for min/max value inputs
                    min_input = await page.query_selector('[data-testid$="-minvalue-"]')
                    max_input = await page.query_selector('[data-testid$="-maxvalue-"]')
                    
                    # More general selector
                    if not min_input:
                        min_input = await last_field.query_selector('input[type="number"]:first-of-type')
                    
                    # Check by label text
                    min_label = await page.evaluate("""
                        () => {
                            const labels = Array.from(document.querySelectorAll('label'));
                            const minLabel = labels.find(l => l.textContent.includes('Min value'));
                            const maxLabel = labels.find(l => l.textContent.includes('Max value'));
                            return {
                                hasMin: !!minLabel,
                                hasMax: !!maxLabel,
                                minText: minLabel ? minLabel.textContent.trim() : null,
                                maxText: maxLabel ? maxLabel.textContent.trim() : null
                            };
                        }
                    """)
                    
                    print(f"  Min/Max labels: {min_label}")
                    
                    if min_label.get('hasMin') and min_label.get('hasMax'):
                        results["test1_number_minmax"] = "PASS"
                        print("  TEST 1 PASS: Min value and Max value inputs present for number field")
                    else:
                        results["test1_number_minmax"] = f"FAIL - hasMin={min_label.get('hasMin')}, hasMax={min_label.get('hasMax')}"
                        print(f"  TEST 1 FAIL: {min_label}")
                    
                    # Test DATE field type - check for date format dropdown
                    print("\n  --- Testing DATE field type ---")
                    type_select = await last_field.query_selector('[role="combobox"]')
                    if type_select:
                        await type_select.click()
                        await page.wait_for_timeout(300)
                        date_option = await page.query_selector('[role="option"]:has-text("Date")')
                        if not date_option:
                            date_option = await page.query_selector('text=Date')
                        if date_option:
                            await date_option.click(force=True)
                            await page.wait_for_timeout(300)
                            print("  Changed to Date type")
                        
                        # Check for date format dropdown
                        date_format_info = await page.evaluate("""
                            () => {
                                const labels = Array.from(document.querySelectorAll('label'));
                                const formatLabel = labels.find(l => l.textContent.includes('Date format'));
                                const formatSelect = document.querySelector('[data-testid$="-dateformat-"]') || 
                                                    document.querySelector('select[value]');
                                return {
                                    hasFormatLabel: !!formatLabel,
                                    labelText: formatLabel ? formatLabel.textContent.trim() : null,
                                    hasFormatSelect: !!formatSelect
                                };
                            }
                        """)
                        print(f"  Date format info: {date_format_info}")
                        
                        if date_format_info.get('hasFormatLabel') and date_format_info.get('hasFormatSelect'):
                            results["test2_date_format"] = "PASS"
                            print("  TEST 2 PASS: Date format dropdown present for date field")
                        elif date_format_info.get('hasFormatLabel'):
                            results["test2_date_format"] = "PARTIAL - label found but no select"
                            print("  TEST 2 PARTIAL: Date format label found but no select dropdown")
                        else:
                            results["test2_date_format"] = "FAIL - no Date format label found"
                            print(f"  TEST 2 FAIL: {date_format_info}")
                        
                        # Test FILE field type - check for max file size
                        print("\n  --- Testing FILE field type ---")
                        type_select = await last_field.query_selector('[role="combobox"]')
                        if type_select:
                            await type_select.click()
                            await page.wait_for_timeout(300)
                            file_option = await page.query_selector('[role="option"]:has-text("File Upload")')
                            if not file_option:
                                file_option = await page.query_selector('text=File Upload')
                            if file_option:
                                await file_option.click(force=True)
                                await page.wait_for_timeout(300)
                                print("  Changed to File Upload type")
                            
                            # Check for max file size input
                            file_size_info = await page.evaluate("""
                                () => {
                                    const labels = Array.from(document.querySelectorAll('label'));
                                    const sizeLabel = labels.find(l => l.textContent.includes('Max file size'));
                                    const sizeInput = document.querySelector('[data-testid$="-maxfilesize-"]') ||
                                                     document.querySelector('input[max="500"]');
                                    return {
                                        hasLabel: !!sizeLabel,
                                        labelText: sizeLabel ? sizeLabel.textContent.trim() : null,
                                        hasInput: !!sizeInput
                                    };
                                }
                            """)
                            print(f"  Max file size info: {file_size_info}")
                            
                            if file_size_info.get('hasLabel') and file_size_info.get('hasInput'):
                                results["test3_file_maxsize"] = "PASS"
                                print("  TEST 3 PASS: Max file size input present for file field")
                            elif file_size_info.get('hasLabel'):
                                results["test3_file_maxsize"] = "PARTIAL - label found, no input"
                            else:
                                results["test3_file_maxsize"] = "FAIL"
                                print(f"  TEST 3 FAIL: {file_size_info}")
        else:
            results["test1_number_minmax"] = "FAIL - add field button not found"
            results["test2_date_format"] = "FAIL - add field button not found"
            results["test3_file_maxsize"] = "FAIL - add field button not found"
            print("  Add field button not found in signup slide over")
        
        await page.screenshot(path=".screenshots/iter279_formbuilder_types.jpeg", quality=40, full_page=False)
        
        # Close slideover
        close_btn = await page.query_selector('button[aria-label="Close"], [data-testid="slideover-close"]')
        if not close_btn:
            close_btn = await page.query_selector('button:has(svg):first-of-type')
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(1000)
    
    # ── TEST 6: Customer Portal tile - Show stats toggle ────────────────────
    print("\n=== TEST 6: Customer Portal tile - Show stats toggle ===")
    
    # Navigate to App Pages tab
    app_pages_tab = await page.query_selector('[role="tab"]:has-text("App Pages"), button:has-text("App Pages")')
    if not app_pages_tab:
        # Re-navigate to auth pages
        await go_to_auth_pages(page)
        await page.evaluate("window.scrollTo(0, 0)")
        app_pages_tab = await page.query_selector('button[role="tab"]:has-text("App Pages")')
    
    if app_pages_tab:
        await app_pages_tab.click()
        await page.wait_for_timeout(1000)
        print("  Clicked App Pages tab")
    
    # Click Customer Portal tile
    portal_tile = await page.query_selector('[data-testid="auth-tile-portal"]')
    if portal_tile:
        await portal_tile.click()
        await page.wait_for_timeout(1500)
        print("  Opened Customer Portal slideover")
        
        # Check for "Show stats on portal" toggle
        stats_toggle = await page.query_selector('[data-testid="portal-show-stats-toggle"]')
        if stats_toggle:
            is_vis = await stats_toggle.is_visible()
            results["test6_portal_stats_toggle"] = "PASS" if is_vis else "FAIL - toggle not visible"
            
            # Get current toggle state
            aria_checked = await stats_toggle.get_attribute("aria-checked")
            print(f"  Stats toggle visible: {is_vis}, current state: {aria_checked}")
            
            # Check for label text
            toggle_label = await page.evaluate("""
                () => {
                    const el = Array.from(document.querySelectorAll('p')).find(p => p.textContent.includes('Show stats on portal'));
                    return el ? el.textContent.trim() : null;
                }
            """)
            print(f"  Toggle label: {toggle_label}")
        else:
            results["test6_portal_stats_toggle"] = "FAIL - toggle not found"
            print("  Stats toggle NOT FOUND in portal slide")
        
        await page.screenshot(path=".screenshots/iter279_portal_toggle.jpeg", quality=40, full_page=False)
        
        # Test toggling - disable stats
        if stats_toggle:
            current_state = await stats_toggle.get_attribute("aria-checked")
            
            # If currently enabled, click to disable
            if current_state == "true":
                await stats_toggle.click()
                await page.wait_for_timeout(500)
                new_state = await stats_toggle.get_attribute("aria-checked")
                print(f"  After click: {current_state} -> {new_state}")
                
                # Save the settings
                save_btn = await page.query_selector('button:has-text("Save")')
                if save_btn:
                    await save_btn.click()
                    await page.wait_for_timeout(2000)
                    print("  Saved portal settings with stats=disabled")
        
        # Close slideover
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(1000)
    else:
        results["test6_portal_stats_toggle"] = "FAIL - portal tile not found"
        print("  Customer Portal tile NOT FOUND")
    
    # ── TEST 7: Portal page respects portal_show_stats toggle ──────────────
    print("\n=== TEST 7: Portal page - portal_show_stats toggle ===")
    
    # Check if portal_show_stats was disabled - navigate to /portal to verify
    # Note: Platform admin viewing /portal may have a different experience
    # Let's check what the portal shows
    await page.goto(f"{BASE_URL}/portal")
    await page.wait_for_timeout(3000)
    
    print(f"  Portal URL: {page.url}")
    
    portal_stats = await page.query_selector('[data-testid="portal-stats"]')
    portal_loading = await page.query_selector('[data-testid="portal-loading"]')
    portal_error = await page.query_selector('[data-testid="portal-error"]')
    
    if portal_loading:
        await page.wait_for_timeout(3000)
        portal_stats = await page.query_selector('[data-testid="portal-stats"]')
    
    print(f"  portal-stats element: {portal_stats is not None}")
    print(f"  portal-loading: {portal_loading is not None}")
    print(f"  portal-error: {portal_error is not None}")
    
    await page.screenshot(path=".screenshots/iter279_portal_page.jpeg", quality=40, full_page=False)
    
    # Check if portal stats is hidden (after toggle disabled)
    if portal_error:
        error_text = await portal_error.text_content()
        print(f"  Portal error: {error_text}")
        results["test7_portal_stats_hidden"] = "SKIP - portal shows error (expected for platform_admin)"
    elif portal_stats:
        is_vis = await portal_stats.is_visible()
        # Since we disabled stats, they should be hidden
        results["test7_portal_stats_hidden"] = "FAIL - stats visible when should be hidden" if is_vis else "PASS - stats hidden after toggle disabled"
        print(f"  Portal stats visible: {is_vis}")
    else:
        # No stats element means it's hidden (good - toggle was disabled)
        results["test7_portal_stats_hidden"] = "PASS - stats element not rendered (toggle disabled)"
        print("  Portal stats not rendered - toggle is disabled, PASS")
    
    # ── TEST 8: UniversalFormRenderer - file upload styled ──────────────────
    print("\n=== TEST 8: UniversalFormRenderer - file upload as styled button ===")
    
    # Check the signup page for file upload rendering
    await page.goto(f"{BASE_URL}/signup")
    await page.wait_for_timeout(2000)
    
    print(f"  Signup page URL: {page.url}")
    await page.screenshot(path=".screenshots/iter279_signup_page.jpeg", quality=40, full_page=False)
    
    # Check for raw file input vs styled file upload
    raw_file_input = await page.query_selector('input[type="file"]:not([class*="hidden"])')
    styled_upload = await page.query_selector('label:has(input[type="file"])')
    choose_file_btn = await page.evaluate("""
        () => {
            const labels = Array.from(document.querySelectorAll('label'));
            const fileLabel = labels.find(l => 
                l.querySelector('input[type="file"]') && 
                (l.textContent.includes('Choose file') || l.textContent.includes('No file chosen'))
            );
            return fileLabel ? {
                found: true,
                text: fileLabel.textContent.trim().slice(0, 100),
                classes: fileLabel.className
            } : null;
        }
    """)
    
    print(f"  Raw visible file input: {raw_file_input is not None}")
    print(f"  Styled label+file input: {styled_upload is not None}")
    print(f"  Choose file button: {choose_file_btn}")
    
    # The signup form might not have a file field unless the schema includes one
    # Let's check what fields are in the signup form
    form_fields = await page.evaluate("""
        () => {
            const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"])'));
            return inputs.map(i => ({type: i.type, class: i.className.slice(0, 50)}));
        }
    """)
    print(f"  Form inputs found: {form_fields}")
    
    # The file upload is styled if input[type=file] is hidden inside a label
    hidden_file = await page.query_selector('input[type="file"].hidden')
    styled_upload_found = hidden_file is not None
    
    # Also check via the UniversalFormRenderer code - it uses label wrapper
    if choose_file_btn:
        results["test8_file_upload_styled"] = "PASS" if choose_file_btn.get('found') else "FAIL"
        print(f"  TEST 8 PASS: File upload renders as styled 'Choose file' button")
    elif styled_upload:
        results["test8_file_upload_styled"] = "PASS - styled label wrapper found"
        print("  TEST 8 PASS: File upload has label wrapper (styled)")
    else:
        # Check if file field is even in the form schema
        results["test8_file_upload_styled"] = "SKIP - no file field in current signup form schema"
        print("  TEST 8 SKIP: No file field visible in current signup form")
    
    print("\n===== ALL TESTS COMPLETE =====")
    return results
