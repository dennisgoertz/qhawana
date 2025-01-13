import importlib.resources
res = importlib.resources.files("resources")


def test_get_supported_mime_types():
    from utils import get_supported_mime_types

    r = get_supported_mime_types()

    assert type(r) is list, "get_supported_mime_types did not return a list"
    assert len(r) > 0, "get_supported_mime_types returned an empty list"


def test_count_rows_of_index():
    from utils import countRowsOfIndex
    from PySide6 import QtGui

    model = QtGui.QStandardItemModel()
    parent = model.invisibleRootItem()
    for i in range(10):
        item = QtGui.QStandardItem(f"item {i}")
        parent.appendRow(item)
        parent = item
    index = model.index(0, 0)

    r = countRowsOfIndex(index)

    assert type(r) is int, "count_rows_of_index did not return an int"
    assert r == 9, "count_rows_of_index did not return the correct number of items"


def test_for_each_item_in_model():
    from utils import forEachItemInModel
    from PySide6 import QtCore, QtGui

    model = QtGui.QStandardItemModel()
    parent = model.invisibleRootItem()

    i_data = []
    for i in range(10):
        item = QtGui.QStandardItem()
        item.setData(f"item {i}", QtCore.Qt.ItemDataRole.UserRole)
        i_data.append(item.data(QtCore.Qt.ItemDataRole.UserRole))
        parent.appendRow(item)
        if i % 2 != 0:
            parent = item

    r_data = []

    def recurse_forEachItemInModel(m, p=QtCore.QModelIndex()):
        for idx, d in forEachItemInModel(m, p):
            if d:
                r_data.append(d)
            if idx:
                recurse_forEachItemInModel(m, idx)

    recurse_forEachItemInModel(model)

    assert r_data == i_data, "ForEachItemInModel does not return all the items from the model"


def test_scale_pixmap_to_widget(qtbot):
    from utils import scalePixmapToWidget
    from PySide6 import QtCore, QtGui, QtWidgets

    pixmap = QtGui.QPixmap(200, 100)
    widget = QtWidgets.QLabel()
    qtbot.addWidget(widget)
    widget.setFixedSize(QtCore.QSize(50, 50))

    scaled_pixmap = scalePixmapToWidget(widget, pixmap)

    # scalePixmapToWidget keeps the aspect ratio of the source pixmap (2:1)
    assert scaled_pixmap.width() == 50, "scalePixmapToWidget did not correctly scale the width"
    assert scaled_pixmap.height() == 25, "scalePixmapToWidget did not correctly scale the height"


# noinspection PyUnusedLocal
def test_get_keyframe_from_video(qapp):
    from utils import getKeyframeFromVideo
    from PySide6 import QtGui

    image = getKeyframeFromVideo(str(res / "bear-1280x720.mp4"))
    assert isinstance(image, QtGui.QImage), "getKeyframeFromVideo did not return a QImage"

    pixmap = QtGui.QPixmap().fromImage(image)
    assert not pixmap.isNull()


def test_time_string_from_msec():
    from utils import timeStringFromMsec

    time_string = timeStringFromMsec(61001)

    assert time_string == "01:01.001", "timeStringFromMsec did not correctly calculate the time string"


def test_get_file_hash_sha1():
    from utils import getFileHashSHA1

    file_hash = getFileHashSHA1(str(res / "Qhawana_Icon_16.png"), used_for_security=False)
    assert file_hash == "f4893ed76b4efc38168f6069e808affd9ee20ab1", "getFileHashSHA1 did not return the correct value"
