import QtQuick
import QtLocation
import QtPositioning

Item {
    anchors.fill: parent

    Plugin {
        id: mapPlugin
        name: "osm"
        PluginParameter {
            name: "osm.mapping.providersrepository.disabled"
            value: "true"
        }
        PluginParameter {
            name: "osm.mapping.custom.host";
            // value: "tile.openstreetmap.org/{z}/{x}/{y}.png"
            value: "a.tile.opentopomap.org/{z}/{x}/{y}.png"
        }
    }

    Map {
        id: map
        plugin: mapPlugin
        anchors.fill: parent
        zoomLevel: Math.floor((maximumZoomLevel - minimumZoomLevel) / 2)
        activeMapType: MapType.CustomMap
        center {
            // The Qt Company in Oslo
            latitude: 59.9485
            longitude: 10.7686
        }
        MapPolyline {
            id: pl
            line.width: 5
            line.color: 'red'
        }
        function loadPath(path) {
            var lines = []
            for(var i=0; i < path.size(); i++){
                lines[i] = path.coordinateAt(i)
            }
            return lines;
        }
        Connections {
            target: br
            function onMove(lat, lon) {
                map.center = QtPositioning.coordinate(lat, lon)
            }
            function onPath(path) {
                pl.path = map.loadPath(path)
            }
            function onFit() {
                map.fitViewportToMapItems()
            }
        }
    }
}