from PySide6.QtWidgets import QWidget, QPushButton
from PySide6.QtGui import QPainter, QColor, QPen, QCursor
from PySide6.QtCore import Qt, QRect, QPoint, Signal


class CropOverlay(QWidget):
    cropSelected = Signal(int, int, int, int)  # x, y, w, h

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)

        self.start_pos = None
        self.end_pos = None
        self.dragging = False

        # Confirm button
        self.confirm_btn = QPushButton("Confirm Crop", self)
        self.confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        self.confirm_btn.hide()
        self.confirm_btn.clicked.connect(self.confirm_crop)

    def mousePressEvent(self, event):
        self.start_pos = event.pos()
        self.end_pos = event.pos()
        self.dragging = True
        self.confirm_btn.hide()
        self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.end_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.end_pos = event.pos()

        # Position confirm button near crop box
        rect = self.get_rect()
        self.confirm_btn.move(rect.x() + rect.width() - 120, rect.y() - 40)
        self.confirm_btn.show()

        self.update()

    def get_rect(self):
        if not self.start_pos or not self.end_pos:
            return QRect()
        return QRect(self.start_pos, self.end_pos).normalized()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Dim background
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))

        # Draw crop rectangle
        rect = self.get_rect()
        if not rect.isNull():
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawRect(rect)

            # Clear inside crop area
            painter.fillRect(rect, QColor(0, 0, 0, 0))

    def confirm_crop(self):
        rect = self.get_rect()
        self.cropSelected.emit(rect.x(), rect.y(), rect.width(), rect.height())
        self.close()
