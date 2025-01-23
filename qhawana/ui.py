import gzip
import json
import faulthandler
import os
import sys

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _typeshed import SupportsWrite

from PySide6 import QtWidgets, QtMultimedia, QtCore, QtGui, QtMultimediaWidgets, QtQuickWidgets, QtPositioning

from qhawana.const import Constants, Scene_Type, Show_States
from qhawana.model import Mv_Project, Mv_Scene, BinItem, SceneItem, QhawanaGraphicsSceneItem
from qhawana.widgets import QhawanaSplash
from qhawana.ui_mainWindow import Ui_mainWindow_Qhawana
from qhawana.ui_multiVisionShow import Ui_Form_multiVisionShow
from qhawana.ui_presenterView import Ui_Form_presenterView
from qhawana.form_panAndZoom import Ui_Form_PanAndZoomEffect
from qhawana.utils import get_supported_mime_types, getKeyframeFromVideo, scalePixmapToWidget, timeStringFromMsec
from qhawana.utils import geoPathFromGPX
from qhawana.worker import Worker
from qhawana.map import PyQMLBridge
from qhawana.pan_and_zoom import pan_and_zoom

import importlib.resources

res = importlib.resources.files("resources")


class Ui_mainWindow(QtWidgets.QMainWindow, Ui_mainWindow_Qhawana):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self)
        self.setParent(parent)
        self.setupUi(self)

        self.setWindowIcon(QtGui.QIcon(str(res / "Qhawana_Icon_32.png")))
        self.label_applicationIcon.setPixmap(QtGui.QPixmap(str(res / "Qhawana_Icon_96.png")))

        self.pushButton_playPausePreview.setIcon(
            self.pushButton_playPausePreview.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))

        self.project = None
        self.scenes_selection_model = None
        self.bin_selection_model = None

        self.pv = Ui_presenterView(parent=self)
        self.changes_saved = True
        self.supported_mime_types = get_supported_mime_types()
        self.scene_index = 0

        self.videoPreviewPlayer = QtMultimedia.QMediaPlayer(parent=self)
        self.videoPreviewPlayer.durationChanged.connect(self.horizontalSlider_videoPosition.setMaximum)
        self.pushButton_playPausePreview.clicked.connect(self.playPauseVideoPreview)
        self.pushButton_inPoint.clicked.connect(self.setVideoInPoint)
        self.pushButton_outPoint.clicked.connect(self.setVideoOutPoint)
        self.videoTimer = QtCore.QTimer()

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

        self.treeView.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.treeView_selection = self.treeView.selectionModel()

        self.threadpool = QtCore.QThreadPool().globalInstance()
        QtCore.qDebug("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())
        QtCore.qDebug("Supported media MIME types: %s" % self.supported_mime_types)

        self.screens = app.screens()
        for i, s in enumerate(self.screens):
            QtCore.qDebug(f"Found screen {i} in {s.orientation().name} with resolution "
                          f"{s.availableGeometry().width()}x{s.availableGeometry().height()}.")

        if len(self.screens) > 1:
            qr = self.screens[0].geometry()
            self.move(qr.left(), qr.top())

        self.pushButton_mediaSourceDirectory.clicked.connect(self.sceneFromDirectoryDialog)
        self.pushButton_startShow.clicked.connect(self.openPresenterView)

        self.textEdit_notes.textChanged.connect(self.updateSceneNotes)
        self.actionNew.triggered.connect(self.newProject)
        self.actionOpen.triggered.connect(self.loadFromFile)
        self.actionSave.triggered.connect(self.saveToFile)
        self.actionSave_As.triggered.connect(self.saveAsFileDialog)
        self.actionQuit.triggered.connect(self.quitProject, QtCore.Qt.ConnectionType.QueuedConnection)
        self.actionAbout_Qhawana.triggered.connect(splash_screen.show)

        self.tableView_scenes.context_menu.triggered.connect(self.sceneContextMenu)

        self.spinBox_transitionTime.valueChanged.connect(
            lambda x: self.project.settings.setProperty("transition_time", x))
        self.spinBox_defaultDelay.valueChanged.connect(
            lambda x: self.project.settings.setProperty("default_delay", x))

        self.newProject()

    @QtCore.Slot()
    def sceneContextMenu(self, signal: QtGui.QAction):
        sender_widget = self.sender().parent()
        sender_index = signal.data()

        assert sender_widget in [self.tableView_scenes, self.listView_filmStrip]
        assert isinstance(sender_index, QtCore.QModelIndex)

        if signal.text() == "Pan and zoom effect":
            scene = sender_widget.model().data(sender_index, QtCore.Qt.ItemDataRole.UserRole)
            if not scene or scene.scene_type != Scene_Type.STILL:
                QtCore.qWarning("Pan and zoom effect is only supported for Scene_Type.STILL")
                return
            form = Dialog_PanAndZoomEffect(parent=self)
            form.setMinimumSize(QtCore.QSize(640, 480))
            form.setSizeGripEnabled(True)
            form.image.openImage(scene.pixmap)
            form.exec()

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

    def settingsChanged(self, setting, value):
        if setting == "save_file":
            self.setWindowTitle(f"Qhawana - {value}")
        elif setting == "transition_time":
            self.pv.mv.scene_fade_in_anim.setDuration(value)
            self.pv.mv.scene_fade_out_anim.setDuration(value // 4)

    def newProject(self):
        if self.changes_saved:
            QtCore.qDebug("Creating new project")
            self.project = Mv_Project()

            self.scenes_selection_model = QtCore.QItemSelectionModel(self.project.mv_show.sequence)
            self.bin_selection_model = QtCore.QItemSelectionModel(self.project.bin)
            self.listView_filmStrip.setModel(self.project.mv_show.sequence)
            self.listView_filmStrip.setSelectionModel(self.scenes_selection_model)
            self.tableView_scenes.setModel(self.project.mv_show.sequence)
            self.tableView_scenes.setSelectionModel(self.scenes_selection_model)
            self.treeView.setModel(self.project.bin)
            self.treeView.setSelectionModel(self.bin_selection_model)

            self.project.mv_show.sequence.dataChanged.connect(self.changed)
            self.project.mv_show.sequence.layoutChanged.connect(self.changed)
            self.project.mv_show.sequence.rowsInserted.connect(self.changed)
            self.project.mv_show.sequence.rowsRemoved.connect(self.changed)
            self.project.settings.valueChanged.connect(self.changed)
            self.project.mv_show.sequence.rowsRemoved.connect(self.showScenePreview)
            self.project.settings.valueChanged.connect(self.settingsChanged)
            self.project.mv_show.sequence.rowsInserted.connect(self.tableView_scenes.resizeColumnsToContents)
            self.scenes_selection_model.selectionChanged.connect(self.showScenePreview)
            self.scenes_selection_model.selectionChanged.connect(self.bin_selection_model.clearSelection)
            self.bin_selection_model.selectionChanged.connect(self.showBinPreview)
            self.bin_selection_model.selectionChanged.connect(self.scenes_selection_model.clearSelection)

            self.project.mv_show.state_changed.connect(self.pv.progressBar_state.setFormat)
            self.project.mv_show.state_changed.connect(lambda x: self.pv.scene_runner(self.pv.current_scene))

            self.scene_index = 0
            self.setWindowTitle("Qhawana")
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
        file_name = QtWidgets.QFileDialog.getSaveFileName(self, self.tr("Save project to file"))[0]
        if file_name:
            self.project.settings.setProperty("save_file", file_name)
            self.saveToFile()

    def saveToFile(self):
        if self.project.settings.getProperty("save_file"):
            self.lockSequence()

            self.progressBar.setEnabled(True)
            self.progressBar.setTextVisible(True)

            worker = Worker(self.saveProjectToFile, self.project.settings.getProperty("save_file"))
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
                file_name = QtWidgets.QFileDialog.getOpenFileName(self, self.tr("Select project file"))[0]
            if file_name:
                self.lockSequence()
                self.newProject()

                self.progressBar.setEnabled(True)
                self.progressBar.setTextVisible(True)

                worker = Worker(self.loadProjectFromFile, file_name)
                worker.signals.progress.connect(self.progressBar.setValue)
                worker.signals.finished.connect(self.resetProgressBar)
                worker.signals.finished.connect(self.unlockSequence)
                self.threadpool.start(worker)
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
        popup.setText(self.tr("The project has unsaved changes"))
        popup.setInformativeText(self.tr("Would you like to save your changes?"))
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
            show = self.project.mv_show.toJson(progress_callback)
            json.dump(settings | project_bin | show, f)

    def loadProjectFromFile(self, file_name, progress_callback):
        QtCore.qDebug(f"Loading project from file {file_name}")

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
            self.project.mv_show.fromJson(json_string["scenes"], progress_callback)

        QtCore.qDebug(f"Project loaded from file {file_name}")

        self.project.settings.setProperty("save_file", file_name)
        self.changes_saved = True
        self.radioButton_changes.setChecked(False)

    def sceneFromDirectoryDialog(self):
        dir_name = QtWidgets.QFileDialog.getExistingDirectory(self, self.tr("Select Media Source Directory"))
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

            bin_item = BinItem.fromFile(path)
            if bin_item:
                category_item = self.project.bin.findItems(bin_item.category.name,
                                                           QtCore.Qt.MatchFlag.MatchExactly, 0)[0]
                category_item.appendRow(bin_item)

            scene_item = SceneItem.fromFile(path)
            if scene_item:
                self.project.mv_show.sequence.appendRow(scene_item)

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
        if self.project.mv_show.length() > 0:
            if len(self.screens) > 1:
                qr = self.screens[0].geometry()
                self.pv.move(qr.left(), qr.top())
            self.pv.changeScene("first")
            self.pv.show()
        else:
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle(self.tr("Empty MultiVision show!"))
            dialog.setText(self.tr("Please add scenes first."))
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
        else:
            QtCore.qDebug("Invalid index, not showing preview")
            return

        bin_item = self.project.bin.itemFromIndex(bin_index)
        if bin_item is None:
            QtCore.qWarning("No bin item for index, not showing preview")
            return

        parent = bin_item.parent()
        if parent is None:
            QtCore.qDebug("Bin item has no parent, not showing preview")
            return

        parent_type = parent.data(QtCore.Qt.ItemDataRole.DisplayRole)
        QtCore.qDebug(f"Showing preview for {parent_type} item {bin_index.row()} "
                      f"({self.project.bin.rowCount(parent.index())} items in bin)")

        graphics_scene = QtWidgets.QGraphicsScene()

        if parent_type == "STILL":
            self.pushButton_playPausePreview.setEnabled(False)
            self.horizontalSlider_videoPosition.setEnabled(False)
            self.videoPreviewPlayer.stop()
            self.videoPreviewPlayer.setSource(QtCore.QUrl())

            image_item = QtWidgets.QGraphicsPixmapItem()
            image_item.setPixmap(
                scalePixmapToWidget(self.graphicsView_preview,
                                    QtGui.QPixmap(bin_item.data(QtCore.Qt.ItemDataRole.UserRole))))
            graphics_scene.addItem(image_item)

        elif parent_type == "VIDEO":
            self.pushButton_playPausePreview.setEnabled(True)
            self.horizontalSlider_videoPosition.setEnabled(True)

            # TODO: Check if MIME Type of scene.source is supported and the file exists
            self.videoPreviewPlayer.setSource(
                QtCore.QUrl.fromLocalFile(bin_item.data(QtCore.Qt.ItemDataRole.UserRole)))

            video_item = QtMultimediaWidgets.QGraphicsVideoItem()
            video_item.setSize(self.graphicsView_preview.size().toSizeF())
            video_item.setAspectRatioMode(QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            self.videoPreviewPlayer.setVideoOutput(video_item)

            self.videoPreviewPlayer.play()
            self.videoTimer.singleShot(100, self.videoPreviewPlayer.pause)

            graphics_scene.addItem(video_item)

        elif parent_type == "TRACK":
            br = PyQMLBridge()
            qw = QtQuickWidgets.QQuickWidget(parent=None)
            qw.engine().rootContext().setContextProperty("br", br)
            qw.setFixedSize(self.graphicsView_preview.size())
            qw.setSource(QtCore.QUrl("qhawana/map.qml"))

            gp = geoPathFromGPX(bin_item.data(QtCore.Qt.ItemDataRole.UserRole))
            br.drawPath(gp)
            center = gp.boundingGeoRectangle().center()
            if center:
                br.setLocation(center.latitude(), center.longitude())
                br.fitViewport()

            graphics_scene.addWidget(qw)

        self.graphicsView_preview.items().clear()
        self.graphicsView_preview.viewport().update()
        self.graphicsView_preview.setScene(graphics_scene)

    def showScenePreview(self, selection):
        if isinstance(selection, QtCore.QItemSelection) and len(selection.indexes()) > 0:
            scene_index = selection.indexes()[0]
        elif isinstance(selection, QtCore.QModelIndex):
            scene_index = selection
        else:
            return

        if scene_index.isValid():
            QtCore.qDebug(f"Showing preview for row {scene_index.row()} "
                          f"({self.project.mv_show.sequence.rowCount()} items in list, "
                          f"{self.project.mv_show.sequence.sceneCount()} scenes in show)")
            scene: Mv_Scene = self.project.mv_show.sequence.item(scene_index.row())
        else:
            QtCore.qDebug("Invalid index, not showing preview")
            return

        self.scene_index = scene_index.row()

        graphics_scene = QtWidgets.QGraphicsScene()

        self.horizontalSlider_videoPosition.setValue(0)
        self.pushButton_playPausePreview.setChecked(False)

        if scene.scene_type == Scene_Type.STILL:
            self.pushButton_inPoint.setEnabled(False)
            self.pushButton_outPoint.setEnabled(False)
            self.pushButton_playPausePreview.setEnabled(False)
            self.horizontalSlider_videoPosition.setEnabled(False)
            self.videoPreviewPlayer.stop()
            self.videoPreviewPlayer.setSource(QtCore.QUrl())

            image_item = QtWidgets.QGraphicsPixmapItem()
            image_item.setPixmap(
                scalePixmapToWidget(self.graphicsView_preview,
                                    getPixmapFromScene(scene)))
            graphics_scene.addItem(image_item)

        elif scene.scene_type == Scene_Type.VIDEO:
            self.pushButton_inPoint.setEnabled(True)
            self.pushButton_outPoint.setEnabled(True)
            self.pushButton_playPausePreview.setEnabled(True)
            self.horizontalSlider_videoPosition.setEnabled(True)

            # TODO: Check if MIME Type of scene.source is supported and the file exists
            self.videoPreviewPlayer.setSource(QtCore.QUrl.fromLocalFile(scene.source))

            video_item = QtMultimediaWidgets.QGraphicsVideoItem()
            video_item.setSize(self.graphicsView_preview.size().toSizeF())
            video_item.setAspectRatioMode(QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            self.videoPreviewPlayer.setVideoOutput(video_item)

            self.videoPreviewPlayer.play()
            if scene.in_point > 0:
                self.videoPreviewPlayer.setPosition(scene.in_point)
            self.videoTimer.singleShot(100, self.videoPreviewPlayer.pause)

            graphics_scene.addItem(video_item)

        elif scene.scene_type == Scene_Type.MAP:
            br = PyQMLBridge()
            qw = QtQuickWidgets.QQuickWidget(parent=None)
            qw.engine().rootContext().setContextProperty("br", br)
            qw.setFixedSize(self.graphicsView_preview.size())
            qw.setSource(QtCore.QUrl("qhawana/map.qml"))

            if scene.location:
                br.setLocation(scene.location[0], scene.location[1])

            bounding_rect = QtPositioning.QGeoRectangle()
            num_items = 0
            for i in scene.graphics_items:
                assert type(i) is QhawanaGraphicsSceneItem
                if i.item_class is QtPositioning.QGeoPath:
                    num_items += 1
                    gp = i.toObject()
                    bounding_rect.extendRectangle(gp.boundingGeoRectangle().topLeft())
                    bounding_rect.extendRectangle(gp.boundingGeoRectangle().bottomRight())
                    br.drawPath(gp)
            if num_items > 0:
                br.setLocation(bounding_rect.center().latitude(), bounding_rect.center().longitude())
                br.fitViewport()

            graphics_scene.addWidget(qw)

        self.graphicsView_preview.items().clear()
        self.graphicsView_preview.viewport().update()
        self.graphicsView_preview.setScene(graphics_scene)

        self.textEdit_notes.setText(scene.notes)

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

            scene = self.project.mv_show.sequence.item(self.scene_index)
            if position == scene.out_point:
                self.videoPreviewPlayer.pause()
        else:
            self.videoPreviewPlayer.setPosition(position)

    def setVideoInPoint(self):
        scene_index = self.project.mv_show.sequence.index(self.scene_index, 4)
        if scene_index.isValid():
            self.project.mv_show.sequence.setData(scene_index,
                                                  self.horizontalSlider_videoPosition.value(),
                                                  QtCore.Qt.ItemDataRole.EditRole)

    def setVideoOutPoint(self):
        scene_index = self.project.mv_show.sequence.index(self.scene_index, 5)
        if scene_index.isValid():
            self.project.mv_show.sequence.setData(scene_index,
                                                  self.horizontalSlider_videoPosition.value(),
                                                  QtCore.Qt.ItemDataRole.EditRole)

    def updateSceneNotes(self):
        scene = self.project.mv_show.sequence.item(self.scene_index)
        if scene:
            scene_data = scene
            scene_data.notes = self.textEdit_notes.toPlainText()

    def changed(self):
        self.changes_saved = False
        self.radioButton_changes.setChecked(True)
        if self.project.settings.getProperty("save_file"):
            self.setWindowTitle("Qhawana - " + str(self.project.settings.getProperty('save_file')) +
                                " (" + self.tr("changed") + ")")


class Dialog_PanAndZoomEffect(QtWidgets.QDialog, Ui_Form_PanAndZoomEffect):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        self.defaultBboxesLandscape = [QtCore.QRectF(0, 0.1, 1, 0.8), QtCore.QRectF(0.1, 0.1, 0.9, 0.8)]
        self.defaultBboxesPortrait = [QtCore.QRectF(0, 0, 1, 0), QtCore.QRectF(0.05, 0.05, 0.9, 0)]

        self.buttonSwapInOutEditor.clicked.connect(self.image.swapEditors)
        self.buttonSwitchInOutEditor.clicked.connect(self.image.switchEditor)
        self.buttonDone.clicked.connect(self.close)
        self.image.bboxesChanged.connect(self.updateInfo)

        self.targetRatioChanged = QtCore.Signal()
        self._target_ratio = 16 / 10

        bboxes = []
        img_size = self.image.getImageSize()

        if img_size.width() > img_size.height():
            for bbox in self.defaultBboxesLandscape:
                bboxes.append(QtCore.QRectF(bbox))
            print('SetImageIdx() bboxes 2:', bboxes)
        else:
            try:
                ratio_img = img_size.height() / img_size.width()
            except ZeroDivisionError:
                # FIXME: KS: 2022-05-13: Not the best solution, but at least program not crashes
                ratio_img = 2 / 3

            ratio_target = self.getTargetRatio()
            print('SetImageIdx() ratio_img:', ratio_img)
            for bbox in self.defaultBboxesPortrait:
                bbox_copy = QtCore.QRectF(bbox)
                bbox_copy.setWidth(bbox_copy.width() * ratio_img * ratio_target)
                bbox_copy.setHeight(bbox_copy.width() / ratio_img / ratio_target)
                print('SetImageIdx() bbox_copy: ', bbox_copy)
                bbox_copy.moveCenter(QtCore.QPointF(0.5, 0.5))
                print('SetImageIdx() bbox_copy: ', bbox_copy)
                bboxes.append(bbox_copy)
            print('SetImageIdx() bboxes 3:', bboxes)

            self.image.setBboxes01(bboxes)
            stay_inside = self.areBboxesInsideImage(bboxes)
            print('SetImageIdx() stay_inside:', stay_inside)
            self.checkboxStayInside.setChecked(stay_inside)

    def updateInfo(self):
        bboxes = self.image.getBboxes01()
        # print('images:', self.images)
        print('bboxes:', bboxes)
        # self.labelInfoPath.setText(self.images[self.imageIdx])
        self.labelInfoScale.setText(
            'in -> out scale: %02f' % (bboxes[1].width() / bboxes[0].width() if bboxes[0].width() > 0 else -1))

    def getTargetRatio(self) -> float:
        return float(self._target_ratio)

    def setTargetRatio(self, ratio: float):
        if 0 < ratio <= 10 and ratio != self._target_ratio:
            self._target_ratio = ratio
            self.targetRatioChanged.emit()

    @staticmethod
    def areBboxesInsideImage(bboxes):
        inside = True
        for bbox in bboxes:
            if bbox.left() < 0 or bbox.top() < 0 or bbox.right() > 1 or bbox.bottom() > 1:
                inside = False
            print('areBboxesInsideImage() bbox:', bbox, 'inside:', inside)
        print('areBboxesInsideImage() return ', inside)
        return inside


class Ui_presenterView(QtWidgets.QWidget, Ui_Form_presenterView):
    scene_changed = QtCore.Signal(int)

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent, QtCore.Qt.WindowType.Window)
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
        # Declare to store and disconnect the signal-slot-connections for the scene timer
        self.timer_connection = None

        self.updateDialPosition()

    def close(self):
        self.parent().project.mv_show.set_state(Show_States.STOPPED)
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
        if self.parent().project.mv_show.state() != Show_States.RUNNING:
            self.progress_animation.stop()
            self.scene_timer.stop()
            return

        if scene_index is None:
            self.mv.scene_fade_out_anim.start()
            QtCore.qDebug(f"Fading out scene {self.current_scene}")
            return

        scene = self.parent().project.mv_show.getScene(scene_index)

        if 0 <= scene.in_point < scene.out_point:
            duration = scene.out_point - scene.in_point
        elif scene.duration == -1:
            duration = self.parent().project.settings.getProperty("default_delay")
        else:
            duration = scene.duration
        self.progress_animation.setDuration(duration)
        self.progress_animation.start()

        try:
            self.scene_timer.disconnect(self.timer_connection)
        except TypeError:
            pass
        self.scene_timer.stop()
        self.timer_connection = self.scene_timer.timeout.connect(self.scene_runner)
        self.scene_timer.setSingleShot(True)
        self.scene_timer.start(duration)

        QtCore.qDebug(f"Running scene {self.current_scene} for {timeStringFromMsec(duration)}")

    def changeScene(self, action, index=None):
        length = self.parent().project.mv_show.length()

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

        scene = self.parent().project.mv_show.getScene(self.current_scene)
        prev_scene = self.parent().project.mv_show.getScene(self.current_scene - 1) \
            if self.current_scene > 0 else None
        next_scene = self.parent().project.mv_show.getScene(self.current_scene + 1) \
            if self.current_scene < (length - 1) else None

        self.label_sceneCounter.setText(f"{self.current_scene + 1}/{length}")
        self.updatePresenterView(scene, prev_scene, next_scene)

        # if self.parent().project.mv_show.state() in (Show_States.RUNNING, Show_States.PAUSED, Show_States.FINISHED):
        self.mv.loadScene(scene)
        if self.parent().project.mv_show.state() == Show_States.RUNNING and self.current_scene >= (length - 1):
            self.parent().project.mv_show.set_state(Show_States.FINISHED)

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
        state = self.parent().project.mv_show.state()
        try:
            self.mv.scene_fade_out_anim.finished.disconnect()
        except TypeError:
            pass
        self.mv.scene_fade_out_anim.finished.connect(lambda: self.changeScene("next"))

        if state in [Show_States.STOPPED, Show_States.FINISHED]:
            self.mv.show()
            self.parent().project.mv_show.set_state(Show_States.RUNNING)
        elif state == Show_States.PAUSED:
            self.parent().project.mv_show.set_state(Show_States.RUNNING)

    def pauseShow(self):
        if self.parent().project.mv_show.state() == Show_States.RUNNING:
            try:
                self.mv.scene_fade_out_anim.finished.disconnect()
            except TypeError:
                # A TypeError is raised if disconnect is called and there are no active connections
                pass

            self.parent().project.mv_show.set_state(Show_States.PAUSED)
            self.progressBar_state.setValue(0)
            # TODO: We could pause instead of stopping, but QTimer does not support pause and resume out of the box.

    def updatePresenterView(self, scene, prev_scene, next_scene):
        self.label_currentView.setPixmap(scalePixmapToWidget(self.label_currentView, getPixmapFromScene(scene)))
        self.label_previousView.setPixmap(scalePixmapToWidget(self.label_previousView, getPixmapFromScene(prev_scene)))
        self.label_nextView.setPixmap(scalePixmapToWidget(self.label_nextView, getPixmapFromScene(next_scene)))
        self.label_notes.setText(scene.notes)


class Ui_multiVisionShow(QtWidgets.QWidget, Ui_Form_multiVisionShow):
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent, QtCore.Qt.WindowType.Window)
        self.setupUi(self)

        self.installEventFilter(self)

        self.videoPlayer = QtMultimedia.QMediaPlayer(parent=self)
        self.audioPlayer = QtMultimedia.QMediaPlayer(parent=self)
        self.videoAudioOutput = QtMultimedia.QAudioOutput(parent=self)
        self.musicAudioOutput = QtMultimedia.QAudioOutput(parent=self)

        self.videoPlayer.setAudioOutput(self.videoAudioOutput)
        self.audioPlayer.setAudioOutput(self.musicAudioOutput)
        self.audioPlayer.setLoops(QtMultimedia.QMediaPlayer.Loops.Infinite)

        self.supported_mimetypes = get_supported_mime_types()

        self.opacityEffect = QtWidgets.QGraphicsOpacityEffect(parent=self)

        self.scene_fade_in_anim = QtCore.QPropertyAnimation(self.opacityEffect, b"opacity", parent=self)
        self.scene_fade_in_anim.setEasingCurve(QtCore.QEasingCurve.Type.Linear)
        self.scene_fade_in_anim.setStartValue(0)
        self.scene_fade_in_anim.setEndValue(1)

        self.scene_fade_out_anim = QtCore.QPropertyAnimation(self.opacityEffect, b"opacity", parent=self)
        self.scene_fade_out_anim.setEasingCurve(QtCore.QEasingCurve.Type.Linear)
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
        graphics_scene = QtWidgets.QGraphicsScene()

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
            graphics_scene.addItem(image_item)

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

            if scene.play_video_audio and not self.parent().pushButton_audio_quiet.isChecked():
                self.parent().pushButton_audio_quiet.click()

            self.parent().parent().project.mv_show.state_changed.connect(self.manageVideoPlayback)

            video_item = QtMultimediaWidgets.QGraphicsVideoItem()
            video_item.setSize(self.graphicsView.size().toSizeF())
            video_item.setAspectRatioMode(QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            video_item.setGraphicsEffect(self.opacityEffect)
            self.videoPlayer.setVideoOutput(video_item)

            graphics_scene.addItem(video_item)

            self.manageVideoPlayback()

        elif scene.scene_type == Scene_Type.MAP:
            br = PyQMLBridge()
            qw = QtQuickWidgets.QQuickWidget(parent=None)
            qw.engine().rootContext().setContextProperty("br", br)
            qw.setFixedSize(self.graphicsView.size())
            qw.setSource(QtCore.QUrl("qhawana/map.qml"))

            if scene.location:
                br.setLocation(scene.location[0], scene.location[1])

            bounding_rect = QtPositioning.QGeoRectangle()
            num_items = 0
            for i in scene.graphics_items:
                assert type(i) is QhawanaGraphicsSceneItem
                if i.item_class is QtPositioning.QGeoPath:
                    num_items += 1
                    gp = i.toObject()
                    bounding_rect.extendRectangle(gp.boundingGeoRectangle().topLeft())
                    bounding_rect.extendRectangle(gp.boundingGeoRectangle().bottomRight())
                    br.drawPath(gp)
            if num_items > 0:
                br.setLocation(bounding_rect.center().latitude(), bounding_rect.center().longitude())
                br.fitViewport()

            graphics_scene.addWidget(qw)

        self.graphicsView.items().clear()
        self.graphicsView.viewport().update()
        self.graphicsView.setScene(graphics_scene)

        self.scene_fade_in_anim.start()
        pz = pan_and_zoom(self.graphicsView)
        pz.start()

        if scene.audio_source:
            # TODO: Check if MIME Type of scene.audio_source is supported and the file exists
            audio_url = QtCore.QUrl.fromLocalFile(scene.audio_source)
            prev_audio_url = self.audioPlayer.source()

            if audio_url != prev_audio_url:
                self.audioPlayer.setSource(audio_url)
                self.audioPlayer.play()
        else:
            self.parent().controlAudio("stop")

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
        if self.parent().parent().project.mv_show.state() == Show_States.PAUSED:
            self.videoPlayer.pause()
        elif self.parent().parent().project.mv_show.state() == Show_States.RUNNING:
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
    faulthandler.enable()
    ui = Ui_mainWindow()

    if show_splash:
        splash_screen.show()
        splash_screen.finish(ui)

    if len(args) > 1:
        ui.loadFromFile(args[1])

    ui.show()
    app.exec()


QtCore.QLoggingCategory.setFilterRules("*.ffmpeg.utils=false")
translator = QtCore.QTranslator()
translator.load('i18n/en_US')
app = QtWidgets.QApplication(sys.argv)
app.installTranslator(translator)
splash_width = app.primaryScreen().geometry().width() // 2 if app.primaryScreen() else 800
splash_height = app.primaryScreen().geometry().height() // 2 if app.primaryScreen() else 600
splash_screen = QhawanaSplash(splash_width, splash_height, str(res / "Qhawana_Splash.png"))

if __name__ == "__main__":
    sys.exit(launcher(sys.argv))
