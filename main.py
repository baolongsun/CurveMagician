import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import splprep, splev
import os
from matplotlib.patches import Rectangle
from matplotlib.widgets import Button, TextBox, RadioButtons

class HarmoniousCurvesEditor:
    def __init__(self, ax, fig, ax_n_input):
        self.fig = fig
        self.ax = ax
        self.canvas = ax.figure.canvas
        self.curves = []

        # 曲线激活锁定
        self.active_curve_idx = None
        self.current_label = "Edit All (None)"

        # 单点拖拽
        self._active_curve_idx = None
        self._active_point_idx = None
        self._epsilon = 15
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

        # Undo 栈（先初始化，延后保存初始状态）
        self.undo_stack = []
        self._in_continuous_drag = False

        # 事件绑定
        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('key_press_event', self.on_key)
        self.canvas.mpl_connect('button_press_event', self.on_double_click)

        # 单选组件引用
        self.radio_menu = None
        self.radio_labels = []

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
        if label == "Edit All (None)":
            self.active_curve_idx = None
        else:
            for idx, curve in enumerate(self.curves):
                if curve['name'] == label:
                    self.active_curve_idx = idx
        if self._selected_points and label != "Edit All (None)":
            valid_points = [(c, p) for c, p in self._selected_points if c == self.active_curve_idx]
            self._selected_points = valid_points
        self._refresh_visual_style()

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
        if event.inaxes != self.ax or self._is_toolbar_active():
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
        if event.inaxes != self.ax or event.ydata is None or self._is_toolbar_active():
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
        need_save = False

        if self._active_curve_idx is not None:
            need_save = True
            self._refresh_visual_style()

        if self._batch_moving:
            need_save = True

        if self._selecting:
            self._selecting = False
            if self._select_start and event.xdata and event.ydata:
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
        # 边界保护：至少保留初始状态，禁止越界
        if len(self.undo_stack) <= 1:
            return
        self.undo_stack.pop()
        prev_state = self.undo_stack[-1]
        # 二次下标防护
        for idx, crv in enumerate(self.curves):
            if idx < len(prev_state):
                crv['x'][:] = prev_state[idx]['x']
                crv['y'][:] = prev_state[idx]['y']
                self._update_spline(idx)
        self._refresh_visual_style()

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


# ===================== Main Program =====================
if __name__ == "__main__":
    data_path = './xx.npy'
    prefix_path = './'

    if not os.path.exists(data_path):
        x = np.linspace(0, 10, 50)
        data = np.array([np.sin(x) + np.random.normal(0, 0.1, 50) for _ in range(3)])
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        np.save(data_path, data)
        print(f"Generated mock data at {data_path}")

    color_list = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                  '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

    fig = plt.figure(figsize=(14, 7))
    ax_main = plt.axes([0.05, 0.1, 0.76, 0.8])
    ax_btn_undo = plt.axes([0.15, 0.92, 0.10, 0.04])
    ax_btn_save = plt.axes([0.27, 0.92, 0.10, 0.04])
    ax_input_n = plt.axes([0.39, 0.92, 0.12, 0.04])
    ax_radio = plt.axes([0.83, 0.1, 0.15, 0.8], facecolor='#f7f7f7')

    ax_main.grid(True, linestyle='--', alpha=0.6)
    # ax_radio.set_title("Select Curve", fontsize=11, pad=10)

    text_box = TextBox(ax_input_n, "", initial="0")
    editor = HarmoniousCurvesEditor(ax_main, fig, ax_input_n)
    text_box.on_submit(editor.set_neighbor_num)

    btn_undo = Button(ax_btn_undo, 'Undo')
    btn_undo.on_clicked(editor.undo)
    btn_save = Button(ax_btn_save, 'Save')
    btn_save.on_clicked(editor.save_curves_npy)

    base_labels = ["Edit All (None)"]
    curve_color_map = []
    data = np.load(data_path, allow_pickle=True)
    for idx in range(data.shape[0]):
        cur_color = color_list[idx % len(color_list)]
        curve_name = f"Curve {idx}"
        base_labels.append(curve_name)
        curve_color_map.append(cur_color)
        editor.add_curve(np.arange(len(data[idx])), data[idx], color=cur_color, name=curve_name)

    # ========== 关键修复：所有曲线加载完成后，再保存初始状态 ==========
    editor._save_current_state()

    radio_menu = RadioButtons(ax_radio, base_labels, active=0, activecolor='#2ca02c')
    radio_menu.on_clicked(editor.set_active_curve)
    editor.set_radio_ref(radio_menu, base_labels)

    for i in range(1, len(radio_menu.labels)):
        color = curve_color_map[i-1]
        label_pos = radio_menu.labels[i].get_position()
        y_pos = label_pos[1]
        color_patch = Rectangle(
            (0.02, y_pos - 0.018), 0.12, 0.035,
            color=color, transform=ax_radio.transAxes, zorder=5
        )
        ax_radio.add_patch(color_patch)

    editor.set_active_curve(base_labels[0])

    plt.show()