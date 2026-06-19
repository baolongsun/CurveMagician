import matplotlib
matplotlib.use('TkAgg')

import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import splprep, splev
import os
from matplotlib.patches import Rectangle, Circle
import matplotlib.widgets as mwidgets
from matplotlib.widgets import Button, TextBox, Slider
from scipy.ndimage import uniform_filter1d
from tkinter import filedialog, messagebox

# 可选依赖：pandas 用于 Excel/CSV 读写
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("提示: 安装 pandas 可支持 CSV/Excel 格式 (pip install pandas openpyxl)")

# 可选依赖：tkinterdnd2 用于文件拖拽
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False
    print("提示: 安装 tkinterdnd2 可启用文件拖拽功能 (pip install tkinterdnd2)")

# ===================== 核心修复：精准、安全的 Matplotlib 补丁 =====================
def patch_matplotlib_widgets_safely():
    """
    精准修复 Matplotlib 组件基类的全局事件分发 Bug，增加防重复修改锁，彻底避免无限递归
    """
    base_class = mwidgets.AxesWidget
    
    # 检查是否已经修补过，防止重复执行
    if not getattr(base_class, '_is_patched_for_resize', False):
        orig_connect = base_class.connect_event
        
        def safe_connect(self, event, callback):
            def safe_callback(evt):
                if evt is None or not hasattr(evt, 'inaxes'):
                    return 
                return callback(evt)
            return orig_connect(self, event, safe_callback)
        
        base_class.connect_event = safe_connect
        base_class._is_patched_for_resize = True

# 启动补丁
patch_matplotlib_widgets_safely()


class HarmoniousCurvesEditor:
    def __init__(self, ax, fig, ax_n_input, ax_radio=None, color_list=None):
        self.fig = fig
        self.ax = ax
        self.canvas = ax.figure.canvas
        self.curves = []

        # 曲线激活锁定
        self.active_curve_idx = None
        self.current_label = "All"

        # 单点拖拽
        self._active_curve_idx = None
        self._active_point_idx = None

        # 增大容差像素，让鼠标更容易选中
        self._epsilon = 30

        self.neighbor_num = 0
        self.ax_n_input = ax_n_input

        # 框选 & 批量移动
        self._selecting = False
        self._select_rect = None
        self._select_start = None
        self._selected_points = []
        self._batch_moving = False
        self._batch_origin = None
        self._selection_x_bounds = None

        # Undo 栈 & 临时操作状态备份
        self.undo_stack = []
        self._in_continuous_drag = False
        self._slider_base_state = None
        self._is_sliding = False  # 标记当前是否正在拖动滑杆

        # 组件引用初始化
        self.radio_menu = None
        self.radio_labels = []
        self.slider_scale = None
        self.slider_smooth = None
        self.slider_noise = None

        # 文件 I/O 状态
        self.current_file_path = None      # 当前文件路径（用于保存时推断格式）
        self.color_list = color_list or [] # 15 色调色板
        self.ax_radio = ax_radio           # 右侧单选面板 axes

        # 拖拽提示 & 单选面板顶层元素引用
        self.drop_hint = None              # 空数据时的拖拽提示文字
        self._top_dots = None              # 面板顶层圆点 scatter
        self._radio_circles = []           # 面板 Circle patch 列表
        self._color_patches = []           # 面板色块 Rectangle 列表

        # 事件绑定
        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('key_press_event', self.on_key)
        self.canvas.mpl_connect('button_press_event', self.on_double_click)

    def set_radio_ref(self, radio_menu, labels):
        self.radio_menu = radio_menu
        self.radio_labels = labels

    def _is_toolbar_active(self):
        toolbar = self.fig.canvas.manager.toolbar
        if toolbar is not None:
            mode = toolbar.mode.lower()
            if 'zoom' in mode or 'pan' in mode:
                return True
        return False

    def on_double_click(self, event):
        if not hasattr(event, 'inaxes') or event.inaxes is None:
            return
        if event.button != 1 or not event.dblclick:
            return
        if event.inaxes != self.ax or self._is_toolbar_active():
            return
        c_idx, _ = self._get_closest_point(event)
        if c_idx is None:
            return
        target_label = f"Curve {c_idx}"
        if self.radio_menu and target_label in self.radio_labels:
            self.radio_menu.set_active(self.radio_labels.index(target_label))
            self.set_active_curve(target_label)

    def set_active_curve(self, label):
        self.current_label = label
        if label == "All":
            self.active_curve_idx = None
        else:
            for idx, curve in enumerate(self.curves):
                if curve['name'] == label:
                    self.active_curve_idx = idx
        if self._selected_points and label != "All":
            valid_points = [(c, p) for c, p in self._selected_points if c == self.active_curve_idx]
            self._selected_points = valid_points
        self._refresh_visual_style()
        self._reset_slider_widgets() 

    def _refresh_visual_style(self):
        for idx, curve in enumerate(self.curves):
            is_curve_active = (self.active_curve_idx is None or idx == self.active_curve_idx)
            if self._selection_x_bounds is not None:
                curve['ctrl_points'].set_alpha(0.02)
                curve['spline_line'].set_alpha(0.1)
                curve['spline_line'].set_linewidth(0.8)
                has_points_selected = any(c == idx for c, _ in self._selected_points)
                if is_curve_active and has_points_selected:
                    sel_p_idxs = [p for c, p in self._selected_points if c == idx]
                    xs_p = curve['x'][sel_p_idxs]
                    ys_p = curve['y'][sel_p_idxs]
                    curve['hl_ctrl_points'].set_data(xs_p, ys_p)
                    curve['hl_ctrl_points'].set_alpha(1.0)
                    curve['hl_ctrl_points'].set_markersize(7)
                    x_fine, y_fine = curve['fine_x_full'], curve['fine_y_full']
                    xmin, xmax = self._selection_x_bounds
                    mask = (x_fine >= xmin) & (x_fine <= xmax)
                    if np.any(mask):
                        curve['hl_spline_line'].set_data(x_fine[mask], y_fine[mask])
                        curve['hl_spline_line'].set_alpha(1.0)
                        curve['hl_spline_line'].set_linewidth(4.0)
                    else:
                        curve['hl_spline_line'].set_data([], [])
                else:
                    curve['hl_spline_line'].set_data([], [])
                    curve['hl_ctrl_points'].set_data([], [])
            else:
                curve['hl_spline_line'].set_data([], [])
                curve['hl_ctrl_points'].set_data([], [])
                if is_curve_active:
                    alpha_ctrl = 0.3 if self.active_curve_idx is None else 0.8
                    lw = 2.0 if self.active_curve_idx is None else 3.5
                    ms = 4 if self.active_curve_idx is None else 6
                    curve['ctrl_points'].set_alpha(alpha_ctrl)
                    curve['ctrl_points'].set_markersize(ms)
                    curve['spline_line'].set_alpha(1.0)
                    curve['spline_line'].set_linewidth(lw)
                else:
                    curve['ctrl_points'].set_alpha(0.05)
                    curve['ctrl_points'].set_markersize(3)
                    curve['spline_line'].set_alpha(0.15)
                    curve['spline_line'].set_linewidth(1.0)
        self.canvas.draw_idle()

    def _clear_selection(self):
        self._selected_points.clear()
        self._batch_moving = False
        self._selection_x_bounds = None
        if self._select_rect is not None:
            self._select_rect.remove()
            self._select_rect = None
        self._refresh_visual_style()
        self._reset_slider_widgets()

    def add_curve(self, x_ctrl, y_ctrl, color='blue', name="Curve"):
        x = np.array(x_ctrl, dtype=float)
        y = np.array(y_ctrl, dtype=float)
        if len(x) < 4:
            raise ValueError("At least 4 control points required.")
        ctrl_points, = self.ax.plot(x, y, 'o', color=color, markersize=4, alpha=0.4, zorder=2)
        spline_line, = self.ax.plot([], [], '-', color=color, linewidth=2, label=name, zorder=1)
        hl_ctrl_points, = self.ax.plot([], [], 'o', color=color, markersize=7, alpha=0.0, zorder=4)
        hl_spline_line, = self.ax.plot([], [], '-', color=color, linewidth=4, alpha=0.0, zorder=3)
        curve_dict = {
            'x': x, 'y': y,
            'color': color,
            'ctrl_points': ctrl_points,
            'spline_line': spline_line,
            'hl_ctrl_points': hl_ctrl_points,
            'hl_spline_line': hl_spline_line,
            'fine_x_full': None, 'fine_y_full': None,
            'name': name
        }
        self.curves.append(curve_dict)
        self._update_spline(len(self.curves) - 1)

    # ===================== 文件 I/O =====================

    def _clear_all_curves(self):
        """移除所有曲线 artist 并重置编辑器状态。"""
        for curve in self.curves:
            for key in ['ctrl_points', 'spline_line', 'hl_ctrl_points', 'hl_spline_line']:
                if curve.get(key) is not None:
                    curve[key].remove()
        self.curves.clear()
        self.undo_stack.clear()
        self._selected_points.clear()
        self._batch_moving = False
        self._selection_x_bounds = None
        self._slider_base_state = None
        self.active_curve_idx = None
        self.current_label = "All"
        self._active_curve_idx = None
        self._active_point_idx = None
        self._hide_drop_hint()
        # 重置坐标轴范围，等新数据加载后再自动适配
        self.ax.relim()
        self.ax.autoscale_view()

    def _auto_range_axes(self):
        """根据当前所有曲线数据自动适配 XY 轴范围，留 8% 边距。"""
        if not self.curves:
            return
        all_x = np.concatenate([c['x'] for c in self.curves])
        all_y = np.concatenate([c['y'] for c in self.curves])
        if len(all_x) == 0 or len(all_y) == 0:
            return

        x_min, x_max = np.min(all_x), np.max(all_x)
        y_min, y_max = np.min(all_y), np.max(all_y)

        # 避免零范围（如只有一条水平线）
        x_range = x_max - x_min or 1.0
        y_range = y_max - y_min or 1.0
        margin = 0.08

        self.ax.set_xlim(x_min - x_range * margin, x_max + x_range * margin)
        self.ax.set_ylim(y_min - y_range * margin, y_max + y_range * margin)
        self.canvas.draw_idle()

    def _expand_axes_if_needed(self):
        """
        检查当前曲线数据是否超出坐标轴范围，如果是则向外扩展（只扩大不缩小）。
        保证拖拽/缩放/加噪后曲线不会跑到视野之外。
        """
        if not self.curves:
            return
        all_y = np.concatenate([c['y'] for c in self.curves])
        if len(all_y) == 0:
            return

        y_min, y_max = np.min(all_y), np.max(all_y)
        cur_ylo, cur_yhi = self.ax.get_ylim()

        y_range = y_max - y_min or 1.0
        margin = 0.10  # 超出时留 10% 余量

        new_lo, new_hi = cur_ylo, cur_yhi
        changed = False

        if y_min < cur_ylo:
            new_lo = y_min - y_range * margin
            changed = True
        if y_max > cur_yhi:
            new_hi = y_max + y_range * margin
            changed = True

        if changed:
            self.ax.set_ylim(new_lo, new_hi)
            self.canvas.draw_idle()

    def _detect_format(self, file_path):
        """根据扩展名返回格式标识。"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.csv':
            return 'csv'
        elif ext in ('.xlsx', '.xls'):
            return 'excel'
        elif ext == '.npy':
            return 'npy'
        else:
            raise ValueError(f"不支持的文件格式: {ext}（支持 .csv .xlsx .npy）")

    def _load_data_from_file(self, file_path):
        """从文件读取曲线数据，返回 2D numpy 数组 (N_points, N_curves)。

        智能化方向判断：以较小的维度作为曲线数（列），较大的维度作为采样点数（行）。
        每一列 = 一条曲线，每一行 = 一个采样点。
        """
        fmt = self._detect_format(file_path)

        if fmt == 'csv':
            if not HAS_PANDAS:
                raise ImportError("读取 CSV 需要 pandas 库: pip install pandas")
            df = pd.read_csv(file_path, header=None)
            if df.empty:
                raise ValueError("CSV 文件为空")
            data = df.values.astype(float)

        elif fmt == 'excel':
            if not HAS_PANDAS:
                raise ImportError("读取 Excel 需要 pandas 和 openpyxl: pip install pandas openpyxl")
            df = pd.read_excel(file_path, header=None)
            if df.empty:
                raise ValueError("Excel 文件为空")
            data = df.values.astype(float)

        elif fmt == 'npy':
            data = np.load(file_path, allow_pickle=True)

        if data.ndim == 1:
            data = data.reshape(-1, 1)          # 单列 = 一条曲线
        if data.ndim != 2:
            raise ValueError(f"数据必须是 1D 或 2D，当前 shape: {data.shape}")

        # ---- 智能方向判断：较小维度 = 曲线数（列），较大维度 = 采样点（行） ----
        n_rows, n_cols = data.shape
        if n_rows < n_cols:
            # 行少列多 → 行=曲线，列=点 → 转置为列式
            data = data.T
            print(f"  方向检测: {n_rows}行×{n_cols}列 → 自动转置为 {n_cols}点×{n_rows}曲线")
        elif n_cols < n_rows:
            # 列少行多 → 已是列式（列=曲线，行=点）
            print(f"  方向检测: {n_rows}行×{n_cols}列 → 已是列式 ({n_rows}点×{n_cols}曲线)")
        # else: 方阵，保持原样，默认列=曲线

        if data.shape[0] < 4:
            raise ValueError(f"每条曲线至少需要 4 个采样点，当前仅 {data.shape[0]} 行")
        return data

    def load_curves_from_file(self, file_path=None):
        """打开文件（或弹出对话框）加载曲线数据，替换当前所有曲线。"""
        if file_path is None:
            file_path = filedialog.askopenfilename(
                title="打开曲线文件",
                filetypes=[
                    ("所有支持格式", "*.csv;*.xlsx;*.xls;*.npy"),
                    ("CSV 文件", "*.csv"),
                    ("Excel 文件", "*.xlsx;*.xls"),
                    ("NumPy 文件", "*.npy"),
                ]
            )
            if not file_path:
                return  # 用户取消

        try:
            data = self._load_data_from_file(file_path)
        except Exception as e:
            messagebox.showerror("加载错误", f"无法加载文件:\n{e}")
            return

        self.current_file_path = file_path
        self._clear_all_curves()
        self._clear_radio_panel()

        # data shape: (N_points, N_curves) — columns are curves
        n_curves = data.shape[1]
        n_points = data.shape[0]
        curve_colors = []
        for idx in range(n_curves):
            color = self.color_list[idx % len(self.color_list)] if self.color_list else f"C{idx}"
            name = f"Curve {idx}"
            curve_colors.append(color)
            self.add_curve(np.arange(n_points), data[:, idx], color=color, name=name)

        self._build_radio_panel(curve_colors)

        self._auto_range_axes()

        self._save_current_state()
        self._reset_slider_widgets()
        self._hide_drop_hint()

        fname = os.path.basename(file_path)
        self.fig.canvas.manager.set_window_title(f"CurveMagician - {fname}")
        print(f"已加载 {n_curves} 条曲线 ({n_points} 点/条)，来自 {file_path}")

    def save_file(self, event=None):
        """弹出保存对话框，支持 CSV / Excel / NPY 格式。"""
        if not self.curves:
            messagebox.showwarning("保存", "没有曲线数据可保存。")
            return

        default_ext = ".npy"
        initial_file = "curves.npy"
        if self.current_file_path:
            default_ext = os.path.splitext(self.current_file_path)[1]
            initial_file = os.path.basename(self.current_file_path)

        file_path = filedialog.asksaveasfilename(
            title="保存曲线为",
            initialfile=initial_file,
            defaultextension=default_ext,
            filetypes=[
                ("NumPy 文件", "*.npy"),
                ("CSV 文件", "*.csv"),
                ("Excel 文件", "*.xlsx"),
            ]
        )
        if not file_path:
            return

        try:
            fmt = self._detect_format(file_path)
            # 收集 Y 值 → (N_curves, N_points) → 转置为列式 (N_points, N_curves)
            # 每一列 = 一条曲线，每一行 = 一个采样点
            data = np.array([curve['y'] for curve in self.curves]).T

            if fmt == 'csv':
                if not HAS_PANDAS:
                    np.savetxt(file_path, data, delimiter=',')
                else:
                    pd.DataFrame(data).to_csv(file_path, index=False, header=False)
            elif fmt == 'excel':
                if not HAS_PANDAS:
                    raise ImportError("保存 Excel 需要 pandas 和 openpyxl: pip install pandas openpyxl")
                pd.DataFrame(data).to_excel(file_path, index=False, header=False)
            elif fmt == 'npy':
                np.save(file_path, data)

            self.current_file_path = file_path
            fname = os.path.basename(file_path)
            self.fig.canvas.manager.set_window_title(f"CurveMagician - {fname}")
            print(f"已保存 {data.shape[1]} 条曲线 ({data.shape[0]} 点/条) 到 {file_path}")
        except Exception as e:
            messagebox.showerror("保存错误", f"保存失败:\n{e}")

    def on_open_clicked(self, event=None):
        """Open 按钮回调。"""
        self.load_curves_from_file()

    # ===================== 单选面板构建 =====================

    def _clear_radio_panel(self):
        """清空右侧单选面板的所有元素。"""
        if self.ax_radio is None:
            return
        self.ax_radio.cla()
        self.ax_radio.set_xticks([])
        self.ax_radio.set_yticks([])
        self.ax_radio.set_navigate(False)
        self.ax_radio.set_xlim(0, 1)
        self.ax_radio.set_ylim(0, 1)
        self._top_dots = None
        self._radio_circles.clear()
        self._color_patches.clear()
        self.radio_menu = None
        self.radio_labels = []

    def _build_radio_panel(self, curve_colors):
        """构建右侧曲线选择面板（Circle patches + 色块 + 文字）。"""
        if self.ax_radio is None:
            return

        ax = self.ax_radio
        base_labels = ["All"] + [f"Curve {i}" for i in range(len(curve_colors))]
        num_labels = len(base_labels)
        font_size = 9 if num_labels > 8 else 10
        activecolor = '#2ca02c'
        active_idx = [0]  # 列表包装

        ys = np.linspace(1, 0, num_labels + 2)[1:-1]
        dot_radius = 0.022 if num_labels > 8 else 0.030
        patch_h = 0.55 / num_labels if num_labels > 8 else 0.035

        self._radio_circles = []

        for i in range(num_labels):
            y = ys[i]

            c = Circle(
                (0.07, y), dot_radius,
                transform=ax.transAxes,
                facecolor='white',
                edgecolor='black',
                linewidth=2.0,
                zorder=10,
            )
            ax.add_patch(c)
            self._radio_circles.append(c)

            ax.text(
                0.42, y, base_labels[i],
                transform=ax.transAxes,
                fontsize=font_size,
                va='center',
            )

            if i == 0:
                continue

            rect = Rectangle(
                (0.17, y - patch_h / 2), 0.22, patch_h,
                facecolor=curve_colors[i - 1],
                transform=ax.transAxes,
                zorder=0,
                edgecolor='#aaaaaa',
                linewidth=0.5,
            )
            ax.add_patch(rect)
            self._color_patches.append(rect)

        # ---- 刷新圆圈状态 ----
        def _refresh_dots():
            for i, c in enumerate(self._radio_circles):
                c.set_facecolor(activecolor if i == active_idx[0] else 'white')

        _refresh_dots()

        # ---- 点击回调 ----
        def _on_radio_click(event):
            if event.inaxes != ax or event.button != 1:
                return
            if event.ydata is None:
                return
            dists = np.abs(ys - event.ydata)
            closest = int(np.argmin(dists))
            if dists[closest] < 0.8 / num_labels:
                active_idx[0] = closest
                _refresh_dots()
                self.fig.canvas.draw_idle()
                self.set_active_curve(base_labels[closest])

        self.fig.canvas.mpl_connect('button_press_event', _on_radio_click)

        # ---- 兼容对象：供双击曲线同步选中 ----
        class _RadioCompat:
            labels = base_labels

            @staticmethod
            def set_active(idx):
                active_idx[0] = idx
                _refresh_dots()
                self.fig.canvas.draw_idle()

            @staticmethod
            def on_clicked(_cb):
                pass

        self.radio_menu = _RadioCompat()
        self.radio_labels = base_labels

    # ===================== 拖拽支持 =====================

    def _show_drop_hint(self):
        """在主图上显示拖放提示文字。"""
        if self.drop_hint is None:
            self.drop_hint = self.ax.text(
                0.5, 0.5,
                '拖放 CSV / Excel / NPY 文件到此处\n或点击 Open 按钮选择文件',
                transform=self.ax.transAxes,
                ha='center', va='center',
                fontsize=16, color='gray', alpha=0.35,
                zorder=100,
            )
        else:
            self.drop_hint.set_visible(True)
        self.canvas.draw_idle()

    def _hide_drop_hint(self):
        """隐藏拖放提示文字。"""
        if self.drop_hint is not None:
            self.drop_hint.set_visible(False)
            self.canvas.draw_idle()

    def _on_drop(self, event):
        """处理文件拖放事件。"""
        files = self.fig.canvas.manager.window.tk.splitlist(event.data)
        if not files:
            return

        cleaned = []
        for f in files:
            f = f.strip()
            if f.startswith('{') and f.endswith('}'):
                f = f[1:-1]
            cleaned.append(f)

        for fpath in cleaned:
            try:
                self._detect_format(fpath)
                self.load_curves_from_file(fpath)
                return
            except ValueError:
                continue

        messagebox.showwarning(
            "不支持的文件",
            "未找到支持的文件格式。\n支持: .csv, .xlsx, .npy"
        )

    def setup_drag_and_drop(self):
        """注册 Tk 窗口为文件拖放目标。"""
        if not HAS_DND:
            return
        try:
            window = self.fig.canvas.manager.window
            window.drop_target_register(DND_FILES)
            window.dnd_bind('<<Drop>>', self._on_drop)
            print("文件拖拽功能已启用")
        except Exception as e:
            print(f"拖拽注册失败: {e}")

    def _update_spline(self, curve_idx):
        curve = self.curves[curve_idx]
        x, y = curve['x'], curve['y']
        tck, u = splprep([x, y], s=0, k=3)
        u_fine = np.linspace(0, 1, 300)
        x_fine, y_fine = splev(u_fine, tck)
        curve['ctrl_points'].set_data(x, y)
        curve['spline_line'].set_data(x_fine, y_fine)
        curve['fine_x_full'] = x_fine
        curve['fine_y_full'] = y_fine

    def on_press(self, event):
        if self._is_toolbar_active():
            return
        
        if not hasattr(event, 'inaxes') or event.inaxes is None:
            return

        # 判断是否点在滑杆区域
        slider_axes = []
        if self.slider_scale: slider_axes.append(self.slider_scale.ax)
        if self.slider_smooth: slider_axes.append(self.slider_smooth.ax)
        if self.slider_noise: slider_axes.append(self.slider_noise.ax)

        if event.inaxes in slider_axes:
            self._is_sliding = True
            return

        if event.inaxes != self.ax:
            return

        if event.button == 3:
            self._clear_selection()
            return
        if event.button == 1:
            if self._selected_points:
                self._batch_moving = True
                self._batch_origin = (event.xdata, event.ydata)
                self._in_continuous_drag = True
                return
            c_idx, p_idx = self._get_closest_point(event)
            if c_idx is not None and p_idx is not None:
                self._active_curve_idx = c_idx
                self._active_point_idx = p_idx
                self._in_continuous_drag = True
                self.curves[c_idx]['ctrl_points'].set_markersize(8)
                self.curves[c_idx]['ctrl_points'].set_alpha(1.0)
                self.canvas.draw_idle()
                return
            self._selecting = True
            self._select_start = (event.xdata, event.ydata)
            self._select_rect = Rectangle(self._select_start, 0, 0, fill=True, alpha=0.2, color='gray')
            self.ax.add_patch(self._select_rect)

    def on_motion(self, event):
        if self._is_toolbar_active():
            return
        if self._is_sliding:
            return  

        if not hasattr(event, 'inaxes') or event.inaxes != self.ax or event.ydata is None:
            return

        if self._active_curve_idx is not None:
            c_idx = self._active_curve_idx
            p_center = self._active_point_idx
            curve = self.curves[c_idx]
            pts_idx = self._get_linked_point_indices(len(curve['y']), p_center)
            dy = event.ydata - curve['y'][p_center]
            for pid in pts_idx:
                curve['y'][pid] += dy
            self._update_spline(c_idx)
            if self._selection_x_bounds is not None:
                self._refresh_visual_style()
            else:
                self.canvas.draw_idle()
            return
        if self._selecting and self._select_rect is not None:
            x0, y0 = self._select_start
            x1, y1 = event.xdata, event.ydata
            self._select_rect.set_width(x1 - x0)
            self._select_rect.set_height(y1 - y0)
            self.canvas.draw_idle()
            return
        if self._batch_moving and self._batch_origin is not None:
            dy = event.ydata - self._batch_origin[1]
            for c_idx, p_idx in self._selected_points:
                if self.active_curve_idx is None or c_idx == self.active_curve_idx:
                    self.curves[c_idx]['y'][p_idx] += dy
            affected = set(c for c, _ in self._selected_points)
            for c in affected:
                self._update_spline(c)
            self._batch_origin = (self._batch_origin[0], event.ydata)
            self._refresh_visual_style()

    def on_release(self, event):
        if self._is_toolbar_active():
            return

        if self._is_sliding:
            self._is_sliding = False
            self._save_current_state()
            self._slider_base_state = [{'y': crv['y'].copy()} for crv in self.curves]
            return

        if not hasattr(event, 'inaxes') or event.inaxes is None:
            return

        need_save = False
        if self._active_curve_idx is not None:
            need_save = True
            self._refresh_visual_style()

        if self._batch_moving:
            need_save = True

        if self._selecting:
            self._selecting = False
            if self._select_start and event.xdata is not None and event.ydata is not None:
                x0, y0 = self._select_start
                x1, y1 = event.xdata, event.ydata
                self._selection_x_bounds = (min(x0, x1), max(x0, x1))
                self._selected_points = self._select_points_in_rect(x0, y0, x1, y1)
                self._refresh_visual_style()
            if self._select_rect is not None:
                self._select_rect.remove()
                self._select_rect = None

        self._active_curve_idx = None
        self._active_point_idx = None
        self._batch_moving = False
        self._batch_origin = None
        self._in_continuous_drag = False

        if need_save:
            self._save_current_state()
            self._reset_slider_widgets()
            self._expand_axes_if_needed()

    def _get_closest_point(self, event):
        if not self.curves or event.xdata is None or event.ydata is None:
            return None, None
        mouse_xy = self.ax.transData.transform((event.xdata, event.ydata))
        if self.active_curve_idx is not None:
            c_idx = self.active_curve_idx
            curve = self.curves[c_idx]
            x, y = curve['x'], curve['y']
            pts_xy = self.ax.transData.transform(np.c_[x, y])
            distances = np.linalg.norm(pts_xy - mouse_xy, axis=1)
            p_idx = np.argmin(distances)
            if distances[p_idx] < self._epsilon:
                return c_idx, p_idx
        else:
            min_dist = float('inf')
            closest_curve, closest_point = None, None
            for c_idx, curve in enumerate(self.curves):
                x, y = curve['x'], curve['y']
                pts_xy = self.ax.transData.transform(np.c_[x, y])
                distances = np.linalg.norm(pts_xy - mouse_xy, axis=1)
                p_idx = np.argmin(distances)
                if distances[p_idx] < min_dist:
                    min_dist = distances[p_idx]
                    closest_curve, closest_point = c_idx, p_idx
            if min_dist < self._epsilon:
                return closest_curve, closest_point
        return None, None

    def _select_points_in_rect(self, x0, y0, x1, y1):
        selected = []
        xmin, xmax = min(x0, x1), max(x0, x1)
        ymin, ymax = min(y0, y1), max(y0, y1)
        curves_to_check = [(self.active_curve_idx, self.curves[self.active_curve_idx])] if self.active_curve_idx is not None else enumerate(self.curves)
        for c_idx, curve in curves_to_check:
            xs, ys = curve['x'], curve['y']
            for p_idx, (px, py) in enumerate(zip(xs, ys)):
                if xmin <= px <= xmax and ymin <= py <= ymax:
                    selected.append((c_idx, p_idx))
        return selected

    def _get_linked_point_indices(self, total_len, center_idx):
        n = self.neighbor_num
        return list(range(max(0, center_idx - n), min(total_len - 1, center_idx + n) + 1))

    def set_neighbor_num(self, text):
        try:
            val = int(text)
            self.neighbor_num = max(0, val)
        except ValueError:
            print("Please enter an integer!")

    def _save_current_state(self):
        state = [{'x': crv['x'].copy(), 'y': crv['y'].copy()} for crv in self.curves]
        self.undo_stack.append(state)

    def undo(self, event=None):
        if len(self.undo_stack) <= 1:
            return
        self.undo_stack.pop()
        prev_state = self.undo_stack[-1]
        for idx, crv in enumerate(self.curves):
            if idx < len(prev_state):
                crv['x'][:] = prev_state[idx]['x']
                crv['y'][:] = prev_state[idx]['y']
                self._update_spline(idx)
        self._refresh_visual_style()
        self._reset_slider_widgets()

    def on_key(self, event):
        if event.key == 's':
            self.save_file()
        elif event.key == 'o':
            self.on_open_clicked()
        elif event.key == 'r':
            self._auto_range_axes()
        elif event.key == 'escape':
            self._clear_selection()
        elif event.key == 'z':
            self.undo()

    def save_curves_npy(self, event=None, filename="adjusted_curves.npy"):
        """兼容旧接口：快速保存为 .npy 到当前目录（按列存储）。"""
        if not self.curves:
            return
        npy_data = np.array([curve['y'] for curve in self.curves]).T
        save_dir = os.path.dirname(self.current_file_path) if self.current_file_path else '.'
        np.save(os.path.join(save_dir, filename), npy_data)
        print(f"NPY 已保存到: {os.path.join(save_dir, filename)}  ({npy_data.shape[0]} 点 x {npy_data.shape[1]} 曲线)")

    def _reset_slider_widgets(self):
        self._slider_base_state = [{'y': crv['y'].copy()} for crv in self.curves]
        if hasattr(self, 'slider_scale') and self.slider_scale:
            self.slider_scale.eventson = False
            self.slider_scale.set_val(1.0)  
            self.slider_scale.eventson = True
        if hasattr(self, 'slider_smooth') and self.slider_smooth:
            self.slider_smooth.eventson = False
            self.slider_smooth.set_val(1)
            self.slider_smooth.eventson = True
        if hasattr(self, 'slider_noise') and self.slider_noise:
            self.slider_noise.eventson = False
            self.slider_noise.set_val(0.0)
            self.slider_noise.eventson = True

    def _get_target_points_map(self):
        targets = {}
        if self._selected_points:
            for c_idx, p_idx in self._selected_points:
                if self.active_curve_idx is None or c_idx == self.active_curve_idx:
                    targets.setdefault(c_idx, []).append(p_idx)
        elif self.active_curve_idx is not None:
            targets[self.active_curve_idx] = list(range(len(self.curves[self.active_curve_idx]['y'])))
        else:
            for c_idx in range(len(self.curves)):
                targets[c_idx] = list(range(len(self.curves[c_idx]['y'])))
        return targets

    def on_slider_changed(self, val=None):
        if self._slider_base_state is None:
            return

        targets = self._get_target_points_map()
        scale_val = self.slider_scale.val
        smooth_val = int(self.slider_smooth.val)
        noise_coeff = self.slider_noise.val

        for c_idx, p_idxs in targets.items():
            orig_y = self._slider_base_state[c_idx]['y'].copy()
            p_idxs = np.array(p_idxs)
            if len(p_idxs) == 0:
                continue
            
            # 1. 缩放
            if scale_val != 1.0:
                orig_y[p_idxs] = orig_y[p_idxs] * scale_val

            # 2. 平滑
            if smooth_val > 1:
                smoothed = uniform_filter1d(orig_y.astype(float), size=smooth_val)
                orig_y[p_idxs] = smoothed[p_idxs]

            # 3. 加噪
            if noise_coeff > 0:
                data_range = np.std(orig_y[p_idxs]) if len(p_idxs) > 1 else np.mean(np.abs(orig_y[p_idxs]))
                if data_range == 0: data_range = 1.0
                
                np.random.seed(42)  
                noise = np.random.normal(0, data_range * 0.05 * noise_coeff, size=len(p_idxs))
                orig_y[p_idxs] += noise

            self.curves[c_idx]['y'][:] = orig_y
            self._update_spline(c_idx)

        self._expand_axes_if_needed()
        self._refresh_visual_style()


# ===================== 主程序 =====================
if __name__ == "__main__":
    data_path = './xx.npy'

    # Generate 12 demo curves if data file doesn't exist
    # Data shape: (N_points, N_curves) — each COLUMN is a curve
    if not os.path.exists(data_path):
        x = np.linspace(0, 10, 50)
        data = np.array([np.sin(x) + np.random.normal(0, 0.1, 50) for _ in range(12)]).T
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        np.save(data_path, data)
        print(f"Generated 12 demo curves: {data_path}  (shape: {data.shape[0]} pts x {data.shape[1]} curves)")

    color_list = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                  '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
                  '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5']

    fig = plt.figure(figsize=(15, 8))

    # ==== UI layout ====
    ax_main = plt.axes([0.05, 0.1, 0.70, 0.8])
    ax_btn_open  = plt.axes([0.05, 0.93, 0.08, 0.035])   # Open
    ax_btn_undo  = plt.axes([0.14, 0.93, 0.08, 0.035])
    ax_btn_save  = plt.axes([0.23, 0.93, 0.10, 0.035])
    ax_input_n   = plt.axes([0.35, 0.93, 0.12, 0.035])

    ax_slider_scale  = plt.axes([0.84, 0.91, 0.12, 0.018], facecolor='#e0e0e0')
    ax_slider_smooth = plt.axes([0.84, 0.86, 0.12, 0.018], facecolor='#e0e0e0')
    ax_slider_noise  = plt.axes([0.84, 0.81, 0.12, 0.018], facecolor='#e0e0e0')

    ax_radio = plt.axes([0.78, 0.08, 0.20, 0.68], facecolor='#fbfbfb')

    ax_main.grid(True, linestyle='--', alpha=0.6)

    # ==== Create editor ====
    text_box = TextBox(ax_input_n, "", initial="0")
    editor = HarmoniousCurvesEditor(
        ax_main, fig, ax_input_n,
        ax_radio=ax_radio, color_list=color_list,
    )
    text_box.on_submit(editor.set_neighbor_num)

    # ==== Buttons ====
    btn_open = Button(ax_btn_open, 'Open')
    btn_open.on_clicked(editor.on_open_clicked)
    btn_undo = Button(ax_btn_undo, 'Undo')
    btn_undo.on_clicked(editor.undo)
    btn_save = Button(ax_btn_save, 'Save')
    btn_save.on_clicked(editor.save_file)

    # ==== Sliders ====
    s_scale = Slider(ax_slider_scale, 'Scale ', 0.0, 2.0, valinit=1.0, valfmt='%.2f', color='#4682b4')
    s_smooth = Slider(ax_slider_smooth, 'Smooth', 1, 15, valinit=1, valfmt='%d', color='#4682b4')
    s_noise = Slider(ax_slider_noise, 'Noise ', 0.0, 5.0, valinit=0.0, valfmt='%.1f', color='#4682b4')

    s_scale.label.set_size(9)
    s_smooth.label.set_size(9)
    s_noise.label.set_size(9)

    editor.slider_scale = s_scale
    editor.slider_smooth = s_smooth
    editor.slider_noise = s_noise

    s_scale.on_changed(editor.on_slider_changed)
    s_smooth.on_changed(editor.on_slider_changed)
    s_noise.on_changed(editor.on_slider_changed)

    # ==== Initial data load ====
    if os.path.exists(data_path):
        editor.load_curves_from_file(os.path.abspath(data_path))
    else:
        editor._show_drop_hint()

    editor._save_current_state()
    editor._reset_slider_widgets()

    # ==== Enable drag-and-drop ====
    editor.setup_drag_and_drop()

    plt.show()