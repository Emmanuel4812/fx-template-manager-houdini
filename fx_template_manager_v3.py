"""
FX Template Manager v3 - UI Redesign
Grid de tarjetas con thumbnails, video embebido y menu contextual
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, List

import hou

from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtCore import Qt, QThread, Signal


CONFIG_FILE = os.path.expanduser("~/.houdini/fx_template_manager_config.json")
_window_instance = None

CARD_W = 200
CARD_H = 210
THUMB_H = 130


# ── Paleta de colores para placeholders (igual a OOL Library) ─────────────────
PLACEHOLDER_COLORS = [
    "#2563eb", "#7c3aed", "#db2777", "#059669",
    "#d97706", "#dc2626", "#0891b2", "#65a30d",
]


def _placeholder_color(name: str) -> str:
    return PLACEHOLDER_COLORS[sum(ord(c) for c in name) % len(PLACEHOLDER_COLORS)]


def _initials(name: str) -> str:
    words = name.replace("_", " ").replace("-", " ").split()
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return name[:2].upper()


# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"template_path": r"D:\escenasHoudiniRecursosVarios"}


def save_config(config: dict):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# ── Modelo de Template ────────────────────────────────────────────────────────

class Template:
    def __init__(self, folder: Path):
        self.path = folder
        self.name = folder.name
        self.hip_file      = self._find_hip()
        self.thumbnail_file = self._find_thumbnail()   # imagen de thumbnail/
        self.video_file    = self._find_video()        # video de video/

    def _find_hip(self) -> Optional[Path]:
        for f in sorted(self.path.glob("*.hip")):
            return f
        return None

    def _find_thumbnail(self) -> Optional[Path]:
        """Busca imagen en carpeta thumbnail/ o thumbnails/"""
        for d in ["thumbnail", "thumbnails"]:
            sub = self.path / d
            if sub.exists():
                for ext in ["*.png", "*.jpg", "*.jpeg", "*.exr"]:
                    for f in sub.glob(ext):
                        return f
        return None

    def _find_video(self) -> Optional[Path]:
        """Busca video en carpeta video/ o videos/"""
        for d in ["video", "videos"]:
            sub = self.path / d
            if sub.exists():
                for ext in ["*.mp4", "*.mov", "*.avi", "*.webm"]:
                    for f in sub.glob(ext):
                        return f
        return None

    def has_thumbnail(self) -> bool:
        return self.thumbnail_file is not None

    def has_video(self) -> bool:
        return self.video_file is not None


# ── Thread de carga ───────────────────────────────────────────────────────────

class TemplateLoader(QThread):
    done = Signal(list)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):
        templates = []
        p = Path(self.path)
        if p.exists():
            for item in sorted(p.iterdir()):
                if item.is_dir() and not item.name.startswith("."):
                    t = Template(item)
                    if t.hip_file:
                        templates.append(t)
        self.done.emit(templates)


# ── Flow layout (distribuye tarjetas automáticamente) ─────────────────────────

class _FlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self.setSpacing(12)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QtCore.QRect(0, 0, width, 0), test=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QtCore.QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test=False):
        m = self.contentsMargins()
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        row_h = 0
        sp = self.spacing()

        for item in self._items:
            w = item.sizeHint()
            next_x = x + w.width() + sp
            if next_x - sp > rect.right() - m.right() and row_h > 0:
                x = rect.x() + m.left()
                y += row_h + sp
                next_x = x + w.width() + sp
                row_h = 0
            if not test:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), w))
            x = next_x
            row_h = max(row_h, w.height())

        return y + row_h - rect.y() + m.bottom()


# ── Tarjeta individual ────────────────────────────────────────────────────────

class ThumbnailCard(QtWidgets.QFrame):
    clicked = Signal(object)
    merged  = Signal(object)
    explore = Signal(object)

    def __init__(self, template: Template, parent=None):
        super().__init__(parent)
        self.template = template
        self.setFixedSize(CARD_W, CARD_H)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self._selected = False
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.thumb = QtWidgets.QLabel()
        self.thumb.setFixedSize(CARD_W - 12, THUMB_H)
        self.thumb.setAlignment(Qt.AlignCenter)
        self._set_thumbnail()
        layout.addWidget(self.thumb)

        name_label = QtWidgets.QLabel(self.template.name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setStyleSheet("color:#ddd; font-size:11px; font-weight:500;")
        layout.addWidget(name_label)

        parts = []
        if self.template.has_video():
            parts.append("Video")
        if self.template.has_thumbnail():
            parts.append("Thumb")
        badge_text = "  ·  ".join(parts) if parts else "Sin preview"
        badge = QtWidgets.QLabel(badge_text)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet("color:#6b7280; font-size:10px;")
        layout.addWidget(badge)

        self._update_style()

    def _set_thumbnail(self):
        w, h = CARD_W - 12, THUMB_H

        # Prioridad 1: imagen de carpeta thumbnail/
        if self.template.has_thumbnail():
            pix = QtGui.QPixmap(str(self.template.thumbnail_file))
            if not pix.isNull():
                scaled = pix.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                x = (scaled.width()  - w) // 2
                y = (scaled.height() - h) // 2
                cropped = scaled.copy(max(0, x), max(0, y), w, h)
                self.thumb.setPixmap(self._round_pixmap(cropped))
                return

        # Prioridad 2: placeholder con color e iniciales
        color    = _placeholder_color(self.template.name)
        initials = _initials(self.template.name)

        pix = QtGui.QPixmap(w, h)
        pix.fill(QtGui.QColor(color))

        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Icono de video si tiene video
        if self.template.has_video():
            f = QtGui.QFont("Arial", 30)
            painter.setFont(f)
            painter.setPen(QtGui.QColor(255, 255, 255, 100))
            painter.drawText(pix.rect(), Qt.AlignCenter, "▶")

        f2 = QtGui.QFont("Arial", 24, QtGui.QFont.Bold)
        painter.setFont(f2)
        painter.setPen(QtGui.QColor(255, 255, 255, 200))
        painter.drawText(pix.rect(), Qt.AlignCenter, initials)
        painter.end()

        self.thumb.setPixmap(self._round_pixmap(pix))

    def _round_pixmap(self, pix: QtGui.QPixmap) -> QtGui.QPixmap:
        rounded = QtGui.QPixmap(pix.size())
        rounded.fill(Qt.transparent)
        p = QtGui.QPainter(rounded)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        path = QtGui.QPainterPath()
        path.addRoundedRect(0, 0, pix.width(), pix.height(), 6, 6)
        p.setClipPath(path)
        p.drawPixmap(0, 0, pix)
        p.end()
        return rounded

    def set_selected(self, value: bool):
        self._selected = value
        self._update_style()

    def _update_style(self):
        if self._selected:
            self.setStyleSheet("""
                ThumbnailCard { background:#1e3a5f; border:2px solid #2563eb; border-radius:8px; }
            """)
        else:
            self.setStyleSheet("""
                ThumbnailCard { background:#1e1e1e; border:2px solid transparent; border-radius:8px; }
                ThumbnailCard:hover { background:#252525; border:2px solid #374151; }
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.template)
        super().mousePressEvent(event)

    def _context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#1e1e1e; border:1px solid #374151; border-radius:6px; padding:4px; }
            QMenu::item { padding:7px 20px; color:#ddd; border-radius:4px; }
            QMenu::item:selected { background:#2563eb; }
        """)
        act_merge  = menu.addAction("Merge con escena abierta")
        act_folder = menu.addAction("Abrir carpeta")
        act_video  = menu.addAction("Reproducir video") if self.template.has_video() else None

        action = menu.exec_(self.mapToGlobal(pos))
        if action == act_merge:
            self.merged.emit(self.template)
        elif action == act_folder:
            self.explore.emit(self.template)
        elif act_video and action == act_video:
            os.startfile(str(self.template.video_file))


# ── Grid scrolleable ──────────────────────────────────────────────────────────

class TemplateGrid(QtWidgets.QScrollArea):
    template_selected = Signal(object)
    merge_requested   = Signal(object)
    explore_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { border:none; background:transparent; }")

        self._container = QtWidgets.QWidget()
        self._layout = _FlowLayout(self._container)
        self.setWidget(self._container)

        self._cards: List[ThumbnailCard] = []

    def populate(self, templates: List[Template]):
        for card in self._cards:
            self._layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        for t in templates:
            card = ThumbnailCard(t)
            card.clicked.connect(self._on_card_clicked)
            card.merged.connect(self.merge_requested)
            card.explore.connect(self.explore_requested)
            self._layout.addWidget(card)
            self._cards.append(card)

        self._container.update()

    def _on_card_clicked(self, template: Template):
        for card in self._cards:
            card.set_selected(card.template is template)
        self.template_selected.emit(template)


# ── Panel de detalle (derecha) ────────────────────────────────────────────────

class DetailPanel(QtWidgets.QWidget):
    merge_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.template: Optional[Template] = None
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Preview: imagen o placeholder con boton de video
        self.preview_label = QtWidgets.QLabel("Selecciona un template")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedHeight(260)
        self.preview_label.setStyleSheet(
            "background:#1a1a1a; color:#555; border-radius:8px; font-size:13px;"
        )
        layout.addWidget(self.preview_label)

        # Boton para abrir video externo (visible solo cuando hay video)
        self.btn_video = QtWidgets.QPushButton("▶   Reproducir video")
        self.btn_video.setFixedHeight(34)
        self.btn_video.setVisible(False)
        self.btn_video.setStyleSheet("""
            QPushButton { background:#374151; color:#ddd; border-radius:6px; font-size:12px; }
            QPushButton:hover { background:#4b5563; }
        """)
        self.btn_video.clicked.connect(self._open_video)
        layout.addWidget(self.btn_video)

        # Info
        info = QtWidgets.QGroupBox("Información")
        info.setStyleSheet("""
            QGroupBox { color:#aaa; border:1px solid #374151; border-radius:6px;
                        margin-top:8px; padding:8px; }
            QGroupBox::title { subcontrol-origin:margin; left:10px; }
        """)
        form = QtWidgets.QFormLayout()
        form.setSpacing(6)

        self.lbl_name    = QtWidgets.QLabel("-")
        self.lbl_file    = QtWidgets.QLabel("-")
        self.lbl_preview = QtWidgets.QLabel("-")
        for lb in (self.lbl_name, self.lbl_file, self.lbl_preview):
            lb.setStyleSheet("color:#ccc;")
            lb.setWordWrap(True)

        def key(t):
            lb = QtWidgets.QLabel(t)
            lb.setStyleSheet("color:#6b7280;")
            return lb

        form.addRow(key("Nombre:"),  self.lbl_name)
        form.addRow(key("Archivo:"), self.lbl_file)
        form.addRow(key("Preview:"), self.lbl_preview)
        info.setLayout(form)
        layout.addWidget(info)

        layout.addStretch()

        self.btn_merge = QtWidgets.QPushButton("Merge con escena abierta")
        self.btn_merge.setFixedHeight(42)
        self.btn_merge.setEnabled(False)
        self.btn_merge.setStyleSheet("""
            QPushButton { background:#2563eb; color:white; font-weight:bold;
                          font-size:13px; border-radius:6px; }
            QPushButton:hover    { background:#1d4ed8; }
            QPushButton:pressed  { background:#1e40af; }
            QPushButton:disabled { background:#374151; color:#6b7280; }
        """)
        self.btn_merge.clicked.connect(lambda: self.merge_requested.emit(self.template))
        layout.addWidget(self.btn_merge)

    def _make_placeholder(self, template: Template, w: int, h: int) -> QtGui.QPixmap:
        """Genera pixmap de color con iniciales, igual que la tarjeta"""
        color    = _placeholder_color(template.name)
        initials = _initials(template.name)

        pix = QtGui.QPixmap(w, h)
        pix.fill(QtGui.QColor(color))

        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        if template.is_video():
            f = QtGui.QFont("Arial", 52)
            painter.setFont(f)
            painter.setPen(QtGui.QColor(255, 255, 255, 80))
            painter.drawText(pix.rect(), Qt.AlignCenter, "▶")

        f2 = QtGui.QFont("Arial", 40, QtGui.QFont.Bold)
        painter.setFont(f2)
        painter.setPen(QtGui.QColor(255, 255, 255, 200))
        painter.drawText(pix.rect(), Qt.AlignCenter, initials)
        painter.end()

        # Bordes redondeados
        rounded = QtGui.QPixmap(pix.size())
        rounded.fill(Qt.transparent)
        p2 = QtGui.QPainter(rounded)
        p2.setRenderHint(QtGui.QPainter.Antialiasing)
        path = QtGui.QPainterPath()
        path.addRoundedRect(0, 0, w, h, 8, 8)
        p2.setClipPath(path)
        p2.drawPixmap(0, 0, pix)
        p2.end()
        return rounded

    def load(self, template: Template):
        self.template = template
        pw = self.preview_label.width() or 340
        ph = self.preview_label.height() or 260

        self.lbl_name.setText(template.name)
        self.lbl_file.setText(template.hip_file.name if template.hip_file else "-")

        # Info de preview en el panel de info
        preview_parts = []
        if template.has_thumbnail():
            preview_parts.append(f"Thumb: {template.thumbnail_file.name}")
        if template.has_video():
            preview_parts.append(f"Video: {template.video_file.name}")
        self.lbl_preview.setText("\n".join(preview_parts) if preview_parts else "Sin preview")

        self.btn_merge.setEnabled(True)

        # ── Thumbnail en el panel ──────────────────────────────────────────────
        if template.has_thumbnail():
            pix = QtGui.QPixmap(str(template.thumbnail_file))
            if not pix.isNull():
                scaled = pix.scaled(pw, ph, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview_label.setPixmap(scaled)
                self.preview_label.setStyleSheet("background:#1a1a1a; border-radius:8px;")
            else:
                self.preview_label.setPixmap(self._make_placeholder(template, pw, ph))
                self.preview_label.setStyleSheet("border-radius:8px;")
        else:
            # Sin thumbnail: placeholder con iniciales (+ icono ▶ si tiene video)
            self.preview_label.setPixmap(self._make_placeholder(template, pw, ph))
            self.preview_label.setStyleSheet("border-radius:8px;")

        # ── Botón de video (independiente del thumbnail) ───────────────────────
        self.btn_video.setVisible(template.has_video())

    def _open_video(self):
        if self.template and self.template.video_file:
            os.startfile(str(self.template.video_file))

    def clear(self):
        self.template = None
        self.preview_label.clear()
        self.preview_label.setText("Selecciona un template")
        self.preview_label.setStyleSheet(
            "background:#1a1a1a; color:#555; border-radius:8px; font-size:13px;"
        )
        self.btn_video.setVisible(False)
        for lb in (self.lbl_name, self.lbl_file, self.lbl_preview):
            lb.setText("-")
        self.btn_merge.setEnabled(False)


# ── Ventana principal ─────────────────────────────────────────────────────────

def get_houdini_main_window():
    for w in QtWidgets.QApplication.topLevelWidgets():
        if w.objectName() == "MainWindow":
            return w
    return QtWidgets.QApplication.activeWindow()


class FXTemplateManager(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FX Template Manager")
        self.resize(1050, 680)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.setStyleSheet("QDialog { background:#141414; }")

        self.config = load_config()
        self._loader: Optional[TemplateLoader] = None
        self._all_templates: List[Template] = []

        self._build_ui()
        self._load_templates()

    def _build_ui(self):
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ── Izquierda ─────────────────────────────────────────────────────────
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        self.path_display = QtWidgets.QLabel(self.config["template_path"])
        self.path_display.setStyleSheet("color:#9ca3af; font-size:11px;")
        self.path_display.setWordWrap(True)
        btn_path = QtWidgets.QPushButton("Cambiar")
        btn_path.setFixedWidth(70)
        btn_path.setStyleSheet("QPushButton{background:#374151;color:#ddd;border-radius:4px;padding:4px 8px;} QPushButton:hover{background:#4b5563;}")
        btn_path.clicked.connect(self._change_path)
        header.addWidget(self.path_display, 1)
        header.addWidget(btn_path)
        left.addLayout(header)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Buscar template...")
        self.search.setStyleSheet("""
            QLineEdit { background:#1e1e1e; color:#ddd; border:1px solid #374151;
                        border-radius:6px; padding:6px 10px; font-size:12px; }
            QLineEdit:focus { border-color:#2563eb; }
        """)
        self.search.textChanged.connect(self._filter)
        left.addWidget(self.search)

        self.grid = TemplateGrid()
        self.grid.template_selected.connect(self.detail_panel.load if hasattr(self, "detail_panel") else lambda t: None)
        self.grid.merge_requested.connect(self._do_merge)
        self.grid.explore_requested.connect(self._open_folder)
        left.addWidget(self.grid, 1)

        self.status_label = QtWidgets.QLabel("Cargando...")
        self.status_label.setStyleSheet("color:#6b7280; font-size:11px;")
        self.btn_refresh = QtWidgets.QPushButton("Actualizar")
        self.btn_refresh.setStyleSheet("QPushButton{background:#1e1e1e;color:#9ca3af;border:1px solid #374151;border-radius:4px;padding:4px 12px;} QPushButton:hover{background:#252525;}")
        self.btn_refresh.clicked.connect(self._load_templates)
        footer = QtWidgets.QHBoxLayout()
        footer.addWidget(self.status_label)
        footer.addStretch()
        footer.addWidget(self.btn_refresh)
        left.addLayout(footer)

        # ── Derecha ───────────────────────────────────────────────────────────
        self.detail_panel = DetailPanel()
        self.detail_panel.merge_requested.connect(self._do_merge)
        self.detail_panel.setFixedWidth(360)

        # Reconectar grid ahora que detail_panel existe
        self.grid.template_selected.connect(self.detail_panel.load)

        root.addLayout(left, 1)
        root.addWidget(self.detail_panel)

    def _load_templates(self):
        self.btn_refresh.setEnabled(False)
        self.status_label.setText("Cargando...")
        self._loader = TemplateLoader(self.config["template_path"])
        self._loader.done.connect(self._on_loaded)
        self._loader.start()

    def _on_loaded(self, templates: List[Template]):
        self._all_templates = templates
        self.grid.populate(templates)
        self.btn_refresh.setEnabled(True)
        self.status_label.setText(f"{len(templates)} templates")

    def _filter(self, text: str):
        filtered = [t for t in self._all_templates if text.lower() in t.name.lower()]
        self.grid.populate(filtered)
        self.status_label.setText(f"{len(filtered)} templates")

    def _change_path(self):
        new = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Selecciona carpeta de templates", self.config["template_path"]
        )
        if new:
            self.config["template_path"] = new
            save_config(self.config)
            self.path_display.setText(new)
            self._load_templates()

    def _do_merge(self, template: Template):
        if not template or not template.hip_file:
            return
        try:
            hou.hipFile.merge(str(template.hip_file))
            QtWidgets.QMessageBox.information(
                self, "Merge completado",
                f"'{template.name}' mergeado correctamente en la escena."
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error en merge", str(e))

    def _open_folder(self, template: Template):
        os.startfile(str(template.path))

    def closeEvent(self, event):
        global _window_instance
        _window_instance = None
        super().closeEvent(event)


# ── Punto de entrada ──────────────────────────────────────────────────────────

def _create_window():
    global _window_instance
    if _window_instance is not None:
        _window_instance.raise_()
        _window_instance.activateWindow()
        return
    win = FXTemplateManager(parent=get_houdini_main_window())
    win.show()
    _window_instance = win


def show():
    import hdefereval
    hdefereval.executeDeferred(_create_window)
