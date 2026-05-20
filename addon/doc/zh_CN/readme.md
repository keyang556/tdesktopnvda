# Telegram 电脑版 NVDA 辅助工具

## 概述

Telegram 电脑版 NVDA 辅助工具是一个给 NVDA 用户使用的 Telegram Desktop 附加组件。它能改善 Telegram 电脑版在某些画面中无法稳定朗读的问题，让会话列表、登录时的国家/地区列表，以及焦点变化更容易被听见。

这个附加组件的功能很单纯：它不会改变您的 Telegram 消息，不会加入新的 Telegram 功能，也不会把账号数据发送到其他地方。它主要是在后台协助 NVDA 正常朗读受影响的 Telegram 界面。

> [!IMPORTANT]
> 此附加组件会改善它能识别的 Telegram 电脑版画面。如果 Telegram 更新后界面有所变化，部分效果可能需要等待附加组件更新。

## 功能特色

* 改善 Telegram 会话列表的焦点朗读。
* 改善使用电话号码登录时，国家/地区选择列表的朗读。
* 保留 Telegram 原本提供的会话名称和列表项目名称。
* 在后台自动运行，不需要另外记忆新的附加组件快捷键。

## 使用技巧与提醒

* 使用 NVDA 操作 Telegram 时，建议让 Telegram 电脑版保持在正常、可见的窗口状态。
* 如果更新 Telegram 后会话列表突然无法朗读，请先重新启动 Telegram 电脑版和 NVDA。
* 如果问题仍然存在，反馈时请附上 Telegram 电脑版版本、NVDA 版本，以及发生问题的画面。

## 将 Telegram 界面切换为简体中文

1. 打开 [简体中文语言链接](https://t.me/setlanguage/zh-hans-beta)。
2. Telegram 打开变更语言的确认对话框之后，按 `Tab` 找到 **Apply Language** 按钮并按下。
3. 如果部分文字没有立即更新，请关闭并重新打开 Telegram Desktop。

## 此附加组件修复了什么

某些 Telegram Desktop 6.8.x 画面可能会让 NVDA 无法朗读当前焦点所在的列表行。最常见的情况是：您在会话列表中上下移动，但 NVDA 没有读出会话名称。

此附加组件会避开 Telegram 在这些行上造成朗读中断的信息，让 NVDA 可以继续读出当前焦点项目。同样的保护也应用在电话号码登录流程中的国家/地区选择对话框。

## 键盘快捷键

此附加组件目前没有新增专用快捷键。请使用 Telegram Desktop 内置快捷键，以及 NVDA 原本的导航方式操作。

## 社区与支持

* **官方 Telegram 频道**：[tdesktopnvda](https://t.me/tdesktopnvda)。欢迎关注频道以获取版本更新和项目消息。
* **Telegram 用户交流群组**：[tdesktopnvda_group](https://t.me/tdesktopnvda_group)。欢迎加入群组提出建议、反馈使用问题，或参与无障碍相关讨论。
* **源代码与问题跟踪**：[keyang556/tdesktopnvda](https://github.com/keyang556/tdesktopnvda)。如果有功能建议或发现错误，欢迎开 Issue；如果愿意协助修复程序、改善文档或翻译，也非常欢迎提交 Pull Request。
* **联系开发者**：Ken Chang <lindsay714322@gmail.com>

## 支持版本

* Telegram Desktop for Windows，特别是 6.8.x 或具有相同会话列表朗读问题的版本。
* NVDA 2024.1 或更新版本。

## 从源代码构建

请在此仓库根目录执行：

```powershell
uv run scons
```

生成的 `.nvda-addon` 包可通过 NVDA 的附加组件管理器安装。
