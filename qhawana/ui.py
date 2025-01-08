import gzip
import json
import mimetypes
import os
import sys
import qtmodern.styles

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from _typeshed import SupportsWrite

import av
import exiftool
from PyQt6 import QtWidgets, QtMultimedia, QtCore, QtGui, QtMultimediaWidgets

from qhawana.const import Constants, Scene_Type, Show_States
from qhawana.model import Mv_Project, Mv_Scene
from qhawana.ui_mainWindow import Ui_mainWindow_Qhawana
from qhawana.ui_multiVisionShow import Ui_Form_multiVisionShow
from qhawana.ui_presenterView import Ui_Form_presenterView
from qhawana.utils import get_supported_mime_types, getKeyframeFromVideo, scalePixmapToWidget, timeStringFromMsec
from qhawana.worker import Worker


class Ui_mainWindow(QtWidgets.QMainWindow, Ui_mainWindow_Qhawana):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.setupUi(self)

        self.pushButton_playPausePreview.setIcon(
            self.pushButton_playPausePreview.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))

        self.project = Mv_Project()
        self.project.bin.clear()
        self.mv_show = self.project.mv_show
        self.pv = None
        self.save_file = None
        self.changes_saved = True
        self.supported_mime_types = get_supported_mime_types()
        self.scene_index = 0

        self.videoPreviewPlayer = QtMultimedia.QMediaPlayer(parent=self)
        self.videoPreviewPlayer.setVideoOutput(self.videoPreviewWidget)
        self.videoPreviewPlayer.durationChanged.connect(self.horizontalSlider_videoPosition.setMaximum)
        self.pushButton_playPausePreview.clicked.connect(self.playPauseVideoPreview)
        self.pushButton_inPoint.clicked.connect(self.setVideoInPoint)
        self.pushButton_outPoint.clicked.connect(self.setVideoOutPoint)
        self.videoTimer = QtCore.QTimer()

        self.listView_filmStrip.setModel(self.mv_show.sequence)
        self.tableView_scenes.setModel(self.mv_show.sequence)
        self.tableView_scenes.setSelectionMode(self.tableView_scenes.SelectionMode.ContiguousSelection)
        self.tableView_scenes.setSelectionBehavior(self.tableView_scenes.SelectionBehavior.SelectRows)
        self.tableView_scenes.setDragDropMode(self.tableView_scenes.DragDropMode.DragDrop)
        '''
        dragDropOverwriteMode : bool  
        If its value is true, the selected data will overwrite the existing item data when dropped,
        while moving the data will clear the item. If its value is false, the selected data will be inserted
        as a new item when the data is dropped. When the data is moved, the item is removed as well.
        '''
        self.tableView_scenes.setDragDropOverwriteMode(False)
        self.tableView_scenes.setAcceptDrops(True)
        self.tableView_scenes.setSortingEnabled(True)

        self.treeView.setModel(self.project.bin)
        self.treeView.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

        self.threadpool = QtCore.QThreadPool().globalInstance()
        QtCore.qInfo("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())
        QtCore.qInfo("Supported media MIME types: %s" % self.supported_mime_types)

        self.screens = app.screens()
        for i, s in enumerate(self.screens):
            QtCore.qInfo(f"Found screen {i} in {s.orientation().name} with resolution "
                         f"{s.availableGeometry().width()}x{s.availableGeometry().height()}.")

        if len(self.screens) > 1:
            qr = self.screens[0].geometry()
            self.move(qr.left(), qr.top())

        self.pushButton_mediaSourceDirectory.clicked.connect(self.sceneFromDirectoryDialog)
        self.pushButton_startShow.clicked.connect(self.openPresenterView)
        self.mv_show.sequence.dataChanged.connect(self.changed)
        self.mv_show.sequence.layoutChanged.connect(self.changed)
        self.mv_show.sequence.rowsInserted.connect(self.changed)
        self.mv_show.sequence.rowsRemoved.connect(self.changed)
        self.project.settings.valueChanged.connect(self.changed)
        self.mv_show.sequence.rowsRemoved.connect(self.showScenePreview)
        self.tableView_scenes.selectionModel().selectionChanged.connect(self.syncSelection)
        self.tableView_scenes.selectionModel().selectionChanged.connect(self.showScenePreview)
        self.listView_filmStrip.selectionModel().selectionChanged.connect(self.syncSelection)
        self.listView_filmStrip.selectionModel().selectionChanged.connect(self.showScenePreview)
        self.treeView.selectionModel().selectionChanged.connect(self.showBinPreview)
        self.mv_show.sequence.rowsInserted.connect(self.tableView_scenes.resizeColumnsToContents)
        self.textEdit_notes.textChanged.connect(self.updateSceneNotes)
        self.actionNew.triggered.connect(self.newProject)
        self.actionOpen.triggered.connect(self.loadFromFile)
        self.actionSave.triggered.connect(self.saveToFile)
        self.actionSave_As.triggered.connect(self.saveAsFileDialog)
        self.actionQuit.triggered.connect(self.quitProject, QtCore.Qt.ConnectionType.QueuedConnection)
        self.actionAbout_Qhawana.triggered.connect(splash_screen.show)

        self.spinBox_transitionTime.valueChanged.connect(
            lambda x: self.project.settings.setProperty("transition_time", x))
        self.spinBox_defaultDelay.valueChanged.connect(
            lambda x: self.project.settings.setProperty("default_delay", x))

    def resizeEvent(self, event):
        # Override QMainWindow's resizeEvent handler to
        # repaint the scene preview if the window size has changed
        # self.showScenePreview(self.listView_filmStrip.selectionModel().selection().indexes())
        QtWidgets.QMainWindow.resizeEvent(self, event)

    def closeEvent(self, event):
        # Override QMainWindow's closeEvent handler to
        # ignore the close event and call quitProject instead to handle unsaved changes
        event.ignore()
        self.quitProject()

    def newProject(self):
        if self.changes_saved:
            self.project.bin.clear()
            self.mv_show.sequence.clear()
            self.mv_show.sequence.__init__()
            self.save_file = None
            self.scene_index = 0
            self.resetProgressBar()
        else:
            answer = self.saveChangesDialog()

            if answer == QtWidgets.QMessageBox.StandardButton.Save:
                if self.saveToFile():
                    self.newProject()
                else:
                    QtCore.qWarning("Could not save project.")
            elif answer == QtWidgets.QMessageBox.StandardButton.Discard:
                self.changes_saved = True
                self.radioButton_changes.setChecked(False)

                self.newProject()
            else:
                # In case the user selected "Cancel", do nothing:
                pass

    def quitProject(self):
        if self.changes_saved:
            app.quit()
        else:
            answer = self.saveChangesDialog()

            if answer == QtWidgets.QMessageBox.StandardButton.Save:
                self.saveToFile()
            elif answer == QtWidgets.QMessageBox.StandardButton.Discard:
                self.changes_saved = True
                self.radioButton_changes.setChecked(False)

                app.quit()
            else:
                # In case the user selected "Cancel", do nothing:
                pass

    def saveAsFileDialog(self):
        file_name = QtWidgets.QFileDialog.getSaveFileName(self, "Save project to file")[0]
        if file_name:
            self.save_file = file_name
            self.saveToFile()

    def saveToFile(self):
        if self.save_file:
            self.lockSequence()

            self.progressBar.setEnabled(True)
            self.progressBar.setTextVisible(True)

            worker = Worker(self.saveProjectToFile, self.save_file)
            worker.signals.progress.connect(self.progressBar.setValue)
            worker.signals.finished.connect(self.resetProgressBar)
            worker.signals.finished.connect(self.unlockSequence)
            self.threadpool.start(worker)

            self.changes_saved = True
            self.radioButton_changes.setChecked(False)

            return True
        else:
            self.saveAsFileDialog()

    def loadFromFile(self, file_name=""):
        if self.changes_saved:
            if not file_name:
                file_name = QtWidgets.QFileDialog.getOpenFileName(self, "Select project file")[0]
            if file_name:
                self.lockSequence()

                self.progressBar.setEnabled(True)
                self.progressBar.setTextVisible(True)

                worker = Worker(self.loadProjectFromFile, file_name)
                worker.signals.progress.connect(self.progressBar.setValue)
                worker.signals.finished.connect(self.resetProgressBar)
                worker.signals.finished.connect(self.unlockSequence)
                self.threadpool.start(worker)

                self.changes_saved = True
                self.radioButton_changes.setChecked(False)
        else:
            answer = self.saveChangesDialog()

            if answer == QtWidgets.QMessageBox.StandardButton.Save:
                self.saveToFile()
            elif answer == QtWidgets.QMessageBox.StandardButton.Discard:
                self.changes_saved = True
                self.radioButton_changes.setChecked(False)

                self.loadFromFile(file_name)
            else:
                # In case the user selected "Cancel", do nothing:
                pass

    def saveChangesDialog(self):
        popup = QtWidgets.QMessageBox(self)
        popup.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        popup.setText("The project has unsaved changes")
        popup.setInformativeText("Would you like to save your changes?")
        popup.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Save |
                                 QtWidgets.QMessageBox.StandardButton.Cancel |
                                 QtWidgets.QMessageBox.StandardButton.Discard)
        popup.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Save)
        popup.setModal(True)
        answer = popup.exec()

        return answer

    def saveProjectToFile(self, file_name, progress_callback):
        f: SupportsWrite[str]
        with gzip.open(file_name, 'wt', encoding='ascii') as f:
            settings = self.project.settings.toJson()
            project_bin = self.project.bin.toJson(progress_callback)
            show = self.mv_show.toJson(progress_callback)
            json.dump(settings | project_bin | show, f)

    def loadProjectFromFile(self, file_name, progress_callback):
        QtCore.qInfo(f"Loading project from file {file_name}")

        try:
            with gzip.open(file_name, 'r') as f:
                json_string = json.load(f)
        except gzip.BadGzipFile:
            with open(file_name) as f:
                json_string = json.load(f)

        if "settings" in json_string:
            QtCore.qDebug(f"Loading project settings {json_string['settings']}")
            self.project.settings.fromJson(json_string["settings"])
            if self.project.settings.getProperty("default_delay"):
                self.spinBox_defaultDelay.setValue(self.project.settings.getProperty("default_delay"))
            if self.project.settings.getProperty("transition_time"):
                self.spinBox_transitionTime.setValue(self.project.settings.getProperty("transition_time"))

        if "project_bin" in json_string:
            self.project.bin.fromJson(json_string["project_bin"], progress_callback)

        if "scenes" in json_string:
            QtCore.qDebug(f"Loading {len(json_string['scenes'])} scenes")
            self.mv_show.fromJson(json_string["scenes"], progress_callback)

        QtCore.qInfo(f"Project loaded from file {file_name}")

        self.save_file = file_name
        self.changes_saved = True
        self.radioButton_changes.setChecked(False)

    def sceneFromDirectoryDialog(self):
        dir_name = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Media Source Directory")
        if dir_name:
            self.textEdit_mediaSourceDirectory.setText(dir_name)
            self.progressBar.setEnabled(True)
            self.progressBar.setTextVisible(True)

            worker = Worker(self.populateModelFromDirectory, dir_name)
            worker.signals.progress.connect(self.progressBar.setValue)
            worker.signals.finished.connect(self.resetProgressBar)
            self.threadpool.start(worker)

    def populateModelFromDirectory(self, dir_name, progress_callback):
        directory = sorted(os.listdir(dir_name))
        num_files = len(directory)

        for index, file in enumerate(directory):
            progress_callback.emit((index + 1) // num_files * 100)

            path = os.path.join(dir_name, file)

            if os.path.isdir(path) or os.path.islink(path):
                # TODO: Consider the option to work recursively and/or process symlinks
                continue

            if os.path.isfile(path) and (
                    path.endswith(".xmp") or
                    path.endswith(".pmv")
            ):
                # We are not interested in certain files like XMP or our own project files
                continue

            mimetype, encoding = mimetypes.guess_type(path)

            if mimetype is None:
                QtCore.qWarning(f"Failed to get Mimetype for {file}.")
                # TODO: Could there be cases where we would want to process
                #  the file even if we don't know the MIME type?
                continue

            if mimetype.startswith("image/"):
                audio_path = ""
                pixmap = QtGui.QPixmap(path)

                exif_data = exiftool.ExifToolHelper().get_metadata(path)[0]
                scene = Mv_Scene(source=path,
                                 audio_source=audio_path,
                                 pixmap=pixmap.scaled(Constants.MV_PREVIEW_SIZE, Constants.MV_PREVIEW_SIZE,
                                                      QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                                      QtCore.Qt.TransformationMode.SmoothTransformation),
                                 scene_type=Scene_Type.STILL,
                                 exif=exif_data)
                QtCore.qDebug(f"Adding image scene from file {path}")

                bin_item = QtGui.QStandardItem(file)
                bin_item.setData(path, QtCore.Qt.ItemDataRole.UserRole)
                bin_item.setDragEnabled(True)
                bin_item.setDropEnabled(False)

                parent = self.project.bin.findItems("STILLS", QtCore.Qt.MatchFlag.MatchExactly, 0)[0]
                parent.appendRow(bin_item)

                QtCore.qDebug(f"Adding image file {path} to project bin")
            elif mimetype.startswith("video/") and mimetype in self.supported_mime_types:
                keyframe_image = getKeyframeFromVideo(path)
                pixmap = QtGui.QPixmap().fromImage(keyframe_image)

                with av.open(path) as container:
                    if len(container.streams.video) == 0:
                        QtCore.qDebug(f"Video file {path} does not contain a video stream")
                        continue

                    # Set scene's play_video_audio property to True if the video has an audio stream:
                    play_video_audio = (len(container.streams.audio) > 0)

                    stream = container.streams.video[0]
                    duration = int(stream.duration * stream.time_base * 1000)
                    in_point = int(stream.start_time * stream.time_base * 1000)
                    out_point = duration - in_point

                exif_data = exiftool.ExifToolHelper().get_metadata(path)[0]
                scene = Mv_Scene(source=path,
                                 pixmap=pixmap.scaled(Constants.MV_PREVIEW_SIZE, Constants.MV_PREVIEW_SIZE,
                                                      QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                                      QtCore.Qt.TransformationMode.SmoothTransformation),
                                 scene_type=Scene_Type.VIDEO,
                                 exif=exif_data,
                                 duration=duration,
                                 in_point=in_point,
                                 out_point=out_point,
                                 play_video_audio=play_video_audio)
                QtCore.qDebug(f"Adding video scene from file {path} with duration {duration} ms, "
                              f"in point {in_point} ms and out point {out_point} ms")

                bin_item = QtGui.QStandardItem(file)
                bin_item.setData(path, QtCore.Qt.ItemDataRole.UserRole)

                bin_item.setDragEnabled(True)
                bin_item.setDropEnabled(False)

                parent = self.project.bin.findItems("VIDEO", QtCore.Qt.MatchFlag.MatchExactly, 0)[0]
                parent.appendRow(bin_item)

                QtCore.qDebug(f"Adding video file {path} to project bin")
            elif mimetype.startswith("audio/"):
                bin_item = QtGui.QStandardItem(file)
                bin_item.setData(path, QtCore.Qt.ItemDataRole.UserRole)
                bin_item.setDragEnabled(True)
                bin_item.setDropEnabled(False)

                parent = self.project.bin.findItems("AUDIO", QtCore.Qt.MatchFlag.MatchExactly, 0)[0]
                parent.appendRow(bin_item)

                QtCore.qDebug(f"Adding audio file {path} to project bin")
                # Audio items will only be added to the project bin, but no scene item will be created, so continue:
                continue
            else:
                QtCore.qInfo(f"File {file.encode(errors='ignore')} ({mimetype}) is not supported.")
                # Files with MIME types that we do not understand will be ignored, so continue:
                continue

            scene_item = QtGui.QStandardItem(file)
            scene_item.setData(scene)
            scene_item.setDropEnabled(False)

            self.mv_show.sequence.appendRow(scene_item)

        return True

    def resetProgressBar(self):
        self.progressBar.setEnabled(False)
        self.progressBar.setTextVisible(False)
        self.progressBar.setValue(0)

    def lockSequence(self):
        self.tableView_scenes.setEnabled(False)
        self.listView_filmStrip.setEnabled(False)

    def unlockSequence(self):
        self.tableView_scenes.setEnabled(True)
        self.listView_filmStrip.setEnabled(True)

    def openPresenterView(self):
        if self.mv_show.length() > 0:
            self.pv = Ui_presenterView(parent=self)
            if len(self.screens) > 1:
                qr = self.screens[0].geometry()
                self.pv.move(qr.left(), qr.top())
            self.pv.show()
        else:
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle("Empty MultiVision show!")
            dialog.setText("Please add scenes first.")
            dialog.exec()

    def showBinPreview(self, selection):
        if isinstance(selection, QtCore.QItemSelection) and len(selection.indexes()) > 0:
            bin_index = selection.indexes()[0]
        elif isinstance(selection, QtCore.QModelIndex):
            bin_index = selection
        else:
            return

        if bin_index.isValid():
            self.horizontalSlider_videoPosition.setValue(0)
            self.pushButton_playPausePreview.setChecked(False)
            self.pushButton_inPoint.setEnabled(False)
            self.pushButton_outPoint.setEnabled(False)

            bin_item = self.project.bin.itemFromIndex(bin_index)
            parent = bin_item.parent() if bin_item else None

            if parent:
                parent_type = parent.data(QtCore.Qt.ItemDataRole.DisplayRole)
                QtCore.qDebug(f"Showing preview for {parent_type} item {bin_index.row()} "
                              f"({self.project.bin.rowCount(parent.index())} items in bin)")

                if parent_type == "STILLS":
                    self.stackedWidget_preview.setCurrentIndex(0)
                    self.pushButton_playPausePreview.setEnabled(False)
                    self.horizontalSlider_videoPosition.setEnabled(False)
                    self.videoPreviewPlayer.stop()
                    self.videoPreviewPlayer.setSource(QtCore.QUrl())

                    self.label_mediaPreview.setPixmap(
                        scalePixmapToWidget(self.label_mediaPreview,
                                            QtGui.QPixmap(bin_item.data(QtCore.Qt.ItemDataRole.UserRole))))
                elif parent_type == "VIDEO":
                    self.stackedWidget_preview.setCurrentIndex(1)
                    self.pushButton_playPausePreview.setEnabled(True)
                    self.horizontalSlider_videoPosition.setEnabled(True)

                    # TODO: Check if MIME Type of scene.source is supported and the file exists
                    self.videoPreviewPlayer.setSource(
                        QtCore.QUrl.fromLocalFile(bin_item.data(QtCore.Qt.ItemDataRole.UserRole)))
                    self.videoPreviewPlayer.play()
                    self.videoTimer.singleShot(100, self.videoPreviewPlayer.pause)
        else:
            QtCore.qDebug("Invalid index, not showing preview")

    def showScenePreview(self, selection):
        if isinstance(selection, QtCore.QItemSelection) and len(selection.indexes()) > 0:
            scene_index = selection.indexes()[0]
        elif isinstance(selection, QtCore.QModelIndex):
            scene_index = selection
        else:
            return

        if scene_index.isValid():
            QtCore.qDebug(f"Showing preview for row {scene_index.row()} "
                          f"({self.mv_show.sequence.rowCount()} items in list, "
                          f"{self.mv_show.sequence.sceneCount()} scenes in show)")
            scene: Mv_Scene = self.mv_show.sequence.item(scene_index.row())

            if scene:
                self.scene_index = scene_index.row()

                self.horizontalSlider_videoPosition.setValue(0)
                self.pushButton_playPausePreview.setChecked(False)

                if scene.scene_type == Scene_Type.STILL:
                    self.stackedWidget_preview.setCurrentIndex(0)
                    self.pushButton_inPoint.setEnabled(False)
                    self.pushButton_outPoint.setEnabled(False)
                    self.pushButton_playPausePreview.setEnabled(False)
                    self.horizontalSlider_videoPosition.setEnabled(False)
                    self.videoPreviewPlayer.stop()
                    self.videoPreviewPlayer.setSource(QtCore.QUrl())

                    self.label_mediaPreview.setPixmap(scalePixmapToWidget(self.label_mediaPreview,
                                                                          getPixmapFromScene(scene)))
                elif scene.scene_type == Scene_Type.VIDEO:
                    self.stackedWidget_preview.setCurrentIndex(1)
                    self.pushButton_inPoint.setEnabled(True)
                    self.pushButton_outPoint.setEnabled(True)
                    self.pushButton_playPausePreview.setEnabled(True)
                    self.horizontalSlider_videoPosition.setEnabled(True)

                    # TODO: Check if MIME Type of scene.source is supported and the file exists
                    self.videoPreviewPlayer.setSource(QtCore.QUrl.fromLocalFile(scene.source))
                    self.videoPreviewPlayer.play()
                    if scene.in_point > 0:
                        self.videoPreviewPlayer.setPosition(scene.in_point)
                    self.videoTimer.singleShot(100, self.videoPreviewPlayer.pause)

                self.textEdit_notes.setText(scene.notes)
        else:
            QtCore.qDebug("Invalid index, not showing preview")

    def playPauseVideoPreview(self, checked):
        if checked:
            try:
                self.horizontalSlider_videoPosition.valueChanged.disconnect()
            except TypeError:
                pass
            self.videoPreviewPlayer.positionChanged.connect(self.manageVideoPositionSlider)

            self.horizontalSlider_videoPosition.setEnabled(False)
            self.videoPreviewPlayer.play()
        else:
            try:
                self.videoPreviewPlayer.positionChanged.disconnect()
            except TypeError:
                pass
            self.horizontalSlider_videoPosition.valueChanged.connect(self.manageVideoPositionSlider)

            self.horizontalSlider_videoPosition.setEnabled(True)
            self.videoPreviewPlayer.pause()

    def manageVideoPositionSlider(self, position=None):
        if self.videoPreviewPlayer.isPlaying():
            self.horizontalSlider_videoPosition.setValue(self.videoPreviewPlayer.position())

            scene = self.mv_show.sequence.item(self.scene_index)
            if position == scene.out_point:
                self.videoPreviewPlayer.pause()
        else:
            self.videoPreviewPlayer.setPosition(position)

    def setVideoInPoint(self):
        scene_index = self.mv_show.sequence.index(self.scene_index, 4)
        if scene_index.isValid():
            self.mv_show.sequence.setData(scene_index,
                                          self.horizontalSlider_videoPosition.value(),
                                          QtCore.Qt.ItemDataRole.EditRole)

    def setVideoOutPoint(self):
        scene_index = self.mv_show.sequence.index(self.scene_index, 5)
        if scene_index.isValid():
            self.mv_show.sequence.setData(scene_index,
                                          self.horizontalSlider_videoPosition.value(),
                                          QtCore.Qt.ItemDataRole.EditRole)

    def syncSelection(self, selection):
        indexes = selection.indexes()

        selection = QtCore.QItemSelection()
        selection_flags = (QtCore.QItemSelectionModel.SelectionFlag.Select |
                           QtCore.QItemSelectionModel.SelectionFlag.Rows)

        if len(indexes) > 0:
            for i in indexes:
                if i.isValid():
                    selection.select(i, i)
            if self.tableView_scenes.selectionModel().selection() != selection:
                # self.tableView_scenes.blockSignals(True)
                self.tableView_scenes.selectionModel().select(selection, selection_flags)
                # self.tableView_scenes.blockSignals(False)
            if self.listView_filmStrip.selectionModel().selection() != selection:
                # self.listView_filmStrip.blockSignals(True)
                self.listView_filmStrip.selectionModel().select(selection, selection_flags)
                # self.listView_filmStrip.blockSignals(False)

    def updateSceneNotes(self):
        scene = self.mv_show.sequence.item(self.scene_index)
        if scene:
            scene_data = scene
            scene_data.notes = self.textEdit_notes.toPlainText()

    def changed(self):
        self.changes_saved = False
        self.radioButton_changes.setChecked(True)


class Ui_presenterView(QtWidgets.QWidget, Ui_Form_presenterView):
    scene_changed = QtCore.pyqtSignal(int)

    def __init__(self, parent: Ui_mainWindow):
        QtWidgets.QWidget.__init__(self)
        self.parent = parent
        self.setupUi(self)

        self.installEventFilter(self)

        self.pushButton_audio_quiet.setIcon(
            self.pushButton_audio_quiet.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaVolume))
        self.pushButton_audio_mute.setIcon(
            self.pushButton_audio_mute.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaVolumeMuted))
        self.pushButton_play.setIcon(
            self.pushButton_play.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))
        self.pushButton_pause.setIcon(
            self.pushButton_pause.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPause))
        self.pushButton_nextView.setIcon(
            self.pushButton_nextView.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaSkipForward))
        self.pushButton_previousView.setIcon(
            self.pushButton_previousView.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaSkipBackward))

        self.mv = Ui_multiVisionShow(parent=self)
        self.current_scene = 0
        self.audio_volume = float(1)

        self.pushButton_play.clicked.connect(self.startShow)
        self.pushButton_pause.clicked.connect(self.pauseShow)
        self.pushButton_previousView.clicked.connect(self.pauseShow)
        self.pushButton_previousView.clicked.connect(lambda x: self.changeScene("prev"))
        self.pushButton_nextView.clicked.connect(self.pauseShow)
        self.pushButton_nextView.clicked.connect(lambda x: self.changeScene("next"))
        self.pushButton_audio_mute.clicked.connect(lambda x: self.controlAudio("mute"))
        self.pushButton_audio_quiet.clicked.connect(lambda x: self.controlAudio("quiet"))
        self.pushButton_audio_fadeIn.clicked.connect(lambda x: self.controlAudio("fade_in"))
        self.pushButton_audio_fadeOut.clicked.connect(lambda x: self.controlAudio("fade_out"))
        self.dial_volume.valueChanged.connect(lambda x: self.controlAudio("volume"))

        self.parent.mv_show.state_changed.connect(self.progressBar_state.setFormat)
        self.parent.mv_show.state_changed.connect(lambda x: self.scene_runner())
        self.scene_changed.connect(self.scene_runner)

        self.audio_fade_in_anim = QtCore.QPropertyAnimation(self.mv.musicAudioOutput, b"volume")
        self.audio_fade_in_anim.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)
        self.audio_fade_in_anim.setKeyValueAt(0.01, 0.01)

        self.audio_fade_out_anim = QtCore.QPropertyAnimation(self.mv.musicAudioOutput, b"volume")
        self.audio_fade_out_anim.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)
        self.audio_fade_out_anim.setKeyValueAt(0.01, 0.01)

        self.progress_animation = QtCore.QPropertyAnimation(self.progressBar_state, b"value")
        self.progress_animation.setEasingCurve(QtCore.QEasingCurve.Type.Linear)
        self.progress_animation.setStartValue(0)
        self.progress_animation.setEndValue(100)

        self.audio_fade_in_anim.finished.connect(self.fadeInFinished)
        self.audio_fade_in_anim.finished.connect(lambda: self.pushButton_audio_fadeIn.setChecked(False))
        self.audio_fade_out_anim.finished.connect(self.fadeOutFinished)
        self.audio_fade_out_anim.finished.connect(lambda: self.pushButton_audio_fadeOut.setChecked(False))

        self.scene_timer = QtCore.QTimer()

        self.updateDialPosition()
        self.changeScene("first")

    def close(self):
        self.parent.mv_show.set_state(Show_States.STOPPED)
        super().close()

    def eventFilter(self, source, event):
        if source is self and event.type() in (
                QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Move, QtCore.QEvent.Type.Show):
            # window_size = self.size()
            # self.gridLayout.move(0, 0)
            # self.gridLayout.setFixedSize(window_size)

            self.label_currentView.setPixmap(
                scalePixmapToWidget(self.label_currentView, self.label_currentView.pixmap()))
            self.label_previousView.setPixmap(
                scalePixmapToWidget(self.label_previousView, self.label_previousView.pixmap()))
            self.label_nextView.setPixmap(
                scalePixmapToWidget(self.label_nextView, self.label_nextView.pixmap()))
        return super(Ui_presenterView, self).eventFilter(source, event)

    def scene_runner(self, scene_index=None):
        if self.parent.mv_show.state() == Show_States.RUNNING:
            if scene_index is None:
                self.mv.scene_fade_out_anim.start()
                QtCore.qDebug(f"Fading out scene {self.current_scene}")
            else:
                scene = self.parent.mv_show.getScene(scene_index)
                if scene.duration > 0 or scene.duration == -1:
                    if 0 <= scene.in_point < scene.out_point:
                        duration = scene.out_point - scene.in_point
                    elif scene.duration == -1:
                        duration = self.parent.project.settings.getProperty("default_delay")
                    else:
                        duration = scene.duration
                    self.progress_animation.setDuration(duration)
                    self.progress_animation.start()

                    try:
                        self.scene_timer.disconnect()
                    except TypeError:
                        pass
                    self.scene_timer.stop()
                    self.scene_timer.timeout.connect(self.scene_runner)
                    self.scene_timer.setSingleShot(True)
                    self.scene_timer.start(duration)

                    QtCore.qDebug(f"Running scene {self.current_scene} for {timeStringFromMsec(duration)}")
        else:
            self.progress_animation.stop()
            self.scene_timer.stop()

    def changeScene(self, action, index=None):
        length = self.parent.mv_show.length()

        if length == 0:
            return False

        if action == "first":
            self.current_scene = 0
        elif action == "prev" and self.current_scene > 0:
            self.current_scene -= 1
        elif action == "next" and self.current_scene < (length - 1):
            self.current_scene += 1
        elif action == "seek" and type(index) is int and 0 <= index < length and index != self.current_scene:
            self.current_scene = index
        else:
            return False

        scene = self.parent.mv_show.getScene(self.current_scene)
        prev_scene = self.parent.mv_show.getScene(self.current_scene - 1) if self.current_scene > 0 else None
        next_scene = self.parent.mv_show.getScene(self.current_scene + 1) if self.current_scene < (length - 1) else None

        self.label_sceneCounter.setText(f"{self.current_scene + 1}/{length}")
        self.updatePresenterView(scene, prev_scene, next_scene)

        if self.parent.mv_show.state() in (Show_States.RUNNING, Show_States.PAUSED, Show_States.FINISHED):
            self.mv.loadScene(scene)
            if self.parent.mv_show.state() == Show_States.RUNNING and self.current_scene >= (length - 1):
                self.parent.mv_show.set_state(Show_States.FINISHED)

        QtCore.qDebug(f"Changing scene to {self.current_scene}")
        self.scene_changed.emit(self.current_scene)

        return True

    def fadeInFinished(self):
        QtCore.qDebug(f"Audio fade in for scene {self.current_scene} is finished")
        self.enableAudioButtons()
        self.updateDialPosition()

    def fadeOutFinished(self):
        QtCore.qDebug(f"Audio fade out for scene {self.current_scene} is finished")
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
        self.dial_volume.setValue(int(round(self.mv.musicAudioOutput.volume() * 100)))

    def controlAudio(self, action):
        if action == "mute":
            if self.pushButton_audio_mute.isChecked():
                self.mv.musicAudioOutput.setMuted(True)
                self.pushButton_audio_fadeOut.setEnabled(False)
                self.pushButton_audio_quiet.setEnabled(False)
            else:
                self.mv.musicAudioOutput.setMuted(False)
                self.pushButton_audio_fadeOut.setEnabled(True)
                self.pushButton_audio_quiet.setEnabled(True)
        elif action == "quiet":
            if self.pushButton_audio_quiet.isChecked():
                self.pushButton_audio_fadeIn.setEnabled(False)
                self.pushButton_audio_fadeOut.setEnabled(False)
                self.pushButton_audio_mute.setEnabled(False)

                self.audio_fade_out_anim.setDuration(500)
                self.audio_fade_out_anim.setStartValue(self.mv.musicAudioOutput.volume())
                self.audio_fade_out_anim.setEndValue(self.audio_volume / 8)
                self.audio_fade_out_anim.start()
            else:
                self.audio_fade_in_anim.setDuration(500)
                self.audio_fade_in_anim.setStartValue(self.mv.musicAudioOutput.volume())
                self.audio_fade_in_anim.setEndValue(self.audio_volume)
                self.audio_fade_in_anim.start()
        elif action == "fade_in":
            if self.pushButton_audio_mute.isChecked():
                self.mv.musicAudioOutput.setMuted(False)
                self.pushButton_audio_mute.setChecked(False)

            self.disableAudioButtons()

            self.audio_fade_in_anim.setDuration(self.spinBox_audio_fadeTime.value() * 1000)
            self.audio_fade_in_anim.setStartValue(self.mv.musicAudioOutput.volume())
            self.audio_fade_in_anim.setEndValue(1)
            self.audio_fade_in_anim.start()
        elif action == "fade_out":
            self.disableAudioButtons()

            self.audio_fade_out_anim.setDuration(self.spinBox_audio_fadeTime.value() * 1000)
            self.audio_fade_out_anim.setStartValue(self.mv.musicAudioOutput.volume())
            self.audio_fade_out_anim.setEndValue(0)
            self.audio_fade_out_anim.start()
        elif action == "volume":
            # self.audio_volume = math.log(self.dial_volume.value(), 100)
            self.audio_volume = self.dial_volume.value() / 100
            self.mv.musicAudioOutput.setVolume(self.audio_volume)
        elif action == "stop":
            try:
                self.audio_fade_out_anim.finished.disconnect()
            except TypeError:
                pass
            self.mv.audioPlayer.stop()
            self.mv.audioPlayer.setSource(QtCore.QUrl())

    def startShow(self):
        state = self.parent.mv_show.state()
        try:
            self.mv.scene_fade_out_anim.finished.disconnect()
        except TypeError:
            pass
        self.mv.scene_fade_out_anim.finished.connect(lambda: self.changeScene("next"))

        if state in [Show_States.STOPPED, Show_States.FINISHED]:
            if len(self.parent.screens) > 1:
                QtCore.qDebug("There is more than one screen. Moving show window to next screen.")
                qr = self.parent.screens[1].geometry()
                self.mv.move(qr.left(), qr.top())
                # self.mv.showFullScreen()
            self.mv.show()
            self.parent.mv_show.set_state(Show_States.RUNNING)
        elif state == Show_States.PAUSED:
            self.parent.mv_show.set_state(Show_States.RUNNING)

    def pauseShow(self):
        if self.parent.mv_show.state() == Show_States.RUNNING:
            try:
                self.mv.scene_fade_out_anim.finished.disconnect()
            except TypeError:
                # A TypeError is raised if disconnect is called and there are no active connections
                pass

            self.parent.mv_show.set_state(Show_States.PAUSED)
            self.progressBar_state.setValue(0)
            # TODO: We could pause instead of stopping, but QTimer does not support pause and resume out of the box.

    def updatePresenterView(self, scene, prev_scene, next_scene):
        self.label_currentView.setPixmap(scalePixmapToWidget(self.label_currentView, getPixmapFromScene(scene)))
        self.label_previousView.setPixmap(scalePixmapToWidget(self.label_previousView, getPixmapFromScene(prev_scene)))
        self.label_nextView.setPixmap(scalePixmapToWidget(self.label_nextView, getPixmapFromScene(next_scene)))
        self.label_notes.setText(scene.notes)


class Ui_multiVisionShow(QtWidgets.QWidget, Ui_Form_multiVisionShow):
    def __init__(self, parent: Ui_presenterView):
        QtWidgets.QWidget.__init__(self)
        self.setupUi(self)
        self.parent = parent
        self.installEventFilter(self)

        self.videoPlayer = QtMultimedia.QMediaPlayer(parent=self)
        self.audioPlayer = QtMultimedia.QMediaPlayer(parent=self)
        self.videoAudioOutput = QtMultimedia.QAudioOutput(parent=self)
        self.musicAudioOutput = QtMultimedia.QAudioOutput(parent=self)

        self.videoPlayer.setAudioOutput(self.videoAudioOutput)
        self.audioPlayer.setAudioOutput(self.musicAudioOutput)
        self.audioPlayer.setLoops(QtMultimedia.QMediaPlayer.Loops.Infinite)

        self.supported_mimetypes = get_supported_mime_types()

        self.opacityEffect = QtWidgets.QGraphicsOpacityEffect()

        self.scene_fade_in_anim = QtCore.QPropertyAnimation(self.opacityEffect, b"opacity")
        self.scene_fade_in_anim.setEasingCurve(QtCore.QEasingCurve.Type.Linear)
        self.scene_fade_in_anim.setDuration(self.parent.parent.project.settings.getProperty("transition_time"))
        self.scene_fade_in_anim.setStartValue(0)
        self.scene_fade_in_anim.setEndValue(1)

        self.scene_fade_out_anim = QtCore.QPropertyAnimation(self.opacityEffect, b"opacity")
        self.scene_fade_out_anim.setEasingCurve(QtCore.QEasingCurve.Type.Linear)
        self.scene_fade_out_anim.setDuration(self.parent.parent.project.settings.getProperty("transition_time") // 4)
        self.scene_fade_out_anim.setStartValue(1)
        self.scene_fade_out_anim.setEndValue(0)

        # Declare to store and disconnect the signal-slot-connections for in point and out point of videos
        self.in_point_connection = None
        self.out_point_connection = None

    def close(self):
        self.videoPlayer.stop()
        self.audioPlayer.stop()
        super().close()

    def eventFilter(self, source, event):
        if source is self and event.type() in (
                QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Move, QtCore.QEvent.Type.Show):
            window_size = self.size()

            self.graphicsView.move(0, 0)
            self.graphicsView.setFixedSize(window_size)

        return super(Ui_multiVisionShow, self).eventFilter(source, event)

    def loadScene(self, scene: Mv_Scene):
        if scene.scene_type == Scene_Type.STILL:
            pixmap = QtGui.QPixmap()
            pixmap.load(scene.source)
            self.videoPlayer.stop()
            self.videoPlayer.setSource(QtCore.QUrl())

            image_item = QtWidgets.QGraphicsPixmapItem()
            image_item.setPixmap(scalePixmapToWidget(
                self.graphicsView,
                pixmap,
                QtCore.Qt.TransformationMode.SmoothTransformation))
            image_item.setGraphicsEffect(self.opacityEffect)
            graphics_scene = QtWidgets.QGraphicsScene()
            graphics_scene.addItem(image_item)

            self.graphicsView.items().clear()
            self.graphicsView.viewport().update()
            self.graphicsView.setScene(graphics_scene)

        elif scene.scene_type == Scene_Type.VIDEO:
            # TODO: Check if MIME Type of scene.source is supported and the file exists
            self.videoPlayer.setSource(QtCore.QUrl.fromLocalFile(scene.source))

            if self.in_point_connection:
                try:
                    self.videoPlayer.playbackStateChanged.disconnect(self.in_point_connection)
                except TypeError:
                    pass

            if self.out_point_connection:
                try:
                    self.videoPlayer.positionChanged.disconnect(self.out_point_connection)
                except TypeError:
                    pass

            if scene.in_point > 0:
                self.in_point_connection = self.videoPlayer.playbackStateChanged.connect(
                    lambda x: self.manageInPoint(scene.in_point))
            if scene.out_point > 0:
                self.out_point_connection = self.videoPlayer.positionChanged.connect(
                    lambda x: self.manageOutPoint(scene.out_point))

            if scene.play_video_audio and not self.parent.pushButton_audio_quiet.isChecked():
                self.parent.pushButton_audio_quiet.click()

            self.parent.parent.mv_show.state_changed.connect(self.manageVideoPlayback)

            video_item = QtMultimediaWidgets.QGraphicsVideoItem()
            video_item.setSize(self.graphicsView.size().toSizeF())
            video_item.setAspectRatioMode(QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            video_item.setGraphicsEffect(self.opacityEffect)
            self.videoPlayer.setVideoOutput(video_item)

            graphics_scene = QtWidgets.QGraphicsScene()
            graphics_scene.addItem(video_item)

            self.graphicsView.items().clear()
            self.graphicsView.viewport().update()
            self.graphicsView.setScene(graphics_scene)

            self.videoPlayer.play()

        self.scene_fade_in_anim.start()

        if scene.audio_source:
            # TODO: Check if MIME Type of scene.audio_source is supported and the file exists
            audio_url = QtCore.QUrl.fromLocalFile(scene.audio_source)
            prev_audio_url = self.audioPlayer.source()

            if audio_url != prev_audio_url:
                self.audioPlayer.setSource(audio_url)
                self.audioPlayer.play()
        else:
            self.parent.controlAudio("stop")

    def manageInPoint(self, pos):
        if self.videoPlayer.isSeekable() and self.videoPlayer.isPlaying():
            QtCore.qDebug(f"Setting video in point to {pos}")
            self.videoPlayer.setPosition(pos)

    def manageOutPoint(self, pos):
        if self.videoPlayer.position() >= pos:
            try:
                self.videoPlayer.playbackStateChanged.disconnect()
            except TypeError:
                pass
            QtCore.qDebug(f"Video out point reached at {pos}")
            self.videoPlayer.stop()

    def manageVideoPlayback(self):
        if self.parent.parent.mv_show.state() == Show_States.PAUSED:
            self.videoPlayer.pause()
        elif self.parent.parent.mv_show.state() == Show_States.RUNNING:
            self.videoPlayer.play()


def getPixmapFromScene(scene: Mv_Scene) -> QtGui.QPixmap:
    if scene:
        if type(scene.pixmap) is QtGui.QPixmap:
            pixmap = scene.pixmap
        else:
            if scene.scene_type == Scene_Type.STILL:
                pixmap = QtGui.QPixmap(scene.source)
            elif scene.scene_type == Scene_Type.VIDEO:
                image = getKeyframeFromVideo(scene.source)
                pixmap = QtGui.QPixmap().fromImage(image)
            else:
                pixmap = QtGui.QPixmap(100, 100)
                pixmap.fill(QtGui.QColor("black"))
    else:
        pixmap = QtGui.QPixmap(100, 100)
        pixmap.fill(QtGui.QColor("black"))

    return pixmap


def launcher(args, show_splash=True):
    if show_splash:
        splash_screen.show()
        splash_screen.finish(ui)

    if len(args) > 1:
        ui.loadFromFile(args[1])

    ui.show()
    app.exec()


app = QtWidgets.QApplication(sys.argv)
qtmodern.styles.dark(app)

splash_width = app.primaryScreen().geometry().width() // 2
splash_height = app.primaryScreen().geometry().height() // 2
splash_pixmap = QtGui.QPixmap("assets/Qhawana_Logo.png")

if splash_pixmap.width() > splash_width or splash_pixmap.height() > splash_height:
    splash_pixmap = splash_pixmap.scaled(splash_width, splash_height,
                                         QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                         QtCore.Qt.TransformationMode.SmoothTransformation)
splash_screen = QtWidgets.QSplashScreen(splash_pixmap)
splash_screen.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

ui = Ui_mainWindow()

if __name__ == "__main__":
    sys.exit(launcher(sys.argv))
