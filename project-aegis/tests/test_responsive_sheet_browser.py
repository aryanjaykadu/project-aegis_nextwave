"""Browser coverage for responsive layout and Operations-sheet recovery."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Error, Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = (
    (1920, 1080), (1440, 900), (1366, 768), (2560, 1440),
    (1024, 768), (768, 1024), (390, 844), (320, 568), (844, 390),
)


@pytest.fixture(scope="module")
def app_url():
    configured_url = os.environ.get("AEGIS_BASE_URL")
    if configured_url:
        yield configured_url.rstrip("/")
        return

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "backend.main:app",
            "--host", "127.0.0.1", "--port", str(port),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if process.poll() is not None:
                pytest.fail("The ProjectAegis test server exited before becoming ready.")
            try:
                with urllib.request.urlopen(url, timeout=0.5):
                    break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        else:
            pytest.fail("The ProjectAegis test server did not become ready.")
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture(scope="module")
def playwright_runtime():
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="module")
def chromium(playwright_runtime) -> Browser:
    try:
        browser = playwright_runtime.chromium.launch(headless=True)
    except Error as error:
        pytest.skip(f"Chromium is not installed for Playwright: {error}")
    yield browser
    browser.close()


def new_page(browser: Browser, app_url: str, width: int = 390, height: int = 844) -> Page:
    context = browser.new_context(
        viewport={"width": width, "height": height},
        has_touch=True,
        service_workers="block",
        reduced_motion="reduce",
    )
    page = context.new_page()
    page.goto(app_url, wait_until="load")
    page.wait_for_function("typeof window.aegisSetOpsSheetSnap === 'function'")
    return page


def drag(page: Page, selector: str, delta_y: int, steps: int = 4) -> None:
    box = page.locator(selector).bounding_box()
    assert box is not None, f"{selector} is not visible"
    x = box["x"] + box["width"] / 2
    start_y = box["y"] + box["height"] / 2
    end_y = min(max(2, start_y + delta_y), page.viewport_size["height"] - 2)
    page.mouse.move(x, start_y)
    page.mouse.down()
    page.mouse.move(x, end_y, steps=steps)
    page.mouse.up()
    page.wait_for_function(
        "['peek','half','full'].includes(document.querySelector('#ops-sheet').dataset.sheetState)"
    )


def test_required_viewports_have_no_horizontal_overflow_or_rail_collisions(chromium, app_url):
    page = new_page(chromium, app_url)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    for width, height in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(80)
        result = page.evaluate(
            """() => {
              const rect = selector => {
                const node = document.querySelector(selector);
                if (!node || getComputedStyle(node).display === 'none') return null;
                const {x,y,width,height} = node.getBoundingClientRect();
                return {x,y,width,height,right:x+width,bottom:y+height};
              };
              return {
                scrollWidth: document.documentElement.scrollWidth,
                width: innerWidth,
                map: rect('#map'),
                ops: rect('#ops-sheet'),
                hud: rect('.comic-panel'),
                search: rect('.search-container'),
                caption: rect('#aegis-layer-caption'),
                dock: rect('#estimate-dock'),
                credits: rect('#aegis-map-credits'),
                actions: rect('#aegis-map-actions'),
                attribution: rect('.leaflet-control-attribution'),
                zoom: rect('.leaflet-control-zoom'),
                scale: rect('.leaflet-control-scale')
              };
            }"""
        )
        assert result["scrollWidth"] <= result["width"], (width, height, result)
        assert result["map"] is not None and result["map"]["width"] > 0
        assert result["attribution"] is not None
        assert result["zoom"] is not None
        if width >= 1024:
            assert result["ops"]["x"] > result["map"]["x"]
            assert result["map"]["right"] <= result["ops"]["x"]
            assert result["hud"]["right"] <= result["ops"]["x"]
            assert result["search"]["x"] >= result["map"]["x"]
            assert result["search"]["right"] <= result["ops"]["x"]
        if width == 844 and height == 390:
            assert result["ops"]["x"] >= 532
            assert result["ops"]["width"] == 300
            assert result["search"]["bottom"] <= result["caption"]["y"]
            assert result["caption"]["bottom"] <= result["credits"]["y"]
            assert result["credits"]["bottom"] <= result["scale"]["y"]
            assert result["hud"]["bottom"] <= result["dock"]["y"]
            assert result["zoom"]["x"] + result["zoom"]["width"] <= result["actions"]["x"]
        if width <= 767:
            assert result["dock"]["bottom"] <= result["ops"]["y"]
            assert result["caption"]["bottom"] < result["dock"]["y"]
    assert not errors, errors
    page.context.close()


def test_sheet_recovers_from_handle_content_scroll_and_interrupted_drag(chromium, app_url):
    page = new_page(chromium, app_url)
    page.locator("#ops-sheet .sheet-handle").wait_for()

    drag(page, "#ops-sheet .sheet-handle", -800)
    assert page.locator("#ops-sheet").get_attribute("data-sheet-state") == "full"

    content = page.locator(".ops-page.active")
    content.evaluate(
        "(node) => { node.insertAdjacentHTML('beforeend', '<div style=\"height:1200px\"></div>'); node.scrollTop = 100; }"
    )
    drag(page, ".ops-page.active", 180)
    assert page.locator("#ops-sheet").get_attribute("data-sheet-state") == "full"
    content.evaluate("(node) => { node.scrollTop = 0; }")
    drag(page, ".ops-page.active", 180)
    assert page.locator("#ops-sheet").get_attribute("data-sheet-state") == "half"

    drag(page, "#ops-sheet .sheet-handle", 600)
    assert page.locator("#ops-sheet").get_attribute("data-sheet-state") == "peek"

    handle = page.locator("#ops-sheet .sheet-handle").bounding_box()
    assert handle is not None
    page.mouse.move(handle["x"] + 20, handle["y"] + 20)
    page.mouse.down()
    page.mouse.move(handle["x"] + 20, handle["y"] - 40)
    page.evaluate("window.dispatchEvent(new Event('blur'))")
    page.mouse.up()
    page.wait_for_timeout(20)
    assert page.locator("#ops-sheet").get_attribute("data-sheet-state") in {"peek", "half", "full"}
    assert not page.locator("body").evaluate("(node) => node.classList.contains('aegis-sheet-dragging')")

    page.keyboard.press("End")
    assert page.locator("#ops-sheet").get_attribute("data-sheet-state") == "full"
    page.keyboard.press("Home")
    assert page.locator("#ops-sheet").get_attribute("data-sheet-state") == "peek"
    page.context.close()


def test_two_hundred_random_handle_gestures_never_leave_sheet_stuck(chromium, app_url):
    page = new_page(chromium, app_url, 320, 568)
    page.evaluate("window.aegisSetOpsSheetSnap('half', false)")
    for index in range(200):
        delta = ((index * 7919) % 521) - 260
        drag(page, "#ops-sheet .sheet-handle", delta, steps=1)
        state = page.locator("#ops-sheet").get_attribute("data-sheet-state")
        assert state in {"peek", "half", "full"}, (index, state)
        assert not page.locator("body").evaluate(
            "(node) => node.classList.contains('aegis-sheet-dragging')"
        ), index

    page.evaluate("window.aegisSetOpsSheetSnap('half', false)")
    drag(page, "#ops-sheet .sheet-handle", 800, steps=1)
    assert page.locator("#ops-sheet").get_attribute("data-sheet-state") == "peek"
    page.context.close()


def test_sheet_settle_finishes_under_four_hundred_milliseconds(chromium, app_url):
    context = chromium.new_context(
        viewport={"width": 390, "height": 844},
        has_touch=True,
        service_workers="block",
        reduced_motion="no-preference",
    )
    page = context.new_page()
    page.goto(app_url, wait_until="load")
    page.wait_for_function("typeof window.aegisSetOpsSheetSnap === 'function'")
    page.evaluate(
        """() => {
          const sheet = document.querySelector('#ops-sheet');
          window.__sheetSettleDuration = null;
          let started = 0;
          sheet.addEventListener('transitionrun', event => {
            if (event.target === sheet && event.propertyName === 'transform') started = performance.now();
          });
          sheet.addEventListener('transitionend', event => {
            if (event.target === sheet && event.propertyName === 'transform' && started) {
              window.__sheetSettleDuration = performance.now() - started;
            }
          });
        }"""
    )
    drag(page, "#ops-sheet .sheet-handle", -800)
    duration = page.evaluate("window.__sheetSettleDuration")
    assert duration is not None and 0 < duration < 400, duration
    page.context.close()


def test_layout_recalculates_across_orientation_and_text_scaling(chromium, app_url):
    page = new_page(chromium, app_url)
    page.set_viewport_size({"width": 844, "height": 390})
    page.wait_for_timeout(300)
    assert page.locator("#ops-sheet").get_attribute("data-sheet-state") == "desktop"
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)
    assert page.locator("#ops-sheet").get_attribute("data-sheet-state") == "peek"
    page.locator("html").evaluate("(node) => node.dataset.textSize = 'largest'")
    page.wait_for_timeout(100)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator("#aegis-sheet-collapse").is_visible() is False
    page.context.close()


@pytest.mark.parametrize("x,y", ((390, 220), (1020, 220), (390, 870), (1020, 870)))
def test_long_press_popups_stay_inside_map_and_clear_of_controls(chromium, app_url, x, y):
    page = new_page(chromium, app_url, 1440, 900)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.mouse.move(x, y)
    page.mouse.down()
    page.wait_for_timeout(700)
    page.mouse.up()
    page.wait_for_selector(".leaflet-popup")
    page.wait_for_timeout(350)

    boxes = page.evaluate(
        """() => {
          const bounds = selector => {
            const node = document.querySelector(selector);
            if (!node) return null;
            const rect = node.getBoundingClientRect();
            return {left:rect.left,top:rect.top,right:rect.right,bottom:rect.bottom};
          };
          return {
            popup:bounds('.leaflet-popup'), map:bounds('#map'),
            search:bounds('.search-container'), zoom:bounds('.leaflet-control-zoom'),
            actions:bounds('#aegis-map-actions'), scale:bounds('.leaflet-control-scale'),
            attribution:bounds('.leaflet-control-attribution'),
            caption:bounds('#aegis-layer-caption'), credits:bounds('#aegis-map-credits')
          };
        }"""
    )
    popup = boxes["popup"]
    map_bounds = boxes["map"]
    assert popup["left"] >= map_bounds["left"]
    assert popup["right"] <= map_bounds["right"]
    assert popup["top"] >= boxes["search"]["bottom"]
    for selector in ("zoom", "actions", "scale", "attribution", "caption", "credits"):
        obstacle = boxes[selector]
        assert (
            popup["right"] <= obstacle["left"]
            or popup["left"] >= obstacle["right"]
            or popup["bottom"] <= obstacle["top"]
            or popup["top"] >= obstacle["bottom"]
        ), (x, y, selector, popup, obstacle)
    page.keyboard.press("Escape")
    page.wait_for_selector(".leaflet-popup", state="detached")
    assert page.locator(".leaflet-popup").count() == 0
    assert not errors, errors
    page.context.close()


def test_webkit_touch_pointer_path(playwright_runtime, app_url):
    try:
        browser = playwright_runtime.webkit.launch(headless=True)
    except Error:
        pytest.skip("Playwright WebKit is not installed; run `python -m playwright install webkit`.")
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        has_touch=True,
        service_workers="block",
        reduced_motion="reduce",
    )
    page = context.new_page()
    page.goto(app_url, wait_until="load")
    page.wait_for_function("typeof window.aegisSetOpsSheetSnap === 'function'")
    page.evaluate("window.aegisSetOpsSheetSnap('full', false)")
    page.evaluate(
        """() => {
          const handle = document.querySelector('#ops-sheet .sheet-handle');
          const box = handle.getBoundingClientRect();
          const x = box.x + box.width / 2;
          const start = box.y + box.height / 2;
          const emit = (type, y) => handle.dispatchEvent(new PointerEvent(type, {
            bubbles: true, cancelable: true, pointerId: 7, pointerType: 'touch',
            isPrimary: true, button: 0, clientX: x, clientY: y
          }));
          emit('pointerdown', start);
          emit('pointermove', start + 40);
          emit('pointermove', start + 100);
          emit('pointermove', start + 180);
          emit('pointerup', start + 180);
        }"""
    )
    page.wait_for_function("document.querySelector('#ops-sheet').dataset.sheetState === 'half'")
    assert page.locator(".leaflet-control-attribution").is_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    context.close()
    browser.close()
