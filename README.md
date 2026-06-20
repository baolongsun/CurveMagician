# CurveMagician 🎨

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Research Tool](https://img.shields.io/badge/Research-Interactive%20Editor-success.svg)]()

**交互式 B 样条（B-Spline）曲线编辑器** — 面向科研与工程数据调校的轻量级可视化工具。直接在图上拖拽控制点完成数据修改，所见即所得，支持一键多格式保存。

![screenshot](cartoon.gif)

---

## 🎯 学术价值与定位

在实验数据处理、仿真参数调优、轨迹规划等科研场景中，原始数据往往伴随噪声、异常值或不符合理论预期。传统的"修改代码 → 运行 → 看图 → 再修改"循环效率低下且缺乏直观反馈。

**CurveMagician 将数据调试变成可视化交互**：

| 传统方式 | CurveMagician |
|:---|:---|
| 编辑器改参数 → 运行脚本 → 看图 | **鼠标拖拽曲线** → 数据实时更新 |
| `np.savetxt` 再 `np.loadtxt` 反复加载 | **原地编辑**，修改即刻生效 |
| 手动写滤波/缩放代码 | 滑杆**实时预览** Scale / Smooth / Noise |
| 单一 .npy 格式 | 拖拽加载 **CSV / Excel / NPY**，保存多格式 |

**适用领域**：实验物理数据处理、机器人轨迹规划、控制算法控制点生成、信号去噪、时间序列微调、有限元仿真曲线修正。

---

## 🚀 快速开始

```bash
# 基础依赖（必需）
pip install numpy matplotlib scipy

# 扩展依赖（推荐，支持 CSV/Excel 与拖拽）
pip install pandas openpyxl tkinterdnd2

# 运行
python main.py
```

首次运行自动生成 `./xx.npy`（12 条演示曲线，50 采样点/条）。支持直接拖入或打开 `.csv` / `.xlsx` / `.npy` 文件替换数据。

---

## 🧮 方法论：B 样条曲线编辑

### 数学基础

CurveMagician 使用 **三次 B 样条（Cubic B-Spline）** 对控制点进行插值：

$$C(u) = \sum_{i=0}^{n} N_{i,3}(u) \cdot P_i, \quad u \in [0, 1]$$

其中 $P_i$ 为用户可拖拽的**控制点**，$N_{i,3}(u)$ 为 3 阶 B 样条基函数，由 `scipy.interpolate.splprep` 计算节点向量，`splev` 生成 300 点精细采样曲线。

### 数据处理流水线

```
原始数据加载          用户交互              输出
┌──────────┐    ┌──────────────┐    ┌──────────┐
│ CSV/Excel│ →  │ 拖拽控制点    │ →  │ CSV/Excel│
│ NPY 文件 │    │ 框选批量移动   │    │ NPY 文件 │
│ 拖拽加载 │    │ Scale 缩放    │    │ 按列存储 │
└──────────┘    │ Smooth 平滑   │    └──────────┘
                │ Noise 加噪    │
                └──────────────┘
```

---

## 🖥️ 界面布局

```
  Left (70%)                                   Right (20%)
+---------------------------------------------+------------------+
|  [Open] [Undo] [Save]  N = [ 0 ]            |  Scale  |===o---|  <- 0~2x
|                                             |  Smooth |==o----|  <- 1~15
|                                             |  Noise  |o------|  <- 0~5
|                                             +------------------+
|       Curve Editor  (ax_main)               |  (*) All         |
|                                             |  ( ) [##] Crv 0  |
|       Drag / Box-select / Double-click      |  ( ) [##] Crv 1  |  <- Selector
|       Drop CSV/Excel/NPY to load            |  ( ) [##] ...   |     (*)=active
|                                             |  ( ) [##] Crv 11 |     ( )=inactive
+---------------------------------------------+------------------+
```

---

## ✨ 核心功能

### 📂 多格式文件 I/O + 拖拽加载

| 操作 | 触发方式 | 支持格式 |
|:---|:---|:---|
| 打开 | `Open` 按钮 / `O` 键 | `.csv` `.xlsx` `.xls` `.npy` |
| 保存 | `Save` 按钮 / `S` 键 | `.csv` `.xlsx` `.npy`（弹出对话框选格式） |
| 拖拽加载 | 拖文件到窗口 | 同上（需 `tkinterdnd2`） |

**智能化数据方向检测**：加载时自动判断行/列方向 — 以较小的维度作为曲线数（列），较大的维度作为采样点数（行）。保存统一为列式（每列一条曲线）。

### 🖱️ 拖拽编辑（原地修改）

- **单点拖拽**：鼠标左键按住控制点上下拖动，底层 NumPy 数组同步更新
- **邻近联动**：拖动时前后 $N$ 个控制点按弹性橡皮筋模型联动平移（$N$ 通过顶部输入框调节，默认 0 = 单点独立）
- **双击聚焦**：双击控制点自动锁定该曲线，其余曲线透明化 — 避免多曲线交织时的误触
- **坐标轴自动扩展**：拖拽超出视野时 Y 轴自动外扩，不会丢失数据

### 🟩 框选批量移动

- 空白区域左键拖拽出灰色矩形选区
- 框内控制点高亮显示，在框内再次拖拽 → 所有选中点同步平移
- 右键或 `Esc` 一键清除选区

### 🎚️ 实时滑杆调参

三条滑杆按固定流水线顺序处理：`Scale(×k) → Smooth(滤波) → Noise(加噪)`

| 滑杆 | 范围 | 默认 | 算法 | 科研用途 |
|:---|:---|:---|:---|:---|
| **Scale** | 0.0 ~ 2.0 | 1.0 | $y' = y \times s$ | 幅值归一化、灵敏度分析 |
| **Smooth** | 1 ~ 15 | 1 | `uniform_filter1d` | 去野点、高频噪声抑制 |
| **Noise** | 0.0 ~ 5.0 | 0.0 | $\mathcal{N}(0, 0.05 \sigma \cdot n)$ | 蒙特卡洛鲁棒性测试 |

> 滑杆以"操作前快照"为基准（`_slider_base_state`），拖拽后自动复位，避免操作叠加混乱。噪声种子固定（seed=42），确保实验可复现。

### 🔒 曲线聚焦与选择

- 右侧面板每条曲线有独立**单选圆圈**（白底黑边，选中变绿）
- 选中 `All` 回到全局编辑模式
- 颜色方块辅助识别曲线身份

### ↩️ 撤销保护

- `Undo` 按钮或 `Z` 键，完整状态栈，带边界保护（不会回滚初始数据）

---

## ⌨️ 快捷键总览

| 按键 | 功能 |
|:---|:---|
| `S` | 保存（弹出格式选择对话框） |
| `O` | 打开文件 |
| `Z` | 撤销 |
| `R` | 重置坐标轴范围（自动适配当前数据） |
| `Esc` / 右键 | 清除框选 |
| 双击控制点 | 聚焦该曲线 |
| 左键拖拽控制点 | 单点 / 邻近联动拖拽 |
| 左键空白拖拽 | 框选 |
| 框内左键拖拽 | 批量移动 |

---

## 📊 数据格式规范

### 列式存储（Column-Oriented）

```
CSV / Excel / NPY 文件结构:

        Curve 0   Curve 1   ...   Curve N-1
Point 0    y₀₀       y₀₁    ...     y₀ₙ₋₁
Point 1    y₁₀       y₁₁    ...     y₁ₙ₋₁
  ...      ...       ...    ...      ...
Point M-1  yₘ₋₁₀    yₘ₋₁₁  ...     yₘ₋₁ₙ₋₁

shape = (M 采样点, N 曲线)
```

- **每一列 = 一条曲线**，**每一行 = 一个采样点**
- X 轴自动生成为 `0, 1, 2, ..., M-1`
- 加载时智能检测方向：维度较小者为曲线数，较大者为采样点数

---

## 📦 依赖

| 库 | 必需 | 用途 |
|:---|:---|:---|
| `numpy` | ✅ | 矩阵运算、.npy 读写 |
| `matplotlib` | ✅ | 图形界面（TkAgg 后端）、交互组件 |
| `scipy` | ✅ | B 样条插值 (`splprep`/`splev`)、均匀滤波 |
| `pandas` | 推荐 | CSV/Excel 读写 |
| `openpyxl` | 推荐 | pandas 读写 .xlsx 的底层引擎 |
| `tkinterdnd2` | 推荐 | 文件拖拽加载（跨平台） |

---

## 🧬 代码架构

```
CurveMagician/
├── main.py              # 主程序入口
├── xx.npy               # 演示数据（自动生成）
└── cartoon.gif          # 效果展示
```

### 核心类 `HarmoniousCurvesEditor`

| 方法 | 功能 |
|:---|:---|
| **文件 I/O** | |
| `load_curves_from_file(path)` | 打开/拖拽 → 清旧 → 加载 → 重建面板 → 自适应坐标轴 |
| `save_file(event)` | 弹出格式对话框保存（csv/xlsx/npy），自动列式输出 |
| `_load_data_from_file(path)` | 多格式读取 + 智能行列方向检测 |
| `_detect_format(path)` | 扩展名 → csv / excel / npy |
| **交互编辑** | |
| `on_press / on_motion / on_release` | 鼠标事件：拖拽、框选、批量移动 |
| `on_double_click` | 双击聚焦联动面板 |
| `on_key` | 键盘：`S`/`O`/`Z`/`R`/`Esc` |
| **信号处理** | |
| `on_slider_changed` | Scale(×k) → Smooth(滤波) → Noise(加噪) 流水线 |
| **坐标轴管理** | |
| `_auto_range_axes()` | 完全重置 XY 范围适配数据（`R` 键触发） |
| `_expand_axes_if_needed()` | 拖拽/滑杆超出视野时**只扩大不缩小** |
| **UI 构建** | |
| `_build_radio_panel(colors)` | 构建右侧单选面板（Circle + Rectangle + Text） |
| `setup_drag_and_drop()` | 注册 Tk 窗口为文件拖放目标 |
| `_show_drop_hint / _hide_drop_hint` | 空数据时的半透明拖放提示 |
| **状态管理** | |
| `undo` | 状态栈弹出，带边界保护 |
| `_save_current_state` | 全量快照当前曲线数据 |
| `_reset_slider_widgets` | 快照基准状态并复位滑杆 |
