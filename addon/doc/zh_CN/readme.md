# Telegram 电脑版无障碍支持

Telegram 电脑版无障碍支持是为 NVDA 用户设计的 Telegram Desktop 附加组件。它改善 Telegram 电脑版在屏幕阅读器下的朗读稳定性，让会话列表、焦点变化和相关状态更容易被理解。

## 已修复问题

Telegram Desktop 6.8.x 会将会话列表暴露为 UIA 列表项目，但在 NVDA 准备焦点朗读时，`SelectionItemPattern.currentSelectionContainer` 可能引发 COM 错误。发生这种情况时，NVDA 会中止焦点事件，导致会话行无法被朗读。

此附加组件会针对受影响的列表行加入 Telegram 专用的 appModule overlay。它保留 Telegram 原有的可访问行名称，并让这些行不返回选择容器，避免触发会阻断朗读的 UIA 查询。同样的保护也应用到 Telegram Desktop `CountrySelectBox` 引入的电话号码国家/地区选择对话框。

## 语言

- 英文：`README.md`
- 繁体中文：`addon/doc/zh_TW/readme.md`
- 简体中文：`addon/doc/zh_CN/readme.md`

附加组件的 manifest 以英文作为默认语言，并通过 `addon/locale/zh_CN/LC_MESSAGES/nvda.po` 提供简体中文元数据。

## 构建

请在此仓库根目录执行：

```powershell
uv run scons
```

生成的 `.nvda-addon` 包可通过 NVDA 的附加组件管理器安装。

## 作者

Ken Chang <lindsay714322@gmail.com>
