# Telegram Desktop Accessibility for NVDA

## Overview

Telegram Desktop Accessibility is an NVDA add-on for Telegram Desktop on Windows. It adds direct navigation commands and announces the active chat while switching conversations, leaving Telegram's native accessibility behavior and accessible names unchanged.

## Features

* `Alt+1` moves focus to the selected chat in the chat list, or to the first chat when no chat is selected. Pressing it while a chat already has focus repeats that chat's name, and pressing it inside the main menu closes the menu first.
* `Alt+M` opens Telegram's main menu.
* `Ctrl+Tab` and `Ctrl+Shift+Tab` keep Telegram's native chat switching and announce the newly active chat title.
* `Ctrl+Enter` on a focused message opens whatever the message holds: its links, the file paths it mentions, and the documents attached to it. A single item opens immediately, and anything more is offered in an accessible chooser in reading order. An attachment already downloaded is opened from Telegram's download folder; otherwise Telegram is asked to download and open it. Outside a message, Telegram's own `Ctrl+Enter` behavior is passed through untouched.
* Structural main-menu controls such as Profile and Accounts, and composer controls Telegram leaves unnamed, receive useful accessible labels. The top bar suggestion is announced by its own wording, and its dismiss button is labelled.
* Controls that reach NVDA carrying only Telegram's internal C++ class path are no longer announced by that path.
* Chat detection uses Telegram's stable UIA class information rather than a translated control name, so the commands do not depend on Telegram's interface language.
* Telegram continues to provide the names of chats, messages, buttons, and list items. The add-on changes names only for known controls that Telegram leaves unlabeled.

## Usage

Install the add-on, restart NVDA when prompted, and use the two add-on shortcuts from the main Telegram window. No configuration is required.

If `Alt+1` cannot find a chat list or the list is empty, NVDA reports that condition. If `Alt+M` is unavailable on the current Telegram screen, NVDA reports that the main menu is not available. When switching chats, the add-on waits for Telegram's window title to update before announcing it.

## Implementation

Telegram Desktop's patched Qt accessibility provider exposes RTTI-based UIA class names. The add-on identifies the chat list as `Dialogs::InnerWidget`, allowing it to work independently of the localized accessible name. It locates that list through UIA point hit-testing first, because a full-subtree provider query costs roughly half a second on large accounts, and falls back to the subtree query for unusual layouts. The main menu command locates Telegram's native menu button inside `Dialogs::Widget`, or as the first `Ui::SideBarButton` in the folder-sidebar layout, and invokes its existing action. It finds that button by point hit-testing near the top-left corner of the window, with the same subtree fallback. A foreground-aware global plugin keeps the shortcuts available when another installed add-on supplies Telegram's app module, without intercepting them in other applications.

Telegram paints its conversation header rather than exposing it as a dedicated accessible title control, but it does update the top-level window name after a native chat switch. `Ctrl+Tab` therefore passes the keystroke through to Telegram and then reads the refreshed provider-side window name, falling back to the display model and finally to Windows OCR of the painted header region.

## Keyboard Shortcuts

### Add-on

| Shortcut | Provided by | Function |
|---|---|---|
| **Alt+1** | Add-on | Move focus to the chat list |
| **Alt+M** | Add-on | Open the main menu |
| **Ctrl+Tab** | Telegram + add-on | Move to the next chat and announce its title |
| **Ctrl+Shift+Tab** | Telegram + add-on | Move to the previous chat and announce its title |
| **Ctrl+Enter** | Add-on | Open the only link or file, or show every link and file in the focused message |

### Chats

| Shortcut | Provided by | Function |
|---|---|---|
| **Up / Down / Page Up / Page Down** | Telegram Desktop | Navigate within a chat |
| **Shift+Scroll** | Telegram Desktop | Speed up in-chat navigation |
| **Up / Left / Right / Down** | Telegram Desktop | Navigate suggested stickers |
| **Left / Right** | Telegram Desktop | Navigate suggested emoji |
| **Ctrl+Page Down / Alt+Down** | Telegram Desktop | Move to the chat below |
| **Ctrl+Page Up / Alt+Up** | Telegram Desktop | Move to the chat above |
| **Esc** | Telegram Desktop | Exit, go back, or cancel the current action |
| **Ctrl+O** | Telegram Desktop | Send a file |

### Folders

| Shortcut | Provided by | Function |
|---|---|---|
| **Ctrl+Shift+Down** | Telegram Desktop | Move to the folder below |
| **Ctrl+Shift+Up** | Telegram Desktop | Move to the folder above |
| **Ctrl+1 through Ctrl+7** | Telegram Desktop | Jump directly to a folder |
| **Ctrl+8** | Telegram Desktop | Jump to the last folder |

### Messages

| Shortcut | Provided by | Function |
|---|---|---|
| **Ctrl+Up / Ctrl+Down** | Telegram Desktop | Reply to a message |
| **Ctrl+Down / Esc** | Telegram Desktop | Cancel a reply |
| **Up** | Telegram Desktop | Edit the last message sent |
| **Delete** | Telegram Desktop | Delete the currently selected message |
| **Ctrl+Numpad Plus / Ctrl+Numpad Minus** | Telegram Desktop | Zoom an image or video in or out |
| **Ctrl+Click the name** | Telegram Desktop | Open a bot profile from an inline message |

### Search

| Shortcut | Provided by | Function |
|---|---|---|
| **Ctrl+F** | Telegram Desktop | Search the selected chat |
| **Esc** | Telegram Desktop | Exit search |
| **Ctrl+J** | Telegram Desktop | Search for a contact |

### Quick Share Panel

| Shortcut | Provided by | Function |
|---|---|---|
| **Up / Down** | Telegram Desktop | Navigate the panel |
| **Enter** | Telegram Desktop | Select a chat |
| **Backspace / Delete** | Telegram Desktop | Remove a chat |
| **Ctrl+Enter** | Telegram Desktop | Send the message |

### Jump To

| Shortcut | Provided by | Function |
|---|---|---|
| **Alt+Enter** | Telegram Desktop | Jump to the bottom of the chat or scroll the chat list to the top |
| **Ctrl+0** | Telegram Desktop | Open Saved Messages |
| **Ctrl+1 through Ctrl+5** | Telegram Desktop | Jump directly to a pinned chat when there are no folders |
| **Ctrl+9** | Telegram Desktop | Open Archived Chats |

### Window

| Shortcut | Provided by | Function |
|---|---|---|
| **Ctrl+W / Alt+F4** | Telegram Desktop | Minimize to the system tray |
| **Ctrl+Q** | Telegram Desktop | Quit Telegram |
| **Ctrl+L** | Telegram Desktop | Lock Telegram |
| **Ctrl+M** | Telegram Desktop | Minimize Telegram |

### Selected Text

| Shortcut | Provided by | Function |
|---|---|---|
| **Ctrl+B** | Telegram Desktop | Bold |
| **Ctrl+I** | Telegram Desktop | Italic |
| **Ctrl+K** | Telegram Desktop | Create a link |
| **Ctrl+U** | Telegram Desktop | Underline |
| **Ctrl+Shift+M** | Telegram Desktop | Monospace |
| **Ctrl+Shift+N** | Telegram Desktop | Remove formatting / plain text |
| **Ctrl+Shift+P** | Telegram Desktop | Spoiler |
| **Ctrl+Shift+X** | Telegram Desktop | Strikethrough |
| **Ctrl+Shift+Period** | Telegram Desktop | Quote |

### Mouse Shortcuts

| Shortcut | Provided by | Function |
|---|---|---|
| **Double-click a message** | Telegram Desktop | Reply |
| **Drag outside the messages** | Telegram Desktop | Select messages |
| **Hover over the timestamp** | Telegram Desktop | Show message information |
| **Hover over a poll percentage** | Telegram Desktop | Show the number of votes |
| **Drag a message to a chat in the list** | Telegram Desktop | Forward the message to that chat |
| **Back** | Telegram Desktop | Exit Archived Chats |
| **Upload a picture and click its preview** | Telegram Desktop | Edit media |
| **Right-click the Send button** | Telegram Desktop | Send silently or schedule a message |

## Community and Support

* **Official Telegram channel**: [tdesktopnvda](https://t.me/tdesktopnvda)
* **Telegram user group**: [tdesktopnvda_group](https://t.me/tdesktopnvda_group)
* **Source code and issue tracking**: [keyang556/tdesktopnvda](https://github.com/keyang556/tdesktopnvda)
* **Developer contact**: Ken Chang <lindsay714322@gmail.com>

## Supported Versions

* Telegram Desktop for Windows 7.0.1 or later.
* NVDA 2024.1 or later.

## Build From Source

From this repository:

```powershell
uv run scons
```

The generated `.nvda-addon` package can be installed through NVDA's Add-on Store.
