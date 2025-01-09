import importlib.resources
res = importlib.resources.files("resources")


def test_mv_project():
    from model import Mv_Project, ProjectSettings, ProjectBinModel, Mv_Show

    project = Mv_Project()

    assert isinstance(project.settings, ProjectSettings), "Mv_Project did not create ProjectSettings instance"
    assert isinstance(project.bin, ProjectBinModel), "Mv_Project did not create ProjectBinModel instance"
    assert isinstance(project.mv_show, Mv_Show), "Mv_Project did not create Mv_Show instance"


def test_mv_show(qtbot):
    from model import Mv_Show, Mv_sequence
    from const import Show_States

    show = Mv_Show()

    assert isinstance(show.sequence, Mv_sequence), "Mv_Show did not create Mv_sequence instance"

    def check_signal(signal):
        return signal == "running"

    with qtbot.waitSignal((show.state_changed, "valueChanged"), timeout=10, check_params_cb=check_signal):
        show.set_state(Show_States.RUNNING)


def test_mv_sequence(qtmodeltester):
    from model import Mv_sequence, Mv_Scene, BinItem
    from const import Scene_Type

    model = Mv_sequence()
    for i in range(3):
        item = BinItem(str(i))
        scene = Mv_Scene(str(res / "Qhawana_Icon_16.png"), Scene_Type.STILL)
        item.setData(scene)
        model.appendRow(item)

    # qtmodeltester.check(model, force_py=True)
    assert model.rowCount() == 3
    assert model.columnCount() == 6


def test_mv_scene():
    from model import Mv_Scene
    from const import Scene_Type

    scene = Mv_Scene(str(res / "Qhawana_Icon_16.png"), Scene_Type.STILL)

    assert scene.scene_type == Scene_Type.STILL, "Failed to create scene of type STILL"


def test_project_bin_model(qtmodeltester):
    from model import ProjectBinModel, BinItem
    model = ProjectBinModel()

    for i in range(4):
        model.setItem(i, 0, BinItem(str(i)))

    qtmodeltester.check(model, force_py=True)


def test_bin_item():
    from model import BinItem

    item = BinItem("Qhawana")

    assert item.text() == "Qhawana", "BinItem does not return correct text"


def test_project_settings(qtbot):
    from model import ProjectSettings

    settings = ProjectSettings()

    assert settings.setProperty("unit_test_str", "qhawana"), "ProjectSetting does not set str value"
    assert settings.getProperty("unit_test_str") == "qhawana", "ProjectSettings does not get str value"

    assert settings.setProperty("unit_test_int", 1234), "ProjectSetting does not set int value"
    assert settings.getProperty("unit_test_int") == 1234, "ProjectSettings does not get int value"

    def check_signal(setting, value):
        return setting == "unit_test_signal" and value == "slot"

    with qtbot.waitSignal((settings.valueChanged, "valueChanged"), timeout=10, check_params_cb=check_signal):
        settings.setProperty("unit_test_signal", "slot")
