from __future__ import annotations

import json
from pathlib import Path

from portrait_collection.axes import CountryTarget, EraDefinition
from portrait_collection.cma import search_portraits_for_combo


class TestCmaSearch:
    def test_正常系_CC0かつ文化圏一致の候補を取得できる(self, tmp_path: Path) -> None:
        fixtures_dir = tmp_path
        (fixtures_dir / "cma").mkdir()

        (fixtures_dir / "cma" / "japan_female_japanese_portrait-woman.json").write_text(
            json.dumps(
                {
                    "data": [
                        {
                            "id": 20,
                            "title": "Portrait of a Woman",
                            "creation_date_earliest": 1790,
                            "creation_date_latest": 1795,
                            "share_license_status": "CC0",
                            "culture": ["Japan, Edo period"],
                            "description": "A portrait of a woman.",
                            "tombstone": "Japanese print",
                            "url": "https://clevelandart.org/art/20",
                            "images": {
                                "web": {
                                    "url": "https://openaccess-cdn.clevelandart.org/20.jpg"
                                }
                            },
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        outcome = search_portraits_for_combo(
            CountryTarget("japan", "Japan", "Q17"),
            EraDefinition("近世後期", "1750–1799", 1750, 1799),
            "female",
            limit=1,
            fixtures_dir=fixtures_dir,
        )

        assert outcome.errors == []
        assert len(outcome.assets) == 1
        assert outcome.assets[0].asset_id == "20"
        assert outcome.assets[0].metadata.download_url.endswith("/20.jpg")
