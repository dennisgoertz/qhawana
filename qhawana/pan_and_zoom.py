from PySide6.QtCore import Qt, QTimer, QRectF, QLineF, QPointF, QObject, QTimeLine, QEasingCurve, qDebug
from PySide6.QtWidgets import QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QApplication
from PySide6.QtGui import QPixmap, QPainter, QResizeEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget

import importlib.resources

res = importlib.resources.files("resources")


class pan_and_zoom(QObject):
    def __init__(self, graphics_view, bbox_from=QRectF(0.0, 0.0, .7, .7),
                 bbox_to=QRectF(.1, .1, .8, .8), duration=5000, parent=None):
        super().__init__(parent)

        self.timeline = QTimeLine(duration)
        self.timeline.setEasingCurve(QEasingCurve.Type.Linear)
        self.timeline.valueChanged.connect(self.inc)
        self.timeline.finished.connect(self.done)

        self.gv: QGraphicsView = graphics_view

        self.start_rect = QRectF(bbox_from.x() * self.gv.sceneRect().width(),
                                 bbox_from.y() * self.gv.sceneRect().height(),
                                 bbox_from.width() * self.gv.sceneRect().width(),
                                 bbox_from.height() * self.gv.sceneRect().height())

        self.end_rect = QRectF(bbox_to.x() * self.gv.sceneRect().width(),
                               bbox_to.y() * self.gv.sceneRect().height(),
                               bbox_to.width() * self.gv.sceneRect().width(),
                               bbox_to.height() * self.gv.sceneRect().height())

        self.gv.setViewport(QOpenGLWidget())
        self.gv.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.gv.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.gv.fitInView(self.start_rect)

    def inc(self):
        cur_rect = self.get_cur_rect(self.timeline.currentValue())
        self.gv.fitInView(cur_rect)

    def start(self):
        self.timeline.start()
        qDebug(f"Starting pan and zoom effect from {self.start_rect} to {self.end_rect} "
               f"in {self.timeline.duration()} ms")

    def done(self):
        print(f"Finished pan and zoom effect at {self.get_cur_rect(1)}, target: {self.end_rect}")

    def get_cur_rect(self, value):
        start_point = self.start_rect.center()
        end_point = self.end_rect.center()

        vector = QLineF(start_point, end_point)
        width_difference = self.start_rect.width() - self.end_rect.width()
        height_difference = self.start_rect.height() - self.end_rect.height()

        cur_rect = QRectF()
        cur_rect.setWidth(self.start_rect.width() - width_difference * value)
        cur_rect.setHeight(self.start_rect.height() - height_difference * value)
        cur_rect.moveCenter(vector.pointAt(value))

        return cur_rect


if __name__ == "__main__":
    app = QApplication()
    ui = QMainWindow()
    ui.show()

    gv = QGraphicsView()
    gv.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    gv.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    ui.layout().addWidget(gv)

    pixmap = QPixmap(str(res / "Qhawana_Splash.png"))
    graphics_scene = QGraphicsScene()

    image_item = QGraphicsPixmapItem()
    image_item.setPixmap(pixmap)
    image_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
    graphics_scene.addItem(image_item)

    gv.setScene(graphics_scene)

    pz = pan_and_zoom(gv)
    pz.start()

    app.exec()
