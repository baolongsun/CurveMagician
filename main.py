import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import splprep, splev
import os
from matplotlib.patches import Rectangle
import matplotlib.widgets as mwidgets
from matplotlib.widgets import Button, TextBox, RadioButtons, Slider
from scipy.ndimage import uniform_filter1d

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
    def __init__(self, ax, fig, ax_n_input):
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
            self.save_curves_npy()
        elif event.key == 'escape':
            self._clear_selection()
        elif event.key == 'z':
            self.undo()

    def save_curves_npy(self, event=None, filename="adjusted_curves.npy"):
        if not self.curves:
            return
        npy_data = np.array([curve['y'] for curve in self.curves])
        np.save(f"{prefix_path}/{filename}", npy_data)
        print(f"NPY Data successfully saved to: {filename}")

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

        self._refresh_visual_style()


# ===================== 主程序 =====================
if __name__ == "__main__":
    data_path = './xx.npy'
    prefix_path = './'

    # 默认模拟生成 12 条测试曲线，用于验证高密度下的排版健壮性
    if not os.path.exists(data_path):
        x = np.linspace(0, 10, 50)
        data = np.array([np.sin(x) + np.random.normal(0, 0.1, 50) for _ in range(12)])
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        np.save(data_path, data)
        print(f"Generated 12 lines mock data at {data_path}")

    color_list = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                  '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
                  '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5']

    fig = plt.figure(figsize=(15, 8))
    
    # 重新布局区域：加宽单选面板，给圆圈+色块+文字留足横向空间
    ax_main = plt.axes([0.05, 0.1, 0.70, 0.8])
    ax_btn_undo = plt.axes([0.15, 0.93, 0.10, 0.035])
    ax_btn_save = plt.axes([0.27, 0.93, 0.10, 0.035])
    ax_input_n = plt.axes([0.39, 0.93, 0.12, 0.035])

    ax_slider_scale  = plt.axes([0.84, 0.91, 0.12, 0.018], facecolor='#e0e0e0')
    ax_slider_smooth = plt.axes([0.84, 0.86, 0.12, 0.018], facecolor='#e0e0e0')
    ax_slider_noise  = plt.axes([0.84, 0.81, 0.12, 0.018], facecolor='#e0e0e0')

    ax_radio         = plt.axes([0.78, 0.08, 0.20, 0.68], facecolor='#fbfbfb')

    ax_main.grid(True, linestyle='--', alpha=0.6)

    text_box = TextBox(ax_input_n, "", initial="0")
    editor = HarmoniousCurvesEditor(ax_main, fig, ax_input_n)
    text_box.on_submit(editor.set_neighbor_num)

    btn_undo = Button(ax_btn_undo, 'Undo')
    btn_undo.on_clicked(editor.undo)
    btn_save = Button(ax_btn_save, 'Save')
    btn_save.on_clicked(editor.save_curves_npy)

    # 提升滑杆对比度与色块宽度，解决“不好滑”问题
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

    base_labels = ["All"]
    curve_color_map = []
    data = np.load(data_path, allow_pickle=True)
    for idx in range(data.shape[0]):
        cur_color = color_list[idx % len(color_list)]
        curve_name = f"Curve {idx}"
        base_labels.append(curve_name)
        curve_color_map.append(cur_color)
        editor.add_curve(np.arange(len(data[idx])), data[idx], color=cur_color, name=curve_name)

    editor._save_current_state()
    editor._reset_slider_widgets()

    # ===== 创建单选菜单（适配 matplotlib 3.7+ API）=====
    num_labels = len(base_labels)
    font_size = 9 if num_labels > 8 else 10
    circle_size = 75 if num_labels > 8 else 100

    # 不隐藏原生按钮，保留内部点击逻辑，彻底规避 KeyError
    radio_props = {
        's': circle_size,
        'edgecolor': 'black',
        'linewidth': 1.5,
        'zorder': 10,
    }
    radio_menu = RadioButtons(
        ax_radio, base_labels, active=0, activecolor='#2ca02c',
        radio_props=radio_props,
    )
    radio_menu.on_clicked(editor.set_active_curve)
    editor.set_radio_ref(radio_menu, base_labels)

    # 原生圆点坐标左移
    offsets = radio_menu._buttons.get_offsets()
    offsets[:, 0] = 0.07
    radio_menu._buttons.set_offsets(offsets)

    # 存储每行Y坐标，手动绘制顶层覆盖圆点
    row_y_list = []
    for i, label_text in enumerate(radio_menu.labels):
        label_text.set_fontsize(font_size)
        pos = label_text.get_position()
        label_text.set_position((0.40, pos[1]))
        row_y_list.append(pos[1])

        if i == 0:
            continue
        color = curve_color_map[i - 1]
        y_pos = pos[1]
        patch_height = 0.55 / num_labels if num_labels > 8 else 0.035
        # 色块避让圆点
        color_patch = Rectangle(
            (0.18, y_pos - patch_height / 2), 0.16, patch_height,
            color=color, transform=ax_radio.transAxes, zorder=5,
            edgecolor='#cccccc', linewidth=0.5,
        )
        ax_radio.add_patch(color_patch)

    # ========== 手动顶层圆点（永久置顶，覆盖原生透明圆点，无点击冲突） ==========
    dot_x = np.full(num_labels, 0.07)
    dot_y = np.array(row_y_list)
    top_dots = ax_radio.scatter(
        dot_x, dot_y,
        s=circle_size,
        edgecolors="black",
        linewidth=1.5,
        zorder=99,  # 全局最高层级，永远可见
        transform=ax_radio.transAxes
    )

    # 同步更新两层圆点颜色
    def sync_dot_style(selected_idx):
        # 顶层手动圆点
        top_fc = []
        for i in range(num_labels):
            if i == selected_idx:
                top_fc.append(radio_menu.activecolor)
            else:
                top_fc.append((1.0, 1.0, 1.0, 1.0))
        top_dots.set_facecolors(top_fc)

        # 底层原生圆点兜底同步
        btns = radio_menu._buttons
        btns.set_edgecolors("black")
        btns.set_linewidths(1.5)
        bot_fc = []
        for i in range(num_labels):
            if i == selected_idx:
                bot_fc.append(radio_menu.activecolor)
            else:
                bot_fc.append((1.0, 1.0, 1.0, 1.0))
        btns.set_facecolors(bot_fc)
        fig.canvas.draw_idle()

    # 重写set_active，切换同步刷新圆点
    original_set_active = radio_menu.set_active
    def patched_set_active(idx):
        original_set_active(idx)
        sync_dot_style(idx)
    radio_menu.set_active = patched_set_active

    # 初始化渲染圆点
    radio_menu.set_active(0)

    plt.show()