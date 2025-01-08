import enum


class Constants(enum.IntEnum):
    MV_ICON_SIZE = 100
    MV_PREVIEW_SIZE = 800


class Scene_Type(enum.IntEnum):
    EMPTY = 0
    STILL = 1
    VIDEO = 2


class Show_States(enum.IntEnum):
    STOPPED = 0
    RUNNING = 1
    PAUSED = 2
    FINISHED = 3
