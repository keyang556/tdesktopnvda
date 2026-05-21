# Telegram Desktop Accessibility for NVDA

## Overview

Telegram Desktop Accessibility is an NVDA add-on for Telegram Desktop on Windows. It helps NVDA keep reading Telegram controls when Telegram exposes information that can otherwise stop focus announcements.

This add-on is intentionally small. It does not add new Telegram features, change your messages, or send any account data anywhere. Its main job is to make affected Telegram screens easier to read with NVDA.

> [!IMPORTANT]
> This add-on improves the Telegram Desktop screens it knows how to recognize. If Telegram changes its interface, some behavior may change until the add-on is updated.

## Features

* Improves Tab focus entry and focus announcements in Telegram chat and message lists.
* Helps NVDA read the country or region list shown while signing in with a phone number.
* Keeps Telegram's own item names intact, so chat, message, and country names are still spoken as Telegram provides them.
* Works quietly in the background. There are no extra add-on commands to remember.

## Tips

* Keep Telegram Desktop in a normal, visible window when navigating with NVDA.
* If the chat list stops reading after a Telegram update, restart Telegram Desktop and NVDA first.
* If the problem continues, please report it with your Telegram Desktop version, NVDA version, and the screen where speech stopped.

## What This Add-On Fixes

Some Telegram Desktop 6.8.3 and later screens can make NVDA stop reading a focused row or miss the row when Tab lands on a list container. The most visible examples are the chat list and message list: you move through items, but NVDA may stay silent.

This add-on restores NVDA-side focusability for the affected Telegram list containers and avoids problematic Telegram selection information on affected rows so NVDA can continue speaking the focused item. The same row protection is also used for the phone number country or region selection dialog.

## Keyboard Shortcuts

This add-on does not add its own keyboard shortcuts. Use Telegram Desktop's built-in shortcuts and normal NVDA navigation commands.

## Community and Support

* **Official Telegram channel**: [tdesktopnvda](https://t.me/tdesktopnvda). Follow the channel for release notes and project updates.
* **Telegram user group**: [tdesktopnvda_group](https://t.me/tdesktopnvda_group). Join the group to ask questions, share usage feedback, or discuss accessibility issues.
* **Source code and issue tracking**: [keyang556/tdesktopnvda](https://github.com/keyang556/tdesktopnvda). If you find a bug or have a feature suggestion, please open an Issue. If you would like to contribute code, documentation, or translations, Pull Requests are welcome.
* **Developer contact**: Ken Chang <lindsay714322@gmail.com>

## Supported Versions

* Telegram Desktop for Windows 6.8.3 and later, especially versions with the same list focus or reading issue.
* NVDA 2024.1 or later.

## Build From Source

From this repository:

```powershell
uv run scons
```

The generated `.nvda-addon` package can be installed through NVDA's add-on manager.
