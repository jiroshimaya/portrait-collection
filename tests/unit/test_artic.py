from __future__ import annotations

import json
from pathlib import Path

from portrait_collection.artic import search_portraits_for_combo
from portrait_collection.axes import CountryTarget, EraDefinition


class TestArticSearch:
    def test_正常系_公開ドメインかつ国名一致の候補を取得できる(
        self, tmp_path: Path
    ) -> None:
        fixtures_dir = tmp_path
        (fixtures_dir / "artic").mkdir()

        (
            fixtures_dir / "artic" / "japan_female_japanese_portrait-woman.json"
        ).write_text(
            json.dumps(
                {
                    "data": [
                        {
                            "id": 10,
                            "title": "Portrait of a Japanese Woman",
                            "date_start": 1880,
                            "date_end": 1880,
                            "image_id": "image-10",
                            "is_public_domain": True,
                            "artist_display": "Japanese artist",
                            "place_of_origin": "Japan",
                        }
                    ],
                    "config": {
                        "website_url": "https://www.artic.edu",
                        "iiif_url": "https://www.artic.edu/iiif/2",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        outcome = search_portraits_for_combo(
            CountryTarget("japan", "Japan", "Q17"),
            EraDefinition("近代後期", "1850–1899", 1850, 1899),
            "female",
            limit=1,
            fixtures_dir=fixtures_dir,
        )

        assert outcome.errors == []
        assert len(outcome.assets) == 1
        assert outcome.assets[0].asset_id == "10"
        assert outcome.assets[0].metadata.download_url.endswith(
            "/image-10/full/843,/0/default.jpg"
        )
