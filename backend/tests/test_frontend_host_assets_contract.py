from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_host_metadata_uses_emblem_and_brand_theme() -> None:
    index = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert '<meta name="theme-color" content="#10243f">' in index
    assert (
        '<link rel="icon" href="/static/assets/院徽.jpg" type="image/jpeg">'
        in index
    )
    assert 'href="/static/assets/brand-mark.svg"' not in index


def test_host_mount_points_and_vendor_order_are_preserved() -> None:
    index = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    app_pos = index.index('<div id="app"')
    toast_pos = index.index('<div id="toast-region"')
    modal_pos = index.index('<div id="modal-root"')
    marked_pos = index.index('/static/assets/vendor/marked.min.js')
    dompurify_pos = index.index('/static/assets/vendor/dompurify.min.js')
    app_script_pos = index.index('/static/js/app.js')

    assert app_pos < toast_pos < modal_pos < marked_pos < dompurify_pos < app_script_pos


def test_emblem_asset_is_an_exact_copy_of_source() -> None:
    source = PROJECT_ROOT / "image" / "院徽.jpg"
    target = PROJECT_ROOT / "frontend" / "assets" / "院徽.jpg"

    assert source.is_file()
    assert target.is_file()
    assert target.read_bytes() == source.read_bytes()
    assert target.stat().st_size > 0


def test_static_mount_serves_frontend_assets() -> None:
    main = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text(
        encoding="utf-8"
    )

    assert 'app.mount("/static", StaticFiles(directory=_frontend_dir)' in main


def test_workbench_assets_use_the_current_cache_version() -> None:
    index = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = (PROJECT_ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    mentorship = (PROJECT_ROOT / "frontend" / "js" / "views" / "mentorship.js").read_text(encoding="utf-8")

    assert "styles.css?v=20260818-workbench" in index
    assert "js/app.js?v=20260818-workbench" in index
    assert "mentorship.js?v=20260818-workbench" in app
    assert "party.js?v=20260818-workbench" in app
    assert "mentor_selection.js?v=20260818-workbench" in mentorship
