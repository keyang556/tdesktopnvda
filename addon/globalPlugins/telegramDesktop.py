# A part of Telegram Desktop Accessibility for NVDA
# Copyright (C) 2026 Ken Chang
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Keep this add-on active when another add-on claims Telegram's app module."""

from __future__ import annotations

from collections.abc import Callable
import importlib
from types import ModuleType

import addonHandler
import api
import globalPluginHandler
from scriptHandler import script


addonHandler.initTranslation()

_TELEGRAM_APP_NAME = "telegram"
_TELEGRAM_GESTURES = {
	"kb:alt+1": "focusChatList",
	"kb:alt+m": "openMainMenu",
}

# Resolve this add-on's module by its qualified owner, bypassing the shared
# appModules/telegram.py lookup that UnigramPlus or another add-on may win.
_telegramModule: ModuleType = addonHandler.getCodeAddon().loadModule("appModules.telegram")
_telegramModule = importlib.reload(_telegramModule)


def _isTelegramObject(obj: object) -> bool:
	try:
		return obj.appModule.appName.casefold() == _TELEGRAM_APP_NAME
	except Exception:
		return False


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Bind this add-on's two commands only while Telegram is foreground."""

	def __init__(self) -> None:
		super().__init__()
		self._telegramGesturesAreBound = False
		self._updateGestureBindings(self._foregroundObject())

	@staticmethod
	def _foregroundObject() -> object | None:
		try:
			return api.getForegroundObject()
		except Exception:
			return None

	def _updateGestureBindings(self, obj: object | None) -> None:
		shouldBind = obj is not None and _isTelegramObject(obj)
		if shouldBind == self._telegramGesturesAreBound:
			return
		if shouldBind:
			self.bindGestures(_TELEGRAM_GESTURES)
		else:
			for gesture in _TELEGRAM_GESTURES:
				try:
					self.removeGestureBinding(gesture)
				except LookupError:
					pass
		self._telegramGesturesAreBound = shouldBind

	def _cleanControlName(self, obj: object) -> None:
		if _isTelegramObject(obj):
			_telegramModule._cleanTelegramControlName(obj)

	def event_foreground(self, obj: object, nextHandler: Callable[[], None]) -> None:
		self._updateGestureBindings(obj)
		nextHandler()

	def event_gainFocus(self, obj: object, nextHandler: Callable[[], None]) -> None:
		# Focus events may arrive after another application takes focus. Decide
		# bindings from the actual foreground and fail closed if it is unreadable.
		self._updateGestureBindings(self._foregroundObject())
		self._cleanControlName(obj)
		nextHandler()

	def event_focusEntered(self, obj: object, nextHandler: Callable[[], None]) -> None:
		self._cleanControlName(obj)
		nextHandler()

	@script(description=_("Move focus to chat list"))
	def script_focusChatList(self, gesture: object) -> None:
		_telegramModule.focusChatList()

	@script(description=_("Open main menu"))
	def script_openMainMenu(self, gesture: object) -> None:
		_telegramModule.openMainMenu()
