# CurveMagician 🎨

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**交互式 B 样条曲线编辑器** — 支持拖拽控制点、框选批量移动、实时滑杆调参，修改后一键保存 `.npy` 数据。

![screenshot](cartoon.gif)

---

## 🚀 快速开始

```bash
# 安装依赖
pip install numpy matplotlib scipy

# 运行（自动生成 12 条演示曲线）
python main.py
```

首次运行会自动在 `./xx.npy` 生成模拟数据；你也可以替换为自己的 `.npy` 文件（shape 为 `(N_curves, N_points)`）。

---

## 🖥️ 界面布局

```
  Left (70%)                                Right (20%)
+------------------------------------------+------------------+
|  [Undo]  [Save]  N = [ 0 ]               |  Scale  |===o----|  <- Scale  0~2x
|                                          |  Smooth |==o-----|  <- Smooth 1~15
|                                          |  Noise  |o-------|  <- Noise  0~5
|                                          +------------------+
|      Curve Editor  (ax_main)             |  (*) All         |
|                                          |  ( ) [##] Crv 0  |
|      Drag / Box-select / Double-click    |  ( ) [##] Crv 1  |  <- Curve selector
|                                          |  ( ) [##] ...    |     (*) = active
|                                          |  ( ) [##] Crv 11 |     ( ) = inactive
+------------------------------------------+------------------+
```

---

## ✨ 核心功能

### 🖱️ 拖拽编辑
- **单点拖拽**：鼠标左键按住控制点上下拖动，底层数据实时更新
- **邻近联动**：拖动一个点时，前后 $N$ 个邻近点同步平移（弹性橡皮筋效果）。$N$ 值通过顶部文本框调节
- **双击聚焦**：双击曲线上的任意控制点，自动锁定该曲线，其余曲线变淡

### 🟩 框选批量移动
- 在空白区域按住左键拖拽出灰色矩形框选区域
- 松开后，框内控制点被高亮
- 在高亮区域内再次拖拽，所有选中点同步上下移动
- 右键或 `Esc` 清除框选

### 🎚️ 三条滑杆：缩放 · 平滑 · 噪点

右侧面板上方有三个实时滑杆，按**固定流水线顺序**处理数据：

$$
\text{原始数据} \xrightarrow{\text{① Scale}} \text{缩放后} \xrightarrow{\text{② Smooth}} \text{平滑后} \xrightarrow{\text{③ Noise}} \text{最终曲线}
$$

| 滑杆 | 范围 | 默认值 | 算法 | 效果 |
|:---|:---|:---|:---|:---|
| **Scale** | 0.0 ~ 2.0 | 1.0 | $y' = y \times \text{scale}$ | 整体纵向拉伸/压缩，1.0 为不变 |
| **Smooth** | 1 ~ 15 | 1 | `scipy.ndimage.uniform_filter1d` | 滑动窗口均值滤波，值越大曲线越平滑，1 为不变 |
| **Noise** | 0.0 ~ 5.0 | 0.0 | $\mathcal{N}(0,\ \sigma \times 0.05 \times \text{noise})$ | 添加高斯噪声（seed=42 可复现），$\sigma$ 为选中点标准差，0.0 为不变 |

> **作用范围**：滑杆作用于当前选中的单条曲线，或 "All" 模式下的全部曲线。
>
> **与拖拽的协作**：滑杆始终以"拖动前"的快照（`_slider_base_state`）为基准计算，因此拖拽后滑杆自动复位，确保两种操作不会叠加混乱。松开滑杆后，新状态被保存为新的基准。



### 🔒 曲线聚焦锁定
- 右侧面板显示所有曲线的颜色方块和单选圆圈
- **点击圆圈**选中目标曲线，其余曲线自动淡化
- 选中 `All` 回到全局编辑模式
- 双击主图中的控制点可快速切换到对应曲线

### ↩️ 撤销
- 点击 `Undo` 按钮或按 `Z` 键撤销上一步操作
- 底层维护完整的状态栈，不会越界回滚初始数据

### 💾 保存
- 点击 `Save` 按钮或按 `S` 键，将当前调整后的数据保存为 `adjusted_curves.npy`
- 原始数据文件不会被覆盖

---

## ⌨️ 快捷键总览

| 操作 | 触发方式 | 说明 |
|:---|:---|:---|
| 保存 | `S` 键 / `Save` 按钮 | 保存当前数据到 `adjusted_curves.npy` |
| 撤销 | `Z` 键 / `Undo` 按钮 | 回滚到上一步状态 |
| 取消框选 | `Esc` 键 / 右键 | 清除框选高亮，回到全局模式 |
| 曲线聚焦 | 双击控制点 | 自动切换到对应曲线 |
| 单点拖拽 | 左键按住控制点拖动 | 上下拖动修改曲线形状 |
| 框选 | 空白处左键拖拽 | 框选区域内控制点 |
| 批量移动 | 在高亮区域内拖拽 | 批量上下平移选中点 |

---

## 📦 依赖

| 库 | 用途 |
|:---|:---|
| `numpy` | 数据存储与矩阵运算 |
| `matplotlib` | 图形界面、交互组件 |
| `scipy` | B 样条插值 (`splprep`/`splev`)、均匀滤波 (`uniform_filter1d`) |

---

## 🧬 代码结构

```
CurveMagician/
├── main.py              # 主程序（RadioButtons 版，兼容 matplotlib 3.7+）
├── main_v2.py           # 改进版（自定义 Circle 面板，彻底解决圆圈可见性问题）
├── xx.npy               # 演示数据（自动生成，12 条曲线 × 50 点）
├── adjusted_curves.npy  # 保存的输出数据
└── cartoon.gif          # 演示截图
```

### 核心类：`HarmoniousCurvesEditor`

| 方法 | 功能 |
|:---|:---|
| `add_curve(x, y, color, name)` | 添加一条曲线（≥4 个控制点） |
| `on_press / on_motion / on_release` | 鼠标事件：拖拽、框选、批量移动 |
| `on_double_click` | 双击控制点 → 联动右侧面板聚焦 |
| `on_key` | 键盘事件：S 保存 / Z 撤销 / Esc 取消 |
| `on_slider_changed` | 滑杆流水线：`Scale(×k)` → `Smooth(uniform_filter1d)` → `Noise(N(0,σ))` |
| `_reset_slider_widgets` | 快照当前状态作为滑杆新基准，并将滑杆复位到默认值 |
| `undo` | 状态栈弹出，恢复上一步 |
| `save_curves_npy` | 导出当前数据到 `.npy` |
| `_update_spline` | B 样条重算（`splprep` + `splev`，300 采样点） |
