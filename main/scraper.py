# 1. Install the Playwright Python package
#---pip install playwright---

# 2. Install the actual browsers (Chromium, Firefox, WebKit)
# This is a separate step required by Playwright
   #---playwright install---

import os
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from .models import Business, ScrapeAction
import time, random
from django.contrib.auth.models import User

def extract_coordinates_from_url(url: str):
    try:
        coordinates = url.split("/@")[-1].split("/")[0]
        lat, lng = coordinates.split(",")[:2]
        return float(lat), float(lng)
    except Exception as e:
        print(f"[Coords] Failed to extract coordinates from URL: {e}")
        return None, None
    

def scrape_google_maps(search_for: str,user_id, total: int = 25):
    print(search_for,"LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL")
    business_list = []

    with sync_playwright() as p:
        print("[INFO] Launching browser...")
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context()
        page = context.new_page()

        try:
            print("[INFO] Navigating to Google Maps...")
            page.goto("https://www.google.com/maps?hl=en", wait_until="domcontentloaded", timeout=60000)

            # 1. AGGRESSIVE COOKIE HANDLING
            # Sometimes it's a 'Before you continue' page, sometimes a popup.
            try:
                # Look for ANY button that looks like an 'Accept' button
                selectors = [
                    "button:has-text('Accept all')", 
                    "button:has-text('I agree')",
                    "button:has-text('Agree')",
                    "//form//button[contains(., 'Accept')]"
                ]
                for selector in selectors:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=3000):
                        print(f"[INFO] Clicking consent: {selector}")
                        btn.click()
                        page.wait_for_load_state("networkidle")
                        break
            except:
                pass

            # 2. MULTI-SELECTOR SEARCH BOX (Resilience)
            # We try the standard ID, the name attribute, and the CSS class
            print("[INFO] Waiting for search box...")
            search_selectors = [
                "#searchboxinput", 
                "input[name='q']", 
                "input.searchboxinput",
                "input.fontBodyMedium"
            ]
            
            search_box = None
            for selector in search_selectors:
                try:
                    # If this succeeds, search_box becomes a valid pointer to that element
                    if page.wait_for_selector(selector, timeout=5000):
                        search_box = page.locator(selector)
                        print(f"[INFO] Found search box with: {selector}")
                        break
                except:
                    continue

            if search_box:
                # IMPORTANT: Use the 'search_box' variable directly!
                # Do NOT use page.locator('//input[@id="searchboxinput"]') here.
                search_box.fill(search_for) 
                search_box.press("Enter")
                print(f"[INFO] Search submitted for: {search_for}")
            else:
                raise Exception("Search box not found with any known selector")

            # Now wait for the results container (the "feed")
            # In the version of Maps where name='q' is used, results might be in a different container
            page.wait_for_selector('div[role="feed"], [aria-label*="Results for"]', timeout=30000)
            time.sleep(3)

            print("[INFO] Scrolling sidebar to load listings...")

            sidebar = page.locator('//div[@role="feed"]')  # main listings container
            previously_counted = 0
            attempts = 0
            max_attempts = 40

            while attempts < max_attempts:
                # Scroll the sidebar fully
                sidebar.evaluate("el => el.scrollTop = el.scrollHeight")
                time.sleep(random.uniform(2.5, 4.5))

                # Count valid listings
                listings = page.locator('//a[contains(@href, "/place/") and @aria-label]')
                count = listings.count()

                if count == previously_counted:
                    attempts += 1
                else:
                    attempts = 0
                    previously_counted = count

                if count >= total:
                    break

            print(f"[INFO] Total listings loaded: {previously_counted}")
            action = ScrapeAction.objects.create(
                user_id=user_id,
                keyword=search_for
            )

            # Scrape each listing
            listings = page.locator('//a[contains(@href, "/place/") and @aria-label]')
            for i in range(min(total, listings.count())):
                try:
                    listing = listings.nth(i)
                    listing.scroll_into_view_if_needed()
                    time.sleep(random.uniform(1, 2))
                    listing.click()

                    page.wait_for_selector('//button[@data-item-id="address"]', timeout=20000)
                    time.sleep(random.uniform(2, 3))

                    business = Business()
                    name_found = listing.get_attribute("aria-label") or ""#business.name,business.address,business.website,business.phone_number,business.category,business.latitude, business.longitude

                    def get_inner_text(xpath):
                        try:
                            elem = page.locator(xpath)
                            return elem.first.inner_text().strip() if elem.count() > 0 else ""
                        except Exception:
                            return ""

                    addr_found = get_inner_text('//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]')
                    web_found = get_inner_text('//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]')
                    phone_found = get_inner_text('//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]')
                    cat_found = get_inner_text('//button[contains(@jsaction, "category")]')
                    lat, lng = extract_coordinates_from_url(page.url)

                    if web_found and not web_found.startswith('http'):
                        web_found = f"https://{web_found}"

                    # SAVE TO DATABASE HERE
                    user_obj = User.objects.get(id=user_id)
                    new_entry = Business.objects.create(
                        user=user_obj,
                        action=action,
                        name=name_found,
                        address=addr_found,
                        website=web_found,
                        phone_number=phone_found,
                        category=cat_found,
                        latitude=lat,
                        longitude=lng
                    )
                    # business.save()

                    # business_list.append(business)
                    print(f"[Scrape] Saved business {i+1}: {business.name}")

                    time.sleep(random.uniform(1.5, 3))

                except PlaywrightTimeoutError:
                    print(f"[Warning] Timeout scraping listing {i+1}")
                except Exception as e:
                    print(f"[Error] Failed to scrape listing {i+1}: {e}")

        except Exception as e:
            print(f"[Playwright Error] {e}")
        finally:
            browser.close()

    print(f"[INFO] Scraped {len(business_list)} businesses")
    return business_list