#!/usr/bin/env python3
"""Browser acceptance for the WebAssembly TX-2 served from build/site by tools/serve_web.py.

Drives the real UI in Chromium:
  1. HELLO from the tape library: plugboard boot -> Lincoln Writer prints HELLO, WORLD.
  2. Tape tools: the upstream example tape fails as shipped and boots after Repair upstream tape.
  3. Sketchpad: library boot, INK, pen + DRAW on screen taps, two connected lines, pen lifted,
     the original display program keeps refreshing both lines; camera PNG export.
  4. Phone viewport: layout fits the screen width.
Requires Playwright: pip install playwright; playwright install chromium.
"""
import argparse, json
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

ROOT = Path(__file__).resolve().parents[1]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--url', default='http://127.0.0.1:8002/')
    a = ap.parse_args()
    report = {'url': a.url}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        def until(expr, timeout=60000):
            try: page.wait_for_function(expr, timeout=timeout)
            except PlaywrightTimeout:
                raise AssertionError(('timeout', expr, page.evaluate('({...tx2.state, display: undefined, writer: undefined})'))) from None
        def codabo():
            page.evaluate("tx2.show('console')"); page.get_by_role('button', name='CODABO', exact=True).first.click()
            page.evaluate("tx2.show('tape')")
        def boot(title):
            page.evaluate("tx2.show('tape')")
            page.locator('.tape-card', has_text=title).get_by_role('button', name='Load and start').click()

        page.goto(a.url)
        until('window.tx2 && tx2.tape.library.length > 0', 30000)
        page.evaluate("tx2.show('writer')")
        caret = page.locator('.paper .caret').first
        initial_cell = caret.evaluate('c => [c.offsetLeft, c.offsetTop]')

        # 1. HELLO
        boot('HELLO, WORLD')
        until("tx2.writer.text.split('HELLO, WORLD\\n').length > 3")
        report['hello'] = page.evaluate('tx2.writer.text')
        page.evaluate("tx2.show('writer')")
        assert caret.is_visible()
        assert caret.evaluate('c => c.offsetTop > c.previousElementSibling.offsetTop && c.offsetLeft === 0'), 'Caret must return to the left margin of the next line'
        page.get_by_role('button', name='New paper', exact=True).first.click()
        assert caret.evaluate('c => [c.offsetLeft, c.offsetTop]') == initial_cell, 'New paper must reset the caret to the first print cell'

        # 2. Upstream tape: as shipped it stops before printing; fixed it prints.
        # Power-cycle to clear the previous program from core before booting.
        page.locator('#power').click(); page.wait_for_timeout(300)
        page.evaluate("tx2.writer.clear(); tx2.show('tape')")
        upstream = ROOT / 'upstream/TX-2-simulator/examples/hello.tape'
        page.locator('input[type=file]').first.set_input_files(str(upstream))
        until("tx2.tape.mountedName === 'hello.tape'")
        codabo()  # console CODABO with TSP 377750
        page.wait_for_timeout(1500)
        report['upstream_raw_writer'] = page.evaluate('tx2.writer.text')
        page.locator('.subtabs button', has_text='Tools').click()
        page.get_by_role('button', name='Repair upstream tape').click()
        page.locator('#power').click(); page.wait_for_timeout(300)
        page.get_by_role('button', name='Mount result in reader').click()
        until("tx2.tape.mountedName === 'fixed.tape'")
        codabo()
        until("tx2.writer.text.includes('HELLO, WORLD')")
        report['upstream_fixed_writer'] = page.evaluate('tx2.writer.text')
        assert 'HELLO' not in report['upstream_raw_writer'], report

        # 3. Sketchpad
        page.locator('.subtabs button', has_text='Reader').click()
        boot('Sketchpad')
        until('tx2.state && tx2.state.points > 3000', 120000)
        page.evaluate("tx2.show('inputs')")
        page.get_by_role('button', name='Aim at INK').click()
        until('tx2.state.hits > 100')
        box = page.locator('#overlay').bounding_box()
        zoom = page.evaluate('tx2.settings.crt.zoom')
        at = lambda x, y: (box['x'] + (512 + x * zoom) * box['width'] / 1024, box['y'] + (512 - y * zoom) * box['height'] / 1024)
        settle = '!tx2.inputs.taps.length && !tx2.inputs.pending.length'
        page.mouse.click(*at(-128, 110)); until(settle)
        for x, y in [(-68, 110), (-20, 160)]:
            page.mouse.move(*at(x, y), steps=20); page.wait_for_timeout(1500)
            page.mouse.click(*at(x, y)); until(settle)
        page.keyboard.press('m'); until(settle)
        page.keyboard.press('Escape')
        page.evaluate("window.__pts = []; tx2.machine.onState(({s}) => { if (window.__pts) window.__pts.push(...s.display); })")
        start = page.evaluate('tx2.state.cycles')
        until(f'tx2.state.cycles > {start + 2500000}')
        pts = page.evaluate('window.__pts'); page.evaluate('window.__pts = null')
        horizontal = {x for x, y, _, unit in pts if unit == 0o60 and abs(y - 110) <= 3 and -124 <= x <= -75}
        diagonal = {(x, y) for x, y, _, unit in pts if unit == 0o60 and -60 < x < -24 and 115 < y < 158}
        page.wait_for_timeout(1500)
        report['sketchpad'] = {'model': page.evaluate('tx2.inputs.counts'), 'fault': page.evaluate('tx2.state.fault'),
                               'refreshed_horizontal_positions': len(horizontal), 'refreshed_diagonal_positions': len(diagonal)}
        assert report['sketchpad']['fault'] == 0 and report['sketchpad']['model']['lines'] >= 2, report
        assert len(horizontal) > 20 and len(diagonal) > 15, report
        page.screenshot(path=str(ROOT / 'results/browser-drawing.png'))
        with page.expect_download() as d:
            page.locator('#camera').click()
        d.value.save_as(str(ROOT / 'results/browser-drawing-export.png'))
        report['camera_png_bytes'] = (ROOT / 'results/browser-drawing-export.png').stat().st_size
        assert report['camera_png_bytes'] > 1000

        # 4. Phone layout
        phone = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True).new_page()
        phone.goto(a.url); phone.wait_for_function('window.tx2 && tx2.tape.library.length > 0', timeout=30000)
        report['phone_overflow_px'] = phone.evaluate('document.documentElement.scrollWidth - innerWidth')
        assert report['phone_overflow_px'] <= 0, report
        phone.screenshot(path=str(ROOT / 'results/browser-phone.png'))
        assert not errors, errors
        report['javascript_errors'] = errors
        browser.close()
    report['passed'] = True
    (ROOT / 'results/browser-integration.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('PASS: HELLO, upstream tape fix, Sketchpad lines with persistent refresh, camera PNG, phone layout')

if __name__ == '__main__':
    main()
