from __future__ import annotations

from portrait_collection.axes import EraDefinition, assign_era, normalize_gender, slugify


class TestAssignEra:
    def test_正常系_birth_yearから一致する時代区分を返す(self) -> None:
        eras = [
            EraDefinition("古代前期", "紀元前400–紀元前1", -400, -1),
            EraDefinition("近代後期", "1850–1899", 1850, 1899),
        ]

        result = assign_era(1867, eras)

        assert result == eras[1]


class TestNormalizeGender:
    def test_正常系_wikidataラベルをmale_femaleに正規化する(self) -> None:
        assert normalize_gender("male") == "male"
        assert normalize_gender("female") == "female"


class TestSlugify:
    def test_正常系_ファイル名向けにasciiスラッグ化する(self) -> None:
        assert slugify("Albert Einstein Portrait 01") == "albert-einstein-portrait-01"
