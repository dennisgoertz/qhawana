import json
import os
from typing import Optional

import av
from PySide6 import QtCore, QtGui

from qhawana.const import Constants, Scene_Type, Show_States
from qhawana.utils import (timeStringFromMsec, getFileHashSHA1, countRowsOfIndex, forEachItemInModel,
                           getKeyframeFromVideo)


class Mv_Project(QtCore.QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mv_show = Mv_Show(self)
        self.bin = ProjectBinModel(self)
        self.settings = ProjectSettings(self)


class Mv_Show(QtCore.QObject):
    state_changed = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sequence = Mv_sequence(parent=self)
        self.__state = Show_States.STOPPED

    def state(self):
        return self.__state

    def set_state(self, state: Show_States) -> bool:
        states = {Show_States.STOPPED: "stopped",
                  Show_States.PAUSED: "paused",
                  Show_States.RUNNING: "running",
                  Show_States.FINISHED: "finished"}
        if state != self.__state:
            self.__state = state
            self.state_changed.emit(states[state])
            QtCore.qDebug(f"Changing show state to {states[state]}")
            return True
        else:
            return False

    def length(self) -> int:
        return self.sequence.rowCount()

    def toJson(self, progress_callback) -> dict[str, list]:
        scenes = []
        num_scenes = self.sequence.rowCount()
        for i in range(num_scenes):
            item = self.sequence.item(i)
            scene_data = item.toJson(store_pixmap=True)
            scenes.append(scene_data)
            progress_callback.emit((i + 1) // num_scenes * 100)
        json_string = {"scenes": scenes}
        return json_string

    def fromJson(self, json_string: dict, progress_callback) -> None:
        self.sequence.clear()
        self.set_state(Show_States.STOPPED)
        num_scenes = len(json_string)
        for i, s in enumerate(json_string):
            progress_callback.emit((i + 1) // num_scenes * 100)
            scene = sceneItemFromJson(s)
            self.sequence.appendRow(scene)

    def getScene(self, index=0):
        return self.sequence.item(index) if 0 <= index < self.length() else False


class Mv_sequence(QtCore.QAbstractTableModel):
    # sequence is a list of QStandardItems with UUIDs referring to a Mv_Scene object
    _sequence = []

    # scenes is a dict of Mv_Scene objects with a UUID as the key
    _scenes = {}

    # horizontal_headers is a list of strings
    _horizontal_headers = []

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setHorizontalHeaderLabels([self.tr("Visual source"), self.tr("Audio source"), self.tr("Capture Time"),
                                        self.tr("Duration"), self.tr("In Point"), self.tr("Out Point")])

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
        elif index.column() == 4 and role == QtCore.Qt.ItemDataRole.DisplayRole:
            return timeStringFromMsec(item_data.in_point)
        elif index.column() == 4 and role == QtCore.Qt.ItemDataRole.EditRole:
            return str(item_data.in_point)
        elif index.column() == 5 and role == QtCore.Qt.ItemDataRole.DisplayRole:
            return timeStringFromMsec(item_data.out_point)
        elif index.column() == 5 and role == QtCore.Qt.ItemDataRole.EditRole:
            return str(item_data.out_point)

    def setData(self, index, value, role=...) -> bool:
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

    def clear(self) -> None:
        self.beginResetModel()
        self._sequence = []
        self._scenes = {}
        self.endResetModel()

    def deleteScene(self, index) -> bool:
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
            pass
        elif role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return self._horizontal_headers[section]
            elif orientation == QtCore.Qt.Orientation.Vertical:
                return section + 1

    def columnCount(self, parent=...) -> int:
        return len(self._horizontal_headers)

    def rowCount(self, parent=...) -> int:
        return len(self._sequence)

    def sceneCount(self) -> int:
        return len(self._scenes)

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

    def item(self, row):
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

    def supportedDragActions(self):
        return QtCore.Qt.DropAction.MoveAction

    def supportedDropActions(self):
        return QtCore.Qt.DropAction.MoveAction | QtCore.Qt.DropAction.CopyAction | QtCore.Qt.DropAction.LinkAction

    def insertRows(self, row, count, parent=...):
        self.beginInsertRows(parent, row, row + count - 1)
        for r in range(count):
            QtCore.qDebug(f"inserting row after {row}")
            self._sequence.insert(row, QtGui.QStandardItem())
        self.endInsertRows()
        return True

    def removeRows(self, row, count, parent=...):
        self.beginRemoveRows(parent, row, row + count - 1)
        for r in range(count):
            QtCore.qDebug(f"deleting row {row}")
            del self._sequence[row]
        self.endRemoveRows()
        return True

    def mimeTypes(self) -> list[str]:
        types = super().mimeTypes()
        types.append("x-application-Qhawana-STILLS")
        types.append("x-application-Qhawana-AUDIO")
        types.append("x-application-Qhawana-VIDEO")

        return types

    def mimeData(self, indexes) -> QtCore.QMimeData:
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

    def dropMimeData(self, data, action, row, column, parent) -> bool:
        QtCore.qDebug(f"Handling {action}")
        if data.hasFormat("application/x-qabstractitemmodeldatalist"):
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

        elif data.hasFormat('x-application-Qhawana-STILLS'):
            QtCore.qDebug("x-application-Qhawana-STILLS")

            return True
        elif data.hasFormat('x-application-Qhawana-AUDIO'):
            QtCore.qDebug("x-application-Qhawana-AUDIO")

            encoded = data.data("x-application-Qhawana-AUDIO")
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

    def flags(self, index) -> QtCore.Qt.ItemFlag:
        default_flags = super().flags(index)
        if index.isValid():
            flags = default_flags | QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsDragEnabled
            scene = self.item(index.row())
            if index.column() in [4, 5]:
                if scene and scene.scene_type == Scene_Type.VIDEO:
                    flags |= QtCore.Qt.ItemFlag.ItemIsEditable
                else:
                    flags ^= QtCore.Qt.ItemFlag.ItemIsEnabled
        else:
            flags = default_flags | QtCore.Qt.ItemFlag.ItemIsDropEnabled
        return flags

    def sort(self, column, order=...):
        rev = (order == QtCore.Qt.SortOrder.DescendingOrder)
        self.beginResetModel()
        self._sequence.sort(key=lambda x: self.dataFromItemAndColumn(x, column), reverse=rev)
        self.endResetModel()

    def dataFromItemAndColumn(self, sort_item: QtGui.QStandardItem, column: int) -> str:
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

        QtCore.qDebug(f"No sort key available for column {column} of scene {item_uuid}")
        return "0"

    def inheritAudio(self, selection: list[QtCore.QModelIndex]):
        QtCore.qDebug(f"Received {selection} of {len(selection)} rows")
        selection.sort(key=lambda x: x.row())
        audio_source = self.item(selection[0].row()).audio_source
        if audio_source:
            for i in selection:
                QtCore.qDebug(f"Setting audio source {audio_source} to scene {i.row()}")
                self.item(i.row()).audio_source = audio_source


class Mv_Scene(QtGui.QStandardItem):
    def __init__(self, source: str, scene_type: Scene_Type, audio_source="", pause=False, duration=-1,
                 in_point=-1, out_point=-1, play_video_audio=False, pixmap=None, notes="", exif=None, parent=None):

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
            try:
                source_hash = getFileHashSHA1(self.source, used_for_security=False)
            except FileNotFoundError:
                QtCore.qWarning(f"Source file {self.source} not found for scene {self.uuid.toString()}")
                pass
            else:
                self.source_hash = source_hash

        if self.audio_source:
            try:
                audio_source_hash = getFileHashSHA1(self.audio_source, used_for_security=False)
            except FileNotFoundError:
                QtCore.qWarning(f"Audio source file {self.audio_source} not found for scene {self.uuid.toString()}")
                pass
            else:
                self.audio_source_hash = audio_source_hash

        self.icon = QtGui.QIcon()
        if self.pixmap:
            self.icon.addPixmap(self.pixmap.scaled(Constants.MV_ICON_SIZE, Constants.MV_ICON_SIZE,
                                                   QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                                   QtCore.Qt.TransformationMode.SmoothTransformation),
                                QtGui.QIcon.Mode.Normal,
                                QtGui.QIcon.State.Off)

        super().__init__(parent)

    def __getstate__(self) -> list:
        state = [self.uuid, self.source, self.audio_source, self.scene_type,
                 self.pause, self.duration, self.notes, self.exif]
        byte_array = QtCore.QByteArray()
        stream = QtCore.QDataStream(byte_array, QtCore.QIODevice.OpenModeFlag.WriteOnly)
        stream << self.pixmap
        state.append(byte_array)

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
        if not stream.atEnd():
            self.pixmap.loadFromData(stream.readBytes())
        elif self.source:
            self.pixmap.load(self.source)

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


class ProjectBinModel(QtGui.QStandardItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.categoryItems = {"STILLS": None, "AUDIO": None, "VIDEO": None, "TRACKS": None}

    def clear(self):
        super().clear()
        self.beginResetModel()
        root = self.invisibleRootItem()
        for c in self.categoryItems.keys():
            ci = QtGui.QStandardItem(c)
            ci.setDragEnabled(False)
            ci.setDropEnabled(True)
            self.categoryItems[c] = ci
            root.appendRow(ci)
        self.setHorizontalHeaderLabels([self.tr("File"), self.tr("Details")])
        self.endResetModel()

    def supportedDropActions(self) -> QtCore.Qt.DropAction:
        return QtCore.Qt.DropAction.IgnoreAction

    def supportedDragActions(self) -> QtCore.Qt.DropAction:
        return QtCore.Qt.DropAction.CopyAction | QtCore.Qt.DropAction.LinkAction

    def mimeTypes(self) -> list[str]:
        types = ["x-application-Qhawana-STILLS", "x-application-Qhawana-AUDIO",
                 "x-application-Qhawana-VIDEO", "x-application-Qhawana-TRACKS"]

        return types

    def mimeData(self, indexes) -> Optional[QtCore.QMimeData]:
        types = self.mimeTypes()

        for index in indexes:
            if index.isValid() and len(types) > 0 and index.column() == 0:
                mime_data = QtCore.QMimeData()
                format_type = types[0]

                item = index.model().itemData(index)[QtCore.Qt.ItemDataRole.UserRole]
                parent_index = index.parent()
                if parent_index.model() is not None:
                    parent_item = parent_index.model().itemData(parent_index)[0]
                    if parent_item == "STILLS":
                        format_type = "x-application-Qhawana-STILLS"
                    elif parent_item == "VIDEO":
                        format_type = "x-application-Qhawana-VIDEO"
                    elif parent_item == "AUDIO":
                        format_type = "x-application-Qhawana-AUDIO"
                    elif parent_item == "TRACKS":
                        format_type = "x-application-Qhawana-TRACKS"

                encoded = QtCore.QByteArray()
                stream = QtCore.QDataStream(encoded, QtCore.QDataStream.OpenModeFlag.WriteOnly)

                stream.writeQString(item)
                mime_data.setData(format_type, encoded)

                return mime_data

    def toJson(self, progress_callback) -> dict:
        items = {}
        item_count = 0
        cur_item = 0

        for i in range(self.rowCount()):
            item_count += countRowsOfIndex(self.index(i, 0))

        for index, data in forEachItemInModel(self):
            if index:
                items[index.data()] = []
                for i, d in forEachItemInModel(self, index):
                    cur_item += 1
                    items[index.data()].append(d)
                    progress_callback.emit(cur_item // item_count * 100)

        json_string = {"project_bin": items}

        return json_string

    def fromJson(self, json_string: dict, progress_callback):
        num_items = 0
        for items in json_string.values():
            num_items += len(items)

        self.clear()
        self.beginResetModel()

        cur_item = 0
        for category, items in json_string.items():
            if category not in self.categoryItems.keys():
                QtCore.qWarning(f"Skipping items in unexpected category '{category}' when population project bin")
                cur_item += len(items)
                progress_callback.emit(cur_item // num_items * 100)
                continue

            for v in items:
                cur_item += 1
                progress_callback.emit(cur_item // num_items * 100)

                if not os.path.exists(v):
                    QtCore.qWarning(f"Skipping nonexistent item '{v}' for category '{category}'"
                                    f"when populating project bin")

                file = os.path.basename(v)
                bin_item = QtGui.QStandardItem(file)
                pixmap = None

                if category == "AUDIO":
                    pixmap = QtGui.QPixmap(Constants.MV_ICON_SIZE, Constants.MV_ICON_SIZE)
                    pixmap.fill(QtGui.QColor("black"))
                elif category == "STILLS":
                    pixmap = QtGui.QPixmap(v).scaled(Constants.MV_ICON_SIZE, Constants.MV_ICON_SIZE,
                                                     QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                                     QtCore.Qt.TransformationMode.FastTransformation)
                elif category == "VIDEO":
                    keyframe_image = getKeyframeFromVideo(v)
                    pixmap = (QtGui.QPixmap().fromImage(keyframe_image).
                              scaled(Constants.MV_ICON_SIZE, Constants.MV_ICON_SIZE,
                                     QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                     QtCore.Qt.TransformationMode.FastTransformation))
                elif category == "TRACKS":
                    pass

                if pixmap:
                    tooltip_image = jsonValFromPixmap(pixmap)
                    html = f'<img src="data:image/png;base64,{tooltip_image}">'
                    bin_item.setData(html, QtCore.Qt.ItemDataRole.ToolTipRole)

                bin_item.setData(v, QtCore.Qt.ItemDataRole.UserRole)
                self.categoryItems[category].appendRow(bin_item)

        self.endResetModel()


class BinItem(QtGui.QStandardItem):
    def __init__(self, *__args):
        super().__init__(*__args)


class ProjectSettings(QtCore.QObject):
    valueChanged = QtCore.Signal(str, list[str], name="valueChanged")

    def __init__(self, parent=None):
        self.__settings = {"transition_time": 1000, "default_delay": 5000}
        super().__init__(parent)

    def toJson(self) -> {str}:
        return {"settings": json.dumps(self.__settings)}

    def fromJson(self, json_string: {str}):
        for setting, value in json.loads(json_string).items():
            self.setProperty(setting, value)

    def getProperty(self, property_name: str):
        try:
            return self.__settings[property_name]
        except KeyError:
            return None

    def setProperty(self, property_name: str, value) -> bool:
        old_value = self.getProperty(property_name)
        if old_value == value:
            return False
        try:
            self.__settings[property_name] = value
        except (TypeError, ValueError):
            return False
        else:
            QtCore.qDebug(f'Setting "{property_name}" from "{old_value}" to "{value}"')
            self.valueChanged.emit(property_name, value)
            return True


def sceneItemFromJson(json_dict: dict) -> Optional[QtGui.QStandardItem]:
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
    icon.addPixmap(pixmap.scaled(Constants.MV_ICON_SIZE, Constants.MV_ICON_SIZE,
                                 QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                 QtCore.Qt.TransformationMode.SmoothTransformation),
                   QtGui.QIcon.Mode.Normal,
                   QtGui.QIcon.State.Off)

    scene = Mv_Scene(source=json_dict["source"],
                     scene_type=json_dict["scene_type"],
                     pixmap=pixmap.scaled(Constants.MV_PREVIEW_SIZE, Constants.MV_PREVIEW_SIZE,
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


def jsonValFromPixmap(pixmap: QtGui.QPixmap) -> str:
    buf = QtCore.QBuffer()
    pixmap.save(buf, "PNG")

    ba1 = buf.data().toBase64()

    # Bug in PySide, see here:
    # https://stackoverflow.com/questions/70749870/qstringdecoder-not-callable-in-pyside6
    # So we'll use plain python instead
    #
    # decoder = QtCore.QStringDecoder(QtCore.QStringDecoder.Encoding.Latin1)
    # return decoder(ba1)
    
    return ba1.data().decode('Latin1')


def pixmapFromJsonVal(val: str) -> QtGui.QPixmap:
    encoded = val.encode('latin-1')

    pixmap = QtGui.QPixmap()
    pixmap.loadFromData(QtCore.QByteArray.fromBase64(encoded), "PNG")

    return pixmap
