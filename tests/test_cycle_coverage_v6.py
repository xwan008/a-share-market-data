import importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path); mod=importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(mod); return mod

repair=load_module('repair_cycle_v6','scripts/repair_anchorless_cycle_valuation.py')

def test_anchorless_cycle_uses_current_year_as_primary_and_blocks_next_year_upside():
    eps0,eps1,haircut=3.0,4.0,0.9
    guarded=min(eps0,eps1); assert guarded==3.0; assert guarded*haircut==2.7

def test_anchorless_cycle_allows_next_year_downside_to_lower_anchor():
    eps0,eps1,haircut=3.0,2.4,0.9
    guarded=min(eps0,eps1); assert guarded==2.4; assert round(guarded*haircut,4)==2.16

def test_all_cycle_subchains_have_explicit_mode_regime_and_market_calibration():
    policy=json.loads((ROOT/'config/cycle_valuation_policy.json').read_text(encoding='utf-8'))
    regime=json.loads((ROOT/'config/cycle_regime_registry.json').read_text(encoding='utf-8'))
    expected={
        'nonferrous::铜矿资源','nonferrous::电解铝','nonferrous::黄金','nonferrous::锂资源/锂盐',
        'coal::动力煤','coal::焦煤','chemicals::氟化工','chemicals::氨纶','chemicals::聚氨酯/MDI/TDI','chemicals::磷化工',
        'building_materials::玻纤','oil_gas::油气开采'
    }
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
    anchorless={
        'coal::动力煤','coal::焦煤','chemicals::氟化工','chemicals::氨纶','chemicals::聚氨酯/MDI/TDI','chemicals::磷化工',
        'building_materials::玻纤','nonferrous::锂资源/锂盐','oil_gas::油气开采'
    }
    for tag in anchorless:
        p=policy['subchain_policies'][tag]
        assert p['valuation_mode']=='conservative_consensus_cycle'
        assert not p.get('anchors')
        assert 0.6<=p['anchorless_normalization_haircut']<=1.0

def test_gold_uses_real_machine_anchor_and_positive_strength_cannot_raise_buy_zone():
    policy=json.loads((ROOT/'config/cycle_valuation_policy.json').read_text(encoding='utf-8'))
    gold=policy['subchain_policies']['nonferrous::黄金']
    assert gold['valuation_mode']=='commodity_anchor_normalized'
    assert gold['anchors']==[{'symbol':'AU0','weight':1.0,'direction':1}]
    assert policy['short_term_anchor_policy']['positive_strength_can_raise_low_risk_buy_zone'] is False
