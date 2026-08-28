from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_bootstrap_never_copies_example_rows():
    text=(ROOT/'scripts/bootstrap_config.py').read_text(encoding='utf-8')
    assert 'target.write_text("{}\\n"' in text
    assert 'target.write_text(lines[0].rstrip()+"\\n"' in text
    assert 'read_text(encoding="utf-8").splitlines()' in text


def test_bundle_explicitly_syncs_gitignored_tenant_config():
    bundle=(ROOT/'databricks.yml').read_text(encoding='utf-8')
    assert 'config/**' in bundle
    ignore=(ROOT/'.gitignore').read_text(encoding='utf-8')
    assert 'config/industrial_instrument_history.csv' in ignore
    assert 'config/pay_category_mapping.json' in ignore


def test_config_sync_helpers_exist_for_bash_and_powershell():
    assert (ROOT/'scripts/sync_config.sh').exists()
    assert (ROOT/'scripts/sync_config.ps1').exists()
