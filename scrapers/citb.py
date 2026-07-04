import logging
import re
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from core.normalizer import clean_text, normalize_phone, normalize_url


class CitbScraper:
    DIRECTORY_URL = "https://myportal.citb.co.uk/CITB-Training-Dir-v2/"
    DETAIL_TEMPLATE = "https://myportal.citb.co.uk/CITB-Training-Dir/ato-Details/?id={}"
    UK_POSTCODE_RE = re.compile(r"\b(?:GIR\s?0AA|(?:[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}))\b", re.I)
    COUNTRY_NAMES = {"england", "scotland", "wales", "northern ireland", "united kingdom", "uk"}

    def __init__(self, client, email_finder=None):
        self.client = client
        self.email_finder = email_finder
        self.log = logging.getLogger(__name__)
        self.course_api_url = ""
        self.course_api_params = {}

    def _discover_course_endpoint(self, html: str) -> None:
        """Read the public course endpoint from CITB's current page script."""
        match = re.search(
            r"urlCall\s*=\s*['\"]([^'\"]*GetCourseSearchResults[^'\"]*)",
            html,
            re.I,
        )
        if not match:
            self.log.warning("CITB course endpoint was not present in the directory page")
            return
        parsed = urlsplit(match.group(1))
        self.course_api_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        self.course_api_params = dict(parse_qsl(parsed.query, keep_blank_values=True))

    def provider_index(self) -> list[tuple[str, str]]:
        html = self.client.get(self.DIRECTORY_URL).text
        self._discover_course_endpoint(html)
        soup = BeautifulSoup(html, "html.parser")
        select = soup.select_one("select#ato")
        if not select:
            raise RuntimeError("CITB provider selector was not found; the directory markup may have changed")
        providers = [(clean_text(o.get_text()), o.get("value", "")) for o in select.select("option[value]") if o.get("value")]
        self.log.info("Discovered %d CITB providers", len(providers))
        return providers

    @staticmethod
    def _field(soup: BeautifulSoup, *ids: str) -> str:
        for field_id in ids:
            node = soup.find(id=field_id) or soup.find(attrs={"name": field_id})
            if node:
                if node.name == "input":
                    return clean_text(node.get("value"))
                return clean_text(node.get_text(" "))
        return ""

    @staticmethod
    def _multiline_field(soup: BeautifulSoup, field_id: str) -> str:
        node = soup.find(id=field_id)
        if not node:
            return ""
        lines = [clean_text(line) for line in node.get_text("\n").splitlines() if clean_text(line)]
        return ", ".join(lines)

    @classmethod
    def _town_from_address(cls, address: str) -> str:
        """Extract the locality printed immediately before a UK postcode."""
        if not address:
            return ""
        parts = [clean_text(part) for part in address.split(",") if clean_text(part)]
        for part in parts:
            match = cls.UK_POSTCODE_RE.search(part)
            if match:
                return clean_text(part[:match.start()].strip(" ,-"))
        candidates = [part for part in parts if part.casefold() not in cls.COUNTRY_NAMES]
        return candidates[-1] if len(candidates) > 1 else ""

    def _locations(self, provider_id: str) -> list[str]:
        if not self.course_api_url:
            self.log.warning("Course locations unavailable because CITB did not publish an endpoint")
            return []
        payload = {
            "PortalUserId": "", "approvedTrainingOrganisationId": provider_id,
            "TrainingCourseNameId": "", "StandardNameId": "", "StartDate": "", "EndDate": "",
            "IncludeUnscheduledTrainingCourses": True, "Postcode": "", "DistanceFromPostcode": "",
            "Keyword": "", "PostCodeLat": "", "PostCodeLong": "",
        }
        try:
            data = self.client.post(self.course_api_url, params=self.course_api_params, json=payload).json()
        except Exception as exc:
            self.log.warning("Course locations unavailable for %s: %s", provider_id, exc)
            return []
        values = []
        for row in data if isinstance(data, list) else []:
            value = clean_text(row.get("location") or row.get("Address"))
            if value:
                values.append(value)
        return list(dict.fromkeys(values))

    def scrape(self, limit: int | None = None, find_emails: bool = True, progress_callback=None) -> list[dict]:
        providers = self.provider_index()[:limit or None]
        if progress_callback:
            progress_callback({"type": "start", "total": len(providers)})
        records = []
        for number, (index_name, provider_id) in enumerate(providers, 1):
            source_url = self.DETAIL_TEMPLATE.format(provider_id)
            self.log.info("[%d/%d] %s", number, len(providers), index_name)
            notes = []
            try:
                soup = BeautifulSoup(self.client.get(source_url).text, "html.parser")
                provider_name = self._field(soup, "name") or index_name
                website = normalize_url(self._field(soup, "websiteurl"))
                email = self._field(soup, "emailaddress1").lower()
                phone = normalize_phone(self._field(soup, "telephone1"))
                addresses = list(dict.fromkeys(filter(None, (
                    self._multiline_field(soup, "address1_composite"),
                    self._multiline_field(soup, "address2_composite"),
                ))))
                address = "; ".join(addresses)
                towns = list(dict.fromkeys(filter(None, (self._town_from_address(item) for item in addresses))))
                location = "; ".join(towns)
            except Exception as exc:
                self.log.warning("Detail page failed for %s: %s", index_name, exc)
                provider_name, website, email, phone, location, address = index_name, "", "", "", "", ""
                notes.append("CITB detail page unavailable")
            if not location:
                locations = self._locations(provider_id)
                location = "; ".join(locations[:5])
                if len(locations) > 5:
                    notes.append(f"{len(locations)} course locations; first 5 shown")
            email_source = source_url if email else ""
            if not email and website and find_emails and self.email_finder:
                email, email_source = self.email_finder.find(website)
            if not email:
                email = "not_found"
            record = {
                "provider_name": provider_name, "town_or_location": location,
                "address": address,
                "website": website, "email": email, "phone": phone,
                "source_url": source_url, "email_source": email_source,
                "notes": "; ".join(notes),
            }
            records.append(record)
            if progress_callback:
                progress_callback({
                    "type": "provider_processed", "processed": number,
                    "total": len(providers), "record": record.copy(),
                })
        return records
