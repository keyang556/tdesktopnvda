# Telegram Desktop Accessibility for NVDA

NVDA add-on for improving Telegram Desktop accessibility.

## Fixed First

Telegram Desktop 6.8.x exposes the chat list as UIA list items, but its
`SelectionItemPattern.currentSelectionContainer` can raise a COM error while
NVDA is preparing focus speech. When that happens, NVDA aborts the focus event
and chat rows are not read.

This add-on adds a Telegram-specific appModule overlay for chat list rows. It
keeps Telegram's existing accessible row names intact and returns no selection
container for those rows, avoiding the failing UIA query that blocks speech.

## Build

From this repository:

```powershell
uv run scons
```

The generated `.nvda-addon` package can then be installed through NVDA's add-on
manager.
