"""Utility functions for scraping operations."""

import asyncio
import logging
from collections.abc import Callable

from patchright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .exceptions import RateLimitError

logger = logging.getLogger(__name__)


async def detect_rate_limit(page: Page) -> None:
    """Detect if LinkedIn has rate-limited or security-challenged the session.

    Checks (in order):
    1. URL contains /checkpoint or /authwall (security challenge)
    2. Body text contains rate-limit phrases on error-shaped pages (throttling)

    The body-text heuristic only runs on pages without a ``<main>`` element
    and with short body text (<2000 chars), since real rate-limit pages are
    minimal error pages.  This avoids false positives from profile content
    that happens to contain phrases like "slow down" or "try again later".

    Raises:
        RateLimitError: If any rate-limiting or security challenge is detected
    """
    # Check URL for security challenges
    current_url = page.url
    if "linkedin.com/checkpoint" in current_url or "authwall" in current_url:
        raise RateLimitError(
            "LinkedIn security checkpoint detected. "
            "You may need to verify your identity or wait before continuing.",
            suggested_wait_time=30,
        )

    # Check for rate limit messages — only on error-shaped pages.
    # Real rate-limit pages have no <main> element and short body text.
    # Normal LinkedIn pages (profiles, jobs) have <main> and long content
    # that may incidentally contain phrases like "slow down".
    try:
        has_main = await page.locator("main").count() > 0
        if has_main:
            return  # Normal page with content, skip body text heuristic

        body_text = await page.locator("body").inner_text(timeout=1000)
        if body_text and len(body_text) < 2000:
            body_lower = body_text.lower()
            if any(
                phrase in body_lower
                for phrase in [
                    "too many requests",
                    "rate limit",
                    "slow down",
                    "try again later",
                ]
            ):
                raise RateLimitError(
                    "Rate limit message detected on page.",
                    suggested_wait_time=30,
                )
    except RateLimitError:
        raise
    except PlaywrightTimeoutError:
        pass


async def scroll_to_bottom(
    page: Page,
    pause_time: float = 1.0,
    max_scrolls: int = 10,
    on_scroll: Callable[[int], None] | None = None,
) -> None:
    """Scroll to the bottom of the page to trigger lazy loading.

    Args:
        page: Patchright page object
        pause_time: Time to pause between scrolls (seconds)
        max_scrolls: Maximum number of scroll attempts
        on_scroll: Optional callback invoked after each scroll attempt.
    """
    for i in range(max_scrolls):
        previous_height = await page.evaluate("document.body.scrollHeight")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        if on_scroll is not None:
            on_scroll(1)
        await asyncio.sleep(pause_time)

        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == previous_height:
            logger.debug("Reached bottom after %d scrolls", i + 1)
            break


async def scroll_job_sidebar(
    page: Page,
    pause_time: float = 1.0,
    max_scrolls: int = 10,
    on_scroll: Callable[[int], None] | None = None,
) -> None:
    """Scroll the job search sidebar to load all job cards.

    LinkedIn renders job search results in a scrollable sidebar container,
    not the main page body. This function finds that container by locating
    a job card link and walking up to its scrollable ancestor, then scrolls
    it iteratively until no new content loads.

    Args:
        page: Patchright page object
        pause_time: Time to pause between scrolls (seconds)
        max_scrolls: Maximum number of scroll attempts
        on_scroll: Optional callback invoked with the number of scroll attempts.
    """
    # Wait for at least one job card link to render before scrolling
    try:
        await page.wait_for_selector('a[href*="/jobs/view/"]', timeout=5000)
    except PlaywrightTimeoutError:
        logger.debug("No job card links found, skipping sidebar scroll")
        return

    scroll_result = await page.evaluate(
        """async ({pauseTime, maxScrolls}) => {
            const link = document.querySelector('a[href*="/jobs/view/"]');
            if (!link) return { status: 'missing_link', attempts: 0, loaded: 0 };

            let container = link.parentElement;
            while (container && container !== document.body) {
                const style = window.getComputedStyle(container);
                const overflowY = style.overflowY;
                if ((overflowY === 'auto' || overflowY === 'scroll')
                    && container.scrollHeight > container.clientHeight) {
                    break;
                }
                container = container.parentElement;
            }

            if (!container || container === document.body) {
                return { status: 'missing_container', attempts: 0, loaded: 0 };
            }

            let attempts = 0;
            let loaded = 0;
            for (let i = 0; i < maxScrolls; i++) {
                const prevHeight = container.scrollHeight;
                container.scrollTop = container.scrollHeight;
                attempts++;
                await new Promise(r => setTimeout(r, pauseTime * 1000));
                if (container.scrollHeight === prevHeight) break;
                loaded++;
            }
            return { status: 'ok', attempts, loaded };
        }""",
        {"pauseTime": pause_time, "maxScrolls": max_scrolls},
    )
    attempts = int(scroll_result.get("attempts", 0))
    if attempts > 0 and on_scroll is not None:
        on_scroll(attempts)

    status = scroll_result.get("status")
    loaded = int(scroll_result.get("loaded", 0))
    if status == "missing_link":
        logger.debug("Job card link disappeared before evaluate, skipping scroll")
    elif status == "missing_container":
        logger.debug("No scrollable container found for job sidebar")
    elif loaded:
        logger.debug("Scrolled job sidebar %d times", loaded)
    else:
        logger.debug("Job sidebar container found but no new content loaded")


async def handle_modal_close(
    page: Page,
    on_click: Callable[[], None] | None = None,
) -> bool:
    """Close any popup modals that might be blocking content.

    Args:
        page: Patchright page object.
        on_click: Optional callback run after the dismiss button is clicked.

    Returns:
        True if a modal was closed, False otherwise.
    """
    try:
        close_button = page.locator(
            'button[aria-label="Dismiss"], '
            'button[aria-label="Close"], '
            "button.artdeco-modal__dismiss"
        ).first

        if await close_button.is_visible(timeout=1000):
            await close_button.click()
            if on_click is not None:
                on_click()
            await asyncio.sleep(0.5)
            logger.debug("Closed modal")
            return True
    except PlaywrightTimeoutError:
        pass
    except Exception as e:
        logger.debug("Error closing modal: %s", e)

    return False
