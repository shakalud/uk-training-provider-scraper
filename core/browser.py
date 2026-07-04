import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HttpClient:
    """Polite requests client shared by directory and website crawls."""

    def __init__(self, timeout: float = 20, delay: float = 1, user_agent: str = "UKTrainingScraper/1.0 (public portfolio project)"):
        self.timeout = timeout
        self.delay = delay
        self.last_request = 0.0
        self.log = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})
        retry = Retry(total=3, backoff_factor=0.8, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET", "POST"))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        wait = self.delay - (time.monotonic() - self.last_request)
        if wait > 0:
            time.sleep(wait)
        self.log.debug("%s %s", method.upper(), url)
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response
        finally:
            self.last_request = time.monotonic()

    def get(self, url: str, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)
