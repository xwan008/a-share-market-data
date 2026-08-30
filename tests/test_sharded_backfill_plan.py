from scripts.sharded_backfill_plan import codes_for_partition, partition_shard_keys


def test_partition_owns_physical_shards_without_overlap():
    codes = ["600001", "600002", "600101", "601000", "000001", "000002", "002001"]
    parts = partition_shard_keys(codes, 3)
    flattened = [key for part in parts for key in part]
    assert sorted(flattened) == sorted(set(flattened))
    assert len(flattened) == len(set(flattened))


def test_codes_from_same_physical_shard_stay_together():
    codes = ["600001", "600002", "600101", "601000", "000001", "000002"]
    owners = {}
    for idx in range(4):
        selected, keys = codes_for_partition(codes, idx, 4)
        for code in selected:
            owners[code] = idx
        assert all(code[:4] in keys for code in selected)
    assert owners["600001"] == owners["600002"]
    assert owners["000001"] == owners["000002"]
