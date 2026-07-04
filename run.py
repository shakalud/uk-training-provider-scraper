import argparse
import logging
from pathlib import Path

import yaml

from app import run_scrape


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape public UK training provider directories")
    parser.add_argument(
        "--scraper",
        default="citb",
        choices=("citb",),
        help="Directory scraper to run (currently supported: citb)",
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--limit", type=int, help="Limit providers (recommended for tests)")
    parser.add_argument("--no-email-finder", action="store_true")
    parser.add_argument("--output-name", default="citb_providers")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    with (root / args.config).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    logging.basicConfig(level=getattr(logging, config.get("logging", {}).get("level", "INFO").upper()), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    result = run_scrape(
        root=root, scraper_name=args.scraper, limit=args.limit,
        find_emails=not args.no_email_finder, output_name=args.output_name,
        config_name=args.config,
    )
    logging.getLogger(__name__).info(
        "Exported %d providers to %s and %s",
        result["rows"], result["csv_path"], result["xlsx_path"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
