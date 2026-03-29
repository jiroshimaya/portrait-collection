from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .axes import slugify
from .commons import CommonsImageMetadata

MET_OBJECT_ENDPOINT: Final[str] = (
    "https://collectionapi.metmuseum.org/public/collection/v1/objects"
)
MET_SEARCH_ENDPOINT: Final[str] = (
    "https://collectionapi.metmuseum.org/public/collection/v1/search"
)
USER_AGENT: Final[str] = (
    "portrait-collection/0.1 (https://github.com/jiroshimaya/portrait-collection)"
)


@dataclass(frozen=True)
class MetObject:
    object_id: int
    title: str
    primary_image_small: str
    object_url: str
    artist_display_name: str
    credit_line: str

    def to_metadata(self) -> CommonsImageMetadata:
        safe_title = slugify(self.title) or f"object-{self.object_id}"
        return CommonsImageMetadata(
            file_title=f"MetObject:{self.object_id}_{safe_title}.jpg",
            download_url=self.primary_image_small,
            media_page_url=self.object_url,
            license_short_name="CC0 / Public Domain",
            license_url="https://creativecommons.org/publicdomain/zero/1.0/",
            usage_terms="The Met Open Access",
            artist=self.artist_display_name,
            credit=self.credit_line,
            attribution_required="false",
        )


def search_portraits_for_person(
    person_name: str,
    *,
    limit: int,
    fixtures_dir: Path | None = None,
) -> list[CommonsImageMetadata]:
    object_ids = _search_object_ids(
        person_name, limit=limit * 4, fixtures_dir=fixtures_dir
    )
    results: list[CommonsImageMetadata] = []

    for object_id in object_ids:
        met_object = _load_object(object_id, fixtures_dir=fixtures_dir)
        if met_object is None:
            continue
        results.append(met_object.to_metadata())
        if len(results) >= limit:
            break

    return results


def _search_object_ids(
    person_name: str,
    *,
    limit: int,
    fixtures_dir: Path | None,
) -> list[int]:
    if fixtures_dir is not None:
        fixture_path = fixtures_dir / "met_search" / f"{slugify(person_name)}.json"
        with fixture_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return list(payload.get("objectIDs", []))[:limit]

    queries = [person_name]
    parts = person_name.split()
    if len(parts) > 1:
        queries.append(parts[-1])

    object_ids: list[int] = []
    seen: set[int] = set()
    for query in queries:
        payload = _fetch_json(
            f"{MET_SEARCH_ENDPOINT}?hasImages=true&title=true&q={quote(query)}",
            context=f"Met search failed for {person_name}",
        )
        for object_id in payload.get("objectIDs") or []:
            if object_id in seen:
                continue
            seen.add(object_id)
            object_ids.append(int(object_id))
            if len(object_ids) >= limit:
                return object_ids

    return object_ids


def _load_object(object_id: int, *, fixtures_dir: Path | None) -> MetObject | None:
    if fixtures_dir is not None:
        fixture_path = fixtures_dir / "met_objects" / f"{object_id}.json"
        with fixture_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        payload = _fetch_json(
            f"{MET_OBJECT_ENDPOINT}/{object_id}",
            context=f"Met object fetch failed for {object_id}",
        )

    if not payload.get("isPublicDomain"):
        return None
    if not payload.get("primaryImageSmall"):
        return None

    return MetObject(
        object_id=int(payload["objectID"]),
        title=str(payload.get("title", f"Object {object_id}")),
        primary_image_small=str(payload["primaryImageSmall"]),
        object_url=str(payload.get("objectURL", "")),
        artist_display_name=str(payload.get("artistDisplayName", "")),
        credit_line=str(payload.get("creditLine", "")),
    )


def _fetch_json(url: str, *, context: str) -> dict[str, Any]:
    request = Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(f"{context}: {error}") from error
