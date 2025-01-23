# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'form_panAndZoom.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QHBoxLayout,
    QLabel, QListView, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget)

from image_widget import ImageWidget

class Ui_Form_PanAndZoomEffect(object):
    def setupUi(self, Form_PanAndZoomEffect):
        if not Form_PanAndZoomEffect.objectName():
            Form_PanAndZoomEffect.setObjectName(u"Form_PanAndZoomEffect")
        Form_PanAndZoomEffect.setWindowModality(Qt.WindowModality.ApplicationModal)
        Form_PanAndZoomEffect.resize(684, 471)
        self.verticalLayout = QVBoxLayout(Form_PanAndZoomEffect)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.image = ImageWidget(Form_PanAndZoomEffect)
        self.image.setObjectName(u"image")

        self.verticalLayout.addWidget(self.image)

        self.labelInfoPath = QLabel(Form_PanAndZoomEffect)
        self.labelInfoPath.setObjectName(u"labelInfoPath")

        self.verticalLayout.addWidget(self.labelInfoPath)

        self.labelInfoScale = QLabel(Form_PanAndZoomEffect)
        self.labelInfoScale.setObjectName(u"labelInfoScale")

        self.verticalLayout.addWidget(self.labelInfoScale)

        self.listView = QListView(Form_PanAndZoomEffect)
        self.listView.setObjectName(u"listView")

        self.verticalLayout.addWidget(self.listView)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.checkboxStayInside = QCheckBox(Form_PanAndZoomEffect)
        self.checkboxStayInside.setObjectName(u"checkboxStayInside")
        self.checkboxStayInside.setChecked(True)

        self.horizontalLayout.addWidget(self.checkboxStayInside)

        self.buttonSwitchInOutEditor = QPushButton(Form_PanAndZoomEffect)
        self.buttonSwitchInOutEditor.setObjectName(u"buttonSwitchInOutEditor")

        self.horizontalLayout.addWidget(self.buttonSwitchInOutEditor)

        self.buttonSwapInOutEditor = QPushButton(Form_PanAndZoomEffect)
        self.buttonSwapInOutEditor.setObjectName(u"buttonSwapInOutEditor")

        self.horizontalLayout.addWidget(self.buttonSwapInOutEditor)

        self.buttonDone = QPushButton(Form_PanAndZoomEffect)
        self.buttonDone.setObjectName(u"buttonDone")

        self.horizontalLayout.addWidget(self.buttonDone)


        self.verticalLayout.addLayout(self.horizontalLayout)

        self.verticalLayout.setStretch(0, 3)
        self.verticalLayout.setStretch(3, 1)

        self.retranslateUi(Form_PanAndZoomEffect)

        QMetaObject.connectSlotsByName(Form_PanAndZoomEffect)
    # setupUi

    def retranslateUi(self, Form_PanAndZoomEffect):
        Form_PanAndZoomEffect.setWindowTitle(QCoreApplication.translate("Form_PanAndZoomEffect", u"Pan and Zoom Effect", None))
        self.labelInfoPath.setText(QCoreApplication.translate("Form_PanAndZoomEffect", u"InfoPath", None))
        self.labelInfoScale.setText(QCoreApplication.translate("Form_PanAndZoomEffect", u"InfoScale", None))
        self.checkboxStayInside.setText(QCoreApplication.translate("Form_PanAndZoomEffect", u"Stay Inside Image", None))
        self.buttonSwitchInOutEditor.setText(QCoreApplication.translate("Form_PanAndZoomEffect", u"Switch In/Out Editor", None))
        self.buttonSwapInOutEditor.setText(QCoreApplication.translate("Form_PanAndZoomEffect", u"Swap In/Out", None))
        self.buttonDone.setText(QCoreApplication.translate("Form_PanAndZoomEffect", u"Done", None))
    # retranslateUi

