from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REFERENCE_DATA_DIR: Final[Path] = (
    Path(__file__).resolve().parents[2] / "data" / "reference"
)
SUPPORTED_GENDERS: Final[tuple[str, ...]] = ("male", "female")
DIRECT_SEARCH_GENDER_TERMS: Final[dict[str, tuple[str, ...]]] = {
    "female": ("portrait woman", "woman"),
    "male": ("portrait man", "man"),
}
COUNTRY_QUERY_VARIANTS: Final[dict[str, tuple[str, ...]]] = {
    "Argentina": ("Argentina", "Argentine"),
    "Australia": ("Australia", "Australian"),
    "Austria": ("Austria", "Austrian"),
    "Belgium": ("Belgium", "Belgian"),
    "Brazil": ("Brazil", "Brazilian"),
    "Canada": ("Canada", "Canadian"),
    "China": ("China", "Chinese"),
    "Czech Republic": ("Czech Republic", "Czech"),
    "Egypt": ("Egypt", "Egyptian"),
    "France": ("France", "French"),
    "Germany": ("Germany", "German"),
    "Greece": ("Greece", "Greek"),
    "Hungary": ("Hungary", "Hungarian"),
    "India": ("India", "Indian"),
    "Indonesia": ("Indonesia", "Indonesian"),
    "Ireland": ("Ireland", "Irish"),
    "Italy": ("Italy", "Italian"),
    "Japan": ("Japan", "Japanese"),
    "Mexico": ("Mexico", "Mexican"),
    "Netherlands": ("Netherlands", "Dutch"),
    "Poland": ("Poland", "Polish"),
    "Romania": ("Romania", "Romanian"),
    "Russia": ("Russia", "Russian"),
    "Singapore": ("Singapore", "Singaporean"),
    "South Africa": ("South Africa", "South African"),
    "South Korea": ("South Korea", "Korean"),
    "Spain": ("Spain", "Spanish"),
    "Taiwan": ("Taiwan", "Taiwanese"),
    "Turkey": ("Turkey", "Turkish"),
    "United Kingdom": ("United Kingdom", "British"),
    "United States": ("United States", "American"),
    "Israel": ("Israel", "Israeli"),
}


@dataclass(frozen=True)
class EraDefinition:
    era_name: str
    birth_year_band: str
    birth_year_start: int
    birth_year_end: int


@dataclass(frozen=True)
class CountryTarget:
    country_code: str
    country_name: str
    wikidata_qid: str


def default_era_file() -> Path:
    return REFERENCE_DATA_DIR / "era_definitions.csv"


def default_country_file() -> Path:
    return REFERENCE_DATA_DIR / "nationality_targets.csv"


def load_era_definitions(path: Path | None = None) -> list[EraDefinition]:
    csv_path = path or default_era_file()

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            EraDefinition(
                era_name=row["era_name"],
                birth_year_band=row["birth_year_band"],
                birth_year_start=int(row["birth_year_start"]),
                birth_year_end=int(row["birth_year_end"]),
            )
            for row in reader
        ]


def load_country_targets(path: Path | None = None) -> list[CountryTarget]:
    csv_path = path or default_country_file()

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            CountryTarget(
                country_code=row["country_code"],
                country_name=row["country_name"],
                wikidata_qid=row["wikidata_qid"],
            )
            for row in reader
        ]


def assign_era(birth_year: int, eras: list[EraDefinition]) -> EraDefinition | None:
    for era in eras:
        if era.birth_year_start <= birth_year <= era.birth_year_end:
            return era

    return None


def normalize_gender(gender_label: str) -> str | None:
    normalized = gender_label.strip().lower()

    if normalized in {"male", "man"}:
        return "male"
    if normalized in {"female", "woman"}:
        return "female"

    return None


def slugify(value: str) -> str:
    ascii_only = value.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()

    return normalized or "item"


def country_query_variants(country_name: str) -> tuple[str, ...]:
    variants = COUNTRY_QUERY_VARIANTS.get(country_name)
    if variants is None:
        return (country_name,)
    return variants
