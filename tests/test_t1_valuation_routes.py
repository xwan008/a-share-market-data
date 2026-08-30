import importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path); mod=importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(mod); return mod

fund=load_module('fund_t1_routes','scripts/build_forward_valuation.py')

def test_all_noncycle_t1_tags_map_to_versioned_business_policy():
    cfg=json.loads((ROOT/'config/valuation_policy_registry.json').read_text(encoding='utf-8'))
    expected={
        'automotive::乘用车':'passenger_car',
        'automotive::商用车动力系统':'commercial_powertrain',
        'computer::数据中心基础设施':'data_center_infrastructure',
        'defense::航空主机':'aviation_oem',
        'electronics::半导体材料':'semiconductor_materials',
        'electronics::半导体设备':'semiconductor_equipment',
        'electronics::高速连接器/铜互连':'high_speed_connector',
        'machinery::工程机械':'construction_machinery',
        'machinery::船机动力':'marine_power',
        'pharma::创新药':'innovative_drug',
        'power_equipment::锂电池':'lithium_battery',
        'power_equipment::风电整机/零部件':'wind_equipment',
        'textile_apparel::纺织制造':'textile_manufacturing',
        'utilities::核电':'nuclear_utility',
    }
    for tag,key in expected.items():
        policy,actual=fund.business_policy([tag],cfg)
        assert actual==key
        assert policy==cfg['business_policies'][key]
        assert len(policy['multiple_range'])==2


def test_all_cycle_t1_tags_are_routed_out_of_generic_pe():
    policy=json.loads((ROOT/'config/cycle_valuation_policy.json').read_text(encoding='utf-8'))
    expected={
        'building_materials::玻纤','chemicals::磷化工','chemicals::聚氨酯/MDI/TDI','coal::焦煤',
        'nonferrous::锂资源/锂盐','nonferrous::黄金','oil_gas::油气开采'
    }
    assert expected<=set(policy['subchain_policies'])


def test_precision_sensitive_t1_chains_do_not_use_broad_hierarchy_shortcuts():
    cfg=json.loads((ROOT/'config/t2_exposure_rules.json').read_text(encoding='utf-8'))
    rules={(r['broad_industry_id'],r['subchain']):r for r in cfg['chains']}
    aviation=rules[('defense','航空主机')]
    engineering=rules[('machinery','工程机械')]
    assert aviation['hierarchy_keywords']==[]
    assert engineering['hierarchy_keywords']==[]
    assert '002297' not in aviation['explicit_exposed']  # 博云新材是上游材料/制动系统，不是整机总装
    assert '002685' not in engineering['explicit_exposed']  # 华东重机核心为港机，不是挖掘机/起重机/装载机整机链
