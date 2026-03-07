import httpx
import logging
from pathlib import Path
from app.core.config import ASSETS_DIR
from urllib.parse import quote

logger = logging.getLogger(__name__)

class BrowserService:
    def __init__(self):
        self.images_dir = ASSETS_DIR / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

    async def fetch_image(self, keyword: str, job_id: str, index: int) -> str:
        """
        Fetch an image for the keyword.
        Uses Pollinations.ai for free AI image generation/search.
        """
        filename = f"{job_id}_{index}.jpg"
        filepath = self.images_dir / filename
        
        # Pollinations API: https://image.pollinations.ai/prompt/{prompt}
        # Encode prompt
        kw = quote(str(keyword or "").strip(), safe="")
        url = f"https://image.pollinations.ai/prompt/{kw}?width=1280&height=720&nologo=true"
        
        logger.info(f"Fetching image for '{keyword}': {url}")
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=30)
                if resp.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
                    return str(filepath)
                else:
                    logger.error(f"Failed to fetch image: {resp.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching image: {e}")
            return None

    async def fetch_screenshot(self, url: str, job_id: str, index: int) -> str:
        """
        Capture screenshot of a webpage using a headless browser service (e.g., screenshotapi.net or similar free/mock).
        Since we don't have Playwright installed in this environment yet, we'll use a public screenshot API or mock it.
        """
        filename = f"{job_id}_screen_{index}.jpg"
        filepath = self.images_dir / filename
        
        # Using a public screenshot service (e.g., screenshotapi.net demo or similar)
        # For robustness in this MVP, we can fallback to Pollinations if URL is not valid or just a concept.
        # But let's try a real screenshot API if possible, or mock it with a "Browser Screenshot" placeholder.
        
        target_url = f"https://image.thum.io/get/width/1280/crop/720/noanimate/{url}"
        
        logger.info(f"Capturing screenshot for '{url}': {target_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(target_url, timeout=30)
                if resp.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
                    return str(filepath)
                else:
                    logger.error(f"Failed to capture screenshot: {resp.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}")
            return None

browser_service = BrowserService()
