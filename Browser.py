import os
import re
import shutil
import time

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from Helper import is_url, write_msg

COOKIE_DIR = 'cookies'

def login(url: str, credentials: str, headless: bool = True, auto: bool = True) -> dict[str, str]:
    """Login to a webpage in a browser to get cookies, user agent, and returned URL"""

    assert is_url(url)

    # --- Parse credentials string ---
    username = password = username_field = password_field = ""
    match_index = 0

    parts = credentials.split(",")
    for part in parts:
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        if key == "match":
            match_index = int(val)
        elif key == "username":
            username = val
        elif key == "password":
            password = val
        elif key == "username-el-name":
            username_field = val
        elif key == "password-el-name":
            password_field = val

    if not username_field:
        username_field = "username"
    if not password_field:
        password_field = "password"

    if os.path.exists(COOKIE_DIR):
        shutil.rmtree(COOKIE_DIR)
    os.mkdir(COOKIE_DIR)

    write_msg(f'login - url {url} - credentials {credentials}')

    chrome_options = webdriver.ChromeOptions()
    if auto and headless:
        chrome_options.add_argument("headless=new")
    if auto:
        prefs = {
            "download.default_directory": os.path.join(os.getcwd(), COOKIE_DIR)
        }
        write_msg(str(prefs))
        chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_position(200, 10, windowHandle='current')
    driver.get(url)

    user_agent = driver.execute_script("return navigator.userAgent")

    if not auto:
        write_msg("1. Login manually")
        write_msg("2. Open network tab")
        write_msg("3. Refresh page")
        write_msg("4. Copy curl with cookie, paste it below")

        cookie = None
        while True:
            curl_data = input("Paste curl data (follow by empty line): ")
            if "cookie" in curl_data.lower():
                cookie = curl_data
            if not curl_data:
                break

        assert cookie is not None
        write_msg("\n\n-------------")
        start = cookie.find("Cookie: ") + len("Cookie: ")
        end = cookie.find("'", start + 1)
        cookie = cookie.replace("%", "%%")
        login_url = driver.current_url
        return {
            "cookie_str": cookie[start:end],
            "user_agent": user_agent,
            "url": login_url
        }

    else:
        try:
            wait = WebDriverWait(driver, 10)
            user_element = wait.until(EC.presence_of_element_located(("name", username_field)))
            pwd_element = wait.until(EC.presence_of_element_located(("name", password_field)))

            user_element.send_keys(username)
            pwd_element.send_keys(password)
            pwd_element.send_keys(Keys.RETURN)

        except TimeoutException:
            write_msg(f"[ERROR] Login form fields not found within timeout.")
            driver.save_screenshot("login_debug.png")
            write_msg("📸 Screenshot saved as login_debug.png")
            with open("login_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            write_msg("📄 HTML snapshot saved as login_page.html")
            driver.quit()
            return {
                "cookie_str": "",
                "user_agent": user_agent,
                "url": url
            }
        except Exception as e:
            write_msg(f"[ERROR] Failed to fill login form: {e}")
            driver.quit()
            return {
                "cookie_str": "",
                "user_agent": user_agent,
                "url": url
            }

        write_msg("Waiting 5 seconds for login")
        time.sleep(5)

        login_url = driver.current_url
        write_msg(f"login URL: {login_url}")

        if "error" in driver.page_source.lower():
            write_msg("[WARNING] Login page shows an error — check credentials or login form structure.")

        # ✅ Cookie extraction directly from browser memory
        cookies = driver.get_cookies()
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies if "name" in c and "value" in c)

        driver.quit()

        return {
            "cookie_str": cookie_str.rstrip("; "),
            "user_agent": user_agent,
            "url": login_url
        }
