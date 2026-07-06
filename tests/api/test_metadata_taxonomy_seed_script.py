from tests.api.init_scripts_import import load_script_module


def _seed_script_source() -> str:
    module = load_script_module("06_neo4j_seed.py")
    return module.__loader__.get_source(module.__name__)


def test_neo4j_init_contains_taxonomy_constraints():
    module = load_script_module("05_neo4j_init.py")
    statements = "\n".join(module.CONSTRAINTS + module.INDEXES)
    assert "MetaCategory" in statements
    assert "MetaTagGroup" in statements
    assert "MetaTag" in statements
    assert "category_code_unique" in statements
    assert "tag_code_unique" in statements
    assert "category_name_idx" in statements
    assert "category_level_idx" in statements
    assert "category_sort_idx" in statements
    assert "tag_name_idx" in statements
    assert "tag_sort_idx" in statements
    assert "change_target_type_idx" in statements
    assert "change_target_id_idx" in statements


def test_seed_script_has_taxonomy_seed_function():
    module = load_script_module("06_neo4j_seed.py")
    assert hasattr(module, "seed_taxonomy")
    assert hasattr(module, "seed_table_classification")


def test_table_classification_matches_taxonomy_by_code():
    source = _seed_script_source()
    assert 'classification["category_code"]' in source
    assert 'classification["tag_codes"]' in source
    assert 'code=tag["code"]' in source
    assert 'id=_tag_id(tag["code"])' in source
    assert "MetaCategory {code: $category_code}" in source
    assert "MetaTag {code: $tag_code}" in source
    assert "_category_path_code_map" not in source
    assert "_tag_name_code_map" not in source
    assert '_tag_code(tag["name"])' not in source
    assert 'replace(" ", "-")' not in source
    assert "MetaCategory {name: $root_name}" not in source
    assert "MetaCategory {name: $child_name}" not in source
    assert "MetaTag {name: $tag_name}" not in source
