from scripts.eval import update_paper09_tables


def test_render_table_21_vtracer_case_basic() -> None:
    data = {
        "variants": {
            "stock": {
                "sizes": [
                    {
                        "size_bytes": 100_000,
                        "summary": {
                            "p50_median": 1_000_000.0,
                            "p50_iqr": 10_000.0,
                            "p99_median": 2_000_000.0,
                            "p99_iqr": 20_000.0,
                        },
                    }
                ]
            },
            "bytesvec": {
                "sizes": [
                    {
                        "size_bytes": 100_000,
                        "summary": {
                            "p50_median": 100_000.0,
                            "p50_iqr": 1_000.0,
                            "p99_median": 200_000.0,
                            "p99_iqr": 2_000.0,
                        },
                    }
                ]
            },
        }
    }

    table = update_paper09_tables._render_table_21_vtracer_case(data=data)
    assert "| 100KB |" in table
    assert "10.0×" in table

