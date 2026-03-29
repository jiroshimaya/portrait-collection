from __future__ import annotations

import json
import re
from dataclasses import dataclass
from time import sleep
from pathlib import Path
from typing import Any, Final
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .axes import (
    DIRECT_SEARCH_GENDER_TERMS,
    CountryTarget,
    EraDefinition,
    country_query_variants,
    slugify,
)
from .commons import CommonsImageMetadata

LOC_SEARCH_ENDPOINT: Final[str] = "https://www.loc.gov/photos/"
USER_AGENT: Final[str] = (
    "portrait-collection/0.1 (https://github.com/jiroshimaya/portrait-collection)"
)
LOC_PAGE_SIZE: Final[int] = 100
LOC_MAX_PAGES_PER_QUERY: Final[int] = 3
LOC_RETRY_DELAYS: Final[tuple[int, ...]] = (1, 2, 4)

_LIVE_PAYLOAD_CACHE: dict[
    tuple[str, int], tuple[dict[str, Any] | None, str | None]
] = {}


@dataclass(frozen=True)
class LocPortraitAsset:
    asset_id: str
    title: str
    year: int
    source_url: str
    metadata: CommonsImageMetadata


@dataclass(frozen=True)
class LocSearchOutcome:
    assets: list[LocPortraitAsset]
    errors: list[str]


def search_portraits_for_combo(
    country: CountryTarget,
    era: EraDefinition,
    gender: str,
    *,
    limit: int,
    fixtures_dir: Path | None = None,
) -> LocSearchOutcome:
    results: list[LocPortraitAsset] = []
    seen_ids: set[str] = set()
    errors: list[str] = []

    for country_term in country_query_variants(country.country_name):
        for term in DIRECT_SEARCH_GENDER_TERMS[gender]:
            for page in range(1, LOC_MAX_PAGES_PER_QUERY + 1):
                payload, query_error = _load_payload(
                    country=country,
                    country_term=country_term,
                    era=era,
                    gender=gender,
                    term=term,
                    page=page,
                    fixtures_dir=fixtures_dir,
                )
                if query_error is not None:
                    errors.append(
                        "Library of Congress search failed for "
                        f"{country.country_name} / {era.era_name} / {gender} / "
                        f"{country_term} / {term} / page {page}: {query_error}"
                    )
                    break
                if payload is None:
                    break
                items = payload.get("results", [])
                if not isinstance(items, list) or not items:
                    break
                for item in items:
                    asset = _build_asset(item=item, era=era)
                    if asset is None or asset.asset_id in seen_ids:
                        continue
                    seen_ids.add(asset.asset_id)
                    results.append(asset)
                    if len(results) >= limit:
                        return LocSearchOutcome(assets=results, errors=errors)
                if len(items) < LOC_PAGE_SIZE:
                    break

    return LocSearchOutcome(assets=results, errors=errors)


def _load_payload(
    *,
    country: CountryTarget,
    country_term: str,
    era: EraDefinition,
    gender: str,
    term: str,
    page: int,
    fixtures_dir: Path | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if fixtures_dir is not None:
        fixture_path = _fixture_path(
            fixtures_dir=fixtures_dir,
            country=country,
            country_term=country_term,
            era=era,
            gender=gender,
            term=term,
            page=page,
        )
        if fixture_path is None or not fixture_path.exists():
            return {"results": []}, None
        with fixture_path.open("r", encoding="utf-8") as handle:
            return json.load(handle), None

    return _load_live_payload(country_term=country_term, term=term, page=page)


def _load_live_payload(
    *, country_term: str, term: str, page: int
) -> tuple[dict[str, Any] | None, str | None]:
    cache_key = (f"{country_term}\u0000{term}", page)
    if cache_key in _LIVE_PAYLOAD_CACHE:
        return _LIVE_PAYLOAD_CACHE[cache_key]

    query = quote(f"{country_term} {term}")
    url = f"{LOC_SEARCH_ENDPOINT}?fo=json&sp={page}&c={LOC_PAGE_SIZE}&q={query}"
    request = Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )

    for attempt, delay_seconds in enumerate(LOC_RETRY_DELAYS):
        if attempt > 0:
            sleep(delay_seconds)
        try:
            with urlopen(request, timeout=30) as response:
                result = (json.load(response), None)
                _LIVE_PAYLOAD_CACHE[cache_key] = result
                return result
        except HTTPError as error:
            if error.code == 429 and attempt < len(LOC_RETRY_DELAYS) - 1:
                continue
            result = (None, str(error))
            _LIVE_PAYLOAD_CACHE[cache_key] = result
            return result
        except (URLError, TimeoutError) as error:
            if attempt < len(LOC_RETRY_DELAYS) - 1:
                continue
            result = (None, str(error))
            _LIVE_PAYLOAD_CACHE[cache_key] = result
            return result

    result = (None, "Unknown error")
    _LIVE_PAYLOAD_CACHE[cache_key] = result
    return result


def _fixture_path(
    *,
    fixtures_dir: Path,
    country: CountryTarget,
    country_term: str,
    era: EraDefinition,
    gender: str,
    term: str,
    page: int,
) -> Path | None:
    loc_dir = fixtures_dir / "loc"
    if country_term == country.country_name and page == 1:
        legacy_path = loc_dir / (
            f"{country.country_code}_{era.birth_year_start}_{era.birth_year_end}_{gender}_{slugify(term)}.json"
        )
        if legacy_path.exists():
            return legacy_path

    suffix = "" if page == 1 else f"_p{page}"
    return loc_dir / (
        f"{country.country_code}_{era.birth_year_start}_{era.birth_year_end}_{gender}_"
        f"{slugify(country_term)}_{slugify(term)}{suffix}.json"
    )


def _build_asset(
    *, item: dict[str, Any], era: EraDefinition
) -> LocPortraitAsset | None:
    year = _extract_year(item)
    if year is None:
        return None
    if not (era.birth_year_start <= year <= era.birth_year_end):
        return None

    item_url = str(item.get("url", ""))
    if not item_url:
        return None

    image_url = _pick_download_url(item.get("image_url", []))
    if image_url is None:
        return None

    rights_advisory = str(item.get("rights_advisory") or "")
    if not _is_usable(rights_advisory=rights_advisory, year=year):
        return None

    asset_id = item_url.rstrip("/").rsplit("/", 1)[-1]
    title = str(item.get("title") or asset_id)

    return LocPortraitAsset(
        asset_id=asset_id,
        title=title,
        year=year,
        source_url=item_url,
        metadata=CommonsImageMetadata(
            file_title=f"LoC:{asset_id}_{slugify(title)}.jpg",
            download_url=image_url,
            media_page_url=item_url,
            license_short_name=_license_short_name(rights_advisory, year),
            license_url="https://www.loc.gov/",
            usage_terms=rights_advisory
            or "Library of Congress public-domain-age heuristic",
            artist="",
            credit=title,
            attribution_required="false",
        ),
    )


def _extract_year(item: dict[str, Any]) -> int | None:
    candidates = [item.get("date")]
    nested_item = item.get("item", {})
    if isinstance(nested_item, dict):
        candidates.append(nested_item.get("date"))
        candidates.append(nested_item.get("created_published_date"))

    for candidate in candidates:
        if not candidate:
            continue
        match = re.search(r"([+-]?\d{3,4})", str(candidate))
        if match is None:
            continue
        try:
            return int(match.group(1))
        except ValueError:
            continue

    return None


def _pick_download_url(image_urls: Any) -> str | None:
    if not isinstance(image_urls, list):
        return None

    jpg_urls = [str(url).split("#", 1)[0] for url in image_urls if ".jpg" in str(url)]
    if not jpg_urls:
        return None

    for preferred_suffix in ("v.jpg", "r.jpg", ".jpg"):
        for url in reversed(jpg_urls):
            if url.endswith(preferred_suffix):
                return url

    return jpg_urls[-1]


def _is_usable(*, rights_advisory: str, year: int) -> bool:
    lowered = rights_advisory.lower()
    if any(
        token in lowered for token in ("restricted", "copyright", "rights reserved")
    ):
        return False
    if any(
        token in lowered
        for token in ("public domain", "no known restrictions", "no restrictions")
    ):
        return True
    return year <= 1929


def _license_short_name(rights_advisory: str, year: int) -> str:
    if rights_advisory:
        return rights_advisory
    if year <= 1929:
        return "Public Domain (age heuristic)"
    return "Unknown"
