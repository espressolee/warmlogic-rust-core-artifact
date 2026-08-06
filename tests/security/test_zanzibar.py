from warm_logic.kernel.zanzibar import RelationTuple, ZanzibarEngine


def test_zanzibar_inheritance():
    engine = ZanzibarEngine(":memory:")  # Use memory for testing

    auth = "did:warm:root:1234"
    sig = "ROOT_AUTHORITY_SIG"

    # 1. Direct Assignment
    # user:bob is a viewer of doc:1
    t1 = RelationTuple(
        "doc", "1", "viewer", "user", "bob", authority=auth, signature=sig
    )
    assert engine.write_tuple(t1) == True

    assert engine.check("doc", "1", "viewer", "bob") == True
    assert engine.check("doc", "1", "viewer", "alice") == False

    # 2. Group Inheritance
    # group:admins#member -> user:alice
    t2 = RelationTuple(
        "group", "admins", "member", "user", "alice", authority=auth, signature=sig
    )
    engine.write_tuple(t2)

    # doc:2#viewer -> group:admins#member
    t3 = RelationTuple(
        "doc", "2", "viewer", "group", "admins", "member", authority=auth, signature=sig
    )
    engine.write_tuple(t3)

    print("Checking group inheritance for Alice on Doc 2...")
    assert engine.check("doc", "2", "viewer", "alice") == True
    print("✅ Inheritance Verified.")

    # 3. Negative Test: Unauthorized Inject
    print("Checking negative test (Unauthorized Inject)...")
    bad_t = RelationTuple(
        "doc", "1", "viewer", "user", "hacker", authority="did:hacker", signature="BAD"
    )
    assert engine.write_tuple(bad_t) == False
    assert engine.check("doc", "1", "viewer", "hacker") == False
    print("✅ Unauthorized Injection Correctly Blocked.")


if __name__ == "__main__":
    test_zanzibar_inheritance()
