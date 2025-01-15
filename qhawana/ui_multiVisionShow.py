# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ui_multiVisionShow.ui'
##
## Created by: Qt User Interface Compiler version 6.8.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsView, QSizePolicy,
    QWidget)

class Ui_Form_multiVisionShow(object):
    def setupUi(self, Form_multiVisionShow):
        if not Form_multiVisionShow.objectName():
            Form_multiVisionShow.setObjectName(u"Form_multiVisionShow")
        Form_multiVisionShow.resize(1081, 786)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(Form_multiVisionShow.sizePolicy().hasHeightForWidth())
        Form_multiVisionShow.setSizePolicy(sizePolicy)
        palette = QPalette()
        brush = QBrush(QColor(0, 0, 0, 255))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.Window, brush)
        palette.setBrush(QPalette.Inactive, QPalette.Window, brush)
        palette.setBrush(QPalette.Disabled, QPalette.Base, brush)
        palette.setBrush(QPalette.Disabled, QPalette.Window, brush)
        Form_multiVisionShow.setPalette(palette)
        Form_multiVisionShow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        Form_multiVisionShow.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.graphicsView = QGraphicsView(Form_multiVisionShow)
        self.graphicsView.setObjectName(u"graphicsView")
        self.graphicsView.setAcceptDrops(False)
        self.graphicsView.setFrameShape(QFrame.Shape.NoFrame)
        self.graphicsView.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphicsView.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphicsView.setBackgroundBrush(brush)
        self.graphicsView.setInteractive(False)
        self.graphicsView.setRenderHints(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.LosslessImageRendering|QPainter.RenderHint.SmoothPixmapTransform|QPainter.RenderHint.TextAntialiasing)

        self.retranslateUi(Form_multiVisionShow)

        QMetaObject.connectSlotsByName(Form_multiVisionShow)
    # setupUi

    def retranslateUi(self, Form_multiVisionShow):
        Form_multiVisionShow.setWindowTitle("")
    # retranslateUi

