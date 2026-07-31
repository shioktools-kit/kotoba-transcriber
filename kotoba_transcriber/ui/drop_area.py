"""ファイルをドラッグ＆ドロップで受け取る領域。クリックでも選択できる。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
)
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from . import styles
from .styles import Palette, qcolor


class _UploadIcon(QWidget):
    """円の中に上向き矢印を描くだけの小さなアイコン。"""

    def __init__(self, palette: Palette, parent=None) -> None:
        super().__init__(parent)
        self._palette = palette
        self.setFixedSize(52, 52)

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())
        painter.setPen(Qt.NoPen)
        painter.setBrush(qcolor(self._palette.accent_soft))
        painter.drawEllipse(rect)

        accent = QColor(self._palette.accent)
        cx = self.width() / 2
        cy = self.height() / 2

        # 縦棒
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(cx - 1, cy - 2, 2, 12), 1, 1)

        # 三角（矢じり）
        path = QPainterPath()
        path.moveTo(cx, cy - 10)
        path.lineTo(cx - 6, cy - 2)
        path.lineTo(cx + 6, cy - 2)
        path.closeSubpath()
        painter.drawPath(path)


class DropArea(QFrame):
    filesDropped = Signal(list)
    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(150)
        self._palette_ref = styles.LIGHT
        self._dragging = False
        self._apply_style()

        self._icon = _UploadIcon(self._palette_ref)

        title = QLabel("ここに音声・動画ファイルをドロップ")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(styles.ui_font(15, QFont.Weight.Bold))

        hint = QLabel("またはクリックして選択・フォルダのドロップも可")
        hint.setAlignment(Qt.AlignCenter)
        hint.setFont(styles.ui_font(12.5))

        formats = QLabel("MP3・M4A・WAV・FLAC・MP4・MOV・MKV など")
        formats.setAlignment(Qt.AlignCenter)
        formats.setFont(styles.ui_font(11))

        self._title = title
        self._hint = hint
        self._formats = formats

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 30, 24, 30)
        layout.setSpacing(10)
        layout.addWidget(self._icon, 0, Qt.AlignHCenter)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(formats)

        self.set_palette(self._palette_ref)

    def set_palette(self, palette: styles.Palette) -> None:
        """テーマ切り替え時に呼ぶ。"""
        self._palette_ref = palette
        self._apply_style()
        self._icon.set_palette(palette)
        self._title.setStyleSheet(f"color: {palette.text_pri};")
        self._hint.setStyleSheet(f"color: {palette.text_muted};")
        self._formats.setStyleSheet(f"color: {palette.text_faint};")

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
