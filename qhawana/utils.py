import hashlib
from typing import Optional

import PIL.ImageQt
import av
import xmlschema
import gpxpy

from PySide6 import QtCore, QtWidgets, QtGui, QtMultimedia, QtPositioning

import importlib.resources

res = importlib.resources.files("resources")


def forEachItemInModel(model: QtCore.QAbstractItemModel, parent=QtCore.QModelIndex()):
    for r in range(0, model.rowCount(parent)):
        index = model.index(r, 0, parent)
        data = model.data(index, QtCore.Qt.ItemDataRole.UserRole)

        if model.hasChildren(index):
            yield index, data
        else:
            yield None, data


def countRowsOfIndex(index=QtCore.QModelIndex()) -> int:
    count: int = 0
    model: QtCore.QAbstractItemModel = index.model()
    if model is None:
        return 0
    row_count: int = model.rowCount(index)
    count += row_count
    for r in range(row_count):
        count += countRowsOfIndex(model.index(r, 0, index))
    return count


def scalePixmapToWidget(widget: QtWidgets.QWidget,
                        pixmap: QtGui.QPixmap,
                        mode=QtCore.Qt.TransformationMode.FastTransformation) -> QtGui.QPixmap:
    scaled_pixmap = pixmap.scaled(
        widget.size(),
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        mode)

    return scaled_pixmap


def getKeyframeFromVideo(path) -> Optional[QtGui.QImage]:
    with av.open(path) as container:
        if len(container.streams.video) == 0:
            QtCore.qWarning(f"File {path} does not contain a video stream")
            return

        stream = container.streams.video[0]
        stream.codec_context.skip_frame = "NONKEY"
        container.streams.video[0].thread_type = "AUTO"

        # Get the first keyframe for the video and convert it to a QImage
        try:
            keyframe = next(container.decode(stream))
            # noinspection PyTypeChecker
            image: QtGui.QImage = PIL.ImageQt.ImageQt(keyframe.to_image())
        except StopIteration:
            QtCore.qWarning(f"Could not extract keyframe from file {path}")
        else:
            # Use convertTo to detach image from original buffer before returning
            image.convertTo(QtGui.QImage.Format.Format_RGB888)

    return image


def get_supported_mime_types() -> list[str]:
    result = []
    for f in QtMultimedia.QMediaFormat().supportedFileFormats(QtMultimedia.QMediaFormat.ConversionMode.Decode):
        mime_type = QtMultimedia.QMediaFormat(f).mimeType()
        result.append(mime_type.name())
    return result


def timeStringFromMsec(msec: int) -> str:
    minutes = msec // 60000
    seconds = (msec // 1000) % 60
    milliseconds = msec % 1000

    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def getFileHashSHA1(path: str, used_for_security=True) -> str:
    buf_size = 65536

    file_sha1 = hashlib.sha1(usedforsecurity=used_for_security)
    with open(path, 'rb') as f:
        while True:
            data = f.read(buf_size)
            if not data:
                break
            file_sha1.update(data)

    return file_sha1.hexdigest()


def validateGPX(path: str) -> bool:
    schema_1_0 = xmlschema.XMLSchema(str(res / "gpx-1.0-strict.xsd"))
    schema_1_1 = xmlschema.XMLSchema(str(res / "gpx-1.1-strict.xsd"))

    return schema_1_0.is_valid(path) or schema_1_1.is_valid(path)


def geoPathFromGPX(path) -> QtPositioning.QGeoPath:
    gpx = gpxpy.parse(open(path))

    geo_path = QtPositioning.QGeoPath()
    for point in gpx.waypoints:
        if point.elevation:
            geo_coordinate = QtPositioning.QGeoCoordinate(point.latitude, point.longitude, point.elevation)
        else:
            geo_coordinate = QtPositioning.QGeoCoordinate(point.latitude, point.longitude
                                                          )
        geo_path.addCoordinate(geo_coordinate)

    return geo_path
