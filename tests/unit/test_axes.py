from __future__ import annotations

from portrait_collection.axes import (
    DIRECT_SEARCH_GENDER_TERMS,
    EraDefinition,
    assign_era,
    country_query_variants,
    load_country_targets,
    load_era_definitions,
    normalize_gender,
    slugify,
)


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


class TestDirectSearchTerms:
    def test_正常系_国名の検索バリエーションを返す(self) -> None:
        assert country_query_variants("Japan") == ("Japan", "Japanese")
        assert country_query_variants("Unknownland") == ("Unknownland",)

    def test_正常系_gender別の直検索語を持つ(self) -> None:
        assert DIRECT_SEARCH_GENDER_TERMS["female"] == ("portrait woman", "woman")
        assert DIRECT_SEARCH_GENDER_TERMS["male"] == ("portrait man", "man")


class TestDefaultReferenceAxes:
    def test_正常系_既定era定義は参考元と同じ13区分を持つ(self) -> None:
        eras = load_era_definitions()

        assert len(eras) == 13
        assert eras[0] == EraDefinition("古代前期", "紀元前400–紀元前1", -400, -1)
        assert eras[-1] == EraDefinition("現代最年少", "2000–2009", 2000, 2009)

    def test_正常系_既定country定義は十分な国数を持つ(self) -> None:
        countries = load_country_targets()

        assert len(countries) >= 20
        assert countries[0].country_name == "Japan"
        assert any(country.country_name == "Egypt" for country in countries)
        assert any(country.country_name == "Singapore" for country in countries)
