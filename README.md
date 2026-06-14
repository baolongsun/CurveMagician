# HarmoniousCurvesEditor 📊🎨

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Scientific Tool](https://img.shields.io/badge/Scientific-Essential-success.svg)](#-科研利器--scientific-powerhouse)

An interactive spline curve editor featuring drag-and-drop manipulation and batch editing for real-time, in-place data modification with direct local saving.

> **项目简介 / Description:**
> 本项目是一款基于 Matplotlib 开发的**轻量级、交互式 B 样条（Spline）数据调校利器**。它打破了传统代码调试数据的繁琐流程，支持通过直观的界面拖拽、区域框选进行数据的**原地（In-place）快速调整**，并允许直接一键保存并覆盖至本地 `.npy` 文件。无缝打通“可视化调校 ➡️ 实时流刷新 ➡️ 本地覆盖存储”的完整闭环。

---

## 🎬 Showcasing / 效果展示

![alt text](cartoon.gif)

---

## 🔬 科研利器 / Scientific Powerhouse

在学术研究与工程实验中，原始采集的数据往往伴随噪声、异常点，通过编写代码不断调参往往效率低下。本项目是**科研人员不可或缺的曲线微调与仿真神器**：
* **快速调校，即刻保存 (Rapid Tuning & Local Saving):** 彻底告别“修改代码-运行查看-再修改”的低效循环。通过鼠标直观拖拽，即可完成对复杂曲线的毫秒级修正，`并支持将拖动修改后的原始数据保存到本地`，让数据调整在眨眼间完成。
* **数据去噪与平滑 (Data Denoising):** 摆脱盲目的调参，通过肉眼可见的平滑样条（Spline）直接剔除异常野点。
* **物理轨迹规划 (Trajectory Planning):** 完美适用于机器人路径规划、自动驾驶控制算法的控制点（Anchor Points）快速生成与动态微调。
* **实验数据实时拟合 (In-place Fitting):** 无缝替换原始实验矩阵，修改即刻生效，助你快速调校出最符合理论预期的完美曲线。

---

## 🚀 Key Features / 核心特性

* 💾 **In-place Quick Saving (快速调整，原地保存):** **核心高频功能！** 曲线调整满意后，敲击键盘 `S` 键或点击内置按钮，编辑后的新坐标将直接**覆盖/重写本地 `.npy` 源文件**，下次运行程序或下游脚本时直接加载最新数据。
* 🖱️ **In-place Drag & Drop (原地交互拖拽):** 颠覆代码调参！直接在图表中拖动控制点，底层数值矩阵同步完成毫秒级原地更新。
* 🔗 **Neighboring Linkage (邻近点联动平滑):** 引入类似弹性橡皮筋的平滑机制。拖动单个点时，其前后的 $N$ 个邻近点会跟随进行高斯式协同形变，保持曲线整体的数学和谐感。
* 🟩 **Batch Area Selection (区域框选批量移动):** 类似网格工具的框选体验。一键框选局部区域内的多个控制点，支持单曲线或多曲线同时跨维度垂直平移。
* 🔒 **Focus Mode (曲线焦点锁定):** 告别多线交织的误触烦恼。支持通过侧边栏 Radio 菜单或直接**双击曲线控制点**，快速孤立/激活目标曲线。
* ↩️ **Robust Undo Stack (防误触撤销栈):** 具备完善的边界保护。支持快捷键无限次撤销，无论是拖歪还是框选错误，都能一键安全回融数据状态。

---

## ⌨️ Shortcuts & Code Mapping / 交互快捷键与底层代码映射

为了方便开发者二次开发与使用者快速上手，以下是系统内嵌的快捷键事件与底层代码函数的映射关系：

| 交互动作 / 快捷键 | 触发方式 / 关联按键 | 底层触发函数 | 功能与逻辑说明 |
| :--- | :--- | :--- | :--- |
| **原地保存 (Save)** | 键盘 **`S`** 键 / `Save` 按钮 | `save_curves_npy()` | 将当前图表中快速调整后的最新矩阵数据，通过 `np.save()` 异步直接**覆盖并写入本地 `.npy` 源文件**。 |
| **撤销回滚 (Undo)** | 键盘 **`Z`** 键 / `Undo` 按钮 | `undo()` | 弹出 `undo_stack` 栈顶状态。代码包含边界保护（`len <= 1` 时禁止越界），确保绝对不会因为误操作回滚掉初始数据。 |
| **取消选择 (Escape)** | 键盘 **`Escape`** 键 | `_clear_selection()` | 清除所有当前的框选高亮（隐藏临时高亮控制点与高亮粗线条），并将框选标志位复位，恢复到全局自由编辑模式。 |
| **右键清空 (Clear)** | 鼠标 **`Right-Click` (右键)** | `on_press()` *(event.button == 3)* | 效果同 `Escape`。在图表任意空白处点击鼠标右键，即可瞬间清除当前的框选矩阵和矩形框。 |
| **曲线聚焦锁定** | 鼠标 **`Double-Click` (双击)** | `on_double_click()` | 双击某个控制点后，底层自动通过 `_get_closest_point()` 识别曲线 ID，动态联动更新右侧 RadioButtons 组件，并将其余未选中曲线淡化。 |
| **单点联动拖拽** | 鼠标 **`Left-Click & Drag`** | `on_motion()` | 持续捕获鼠标垂直位移 $\Delta y$，通过 `_get_linked_point_indices()` 动态计算当前 $N$ 邻域内的点并同步进行原地累加。 |
| **区域批量框选** | 空白处 **`Left-Click & Drag`** | `on_press()` ➡️ `on_motion()` | 底层在 `on_press` 时生成 `Rectangle` 补丁，在鼠标滑动中动态计算宽高，并在 `on_release` 时通过 `_select_points_in_rect()` 捕获多点。 |
| **批量垂直平移** | 框选高亮内 **`Left-Click & Drag`** | `on_motion()` *(self._batch_moving)* | 遍历 `_selected_points` 集合中的所有曲线与点索引，对满足激活条件的所有控制点同时应用 $\Delta y$ 偏移量并重绘样条。 |

---

## 📦 Installation / 安装指南

Ensure you have Python 3.8+ installed, then install the required lightweight dependencies:

```bash
pip install numpy matplotlib scipy