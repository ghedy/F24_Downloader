"""Carosello Bootstrap simulato con gli stessi controlli del portale AdE."""
from threading import Event
from urllib.parse import urlsplit, parse_qs
import json
import pytest
from playwright.sync_api import sync_playwright
from src import f24_downloader as downloader
from src.models import Cancelled

@pytest.fixture(scope="module")
def carousel_browser():
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(headless=True)
        yield browser
        browser.close()

def _html(mode="hidden", initial=0, loop=True, only_previous=False, stuck=False, clone=False):
    groups = [[2026, 2025], [2024, 2023], [2022, 2021], [2020, 2019]]
    slides = "".join('<div class="carousel-item">' + "".join(
        f'<a href="/cassfisc-web/CassettoFiscaleServlet?Ric=F24&amp;Anno={year}">{year}</a>'
        for year in group) + '</div>' for group in groups)
    hidden_clone = ('<div style="display:none"><a href="/cassfisc-web/CassettoFiscaleServlet?Ric=F24&amp;Anno=2020">2020</a></div>'
                    if clone else "")
    code = """
    let current = INITIAL, busy = false;
    const clipped = CLIPPED, loop = LOOP, stuck = STUCK;
    function render() {
        document.querySelectorAll('.carousel-item').forEach((item, index) => {
            item.className = 'carousel-item' + (index === current ? ' active' : '');
            item.style.display = clipped || index === current ? 'block' : 'none';
            item.style.transform = clipped ? 'translateX(' + ((index-current)*240) + 'px)' : '';
        });
        if (!loop) {
            document.querySelector('.carousel-control-next').classList.toggle('disabled', current === 3);
            document.querySelector('.carousel-control-prev').classList.toggle('disabled', current === 0);
        }
    }
    function move(direction) {
        if (busy || stuck) return false;
        busy = true;
        document.querySelector('.carousel-item.active').classList.add('carousel-item-left');
        setTimeout(() => {
            current = loop ? (current + direction + 4) % 4 : Math.min(3, Math.max(0, current+direction));
            render(); busy = false;
            window.recordMove(direction);
        }, 180);
        return false;
    }
    render();
    """
    for key, value in [("INITIAL", initial), ("CLIPPED", mode == "clipped"), ("LOOP", loop), ("STUCK", stuck)]:
        code = code.replace(key, json.dumps(value))
    next_style = ' style="display:none"' if only_previous else ""
    return (hidden_clone + """
    <style>
    #service-slider {width:280px;height:120px}
    .carousel-inner {position:relative;width:240px;height:70px;overflow:hidden}
    .carousel-item {position:absolute;top:0;left:0;width:240px;height:70px}
    .carousel-item a {display:inline-block;width:90px;height:45px}
    </style><div id="service-slider"><div class="carousel-inner">""" + slides + """
    </div><a class="carousel-control-next icon-primary" href="#service-slider" role="button"
    data-slide="next" aria-hidden="true" onclick="return move(1)" """ + next_style + """>Anni successivi</a>
    <a class="carousel-control-prev icon-primary" href="#service-slider" role="button"
    data-slide="prev" aria-hidden="true" onclick="return move(-1)">Anni precedenti</a>
    </div><script>""" + code + "</script>")

def _open(context, **options):
    moves = []
    page = context.new_page()
    page.expose_function("recordMove", lambda direction: moves.append(direction))
    selected = []
    html = _html(**options)
    def respond(route):
        query = parse_qs(urlsplit(route.request.url).query)
        if query.get("Ric") == ["F24"]:
            selected.append(query["Anno"][0])
            route.fulfill(status=200, content_type="text/html", body="Elenco F24 sintetico")
        else:
            route.fulfill(status=200, content_type="text/html", body=html)
    context.route("**/*", respond)
    page.goto(downloader.BASE_URL + "?Ric=VERS")
    return page, moves, selected

@pytest.mark.parametrize("mode", ["hidden", "clipped"])
def test_reaches_hidden_2020_after_scroll_and_ignores_hidden_clone(carousel_browser, mode):
    with carousel_browser.new_context() as context:
        page, moves, selected = _open(context, mode=mode, clone=True)
        downloader.seleziona_anno(page, "2020", log=lambda _: None)
        assert selected == ["2020"]
        assert moves == [1, 1, 1]

def test_missing_year_stops_after_one_complete_cycle(carousel_browser):
    with carousel_browser.new_context() as context:
        page, moves, selected = _open(context)
        with pytest.raises(downloader.YearNotAvailable):
            downloader.seleziona_anno(page, "2018", log=lambda _: None)
        assert moves == [1, 1, 1, 1]
        assert selected == []

def test_previous_control_is_used_when_next_unavailable(carousel_browser):
    with carousel_browser.new_context() as context:
        page, moves, selected = _open(context, initial=3, loop=False, only_previous=True)
        downloader.seleziona_anno(page, "2026", log=lambda _: None)
        assert selected == ["2026"]
        assert moves == [-1, -1, -1]

def test_visible_year_does_not_scroll(carousel_browser):
    with carousel_browser.new_context() as context:
        page, moves, selected = _open(context)
        downloader.seleziona_anno(page, "2025", log=lambda _: None)
        assert moves == []
        assert selected == ["2025"]

def test_stuck_carousel_is_reported_instead_of_skipping_year(carousel_browser, monkeypatch):
    monkeypatch.setattr(downloader, "CAROUSEL_WAIT_SECONDS", 0.25)
    with carousel_browser.new_context() as context:
        page, moves, selected = _open(context, stuck=True)
        with pytest.raises(RuntimeError, match="scorrimento"):
            downloader.seleziona_anno(page, "2020", log=lambda _: None)
        assert selected == []

def test_cancellation_before_scroll_is_honored(carousel_browser):
    with carousel_browser.new_context() as context:
        page, moves, selected = _open(context)
        cancel = Event()
        def stop(message):
            if "scorro" in message:
                cancel.set()
        with pytest.raises(Cancelled):
            downloader.seleziona_anno(page, "2020", cancel=cancel, log=stop)
        assert moves == [] and selected == []
