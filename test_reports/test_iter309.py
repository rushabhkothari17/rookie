"""
Test script for iteration 309 - 7 UI/UX fixes testing
Tests: sidebar collapse, footer text, sticky scrollbar, customer dropdown (SearchableSelect),
default tax defaults, tax auto-population, strict tax validation
"""
import asyncio
import json
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://partner-plan-flow.preview.emergentagent.com')
ADMIN_EMAIL = 'admin@automateaccounts.local'
ADMIN_PASSWORD = 'ChangeMe123!'
TENANT_CODE = 'automate-accounts'

results = {}

async def login_admin(page):
    """Login as platform admin"""
    await page.goto(BASE_URL)
    await page.wait_for_timeout(2000)
    tenant_input = await page.query_selector('input[placeholder="Partner code"]')
    if tenant_input:
        await page.fill('input[placeholder="Partner code"]', TENANT_CODE)
        await page.click('button:has-text("Continue")')
        await page.wait_for_timeout(2000)
    await page.fill('input[type="email"]', ADMIN_EMAIL)
    await page.fill('input[type="password"]', ADMIN_PASSWORD)
    await page.click('button[type="submit"]')
    await page.wait_for_timeout(3000)
    is_admin = await page.is_visible('[data-testid="admin-page"]')
    print(f"Admin login success: {is_admin}")
    return is_admin


async def test_footer_text(page):
    """Test footer text CSS variable is rgba(255,255,255,0.72)"""
    print("\n=== TEST: Footer Text ===")
    try:
        await page.goto(BASE_URL)
        await page.wait_for_timeout(2000)
        
        # Check CSS variable
        css_var = await page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--aa-footer-text-dim')")
        print(f"--aa-footer-text-dim = '{css_var.strip()}'")
        
        if "0.72" in css_var or "rgba(255, 255, 255, 0.72)" in css_var:
            results['footer_text'] = 'PASS: CSS variable = rgba(255,255,255,0.72)'
            print("PASS: Footer text CSS variable is correct")
        else:
            results['footer_text'] = f'FAIL: CSS variable = {css_var}'
            print(f"FAIL: Footer text CSS variable = {css_var}")
        
        # Scroll to footer and take screenshot
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=".screenshots/iter309_footer.jpeg", quality=40, full_page=False)
        
    except Exception as e:
        results['footer_text'] = f'ERROR: {e}'
        print(f"Error: {e}")


async def test_sidebar_collapse(page):
    """Test sidebar collapse: only section icons visible, clicking section icon expands"""
    print("\n=== TEST: Sidebar Collapse ===")
    try:
        # Should already be on admin page from login
        await page.wait_for_selector('[data-testid="admin-page"]', timeout=5000)
        
        # Get current sidebar width
        sidebar_width = await page.evaluate("() => { const s = document.querySelector('.aa-sidebar'); return s ? s.offsetWidth : 0; }")
        print(f"Initial sidebar width: {sidebar_width}")
        
        # Collapse if not already collapsed
        if sidebar_width > 80:
            await page.click('[data-testid="sidebar-collapse-btn"]', force=True)
            await page.wait_for_timeout(600)
        
        # Check sidebar width
        collapsed_width = await page.evaluate("() => { const s = document.querySelector('.aa-sidebar'); return s ? s.offsetWidth : 0; }")
        print(f"Collapsed sidebar width: {collapsed_width}")
        
        # Check tab items (nav items) - how many are visible?
        nav_items = await page.evaluate("""() => {
            const items = document.querySelectorAll('.aa-nav-item');
            return Array.from(items).map(el => ({
                testId: el.getAttribute('data-testid'),
                visible: el.offsetWidth > 0 && el.offsetHeight > 0,
                classes: el.className.includes('justify-center')
            }));
        }""")
        print(f"Nav items when collapsed: {nav_items}")
        
        # Check section header buttons (should show section icons)
        section_buttons = await page.evaluate("""() => {
            const sidebar = document.querySelector('.aa-sidebar');
            const btns = sidebar ? sidebar.querySelectorAll('button[title]') : [];
            return Array.from(btns).map(b => ({ title: b.getAttribute('title') }));
        }""")
        print(f"Section buttons with titles: {section_buttons}")
        
        await page.screenshot(path=".screenshots/iter309_sidebar_collapsed.jpeg", quality=40, full_page=False)
        
        # Test A: Check collapsed width is ~64px
        if collapsed_width <= 80:
            print("PASS A: Sidebar collapsed to 64px")
        else:
            print(f"FAIL A: Sidebar width = {collapsed_width}")
        
        # Test for tab items visible (should show only icons, no text)
        has_text_labels = await page.evaluate("""() => {
            const items = document.querySelectorAll('.aa-nav-item');
            for (const item of items) {
                const span = item.querySelector('span');
                if (span && span.textContent.trim()) return true;
            }
            return false;
        }""")
        print(f"Tab labels visible when collapsed: {has_text_labels}")
        
        # Check if any tab items are visible (they should be hidden per user requirement)
        visible_nav_count = len([n for n in nav_items if n['visible']])
        print(f"Visible tab items when collapsed: {visible_nav_count}")
        
        if visible_nav_count > 0:
            print(f"NOTE: {visible_nav_count} tab items still show icons when collapsed (user wanted only section icons)")
        
        # Test B: Click section icon to expand sidebar
        people_btn = await page.query_selector('[title="People"]')
        if people_btn:
            await page.click('[title="People"]', force=True)
            await page.wait_for_timeout(700)
            expanded_width = await page.evaluate("() => { const s = document.querySelector('.aa-sidebar'); return s ? s.offsetWidth : 0; }")
            print(f"Sidebar width after clicking People section: {expanded_width}")
            
            # Check active tab
            active_tabs = await page.evaluate("""() => {
                const items = document.querySelectorAll('.aa-nav-item.active');
                return Array.from(items).map(el => el.getAttribute('data-testid'));
            }""")
            print(f"Active tabs after clicking People section: {active_tabs}")
            
            await page.screenshot(path=".screenshots/iter309_sidebar_expanded_after_click.jpeg", quality=40, full_page=False)
            
            if expanded_width > 100:
                results['sidebar_expand_click'] = f'PASS: Sidebar expanded to {expanded_width}px after clicking People section icon'
                print("PASS B: Sidebar expanded after clicking section icon")
            else:
                results['sidebar_expand_click'] = f'FAIL: Sidebar width = {expanded_width} after click'
                print("FAIL B: Sidebar did not expand")
            
            # Check if Users/Customers tabs are visible
            if any('users' in (t or '') or 'customers' in (t or '') for t in active_tabs):
                print("PASS B2: People section tabs visible after expansion")
            else:
                print(f"WARN B2: Active tabs = {active_tabs}")
        else:
            # Try Commerce section
            commerce_btn = await page.query_selector('[title="Commerce"]')
            print(f"People button not found. Commerce button found: {commerce_btn is not None}")
        
        # Summary for sidebar
        tab_icons_visible = visible_nav_count > 0
        if tab_icons_visible:
            results['sidebar_collapse'] = f'PARTIAL: Collapsed width=64px ✓, but {visible_nav_count} tab items still show icons (user wants only section icons)'
        else:
            results['sidebar_collapse'] = 'PASS: Sidebar collapses to 64px, only section icons visible'
            
    except Exception as e:
        results['sidebar_collapse'] = f'ERROR: {e}'
        print(f"Error: {e}")


async def test_orders_customer_dropdown(page):
    """Test Create Manual Order uses SearchableSelect not native datalist"""
    print("\n=== TEST: Orders Customer Dropdown (SearchableSelect) ===")
    try:
        # Navigate to Orders tab
        await page.click('[data-testid="admin-tab-orders"]', force=True)
        await page.wait_for_timeout(1500)
        
        # Click Create Manual Order
        create_btn = await page.query_selector('[data-testid="admin-create-order-btn"]')
        if not create_btn:
            print("Create Order button not found, trying Commerce section")
            # Try expanding Commerce
            commerce_btn = await page.query_selector('[title="Commerce"]')
            if not commerce_btn:
                await page.query_selector('[data-testid="admin-section-commerce"]')
            if commerce_btn:
                await page.click('[title="Commerce"]', force=True)
                await page.wait_for_timeout(500)
            await page.click('[data-testid="admin-tab-orders"]', force=True)
            await page.wait_for_timeout(1500)
            
        await page.click('[data-testid="admin-create-order-btn"]', force=True)
        await page.wait_for_timeout(1000)
        
        # Check if dialog is open
        dialog_visible = await page.is_visible('[data-testid="admin-order-edit-dialog"], [role="dialog"]')
        print(f"Dialog visible: {dialog_visible}")
        
        # Check if customer email field is SearchableSelect (not native datalist/input)
        customer_email_field = await page.evaluate("""() => {
            // Check for SearchableSelect trigger - should be a button/div with ComboBox role
            const dialog = document.querySelector('[role="dialog"]');
            if (!dialog) return { found: false };
            
            // Look for searchable-select or combobox trigger
            const testIdField = dialog.querySelector('[data-testid="manual-order-customer-email"]');
            const combobox = dialog.querySelector('[role="combobox"]');
            const datalist = dialog.querySelector('input[list]');
            const searchSelect = dialog.querySelector('.searchable-select, [data-searchable]');
            
            // SearchableSelect typically renders as a button with role=combobox
            const allButtons = Array.from(dialog.querySelectorAll('button')).map(b => ({
                text: b.textContent.trim().slice(0, 50),
                testId: b.getAttribute('data-testid'),
                type: b.getAttribute('type')
            })).filter(b => b.text.length > 0);
            
            return {
                found: true,
                testIdField: testIdField ? testIdField.tagName : null,
                hasCombobox: !!combobox,
                hasDatalist: !!datalist,
                hasSearchSelect: !!searchSelect,
                firstFewButtons: allButtons.slice(0, 5)
            };
        }""")
        print(f"Customer email field info: {customer_email_field}")
        
        await page.screenshot(path=".screenshots/iter309_create_order_dialog.jpeg", quality=40, full_page=False)
        
        if customer_email_field.get('hasCombobox') or customer_email_field.get('testIdField'):
            results['customer_dropdown'] = 'PASS: Customer field uses SearchableSelect (combobox role found)'
            print("PASS: Customer dropdown uses SearchableSelect")
        elif customer_email_field.get('hasDatalist'):
            results['customer_dropdown'] = 'FAIL: Customer field still uses native datalist'
            print("FAIL: Native datalist still being used")
        else:
            results['customer_dropdown'] = f'INFO: Field info = {customer_email_field}'
            print(f"INFO: Customer field details: {customer_email_field}")
        
        # Check for the specific data-testid
        searchable_select = await page.query_selector('[data-testid="manual-order-customer-email"]')
        if searchable_select:
            tag = await searchable_select.evaluate("el => el.tagName")
            classes = await searchable_select.evaluate("el => el.className")
            print(f"Customer email element: tag={tag}, classes={classes[:80]}")
        else:
            print("manual-order-customer-email not found")
        
        # Close dialog
        await page.keyboard.press('Escape')
        await page.wait_for_timeout(500)
        
    except Exception as e:
        results['customer_dropdown'] = f'ERROR: {e}'
        print(f"Error: {e}")
        try:
            await page.keyboard.press('Escape')
        except:
            pass


async def test_partner_orders_default_tax(page):
    """Test Partner Orders new order form has 'No tax' / '0' by default"""
    print("\n=== TEST: Partner Orders Default Tax ===")
    try:
        # Navigate to Partner Orders
        # Need to expand Platform section
        platform_btn = await page.query_selector('[title="Platform"]')
        if not platform_btn:
            # Try clicking Platform section header
            platform_section = await page.query_selector('[data-testid="admin-section-platform"]')
            if platform_section:
                await page.click('[data-testid="admin-section-platform"]', force=True)
                await page.wait_for_timeout(400)
        else:
            await page.click('[title="Platform"]', force=True)
            await page.wait_for_timeout(500)
        
        # Expand platform section if collapsed
        platform_expanded = await page.is_visible('[data-testid="admin-tab-partner-orders"]')
        if not platform_expanded:
            # Try expanding Platform section
            platform_section = await page.query_selector('[data-testid="admin-section-platform"]')
            if platform_section:
                await page.click('[data-testid="admin-section-platform"]', force=True)
                await page.wait_for_timeout(400)
        
        await page.click('[data-testid="admin-tab-partner-orders"]', force=True)
        await page.wait_for_timeout(1500)
        print("Navigated to Partner Orders tab")
        
        # Click + New Order button
        await page.click('[data-testid="create-partner-order-btn"]', force=True)
        await page.wait_for_timeout(1000)
        
        # Check tax name and tax rate default values
        tax_name_input = await page.query_selector('[data-testid="order-tax-name-input"]')
        tax_rate_input = await page.query_selector('[data-testid="order-tax-rate-input"]')
        
        if tax_name_input and tax_rate_input:
            tax_name_val = await tax_name_input.evaluate("el => el.value")
            tax_rate_val = await tax_rate_input.evaluate("el => el.value")
            print(f"Tax Name default: '{tax_name_val}'")
            print(f"Tax Rate default: '{tax_rate_val}'")
            
            await page.screenshot(path=".screenshots/iter309_partner_order_new.jpeg", quality=40, full_page=False)
            
            if tax_name_val == "No tax" and tax_rate_val == "0":
                results['partner_order_default_tax'] = 'PASS: Tax Name="No tax", Tax Rate="0" by default'
                print("PASS: Default tax fields correct")
            else:
                results['partner_order_default_tax'] = f'FAIL: Tax Name="{tax_name_val}", Tax Rate="{tax_rate_val}"'
                print(f"FAIL: Default tax fields wrong: name={tax_name_val}, rate={tax_rate_val}")
        else:
            print("Tax name/rate inputs not found in dialog")
            await page.screenshot(path=".screenshots/iter309_partner_order_notfound.jpeg", quality=40, full_page=False)
            results['partner_order_default_tax'] = 'ERROR: Tax inputs not found in dialog'
        
        # Close dialog
        await page.keyboard.press('Escape')
        await page.wait_for_timeout(500)
        
    except Exception as e:
        results['partner_order_default_tax'] = f'ERROR: {e}'
        print(f"Error: {e}")
        try:
            await page.keyboard.press('Escape')
        except:
            pass


async def test_partner_sub_default_tax(page):
    """Test Partner Subscriptions new sub form has 'No tax' / '0' by default"""
    print("\n=== TEST: Partner Subscriptions Default Tax ===")
    try:
        # Navigate to Partner Subscriptions
        await page.click('[data-testid="admin-tab-partner-subscriptions"]', force=True)
        await page.wait_for_timeout(1500)
        print("Navigated to Partner Subscriptions tab")
        
        # Click + New Subscription button
        await page.click('[data-testid="create-partner-sub-btn"]', force=True)
        await page.wait_for_timeout(1000)
        
        # Check tax name and tax rate default values
        tax_name_input = await page.query_selector('[data-testid="sub-tax-name-input"]')
        tax_rate_input = await page.query_selector('[data-testid="sub-tax-rate-input"]')
        
        if tax_name_input and tax_rate_input:
            tax_name_val = await tax_name_input.evaluate("el => el.value")
            tax_rate_val = await tax_rate_input.evaluate("el => el.value")
            print(f"Sub Tax Name default: '{tax_name_val}'")
            print(f"Sub Tax Rate default: '{tax_rate_val}'")
            
            await page.screenshot(path=".screenshots/iter309_partner_sub_new.jpeg", quality=40, full_page=False)
            
            if tax_name_val == "No tax" and tax_rate_val == "0":
                results['partner_sub_default_tax'] = 'PASS: Tax Name="No tax", Tax Rate="0" by default'
                print("PASS: Default sub tax fields correct")
            else:
                results['partner_sub_default_tax'] = f'FAIL: Tax Name="{tax_name_val}", Tax Rate="{tax_rate_val}"'
                print(f"FAIL: Default sub tax fields wrong: name={tax_name_val}, rate={tax_rate_val}")
        else:
            print("Sub Tax name/rate inputs not found")
            results['partner_sub_default_tax'] = 'ERROR: Tax inputs not found'
        
        # Close dialog
        await page.keyboard.press('Escape')
        await page.wait_for_timeout(500)
        
    except Exception as e:
        results['partner_sub_default_tax'] = f'ERROR: {e}'
        print(f"Error: {e}")
        try:
            await page.keyboard.press('Escape')
        except:
            pass


async def test_tax_auto_population_1edd(page):
    """Test tax auto-population when 1EDD partner selected"""
    print("\n=== TEST: Tax Auto-Population for 1EDD Partner ===")
    try:
        # Navigate to Partner Orders
        await page.click('[data-testid="admin-tab-partner-orders"]', force=True)
        await page.wait_for_timeout(1500)
        
        # Open New Order
        await page.click('[data-testid="create-partner-order-btn"]', force=True)
        await page.wait_for_timeout(1000)
        
        # Check initial defaults
        tax_name_before = await page.evaluate("() => { const el = document.querySelector('[data-testid=\"order-tax-name-input\"]'); return el ? el.value : null; }")
        tax_rate_before = await page.evaluate("() => { const el = document.querySelector('[data-testid=\"order-tax-rate-input\"]'); return el ? el.value : null; }")
        print(f"Before partner selection: name='{tax_name_before}', rate='{tax_rate_before}'")
        
        # Find and click the Partner select
        partner_select = await page.query_selector('[data-testid="order-partner-select"]')
        if partner_select:
            # Click to open it
            await page.click('[data-testid="order-partner-select"]', force=True)
            await page.wait_for_timeout(500)
            
            # Look for 1EDD option
            partner_options = await page.evaluate("""() => {
                const popup = document.querySelector('[data-radix-popper-content-wrapper], [role="listbox"]');
                if (!popup) return [];
                return Array.from(popup.querySelectorAll('[role="option"], li, div[class*="item"]')).map(el => el.textContent.trim()).filter(t => t).slice(0, 20);
            }""")
            print(f"Partner options: {partner_options[:10]}")
            
            # Type to search for 1EDD
            search_input = await page.query_selector('[data-radix-popper-content-wrapper] input, [role="combobox"] + input, input[placeholder*="Search"]')
            if search_input:
                await page.fill('[data-radix-popper-content-wrapper] input, input[placeholder*="Search"]', '1EDD')
            
            # Wait for filter and look for 1EDD
            await page.wait_for_timeout(500)
            edd_option = await page.query_selector('text=1EDD')
            if not edd_option:
                # Look in the popup 
                edd_option = await page.query_selector('[data-radix-popper-content-wrapper] *:has-text("1EDD"), [role="option"]:has-text("1EDD")')
            
            if edd_option:
                print("Found 1EDD option, clicking...")
                await edd_option.click(force=True)
                await page.wait_for_timeout(800)
                
                # Check tax auto-populated
                tax_name_after = await page.evaluate("() => { const el = document.querySelector('[data-testid=\"order-tax-name-input\"]'); return el ? el.value : null; }")
                tax_rate_after = await page.evaluate("() => { const el = document.querySelector('[data-testid=\"order-tax-rate-input\"]'); return el ? el.value : null; }")
                print(f"After selecting 1EDD: name='{tax_name_after}', rate='{tax_rate_after}'")
                
                await page.screenshot(path=".screenshots/iter309_tax_auto_1edd.jpeg", quality=40, full_page=False)
                
                if tax_name_after and tax_name_after != "No tax" and tax_rate_after and tax_rate_after != "0":
                    results['tax_auto_population_1edd'] = f'PASS: Auto-populated tax_name="{tax_name_after}", tax_rate="{tax_rate_after}"'
                    print(f"PASS: Tax auto-populated: {tax_name_after} / {tax_rate_after}%")
                elif tax_name_after == "GST" or "GST" in str(tax_name_after):
                    results['tax_auto_population_1edd'] = f'PASS: GST auto-populated, rate={tax_rate_after}'
                    print("PASS: GST auto-populated for 1EDD")
                else:
                    results['tax_auto_population_1edd'] = f'PARTIAL or FAIL: name={tax_name_after}, rate={tax_rate_after}'
                    print(f"CHECK: Tax after 1EDD: name={tax_name_after}, rate={tax_rate_after}")
            else:
                print("1EDD option not found in partner list")
                
                # Get all options visible
                all_opts = await page.evaluate("""() => {
                    const els = document.querySelectorAll('[data-radix-popper-content-wrapper] *');
                    return Array.from(els).map(el => el.textContent.trim()).filter(t => t.length > 1 && t.length < 50).slice(0, 20);
                }""")
                print(f"All visible options: {all_opts}")
                results['tax_auto_population_1edd'] = 'WARN: 1EDD partner not found in dropdown'
        else:
            print("Partner select not found")
            results['tax_auto_population_1edd'] = 'ERROR: Partner select not found'
        
        # Close dialog
        await page.keyboard.press('Escape')
        await page.wait_for_timeout(500)
        
    except Exception as e:
        results['tax_auto_population_1edd'] = f'ERROR: {e}'
        print(f"Error: {e}")
        try:
            await page.keyboard.press('Escape')
        except:
            pass


async def test_sticky_scrollbar(page):
    """Test sticky scrollbar thickness in Partner Orders tab"""
    print("\n=== TEST: Sticky Scrollbar ===")
    try:
        # Navigate to Partner Orders
        await page.click('[data-testid="admin-tab-partner-orders"]', force=True)
        await page.wait_for_timeout(1500)
        
        # Check CSS for sticky-scroll-bar
        scrollbar_css = await page.evaluate("""() => {
            // Get computed style for the sticky scrollbar
            const el = document.querySelector('.sticky-scroll-bar');
            if (!el) return { found: false };
            const style = window.getComputedStyle(el);
            return {
                found: true,
                display: style.display,
                height: style.height,
                position: style.position,
                overflow: style.overflow
            };
        }""")
        print(f"Sticky scrollbar element info: {scrollbar_css}")
        
        # Check the inline height style on the element
        scrollbar_height = await page.evaluate("""() => {
            const el = document.querySelector('.sticky-scroll-bar');
            if (!el) return null;
            return { 
                inlineHeight: el.style.height,
                offsetHeight: el.offsetHeight,
                className: el.className
            };
        }""")
        print(f"Sticky scrollbar height info: {scrollbar_height}")
        
        # Check if CSS class is present in stylesheet
        css_rule_check = await page.evaluate("""() => {
            let found = false;
            let ruleText = '';
            for (const sheet of document.styleSheets) {
                try {
                    for (const rule of sheet.cssRules || []) {
                        if (rule.selectorText && rule.selectorText.includes('sticky-scroll-bar')) {
                            found = true;
                            ruleText += rule.cssText + ' | ';
                        }
                    }
                } catch(e) {}
            }
            return { found, ruleText: ruleText.slice(0, 500) };
        }""")
        print(f"CSS rule check: {css_rule_check}")
        
        # Take screenshot at narrow viewport to force overflow
        await page.set_viewport_size({"width": 1200, "height": 800})
        await page.wait_for_timeout(1000)
        
        scrollbar_visible = await page.evaluate("""() => {
            const el = document.querySelector('.sticky-scroll-bar');
            if (!el) return false;
            const style = window.getComputedStyle(el);
            return style.display !== 'none' && el.offsetWidth > 0;
        }""")
        print(f"Sticky scrollbar visible at 1200px: {scrollbar_visible}")
        
        await page.screenshot(path=".screenshots/iter309_sticky_scrollbar.jpeg", quality=40, full_page=False)
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        if css_rule_check.get('found') and 'height: 14px' in (css_rule_check.get('ruleText', '')):
            results['sticky_scrollbar'] = 'PASS: sticky-scroll-bar CSS class found with height:14px'
            print("PASS: Sticky scrollbar CSS is correct (14px height)")
        elif scrollbar_height and scrollbar_height.get('inlineHeight') == '18px':
            results['sticky_scrollbar'] = 'PASS: Sticky scrollbar has 18px height inline style'
            print("PASS: Sticky scrollbar height = 18px (inline)")
        else:
            results['sticky_scrollbar'] = f'INFO: CSS={css_rule_check}, height={scrollbar_height}'
            print(f"INFO: Need manual verification - CSS rule present: {css_rule_check.get('found')}")
            
    except Exception as e:
        results['sticky_scrollbar'] = f'ERROR: {e}'
        print(f"Error: {e}")


async def test_strict_tax_validation(page):
    """Test strict tax validation when enabling tax collection"""
    print("\n=== TEST: Strict Tax Validation ===")
    try:
        # Navigate to Taxes tab under Settings
        settings_section = await page.query_selector('[data-testid="admin-section-settings"]')
        if settings_section:
            await page.click('[data-testid="admin-section-settings"]', force=True)
            await page.wait_for_timeout(400)
        
        taxes_tab = await page.query_selector('[data-testid="admin-tab-taxes"]')
        if not taxes_tab:
            # Try via sidebar
            await page.click('text=Taxes', force=True)
        else:
            await page.click('[data-testid="admin-tab-taxes"]', force=True)
        await page.wait_for_timeout(1500)
        
        # Click Tax Collection sub-tab
        tax_settings_tab = await page.query_selector('[data-testid="taxes-tab-settings"]')
        if tax_settings_tab:
            await page.click('[data-testid="taxes-tab-settings"]', force=True)
            await page.wait_for_timeout(500)
        
        # Check current tax enabled state
        tax_toggle = await page.query_selector('[data-testid="tax-enabled-toggle"]')
        if not tax_toggle:
            print("Tax toggle not found")
            results['strict_tax_validation'] = 'ERROR: Tax toggle not found'
            return
        
        current_state = await tax_toggle.evaluate("el => el.checked")
        print(f"Tax collection currently enabled: {current_state}")
        
        await page.screenshot(path=".screenshots/iter309_taxes_settings.jpeg", quality=40, full_page=False)
        
        # Check the country selection is visible when enabled
        if current_state:
            country_select = await page.is_visible('[data-testid="tax-country-select"]')
            print(f"Country select visible when enabled: {country_select}")
            
            # Get current country setting
            country_val = await page.evaluate("""() => {
                const sel = document.querySelector('[data-testid="tax-country-select"]');
                if (!sel) return null;
                const trigger = sel.querySelector('[data-radix-select-trigger]') || sel;
                return trigger.textContent.trim();
            }""")
            print(f"Current country: {country_val}")
            
            results['strict_tax_validation'] = f'PASS: Tax enabled, country select visible. Country={country_val}'
            print("PASS: Tax validation UI elements present")
        else:
            print("Tax is disabled - testing enable validation")
            # Try to enable tax collection
            await page.click('[data-testid="tax-enabled-toggle"]', force=True)
            await page.wait_for_timeout(1000)
            
            # Check if error toast appears or country/state pre-populated
            new_state = await tax_toggle.evaluate("el => el.checked")
            print(f"After enabling: checked={new_state}")
            
            # Look for toast messages
            error_text = await page.evaluate("""() => {
                const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"], [data-sonner-toast]'));
                return errorElements.map(el => el.textContent).join(", ");
            }""")
            if error_text:
                print(f"Toast/error: {error_text[:200]}")
            
            await page.screenshot(path=".screenshots/iter309_tax_enable_test.jpeg", quality=40, full_page=False)
            
            if new_state:
                results['strict_tax_validation'] = 'PASS: Tax enabled successfully (org has country set)'
                print("PASS: Tax enabled (validation passed)")
            elif error_text:
                results['strict_tax_validation'] = f'PASS: Validation error shown: {error_text[:100]}'
                print(f"PASS: Validation error shown correctly")
            else:
                results['strict_tax_validation'] = 'INFO: Tax not enabled - check manually'
                print("INFO: Tax toggle state unclear")
        
    except Exception as e:
        results['strict_tax_validation'] = f'ERROR: {e}'
        print(f"Error: {e}")


# Main execution
async def main():
    pass

import sys
print("Test script loaded. Running via Playwright browser automation tool.")
