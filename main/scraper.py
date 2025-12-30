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
    business_list = []

    with sync_playwright() as p:
        print("[INFO] Launching browser...")
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context()
        page = context.new_page()

        try:
            print("[INFO] Navigating to Google Maps...")
            page.goto("https://www.google.com/maps", wait_until="domcontentloaded", timeout=120000)
            page.wait_for_selector('//input[@id="searchboxinput"]', timeout=15000)

            print(f"[INFO] Searching for: {search_for}")
            search_box = page.locator('//input[@id="searchboxinput"]')
            search_box.fill(search_for)
            page.keyboard.press("Enter")

            page.wait_for_selector('//a[contains(@href, "/place/")]', timeout=20000)
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