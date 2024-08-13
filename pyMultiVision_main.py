import math
import exiftool
import os
import json
import mimetypes
import sys
import traceback
from enum import IntEnum
from PyQt6 import QtCore, QtGui, QtWidgets, QtMultimedia
from ui_mainWindow import Ui_mainWindow_pyMultiVision
from ui_presenterView import Ui_Form_presenterView
from ui_multiVisionShow import Ui_Form_multiVisionShow


class Scene_Type(IntEnum):
    EMPTY = 0
    STILL = 1
    VIDEO = 2


class Show_States(IntEnum):
    STOPPED = 0
    RUNNING = 1
    PAUSED = 2
    FINISHED = 3


class WorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(tuple)
    result = QtCore.pyqtSignal(object)
    progress = QtCore.pyqtSignal(int)


class Worker(QtCore.QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        self.kwargs['progress_callback'] = self.signals.progress

    @QtCore.pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


class Mv_Show:
    def __init__(self):
        self.sequence = QtGui.QStandardItemModel()
        self.state = Show_States.STOPPED

    def length(self):
        return self.sequence.rowCount()

    def toJson(self):
        scenes = []
        for index in range(self.sequence.rowCount()):
            item = self.sequence.item(index)
            scene_data = item.data().toJson()
            scene_data["filename"] = item.text()
            scenes.append(scene_data)
        json_string = {"scenes": scenes}
        return json_string

    def fromJson(self, json_string: dict):
        self.state = Show_States.STOPPED
        for s in json_string["scenes"]:
            scene = Mv_Scene.fromJson(s)
            self.sequence.appendRow(scene)

    def getModel(self):
        return self.sequence

    def getScene(self, index=0):
        # return self.sequence[index] if 0 <= index < self.length() else False
        # index = self.sequence.index(index, 0) if 0 <= index < self.length() else False
        return self.sequence.item(index, 0).data() if 0 <= index < self.length() else False


class Mv_Scene:
    def __init__(self, source: str, scene_type: Scene_Type, audio_source="", pause=False, duration=5,
                 pixmap=None, notes="", exif=None):

        self.source = source
        self.audio_source = audio_source
        self.scene_type = scene_type
        self.pause = pause
        self.duration = duration
        self.pixmap = pixmap
        self.notes = notes
        self.exif = exif

        if self.source and self.pixmap is None:
            if self.scene_type == Scene_Type.STILL:
                self.pixmap = QtGui.QPixmap(self.source)
            elif self.scene_type == Scene_Type.VIDEO:
                # TODO: Prepare video scene
                pass

    def toJson(self) -> dict:
        json_dict = {"source": self.source,
                     "audio_source": self.audio_source,
                     "scene_type": self.scene_type,
                     "pause": self.pause,
                     "duration": self.duration,
                     "pixmap": None,
                     "notes": self.notes,
                     "exif": self.exif}
        return json_dict

    def fromJson(json_dict: dict) -> QtGui.QStandardItem:
        pixmap = QtGui.QPixmap(json_dict["source"])
        icon = QtGui.QIcon()
        icon.addPixmap(pixmap, QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
        scene = Mv_Scene(source=json_dict["source"],
                         audio_source=json_dict["audio_source"],
                         pixmap=pixmap,
                         scene_type=json_dict["scene_type"],
                         pause=json_dict["pause"],
                         duration=json_dict["duration"],
                         notes=json_dict["notes"],
                         exif=json_dict["exif"])
        item = QtGui.QStandardItem(icon, json_dict["filename"])
        item.setData(scene)
        return item


def getPixmapFromScene(scene: Mv_Scene) -> QtGui.QPixmap:
    if scene:
        if type(scene.pixmap) is QtGui.QPixmap:
            pixmap = scene.pixmap
        else:
            pixmap = QtGui.QPixmap(100, 100)
            pixmap.fill(QtGui.QColor("black"))

            if scene.scene_type == Scene_Type.STILL:
                pixmap.load(scene.source)
            elif scene.scene_type == Scene_Type.VIDEO:
                # TODO: Generate video thumbnail and store it in the QPixmap
                pass
    else:
        pixmap = QtGui.QPixmap(100, 100)
        pixmap.fill(QtGui.QColor("black"))

    return pixmap


class Ui_mainWindow(QtWidgets.QMainWindow, Ui_mainWindow_pyMultiVision):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.setupUi(self)

        self.mvshow = Mv_Show()
        self.pv = None
        self.save_file = None
        self.supported_mime_types = get_supported_mime_types()
        self.scene_index = 0

        self.threadpool = QtCore.QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())
        print("Supported media MIME types: %s" % self.supported_mime_types)

        # self.tableView_scenes.setItemDelegateForColumn()
        self.pushButton_mediaSourceDirectory.clicked.connect(self.sceneFromDirectoryDialog)
        self.pushButton_startShow.clicked.connect(self.openPresenterView)
        self.listView_filmStrip.clicked.connect(self.showScenePreview)
        self.tableView_scenes.clicked.connect(self.showScenePreview)
        self.textEdit_notes.textChanged.connect(self.updateSceneNotes)
        self.actionNew.triggered.connect(self.newProject)
        self.actionOpen.triggered.connect(self.loadFromFile)
        self.actionSave.triggered.connect(self.saveToFile)
        self.actionSave_As.triggered.connect(self.saveAsFileDialog)
        self.actionQuit.triggered.connect(app.quit, QtCore.Qt.ConnectionType.QueuedConnection)

    def newProject(self):
        del self.mvshow
        self.mvshow = Mv_Show()
        self.save_file = None
        self.scene_index = 0
        self.updateFilmStrip()

    def saveAsFileDialog(self):
        file_name = QtWidgets.QFileDialog.getSaveFileName(self, "Save project to file")[0]
        if file_name:
            self.save_file = file_name
            self.saveToFile()

    def saveToFile(self):
        if self.save_file:
            with open(self.save_file, 'w') as f:
                json.dump(self.mvshow.toJson(), f, ensure_ascii=False, indent=4)
        else:
            self.saveAsFileDialog()

    def loadFromFile(self, file_name=""):
        if not file_name:
            file_name = QtWidgets.QFileDialog.getOpenFileName(self, "Select project file")[0]
        if file_name:
            worker = Worker(self.loadShowFromFile, file_name)
            worker.signals.finished.connect(self.updateFilmStrip)
            self.threadpool.start(worker)

    def loadShowFromFile(self, file_name, progress_callback):
        with open(file_name, 'r') as f:
            json_string = json.load(f)
        self.mvshow.fromJson(json_string)
        self.save_file = file_name

    def sceneFromDirectoryDialog(self):
        dir_name = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Media Source Directory")
        if dir_name:
            self.textEdit_mediaSourceDirectory.setText(dir_name)
            self.progressBar.setEnabled(True)
            self.progressBar.setTextVisible(True)

            worker = Worker(self.populateModelFromDirectory, dir_name)
            worker.signals.progress.connect(self.populateModelFromDirectory_progress)
            worker.signals.finished.connect(self.updateFilmStrip)
            self.threadpool.start(worker)

    def populateModelFromDirectory(self, dir_name, progress_callback):
        directory = os.listdir(dir_name)
        num_files = len(directory)

        for index, file in enumerate(directory):
            path = os.path.join(dir_name, file)
            mimetype, encoding = mimetypes.guess_type(path)

            if mimetype.startswith("image/"):
                audiopath = "/home/scout/mp3/[Soundtracks]/Hans Zimmer/2000 - Gladiator/12-Slaves to Rome.mp3"
                pixmap = QtGui.QPixmap(path)
                icon = QtGui.QIcon()
                icon.addPixmap(pixmap, QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
                scene = Mv_Scene(source=path,
                                 audio_source=audiopath,
                                 pixmap=pixmap,
                                 scene_type=Scene_Type.STILL,
                                 exif=exiftool.ExifToolHelper().get_metadata(path))
                item = QtGui.QStandardItem(icon, file)
                item.setData(scene)
                self.mvshow.sequence.appendRow(item)
            elif mimetype.startswith("video/") and mimetype in self.supported_mime_types:
                # TODO: Generate video thumbnail and store it in the QPixmap
                pixmap = QtGui.QPixmap(100, 100)
                pixmap.fill(QtGui.QColor("black"))
                icon = QtGui.QIcon()
                icon.addPixmap(pixmap, QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
                scene = Mv_Scene(source=path, scene_type=Scene_Type.VIDEO)
                item = QtGui.QStandardItem(icon, file)
                item.setData(scene)
                self.mvshow.sequence.appendRow(item)

            progress_callback.emit(int((index + 1) * 100 / num_files))

        return True

    def populateModelFromDirectory_progress(self, percentage):
        self.progressBar.setValue(percentage)

    def updateFilmStrip(self):
        model = self.mvshow.sequence

        self.listView_filmStrip.setModel(model)
        self.tableView_scenes.setModel(model)
        self.tableView_scenes.resizeColumnsToContents()

        self.progressBar.setEnabled(False)
        self.progressBar.setTextVisible(False)
        self.progressBar.setValue(0)

    def openPresenterView(self):
        if self.mvshow.length() > 0:
            self.pv = Ui_presenterView(parent=self)
            self.pv.show()
        else:
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("Empty MultiVision show!")
            dialog.setText("Please add scenes first.")
            dialog.exec()

    def showScenePreview(self, index):
        self.tableView_scenes.setCurrentIndex(index)
        self.listView_filmStrip.setCurrentIndex(index)
        self.scene_index = index.row()
        scene = self.mvshow.sequence.item(self.scene_index).data()
        self.label_mediaPreview.setPixmap(scalePixmapToWidget(self.label_mediaPreview, getPixmapFromScene(scene)))
        self.textEdit_notes.setText(scene.notes)

    def updateSceneNotes(self):
        scene = self.mvshow.sequence.item(self.scene_index).data()
        scene.notes = self.textEdit_notes.toPlainText()


class Ui_presenterView(QtWidgets.QWidget, Ui_Form_presenterView):
    def __init__(self, parent: Ui_mainWindow):
        QtWidgets.QWidget.__init__(self)
        self.parent = parent
        self.setupUi(self)

        self.mv = Ui_multiVisionShow(parent=self)
        self.current_scene = 0
        self.audio_volume = float(1)

        self.pushButton_play.clicked.connect(self.startShow)
        self.pushButton_previousView.clicked.connect(lambda x: self.changeScene("prev"))
        self.pushButton_nextView.clicked.connect(lambda x: self.changeScene("next"))
        self.pushButton_audio_mute.clicked.connect(lambda x: self.controlAudio("mute"))
        self.pushButton_audio_quiet.clicked.connect(lambda x: self.controlAudio("quiet"))
        self.pushButton_audio_fadeIn.clicked.connect(lambda x: self.controlAudio("fade_in"))
        self.pushButton_audio_fadeOut.clicked.connect(lambda x: self.controlAudio("fade_out"))

        self.dial_volume.valueChanged.connect(lambda x: self.controlAudio("volume"))

        self.fade_in_anim = QtCore.QPropertyAnimation(self.mv.audioOutput, b"volume")
        self.fade_in_anim.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)
        self.fade_in_anim.setKeyValueAt(0.01, 0.01)

        self.fade_out_anim = QtCore.QPropertyAnimation(self.mv.audioOutput, b"volume")
        self.fade_out_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self.fade_out_anim.setKeyValueAt(0.01, self.audio_volume)

        self.fade_in_anim.finished.connect(self.fadeInFinished)
        self.fade_in_anim.finished.connect(lambda: self.uncheckPushButton(self.pushButton_audio_fadeIn))
        self.fade_out_anim.finished.connect(self.fadeOutFinished)
        self.fade_out_anim.finished.connect(lambda: self.uncheckPushButton(self.pushButton_audio_fadeOut))

        self.updateDialPosition()
        self.changeScene("first")

    def uncheckPushButton(self, button: QtWidgets.QPushButton):
        button.setChecked(False)

    def fadeInFinished(self):
        self.enableAudioButtons()
        self.updateDialPosition()

    def fadeOutFinished(self):
        self.enableAudioButtons()
        self.updateDialPosition()

    def disableAudioButtons(self):
        self.pushButton_audio_fadeIn.setEnabled(False)
        self.pushButton_audio_fadeOut.setEnabled(False)
        self.pushButton_audio_mute.setEnabled(False)
        self.pushButton_audio_quiet.setEnabled(False)

    def enableAudioButtons(self):
        self.pushButton_audio_fadeIn.setEnabled(True)
        self.pushButton_audio_fadeOut.setEnabled(True)
        self.pushButton_audio_quiet.setEnabled(True)
        self.pushButton_audio_mute.setEnabled(True)

    def updateDialPosition(self):
        # self.dial_volume.setValue(int(round(100 ** self.audio_volume, 0)))
        self.dial_volume.setValue(int(round(self.mv.audioOutput.volume() * 100)))

    def controlAudio(self, action):
        if action == "mute":
            if self.pushButton_audio_mute.isChecked():
                self.mv.audioOutput.setMuted(True)
                self.pushButton_audio_fadeOut.setEnabled(False)
                self.pushButton_audio_quiet.setEnabled(False)
            else:
                self.mv.audioOutput.setMuted(False)
                self.pushButton_audio_fadeOut.setEnabled(True)
                self.pushButton_audio_quiet.setEnabled(True)
        elif action == "quiet":
            if self.pushButton_audio_quiet.isChecked():
                self.pushButton_audio_fadeIn.setEnabled(False)
                self.pushButton_audio_fadeOut.setEnabled(False)
                self.pushButton_audio_mute.setEnabled(False)

                self.fade_out_anim.setDuration(500)
                self.fade_out_anim.setStartValue(self.mv.audioOutput.volume())
                self.fade_out_anim.setEndValue(self.mv.audioOutput.volume() / 8)
                self.fade_out_anim.start()
            else:
                self.fade_in_anim.setDuration(500)
                self.fade_in_anim.setStartValue(self.mv.audioOutput.volume())
                self.fade_in_anim.setEndValue(self.mv.audioOutput.volume() * 8)
                self.fade_in_anim.start()
        elif action == "fade_in":
            if self.pushButton_audio_mute.isChecked():
                self.mv.audioOutput.setMuted(False)
                self.pushButton_audio_mute.setChecked(False)

            self.disableAudioButtons()

            self.fade_in_anim.setDuration(self.spinBox_audio_fadeTime.value() * 1000)
            self.fade_in_anim.setStartValue(self.mv.audioOutput.volume())
            self.fade_in_anim.setEndValue(1)
            self.fade_in_anim.start()
        elif action == "fade_out":
            self.disableAudioButtons()

            self.fade_out_anim.setDuration(self.spinBox_audio_fadeTime.value() * 1000)
            self.fade_out_anim.setStartValue(self.mv.audioOutput.volume())
            self.fade_out_anim.setEndValue(0)
            self.fade_out_anim.start()
        elif action == "volume":
            # self.audio_volume = math.log(self.dial_volume.value(), 100)
            self.mv.audioOutput.setVolume(self.dial_volume.value() / 100)

    def changeScene(self, action, index=None):
        length = self.parent.mvshow.length()

        if length == 0:
            return False

        if action == "first":
            self.current_scene = 0
        elif action == "prev" and self.current_scene > 0:
            self.current_scene -= 1
        elif action == "next" and self.current_scene < (length - 1):
            self.current_scene += 1
        elif action == "seek" and type(index) is int and 0 <= index < length:
            self.current_scene = index
        else:
            return False

        scene = self.parent.mvshow.getScene(self.current_scene)
        prev_scene = self.parent.mvshow.getScene(self.current_scene - 1) if self.current_scene > 0 else None
        next_scene = self.parent.mvshow.getScene(self.current_scene + 1) if self.current_scene < (length - 1) else None

        self.label_sceneCounter.setText(f"{self.current_scene + 1}/{length}")
        self.updatePresenterView(scene, prev_scene, next_scene)

        if self.parent.mvshow.state in (Show_States.RUNNING, Show_States.PAUSED):
            self.mv.loadScene(scene)

    def startShow(self):
        self.mv.show()
        self.parent.mvshow.state = Show_States.RUNNING
        self.changeScene("first")

    def pauseShow(self):
        self.parent.mvshow.state = Show_States.PAUSED

    def updatePresenterView(self, scene, prev_scene, next_scene):
        self.label_currentView.setPixmap(scalePixmapToWidget(self.label_currentView, getPixmapFromScene(scene)))
        self.label_previousView.setPixmap(scalePixmapToWidget(self.label_previousView, getPixmapFromScene(prev_scene)))
        self.label_nextView.setPixmap(scalePixmapToWidget(self.label_nextView, getPixmapFromScene(next_scene)))


def get_supported_mime_types() -> list:
    result = []
    for f in QtMultimedia.QMediaFormat().supportedFileFormats(QtMultimedia.QMediaFormat.ConversionMode.Decode):
        mime_type = QtMultimedia.QMediaFormat(f).mimeType()
        result.append(mime_type.name())
    return result


def scalePixmapToWidget(widget: QtWidgets.QWidget,
                        pixmap: QtGui.QPixmap,
                        mode=QtCore.Qt.TransformationMode.FastTransformation):
    window_size = widget.size()
    scaled_pixmap = pixmap.scaled(
        window_size,
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        mode)

    return scaled_pixmap


class Ui_multiVisionShow(QtWidgets.QWidget, Ui_Form_multiVisionShow):
    def __init__(self, parent: Ui_presenterView):
        QtWidgets.QWidget.__init__(self)
        self.setupUi(self)
        self.parent = parent
        self.installEventFilter(self)
        self.videoPlayer = QtMultimedia.QMediaPlayer(parent=self)
        self.audioPlayer = QtMultimedia.QMediaPlayer(parent=self)
        self.audioOutput = QtMultimedia.QAudioOutput(parent=self)
        self.supported_mimetypes = get_supported_mime_types()

        self.videoPlayer.setVideoOutput(self.videoWidget)
        self.videoPlayer.setAudioOutput(self.audioOutput)
        self.videoWidget.setGeometry(self.label_image.geometry())
        self.videoWidget.setAspectRatioMode(QtCore.Qt.AspectRatioMode.KeepAspectRatio)

        self.audioPlayer.setAudioOutput(self.audioOutput)
        self.audioPlayer.setLoops(QtMultimedia.QMediaPlayer.Loops.Infinite)

    def eventFilter(self, source, event):
        if source is self and event.type() in (
                QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Move, QtCore.QEvent.Type.Show):
            window_size = self.size()
            self.label_image.hide()
            self.label_image.move(0, 0)
            self.label_image.setFixedSize(window_size)
            if self.label_image.pixmap():
                self.label_image.setPixmap(scalePixmapToWidget(
                    self.label_image,
                    self.label_image.pixmap(),
                    QtCore.Qt.TransformationMode.SmoothTransformation))
            self.videoWidget.hide()
            self.videoWidget.move(0, 0)
            self.videoWidget.setFixedSize(window_size)
        return super(Ui_multiVisionShow, self).eventFilter(source, event)

    def loadScene(self, scene: Mv_Scene):
        if scene.scene_type == Scene_Type.STILL:
            if not scene.pixmap:
                scene.pixmap.load(scene.source)
            self.videoPlayer.stop()
            self.videoWidget.hide()
            self.label_image.setPixmap(scalePixmapToWidget(self.label_image,
                                                           scene.pixmap,
                                                           QtCore.Qt.TransformationMode.SmoothTransformation))
            self.label_image.show()
            self.label_image.raise_()
        elif scene.scene_type == Scene_Type.VIDEO:
            self.label_image.hide()
            # TODO: Check if MIME Type of scene.source is supported and the file exists
            self.videoPlayer.setSource(QtCore.QUrl.fromLocalFile(scene.source))
            self.videoPlayer.play()
            self.videoWidget.show()
            self.videoWidget.raise_()

        if scene.audio_source:
            # TODO: Check if MIME Type of scene.audio_source is supported and the file exists
            audio_url = QtCore.QUrl.fromLocalFile(scene.audio_source)
            prev_audio_url = self.audioPlayer.source()

            if audio_url != prev_audio_url:
                self.audioPlayer.setSource(audio_url)
                self.audioPlayer.play()
        else:
            self.audioPlayer.stop()
            self.audioPlayer.setSource(QtCore.QUrl())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("fusion")
    ui = Ui_mainWindow()

    if len(sys.argv) > 1:
        ui.loadFromFile(sys.argv[1])

    ui.show()
    sys.exit(app.exec())
