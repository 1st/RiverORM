import pytest

from riverorm.models import Model


# Helper to create dummy classes with given name
def make_model_class(name):
    return type(name, (Model,), {})


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
def test_table_name_examples(class_name, expected):
    cls = make_model_class(class_name)
    assert cls.table_name() == expected, f"{class_name} -> {cls.table_name()} != {expected}"
