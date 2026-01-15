import asyncio
import re
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

class PriceScraper:

    def get_first_price(self, price_list):
        for i, item in enumerate(price_list):
            item = item.strip()
            if re.fullmatch(r"\$\d+\.\d{2}", item):
                return float(item[1:])
            if item == "$" and i + 1 < len(price_list):
                nxt = price_list[i + 1].strip()
                if re.fullmatch(r"\d+\.\d{2}", nxt):
                    return float(nxt)
        return None

    async def search_top_10(self, page, query):
        base_url = "https://www.lazada.sg"

        await page.goto(base_url, wait_until="domcontentloaded")
        await asyncio.sleep(5)

        await page.locator("input[type='search']").fill(query)
        await page.keyboard.press("Enter")

        await page.wait_for_selector("[data-qa-locator='product-item']", timeout=30000)

        product_cards = page.locator("[data-qa-locator='product-item']")
        count = await product_cards.count()

        urls = []
        for i in range(min(10, count)):
            href = await product_cards.nth(i).locator("a").first.get_attribute("href")
            if href:
                if href.startswith("http"):
                    urls.append(href)
                else:
                    urls.append(base_url + href)

        return urls

    async def scrape_product(self, context, url):
        page = await context.new_page()

        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        await page.mouse.wheel(0, 3000)
        await page.wait_for_timeout(2000)

        name = (await page.title()).split("|")[0].strip()

        variants = page.locator(".sku-property-text")
        if await variants.count() > 0:
            await variants.first.click()
            await asyncio.sleep(2)

        try:
            await page.wait_for_selector(
                ".pdp-mod-product-info span[class*='price']",
                timeout=15000
            )
            price_locator = page.locator(".pdp-mod-product-info span[class*='price']")
        except:
            await page.wait_for_selector("span[class*='price']", timeout=15000)
            price_locator = page.locator("span[class*='price']")

        price_parts = await price_locator.all_inner_texts()
        price = self.get_first_price(price_parts)

        await page.close()

        return {
            "name": name,
            "price": price,
            "url": url
        }

    async def search_and_scrape_top_10(self, query):
        async with Stealth().use_async(async_playwright()) as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            urls = await self.search_top_10(page, query)

            results = []
            for url in urls:
                try:
                    data = await self.scrape_product(context, url)
                    results.append(data)
                except Exception as e:
                    results.append({"url": url, "error": str(e)})

            await browser.close()
            return results


if __name__ == "__main__":
    scraper = PriceScraper()
    results = asyncio.run(scraper.search_and_scrape_top_10("logitech mechanical keyboard"))
    for r in results:
        print(r)
