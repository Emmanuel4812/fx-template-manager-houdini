"""
FX Template Manager v3
Usa hou.qt.mainWindow() como parent - sin congelaciones en Houdini
"""

import os
import sys
import json
import subprocess
from pathlib import Path

import hou

from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtCore import Qt, QThread, Signal


def get_houdini_main_window():
    """Obtiene la ventana principal de Houdini de forma compatible"""
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == "MainWindow":
            return widget
    return QtWidgets.QApplication.activeWindow()


CONFIG_FILE = os.path.expanduser("~/.houdini/fx_template_manager_config.json")

# Referencia global para evitar que el garbage collector destruya la ventana
_window_instance = None


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"template_path": r"D:\escenasHoudiniRecursosVarios"}


def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


class Template:
    def __init__(self, folder: Path):
        self.path = folder
        self.name = folder.name
        self.hip_file = self._find_hip()
        self.preview_file = self._find_preview()

    def _find_hip(self):
        for f in sorted(self.path.glob("*.hip")):
            return f
        return None

    def _find_preview(self):
        for d in ["video", "videos", "preview", "previews"]:
            sub = self.path / d
            if sub.exists():
                for ext in ["*.mp4", "*.mov", "*.avi", "*.webm", "*.png", "*.jpg", "*.jpeg", "*.exr"]:
                    for f in sub.glob(ext):
                        return f
        for ext in ["*.mp4", "*.mov", "*.avi", "*.png", "*.jpg", "*.jpeg"]:
            for f in self.path.glob(ext):
                return f
        return None

    def is_video(self):
        if self.preview_file:
            return self.preview_file.suffix.lower() in [".mp4", ".mov", ".avi", ".webm"]
        return False

    def is_image(self):
        if self.preview_file:
            return self.preview_file.suffix.lower() in [".png", ".jpg", ".jpeg", ".exr"]
        return False


class TemplateLoader(QThread):
    done = Signal(list)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        templates = []
        p = Path(self.path)
        if not p.exists():
            self.done.emit([])
            return
        for item in sorted(p.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                t = Template(item)
                if t.hip_file:
                    templates.append(t)
        self.done.emit(templates)


class PreviewLabel(QtWidgets.QLabel):
    """Label que muestra imagen o texto de placeholder"""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(420, 280)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#1a1a1a; color:#555; border-radius:6px;")
        self.set_placeholder("Selecciona un template")

    def set_placeholder(self, text="Sin preview"):
        self.clear()
        self.setText(text)
        self.setStyleSheet("background:#1a1a1a; color:#555; border-radius:6px; font-size:13px;")

    def show_image(self, path: str):
        pix = QtGui.QPixmap(path)
        if pix.isNull():
            self.set_placeholder("Error cargando imagen")
            return
        scaled = pix.scaled(420, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)
        self.setStyleSheet("background:#1a1a1a; border-radius:6px;")


class FXTemplateManager(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("FX Template Manager")
        self.resize(860, 620)
        self.setWindowFlags(self.windowFlags() | Qt.Window)

        self.config = load_config()
        self.templates = []
        self.selected = None
        self._loader = None

        self._build_ui()
        self._load_templates()

    # ─── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QHBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Panel izquierdo ──
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(6)

        # Ruta
        path_row = QtWidgets.QHBoxLayout()
        self.path_label = QtWidgets.QLabel(self.config["template_path"])
        self.path_label.setStyleSheet("color:#aaa; font-size:11px;")
        self.path_label.setWordWrap(True)

        btn_change = QtWidgets.QPushButton("Cambiar ruta")
        btn_change.setFixedWidth(100)
        btn_change.clicked.connect(self._change_path)

        path_row.addWidget(self.path_label, 1)
        path_row.addWidget(btn_change)
        left.addLayout(path_row)

        # Buscador
        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText("Buscar template...")
        self.search_box.textChanged.connect(self._filter_list)
        left.addWidget(self.search_box)

        # Lista
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSpacing(2)
        self.list_widget.setStyleSheet("""
            QListWidget { background:#1e1e1e; border-radius:6px; }
            QListWidget::item { padding:6px 8px; border-radius:4px; color:#ddd; }
            QListWidget::item:selected { background:#2563eb; color:white; }
            QListWidget::item:hover:!selected { background:#2a2a2a; }
        """)
        self.list_widget.itemClicked.connect(self._on_select)
        left.addWidget(self.list_widget, 1)

        # Refresh
        self.btn_refresh = QtWidgets.QPushButton("Actualizar lista")
        self.btn_refresh.clicked.connect(self._load_templates)
        left.addWidget(self.btn_refresh)

        left_w = QtWidgets.QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(280)

        # ── Panel derecho ──
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(8)

        # Preview imagen
        self.preview = PreviewLabel()
        right.addWidget(self.preview)

        # Botón abrir video
        self.btn_video = QtWidgets.QPushButton("▶  Abrir video preview")
        self.btn_video.setVisible(False)
        self.btn_video.setStyleSheet("QPushButton{background:#374151;color:#ddd;padding:6px;border-radius:4px;} QPushButton:hover{background:#4b5563;}")
        self.btn_video.clicked.connect(self._open_video)
        right.addWidget(self.btn_video)

        # Info
        self.info_box = QtWidgets.QGroupBox("Template")
        info_layout = QtWidgets.QFormLayout()
        info_layout.setSpacing(6)

        self.lbl_name     = QtWidgets.QLabel("-")
        self.lbl_file     = QtWidgets.QLabel("-")
        self.lbl_preview  = QtWidgets.QLabel("-")

        for lbl in (self.lbl_name, self.lbl_file, self.lbl_preview):
            lbl.setStyleSheet("color:#ccc;")
            lbl.setWordWrap(True)

        info_layout.addRow(QtWidgets.QLabel("Nombre:"),  self.lbl_name)
        info_layout.addRow(QtWidgets.QLabel("Archivo:"), self.lbl_file)
        info_layout.addRow(QtWidgets.QLabel("Preview:"), self.lbl_preview)
        self.info_box.setLayout(info_layout)
        right.addWidget(self.info_box)

        right.addStretch()

        # Botón merge
        self.btn_merge = QtWidgets.QPushButton("  Merge con escena abierta")
        self.btn_merge.setFixedHeight(42)
        self.btn_merge.setEnabled(False)
        self.btn_merge.setStyleSheet("""
            QPushButton {
                background:#2563eb; color:white;
                font-weight:bold; font-size:13px;
                border-radius:6px;
            }
            QPushButton:hover  { background:#1d4ed8; }
            QPushButton:pressed{ background:#1e40af; }
            QPushButton:disabled{ background:#374151; color:#6b7280; }
        """)
        self.btn_merge.clicked.connect(self._do_merge)
        right.addWidget(self.btn_merge)

        right_w = QtWidgets.QWidget()
        right_w.setLayout(right)

        root.addWidget(left_w)
        root.addWidget(right_w, 1)

    # ─── Lógica ────────────────────────────────────────────────────────────────

    def _load_templates(self):
        self.list_widget.clear()
        self.templates = []
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Cargando...")

        self._loader = TemplateLoader(self.config["template_path"])
        self._loader.done.connect(self._on_loaded)
        self._loader.start()

    def _on_loaded(self, templates):
        self.templates = templates
        self._populate_list(templates)
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText(f"Actualizar lista  ({len(templates)} templates)")

    def _populate_list(self, templates):
        self.list_widget.clear()
        for t in templates:
            icon_char = "🎥" if t.is_video() else ("🖼" if t.is_image() else "📄")
            item = QtWidgets.QListWidgetItem(f"{icon_char}  {t.name}")
            item.setToolTip(str(t.hip_file))
            self.list_widget.addItem(item)

    def _filter_list(self, text):
        filtered = [t for t in self.templates if text.lower() in t.name.lower()]
        self._populate_list(filtered)
        # Guardar referencia de filtrado para que on_select use el correcto
        self._filtered = filtered

    def _on_select(self, item):
        text = self.search_box.text()
        pool = self._filtered if text else self.templates
        idx  = self.list_widget.row(item)
        if idx < 0 or idx >= len(pool):
            return
        self.selected = pool[idx]
        self._update_info()

    def _update_info(self):
        t = self.selected
        if not t:
            return

        self.lbl_name.setText(t.name)
        self.lbl_file.setText(t.hip_file.name)

        if t.preview_file:
            self.lbl_preview.setText(t.preview_file.name)
        else:
            self.lbl_preview.setText("Sin preview")

        # Preview
        if t.is_image():
            self.preview.show_image(str(t.preview_file))
            self.btn_video.setVisible(False)
        elif t.is_video():
            self.preview.set_placeholder(f"🎬  {t.preview_file.name}\n\nHaz click en 'Abrir video preview'")
            self.btn_video.setVisible(True)
        else:
            self.preview.set_placeholder("Sin preview disponible")
            self.btn_video.setVisible(False)

        self.btn_merge.setEnabled(True)

    def _open_video(self):
        if self.selected and self.selected.preview_file:
            os.startfile(str(self.selected.preview_file))

    def _change_path(self):
        new_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Selecciona carpeta de templates",
            self.config["template_path"]
        )
        if new_path:
            self.config["template_path"] = new_path
            save_config(self.config)
            self.path_label.setText(new_path)
            self._load_templates()

    def _do_merge(self):
        if not self.selected:
            return
        hip_path = str(self.selected.hip_file)
        try:
            # API correcta en Houdini 19.x — equivalente a File > Merge (Alt+M)
            hou.hipFile.merge(hip_path)
            QtWidgets.QMessageBox.information(
                self, "Merge completado",
                f"'{self.selected.name}' mergeado correctamente en la escena."
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error en merge", str(e))

    def closeEvent(self, event):
        global _window_instance
        _window_instance = None
        super().closeEvent(event)


# ─── Punto de entrada ──────────────────────────────────────────────────────────

def _create_window():
    global _window_instance

    if _window_instance is not None:
        _window_instance.raise_()
        _window_instance.activateWindow()
        return

    parent = get_houdini_main_window()
    win = FXTemplateManager(parent=parent)
    win.show()
    _window_instance = win


def show():
    # hdefereval ejecuta en el siguiente tick del event loop de Houdini
    # Esto evita que la Python Shell se congele
    import hdefereval
    hdefereval.executeDeferred(_create_window)
