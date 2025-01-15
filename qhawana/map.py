from PySide6 import QtCore, QtPositioning, QtQuickWidgets, QtWidgets, QtQml

QML_IMPORT_NAME = "io.qt.qhawana"
QML_IMPORT_MAJOR_VERSION = 1


@QtQml.QmlElement
class PyQMLBridge(QtCore.QObject):
    move = QtCore.Signal(float, float, name="move")
    path = QtCore.Signal(QtPositioning.QGeoPath, name="path")
    fit = QtCore.Signal(name="fit")

    def __init__(self, parent=None):
        super().__init__(parent)

    def setLocation(self, lat, lon):
        self.move.emit(lat, lon)
        print(f"Setting location to {lat}, {lon}")

    def drawPath(self, path):
        self.path.emit(path)

    def fitViewport(self):
        self.fit.emit()



if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    mw = QtWidgets.QMainWindow()
    qw = QtQuickWidgets.QQuickWidget()
    gc = QtPositioning.QGeoCoordinate()

    br = PyQMLBridge()
    qw.engine().rootContext().setContextProperty("br", br)
    qw.setSource(QtCore.QUrl("map.qml"))


    def move_map():
        print("Moving!")
        br.setLocation(58.9485, 11.7686)


    QtCore.QTimer().singleShot(3000, move_map)

    mw.layout().addWidget(qw)

    mw.show()
    app.exec()
