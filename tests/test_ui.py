def test_launcher(qtbot):
    from qhawana.ui import Ui_mainWindow
    ui = Ui_mainWindow()
    qtbot.addWidget(ui)
    ui.show()
    with qtbot.waitExposed(ui):
        assert ui.isVisible(), "UI could not be loaded"
