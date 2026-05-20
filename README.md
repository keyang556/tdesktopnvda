# Telegram Desktop Accessibility for NVDA

Telegram Desktop Accessibility is an NVDA add-on for improving Telegram Desktop accessibility. It focuses on keeping Telegram Desktop readable when broken UI Automation data would otherwise stop NVDA from announcing focused controls.

## Languages

- English: `README.md`
- Traditional Chinese: `addon/doc/zh_TW/readme.md`
- Simplified Chinese: `addon/doc/zh_CN/readme.md`

The add-on manifest uses English as the default language and includes Traditional Chinese and Simplified Chinese localized metadata through gettext catalogs under `addon/locale/`.

## Fixed First

Telegram Desktop 6.8.x exposes the chat list as UIA list items, but its
`SelectionItemPattern.currentSelectionContainer` can raise a COM error while
NVDA is preparing focus speech. When that happens, NVDA aborts the focus event
and chat rows are not read.

This add-on adds Telegram-specific appModule overlays for affected list rows. It
keeps Telegram's existing accessible row names intact and returns no selection
container for those rows, avoiding the failing UIA query that blocks speech.
The same protection is applied to the phone number country selection dialog
introduced by Telegram Desktop's `CountrySelectBox`.

## Author

Ken Chang <lindsay714322@gmail.com>

## Build

From this repository:

```powershell
uv run scons
```

The generated `.nvda-addon` package can then be installed through NVDA's add-on
manager.
