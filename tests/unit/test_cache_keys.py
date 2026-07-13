from demo_command_center.cache.keys.policy import CacheKeyPolicy


def test_cache_key_hashes_opaque_identifier() -> None:
    policy = CacheKeyPolicy(environment="test", tenant_id="nxtutors")
    key = policy.build("conversation", "sensitive-reference")
    assert "sensitive-reference" not in key
    assert key.startswith("dcc:test:nxtutors:v1:conversation:")
