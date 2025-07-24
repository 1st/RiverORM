# Helper to create dummy classes with given name and optional Meta.table_name
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
def test_table_name_edge_cases(class_name, expected):
    cls = make_model_class(class_name)
    assert cls.table_name() == expected, f"{class_name} -> {cls.table_name()} != {expected}"


def test_table_name_manual_override():
    # Manual override
    cls = make_model_class("UserNDA", table_name="custom_table")
    assert cls.table_name() == "custom_table"
    # Manual override with empty string falls back to auto
    cls2 = make_model_class("UserNDA", table_name="")
    assert cls2.table_name() == "user_nda"
    # Manual override with None falls back to auto
    cls3 = make_model_class("UserNDA", table_name=None)
    assert cls3.table_name() == "user_nda"
