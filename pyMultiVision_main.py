# import math
import PyQt6.QtCore
import base64
import exiftool
import av
import gzip
import hashlib
import PIL.Image
import PIL.ImageQt
import os
import json
import mimetypes
import qtmodern.styles
import sys
import traceback
import uuid
from enum import IntEnum

from PyQt6 import QtCore, QtGui, QtMultimedia, QtWidgets
from ui_mainWindow import Ui_mainWindow_pyMultiVision
from ui_presenterView import Ui_Form_presenterView
from ui_multiVisionShow import Ui_Form_multiVisionShow

MV_ICON_SIZE = 50
MV_PREVIEW_SIZE = 800
BUF_SIZE = 65536


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


class Mv_Project(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.show = Mv_Show()
        self.bin = ProjectBinModel()

    def clear_bin(self):
        self.bin.clear()
        root = self.bin.invisibleRootItem()
        for n in ["STILLS", "VIDEO", "AUDIO"]:
            item = QtGui.QStandardItem(n)
            item.setDragEnabled(False)
            item.setDropEnabled(True)
            root.appendRow(item)
        self.bin.setHorizontalHeaderLabels(["File", "Details"])
        return self.bin


class Mv_Show(QtCore.QObject):
    state_changed = PyQt6.QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.sequence = Mv_sequence(parent=self)
        self.__state = Show_States.STOPPED

    def state(self):
        return self.__state

    def set_state(self, state: Show_States):
        states = {Show_States.STOPPED: "stopped",
                  Show_States.PAUSED: "paused",
                  Show_States.RUNNING: "running",
                  Show_States.FINISHED: "finished"}
        if state != self.__state:
            self.__state = state
            self.state_changed.emit(states[state])
            QtCore.qDebug(f"Changing show state to {states[state]}")
            return state
        else:
            return False

    def length(self):
        return self.sequence.rowCount()

    def toJson(self, progress_callback):
        scenes = []
        num_scenes = self.sequence.rowCount()
        for index in range(num_scenes):
            item = self.sequence.item(index)
            scene_data = item.toJson(store_pixmap=True)
            scenes.append(scene_data)
            progress_callback.emit((index + 1) // num_scenes * 100)
        json_string = {"scenes": scenes}
        return json_string

    def fromJson(self, json_string: dict, progress_callback):
        self.sequence.clear()
        self.set_state(Show_States.STOPPED)
        num_scenes = len(json_string["scenes"])
        for i, s in enumerate(json_string["scenes"]):
            progress_callback.emit((i + 1) // num_scenes * 100)
            scene = Mv_Scene.fromJson(s)
            self.sequence.appendRow(scene)

    def getModel(self):
        return self.sequence

    def getScene(self, index=0):
        return self.sequence.item(index, 0) if 0 <= index < self.length() else False


class Mv_sequence(QtCore.QAbstractTableModel):
    # sequence is a list of QStandardItems with UUIDs referring to a Mv_Scene object
    _sequence = []

    # scenes is a dict of Mv_Scene objects with a UUID as the key
    _scenes = {}

    # horizontal_headers is a list of strings
    _horizontal_headers = []

    def __init__(self, parent=None):
        super().__init__()
        self.setHorizontalHeaderLabels(["Visual source", "Audio source", "Capture Time",
                                        "Duration", "In Point", "Out Point"])

    def data(self, index, role=...):
        if not (index.isValid() and index.row() <= self.rowCount()):
            QtCore.qWarning("Invalid index for sequence")
            return False
        item: QtGui.QStandardItem = self._sequence[index.row()]
        item_uuid = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if item_uuid is None or item_uuid.isNull():
            # This happens when data() is requested for an empty item
            QtCore.qWarning(f"Item {index.row()} in sequence does not have a valid UUID")
            return False
        if item_uuid not in self._scenes:
            QtCore.qWarning(f"Scene for item in sequence with UUID {item_uuid} not found")
            return False
        item_data: Mv_Scene = self._scenes[item_uuid]
        if item_data is None:
            QtCore.qWarning(f"Scene for item in sequence with UUID {item_uuid} is empty")
            return False
        if role == QtCore.Qt.ItemDataRole.UserRole:
            print("UserRole data requested")
            return item_data
        elif index.column() == 0:
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                if item_data.exif:
                    return item_data.exif["File:FileName"]
                else:
                    return item_data.source
            elif role == QtCore.Qt.ItemDataRole.DecorationRole:
                return item_data.icon
        elif index.column() == 1:
            if role == QtCore.Qt.ItemDataRole.DisplayRole or role == QtCore.Qt.ItemDataRole.ToolTipRole:
                return item_data.audio_source
        elif index.column() == 2:
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                if item_data.exif:
                    if "EXIF:CreateDate" in item_data.exif:
                        return item_data.exif["EXIF:CreateDate"]
                    elif "QuickTime:CreateDate" in item_data.exif:
                        return item_data.exif["QuickTime:CreateDate"]
        elif index.column() == 3:
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                if item_data.duration > 0:
                    return timeStringFromMsec(item_data.duration)
                elif item_data.duration == 0:
                    return "(stop)"
                elif item_data.duration == -1:
                    return "(default)"
            elif role == QtCore.Qt.ItemDataRole.SizeHintRole:
                return "0000:00:00 00:00:00"
        elif index.column() in [4, 5] and item_data.scene_type == Scene_Type.STILL:
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                return ""
            elif role == QtCore.Qt.ItemDataRole.SizeHintRole:
                return "000:00.000"
        elif (index.column() == 4 and
              role == QtCore.Qt.ItemDataRole.DisplayRole):
            return timeStringFromMsec(item_data.in_point)
        elif (index.column() == 4 and
              role == QtCore.Qt.ItemDataRole.EditRole):
            return str(item_data.in_point)
        elif (index.column() == 5 and
              role == QtCore.Qt.ItemDataRole.DisplayRole):
            return timeStringFromMsec(item_data.out_point)
        elif (index.column() == 5 and
              role == QtCore.Qt.ItemDataRole.EditRole):
            return str(item_data.out_point)

    def setData(self, index, value, role=...):
        if role == QtCore.Qt.ItemDataRole.EditRole and index.column() in [4, 5]:
            item = self._sequence[index.row()]
            item_uuid = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if item_uuid is None or item_uuid.isNull():
                QtCore.qWarning(f"Item {index.row()} in sequence does not have a valid UUID")
                return False
            if item_uuid not in self._scenes:
                QtCore.qWarning(f"Scene for item in sequence with UUID {item_uuid} not found")
                return False
            item_data: Mv_Scene = self._scenes[item_uuid]

            if int(value) > item_data.duration or int(value) < 0:
                return False
            if index.column() == 4:
                if int(value) < item_data.out_point:
                    item_data.in_point = int(value)
                else:
                    return False
            elif index.column() == 5:
                if int(value) > item_data.in_point:
                    item_data.out_point = int(value)
                else:
                    return False

            self.dataChanged.emit(index, index)
            return True
        else:
            return super().setData(index, value, role)

    def clear(self):
        self.beginResetModel()
        self._sequence = []
        self._scenes = {}
        self.endResetModel()
        return True

    def deleteScene(self, index):
        if index.isValid():
            self.beginRemoveRows(self.index(index.row(), 0), index.row(), index.row())
            item = self._sequence.pop(index.row())
            del self._scenes[item.data(QtCore.Qt.ItemDataRole.UserRole)]
            self.endRemoveRows()
            return True
        else:
            return False

    def headerData(self, section, orientation, role=...):
        if role == QtCore.Qt.ItemDataRole.SizeHintRole:
            return QtCore.QVariant()
        elif role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return self._horizontal_headers[section]
            elif orientation == QtCore.Qt.Orientation.Vertical:
                return section + 1

    def columnCount(self, parent=...):
        return len(self._horizontal_headers)

    def rowCount(self, parent=...):
        return len(self._sequence)

    def appendRow(self, item: QtGui.QStandardItem):
        length = self.rowCount()
        self.beginInsertRows(self.index(self.rowCount() - 1, 0), length, length)
        scene = item.data()
        self._scenes[scene.uuid] = scene
        item.setData(scene.uuid, QtCore.Qt.ItemDataRole.UserRole)
        self._sequence.append(item)
        self.endInsertRows()
        self.rowsInserted.emit(QtCore.QModelIndex(), length, length)

    def setHorizontalHeaderLabels(self, labels):
        self._horizontal_headers.clear()
        for text in labels:
            self._horizontal_headers.append(text)
        self.headerDataChanged.emit(QtCore.Qt.Orientation.Horizontal, 0, len(labels) - 1)

    def item(self, row, column=0):
        try:
            item = self._sequence[row]
        except IndexError:
            QtCore.qWarning(f"Sequence item index is out of bounds "
                            f"(Item {row} requested, sequence has {self.rowCount()} items)")
            return False
        item_uuid = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if item_uuid is None or item_uuid.isNull():
            QtCore.qWarning("Item in sequence does not have a valid UUID")
            return False
        if item_uuid not in self._scenes:
            QtCore.qWarning(f"Scene for item in sequence with UUID {item_uuid} not found")
            return False

        return self._scenes[item_uuid]
        # return self.data(self.index(row, column), QtCore.Qt.ItemDataRole.UserRole)

    def supportedDragActions(self):
        return QtCore.Qt.DropAction.MoveAction

    def supportedDropActions(self):
        return QtCore.Qt.DropAction.MoveAction | QtCore.Qt.DropAction.CopyAction | QtCore.Qt.DropAction.LinkAction

    def insertRows(self, row, count, parent=...):
        self.beginInsertRows(parent, row, row + count - 1)
        for r in range(count):
            print(f"inserting row after {row}")
            self._sequence.insert(row, QtGui.QStandardItem())
        self.endInsertRows()
        return True

    def removeRows(self, row, count, parent=...):
        self.beginRemoveRows(parent, row, row + count - 1)
        for r in range(count):
            print(f"deleting row {row}")
            del self._sequence[row]
        self.endRemoveRows()
        return True

    def mimeTypes(self):
        types = super().mimeTypes()
        types.append("x-application-pyMultiVision-STILLS")
        types.append("x-application-pyMultiVision-AUDIO")
        types.append("x-application-pyMultiVision-VIDEO")

        return types

    def mimeData(self, indexes):
        types = self.mimeTypes()

        encoded = QtCore.QByteArray()
        stream = QtCore.QDataStream(encoded, QtCore.QDataStream.OpenModeFlag.WriteOnly)
        format_type = types[0]
        mime_data = QtCore.QMimeData()

        for index in indexes:
            if index.isValid() and len(types) > 0 and index.column() == 0:
                item: QtGui.QStandardItem = self._sequence[index.row()]
                item_uuid = item.data(QtCore.Qt.ItemDataRole.UserRole)

                stream << item_uuid

        mime_data.setData(format_type, encoded)

        return mime_data

    def dropMimeData(self, data, action, row, column, parent):
        QtCore.qDebug(f"Handling {action}")
        if data.hasFormat('application/x-qabstractitemmodeldatalist'):
            QtCore.qDebug("Dropping application/x-qabstractitemmodeldatalist")
            if not data or not action == QtCore.Qt.DropAction.MoveAction:
                return False

            types = super().mimeTypes()
            if len(types) == 0:
                return False

            format_type = types[0]

            if not data.hasFormat(format_type):
                return False

            encoded = data.data(format_type)
            stream = QtCore.QDataStream(encoded, QtCore.QDataStream.OpenModeFlag.ReadOnly)

            # otherwise insert new rows for the data
            item_uuid = QtCore.QUuid()
            while not stream.atEnd():
                stream >> item_uuid
                self.insertRow(row, parent)
                QtCore.qDebug(f"Setting UUID {item_uuid.toString()} for inserted item in row {row}")
                self._sequence[row].setData(item_uuid, QtCore.Qt.ItemDataRole.UserRole)
                self.setData(self.index(row, column, parent), item_uuid, QtCore.Qt.ItemDataRole.UserRole)
            return True

        elif data.hasFormat('x-application-pyMultiVision-STILLS'):
            QtCore.qDebug("x-application-pyMultiVision-STILLS")

            return True
        elif data.hasFormat('x-application-pyMultiVision-AUDIO'):
            QtCore.qDebug("x-application-pyMultiVision-AUDIO")

            encoded = data.data("x-application-pyMultiVision-AUDIO")
            stream = QtCore.QDataStream(encoded, QtCore.QDataStream.OpenModeFlag.ReadOnly)

            item = stream.readQString()

            scene_uuid = self._sequence[row].data(QtCore.Qt.ItemDataRole.UserRole)
            scene = self._scenes[scene_uuid]
            scene.audio_source = item

            changed_index = self.index(row, column)
            self.dataChanged.emit(changed_index, changed_index)

            return True
        else:
            return False

    def flags(self, index):
        default_flags = super().flags(index)
        if index.isValid():
            flags = default_flags | QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsDragEnabled
            scene = self.item(index.row())
            if index.column() in [4, 5]:
                if scene and scene.scene_type == Scene_Type.VIDEO:
                    flags = flags | QtCore.Qt.ItemFlag.ItemIsEditable
                else:
                    flags = flags ^ QtCore.Qt.ItemFlag.ItemIsEnabled
        else:
            flags = default_flags | QtCore.Qt.ItemFlag.ItemIsDropEnabled
        return flags

    def sort(self, column, order=...):
        rev = (order == QtCore.Qt.SortOrder.DescendingOrder)
        self.beginResetModel()
        self._sequence.sort(key=lambda x: self.dataFromItemAndColumn(x, column), reverse=rev)
        self.endResetModel()

    def dataFromItemAndColumn(self, sort_item: QtGui.QStandardItem, column: int):
        item_uuid = sort_item.data(QtCore.Qt.ItemDataRole.UserRole)

        scene: Mv_Scene = self._scenes[item_uuid]
        if column == 0:
            return scene.source
        elif column == 2:
            if scene.exif:
                if "EXIF:CreateDate" in scene.exif:
                    return scene.exif["EXIF:CreateDate"]
                elif "QuickTime:CreateDate" in scene.exif:
                    return scene.exif["QuickTime:CreateDate"]

        return False

    def inheritAudio(self, selection: list[QtCore.QModelIndex]):
        print(f"Received {selection} of {len(selection)} rows")
        selection.sort(key=lambda x: x.row())
        audio_source = self.item(selection[0].row()).audio_source
        if audio_source:
            for i in selection:
                QtCore.qDebug(f"Setting audio source {audio_source} to scene {i.row()}")
                self.item(i.row()).audio_source = audio_source


class Mv_Scene(QtGui.QStandardItem):
    def __init__(self, source: str, scene_type: Scene_Type, audio_source="", pause=False, duration=-1,
                 in_point=-1, out_point=-1, play_video_audio=False, pixmap=None, notes="", exif=None):

        self.uuid = QtCore.QUuid().createUuid()
        self.source = source
        self.source_hash = ""
        self.audio_source = audio_source
        self.audio_source_hash = ""
        self.scene_type = scene_type
        self.pause = pause
        self.duration = duration
        self.in_point = in_point
        self.out_point = out_point
        self.play_video_audio = play_video_audio
        self.pixmap = pixmap
        self.notes = notes
        self.exif = exif

        if self.source:
            file_sha1 = hashlib.sha1()
            try:
                with open(self.source, 'rb') as f:
                    while True:
                        data = f.read(BUF_SIZE)
                        if not data:
                            break
                        file_sha1.update(data)
            except FileNotFoundError:
                QtCore.qWarning(f"Source file {self.source} not found for scene {self.uuid.toString()}")
                pass
            else:
                self.source_hash = file_sha1.hexdigest()

        if self.audio_source:
            file_sha1 = hashlib.sha1()
            try:
                with open(self.audio_source, 'rb') as f:
                    while True:
                        data = f.read(BUF_SIZE)
                        if not data:
                            break
                        file_sha1.update(data)
            except FileNotFoundError:
                QtCore.qWarning(f"Audio source file {self.audio_source} not found for scene {self.uuid.toString()}")
                pass
            else:
                self.audio_source_hash = file_sha1.hexdigest()

        self.icon = QtGui.QIcon()
        self.icon.addPixmap(self.pixmap.scaled(MV_ICON_SIZE, MV_ICON_SIZE,
                                               QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                               QtCore.Qt.TransformationMode.SmoothTransformation),
                            QtGui.QIcon.Mode.Normal,
                            QtGui.QIcon.State.Off)

        super().__init__()

    def __getstate__(self):
        print(f"Serializing scene {self.source}")
        state = [self.uuid, self.source, self.audio_source, self.scene_type,
                 self.pause, self.duration, self.notes, self.exif]
        byte_array = QtCore.QByteArray()
        stream = QtCore.QDataStream(byte_array, QtCore.QIODevice.OpenModeFlag.WriteOnly)
        stream << self.pixmap
        state.append(byte_array)
        # QtCore.qDebug(f"Serialized Mv_Scene: {state}")
        return state

    def __setstate__(self, state):
        self.uuid = state[0]
        self.source = state[1]
        self.audio_source = state[2]
        self.scene_type = state[3]
        self.pause = state[4]
        self.duration = state[5]
        self.notes = state[6]
        self.exif = state[7]
        self.pixmap = QtGui.QPixmap()
        stream = QtCore.QDataStream(state[8], QtCore.QIODevice.OpenModeFlag.ReadOnly)
        stream >> self.pixmap
        # self.pixmap = QtGui.QPixmap(self.source)
        # self.pixmap = None

    def toJson(self, store_pixmap=False) -> dict:
        json_dict = {"source": self.source,
                     "source_hash": self.source_hash,
                     "audio_source": self.audio_source,
                     "audio_source_hash": self.audio_source_hash,
                     "scene_type": self.scene_type,
                     "pause": self.pause,
                     "duration": self.duration,
                     "in_point": self.in_point,
                     "out_point": self.out_point,
                     "play_video_audio": self.play_video_audio,
                     "notes": self.notes,
                     "exif": self.exif}
        if store_pixmap and self.pixmap:
            json_dict["pixmap"] = jsonValFromPixmap(self.pixmap)
        else:
            json_dict["pixmap"] = None

        return json_dict

    def fromJson(json_dict: dict) -> QtGui.QStandardItem:
        if "pixmap" in json_dict and json_dict["pixmap"]:
            pixmap = pixmapFromJsonVal(json_dict["pixmap"])
        else:
            if json_dict["scene_type"] == Scene_Type.VIDEO:
                keyframe_image = getKeyframeFromVideo(json_dict["source"])
                pixmap = QtGui.QPixmap().fromImage(keyframe_image)
            elif json_dict["scene_type"] == Scene_Type.STILL:
                pixmap = QtGui.QPixmap(json_dict["source"])
            else:
                pixmap = QtGui.QPixmap(100, 100)
                pixmap.fill(QtGui.QColor("black"))
        icon = QtGui.QIcon()
        icon.addPixmap(pixmap.scaled(MV_ICON_SIZE, MV_ICON_SIZE,
                                     QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                     QtCore.Qt.TransformationMode.SmoothTransformation),
                       QtGui.QIcon.Mode.Normal,
                       QtGui.QIcon.State.Off)

        scene = Mv_Scene(source=json_dict["source"],
                         scene_type=json_dict["scene_type"],
                         pixmap=pixmap.scaled(MV_PREVIEW_SIZE, MV_PREVIEW_SIZE,
                                              QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                              QtCore.Qt.TransformationMode.SmoothTransformation)
                         )

        if "play_video_audio" in json_dict:
            scene.play_video_audio = json_dict["play_video_audio"]
        elif scene.scene_type == Scene_Type.VIDEO:
            with av.open(scene.source) as container:
                # Set scene's play_video_audio property to True if the video has an audio stream:
                scene.play_video_audio = (len(container.streams.audio) > 0)
        if "audio_source" in json_dict:
            scene.audio_source = json_dict["audio_source"]
        if "pause" in json_dict:
            scene.pause = json_dict["pause"]
        if "duration" in json_dict:
            scene.duration = json_dict["duration"]
        if "in_point" in json_dict:
            scene.in_point = json_dict["in_point"]
        if "out_point" in json_dict:
            scene.out_point = json_dict["out_point"]
        if "notes" in json_dict:
            scene.notes = json_dict["notes"]
        if "exif" in json_dict:
            scene.exif = json_dict["exif"]
        if "source_hash" in json_dict:
            scene.source_hash = json_dict["source_hash"]
        if "audio_source_hash" in json_dict:
            scene.audio_source_hash = json_dict["audio_source_hash"]

        item = QtGui.QStandardItem(icon, json_dict["source"])
        item.setDropEnabled(False)
        item.setData(scene)
        return item


class FilmStripWidget(QtWidgets.QListView):
    pass
    # def __init__(self, parent=None):
    #    super(FilmStripWidget, self).__init__(parent)


class FilmStripItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        # model = index.model()
        self.initStyleOption(option, index)
        # style = option.widget.style()
        super().paint(painter, option, index)


class SceneTableWidget(QtWidgets.QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.DefaultContextMenu)
        self.horizontalHeader().setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)

    def sortByColumn(self, column, order):
        popup = QtWidgets.QMessageBox(self)
        popup.setIcon(QtWidgets.QMessageBox.Icon.Question)
        popup.setText("Confirm sorting")
        popup.setInformativeText(f"Would you like to sort by column {column} in {order}?")
        popup.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Yes |
                                 QtWidgets.QMessageBox.StandardButton.No)
        popup.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
        popup.setModal(True)
        answer = popup.exec()

        if answer:
            super().sortByColumn(column, order)

    def contextMenuEvent(self, e):
        handled = False
        index = self.indexAt(e.pos())

        menu = QtWidgets.QMenu()
        # dummy = QtGui.QAction("Dummy action", menu) # default action for all columns

        if index.column() == 0:
            action_1 = QtGui.QAction("Delete scene", menu)
            action_1.triggered.connect(lambda x: self.model().deleteScene(index))
            menu.addAction(action_1)
            handled = True
        elif index.column() == 1:
            action_2 = QtGui.QAction("Inherit audio from above", menu)
            selected_rows = []
            item_selection = self.selectionModel().selection()
            for selected_index in item_selection.indexes():
                if selected_index.column() == 0:
                    selected_rows.append(selected_index)
            if len(selected_rows) > 1:
                action_2.triggered.connect(lambda x: self.model().inheritAudio(selected_rows))
                menu.addAction(action_2)
            handled = True

        if handled:
            menu.addSeparator()
            # menu.addAction(dummy)
            menu.exec(e.globalPos())
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        if e.source() is self:
            QtCore.qDebug("Internal move")
        else:
            QtCore.qDebug("External drop")
        super().dropEvent(e)

    def dragEnterEvent(self, e):
        if e.source() is self:
            QtCore.qDebug(f"Entered internal drag with MIME {str(e.mimeData())}")
            super().dragEnterEvent(e)
        else:
            formats = e.mimeData().formats()
            QtCore.qDebug(f"Entered external drag from {e.source()} with MIME {e.mimeData().formats()}")
            if ("x-application-pyMultiVision-STILLS" in formats or
                    "x-application-pyMultiVision-VIDEO" in formats or
                    "x-application-pyMultiVision-AUDIO" in formats):
                e.accept()

    def dragMoveEvent(self, e):
        if e.source() is self:
            super().dragMoveEvent(e)
        else:
            cursor_pos = self.viewport().mapFromGlobal(QtGui.QCursor().pos())
            index = self.indexAt(cursor_pos)
            self.setDragDropOverwriteMode(False)

            formats = e.mimeData().formats()
            if ("x-application-pyMultiVision-STILLS" in formats or "x-application-pyMultiVision-VIDEO" in formats and
                index.column() == 0) or ("x-application-pyMultiVision-AUDIO" in formats and index.column() == 1):
                self.setDropIndicatorShown(True)
                e.accept()
            else:
                self.setDropIndicatorShown(False)
                e.ignore()


class SceneTableTextOnlyDelegate(QtWidgets.QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QtCore.QSize(50, 12)

    def paint(self, painter, option, index):
        text = index.data(QtCore.Qt.ItemDataRole.DisplayRole)

        textFont = QtGui.QFont(option.font)
        textFont.setPixelSize(20)
        fm = QtGui.QFontMetrics(textFont)
        textRect = QtCore.QRectF(option.rect)
        # titleRect.setLeft(iconRect.right())
        textRect.setHeight(fm.height())

        color = (
            option.palette.color(QtGui.QPalette.ColorRole.BrightText)
            if option.state & QtWidgets.QStyle.StateFlag.State_Selected
            else option.palette.color(QtGui.QPalette.ColorRole.WindowText)
        )
        painter.save()
        painter.setFont(textFont)
        pen = painter.pen()
        pen.setColor(color)
        painter.setPen(pen)
        painter.drawText(textRect, text)
        painter.restore()


class ProjectBinWidget(QtWidgets.QTreeView):
    def __init__(self, parent=None):
        QtWidgets.QTreeView.__init__(self, parent)
        self.dragStartPosition = QtCore.QPoint()

    def dragEnterEvent(self, e):
        QtCore.qDebug(f"Entering drag from {e.source()} ({e.mimeData().formats()})")
        # cursor_pos = self.viewport().mapFromGlobal(QtGui.QCursor().pos())
        # selected_index = self.indexAt(cursor_pos)
        # selected_item = self.model().itemData(selected_index)

        super().dragEnterEvent(e)

    def mousePressEvent(self, e):
        if e.buttons() == QtCore.Qt.MouseButton.LeftButton:
            self.dragStartPosition = e.pos()
        super().mousePressEvent(e)

    '''
    def mouseMoveEvent(self, e):
        if e.buttons() == QtCore.Qt.MouseButton.LeftButton:
            if (e.pos() - self.dragStartPosition).manhattanLength() > QtWidgets.QApplication.startDragDistance():
                drag = QtGui.QDrag(self)
                mime = QtCore.QMimeData()

                selected_index = self.selectedIndexes()[0]
                item = selected_index.model().itemData(selected_index)
                parent_index = selected_index.parent()
                if parent_index.model() is not None:
                    parent_item = parent_index.model().itemData(parent_index)
                    if parent_item[0] == "STILLS":
                        mime.setData("x-application-pyMultiVision-STILLS", b"")
                    elif parent_item[0] == "VIDEO":
                        mime.setData("x-application-pyMultiVision-VIDEO", b"")
                    elif parent_item[0] == "AUDIO":
                        mime.setData("x-application-pyMultiVision-AUDIO",
                                     bytes(selected_index.model().data(selected_index).encode("utf-8")))
                    drag.setMimeData(mime)
                    icon = selected_index.model().data(selected_index, QtCore.Qt.ItemDataRole.DecorationRole)
                    if type(icon) is QtGui.QIcon:
                        drag.setPixmap(icon.pixmap(50, 50))
                    drag.exec(QtCore.Qt.DropAction.LinkAction)
                    e.accept()
                else:
                    parent_item = None
                    e.ignore()
                QtCore.qDebug(f"dragging item {item} with parent {parent_item}")
    '''


class ProjectBinModel(QtGui.QStandardItemModel):
    def __init__(self, parent=None):
        QtGui.QStandardItemModel.__init__(self, parent)

    def supportedDropActions(self):
        return QtCore.Qt.DropAction.IgnoreAction

    def supportedDragActions(self):
        return QtCore.Qt.DropAction.CopyAction | QtCore.Qt.DropAction.LinkAction

    def mimeTypes(self):
        types = ["x-application-pyMultiVision-STILLS", "x-application-pyMultiVision-AUDIO",
                 "x-application-pyMultiVision-VIDEO"]

        return types

    def mimeData(self, indexes):
        types = self.mimeTypes()

        for index in indexes:
            if index.isValid() and len(types) > 0 and index.column() == 0:
                mime_data = QtCore.QMimeData()
                format_type = types[0]

                item = index.model().itemData(index)[0]
                parent_index = index.parent()
                if parent_index.model() is not None:
                    parent_item = parent_index.model().itemData(parent_index)[0]
                    if parent_item == "STILLS":
                        format_type = "x-application-pyMultiVision-STILLS"
                    elif parent_item == "VIDEO":
                        format_type = "x-application-pyMultiVision-VIDEO"
                    elif parent_item == "AUDIO":
                        format_type = "x-application-pyMultiVision-AUDIO"

                encoded = QtCore.QByteArray()
                stream = QtCore.QDataStream(encoded, QtCore.QDataStream.OpenModeFlag.WriteOnly)

                stream.writeQString(item)
                mime_data.setData(format_type, encoded)

                return mime_data


class BinItem(QtGui.QStandardItem):
    def __init__(self, *__args):
        super().__init__()


def getPixmapFromScene(scene: Mv_Scene) -> QtGui.QPixmap:
    if scene:
        #if type(scene.pixmap) is QtGui.QPixmap:
        #    pixmap = scene.pixmap
        #else:
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


def scalePixmapToWidget(widget: QtWidgets.QWidget,
                        pixmap: QtGui.QPixmap,
                        mode=QtCore.Qt.TransformationMode.FastTransformation):
    scaled_pixmap = pixmap.scaled(
        widget.size(),
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        mode)

    return scaled_pixmap


def getKeyframeFromVideo(path) -> QtGui.QImage:
    with av.open(path) as container:
        stream = container.streams.video[0]
        stream.codec_context.skip_frame = "NONKEY"
        container.streams.video[0].thread_type = "AUTO"

        # Get the first keyframe for the video and convert it to a QImage
        keyframe = next(container.decode(stream))
        # noinspection PyTypeChecker
        image: QtGui.QImage = PIL.ImageQt.ImageQt(keyframe.to_image())

        # Use convertTo to detach image from original buffer before returning
        image.convertTo(QtGui.QImage.Format.Format_RGB888)

    return image


def get_supported_mime_types() -> list:
    result = []
    for f in QtMultimedia.QMediaFormat().supportedFileFormats(QtMultimedia.QMediaFormat.ConversionMode.Decode):
        mime_type = QtMultimedia.QMediaFormat(f).mimeType()
        result.append(mime_type.name())
    return result


def jsonValFromPixmap(pixmap: QtGui.QPixmap) -> str:
    buf = QtCore.QBuffer()
    pixmap.save(buf, "PNG")

    ba1 = buf.data().toBase64()

    decoder = QtCore.QStringDecoder(QtCore.QStringDecoder.Encoding.Latin1)

    return decoder(ba1)


def pixmapFromJsonVal(val: str) -> QtGui.QPixmap:
    encoded = val.encode('latin-1')

    pixmap = QtGui.QPixmap()
    pixmap.loadFromData(QtCore.QByteArray.fromBase64(encoded), "PNG")

    return pixmap


def timeStringFromMsec(msec: int):
    minutes = msec // 60000
    seconds = (msec // 1000) % 60
    milliseconds = msec % 1000

    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


class Ui_mainWindow(QtWidgets.QMainWindow, Ui_mainWindow_pyMultiVision):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.setupUi(self)

        self.pushButton_playPausePreview.setIcon(
            self.pushButton_playPausePreview.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))

        self.project = Mv_Project()
        self.project.mvshow = Mv_Show()
        self.mvshow = self.project.mvshow
        self.pv = None
        self.save_file = None
        self.changes_saved = True
        self.supported_mime_types = get_supported_mime_types()
        self.scene_index = 0

        self.videoPreviewPlayer = QtMultimedia.QMediaPlayer(parent=self)
        self.videoPreviewPlayer.setVideoOutput(self.videoPreviewWidget)
        self.pushButton_playPausePreview.clicked.connect(self.playPauseVideoPreview)
        self.pushButton_inPoint.clicked.connect(self.setVideoInPoint)
        self.pushButton_outPoint.clicked.connect(self.setVideoOutPoint)
        self.videoTimer = QtCore.QTimer()

        sequence_model = self.mvshow.sequence
        self.listView_filmStrip.setModel(sequence_model)
        self.tableView_scenes.setModel(sequence_model)
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

        bin_model = self.project.clear_bin()
        self.treeView.setModel(bin_model)

        self.threadpool = QtCore.QThreadPool().globalInstance()
        # self.threadpool.setMaxThreadCount(1)
        QtCore.qInfo("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())
        QtCore.qInfo("Supported media MIME types: %s" % self.supported_mime_types)

        self.screens = app.screens()
        for i, s in enumerate(self.screens):
            QtCore.qInfo(f"Found screen {i} in {s.orientation().name} with resolution "
                         f"{s.availableGeometry().width()}x{s.availableGeometry().height()}.")

        if len(self.screens) > 1:
            qr = self.screens[0].geometry()
            self.move(qr.left(), qr.top())

        # self.tableView_scenes.setItemDelegateForColumn(1, SceneTableTextOnlyDelegate())
        self.pushButton_mediaSourceDirectory.clicked.connect(self.sceneFromDirectoryDialog)
        self.pushButton_startShow.clicked.connect(self.openPresenterView)
        self.mvshow.sequence.dataChanged.connect(self.changed)
        self.mvshow.sequence.layoutChanged.connect(self.changed)
        self.mvshow.sequence.rowsInserted.connect(self.changed)
        self.mvshow.sequence.rowsRemoved.connect(self.changed)
        self.mvshow.sequence.rowsRemoved.connect(self.showScenePreview)
        self.tableView_scenes.selectionModel().selectionChanged.connect(self.syncSelection)
        self.tableView_scenes.selectionModel().selectionChanged.connect(self.showScenePreview)
        self.listView_filmStrip.selectionModel().selectionChanged.connect(self.syncSelection)
        self.listView_filmStrip.selectionModel().selectionChanged.connect(self.showScenePreview)
        self.mvshow.sequence.rowsInserted.connect(self.tableView_scenes.resizeColumnsToContents)
        self.textEdit_notes.textChanged.connect(self.updateSceneNotes)
        self.actionNew.triggered.connect(self.newProject)
        self.actionOpen.triggered.connect(self.loadFromFile)
        self.actionSave.triggered.connect(self.saveToFile)
        self.actionSave_As.triggered.connect(self.saveAsFileDialog)
        self.actionQuit.triggered.connect(self.quitProject, QtCore.Qt.ConnectionType.QueuedConnection)

        self.FilmStripDelegate = FilmStripItemDelegate()
        # self.listView_filmStrip.setItemDelegate(self.FilmStripDelegate)

    def resizeEvent(self, event):
        # Override QMainWindow's resizeEvent handler to
        # repaint the scene preview if the window size has changed
        # self.showScenePreview(self.listView_filmStrip.selectionModel().selection().indexes())
        QtWidgets.QMainWindow.resizeEvent(self, event)

    def closeEvent(self, event):
        # Override QMainwindow's closeEvent handler to
        # ignore the close event and call quitProject instead to handle unsaved changes
        event.ignore()
        self.quitProject()

    def newProject(self):
        if self.changes_saved:
            self.project.clear_bin()
            self.mvshow.sequence.clear()
            self.mvshow.sequence.__init__()
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
                # In case the user selected 'Cancel', do nothing:
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
                if self.saveToFile():
                    self.loadFromFile(file_name)
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
        with gzip.open(self.save_file, 'wt', encoding='ascii') as f:
            json.dump(self.mvshow.toJson(progress_callback), f)

    def loadProjectFromFile(self, file_name, progress_callback):
        try:
            with gzip.open(file_name, 'r') as f:
                json_string = json.load(f)
        except gzip.BadGzipFile:
            with open(file_name, 'r') as f:
                json_string = json.load(f)

        self.mvshow.fromJson(json_string, progress_callback)
        self.save_file = file_name

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
            # self.populateModelFromDirectory(dir_name, None)

    def populateModelFromDirectory(self, dir_name, progress_callback):
        directory = sorted(os.listdir(dir_name))
        num_files = len(directory)

        for index, file in enumerate(directory):
            progress_callback.emit(int((index + 1) * 100 / num_files))

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
                audiopath = ""
                pixmap = QtGui.QPixmap(path)
                # try:
                #     pil_image = PIL.Image.open(path)
                #     exif_tags = pil_image.getexif()
                # except PIL.UnidentifiedImageError:
                #     exif_tags = []

                exif_data = exiftool.ExifToolHelper().get_metadata(path)[0]
                scene = Mv_Scene(source=path,
                                 audio_source=audiopath,
                                 pixmap=pixmap.scaled(MV_PREVIEW_SIZE, MV_PREVIEW_SIZE,
                                                      QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                                      QtCore.Qt.TransformationMode.SmoothTransformation),
                                 scene_type=Scene_Type.STILL,
                                 exif=exif_data)
                QtCore.qDebug(f"Adding image scene from file {path}")

                # print(f"ExifTool: {scene.exif}")
                # print(f"PIL: {exif_tags}")
                bin_item = QtGui.QStandardItem(path)
                bin_item.setDragEnabled(True)
                bin_item.setDropEnabled(False)
                if "EXIF:CreateDate" in scene.exif:
                    bin_item.setData(scene.exif["EXIF:CreateDate"])
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
                                 pixmap=pixmap.scaled(MV_PREVIEW_SIZE, MV_PREVIEW_SIZE,
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

                bin_item = QtGui.QStandardItem(path)
                parent = self.project.bin.findItems("VIDEO", QtCore.Qt.MatchFlag.MatchExactly, 0)[0]
                parent.appendRow(bin_item)
                QtCore.qDebug(f"Adding video file {path} to project bin")
            elif mimetype.startswith("audio/"):
                bin_item = QtGui.QStandardItem(path)
                parent = self.project.bin.findItems("AUDIO", QtCore.Qt.MatchFlag.MatchExactly, 0)[0]
                parent.appendRow(bin_item)
                QtCore.qDebug(f"Adding audio file {path} to project bin")
                # Audio items will only be added to the project bin, but no scene item will be created, so continue:
                continue
            else:
                QtCore.qInfo(f"File {file.encode("utf-8", "ignore")} ({mimetype}) is not supported.")
                # Files with MIME types that we do not understand will be ignored, so continue:
                continue

            scene_item = QtGui.QStandardItem(file)
            scene_item.setData(scene)
            # scene_item.setData(audiopath, QtCore.Qt.ItemDataRole.UserRole + 1)
            # scene_item.setData(scene.duration, QtCore.Qt.ItemDataRole.UserRole + 2)
            scene_item.setDropEnabled(False)

            self.mvshow.sequence.appendRow(scene_item)

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
        if self.mvshow.length() > 0:
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

    def showScenePreview(self, selection):
        if type(selection) == QtCore.QItemSelection and len(selection.indexes()) > 0:
            scene_index = selection.indexes()[0]
        elif type(selection) == QtCore.QModelIndex:
            scene_index = selection
        else:
            return

        if scene_index.isValid():
            QtCore.qDebug(f"Showing preview for row {scene_index.row()} "
                          f"({len(self.mvshow.sequence._sequence)} items in list, "
                          f"{len(self.mvshow.sequence._scenes)} scenes in show)")
            scene: Mv_Scene = self.mvshow.sequence.item(scene_index.row())

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
                    self.horizontalSlider_videoPosition.setMaximum(scene.duration)

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

            scene = self.mvshow.sequence.item(self.scene_index)
            if position == scene.out_point:
                self.videoPreviewPlayer.pause()
        else:
            self.videoPreviewPlayer.setPosition(position)

    def setVideoInPoint(self):
        scene_index = self.mvshow.sequence.index(self.scene_index, 4)
        if scene_index.isValid():
            self.mvshow.sequence.setData(scene_index,
                                         self.horizontalSlider_videoPosition.value(),
                                         QtCore.Qt.ItemDataRole.EditRole)

    def setVideoOutPoint(self):
        scene_index = self.mvshow.sequence.index(self.scene_index, 5)
        if scene_index.isValid():
            self.mvshow.sequence.setData(scene_index,
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
        scene = self.mvshow.sequence.item(self.scene_index)
        if scene:
            #scene_data = scene.data(QtCore.Qt.ItemDataRole.UserRole)
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

        self.parent.mvshow.state_changed.connect(self.progressBar_state.setFormat)
        self.parent.mvshow.state_changed.connect(lambda x: self.scene_runner())
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
        self.audio_fade_in_anim.finished.connect(lambda: self.uncheckPushButton(self.pushButton_audio_fadeIn))
        self.audio_fade_out_anim.finished.connect(self.fadeOutFinished)
        self.audio_fade_out_anim.finished.connect(lambda: self.uncheckPushButton(self.pushButton_audio_fadeOut))

        self.scene_timer = QtCore.QTimer()

        self.updateDialPosition()
        self.changeScene("first")

    def close(self):
        self.parent.mvshow.set_state(Show_States.STOPPED)
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
        if self.parent.mvshow.state() == Show_States.RUNNING:
            if scene_index is None:
                QtCore.qDebug(f"Fading out scene {self.current_scene}")
                self.mv.scene_fade_out_anim.start()
            else:
                scene = self.parent.mvshow.getScene(scene_index)
                if scene.duration > 0 or scene.duration == -1:
                    if scene.in_point >= 0 and scene.out_point >= 0:
                        duration = scene.out_point - scene.in_point
                    else:
                        duration = self.parent.spinBox_defaultDelay.value() if scene.duration == -1 else scene.duration
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
                    # self.scene_timer.singleShot(duration, self.scene_runner)
                    QtCore.qDebug(f"Running scene {self.current_scene} for {timeStringFromMsec(duration)}")
        else:
            self.progress_animation.stop()
            self.scene_timer.stop()

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
        elif action == "seek" and type(index) is int and 0 <= index < length and index != self.current_scene:
            self.current_scene = index
        else:
            return False

        scene = self.parent.mvshow.getScene(self.current_scene)
        prev_scene = self.parent.mvshow.getScene(self.current_scene - 1) if self.current_scene > 0 else None
        next_scene = self.parent.mvshow.getScene(self.current_scene + 1) if self.current_scene < (length - 1) else None

        self.label_sceneCounter.setText(f"{self.current_scene + 1}/{length}")
        self.updatePresenterView(scene, prev_scene, next_scene)

        if self.parent.mvshow.state() in (Show_States.RUNNING, Show_States.PAUSED, Show_States.FINISHED):
            self.mv.loadScene(scene)
            if self.parent.mvshow.state() == Show_States.RUNNING and self.current_scene >= (length - 1):
                self.parent.mvshow.set_state(Show_States.FINISHED)

        QtCore.qDebug(f"Changing scene to {self.current_scene}")
        self.scene_changed.emit(self.current_scene)

        return True

    def uncheckPushButton(self, button: QtWidgets.QPushButton):
        button.setChecked(False)

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
        state = self.parent.mvshow.state()
        try:
            self.mv.scene_fade_out_anim.finished.disconnect()
        except TypeError:
            pass
        self.mv.scene_fade_out_anim.finished.connect(lambda: self.changeScene("next"))

        if state in [Show_States.STOPPED, Show_States.FINISHED]:
            if len(self.parent.screens) > 1:
                QtCore.qDebug("There is more than one screen. Moving show window to next screen.")
                qr = self.parent.screens[1].geometry()
                for screen in self.parent.screens:
                    print(screen.geometry())
                print(f"{qr.left()}, {qr.top()}")
                self.mv.move(qr.left(), qr.top())
                # self.mv.showFullScreen()
            self.mv.show()
            self.parent.mvshow.set_state(Show_States.RUNNING)
        elif state == Show_States.PAUSED:
            self.parent.mvshow.set_state(Show_States.RUNNING)

    def pauseShow(self):
        if self.parent.mvshow.state() == Show_States.RUNNING:
            try:
                self.mv.scene_fade_out_anim.finished.disconnect()
            except TypeError:
                # A TypeError is raised if disconnect is called and there are no active connections
                pass

            self.parent.mvshow.set_state(Show_States.PAUSED)
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
        self.supported_mimetypes = get_supported_mime_types()

        self.videoPlayer.setVideoOutput(self.videoWidget)
        self.videoPlayer.setAudioOutput(self.videoAudioOutput)
        self.videoWidget.setGeometry(self.label_image.geometry())
        self.videoWidget.setAspectRatioMode(QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        # TODO: Use QGraphicsScene, videoitem (QGraphicsVideoItem) instead to allow for opacity effect:
        # https://forum.qt.io/topic/73384/video-to-image-transitions/2

        self.audioPlayer.setAudioOutput(self.musicAudioOutput)
        self.audioPlayer.setLoops(QtMultimedia.QMediaPlayer.Loops.Infinite)

        self.opacityEffect = QtWidgets.QGraphicsOpacityEffect()

        self.scene_fade_in_anim = QtCore.QPropertyAnimation(self.opacityEffect, b"opacity")
        self.scene_fade_in_anim.setEasingCurve(QtCore.QEasingCurve.Type.Linear)
        self.scene_fade_in_anim.setDuration(self.parent.parent.spinBox_transitionTime.value())
        self.scene_fade_in_anim.setStartValue(0)
        self.scene_fade_in_anim.setEndValue(1)

        self.scene_fade_out_anim = QtCore.QPropertyAnimation(self.opacityEffect, b"opacity")
        self.scene_fade_out_anim.setEasingCurve(QtCore.QEasingCurve.Type.Linear)
        self.scene_fade_out_anim.setDuration(self.parent.parent.spinBox_transitionTime.value() // 4)
        self.scene_fade_out_anim.setStartValue(1)
        self.scene_fade_out_anim.setEndValue(0)

        self.in_point_connection = QtCore.pyqtBoundSignal()
        self.out_point_connection = QtCore.pyqtBoundSignal()


    def close(self):
        self.videoPlayer.stop()
        self.audioPlayer.stop()
        super().close()

    def eventFilter(self, source, event):
        if source is self and event.type() in (
                QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Move, QtCore.QEvent.Type.Show):
            window_size = self.size()

            self.label_image.move(0, 0)
            self.label_image.setFixedSize(window_size)
            self.label_image.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            self.videoWidget.move(0, 0)
            self.videoWidget.setFixedSize(window_size)
            scene = self.parent.parent.mvshow.getScene(self.parent.current_scene)
            if scene.scene_type == Scene_Type.STILL:
                pixmap = QtGui.QPixmap()
                pixmap.load(scene.source)
                self.label_image.setPixmap(scalePixmapToWidget(
                    self.label_image,
                    pixmap,
                    QtCore.Qt.TransformationMode.SmoothTransformation))
        return super(Ui_multiVisionShow, self).eventFilter(source, event)

    def loadScene(self, scene: Mv_Scene):
        if scene.scene_type == Scene_Type.STILL:
            pixmap = QtGui.QPixmap()
            pixmap.load(scene.source)
            self.videoPlayer.stop()
            self.videoPlayer.setSource(QtCore.QUrl())
            self.videoWidget.hide()
            self.label_image.setPixmap(scalePixmapToWidget(
                self.label_image,
                pixmap,
                QtCore.Qt.TransformationMode.SmoothTransformation))
            self.label_image.setGraphicsEffect(self.opacityEffect)
            self.label_image.show()
            self.label_image.raise_()
        elif scene.scene_type == Scene_Type.VIDEO:
            self.label_image.hide()
            # TODO: Check if MIME Type of scene.source is supported and the file exists
            self.videoPlayer.setSource(QtCore.QUrl.fromLocalFile(scene.source))

            try:
                self.videoPlayer.playbackStateChanged.disconnect(self.in_point_connection)
                self.videoPlayer.positionChanged.disconnect(self.out_point_connection)
            except TypeError:
                pass

            if scene.in_point > 0:
                self.in_point_connection = self.videoPlayer.playbackStateChanged.connect(
                    lambda x: self.manageInPoint(scene.in_point))
            if scene.out_point > 0:
                self.out_point_connection = self.videoPlayer.positionChanged.connect(
                    lambda x: self.manageOutPoint(scene.out_point))

            if scene.play_video_audio:
                self.parent.pushButton_audio_quiet.click()

            self.videoPlayer.play()
            self.parent.parent.mvshow.state_changed.connect(self.manageVideoPlayback)
            self.videoWidget.setGraphicsEffect(self.opacityEffect)
            self.videoWidget.show()
            self.videoWidget.raise_()

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
        if self.parent.parent.mvshow.state() == Show_States.PAUSED:
            self.videoPlayer.pause()
        elif self.parent.parent.mvshow.state() == Show_States.RUNNING:
            self.videoPlayer.play()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    ui = Ui_mainWindow()

    qtmodern.styles.dark(app)

    if len(sys.argv) > 1:
        ui.loadFromFile(sys.argv[1])

    ui.show()
    sys.exit(app.exec())
