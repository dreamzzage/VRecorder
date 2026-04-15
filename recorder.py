import sys
import subprocess
import threading

import pygetwindow as gw
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QFileDialog, QMessageBox,
    QGroupBox, QLineEdit
)
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRect, Signal


# ============================================================
#  CROP OVERLAY (MERGED)
# ============================================================

class CropOverlay(QWidget):
    cropSelected = Signal(int, int, int, int)

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

        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))

        rect = self.get_rect()
        if not rect.isNull():
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawRect(rect)
            painter.fillRect(rect, QColor(0, 0, 0, 0))

    def confirm_crop(self):
        rect = self.get_rect()
        self.cropSelected.emit(rect.x(), rect.y(), rect.width(), rect.height())
        self.close()


# ============================================================
#  MAIN RECORDER
# ============================================================

class WindowRecorderQt(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Recorder")
        self.resize(720, 360)

        self.ffmpeg_process = None
        self.output_path = ""
        self.crop_rect = None

        root = QVBoxLayout()
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # ---------------- VIDEO GROUP ----------------
        video_group = QGroupBox("Video Source")
        video_layout = QVBoxLayout()
        video_group.setLayout(video_layout)

        src_row = QHBoxLayout()
        src_label = QLabel("Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Window (gdigrab)", "Desktop (ddagrab)"])
        src_row.addWidget(src_label)
        src_row.addWidget(self.mode_combo)
        video_layout.addLayout(src_row)

        win_label = QLabel("Select Window (for Window mode):")
        video_layout.addWidget(win_label)

        win_row = QHBoxLayout()
        self.window_combo = QComboBox()
        win_row.addWidget(self.window_combo)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_windows)
        win_row.addWidget(self.refresh_btn)
        video_layout.addLayout(win_row)

        root.addWidget(video_group)

        # ---------------- AUDIO GROUP ----------------
        audio_group = QGroupBox("Audio")
        audio_layout = QVBoxLayout()
        audio_group.setLayout(audio_layout)

        audio_mode_row = QHBoxLayout()
        audio_mode_label = QLabel("Audio mode:")
        self.audio_mode_combo = QComboBox()
        self.audio_mode_combo.addItems([
            "None",
            "Desktop only",
            "Microphone only",
            "Desktop + Microphone"
        ])
        audio_mode_row.addWidget(audio_mode_label)
        audio_mode_row.addWidget(self.audio_mode_combo)
        audio_layout.addLayout(audio_mode_row)

        dev_row1 = QHBoxLayout()
        self.desktop_audio_edit = QLineEdit()
        self.desktop_audio_edit.setPlaceholderText('Desktop audio device (e.g. "virtual-audio-capturer")')
        dev_row1.addWidget(self.desktop_audio_edit)
        audio_layout.addLayout(dev_row1)

        dev_row2 = QHBoxLayout()
        self.mic_audio_edit = QLineEdit()
        self.mic_audio_edit.setPlaceholderText('Microphone device (e.g. "Microphone (Realtek...)")')
        dev_row2.addWidget(self.mic_audio_edit)
        audio_layout.addLayout(dev_row2)

        root.addWidget(audio_group)

        # ---------------- OUTPUT + CONTROLS ----------------
        out_row = QHBoxLayout()
        self.choose_output_btn = QPushButton("Choose Output File")
        self.choose_output_btn.clicked.connect(self.choose_output)
        out_row.addWidget(self.choose_output_btn)

        self.preview_btn = QPushButton("Live Preview")
        self.preview_btn.clicked.connect(self.start_preview)
        out_row.addWidget(self.preview_btn)

        root.addLayout(out_row)

        ctrl_row = QHBoxLayout()
        self.start_btn = QPushButton("Start Recording")
        self.start_btn.clicked.connect(self.start_recording)
        ctrl_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Recording")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_recording)
        ctrl_row.addWidget(self.stop_btn)

        # CROP BUTTON
        self.crop_btn = QPushButton("Crop Area")
        self.crop_btn.clicked.connect(self.open_crop_overlay)
        ctrl_row.addWidget(self.crop_btn)

        root.addLayout(ctrl_row)

        self.status_label = QLabel("Status: Idle")
        root.addWidget(self.status_label)

        self.setLayout(root)

        self.refresh_windows()

    def log(self, *args):
        print("[Qt GUI]", *args, flush=True)

    # ---------------- UI HELPERS ----------------

    def refresh_windows(self):
        self.window_combo.clear()
        windows = [w for w in gw.getAllTitles() if w.strip()]
        self.window_combo.addItems(windows)
        self.log("Found windows:", windows)

    def choose_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Choose Output File",
            "",
            "MP4 Files (*.mp4);;MKV Files (*.mkv);;AVI Files (*.avi)"
        )
        if path:
            self.output_path = path
            self.log("Output file set to:", self.output_path)

    # ---------------- CROP OVERLAY ----------------

    def open_crop_overlay(self):
        self.overlay = CropOverlay()
        screen = self.screen().geometry()
        self.overlay.setGeometry(screen)
        self.overlay.cropSelected.connect(self.apply_crop)
        self.overlay.showFullScreen()

    def apply_crop(self, x, y, w, h):
        self.crop_rect = (x, y, w, h)
        self.log(f"Crop selected: {x},{y} {w}x{h}")

    # ---------------- VIDEO INPUT ----------------

    def build_video_input_args(self, for_preview=False):
        mode = self.mode_combo.currentText()

        # -------- WINDOW MODE --------
        if mode.startswith("Window"):
            title = self.window_combo.currentText()
            if not title:
                raise RuntimeError("No window selected.")

            win = None
            for w in gw.getAllWindows():
                if w.title == title:
                    win = w
                    break
            if not win:
                raise RuntimeError("Window not found.")

            x, y, width, height = win.left, win.top, win.width, win.height
            width -= width % 2
            height -= height % 2

            args = [
                "-f", "gdigrab",
                "-framerate", "30",
                "-offset_x", str(x),
                "-offset_y", str(y),
                "-video_size", f"{width}x{height}",
                "-i", "desktop"
            ]

            vf = []

            if self.crop_rect:
                cx, cy, cw, ch = self.crop_rect
                vf.append(f"crop={cw}:{ch}:{cx}:{cy}")

            vf.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

            args += ["-vf", ",".join(vf)]
            return args

        # -------- DESKTOP MODE --------
        else:
            return [
                "-f", "ddagrab",
                "-framerate", "30",
                "-i", "desktop",
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"
            ]

    # ---------------- AUDIO INPUT ----------------

    def build_audio_input_args(self):
        mode = self.audio_mode_combo.currentText()
        desktop_dev = self.desktop_audio_edit.text().strip()
        mic_dev = self.mic_audio_edit.text().strip()

        args = []
        map_args = []

        if mode == "None":
            return args, map_args

        if mode in ("Desktop only", "Desktop + Microphone"):
            if not desktop_dev:
                raise RuntimeError("Desktop audio mode selected but no device set.")
            args += ["-f", "dshow", "-i", f"audio={desktop_dev}"]
            map_args += ["-map", "1:a"]

        if mode in ("Microphone only", "Desktop + Microphone"):
            if not mic_dev:
                raise RuntimeError("Microphone mode selected but no device set.")
            args += ["-f", "dshow", "-i", f"audio={mic_dev}"]
            if mode == "Microphone only":
                map_args += ["-map", "1:a"]

        return args, map_args

    # ---------------- PREVIEW ----------------

    def start_preview(self):
        try:
            vid_args = self.build_video_input_args(for_preview=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        cmd = ["ffplay", "-loglevel", "warning"] + vid_args
        threading.Thread(target=lambda: subprocess.run(cmd), daemon=True).start()

    # ---------------- RECORDING ----------------

    def start_recording(self):
        if not self.output_path:
            QMessageBox.critical(self, "Error", "Choose an output file first.")
            return

        try:
            vid_args = self.build_video_input_args()
            aud_args, aud_map = self.build_audio_input_args()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        cmd = ["ffmpeg", "-y", "-loglevel", "verbose"]
        cmd += vid_args
        cmd += aud_args

        cmd += ["-map", "0:v"]

        audio_mode = self.audio_mode_combo.currentText()

        if audio_mode == "None":
            pass
        elif audio_mode in ("Desktop only", "Microphone only"):
            cmd += aud_map
        else:
            cmd += [
                "-filter_complex", "[1:a][2:a]amix=inputs=2:normalize=1[aout]",
                "-map", "[aout]"
            ]

        cmd += [
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "veryfast",
            "-crf", "23",
            self.output_path
        ]

        def run_ffmpeg():
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.ffmpeg_process = proc

            def stream():
                for line in proc.stderr:
                    print("[ffmpeg]", line.rstrip())

            threading.Thread(target=stream, daemon=True).start()

            proc.wait()
            self.ffmpeg_process = None
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText("Status: Idle")

        threading.Thread(target=run_ffmpeg, daemon=True).start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Status: Recording...")

    # ---------------- STOP ----------------

    def stop_recording(self):
        if self.ffmpeg_process:
            try:
                self.ffmpeg_process.communicate(input="q")
            except:
                self.ffmpeg_process.terminate()

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Status: Stopped")
        QMessageBox.information(self, "Done", "Recording stopped.")


# ============================================================
#  MAIN
# ============================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = WindowRecorderQt()
    w.show()
    sys.exit(app.exec())
