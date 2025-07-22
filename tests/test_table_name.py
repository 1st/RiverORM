from riverorm.models import Model


# Helper to create dummy classes with given name
def make_model_class(name):
    return type(name, (Model,), {})


def test_table_name_examples():
    cases = [
        ("NDA", "nda"),
        ("UserNDA", "user_nda"),
        ("UserNDAContract", "user_nda_contract"),
        ("UserConfig", "user_config"),
        ("User", "user"),
    ]
    for class_name, expected in cases:
        cls = make_model_class(class_name)
        assert cls.table_name() == expected, f"{class_name} -> {cls.table_name()} != {expected}"
