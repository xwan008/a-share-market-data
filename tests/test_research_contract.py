import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def manifest():
    return json.loads((ROOT/'config/research_pipeline_manifest.json').read_text(encoding='utf-8'))

def test_manifest_schema25_and_stage_order():
    m=manifest()
    assert m['schema_version']==25 and m['mode']=='shadow'
    assert m['stage_order']==['data_health','taxonomy_coverage','market_profitability_discovery','profit_chain_decomposition','chain_company_comparison','valuation','price_structure','completion_gate_and_opportunity_synthesis']
    assert m['coverage_contract']['expected_counts']=={'level1':31,'level2':134,'level3':346}

def test_public_evidence_is_required_but_not_persisted_as_pool():
    m=manifest(); e=m['evidence_contract']; p=m['persistence_contract']
    assert e['repository_whitelist_applies_only_to_persistent_mechanical_data'] is True
    assert e['current_public_research_evidence_allowed'] is True
    assert e['current_public_research_evidence_required_for_1800_full_research'] is True
    assert p['persistent_intermediate_research_outputs_allowed'] is False
    assert p['cross_run_candidate_or_opportunity_caches_allowed'] is False

def test_incomplete_fails_closed():
    s=manifest()['research_state_contract']
    assert s['manifest_schema_must_equal_current'] is True
    assert s['on_incomplete']=='incomplete_research'
    assert s['incomplete_must_not_publish_new_current_opportunities'] is True
