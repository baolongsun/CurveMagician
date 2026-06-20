import sys
import numpy as np
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QLineEdit, QFileDialog, QMessageBox,
    QGraphicsDropShadowEffect, QFrame, QSizePolicy, QSpacerItem,
    QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QColor, QPalette, QFont, QMouseEvent, QKeyEvent
import pyqtgraph as pg
from scipy.interpolate import splprep, splev
from scipy.ndimage import uniform_filter1d


# ═══════════════════════════════════════════════════════════════════
#  Gemini / Material You 风格配色
# ═══════════════════════════════════════════════════════════════════
class Theme:
    BG_WINDOW     = "#f6f8fc"
    BG_CARD       = "#ffffff"
    BG_CARD_HOVER = "#f4f6fa"
    BORDER        = "#e3e8f0"
    TEXT_PRIMARY  = "#1f2937"
    TEXT_SECOND   = "#6b7280"
    ACCENT        = "#4f46e5"      # 靛蓝主色
    ACCENT_LIGHT  = "#e0e7ff"
    ACCENT_HOVER  = "#4338ca"
    SUCCESS       = "#10b981"
    WARNING       = "#f59e0b"
    DANGER        = "#ef4444"
    SHADOW        = "#94a3b8"

    CURVES = [
        "#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6",
        "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
    ]


# ═══════════════════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════════════════
def make_demo_curves(n_pts=80):
    x = np.linspace(0, 3 * np.pi, n_pts)
    return np.column_stack([
        1.0  * np.sin(x),
        0.65 * np.sin(2.0 * x - 0.8),
        0.45 * np.sin(3.5 * x + 0.5),
    ])


def cubic_spline(x, y, n=300):
    tck, u = splprep([x, y], s=0, k=3)
    u_fine = np.linspace(0, 1, n)
    xf, yf = splev(u_fine, tck)
    return xf, yf


class Card(QFrame):
    """圆角卡片容器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(f"""
            #card {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 16px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(Theme.SHADOW))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)


class ModernButton(QPushButton):
    """圆角主按钮"""
    def __init__(self, text, color=Theme.ACCENT, hover=Theme.ACCENT_HOVER,
                 text_color="white", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(34)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {text_color};
                border: none;
                border-radius: 10px;
                padding: 6px 18px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:pressed {{ background-color: {color}; }}
        """)


class ToolButton(QPushButton):
    """工具栏小按钮"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(32)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
                padding: 4px 14px;
                font-weight: 500;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {Theme.BG_CARD_HOVER}; }}
        """)


class SectionTitle(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            color: {Theme.TEXT_PRIMARY};
            font-weight: 700;
            font-size: 13px;
            padding-bottom: 4px;
        """)


class StyledSlider(QWidget):
    """带数值标签的滑杆"""
    def __init__(self, name, min_val, max_val, default, decimals=0, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        top = QHBoxLayout()
        self.label = QLabel(name)
        self.label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 500;")
        self.value_label = QLabel(str(default))
        self.value_label.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 12px; font-weight: 700;")
        top.addWidget(self.label)
        top.addStretch()
        top.addWidget(self.value_label)
        layout.addLayout(top)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(1000)
        self.slider.setValue(int((default - min_val) / (max_val - min_val) * 1000))
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {Theme.BORDER};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {Theme.ACCENT};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                margin: -5px 0;
                background: {Theme.ACCENT};
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{ background: {Theme.ACCENT_HOVER}; }}
        """)
        layout.addWidget(self.slider)

        self.min_val = min_val
        self.max_val = max_val
        self.decimals = decimals
        self.slider.valueChanged.connect(self._update_label)
        self._callbacks = []

    def value(self):
        t = self.slider.value() / 1000.0
        v = self.min_val + t * (self.max_val - self.min_val)
        return round(v, self.decimals)

    def _update_label(self):
        v = self.value()
        self.value_label.setText(f"{v:.{self.decimals}f}")
        for cb in self._callbacks:
            cb(v)

    def on_changed(self, callback):
        self._callbacks.append(callback)

    def set_value(self, v):
        t = (v - self.min_val) / (self.max_val - self.min_val)
        self.slider.setValue(int(t * 1000))


class CurveListItem(QFrame):
    """左侧曲线卡片项"""
    clicked = None  # 通过构造函数设置

    def __init__(self, name, color, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 10px;
            }}
            QFrame:hover {{ background-color: {Theme.BG_CARD_HOVER}; }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        layout.addWidget(self.dot)

        self.name = QLabel(name)
        self.name.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 500;")
        layout.addWidget(self.name)
        layout.addStretch()

    def set_active(self, active):
        self.active = active
        if active:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.ACCENT_LIGHT};
                    border: 1px solid {Theme.ACCENT};
                    border-radius: 10px;
                }}
            """)
            self.name.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 12px; font-weight: 700;")
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {Theme.BG_CARD};
                    border: 1px solid {Theme.BORDER};
                    border-radius: 10px;
                }}
                QFrame:hover {{ background-color: {Theme.BG_CARD_HOVER}; }}
            """)
            self.name.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 500;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.clicked:
            self.clicked(self.index)


# ═══════════════════════════════════════════════════════════════════
#  主窗口
# ═══════════════════════════════════════════════════════════════════
class CurveMagicianQt(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CurveMagician")
        self.setMinimumSize(1280, 800)
        self.setStyleSheet(f"background-color: {Theme.BG_WINDOW};")

        # 数据
        self.curves = []          # dict 列表
        self.active_curve_idx = None
        self.current_label = "All"
        self.undo_stack = []
        self.neighbor_num = 0
        self.epsilon = 30
        self.slider_base_state = None

        # 交互状态
        self._drag_curve = None
        self._drag_point = None
        self._selecting = False
        self._select_start = None
        self._selected_points = []
        self._batch_moving = False
        self._batch_origin = None
        self._selection_x_bounds = None
        self._noise_seed = 0

        self._build_ui()
        self._load_demo()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(18)

        # ── 左侧：曲线列表 ──
        self.left_card = Card()
        left_layout = QVBoxLayout(self.left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        title = SectionTitle("Curves")
        left_layout.addWidget(title)

        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setStyleSheet("border: none; background: transparent;")
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch()
        self.list_scroll.setWidget(self.list_container)
        left_layout.addWidget(self.list_scroll)

        main.addWidget(self.left_card, 1)

        # ── 中间：绘图区 ──
        self.center_card = Card()
        center_layout = QVBoxLayout(self.center_card)
        center_layout.setContentsMargins(12, 12, 12, 12)

        # 自定义工具栏
        toolbar = QHBoxLayout()
        self.btn_open = ToolButton("Open")
        self.btn_save = ToolButton("Save")
        self.btn_undo = ToolButton("Undo")
        self.btn_fit  = ToolButton("Fit")
        self.neighbor_input = QLineEdit("0")
        self.neighbor_input.setFixedWidth(60)
        self.neighbor_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.neighbor_input.setStyleSheet(f"""
            QLineEdit {{
                background: {Theme.BG_WINDOW};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
                padding: 5px;
                color: {Theme.TEXT_PRIMARY};
                font-weight: 600;
            }}
        """)
        self.neighbor_input.textChanged.connect(self._on_neighbor_changed)

        self.btn_zoom = ToolButton("Zoom")
        self.btn_zoom.setCheckable(True)
        self.btn_zoom.setChecked(True)

        toolbar.addWidget(self.btn_open)
        toolbar.addWidget(self.btn_save)
        toolbar.addWidget(self.btn_undo)
        toolbar.addWidget(self.btn_fit)
        toolbar.addWidget(self.btn_zoom)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("+/-N"))
        toolbar.addWidget(self.neighbor_input)

        self.btn_zoom.toggled.connect(self._toggle_zoom)
        center_layout.addLayout(toolbar)

        # PyQtGraph 绘图
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMenuEnabled(False)
        self.plot_widget.setBackground(Theme.BG_CARD)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self.plot_widget.getAxis('bottom').setPen(pg.mkPen(color=Theme.BORDER, width=1))
        self.plot_widget.getAxis('left').setPen(pg.mkPen(color=Theme.BORDER, width=1))
        self.plot_widget.getAxis('bottom').setTextPen(pg.mkPen(color=Theme.TEXT_SECOND))
        self.plot_widget.getAxis('left').setTextPen(pg.mkPen(color=Theme.TEXT_SECOND))
        self.plot_widget.setLabel('bottom', 'index')
        self.plot_widget.setLabel('left', 'value')
        # 禁用视图拖拽平移，保留滚轮缩放；鼠标拖动仅用于框选/拖拽控制点
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.scene().sigMouseClicked.connect(self._on_plot_click)

        # 通过事件过滤器获取按下/移动/释放
        self.plot_widget.viewport().installEventFilter(self)

        # 框选矩形（初始隐藏）
        self._select_rect = None

        # 拖拽提示（空数据时显示）
        self._drop_hint = pg.TextItem(
            text="拖放 CSV / Excel / NPY 文件到此处\n或点击 Open 按钮选择文件",
            color=QColor(Theme.TEXT_SECOND), anchor=(0.5, 0.5), fill=QColor(Theme.BG_CARD)
        )
        self._drop_hint.setFont(QFont("Inter", 12))
        self.plot_widget.addItem(self._drop_hint)
        self._drop_hint.setVisible(False)

        # 文件拖拽支持
        self.setAcceptDrops(True)

        center_layout.addWidget(self.plot_widget, 1)
        main.addWidget(self.center_card, 4)

        # ── 右侧：调节面板 ──
        self.right_card = Card()
        right_layout = QVBoxLayout(self.right_card)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(18)

        adj_title = SectionTitle("Adjust")
        right_layout.addWidget(adj_title)

        self.slider_scale  = StyledSlider("Scale",  0.0, 2.0, 1.0,  decimals=2)
        self.slider_smooth = StyledSlider("Smooth", 1,   15,  1,    decimals=0)
        self.slider_noise  = StyledSlider("Noise",  0.0, 5.0, 0.0,  decimals=1)
        self.slider_scale.on_changed(self._on_slider_changed)
        self.slider_smooth.on_changed(self._on_slider_changed)
        self.slider_noise.on_changed(self._on_slider_changed)
        right_layout.addWidget(self.slider_scale)
        right_layout.addWidget(self.slider_smooth)
        right_layout.addWidget(self.slider_noise)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {Theme.BORDER};")
        right_layout.addWidget(sep)

        resample_layout = QVBoxLayout()
        resample_layout.setSpacing(8)
        resample_title = SectionTitle("Resample")
        resample_layout.addWidget(resample_title)
        resample_input_layout = QHBoxLayout()
        self.resample_input = QLineEdit()
        self.resample_input.setPlaceholderText("points")
        self.resample_input.setStyleSheet(f"""
            QLineEdit {{
                background: {Theme.BG_WINDOW};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
                padding: 6px 10px;
                color: {Theme.TEXT_PRIMARY};
                font-weight: 500;
            }}
        """)
        resample_input_layout.addWidget(self.resample_input)
        self.btn_resample = ModernButton("Apply")
        self.btn_resample.setFixedWidth(70)
        resample_input_layout.addWidget(self.btn_resample)
        resample_layout.addLayout(resample_input_layout)
        right_layout.addLayout(resample_layout)

        right_layout.addStretch()

        # 状态信息
        self.info_num = QLabel("")
        self.info_num.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 700;")
        self.info_tag = QLabel("")
        self.info_tag.setStyleSheet(f"color: {Theme.TEXT_SECOND}; font-size: 12px;")
        right_layout.addWidget(self.info_num)
        right_layout.addWidget(self.info_tag)

        main.addWidget(self.right_card, 1)

        # 事件连接
        self.btn_open.clicked.connect(self._open_file)
        self.btn_save.clicked.connect(self._save_file)
        self.btn_undo.clicked.connect(self._undo)
        self.btn_fit.clicked.connect(self._auto_range)
        self.btn_resample.clicked.connect(self._do_resample)

    # ═══════════════════════════════════════════════════════════════
    #  数据管理
    # ═══════════════════════════════════════════════════════════════
    def _add_curve(self, x, y, color, name):
        pen = pg.mkPen(color=color, width=2.5)
        ctrl_pen = pg.mkPen(color=color, width=1)
        ctrl_brush = pg.mkBrush(color)
        spline = self.plot_widget.plot(x, y, pen=pen, name=name)
        scatter = pg.ScatterPlotItem(
            x=x, y=y, size=7, pen=ctrl_pen, brush=ctrl_brush,
            hoverable=True, hoverSize=10
        )
        self.plot_widget.addItem(scatter)
        curve = {
            'x': np.array(x, dtype=float),
            'y': np.array(y, dtype=float),
            'color': color,
            'spline': spline,
            'scatter': scatter,
            'name': name,
        }
        self.curves.append(curve)
        self._update_spline(len(self.curves) - 1)

    def _refresh_curve_styles(self):
        """根据 active_curve_idx 调整各曲线透明度/粗细"""
        for idx, c in enumerate(self.curves):
            active = (self.active_curve_idx is None or idx == self.active_curve_idx)
            if active:
                lw = 2.5 if self.active_curve_idx is None else 3.5
                alpha = 180 if self.active_curve_idx is None else 255
                size = 7 if self.active_curve_idx is None else 9
            else:
                lw = 1.0
                alpha = 50
                size = 4
            color = QColor(c['color'])
            color.setAlpha(alpha)
            c['spline'].setPen(pg.mkPen(color=color, width=lw))
            c['scatter'].setBrush(pg.mkBrush(color))
            c['scatter'].setSize(size)

    def _update_spline(self, idx):
        c = self.curves[idx]
        xf, yf = cubic_spline(c['x'], c['y'])
        c['spline'].setData(xf, yf)
        c['scatter'].setData(x=c['x'], y=c['y'])

    def _load_demo(self):
        data = make_demo_curves()
        for i in range(data.shape[1]):
            self._add_curve(
                np.arange(data.shape[0]),
                data[:, i],
                Theme.CURVES[i % len(Theme.CURVES)],
                f"Curve {i}"
            )
        self._save_state()
        self._reset_sliders()
        self._rebuild_list()
        self._refresh_curve_styles()
        self._auto_range()
        self._update_info()

    def _save_state(self):
        state = [{'x': c['x'].copy(), 'y': c['y'].copy()} for c in self.curves]
        self.undo_stack.append(state)

    def _undo(self):
        if len(self.undo_stack) <= 1:
            return
        self.undo_stack.pop()
        prev = self.undo_stack[-1]
        for i, c in enumerate(self.curves):
            if i < len(prev):
                c['x'] = prev[i]['x'].copy()
                c['y'] = prev[i]['y'].copy()
                self._update_spline(i)
        self._reset_sliders()
        self._refresh_curve_styles()
        self._update_info()

    # ═══════════════════════════════════════════════════════════════
    #  UI 更新
    # ═══════════════════════════════════════════════════════════════
    def _rebuild_list(self):
        # 清除旧项（保留 stretch）
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        items = [("All", None, -1)]
        for i, c in enumerate(self.curves):
            items.append((c['name'], c['color'], i))

        for name, color, idx in items:
            item = CurveListItem(name, color or Theme.ACCENT, idx)
            item.clicked = self._on_curve_selected
            if (idx == -1 and self.current_label == "All") or \
               (idx == self.active_curve_idx):
                item.set_active(True)
            self.list_layout.insertWidget(self.list_layout.count() - 1, item)

    def _on_curve_selected(self, idx):
        if idx == -1:
            self.current_label = "All"
            self.active_curve_idx = None
        else:
            self.current_label = self.curves[idx]['name']
            self.active_curve_idx = idx
        self._rebuild_list()
        self._update_info()
        self._refresh_curve_styles()

    def _next_curve(self, step=1):
        if not self.curves:
            return
        n = len(self.curves) + 1  # All + curves
        current = 0 if self.active_curve_idx is None else self.active_curve_idx + 1
        nxt = (current + step) % n
        self._on_curve_selected(nxt - 1)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            if not path:
                continue
            try:
                self._detect_format(path)
                self._open_path(path)
                return
            except ValueError:
                continue
        if urls:
            QMessageBox.warning(self, "不支持的文件", "仅支持 .csv, .xlsx, .npy")

    def _detect_format(self, path):
        ext = Path(path).suffix.lower()
        if ext == '.csv':
            return 'csv'
        elif ext in ('.xlsx', '.xls'):
            return 'excel'
        elif ext == '.npy':
            return 'npy'
        else:
            raise ValueError(f"不支持格式: {ext}")

    def _on_neighbor_changed(self, text):
        try:
            self.neighbor_num = max(0, int(text))
        except ValueError:
            self.neighbor_num = 0

    def _reset_sliders(self):
        self.slider_base_state = [{'y': c['y'].copy()} for c in self.curves]
        self.slider_scale.set_value(1.0)
        self.slider_smooth.set_value(1)
        self.slider_noise.set_value(0.0)

    def _update_info(self):
        if not self.curves:
            self.info_num.setText("")
            self.info_tag.setText("")
            self._drop_hint.setVisible(True)
            return
        self._drop_hint.setVisible(False)

        val = ""
        if self._selected_points:
            by_curve = {}
            for c, p in self._selected_points:
                by_curve.setdefault(c, []).append(p)
            n = len(self._selected_points)
            detail = ", ".join(f"C{c}: {len(p_)}p" for c, p_ in sorted(by_curve.items()))
            self.info_num.setText(f"{n} pts")
            self.info_tag.setText(f"Box-sel ({detail})")
            counts = {len(p_) for p_ in by_curve.values()}
            val = str(counts.pop()) if len(counts) == 1 else "---"
        elif self.active_curve_idx is not None:
            n = len(self.curves[self.active_curve_idx]['y'])
            self.info_num.setText(f"{n} pts")
            self.info_tag.setText(self.current_label)
            val = str(n)
        else:
            total = sum(len(c['y']) for c in self.curves)
            nc = len(self.curves)
            ppc = len(self.curves[0]['y'])
            self.info_num.setText(f"{total} pts")
            self.info_tag.setText(f"All ({nc} curves × {ppc})")
            counts = {len(c['y']) for c in self.curves}
            val = str(counts.pop()) if len(counts) == 1 else "---"

        # 同步重采样输入框（避免覆盖用户输入）
        if val != getattr(self, '_last_npts_val', None):
            self.resample_input.setText(val)
            self._last_npts_val = val

    # ═══════════════════════════════════════════════════════════════
    #  滑杆处理
    # ═══════════════════════════════════════════════════════════════
    def _on_slider_changed(self, _=None):
        if self.slider_base_state is None or not self.curves:
            return
        scale = self.slider_scale.value()
        smooth = int(self.slider_smooth.value())
        noise = self.slider_noise.value()

        targets = self._get_target_points_map()
        for c_idx, p_idxs in targets.items():
            orig = self.slider_base_state[c_idx]['y'].copy()
            p_idxs = np.array(p_idxs)
            if len(p_idxs) == 0:
                continue
            if scale != 1.0:
                orig[p_idxs] *= scale
            if smooth > 1:
                smoothed = uniform_filter1d(orig.astype(float), size=smooth)
                orig[p_idxs] = smoothed[p_idxs]
            if noise > 0:
                std = np.std(orig[p_idxs]) if len(p_idxs) > 1 else np.mean(np.abs(orig[p_idxs]))
                if std == 0:
                    std = 1.0
                rng = np.random.RandomState(self._noise_seed or 0)
                orig[p_idxs] += rng.normal(0, std * 0.05 * noise, size=len(p_idxs))
            self.curves[c_idx]['y'] = orig
            self._update_spline(c_idx)
        self._update_info()

    def _get_target_points_map(self):
        targets = {}
        if self._selected_points:
            for c, p in self._selected_points:
                if self.active_curve_idx is None or c == self.active_curve_idx:
                    targets.setdefault(c, []).append(p)
        elif self.active_curve_idx is not None:
            targets[self.active_curve_idx] = list(range(len(self.curves[self.active_curve_idx]['y'])))
        else:
            for c_idx, c in enumerate(self.curves):
                targets[c_idx] = list(range(len(c['y'])))
        return targets

    # ═══════════════════════════════════════════════════════════════
    #  鼠标交互
    # ═══════════════════════════════════════════════════════════════
    def _on_plot_click(self, event):
        # 双击：切换到对应曲线
        if event.double():
            pos = event.scenePos()
            mp = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            c_idx, p_idx = self._get_closest_point(mp.x(), mp.y())
            if c_idx is not None:
                self._on_curve_selected(c_idx)
            return

        # 右键清除选择
        if event.button() == Qt.MouseButton.RightButton:
            self._clear_selection()


    def _create_select_rect(self, x, y):
        if self._select_rect is not None:
            self.plot_widget.removeItem(self._select_rect)
        pen = pg.mkPen(color=Theme.ACCENT, width=1.5, style=Qt.PenStyle.DashLine)
        brush = pg.mkBrush(color=QColor(Theme.ACCENT_LIGHT))
        self._select_rect = pg.ROI([min(self._select_start[0], x), min(self._select_start[1], y)],
                                   [abs(x - self._select_start[0]), abs(y - self._select_start[1])],
                                   pen=pen, brush=brush, movable=False, rotatable=False,
                                   resizable=False, removable=False)
        self.plot_widget.addItem(self._select_rect)

    def _update_select_rect(self, x, y):
        if self._select_rect is None:
            return
        x0, y0 = self._select_start
        self._select_rect.setPos(min(x0, x), min(y0, y))
        self._select_rect.setSize(abs(x - x0), abs(y - y0))

    def _remove_select_rect(self):
        if self._select_rect is not None:
            self.plot_widget.removeItem(self._select_rect)
            self._select_rect = None

    def eventFilter(self, obj, event):
        if obj is self.plot_widget.viewport():
            etype = event.type()
            if etype == QMouseEvent.Type.MouseButtonPress:
                self._on_mouse_press(event)
                return False
            elif etype == QMouseEvent.Type.MouseMove:
                self._on_mouse_move(event)
                return False
            elif etype == QMouseEvent.Type.MouseButtonRelease:
                self._on_mouse_release(event)
                return False
        return super().eventFilter(obj, event)

    def _event_pos_to_view(self, event):
        """把 QWidget 鼠标事件坐标转换为 ViewBox 的数据坐标"""
        widget_pos = event.position()
        scene_pos = self.plot_widget.mapToScene(widget_pos.toPoint())
        view_pos = self.plot_widget.plotItem.vb.mapSceneToView(scene_pos)
        return view_pos.x(), view_pos.y()

    def _on_mouse_press(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x, y = self._event_pos_to_view(event)

        c_idx, p_idx = self._get_closest_point(x, y)
        if c_idx is not None:
            if self._selected_points:
                if self.active_curve_idx is None or c_idx == self.active_curve_idx:
                    point_in_selection = any((c_idx == sc and p_idx == sp)
                                             for sc, sp in self._selected_points)
                    if point_in_selection:
                        self._batch_moving = True
                        self._batch_origin = (x, y)
                        return
            self._drag_curve = c_idx
            self._drag_point = p_idx
        else:
            self._selecting = True
            self._select_start = (x, y)
            self._selected_points.clear()
            self._selection_x_bounds = None
            self._create_select_rect(x, y)
            self._update_info()

    def _on_mouse_move(self, event):
        if not (self._drag_curve is not None or self._batch_moving or self._selecting):
            return
        x, y = self._event_pos_to_view(event)

        if self._drag_curve is not None:
            c = self.curves[self._drag_curve]
            center = self._drag_point
            linked = self._get_linked_indices(len(c['y']), center)
            dy = y - c['y'][center]
            for pid in linked:
                c['y'][pid] += dy
            self._update_spline(self._drag_curve)
            self._expand_axes_if_needed()
            self._update_info()
            return

        if self._batch_moving and self._batch_origin is not None:
            dy = y - self._batch_origin[1]
            affected = set()
            for c_idx, p_idx in self._selected_points:
                if self.active_curve_idx is None or c_idx == self.active_curve_idx:
                    self.curves[c_idx]['y'][p_idx] += dy
                    affected.add(c_idx)
            for c_idx in affected:
                self._update_spline(c_idx)
            self._batch_origin = (self._batch_origin[0], y)
            self._expand_axes_if_needed()
            self._update_info()
            return

        if self._selecting and self._select_start is not None:
            self._selected_points = self._select_points_in_rect(
                self._select_start[0], self._select_start[1], x, y)
            self._selection_x_bounds = (
                min(self._select_start[0], x), max(self._select_start[0], x))
            self._update_select_rect(x, y)
            self._update_info()

    def _on_mouse_release(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._drag_curve is not None:
            self._drag_curve = None
            self._drag_point = None
            self._save_state()
            self._reset_sliders()

        if self._batch_moving:
            self._batch_moving = False
            self._batch_origin = None
            self._save_state()
            self._reset_sliders()

        if self._selecting:
            self._selecting = False
            self._remove_select_rect()
            if self._selected_points:
                self._save_state()
                self._reset_sliders()

    def _get_closest_point(self, mx, my):
        if not self.curves:
            return None, None
        candidates = ([self.active_curve_idx] if self.active_curve_idx is not None
                      else range(len(self.curves)))
        best = (None, None, float('inf'))
        for c_idx in candidates:
            c = self.curves[c_idx]
            pts = np.c_[c['x'], c['y']]
            # 用视图坐标计算像素距离
            view = self.plot_widget.plotItem.vb
            screen = [view.mapViewToScene(pg.Point(px, py)) for px, py in pts]
            mouse = self.plot_widget.plotItem.vb.mapViewToScene(pg.Point(mx, my))
            dists = [((p.x() - mouse.x()) ** 2 + (p.y() - mouse.y()) ** 2) ** 0.5 for p in screen]
            p_idx = int(np.argmin(dists))
            if dists[p_idx] < best[2]:
                best = (c_idx, p_idx, dists[p_idx])
        if best[2] < self.epsilon:
            return best[0], best[1]
        return None, None

    def _get_linked_indices(self, total, center):
        return list(range(max(0, center - self.neighbor_num),
                          min(total - 1, center + self.neighbor_num) + 1))

    def _select_points_in_rect(self, x0, y0, x1, y1):
        selected = []
        xmin, xmax = min(x0, x1), max(x0, x1)
        ymin, ymax = min(y0, y1), max(y0, y1)
        check = ([self.active_curve_idx] if self.active_curve_idx is not None
                 else range(len(self.curves)))
        for c_idx in check:
            c = self.curves[c_idx]
            for p_idx, (px, py) in enumerate(zip(c['x'], c['y'])):
                if xmin <= px <= xmax and ymin <= py <= ymax:
                    selected.append((c_idx, p_idx))
        return selected

    def _clear_selection(self):
        self._selected_points.clear()
        self._selection_x_bounds = None
        self._batch_moving = False
        self._batch_origin = None
        self._update_info()

    # ═══════════════════════════════════════════════════════════════
    #  重采样
    # ═══════════════════════════════════════════════════════════════
    def _do_resample(self):
        text = self.resample_input.text()
        try:
            n_new = int(text)
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入整数")
            return
        if n_new < 4:
            QMessageBox.warning(self, "约束错误", "至少需要 4 个点")
            return

        targets = {}
        if self._selected_points:
            for c, p in self._selected_points:
                if self.active_curve_idx is None or c == self.active_curve_idx:
                    targets.setdefault(c, []).append(p)
        else:
            t = [self.active_curve_idx] if self.active_curve_idx is not None else range(len(self.curves))
            for c in t:
                targets[c] = list(range(len(self.curves[c]['y'])))

        counts = {len(v) for v in targets.values()}
        if len(counts) > 1:
            QMessageBox.critical(self, "重采样失败", "选中各曲线点数不一致")
            return

        modified = False
        for c_idx, p_idxs in targets.items():
            curve = self.curves[c_idx]
            orig = curve['y']
            i_min, i_max = min(p_idxs), max(p_idxs)
            n_old = i_max - i_min + 1
            if n_old == n_new and self._selected_points:
                continue
            pad = 2
            ext_min = max(0, i_min - pad)
            ext_max = min(len(orig) - 1, i_max + pad)
            seg_y = orig[ext_min:ext_max + 1]
            seg_x = np.arange(len(seg_y), dtype=float)
            k = 3 if len(seg_y) > 3 else max(1, len(seg_y) - 1)
            tck, _ = splprep([seg_x, seg_y], s=0, k=k)
            left_pad = i_min - ext_min
            right_pad = ext_max - i_max
            total_new = left_pad + n_new + right_pad
            u_new = np.linspace(0, 1, total_new)
            _, y_res = splev(u_new, tck)
            core = y_res[left_pad:total_new - right_pad]
            new_y = np.concatenate([orig[:i_min], core, orig[i_max + 1:]])
            curve['y'] = new_y
            curve['x'] = np.arange(len(new_y), dtype=float)
            self._update_spline(c_idx)
            modified = True

        if modified:
            self._save_state()
            self._reset_sliders()
            self._clear_selection()
            self._update_info()

    # ═══════════════════════════════════════════════════════════════
    #  文件 I/O
    # ═══════════════════════════════════════════════════════════════
    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开曲线文件", "",
            "CSV (*.csv);;NumPy (*.npy);;Excel (*.xlsx *.xls)")
        if not path:
            return
        self._open_path(path)

    def _open_path(self, path):
        try:
            data = self._load_data(path)
        except Exception as e:
            QMessageBox.critical(self, "加载错误", str(e))
            return
        self._clear_all()
        n_pts = data.shape[0]
        for i in range(data.shape[1]):
            self._add_curve(
                np.arange(n_pts), data[:, i],
                Theme.CURVES[i % len(Theme.CURVES)],
                f"Curve {i}"
            )
        self._save_state()
        self._reset_sliders()
        self._rebuild_list()
        self._refresh_curve_styles()
        self._auto_range()
        self._update_info()
        self.setWindowTitle(f"CurveMagician - {Path(path).name}")

    def _load_data(self, path):
        ext = Path(path).suffix.lower()
        if ext == '.csv':
            data = np.loadtxt(path, delimiter=',', dtype=float, ndmin=2)
        elif ext == '.npy':
            data = np.load(path, allow_pickle=True)
        elif ext in ('.xlsx', '.xls'):
            try:
                from openpyxl import load_workbook
            except ImportError:
                raise ImportError("需要 openpyxl: pip install openpyxl")
            wb = load_workbook(path, data_only=True)
            ws = wb.active
            rows = [[cell.value or 0 for cell in row] for row in ws.iter_rows()]
            wb.close()
            data = np.array(rows, dtype=float)
        else:
            raise ValueError(f"不支持格式: {ext}")
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        if data.shape[0] < data.shape[1]:
            data = data.T
        if data.shape[0] < 4:
            raise ValueError("每条曲线至少 4 个点")
        return data

    def _save_file(self):
        if not self.curves:
            QMessageBox.warning(self, "保存", "没有曲线数据")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存曲线", "curves.npy",
            "NumPy (*.npy);;CSV (*.csv);;Excel (*.xlsx)")
        if not path:
            return
        data = np.array([c['y'] for c in self.curves]).T
        ext = Path(path).suffix.lower()
        try:
            if ext == '.csv':
                np.savetxt(path, data, delimiter=',', fmt='%.8g')
            elif ext == '.npy':
                np.save(path, data)
            elif ext == '.xlsx':
                try:
                    from openpyxl import Workbook
                except ImportError:
                    raise ImportError("需要 openpyxl: pip install openpyxl")
                wb = Workbook()
                ws = wb.active
                for row in data:
                    ws.append(row.tolist())
                wb.save(path)
            self.setWindowTitle(f"CurveMagician - {Path(path).name}")
        except Exception as e:
            QMessageBox.critical(self, "保存错误", str(e))

    def _clear_all(self):
        for c in self.curves:
            self.plot_widget.removeItem(c['spline'])
            self.plot_widget.removeItem(c['scatter'])
        self.curves.clear()
        self.undo_stack.clear()
        self._clear_selection()
        self.active_curve_idx = None
        self.current_label = "All"

    def _auto_range(self):
        if not self.curves:
            return
        all_x = np.concatenate([c['x'] for c in self.curves])
        all_y = np.concatenate([c['y'] for c in self.curves])
        xr = all_x.max() - all_x.min() or 1.0
        yr = all_y.max() - all_y.min() or 1.0
        self.plot_widget.setXRange(all_x.min() - xr * 0.08, all_x.max() + xr * 0.08, padding=0)
        self.plot_widget.setYRange(all_y.min() - yr * 0.08, all_y.max() + yr * 0.08, padding=0)

    def _toggle_zoom(self, enabled):
        self.plot_widget.setMouseEnabled(x=enabled, y=enabled)

    def _expand_axes_if_needed(self):
        if not self.curves:
            return
        all_y = np.concatenate([c['y'] for c in self.curves])
        if len(all_y) == 0:
            return
        y_min, y_max = np.min(all_y), np.max(all_y)
        cur_lo, cur_hi = self.plot_widget.getViewBox().viewRange()[1]
        y_range = y_max - y_min or 1.0
        margin = 0.10
        changed = False
        new_lo, new_hi = cur_lo, cur_hi
        if y_min < cur_lo:
            new_lo = y_min - y_range * margin
            changed = True
        if y_max > cur_hi:
            new_hi = y_max + y_range * margin
            changed = True
        if changed:
            self.plot_widget.setYRange(new_lo, new_hi, padding=0)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        mod = event.modifiers()
        ctrl = mod & Qt.KeyboardModifier.ControlModifier

        if key == Qt.Key.Key_Delete:
            self._delete_selected()
        elif key == Qt.Key.Key_Z and ctrl:
            self._undo()
        elif key == Qt.Key.Key_O and ctrl:
            self._open_file()
        elif key == Qt.Key.Key_S and ctrl:
            self._save_file()
        elif key == Qt.Key.Key_Escape:
            self._clear_selection()
        elif key == Qt.Key.Key_A and not ctrl:
            self._on_curve_selected(-1)
        elif key == Qt.Key.Key_Tab:
            self._next_curve(1)
        elif key == Qt.Key.Key_Backtab:
            self._next_curve(-1)
        else:
            super().keyPressEvent(event)

    def _delete_selected(self):
        if not self._selected_points:
            return
        by_curve = {}
        for c, p in self._selected_points:
            by_curve.setdefault(c, []).append(p)
        for c_idx, p_idxs in by_curve.items():
            curve = self.curves[c_idx]
            keep = [i for i in range(len(curve['y'])) if i not in p_idxs]
            if len(keep) < 4:
                continue
            curve['y'] = curve['y'][keep]
            curve['x'] = np.arange(len(keep), dtype=float)
            self._update_spline(c_idx)
        self._save_state()
        self._clear_selection()
        self._update_info()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Inter", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)
    window = CurveMagicianQt()
    window.show()
    sys.exit(app.exec())
