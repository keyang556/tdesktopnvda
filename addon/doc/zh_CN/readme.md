# Telegram 电脑版 NVDA 无障碍附加组件

* 作者：[Ken Chang](https://t.me/Keyang556)
* [Telegram 频道](https://t.me/tdesktopnvda)
* [Telegram 用户群组](https://t.me/tdesktopnvda_group)

## 概述

Telegram 电脑版 NVDA 无障碍附加组件适用于 Windows 版 Telegram Desktop。此附加组件提供直接导航和通话命令，并保留 Telegram 原有的无障碍行为和控件名称。

## 功能

* `Alt+1` 将焦点移到会话列表中已选中的会话；没有选中项目时，则移到第一个会话。
* `Alt+M` 打开 Telegram 主菜单。
* `Alt+Y`、`Alt+N`、`Alt+A` 和 `Alt+V` 分别用于接听通话、拒接或挂断、开关麦克风，以及开关摄像头。每个命令都会用 Telegram 自己的措辞报出所执行的操作，因此会跟随 Telegram 的界面语言。
* 所有命令都会列在 NVDA 的“输入手势”对话框中，归类于“Telegram Desktop Accessibility”，因此可以自行更改或移除默认快捷键。在 Telegram 以外的程序中，按键会原样传给该程序。
* 主菜单的结构性控件（例如个人资料和账号）、未命名的输入栏控件，以及顶栏的建议项，都会获得可用的无障碍标签。Telegram 已提供的真实名称始终保留。
* 当 UnigramPlus 或其他附加组件占用 Telegram 共用的 app module 名额时，会由前台感知的回退机制继续提供这些快捷键和标签，且不会在 Telegram 以外绑定按键。
* 会话和通话控件的识别使用 Telegram 稳定的 UIA 类信息，不使用翻译后的控件名称，因此不受 Telegram 界面语言影响。
* 只公开 Telegram 内部 C++ 类路径的控件不再朗读该路径；Telegram 提供的其他名称不会被替换。

## 使用方法

安装附加组件并按提示重新启动 NVDA 后，即可在 Telegram 主窗口使用这些快捷键，无需额外配置。

如果 `Alt+1` 找不到会话列表或列表为空，NVDA 会说明原因。如果当前 Telegram 界面没有主菜单，按下 `Alt+M` 时 NVDA 会提示主菜单不可用。找不到对应控件时，通话命令会提示没有来电或当前不在通话中。通话在独立窗口中进行，因此即使 Telegram 主窗口在前台，通话命令仍然可用。

若要改用其他按键，请打开“NVDA 菜单”>“首选项”>“输入手势”，展开“Telegram Desktop Accessibility”分类，再为任一命令添加或移除手势。

## 将 Telegram 切换为简体中文

1. 打开 Telegram，按下 **Main menu** 按钮。
2. 按 `Tab` 找到 **Settings**，再按 `Enter`。
3. 按 `Tab` 找到 **Language**，再按 `Enter`。
4. 选择 **简体中文**。
5. 找到 **OK** 并按下，完成语言切换。

## 快捷键

> “提供者”一列中，`附加组件` 表示由本附加组件提供的快捷键，`Telegram Desktop` 表示 Telegram Desktop 内置的快捷键。
>
> **提示：**附加组件的快捷键可从“NVDA 菜单”>“首选项”>“输入手势”自行更改。

### 会话

| 快捷键 | 提供者 | 功能 |
|---|---|---|
| **Alt+1** | 附加组件 | 将焦点移到会话列表 |
| **上 / 下 / Page Up / Page Down** | Telegram Desktop | 在会话内导航 |
| **Shift+滚动** | Telegram Desktop | 加速会话内导航 |
| **上 / 左 / 右 / 下** | Telegram Desktop | 导航建议的贴纸 |
| **左 / 右** | Telegram Desktop | 导航建议的表情符号 |
| **Ctrl+Tab / Ctrl+Page Down / Alt+下** | Telegram Desktop | 移到下一个会话 |
| **Ctrl+Shift+Tab / Ctrl+Page Up / Alt+上** | Telegram Desktop | 移到上一个会话 |
| **Esc** | Telegram Desktop | 退出、返回或取消当前操作 |
| **Ctrl+O** | Telegram Desktop | 发送文件 |

### 通话

| 快捷键 | 提供者 | 功能 |
|---|---|---|
| **Alt+Y** | 附加组件 | 接听来电 |
| **Alt+N** | 附加组件 | 拒接来电，或挂断进行中的通话 |
| **Alt+A** | 附加组件 | 通话中开启或关闭麦克风 |
| **Alt+V** | 附加组件 | 通话中开启或关闭摄像头 |

### 文件夹

| 快捷键 | 提供者 | 功能 |
|---|---|---|
| **Ctrl+Shift+下** | Telegram Desktop | 移到下一个文件夹 |
| **Ctrl+Shift+上** | Telegram Desktop | 移到上一个文件夹 |
| **Ctrl+1 至 Ctrl+7** | Telegram Desktop | 直接跳到指定文件夹 |
| **Ctrl+8** | Telegram Desktop | 跳到最后一个文件夹 |

### 消息

| 快捷键 | 提供者 | 功能 |
|---|---|---|
| **Ctrl+上 / Ctrl+下** | Telegram Desktop | 回复消息 |
| **Ctrl+下 / Esc** | Telegram Desktop | 取消回复 |
| **上** | Telegram Desktop | 编辑最后发送的消息 |
| **Delete** | Telegram Desktop | 删除当前选中的消息 |
| **Ctrl+数字键盘加号 / Ctrl+数字键盘减号** | Telegram Desktop | 放大或缩小图片／视频 |
| **Ctrl+单击名称** | Telegram Desktop | 从内联消息打开机器人资料 |

### 搜索

| 快捷键 | 提供者 | 功能 |
|---|---|---|
| **Ctrl+F** | Telegram Desktop | 搜索当前会话 |
| **Esc** | Telegram Desktop | 退出搜索 |
| **Ctrl+J** | Telegram Desktop | 搜索联系人 |

### 快速分享面板

| 快捷键 | 提供者 | 功能 |
|---|---|---|
| **上 / 下** | Telegram Desktop | 在面板中导航 |
| **Enter** | Telegram Desktop | 选择会话 |
| **Backspace / Delete** | Telegram Desktop | 移除会话 |
| **Ctrl+Enter** | Telegram Desktop | 发送消息 |

### 跳转

| 快捷键 | 提供者 | 功能 |
|---|---|---|
| **Alt+Enter** | Telegram Desktop | 跳到会话底部，或将会话列表滚动到顶部 |
| **Ctrl+0** | Telegram Desktop | 打开“收藏夹” |
| **Ctrl+1 至 Ctrl+5** | Telegram Desktop | 没有文件夹时，直接跳到指定的置顶会话 |
| **Ctrl+9** | Telegram Desktop | 打开“已归档的对话” |

### 窗口

| 快捷键 | 提供者 | 功能 |
|---|---|---|
| **Alt+M** | 附加组件 | 打开主菜单 |
| **Ctrl+W / Alt+F4** | Telegram Desktop | 最小化到系统托盘 |
| **Ctrl+Q** | Telegram Desktop | 退出 Telegram |
| **Ctrl+L** | Telegram Desktop | 锁定 Telegram |
| **Ctrl+M** | Telegram Desktop | 最小化 Telegram |

### 选中的文本

| 快捷键 | 提供者 | 功能 |
|---|---|---|
| **Ctrl+B** | Telegram Desktop | 粗体 |
| **Ctrl+I** | Telegram Desktop | 斜体 |
| **Ctrl+K** | Telegram Desktop | 创建链接 |
| **Ctrl+U** | Telegram Desktop | 下划线 |
| **Ctrl+Shift+M** | Telegram Desktop | 等宽文本 |
| **Ctrl+Shift+N** | Telegram Desktop | 清除格式／纯文本 |
| **Ctrl+Shift+P** | Telegram Desktop | 剧透格式 |
| **Ctrl+Shift+X** | Telegram Desktop | 删除线 |
| **Ctrl+Shift+句号** | Telegram Desktop | 引用 |

### 鼠标快捷操作

| 快捷键 | 提供者 | 功能 |
|---|---|---|
| **双击消息** | Telegram Desktop | 回复 |
| **从消息向外拖动** | Telegram Desktop | 选择多条消息 |
| **将鼠标悬停在时间戳上** | Telegram Desktop | 显示消息信息 |
| **将鼠标悬停在投票百分比上** | Telegram Desktop | 显示票数 |
| **将消息拖到列表中的会话** | Telegram Desktop | 将消息转发到该会话 |
| **返回** | Telegram Desktop | 退出“已归档的对话” |
| **上传图片后单击预览** | Telegram Desktop | 编辑媒体 |
| **右键单击“发送”按钮** | Telegram Desktop | 静默发送或定时发送消息 |

## 实现方式

Telegram Desktop 修补后的 Qt 无障碍提供程序会通过 UIA 公开 RTTI 类名。附加组件使用 `Dialogs::InnerWidget` 识别会话列表，因此无需匹配本地化后的无障碍名称。主菜单命令则通过 UIA 坐标命中测试在左上角查找 Telegram 原生的按钮，同时支持 `Dialogs::Widget` 和文件夹侧栏两种布局，必要时再回退到既有的提供程序端子树查询。

Telegram 的通话面板把每个控件都创建为 `Ui::CallButton`，从左到右依次是共享屏幕、摄像头、取消或拒接、接听或挂断、麦克风、添加成员。其中只有摄像头和麦克风带有设备选择的角落按钮，因此附加组件通过该角落按钮识别这两者，其余则按它们在这一排中的位置识别。查找控件时完全不读取翻译后的名称；只有在报出操作时才读取名称，因为每个按钮的名称就是按下后会执行的操作。

所有命令都由全局插件拥有，并以限定的所有者解析本附加组件的 app module，避免其他附加组件占用共用的 `appModules/telegram.py` 名额。命令只定义一次，且定义在始终运行的插件中，NVDA 的“输入手势”对话框才会为每个命令保留唯一且可重新指定的条目；每个命令会自行检查前台窗口，并在 Telegram 不在前台时把按键传给该程序。

## 社区与支持

* **Telegram 官方频道**：[tdesktopnvda](https://t.me/tdesktopnvda)
* **Telegram 用户群组**：[tdesktopnvda_group](https://t.me/tdesktopnvda_group)
* **源代码和问题跟踪**：[keyang556/tdesktopnvda](https://github.com/keyang556/tdesktopnvda)
* **开发者联系方式**：[Ken Chang](https://t.me/Keyang556) <lindsay714322@gmail.com>

## 支持版本

* Telegram Desktop for Windows 7.0.1 或更高版本。
* NVDA 2024.1 或更高版本。

## 从源代码构建

在此仓库根目录运行：

```powershell
uv run scons
```

生成的 `.nvda-addon` 软件包可通过 NVDA 附加组件商店安装。
