"""Run on your LOCAL Windows/WSL browser, while FastAPI server is listening on 127.0.0.1:8765.

Usage: pip install playwright && python -m playwright install chromium && python scripts/browser_smoke.py
This environment's headless browser navigation may be blocked by platform admin policy.
"""
from __future__ import annotations
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        page=await browser.new_page(viewport={'width':1600,'height':1000})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto('http://127.0.0.1:8765/',wait_until='networkidle')
        assert 'SAR2Action' in await page.title()
        await page.locator('#quickAnalyze').click()
        await page.locator('.claim-list li').first.wait_for(timeout=15000)
        await page.locator('.evidence-chip').first.click()
        assert await page.locator('#evidenceDialog').evaluate('(e)=>e.open')
        await page.locator('#closeDialog').click()
        await page.locator('#quickStory').click()
        await page.locator('#storyOutput .story-frame').first.wait_for(timeout=15000)
        assert await page.locator('#storyOutput .story-frame').count()==5
        await page.screenshot(path='browser_smoke.png',full_page=True)
        assert not errors,errors
        print('Browser smoke PASSED; screenshot: browser_smoke.png')
        await browser.close()

if __name__=='__main__':asyncio.run(main())
