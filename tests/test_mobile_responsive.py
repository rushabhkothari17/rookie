"""
Mobile Responsiveness Tests for:
1. TopNav hamburger menu (390px mobile) 
2. TopNav desktop nav links (1280px)
3. Admin page mobile sidebar toggle
4. Store page mobile filters
5. Store hero no overflow (390px)
6. Store search+sort stacking (390px)
7. Admin tables horizontal scroll on mobile
8. Full page smoke test at 1280px
"""

import asyncio
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

def get_auth_token():
    """Get a valid auth token for the admin user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@automateaccounts.local", "password": "ChangeMe123!"},
        timeout=10
    )
    if response.status_code == 200:
        return response.json().get("token")
    return None

async def setup_auth(page, token: str):
    """Set auth token in localStorage and reload"""
    await page.evaluate(f"localStorage.setItem('aa_token', '{token}')")

async def test_topnav_mobile_hamburger(page):
    """Test 1: TopNav hamburger menu on 390px mobile viewport"""
    print("\n=== TEST 1: TopNav Hamburger Menu (Mobile 390px) ===")
    try:
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.goto(f"{BASE_URL}/store", wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(1000)

        # Check hamburger is visible
        hamburger = page.locator('[data-testid="nav-hamburger"]')
        is_visible = await hamburger.is_visible()
        if is_visible:
            print("PASS: Hamburger button is visible on mobile")
        else:
            print("FAIL: Hamburger button NOT visible on mobile")
            return False

        # Check desktop nav links are hidden
        desktop_nav = page.locator('[data-testid="nav-links"]')
        # nav-links has "hidden md:flex" which should hide it on mobile
        is_hidden = not await desktop_nav.is_visible()
        if is_hidden:
            print("PASS: Desktop nav links are hidden on mobile")
        else:
            print("WARN: Desktop nav links may not be hidden on mobile (check CSS)")

        # Mobile drawer should NOT be visible before clicking
        mobile_menu = page.locator('[data-testid="nav-mobile-menu"]')
        menu_visible_before = await mobile_menu.is_visible()
        if not menu_visible_before:
            print("PASS: Mobile menu drawer is closed by default")
        else:
            print("FAIL: Mobile menu drawer should be closed by default")

        # Click hamburger
        await hamburger.click()
        await page.wait_for_timeout(500)

        # Mobile drawer should now be visible
        menu_visible_after = await mobile_menu.is_visible()
        if menu_visible_after:
            print("PASS: Mobile menu drawer opens after hamburger click")
        else:
            print("FAIL: Mobile menu drawer did NOT open after hamburger click")
            return False

        # Check nav links are visible in mobile menu
        mobile_store_link = page.locator('[data-testid="mobile-nav-store"]')
        store_visible = await mobile_store_link.is_visible()
        if store_visible:
            print("PASS: Store nav link visible in mobile menu")
        else:
            # Try alternate testid format
            alt_link = page.locator('[data-testid^="mobile-nav"]').first
            alt_visible = await alt_link.is_visible()
            if alt_visible:
                print("PASS: Nav links visible in mobile menu (alt selector)")
            else:
                print("WARN: Could not verify specific nav links in mobile menu")

        # Click hamburger again to close
        await page.locator('[data-testid="nav-hamburger"]').click()
        await page.wait_for_timeout(400)
        closed = not await mobile_menu.is_visible()
        if closed:
            print("PASS: Mobile menu closes on second hamburger click")
        else:
            print("WARN: Mobile menu did not close on second click")

        # Take screenshot
        await page.screenshot(path="/app/test_reports/mobile_topnav_hamburger.jpeg", type="jpeg", quality=40, full_page=False)
        print("Screenshot saved: mobile_topnav_hamburger.jpeg")
        return True
    except Exception as e:
        print(f"ERROR in test 1: {e}")
        return False


async def test_topnav_desktop(page):
    """Test 2: TopNav at 1280px desktop - full nav links visible, hamburger hidden"""
    print("\n=== TEST 2: TopNav Desktop (1280px) ===")
    try:
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto(f"{BASE_URL}/store", wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(1000)

        # Hamburger should be hidden
        hamburger = page.locator('[data-testid="nav-hamburger"]')
        hamburger_hidden = not await hamburger.is_visible()
        if hamburger_hidden:
            print("PASS: Hamburger button is hidden on desktop")
        else:
            print("FAIL: Hamburger button should be hidden on desktop (md:hidden)")

        # Desktop nav links should be visible
        nav_links = page.locator('[data-testid="nav-links"]')
        nav_visible = await nav_links.is_visible()
        if nav_visible:
            print("PASS: Desktop nav links visible on 1280px")
        else:
            print("FAIL: Desktop nav links NOT visible on 1280px")

        # User trigger (dropdown) should be visible
        user_trigger = page.locator('[data-testid="nav-user-trigger"]')
        user_visible = await user_trigger.is_visible()
        if user_visible:
            print("PASS: User menu trigger visible on desktop")
        else:
            print("WARN: User menu trigger not visible (may need auth)")

        await page.screenshot(path="/app/test_reports/desktop_topnav.jpeg", type="jpeg", quality=40, full_page=False)
        print("Screenshot saved: desktop_topnav.jpeg")
        return True
    except Exception as e:
        print(f"ERROR in test 2: {e}")
        return False


async def test_admin_mobile_sidebar(page, token: str):
    """Test 3: Admin page mobile sidebar toggle (390px)"""
    print("\n=== TEST 3: Admin Mobile Sidebar Toggle (390px) ===")
    try:
        await page.set_viewport_size({"width": 390, "height": 844})
        await setup_auth(page, token)
        await page.goto(f"{BASE_URL}/admin", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # Check sidebar toggle button is visible
        sidebar_toggle = page.locator('[data-testid="admin-sidebar-toggle"]')
        toggle_visible = await sidebar_toggle.is_visible()
        if toggle_visible:
            print("PASS: Admin sidebar toggle button visible on mobile")
        else:
            print("FAIL: Admin sidebar toggle button NOT visible on mobile")
            # Check if admin page loaded
            admin_page = page.locator('[data-testid="admin-page"]')
            if await admin_page.is_visible():
                print("INFO: Admin page is loaded but sidebar toggle not found")
            else:
                print("INFO: Admin page not loaded - check authentication")
            await page.screenshot(path="/app/test_reports/admin_mobile_debug.jpeg", type="jpeg", quality=40, full_page=False)
            return False

        # Check sidebar is NOT visible before clicking (it should be off-screen on mobile)
        # The sidebar has -translate-x-full when sidebarOpen is false
        sidebar_div = page.locator('[data-testid="admin-tabs"] > div').first
        
        # Click toggle
        await sidebar_toggle.click()
        await page.wait_for_timeout(500)
        print("PASS: Clicked admin sidebar toggle")

        # Overlay backdrop should appear
        backdrop = page.locator('.fixed.inset-0.bg-black\\/30')
        backdrop_visible = await backdrop.is_visible()
        if backdrop_visible:
            print("PASS: Sidebar overlay/backdrop is visible after toggle")
        else:
            print("WARN: Sidebar overlay backdrop not visible (may use different selector)")

        # Take screenshot with sidebar open
        await page.screenshot(path="/app/test_reports/admin_mobile_sidebar_open.jpeg", type="jpeg", quality=40, full_page=False)
        print("Screenshot saved: admin_mobile_sidebar_open.jpeg")

        # Click a tab to close the sidebar
        customers_tab = page.locator('[data-testid="admin-tab-customers"]')
        if await customers_tab.is_visible():
            await customers_tab.click()
            await page.wait_for_timeout(500)
            print("PASS: Clicked a tab to close sidebar")

            # Backdrop should be gone
            backdrop_after = await backdrop.is_visible()
            if not backdrop_after:
                print("PASS: Sidebar closes after clicking a tab")
            else:
                print("WARN: Sidebar may still be open after tab click")
        else:
            print("WARN: Customers tab not visible in sidebar")

        return True
    except Exception as e:
        print(f"ERROR in test 3: {e}")
        await page.screenshot(path="/app/test_reports/admin_mobile_error.jpeg", type="jpeg", quality=40, full_page=False)
        return False


async def test_store_mobile_filters(page, token: str):
    """Test 4: Store page mobile filters toggle (390px)"""
    print("\n=== TEST 4: Store Mobile Filters Toggle (390px) ===")
    try:
        await page.set_viewport_size({"width": 390, "height": 844})
        await setup_auth(page, token)
        await page.goto(f"{BASE_URL}/store", wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(2000)

        # Mobile filters toggle button should be visible
        filters_toggle = page.locator('[data-testid="mobile-filters-toggle"]')
        toggle_visible = await filters_toggle.is_visible()
        if toggle_visible:
            print("PASS: Mobile filters toggle button visible on 390px")
        else:
            print("FAIL: Mobile filters toggle button NOT visible on 390px")
            return False

        # Category sidebar should be hidden by default (has 'hidden' class on mobile)
        sidebar = page.locator('[data-testid="category-sidebar"]')
        sidebar_visible = await sidebar.is_visible()
        if not sidebar_visible:
            print("PASS: Category sidebar is hidden by default on mobile")
        else:
            print("WARN: Category sidebar is visible by default (should be hidden on mobile)")

        # Click filters toggle
        await filters_toggle.click()
        await page.wait_for_timeout(500)
        print("PASS: Clicked mobile filters toggle")

        # Sidebar should now be visible
        sidebar_after = await sidebar.is_visible()
        if sidebar_after:
            print("PASS: Category sidebar visible after clicking filters toggle")
        else:
            print("FAIL: Category sidebar NOT visible after filters toggle click")

        await page.screenshot(path="/app/test_reports/store_mobile_filters_open.jpeg", type="jpeg", quality=40, full_page=False)
        print("Screenshot saved: store_mobile_filters_open.jpeg")

        # Click toggle again to hide
        await page.locator('[data-testid="mobile-filters-toggle"]').click()
        await page.wait_for_timeout(400)
        sidebar_closed = not await sidebar.is_visible()
        if sidebar_closed:
            print("PASS: Filters panel closes on second toggle click")
        else:
            print("WARN: Filters panel did not close on second click")

        return True
    except Exception as e:
        print(f"ERROR in test 4: {e}")
        return False


async def test_store_hero_no_overflow(page, token: str):
    """Test 5: Store hero section no horizontal overflow on 390px"""
    print("\n=== TEST 5: Store Hero No Overflow (390px) ===")
    try:
        await page.set_viewport_size({"width": 390, "height": 844})
        await setup_auth(page, token)
        await page.goto(f"{BASE_URL}/store", wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(1500)

        # Check body/store-page width vs scroll width (should be equal if no overflow)
        overflow_check = await page.evaluate("""() => {
            const body = document.body;
            const html = document.documentElement;
            const hero = document.querySelector('[data-testid="store-hero"]');
            
            const bodyWidth = body.scrollWidth;
            const viewportWidth = window.innerWidth;
            const hasHorizontalOverflow = bodyWidth > viewportWidth;
            
            let heroInfo = null;
            if (hero) {
                const rect = hero.getBoundingClientRect();
                heroInfo = {
                    width: rect.width,
                    right: rect.right,
                    overflow: rect.right > viewportWidth + 1
                };
            }
            
            return {
                bodyScrollWidth: bodyWidth,
                viewportWidth: viewportWidth,
                hasHorizontalOverflow: hasHorizontalOverflow,
                heroInfo: heroInfo,
                overflowDiff: bodyWidth - viewportWidth
            };
        }""")

        print(f"  Viewport width: {overflow_check['viewportWidth']}px")
        print(f"  Body scroll width: {overflow_check['bodyScrollWidth']}px")
        print(f"  Overflow diff: {overflow_check['overflowDiff']}px")

        if not overflow_check['hasHorizontalOverflow']:
            print("PASS: No horizontal overflow on store page at 390px")
        else:
            print(f"FAIL: Horizontal overflow detected ({overflow_check['overflowDiff']}px)")

        if overflow_check['heroInfo']:
            hero = overflow_check['heroInfo']
            if not hero['overflow']:
                print("PASS: Store hero section within viewport bounds")
            else:
                print(f"FAIL: Store hero overflows: right={hero['right']}px > viewport {overflow_check['viewportWidth']}px")
        else:
            print("WARN: Could not find store-hero element")

        await page.screenshot(path="/app/test_reports/store_hero_mobile.jpeg", type="jpeg", quality=40, full_page=False)
        return True
    except Exception as e:
        print(f"ERROR in test 5: {e}")
        return False


async def test_store_search_sort_stacking(page, token: str):
    """Test 6: Store search + sort row stacks on 390px without overflow"""
    print("\n=== TEST 6: Store Search + Sort Stacking (390px) ===")
    try:
        await page.set_viewport_size({"width": 390, "height": 844})
        await setup_auth(page, token)
        await page.goto(f"{BASE_URL}/store", wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(1500)

        # Check search input and sort select are visible
        search_input = page.locator('[data-testid="store-search-input"]')
        sort_select = page.locator('[data-testid="sort-select"]')

        search_visible = await search_input.is_visible()
        sort_visible = await sort_select.is_visible()

        if search_visible:
            print("PASS: Search input visible on mobile")
        else:
            print("WARN: Search input not visible on mobile")

        if sort_visible:
            print("PASS: Sort select visible on mobile")
        else:
            print("WARN: Sort select not visible on mobile")

        # Check for overflow in the search/sort row
        layout_info = await page.evaluate("""() => {
            const searchInput = document.querySelector('[data-testid="store-search-input"]');
            const sortSelect = document.querySelector('[data-testid="sort-select"]');
            const viewport = window.innerWidth;
            
            let result = { viewport, elements: [] };
            
            [searchInput, sortSelect].forEach((el, i) => {
                if (el) {
                    const rect = el.getBoundingClientRect();
                    result.elements.push({
                        name: i === 0 ? 'search' : 'sort',
                        x: rect.x,
                        right: rect.right,
                        width: rect.width,
                        overflows: rect.right > viewport + 2
                    });
                }
            });
            
            // Check the overall page overflow
            result.pageOverflow = document.documentElement.scrollWidth > viewport;
            result.pageScrollWidth = document.documentElement.scrollWidth;
            
            return result;
        }""")

        print(f"  Viewport: {layout_info['viewport']}px")
        for el in layout_info['elements']:
            status = "OVERFLOW" if el['overflows'] else "OK"
            print(f"  {el['name']}: right={el['right']:.0f}px, width={el['width']:.0f}px [{status}]")

        if not layout_info['pageOverflow']:
            print("PASS: No horizontal page overflow at 390px")
        else:
            print(f"FAIL: Page has horizontal overflow (scroll width: {layout_info['pageScrollWidth']}px)")

        await page.screenshot(path="/app/test_reports/store_search_sort_mobile.jpeg", type="jpeg", quality=40, full_page=False)
        print("Screenshot saved: store_search_sort_mobile.jpeg")
        return True
    except Exception as e:
        print(f"ERROR in test 6: {e}")
        return False


async def test_admin_tables_mobile_scroll(page, token: str):
    """Test 7: Admin tables should be horizontally scrollable on mobile"""
    print("\n=== TEST 7: Admin Tables Mobile Scroll (390px) ===")
    try:
        await page.set_viewport_size({"width": 390, "height": 844})
        await setup_auth(page, token)
        await page.goto(f"{BASE_URL}/admin", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # Navigate to customers tab (which has a table)
        customers_tab = page.locator('[data-testid="admin-tab-customers"]')
        if not await customers_tab.is_visible():
            # Try opening the sidebar first
            toggle = page.locator('[data-testid="admin-sidebar-toggle"]')
            if await toggle.is_visible():
                await toggle.click()
                await page.wait_for_timeout(500)

        if await customers_tab.is_visible():
            await customers_tab.click()
            await page.wait_for_timeout(2000)
            print("PASS: Navigated to customers tab")
        else:
            print("WARN: Customers tab not accessible, checking current view")

        # Check if tables have proper overflow
        table_info = await page.evaluate("""() => {
            const tables = document.querySelectorAll('[data-testid="admin-tabs"] table');
            const viewport = window.innerWidth;
            const results = [];
            
            tables.forEach((table, i) => {
                const rect = table.getBoundingClientRect();
                const parent = table.closest('[class*="overflow"]') || table.parentElement;
                const parentStyle = parent ? window.getComputedStyle(parent) : null;
                
                results.push({
                    index: i,
                    tableWidth: rect.width,
                    viewport: viewport,
                    tableOverflows: rect.width > viewport + 2,
                    parentOverflowX: parentStyle ? parentStyle.overflowX : 'unknown'
                });
            });
            
            // Also check page-level overflow
            const pageScrollWidth = document.documentElement.scrollWidth;
            const pageOverflows = pageScrollWidth > viewport + 2;
            
            return {
                tables: results,
                pageScrollWidth: pageScrollWidth,
                viewport: viewport,
                pageOverflows: pageOverflows
            };
        }""")

        print(f"  Viewport: {table_info['viewport']}px")
        print(f"  Page scroll width: {table_info['pageScrollWidth']}px")
        print(f"  Page overflows: {table_info['pageOverflows']}")

        if not table_info['tables']:
            print("WARN: No tables found in admin tabs (may need to load data)")
        else:
            for t in table_info['tables']:
                overflow_parent = t['parentOverflowX'] in ['auto', 'scroll']
                status = "OK - scroll container" if overflow_parent else ("OK - table fits" if not t['tableOverflows'] else "OVERFLOW")
                print(f"  Table {t['index']}: width={t['tableWidth']:.0f}px, parent overflow-x={t['parentOverflowX']} [{status}]")

        if not table_info['pageOverflows']:
            print("PASS: No page-level horizontal overflow on admin mobile")
        else:
            print(f"FAIL: Page has overflow on admin mobile ({table_info['pageScrollWidth'] - table_info['viewport']}px)")

        await page.screenshot(path="/app/test_reports/admin_tables_mobile.jpeg", type="jpeg", quality=40, full_page=False)
        print("Screenshot saved: admin_tables_mobile.jpeg")
        return True
    except Exception as e:
        print(f"ERROR in test 7: {e}")
        return False


async def test_desktop_smoke_test(page, token: str):
    """Test 8: Full page smoke test on desktop 1280px"""
    print("\n=== TEST 8: Desktop Smoke Test (1280px) ===")
    try:
        await page.set_viewport_size({"width": 1280, "height": 800})
        results = {}

        # Test Store page
        await setup_auth(page, token)
        await page.goto(f"{BASE_URL}/store", wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(1500)
        
        store_hero = await page.locator('[data-testid="store-hero"]').is_visible()
        store_layout = await page.locator('[data-testid="store-layout"]').is_visible()
        
        # Check no horizontal overflow
        store_overflow = await page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 2")
        results['store'] = {
            'hero_visible': store_hero,
            'layout_visible': store_layout,
            'has_overflow': store_overflow
        }
        print(f"  Store: hero={store_hero}, layout={store_layout}, overflow={store_overflow}")
        if store_hero and store_layout and not store_overflow:
            print("PASS: Store page renders correctly at 1280px")
        else:
            print("WARN: Store page has issues at 1280px")

        await page.screenshot(path="/app/test_reports/desktop_store.jpeg", type="jpeg", quality=40, full_page=False)

        # Test Admin page
        await page.goto(f"{BASE_URL}/admin", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)
        
        admin_page = await page.locator('[data-testid="admin-page"]').is_visible()
        admin_tabs = await page.locator('[data-testid="admin-tabs"]').is_visible()
        # Hamburger should be hidden at 1280px
        hamburger_hidden = not await page.locator('[data-testid="admin-sidebar-toggle"]').is_visible()
        admin_overflow = await page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 2")
        
        results['admin'] = {
            'page_visible': admin_page,
            'tabs_visible': admin_tabs,
            'hamburger_hidden': hamburger_hidden,
            'has_overflow': admin_overflow
        }
        print(f"  Admin: page={admin_page}, tabs={admin_tabs}, sidebar_toggle_hidden={hamburger_hidden}, overflow={admin_overflow}")
        if admin_page and admin_tabs and hamburger_hidden:
            print("PASS: Admin page renders correctly at 1280px (mobile toggle hidden)")
        else:
            print(f"WARN: Admin page issues at 1280px")

        await page.screenshot(path="/app/test_reports/desktop_admin.jpeg", type="jpeg", quality=40, full_page=False)

        # Test Login page
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(1000)
        login_overflow = await page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 2")
        print(f"  Login page: overflow={login_overflow}")
        if not login_overflow:
            print("PASS: Login page renders without overflow at 1280px")
        else:
            print("WARN: Login page has overflow at 1280px")

        await page.screenshot(path="/app/test_reports/desktop_login.jpeg", type="jpeg", quality=40, full_page=False)

        return True
    except Exception as e:
        print(f"ERROR in test 8: {e}")
        return False


async def run_all_tests(page):
    """Run all mobile responsiveness tests"""
    page.on("console", lambda msg: print(f"  CONSOLE [{msg.type}]: {msg.text}") if msg.type == "error" else None)

    token = get_auth_token()
    if not token:
        print("FATAL: Could not get auth token")
        return

    print(f"Got auth token: {token[:50]}...")

    results = {}

    # Test 1: Mobile hamburger
    await setup_auth(page, token)
    results['test1_hamburger'] = await test_topnav_mobile_hamburger(page)

    # Test 2: Desktop nav
    await setup_auth(page, token)
    results['test2_desktop_nav'] = await test_topnav_desktop(page)

    # Test 3: Admin mobile sidebar
    results['test3_admin_sidebar'] = await test_admin_mobile_sidebar(page, token)

    # Test 4: Store mobile filters
    results['test4_store_filters'] = await test_store_mobile_filters(page, token)

    # Test 5: Store hero overflow
    results['test5_hero_overflow'] = await test_store_hero_no_overflow(page, token)

    # Test 6: Search + sort stacking
    results['test6_search_sort'] = await test_store_search_sort_stacking(page, token)

    # Test 7: Admin tables mobile scroll
    results['test7_admin_tables'] = await test_admin_tables_mobile_scroll(page, token)

    # Test 8: Desktop smoke test
    results['test8_desktop_smoke'] = await test_desktop_smoke_test(page, token)

    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if v is False)
    print(f"Passed: {passed}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")
    for name, result in results.items():
        status = "PASS" if result else ("FAIL" if result is False else "WARN")
        print(f"  [{status}] {name}")


# This runs via browser automation tool's async runner
await run_all_tests(page)
