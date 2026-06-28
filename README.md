<p align="center"><img src="image.png" width="180"></p>

# CurveMagician

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**交互式三次样条曲线编辑器** — 拖拽实时修改，框选批量操作，可调窗口微调，滑杆调参，支持 CSV / Excel / NPY 导入导出。

![screenshot](cartoon.gif)

---

## 快速开始

```bash
pip install numpy matplotlib scipy       # 必需
pip install openpyxl tkinterdnd2         # 可选：Excel 读写 + 拖拽加载
python main_qt.py
```

启动自动加载 3 条演示正弦曲线。CSV / Excel 支持**不等长曲线**（ragged columns）。

---

## 界面

```
┌───────────────────────────────────────────────────┬──────────────────────┐
│ [Open][Save][Undo][Fit][Pin] [+/-N] [cnt] [Rsmpl] │ Scale  ═══o════      │
│                                                   │ Smooth ══o═════      │
│                    主绘图区                         │ Noise  ═o══════      │
│         拖拽控制点 / 框选 / 双击聚焦 / Shift+框选     ├──────────────────────┤
│         拖放文件直接加载                             │ ( ) All              │
│                                                   │ ( ) ██ Curve 0       │
│                                                   │ (🔒) ██ Curve 1 ←锁   │
│                                                   │ (📌) ██ Curve 2 ←固定 │
├───────────────────────────────────────────────────┴──────────────────────┤
│  50 pts  Adjusting (C1: 12p, C2: 8p)                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

底部状态栏实时显示选中点数与当前曲线，输入框自动同步当前点数，不一致时显示 `---`。

---

## 操作

### 鼠标

| 操作 | 效果 |
|:---|:---|
| 左键拖拽控制点 | 上下移动，联动 ±N 个相邻点 |
| 空白处左键拖拽 | 框选多个控制点 |
| **Shift + 左键拖拽** | 框选后进入**可调窗口模式**，拖拽手柄微调窗口大小 |
| 可调窗口内双击 / `Enter` | 确认窗口，固化选择 |
| 可调窗口内 `Esc` / 右键 | 取消窗口 |
| 框内再次拖拽 | 批量移动 |
| 双击控制点 | 聚焦/锁定该曲线 |
| 右键 / `Esc` | 清除选区 |

### 右侧面板

| 操作 | 效果 |
|:---|:---|
| 单击曲线图标 | 选中该曲线（单选） |
| 双击曲线图标 | **锁定**曲线（🔒）— 始终高亮，仍可编辑 |
| **Pin 按钮** | **固定**当前活跃曲线（📌）— 始终高亮，**永不选中/拖拽** |

### 滑杆（Scale → Smooth → Noise 流水线）

| 滑杆 | 范围 | 作用 |
|:---|:---|:---|
| Scale | 0 ~ 2× | 幅值缩放 |
| Smooth | 1 ~ 15 | 均匀滤波去噪 |
| Noise | 0 ~ 5 | 高斯噪声（每次拖拽随机种子） |

### 快捷键

| 按键 | 功能 |
|:---|:---|
| `Tab` | 轮流切换曲线（All → Curve 0 → … → All） |
| `A` | 选中全部曲线 |
| `Delete` | 删除框选控制点（≥4 点保护） |
| `Z` | 撤销 |
| `O` | 打开文件 |
| `S` | 另存为 |
| `R` | 坐标轴适配全部数据 |
| `Esc` | 清除选区 / 取消可调窗口 |
| `Enter` | 确认可调窗口 |

### 重采样

输入框显示当前选中曲线的控制点数。修改目标值后点 **Resample**，三次样条插值将控制点均匀重采样，边界自动缓冲保证平滑衔接。

---

## 数据格式

**列式存储**（每列 = 一条曲线，每行 = 一个采样点）。加载时自动检测行列方向。**支持不等长曲线**——每条曲线独立读取，短列不补零。

```
       Curve 0   Curve 1   Curve 2
Pt 0      y₀₀       y₀₁       y₀₂
 Pt 1     y₁₀       y₁₁       y₁₂
  ...      ...       ...         
Pt 79     y₇₉₀      y₇₉₁      y₇₉₂+y₈₀₂  ← Curve 2 更长
```

- **等长** → 可保存为 NPY / CSV / Excel
- **不等长** → 自动隐藏 NPY，推荐 Excel / CSV，短列尾部留空

---

## 代码结构

```
main_qt.py
├── _make_demo_curves()              演示数据
├── _build_ui()                      Figure + 布局
├── _wire_widgets()                  控件绑定 (含 Pin 按钮)
├── _load_demo()                     加载演示
├── HarmoniousCurvesEditor           核心编辑类
│   ├── 文件 I/O                     CSV / Excel / NPY · 不等长支持
│   ├── 交互编辑                     拖拽 · 框选 · 删点 · 撤销
│   ├── Shift+框选可调窗口            进入/拖拽微调/确认/取消
│   ├── Lock & Pin                   锁定(🔒) · 固定(📌) · 永不选中
│   ├── 信号处理                     Scale · Smooth · Noise
│   └── 重采样                       样条插值增/减控制点
└── main()                           入口
```

---

## 打包

```bash
nuitka --standalone --onefile --remove-output       \
       --no-deployment-flag=self-execution          \
       --jobs=4 --enable-plugin=tk-inter            \
       --nofollow-import-to=PyQt5                   \
       --nofollow-import-to=PyQt6                   \
       --nofollow-import-to=PySide2                 \
       --nofollow-import-to=PySide6                 \
       main_qt.py
```

---

## 依赖

| 库 | 必需 | 用途 |
|:---|:---|:---|
| numpy | ✓ | 数组运算 |
| matplotlib | ✓ | 图形界面 (TkAgg) |
| scipy | ✓ | 三次样条插值、均匀滤波 |
| openpyxl | — | Excel 读写 |
| tkinterdnd2 | — | 文件拖拽加载 |
