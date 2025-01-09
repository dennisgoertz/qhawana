import importlib.resources
res = importlib.resources.files("resources")


def test_film_strip_widget(qtbot):
    from widgets import FilmStripWidget

    widget = FilmStripWidget()
    qtbot.addWidget(widget)
    widget.show()

    with qtbot.waitExposed(widget):
        assert widget.isVisible(), "FilmStripWidget could not be shown"


def test_scene_table_widget(qtbot):
    from widgets import SceneTableWidget

    widget = SceneTableWidget()
    qtbot.addWidget(widget)
    widget.show()

    with qtbot.waitExposed(widget):
        assert widget.isVisible(), "SceneTableWidget could not be shown"


def test_project_bin_widget(qtbot):
    from widgets import ProjectBinWidget

    widget = ProjectBinWidget()
    qtbot.addWidget(widget)
    widget.show()

    with qtbot.waitExposed(widget):
        assert widget.isVisible(), "ProjectBinWidget could not be shown"


def test_qhawana_splash(qtbot):
    from widgets import QhawanaSplash

    splash = QhawanaSplash(800, 600, str(res / "Qhawana_Splash.png"))
    qtbot.addWidget(splash)
    splash.show()

    assert not splash.pixmap().isNull(), "QhawanaSplash did not load QPixmap from file"

    with qtbot.waitExposed(splash):
        assert splash.isVisible(), "QhawanaSplash could not be shown"

