from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_runtime_builders_are_absent():
    assert not (ROOT / "scripts/build_v2_full_market_price_structure.py").exists()
    assert not (ROOT / "scripts/migrate_level3_industry_state.py").exists()


def test_production_builders_have_no_legacy_imports():
    for path in (
        ROOT / "scripts/build_full_market_price_structure.py",
        ROOT / "scripts/build_bridge.py",
    ):
        text = path.read_text(encoding="utf-8")
        assert "build_v2_full_market_price_structure" not in text
        assert "data/research/v2" not in text
        assert "shadow" not in text


def test_workflows_have_no_legacy_runtime_dependencies():
    update_market = (ROOT / ".github/workflows/update-market.yml").read_text(encoding="utf-8")
    research_ci = (ROOT / ".github/workflows/research-contract-ci.yml").read_text(encoding="utf-8")
    for text in (update_market, research_ci):
        assert "build_v2_full_market_price_structure.py" not in text
        assert "migrate_level3_industry_state.py" not in text


def test_market_data_workflow_cannot_persist_on_code_push():
    text = (ROOT / ".github/workflows/update-market.yml").read_text(encoding="utf-8")
    trigger_block = text.split("permissions:", 1)[0]
    assert "push:" not in trigger_block
    assert "steps.session.outputs.persist == 'true'" in text
    assert "status == 'closed'" in text


def test_market_data_workflow_dispatches_locked_runtime_snapshot_after_data_push():
    update = (ROOT / ".github/workflows/update-market.yml").read_text(encoding="utf-8")
    snapshot = (ROOT / ".github/workflows/runtime-snapshot.yml").read_text(encoding="utf-8")
    helper = (ROOT / "scripts/dispatch_workflow_and_wait.sh").read_text(encoding="utf-8")

    assert "bash scripts/dispatch_workflow_and_wait.sh runtime-snapshot.yml main" in update
    assert "if: steps.commit.outputs.pushed == 'true'" in update
    assert "gh workflow run" in helper
    assert "headSha" in helper
    assert "createdAt" in helper
    assert "actions/upload-artifact@v4" in snapshot
    assert "name: a-share-runtime-snapshot" in snapshot
    assert "runtime_snapshot_manifest.json" in snapshot
    assert "['git', 'rev-parse', 'HEAD']" in snapshot


def test_downstream_publication_is_event_driven_and_cron_is_root_only():
    market = (ROOT / ".github/workflows/update-market.yml").read_text(encoding="utf-8")
    backfill = (ROOT / ".github/workflows/backfill-history.yml").read_text(encoding="utf-8")
    industry = (ROOT / ".github/workflows/build-company-industry-index.yml").read_text(encoding="utf-8")
    snapshot = (ROOT / ".github/workflows/runtime-snapshot.yml").read_text(encoding="utf-8")
    evidence = (ROOT / ".github/workflows/update-industry-evidence.yml").read_text(encoding="utf-8")
    bundle = (ROOT / ".github/workflows/production-bundle.yml").read_text(encoding="utf-8")

    assert sum(text.count("- cron:") for text in (market, backfill, industry)) == 4
    for text in (snapshot, evidence, bundle):
        trigger_block = text.split("permissions:", 1)[0]
        assert "schedule:" not in trigger_block

    snapshot_trigger = snapshot.split("permissions:", 1)[0]
    assert "workflow_dispatch:" in snapshot_trigger
    assert "push:" not in snapshot_trigger
    assert "bash scripts/dispatch_workflow_and_wait.sh update-industry-evidence.yml main" in snapshot
    assert "bash scripts/dispatch_workflow_and_wait.sh production-bundle.yml main" in evidence


def test_industry_evidence_refresh_is_schema_and_anchor_aware():
    workflow = (ROOT / ".github/workflows/update-industry-evidence.yml").read_text(encoding="utf-8")
    builder = (ROOT / "scripts/build_industry_evidence.py").read_text(encoding="utf-8")
    assert "EXPECTED_EVIDENCE_SCHEMA_VERSION = 3" in workflow
    assert "current.get('schema_version') == EXPECTED_EVIDENCE_SCHEMA_VERSION" in workflow
    assert "source_leading_anchor_generated_at" in workflow
    assert "python scripts/fetch_industry_leading_anchors.py" in workflow
    assert '"schema_version": 3' in builder
    assert "industry_leading_anchors.json" in builder


def test_leading_anchor_matrix_accounts_for_all_level1_and_forbids_market_price_proxy():
    import json

    matrix = json.loads((ROOT / "config/industry_leading_anchor_sources.json").read_text(encoding="utf-8"))
    universe = json.loads((ROOT / "config/industry_scan_universe.json").read_text(encoding="utf-8"))
    level1_codes = {row["code"] for row in universe["levels"]["level1"]}
    assert matrix["required_level1_count"] == 31
    assert set(matrix["industries"]) == level1_codes
    assert matrix["rules"]["stock_or_industry_index_price_forbidden"] is True
    forbidden = {"stock_price", "industry_index_price", "industry_kline", "stock_kline"}
    for code, row in matrix["industries"].items():
        assert row["candidates"], code
        assert not ({candidate.get("type") for candidate in row["candidates"]} & forbidden), code


def test_production_bundle_carries_leading_anchor_contract_and_payload():
    bundle = (ROOT / ".github/workflows/production-bundle.yml").read_text(encoding="utf-8")
    assert "config/industry_leading_anchor_sources.json" in bundle
    assert "data/research/industry_leading_anchors.json" in bundle
    assert "scripts/fetch_industry_leading_anchors.py" in bundle
    assert "leading_anchor_complete" in bundle


def test_research_directory_has_only_authoritative_runtime_files_and_readme():
    research_dir = ROOT / "data/research"
    names = {p.name for p in research_dir.iterdir()}
    allowed = {
        "README.md",
        "company_industry_index.json",
        "full_market_price_structure.json",
        "industry_state.json",
        "industry_leading_anchors.json",
        "industry_evidence.json",
        "evidence_gate.json",
    }
    assert names <= allowed
    assert {
        "README.md",
        "company_industry_index.json",
        "full_market_price_structure.json",
        "industry_state.json",
    } <= names


def test_root_readme_declares_no_persisted_formal_run_state():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "only cross-run fundamental research memory" in text
    assert "research_state.json" in text
    assert "forbidden" in text
    assert "are generated fresh on every run and are not persisted" in text


def test_runtime_is_manifest_whitelisted():
    import json

    runtime = json.loads((ROOT / "config/research_runtime_policy.json").read_text(encoding="utf-8"))
    policy = runtime["repository_data_policy"]
    assert policy["allow_only_manifest_authoritative_data"] is True
    assert policy["do_not_scan_repository_for_extra_research_json"] is True
    assert policy["git_history_is_audit_only_not_runtime_input"] is True
