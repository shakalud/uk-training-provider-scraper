import logging
import re
from collections import deque
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .normalizer import normalize_url

EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])", re.I)
CONTACT_HINTS = ("contact", "about", "location", "find-us", "get-in-touch")
EXCLUDED_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")


class EmailFinder:
    def __init__(self, client, max_pages: int = 3):
        self.client = client
        self.max_pages = max(1, max_pages)
        self.log = logging.getLogger(__name__)

    def find(self, website: str) -> tuple[str, str]:
        start = normalize_url(website)
        if not start:
            return "not_found", ""
        domain = urlsplit(start).netloc.lower().removeprefix("www.")
        queue, seen = deque([start]), set()
        while queue and len(seen) < self.max_pages:
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            try:
                response = self.client.get(url, allow_redirects=True)
            except Exception as exc:
                self.log.debug("Email page failed %s: %s", url, exc)
                continue
            if "text/html" not in response.headers.get("Content-Type", "text/html"):
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            candidates = []
            for link in soup.select("a[href]"):
                href = link.get("href", "")
                if href.lower().startswith("mailto:"):
                    candidates.extend(EMAIL_RE.findall(href[7:].split("?", 1)[0]))
            candidates.extend(EMAIL_RE.findall(soup.get_text(" ")))
            candidates = [e.lower() for e in candidates if not e.lower().endswith(EXCLUDED_SUFFIXES)]
            if candidates:
                return sorted(set(candidates), key=lambda e: (e.startswith(("noreply@", "no-reply@")), len(e)))[0], response.url
            if len(seen) == 1:
                links = []
                for link in soup.select("a[href]"):
                    href = link.get("href", "")
                    label = (link.get_text(" ", strip=True) + " " + href).lower()
                    target = urljoin(response.url, href).split("#", 1)[0]
                    if any(h in label for h in CONTACT_HINTS) and urlsplit(target).netloc.lower().removeprefix("www.") == domain:
                        links.append(target)
                queue.extend(dict.fromkeys(links))
        return "not_found", ""
