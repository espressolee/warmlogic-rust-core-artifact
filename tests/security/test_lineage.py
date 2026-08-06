from warm_logic.kernel.lineage import LineageTracker, PolicyZone, enforce_lineage_flow


def test_lineage_enforcement():
    tracker = LineageTracker()

    # 1. Base Flow
    tracker.track("data_1", PolicyZone.PUBLIC, "user_0")
    assert tracker.check_flow("data_1", PolicyZone.INTERNAL) == True
    assert tracker.check_flow("data_1", PolicyZone.PUBLIC) == True

    # 2. Strict Blocking
    tracker.track("secret_data", PolicyZone.SECRET, "admin_1")
    assert tracker.check_flow("secret_data", PolicyZone.SECRET) == True
    assert tracker.check_flow("secret_data", PolicyZone.INTERNAL) == False
    assert tracker.check_flow("secret_data", PolicyZone.PUBLIC) == False

    # 3. Inheritance (Contamination)
    # A is PUBLIC, B is SECRET
    tracker.track("A", PolicyZone.PUBLIC, "user_1")
    tracker.track("B", PolicyZone.SECRET, "user_1")

    # C is derived from A and B
    tracker.track("C", PolicyZone.PUBLIC, "user_1", parents=["A", "B"])

    # C must be SECRET because it touched B
    assert tracker.records["C"].zone == PolicyZone.SECRET
    assert tracker.check_flow("C", PolicyZone.INTERNAL) == False

    print("✅ Lineage & Zone Inheritance Verified.")


if __name__ == "__main__":
    test_lineage_enforcement()
