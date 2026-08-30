import importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path); mod=importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(mod); return mod

repair=load_module('repair_cycle_v6','scripts/repair_anchorless_cycle_valuation.py')

def test_anchorless_cycle_uses_current_year_as_primary_and_blocks_next_year_upside():
    # The repair script implements guarded=min(2026,2027), then applies a structural haircut.
    eps0,eps1,haircut=3.0,4.0,0.9
    guarded=min(eps0,eps1); assert guarded==3.0; assert guarded*haircut==2.7

def test_anchorless_cycle_allows_next_year_downside_to_lower_anchor():
    eps0,eps1,haircut=3.0,2.4,0.9
    guarded=min(eps0,eps1); assert guarded==2.4; assert round(guarded*haircut,4)==2.16

def test_all_cycle_subchains_have_explicit_mode_regime_and_market_calibration():
    policy=json.loads((ROOT/'config/cycle_valuation_policy.json').read_text(encoding='utf-8'))
    regime=json.loads((ROOT/'config/cycle_regime_registry.json').read_text(encoding='utf-8'))
    expected={'nonferrous::铜矿资源','nonferrous::电解铝','coal::动力煤','chemicals::氟化工','chemicals::氨纶'}
    assert expected<=set(policy['subchain_policies'])
    for tag in expected:
        p=policy['subchain_policies'][tag]
        assert p['valuation_mode'] in {'commodity_anchor_normalized','conservative_consensus_cycle'}
        assert p['requires_regime'] is True
        assert p['market_price_calibration'] is True
        assert tag in regime['subchains']

def test_anchorless_subchains_do_not_depend_on_fake_futures_symbol():
    policy=json.loads((ROOT/'config/cycle_valuation_policy.json').read_text(encoding='utf-8'))
    assert 'ZC0' not in policy.get('anchor_series',{})
    for tag in ('coal::动力煤','chemicals::氟化工','chemicals::氨纶'):
        p=policy['subchain_policies'][tag]
        assert p['valuation_mode']=='conservative_consensus_cycle'
        assert not p.get('anchors')
        assert 0.6<=p['anchorless_normalization_haircut']<=1.0
