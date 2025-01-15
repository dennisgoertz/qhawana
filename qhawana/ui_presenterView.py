# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ui_presenterView.ui'
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
from PySide6.QtWidgets import (QApplication, QDial, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QSizePolicy, QSpinBox, QWidget)

class Ui_Form_presenterView(object):
    def setupUi(self, Form_presenterView):
        if not Form_presenterView.objectName():
            Form_presenterView.setObjectName(u"Form_presenterView")
        Form_presenterView.resize(1015, 609)
        self.horizontalLayout = QHBoxLayout(Form_presenterView)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.groupBox = QGroupBox(Form_presenterView)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy)
        self.groupBox.setMinimumSize(QSize(300, 140))
        self.gridLayout_2 = QGridLayout(self.groupBox)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.pushButton_audio_mute = QPushButton(self.groupBox)
        self.pushButton_audio_mute.setObjectName(u"pushButton_audio_mute")
        icon = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.AudioVolumeMuted))
        self.pushButton_audio_mute.setIcon(icon)
        self.pushButton_audio_mute.setCheckable(True)
        self.pushButton_audio_mute.setChecked(False)

        self.gridLayout_2.addWidget(self.pushButton_audio_mute, 0, 1, 1, 1)

        self.pushButton_audio_quiet = QPushButton(self.groupBox)
        self.pushButton_audio_quiet.setObjectName(u"pushButton_audio_quiet")
        icon1 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.AudioVolumeLow))
        self.pushButton_audio_quiet.setIcon(icon1)
        self.pushButton_audio_quiet.setCheckable(True)
        self.pushButton_audio_quiet.setChecked(False)

        self.gridLayout_2.addWidget(self.pushButton_audio_quiet, 0, 0, 1, 1)

        self.spinBox_audio_fadeTime = QSpinBox(self.groupBox)
        self.spinBox_audio_fadeTime.setObjectName(u"spinBox_audio_fadeTime")
        self.spinBox_audio_fadeTime.setMinimum(1)
        self.spinBox_audio_fadeTime.setMaximum(10)
        self.spinBox_audio_fadeTime.setSingleStep(1)
        self.spinBox_audio_fadeTime.setDisplayIntegerBase(10)

        self.gridLayout_2.addWidget(self.spinBox_audio_fadeTime, 2, 2, 1, 1)

        self.pushButton_audio_fadeOut = QPushButton(self.groupBox)
        self.pushButton_audio_fadeOut.setObjectName(u"pushButton_audio_fadeOut")
        self.pushButton_audio_fadeOut.setCheckable(True)
        self.pushButton_audio_fadeOut.setChecked(False)

        self.gridLayout_2.addWidget(self.pushButton_audio_fadeOut, 1, 0, 1, 1)

        self.pushButton_audio_fadeIn = QPushButton(self.groupBox)
        self.pushButton_audio_fadeIn.setObjectName(u"pushButton_audio_fadeIn")
        self.pushButton_audio_fadeIn.setCheckable(True)
        self.pushButton_audio_fadeIn.setChecked(False)

        self.gridLayout_2.addWidget(self.pushButton_audio_fadeIn, 1, 1, 1, 1)

        self.dial_volume = QDial(self.groupBox)
        self.dial_volume.setObjectName(u"dial_volume")
        self.dial_volume.setMinimumSize(QSize(0, 0))
        self.dial_volume.setMinimum(1)
        self.dial_volume.setMaximum(100)
        self.dial_volume.setValue(100)
        self.dial_volume.setTracking(True)
        self.dial_volume.setOrientation(Qt.Orientation.Horizontal)
        self.dial_volume.setInvertedAppearance(False)
        self.dial_volume.setInvertedControls(False)

        self.gridLayout_2.addWidget(self.dial_volume, 0, 2, 2, 1)


        self.gridLayout.addWidget(self.groupBox, 2, 0, 1, 1)

        self.label_previousView = QLabel(Form_presenterView)
        self.label_previousView.setObjectName(u"label_previousView")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.label_previousView.sizePolicy().hasHeightForWidth())
        self.label_previousView.setSizePolicy(sizePolicy1)
        self.label_previousView.setMinimumSize(QSize(150, 100))
        self.label_previousView.setFrameShape(QFrame.Shape.Box)
        self.label_previousView.setScaledContents(False)
        self.label_previousView.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout.addWidget(self.label_previousView, 1, 0, 1, 1)

        self.label_nextView = QLabel(Form_presenterView)
        self.label_nextView.setObjectName(u"label_nextView")
        sizePolicy1.setHeightForWidth(self.label_nextView.sizePolicy().hasHeightForWidth())
        self.label_nextView.setSizePolicy(sizePolicy1)
        self.label_nextView.setMinimumSize(QSize(150, 100))
        self.label_nextView.setFrameShape(QFrame.Shape.Box)
        self.label_nextView.setScaledContents(False)
        self.label_nextView.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout.addWidget(self.label_nextView, 1, 2, 1, 1)

        self.groupBox_2 = QGroupBox(Form_presenterView)
        self.groupBox_2.setObjectName(u"groupBox_2")
        sizePolicy.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy)
        self.groupBox_2.setMinimumSize(QSize(300, 140))
        self.gridLayout_3 = QGridLayout(self.groupBox_2)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.pushButton_previousView = QPushButton(self.groupBox_2)
        self.pushButton_previousView.setObjectName(u"pushButton_previousView")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.pushButton_previousView.sizePolicy().hasHeightForWidth())
        self.pushButton_previousView.setSizePolicy(sizePolicy2)
        self.pushButton_previousView.setMinimumSize(QSize(30, 30))
        self.pushButton_previousView.setMaximumSize(QSize(100, 100))
        self.pushButton_previousView.setBaseSize(QSize(100, 100))
        icon2 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.MediaSeekBackward))
        self.pushButton_previousView.setIcon(icon2)

        self.gridLayout_3.addWidget(self.pushButton_previousView, 0, 0, 1, 1)

        self.pushButton_play = QPushButton(self.groupBox_2)
        self.pushButton_play.setObjectName(u"pushButton_play")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.pushButton_play.sizePolicy().hasHeightForWidth())
        self.pushButton_play.setSizePolicy(sizePolicy3)
        self.pushButton_play.setMinimumSize(QSize(30, 30))
        self.pushButton_play.setMaximumSize(QSize(100, 100))
        self.pushButton_play.setBaseSize(QSize(100, 100))
        icon3 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.MediaPlaybackStart))
        self.pushButton_play.setIcon(icon3)

        self.gridLayout_3.addWidget(self.pushButton_play, 0, 1, 1, 1)

        self.pushButton_pause = QPushButton(self.groupBox_2)
        self.pushButton_pause.setObjectName(u"pushButton_pause")
        sizePolicy2.setHeightForWidth(self.pushButton_pause.sizePolicy().hasHeightForWidth())
        self.pushButton_pause.setSizePolicy(sizePolicy2)
        self.pushButton_pause.setMinimumSize(QSize(30, 30))
        self.pushButton_pause.setMaximumSize(QSize(100, 100))
        self.pushButton_pause.setBaseSize(QSize(100, 100))
        icon4 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.MediaPlaybackPause))
        self.pushButton_pause.setIcon(icon4)

        self.gridLayout_3.addWidget(self.pushButton_pause, 0, 2, 1, 1)

        self.pushButton_nextView = QPushButton(self.groupBox_2)
        self.pushButton_nextView.setObjectName(u"pushButton_nextView")
        sizePolicy2.setHeightForWidth(self.pushButton_nextView.sizePolicy().hasHeightForWidth())
        self.pushButton_nextView.setSizePolicy(sizePolicy2)
        self.pushButton_nextView.setMinimumSize(QSize(30, 30))
        self.pushButton_nextView.setMaximumSize(QSize(100, 100))
        self.pushButton_nextView.setBaseSize(QSize(100, 100))
        icon5 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.MediaSeekForward))
        self.pushButton_nextView.setIcon(icon5)

        self.gridLayout_3.addWidget(self.pushButton_nextView, 0, 3, 1, 1)

        self.progressBar_state = QProgressBar(self.groupBox_2)
        self.progressBar_state.setObjectName(u"progressBar_state")
        self.progressBar_state.setEnabled(True)
        self.progressBar_state.setValue(0)
        self.progressBar_state.setTextVisible(True)

        self.gridLayout_3.addWidget(self.progressBar_state, 1, 0, 1, 4)


        self.gridLayout.addWidget(self.groupBox_2, 2, 2, 1, 1)

        self.label_sceneCounter = QLabel(Form_presenterView)
        self.label_sceneCounter.setObjectName(u"label_sceneCounter")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.label_sceneCounter.sizePolicy().hasHeightForWidth())
        self.label_sceneCounter.setSizePolicy(sizePolicy4)
        font = QFont()
        font.setPointSize(18)
        self.label_sceneCounter.setFont(font)
        self.label_sceneCounter.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout.addWidget(self.label_sceneCounter, 3, 1, 1, 1)

        self.label_currentView = QLabel(Form_presenterView)
        self.label_currentView.setObjectName(u"label_currentView")
        sizePolicy5 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.label_currentView.sizePolicy().hasHeightForWidth())
        self.label_currentView.setSizePolicy(sizePolicy5)
        self.label_currentView.setMinimumSize(QSize(200, 150))
        self.label_currentView.setMaximumSize(QSize(16777215, 16777215))
        self.label_currentView.setFrameShape(QFrame.Shape.Box)
        self.label_currentView.setScaledContents(False)
        self.label_currentView.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout.addWidget(self.label_currentView, 1, 1, 1, 1)

        self.label_notes = QLabel(Form_presenterView)
        self.label_notes.setObjectName(u"label_notes")
        font1 = QFont()
        font1.setFamilies([u"Serif"])
        font1.setPointSize(18)
        self.label_notes.setFont(font1)
        self.label_notes.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.label_notes.setWordWrap(True)
        self.label_notes.setMargin(10)

        self.gridLayout.addWidget(self.label_notes, 2, 1, 1, 1)


        self.horizontalLayout.addLayout(self.gridLayout)


        self.retranslateUi(Form_presenterView)

        QMetaObject.connectSlotsByName(Form_presenterView)
    # setupUi

    def retranslateUi(self, Form_presenterView):
        Form_presenterView.setWindowTitle("")
        self.groupBox.setTitle(QCoreApplication.translate("Form_presenterView", u"Audio controls", None))
        self.pushButton_audio_mute.setText(QCoreApplication.translate("Form_presenterView", u"Mute", None))
        self.pushButton_audio_quiet.setText(QCoreApplication.translate("Form_presenterView", u"Quiet", None))
        self.spinBox_audio_fadeTime.setSuffix(QCoreApplication.translate("Form_presenterView", u" s", None))
        self.spinBox_audio_fadeTime.setPrefix("")
        self.pushButton_audio_fadeOut.setText(QCoreApplication.translate("Form_presenterView", u"fade out", None))
        self.pushButton_audio_fadeIn.setText(QCoreApplication.translate("Form_presenterView", u"fade in", None))
        self.label_previousView.setText("")
        self.label_nextView.setText("")
        self.groupBox_2.setTitle(QCoreApplication.translate("Form_presenterView", u"Scene controls", None))
        self.pushButton_previousView.setText("")
        self.pushButton_play.setText("")
        self.pushButton_pause.setText("")
        self.pushButton_nextView.setText("")
        self.progressBar_state.setFormat(QCoreApplication.translate("Form_presenterView", u"state", None))
        self.label_sceneCounter.setText(QCoreApplication.translate("Form_presenterView", u"1/n", None))
        self.label_currentView.setText("")
        self.label_notes.setText(QCoreApplication.translate("Form_presenterView", u"Scene Notes", None))
    # retranslateUi

