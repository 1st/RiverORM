from typing import ClassVar

import pytest

from riverorm.models import Model


def make_model_class(name, table_name=None) -> type[Model]:
    meta_attrs = {}
    if table_name is not None:
        meta_attrs["table_name"] = table_name
    Meta = type("Meta", (), meta_attrs)
    attrs = {"Meta": Meta, "__module__": __name__, "__annotations__": {"Meta": ClassVar[type]}}
    return type(name, (Model,), attrs)


class TestTableName:
    @pytest.mark.parametrize(
        "class_name, expected",
        [
            ("NDA", "nda"),
            ("UserNDA", "user_nda"),
            ("UserNDAContract", "user_nda_contract"),
            ("UserConfig", "user_config"),
            ("User", "user"),
        ],
    )
    def test_table_name_examples(self, class_name, expected):
        cls = make_model_class(class_name)
        assert cls.table_name() == expected, f"{class_name} -> {cls.table_name()} != {expected}"


class TestTableNameEdgeCases:
    """
    Test various edge cases for table name generation
    """

    @pytest.mark.parametrize(
        "class_name, expected",
        [
            ("UserA", "user_a"),
            ("UserAContract", "user_a_contract"),
            ("userNDA", "user_nda"),
            ("UserNDAXML", "user_ndaxml"),
            ("UserNDAXMLContract", "user_ndaxml_contract"),
            ("UserNDA2", "user_nda2"),
            ("UserN2DA", "user_n2da"),
            ("UserNDA2FA", "user_nda2fa"),
            ("User2FA", "user_2fa"),
            ("NDAUser", "nda_user"),
            ("NDAXML", "ndaxml"),
            ("XMLUserNDA", "xml_user_nda"),
            ("user", "user"),
            ("User_NDA", "user_nda"),
            ("User__NDA", "user__nda"),  # double underscore preserved
            ("User2Company", "user_2_company"),
        ],
    )
    def test_table_name_edge_cases(self, class_name, expected):
        cls = make_model_class(class_name)
        assert cls.table_name() == expected, f"{class_name} -> {cls.table_name()} != {expected}"

    @pytest.mark.parametrize(
        "class_name, table_name, expected",
        [
            ("UserNDA", "custom_table", "custom_table"),
            ("UserNDA", "", "user_nda"),  # empty string falls back to auto
            ("UserNDA", None, "user_nda"),  # None falls back to auto
        ],
    )
    def test_table_name_manual_override(self, class_name, table_name, expected):
        # Manual override
        cls = make_model_class(class_name, table_name=table_name)
        assert cls.table_name() == expected
