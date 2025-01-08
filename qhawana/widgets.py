from PyQt6 import QtWidgets, QtCore, QtGui


class FilmStripWidget(QtWidgets.QListView):
    def __init__(self, parent=None):
        super().__init__(parent)


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
        action_delete_scene = QtGui.QAction("Delete scene", menu)
        action_delete_scene.triggered.connect(lambda x: self.model().deleteScene(index))

        if index.column() == 0:
            action_edit_scene = QtGui.QAction("Edit scene", menu)
            menu.addAction(action_edit_scene)
            handled = True
        elif index.column() == 1:
            action_inherit_audio = QtGui.QAction("Inherit audio from above", menu)
            selected_rows = []
            item_selection = self.selectionModel().selection()
            for selected_index in item_selection.indexes():
                if selected_index.column() == 0:
                    selected_rows.append(selected_index)
            if len(selected_rows) > 1:
                action_inherit_audio.triggered.connect(lambda x: self.model().inheritAudio(selected_rows))
                menu.addAction(action_inherit_audio)
            handled = True

        if handled:
            menu.addSeparator()
            menu.addAction(action_delete_scene)
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
            if ("x-application-Qhawana-STILLS" in formats or
                    "x-application-Qhawana-VIDEO" in formats or
                    "x-application-Qhawana-AUDIO" in formats):
                e.accept()

    def dragMoveEvent(self, e):
        if e.source() is self:
            super().dragMoveEvent(e)
        else:
            cursor_pos = self.viewport().mapFromGlobal(QtGui.QCursor().pos())
            index = self.indexAt(cursor_pos)
            self.setDragDropOverwriteMode(False)

            formats = e.mimeData().formats()
            if (index.isValid() and (
                    ("x-application-Qhawana-STILLS" in formats or
                     "x-application-Qhawana-VIDEO" in formats) and
                    index.column() == 0) or
                    ("x-application-Qhawana-AUDIO" in formats and
                     index.column() == 1)):
                self.setDropIndicatorShown(True)
                e.accept()
            else:
                self.setDropIndicatorShown(False)
                e.ignore()


class ProjectBinWidget(QtWidgets.QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
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
                        mime.setData("x-application-Qhawana-STILLS", b"")
                    elif parent_item[0] == "VIDEO":
                        mime.setData("x-application-Qhawana-VIDEO", b"")
                    elif parent_item[0] == "AUDIO":
                        mime.setData("x-application-Qhawana-AUDIO",
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
