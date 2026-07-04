"""Application service shared by the command-line and Tkinter interfaces."""

from pathlib import Path

import yaml

from core.browser import HttpClient
from core.email_finder import EmailFinder
from core.exporter import export
from core.normalizer import deduplicate
from scrapers.citb import CitbScraper


def run_scrape(
    *,
    root: Path,
    scraper_name: str = "citb",
    limit: int | None = None,
    find_emails: bool = True,
    output_name: str = "citb_export",
    config_name: str = "config.yaml",
    progress_callback=None,
) -> dict:
    def emit(event: dict) -> None:
        if progress_callback:
            progress_callback(event)

    with (root / config_name).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    http = config.get("http", {})
    client = HttpClient(
        timeout=http.get("timeout_seconds", 20),
        delay=http.get("delay_seconds", 1),
        user_agent=http.get("user_agent", "UKTrainingScraper/1.0"),
    )
    finder = EmailFinder(client, max_pages=config.get("email_finder", {}).get("max_pages", 3))
    if scraper_name == "citb":
        scraper = CitbScraper(client, finder)
    else:
        raise ValueError(f"Unsupported scraper '{scraper_name}'. Currently supported: citb")
    records = deduplicate(scraper.scrape(limit=limit, find_emails=find_emails, progress_callback=emit))
    csv_path, xlsx_path = export(records, root / config.get("output_dir", "outputs"), output_name)
    emit({"type": "export_complete", "csv_path": str(csv_path), "xlsx_path": str(xlsx_path)})
    result = {
        "records": records,
        "csv_path": csv_path,
        "xlsx_path": xlsx_path,
        "rows": len(records),
        "emails": sum(bool(r.get("email") and r["email"] != "not_found") for r in records),
        "phones": sum(bool(r.get("phone")) for r in records),
        "websites": sum(bool(r.get("website")) for r in records),
        "locations": sum(bool(r.get("town_or_location")) for r in records),
    }
    emit({"type": "done", **{key: value for key, value in result.items() if key != "records"}})
    return result
