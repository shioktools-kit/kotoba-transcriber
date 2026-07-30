"""ファイルをドラッグ＆ドロップで受け取る領域。クリックでも選択できる。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from . import styles


class DropArea(QFrame):
    filesDropped = Signal(list)
    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(108)
        self._palette_ref = styles.LIGHT
        self._dragging = False
        self._apply_style()

        title = QLabel("ここに音声・動画ファイルをドロップ")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignCenter)

        hint = QLabel(
            "クリックしてファイルを選ぶこともできます　/　フォルダのドロップにも対応\n"
            "mp3, m4a, wav, flac, mp4, mov, mkv など"
        )
        hint.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(hint)

    def set_palette(self, palette: styles.Palette) -> None:
        """テーマ切り替え時に呼ぶ。"""
        self._palette_ref = palette
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(styles.drop_area_qss(self._palette_ref, self._dragging))

    def _set_dragging(self, dragging: bool) -> None:
        self._dragging = dragging
        self._apply_style()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_dragging(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_dragging(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_dragging(False)
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if paths:
            event.acceptProposedAction()
            self.filesDropped.emit(paths)
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)
