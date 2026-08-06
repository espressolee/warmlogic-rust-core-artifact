import warm_logic.VERSION as v


def test_version_format():
    assert isinstance(v.__version__, str)
    assert len(v.__version__.split(".")) >= 3
    print(f"Version verified: {v.__version__}")


if __name__ == "__main__":
    test_version_format()
