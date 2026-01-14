import asyncio
import re
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

class PriceScraper:
    async def get_page_data(self, url: str):
        async with Stealth().use_async(async_playwright()) as p:
            # We use a real browser window so you can solve any captcha that appears
            browser = await p.chromium.launch(headless=False) 
            context = await browser.new_context()
            page = await context.new_page()

            print(f"🔍 Accessing: {url}")
            try:
                await page.goto(url, wait_until="load")
                
                # Give the page 10 seconds. If a captcha appears, SOLVE IT MANUALLY.
                print("⏳ Human Check: If you see a slider, solve it in the browser window now...")
                await asyncio.sleep(10) 

                # AGNOSTIC EXTRACTION:
                # 1. Get the Page Title (Usually the <h1> or the largest meta title)
                name = await page.title()
                # Clean Shopee's suffix from title
                name = name.split("|")[0].strip()

                # 2. Find the Price by looking for the '$' character and surrounding numbers
                # We evaluate this inside the browser to find the most likely price element

                price_candidates = await page.evaluate("""
                () => {
                    const priceRegex = /\\$\\d+(?:\\.\\d{2})?/g;
                    const results = [];

                    document.querySelectorAll('span, div').forEach(el => {
                        if (!el.innerText) return;
                        if (el.innerText.length > 60) return; // 🚫 skip large blocks

                        const matches = el.innerText.match(priceRegex);
                        if (!matches) return;

                        const style = window.getComputedStyle(el);

                        matches.forEach(price => {
                            results.push({
                                price,
                                fontSize: parseFloat(style.fontSize),
                                isStriked: style.textDecoration.includes('line-through'),
                                color: style.color,
                                textContext: el.innerText
                            });
                        });
                    });

                    return results;
                }
                """)

                def get_product_price_only(candidates):
                    """
                    candidates: The list of objects you got (price, fontSize, textContext, etc.)
                    """
                    # 1. Filter out known 'Shipping' or 'Voucher' keywords using regex
                    # This specifically removes the $60.00 and $5.99 delivery fees
                    filtered = [
                        item for item in candidates 
                        if not re.search(r'delivery|spend|min\.|slot|express', item['textContext'], re.IGNORECASE)
                        and not item.get('isStriked', False) and not item.get('fontSize') == 13
                    ]

                    if not filtered:
                        return None

                    # 2. Pick the item with the LARGEST font size
                    # On Lazada/Shopee, the product price ($7.50) is visually the biggest element
                    main_item = max(filtered, key=lambda x: x['fontSize'])
                    
                    # 3. Final Regex: Extract only the decimal number from the winning string
                    # Matches: 7.50 from "$7.50" or "SGD 7.50"
                    price_match = re.search(r"(\d+\.\d{2})", main_item['price'])
                    return float(price_match.group(1)) if price_match else None
                
                best_price = get_product_price_only(price_candidates)

                return best_price


            except Exception as e:
                return {"error": f"Extraction failed: {str(e)}"}
            finally:
                await browser.close()

if __name__ == "__main__":
    scraper = PriceScraper()
    url = "https://www.lazada.sg/products/pdp-i301072965-s527094858.html?scm=1007.17760.398138.0&pvid=d9bfb37c-7bba-4f2f-a3db-f159b313ea3b&search=flashsale&spm=a2o42.homepage.FlashSale.d_301072965"
    print(asyncio.run(scraper.get_page_data(url)))