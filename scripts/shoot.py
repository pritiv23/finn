"""Phone-sized screenshots of every screen, plus any console errors. Dev aid."""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/shots"
ROUTES = [("brief", "#/brief"), ("ask", "#/ask"), ("dossier", "#/ask/MERIDIAN"), ("watch", "#/watch")]

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    for name, h in ROUTES:
        page.goto(BASE + h)
        page.wait_for_timeout(1200)
        page.screenshot(path=f"{OUT}/{name}.png", full_page=True)
    print("errors:", [e for e in errors if "fonts.g" not in e and "ERR_" not in e] or "none")
    b.close()
