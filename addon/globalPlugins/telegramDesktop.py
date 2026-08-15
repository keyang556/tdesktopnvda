# A part of Telegram Desktop Accessibility for NVDA
# Copyright (C) 2026 Ken Chang
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""This add-on's user-assignable Telegram commands.

The commands live in a global plug-in rather than in the app module for two
reasons. NVDA offers an app module's commands in the Input Gestures dialog only
when the dialog was opened from that application, and it drops them entirely
when UnigramPlus or another add-on wins the shared ``appModules/telegram.py``
lookup. A global plug-in is always running, so NVDA always lists these commands
and the user can always reassign them.
"""

from __future__ import annotations

from collections.abc import Callable
import importlib
from types import ModuleType
from typing import TYPE_CHECKING, cast

import addonHandler
import api
import globalPluginHandler
from logHandler import log
from scriptHandler import script


if TYPE_CHECKING:
	import inputCore


addonHandler.initTranslation()

_TELEGRAM_APP_NAME = "telegram"

_codeAddon: addonHandler.Addon = addonHandler.getCodeAddon()

# Resolve this add-on's module by its qualified owner, bypassing the shared
# appModules/telegram.py lookup that UnigramPlus or another add-on may win.
_telegramModule: ModuleType = _codeAddon.loadModule("appModules.telegram")
_telegramModule = importlib.reload(_telegramModule)

#: The Input Gestures category these commands are grouped under.
ADDON_SUMMARY: str = cast(str, _codeAddon.manifest["summary"])


def _isTelegramObject(obj: object) -> bool:
	try:
		return obj.appModule.appName.casefold() == _TELEGRAM_APP_NAME
	except Exception:
		return False


def _foregroundObject() -> object | None:
	try:
		return api.getForegroundObject()
	except Exception:
		return None


def _telegramIsInForeground() -> bool:
	"""Return whether Telegram owns the foreground, failing closed if unreadable."""
	return _isTelegramObject(_foregroundObject())


def _passGestureToApplication(gesture: "inputCore.InputGesture") -> None:
	"""Let the focused application receive a gesture this add-on will not act on.

	These commands are bound globally so that NVDA can list them in the Input
	Gestures dialog at any time. Outside Telegram they must therefore behave as
	if the add-on had never claimed the keystroke.
	"""
	try:
		gesture.send()
	except Exception:
		# Only keyboard gestures can be sent on to the application.
		log.debugWarning("Telegram command could not pass its gesture through", exc_info=True)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Own this add-on's commands so NVDA can reassign them at any time."""

	scriptCategory = ADDON_SUMMARY

	def _cleanControlName(self, obj: object) -> None:
		if _isTelegramObject(obj):
			_telegramModule._cleanTelegramControlName(obj)

	def event_gainFocus(self, obj: object, nextHandler: Callable[[], None]) -> None:
		self._cleanControlName(obj)
		nextHandler()

	def event_focusEntered(self, obj: object, nextHandler: Callable[[], None]) -> None:
		self._cleanControlName(obj)
		nextHandler()

	@script(
		# Translators: The description of a command to move focus to Telegram's chat list.
		description=_("Move focus to chat list"),
		gesture="kb:alt+1",
	)
	def script_focusChatList(self, gesture: "inputCore.InputGesture") -> None:
		# NVDA resolves a user-assigned gesture from its own gesture map, which
		# ignores per-instance bindings. The foreground test therefore belongs
		# here, so a reassigned command still cannot act outside Telegram.
		if not _telegramIsInForeground():
			_passGestureToApplication(gesture)
			return
		_telegramModule.focusChatList()

	@script(
		# Translators: The description of a command to open Telegram's main menu.
		description=_("Open main menu"),
		gesture="kb:alt+m",
	)
	def script_openMainMenu(self, gesture: "inputCore.InputGesture") -> None:
		if not _telegramIsInForeground():
			_passGestureToApplication(gesture)
			return
		_telegramModule.openMainMenu()
