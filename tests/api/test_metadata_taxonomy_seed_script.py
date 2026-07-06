from tests.api.init_scripts_import import load_script_module


def test_neo4j_init_contains_taxonomy_constraints():
    module = load_script_module("05_neo4j_init.py")
    statements = "\n".join(module.CONSTRAINTS + module.INDEXES)
    assert "MetaCategory" in statements
    assert "MetaTagGroup" in statements
    assert "MetaTag" in statements
    assert "category_code_unique" in statements
    assert "tag_code_unique" in statements


def test_seed_script_has_taxonomy_seed_function():
    module = load_script_module("06_neo4j_seed.py")
    assert hasattr(module, "seed_taxonomy")
    assert hasattr(module, "seed_table_classification")
