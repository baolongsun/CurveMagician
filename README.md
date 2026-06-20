# CurveMagician

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**交互式三次样条曲线编辑器** — 拖拽实时修改，框选批量操作，滑杆调参，支持 CSV / Excel / NPY 导入导出。

![screenshot](cartoon.gif)

---

## 快速开始

```bash
pip install numpy matplotlib scipy       # 必需
pip install openpyxl tkinterdnd2         # 可选：Excel 读写 + 拖拽加载
python main.py
```

启动自动加载 3 条演示正弦曲线。CSV 走 numpy 原生、Excel 需 openpyxl、拖拽需 tkinterdnd2。

---

## 界面

```
┌───────────────────────────────────────────────┬─────────────────────┐
│ [Open][Save][Undo] [+/-N] [Fit] [cnt] [Rsmpl] │ Scale  ═══o════     │
│                                               │ Smooth ══o═════     │
│                   主绘图区                     │ Noise  ═o══════     │
│           拖拽控制点 / 框选 / 双击聚焦          ├─────────────────────┤
│           拖放文件直接加载                      │ (●) All             │
│                                               │ ( ) ██ Curve 0      │
│                                               │ ( ) ██ Curve 1      │
│                                               │ ( ) ██ Curve 2      │
├───────────────────────────────────────────────┴─────────────────────┤
│  50 pts  Curve 2                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

底部状态栏实时显示选中点数与当前曲线，输入框自动同步当前点数，不一致时显示 `---`。

---

## 操作

### 鼠标

| 操作 | 效果 |
|:---|:---|
| 左键拖拽控制点 | 上下移动，联动 ±N 个相邻点 |
| 空白处左键拖拽 | 框选多个控制点 |
| 框内再次拖拽 | 批量移动 |
| 双击控制点 | 聚焦该曲线（其余淡出） |
| 右键 / `Esc` | 清除选区 |

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
| `Esc` | 清除选区 |

### 重采样

输入框显示当前选中曲线的控制点数。修改目标值后点 **Resample**，三次样条插值将控制点均匀重采样，边界自动缓冲保证平滑衔接。

---

## 数据格式

**列式存储**（每列 = 一条曲线，每行 = 一个采样点）。加载时自动检测行列方向。

```
       Curve 0   Curve 1   Curve 2
Pt 0      y₀₀       y₀₁       y₀₂
 Pt 1     y₁₀       y₁₁       y₁₂
  ...      ...       ...       ...
Pt 79     y₇₉₀      y₇₉₁      y₇₉₂
```

---

## 代码结构

```
main.py
├── _make_demo_curves()        演示数据
├── _build_ui()                Figure + 布局
├── _wire_widgets()            控件绑定
├── _load_demo()               加载演示
├── HarmoniousCurvesEditor     核心编辑类
│   ├── 文件 I/O               CSV / Excel / NPY
│   ├── 交互编辑               拖拽、框选、删点、撤销
│   ├── 信号处理               Scale · Smooth · Noise
│   └── 重采样                 样条插值增/减控制点
└── main()                     入口
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
       main.py
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
