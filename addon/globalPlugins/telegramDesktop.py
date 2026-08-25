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
import ntpath
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
_TELEGRAM_PRODUCT_NAME = "telegram desktop"
_TELEGRAM_EXECUTABLE_NAME = "telegram.exe"
_UNIGRAM_IDENTIFIER = "unigram"

_codeAddon: addonHandler.Addon = addonHandler.getCodeAddon()

# Resolve this add-on's module by its qualified owner, bypassing the shared
# appModules/telegram.py lookup that UnigramPlus or another add-on may win.
_telegramModule: ModuleType = _codeAddon.loadModule("appModules.telegram")
_telegramModule = importlib.reload(_telegramModule)

#: The Input Gestures category these commands are grouped under.
ADDON_SUMMARY: str = cast(str, _codeAddon.manifest["summary"])


def _normalizedAppModuleAttribute(appModule: object, name: str) -> str:
	"""Return a case-insensitive app-module attribute, or an empty value."""
	try:
		return str(getattr(appModule, name, "") or "").casefold()
	except Exception:
		return ""


def _isTelegramObject(obj: object) -> bool:
	"""Return whether *obj* belongs to the official Telegram Desktop process.

	Unigram also registers as ``telegram`` with NVDA.  Do not let that shared
	app name alone grant this global plug-in ownership of its gestures or UIA
	objects: Telegram Desktop's PE metadata identifies the product and its
	executable independently, without traversing the UIA tree.
	"""
	try:
		appModule = obj.appModule
	except Exception:
		return False

	if _normalizedAppModuleAttribute(appModule, "appName") != _TELEGRAM_APP_NAME:
		return False

	productName = _normalizedAppModuleAttribute(appModule, "productName")
	appPath = _normalizedAppModuleAttribute(appModule, "appPath")
	if _UNIGRAM_IDENTIFIER in productName or _UNIGRAM_IDENTIFIER in appPath:
		return False

	return (
		productName == _TELEGRAM_PRODUCT_NAME
		and ntpath.basename(appPath) == _TELEGRAM_EXECUTABLE_NAME
	)


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

	def getScript(self, gesture: "inputCore.InputGesture") -> object | None:
		"""Only claim built-in gestures while Telegram Desktop is foreground.

		Calling ``gesture.send()`` after this plug-in has won lookup only forwards
		the key to Windows; it does not restart NVDA's script lookup for an app
		module such as UnigramPlus.  Returning ``None`` here lets NVDA continue to
		that app module naturally.  The checks inside each command remain needed
		for user gesture-map assignments, which NVDA resolves before this method.
		"""
		if not _telegramIsInForeground():
			return None
		return super().getScript(gesture)

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

	@script(
		# Translators: The description of a command to accept an incoming Telegram call.
		description=_("Answer the incoming call"),
		gesture="kb:alt+y",
	)
	def script_answerCall(self, gesture: "inputCore.InputGesture") -> None:
		if not _telegramIsInForeground():
			_passGestureToApplication(gesture)
			return
		_telegramModule.answerCall()

	@script(
		# Translators: The description of a command to hang up a Telegram call.
		description=_("Decline the incoming call, or end the call in progress"),
		gesture="kb:alt+n",
	)
	def script_endCall(self, gesture: "inputCore.InputGesture") -> None:
		if not _telegramIsInForeground():
			_passGestureToApplication(gesture)
			return
		_telegramModule.endCall()

	@script(
		# Translators: The description of a command to toggle the microphone in a Telegram call.
		description=_("Mute or unmute the microphone during a call"),
		gesture="kb:alt+a",
	)
	def script_toggleCallMicrophone(self, gesture: "inputCore.InputGesture") -> None:
		if not _telegramIsInForeground():
			_passGestureToApplication(gesture)
			return
		_telegramModule.toggleCallMicrophone()

	@script(
		# Translators: The description of a command to toggle the camera in a Telegram call.
		description=_("Turn the camera on or off during a call"),
		gesture="kb:alt+v",
	)
	def script_toggleCallCamera(self, gesture: "inputCore.InputGesture") -> None:
		if not _telegramIsInForeground():
			_passGestureToApplication(gesture)
			return
		_telegramModule.toggleCallCamera()
