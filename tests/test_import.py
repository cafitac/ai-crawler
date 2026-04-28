def test_package_imports_with_version() -> None:
    import ai_crawler

    assert isinstance(ai_crawler.__version__, str)
    assert ai_crawler.__version__
