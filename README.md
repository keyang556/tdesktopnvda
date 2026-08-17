# Telegram Desktop Accessibility

* Author: [Ken Chang](https://t.me/Keyang556)
* [Telegram channel](https://t.me/tdesktopnvda)
* [Telegram user group](https://t.me/tdesktopnvda_group)

## Overview

Telegram Desktop Accessibility is an NVDA add-on for Telegram Desktop on Windows. It adds direct navigation and call commands, and fills missing accessible names on known Telegram controls.

## Features

* `Alt+1` moves focus to the selected chat in the chat list, or to the first chat when no chat is selected.
* `Alt+M` opens Telegram's main menu.
* `Alt+Y`, `Alt+N`, `Alt+A` and `Alt+V` answer a call, decline or end it, mute or unmute the microphone, and turn the camera on or off. Each of them reports the action in Telegram's own wording, so it follows Telegram's display language.
* Every command is listed in NVDA's Input Gestures dialog under "Telegram Desktop Accessibility", so any default shortcut can be reassigned or removed. Outside Telegram the assigned keystroke reaches the application unchanged.
* Structural main-menu controls such as Profile and Accounts, unnamed composer controls, and the top-bar suggestion receive useful accessible labels. A real name supplied by Telegram is always preserved.
* A foreground-aware fallback keeps the shortcuts and labels available when UnigramPlus or another installed add-on claims Telegram's shared app-module slot. It does not bind the shortcuts outside Telegram.
* Chat and call controls are detected through Telegram's stable UIA class information rather than a translated control name, so the commands do not depend on Telegram's interface language.
* Controls that expose only Telegram's internal C++ class path no longer announce that path. Other names from Telegram are not replaced.

## Usage

Install the add-on, restart NVDA when prompted, and use the add-on shortcuts from the main Telegram window. No configuration is required.

If `Alt+1` cannot find a chat list or the list is empty, NVDA reports that condition. If `Alt+M` is unavailable on the current Telegram screen, NVDA reports that the main menu is not available. The call commands report that there is no incoming call, or that you are not in a call, when the matching control is not on screen. A call runs in a window of its own, so the call commands also work while the main Telegram window is in front.

To use different keys, open NVDA menu > Preferences > Input Gestures, expand the "Telegram Desktop Accessibility" category, and add or remove a gesture for any command.

## Keyboard Shortcuts

> In the "Provided by" column, `Add-on` identifies shortcuts provided by this add-on and `Telegram Desktop` identifies shortcuts built into Telegram Desktop.
>
> **Tip:** you can customize the add-on shortcuts from NVDA menu > Preferences > Input Gestures.

### Chats

| Shortcut | Provided by | Function |
|---|---|---|
| **Alt+1** | Add-on | Move focus to the chat list |
| **Up / Down / Page Up / Page Down** | Telegram Desktop | Navigate within a chat |
| **Shift+Scroll** | Telegram Desktop | Speed up in-chat navigation |
| **Up / Left / Right / Down** | Telegram Desktop | Navigate suggested stickers |
| **Left / Right** | Telegram Desktop | Navigate suggested emoji |
| **Ctrl+Tab / Ctrl+Page Down / Alt+Down** | Telegram Desktop | Move to the chat below |
| **Ctrl+Shift+Tab / Ctrl+Page Up / Alt+Up** | Telegram Desktop | Move to the chat above |
| **Esc** | Telegram Desktop | Exit, go back, or cancel the current action |
| **Ctrl+O** | Telegram Desktop | Send a file |

### Calls

| Shortcut | Provided by | Function |
|---|---|---|
| **Alt+Y** | Add-on | Answer the incoming call |
| **Alt+N** | Add-on | Decline the incoming call, or end the call in progress |
| **Alt+A** | Add-on | Mute or unmute the microphone during a call |
| **Alt+V** | Add-on | Turn the camera on or off during a call |

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
| **Alt+M** | Add-on | Open the main menu |
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

## Implementation

Telegram Desktop's patched Qt accessibility provider exposes RTTI-based UIA class names. The add-on identifies the chat list as `Dialogs::InnerWidget`, allowing it to work independently of the localized accessible name. The main menu command finds Telegram's native button by UIA point hit-testing near the top-left corner, supporting both `Dialogs::Widget` and folder-sidebar layouts, then falls back to the existing provider-side subtree query.

Telegram's call panel builds every control as a `Ui::CallButton`, laid out as screen sharing, camera, cancel or decline, answer or hang up, microphone, add people. Only the camera and the microphone carry a device-selection corner button, so the add-on recognizes those two by that corner button and the remaining commands by their place in the row. No translated name is read to find a control; a name is only read back to report the action, because each button is named after what pressing it does.

A global plug-in owns every command and resolves this add-on's app module by its qualified owner, avoiding the shared `appModules/telegram.py` lookup when another add-on wins it. Defining the commands once, in a plug-in that is always running, is what keeps a single reassignable entry per command in NVDA's Input Gestures dialog; each command checks the foreground itself and passes its gesture on when Telegram is not in front.

## Community and Support

* **Official Telegram channel**: [tdesktopnvda](https://t.me/tdesktopnvda)
* **Telegram user group**: [tdesktopnvda_group](https://t.me/tdesktopnvda_group)
* **Source code and issue tracking**: [keyang556/tdesktopnvda](https://github.com/keyang556/tdesktopnvda)
* **Developer contact**: [Ken Chang](https://t.me/Keyang556) <lindsay714322@gmail.com>

## Supported Versions

* Telegram Desktop for Windows 7.0.1 or later.
* NVDA 2024.1 or later.

## Build From Source

From this repository:

```powershell
uv run scons
```

The generated `.nvda-addon` package can be installed through NVDA's Add-on Store.
