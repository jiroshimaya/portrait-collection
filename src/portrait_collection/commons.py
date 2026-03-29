from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

COMMONS_API_ENDPOINT: Final[str] = "https://commons.wikimedia.org/w/api.php"
USER_AGENT: Final[str] = (
    "portrait-collection/0.1 (https://github.com/jiroshimaya/portrait-collection)"
)


@dataclass(frozen=True)
class CommonsImageMetadata:
    file_title: str
    download_url: str
    media_page_url: str
    license_short_name: str
    license_url: str
    usage_terms: str
    artist: str
    credit: str
    attribution_required: str


def fetch_image_metadata(
    file_title: str,
    *,
    image_width: int,
    fixtures_dir: Path | None = None,
) -> CommonsImageMetadata:
    payload = _load_payload(
        file_title=file_title, image_width=image_width, fixtures_dir=fixtures_dir
    )
    pages = payload["query"]["pages"]
    page = next(iter(pages.values()))
    image_info = page["imageinfo"][0]
    metadata = image_info.get("extmetadata", {})

    return CommonsImageMetadata(
        file_title=file_title,
        download_url=image_info.get("thumburl", image_info["url"]),
        media_page_url=f"https://commons.wikimedia.org/wiki/{quote(file_title.replace(' ', '_'))}",
        license_short_name=_extract_metadata_value(metadata, "LicenseShortName"),
        license_url=_extract_metadata_value(metadata, "LicenseUrl"),
        usage_terms=_extract_metadata_value(metadata, "UsageTerms"),
        artist=_extract_metadata_value(metadata, "Artist"),
        credit=_extract_metadata_value(metadata, "Credit"),
        attribution_required=_extract_metadata_value(metadata, "AttributionRequired"),
    )


def is_commercially_usable(metadata: CommonsImageMetadata) -> bool:
    joined = " ".join(
        [
            metadata.license_short_name,
            metadata.usage_terms,
            metadata.license_url,
        ]
    ).lower()

    if "noncommercial" in joined or "by-nc" in joined or "cc-nc" in joined:
        return False

    return any(
        token in joined
        for token in (
            "public domain",
            "no known restrictions",
            "no restrictions",
            "cc by",
            "cc-by",
            "cc0",
            "gfdl",
            "/licenses/by",
        )
    )


def download_image(
    file_title: str,
    *,
    download_url: str,
    destination: Path,
    fixtures_dir: Path | None = None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    if fixtures_dir is not None:
        fixture_path = fixtures_dir / "binary" / quote(file_title, safe="")
        shutil.copyfile(fixture_path, destination)
        return

    request = Request(download_url, headers={"User-Agent": USER_AGENT})

    try:
        with urlopen(request, timeout=90) as response, destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise RuntimeError(
            f"Image download failed for {file_title}: {error}"
        ) from error


def _load_payload(
    file_title: str, image_width: int, fixtures_dir: Path | None
) -> dict[str, Any]:
    if fixtures_dir is not None:
        fixture_path = fixtures_dir / "commons" / f"{quote(file_title, safe='')}.json"

        with fixture_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    params = (
        f"action=query&titles={quote(file_title)}&prop=imageinfo&iiprop=url|extmetadata"
        f"&iiurlwidth={image_width}&format=json"
    )
    request = Request(
        f"{COMMONS_API_ENDPOINT}?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=90) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(
            f"Commons metadata fetch failed for {file_title}: {error}"
        ) from error


def _extract_metadata_value(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key, {})

    if not isinstance(value, dict):
        return ""

    return str(value.get("value", ""))
