# A part of Telegram Desktop Accessibility for NVDA
# Copyright (C) 2026 Ken Chang
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Keep this add-on's commands available when another add-on claims Telegram."""

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
	"kb:control+enter": "showMessageLinks",
	"kb:control+tab": "switchChat",
	"kb:control+shift+tab": "switchChat",
}

# Loading through the owning add-on gives this module a qualified name and
# bypasses the shared appModules search path. That matters when UnigramPlus or
# another add-on also provides appModules/telegram.py.
_telegramModule: ModuleType = addonHandler.getCodeAddon().loadModule("appModules.telegram")
# NVDA reloads global plug-ins without necessarily evicting add-on-owned app
# modules from sys.modules. Refresh this module so newly added or changed
# shortcut helpers are available immediately after Tools -> Reload Add-ons.
_telegramModule = importlib.reload(_telegramModule)


def _isTelegramObject(obj: object) -> bool:
	try:
		return obj.appModule.appName.casefold() == _TELEGRAM_APP_NAME
	except Exception:
		return False


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Bind Telegram commands only while Telegram is the foreground app."""

	def __init__(self) -> None:
		super().__init__()
		self._telegramGesturesAreBound = False
		try:
			foreground = api.getForegroundObject()
		except Exception:
			foreground = None
		self._updateGestureBindings(foreground)

	def _updateGestureBindings(self, obj: object) -> None:
		shouldBind = _isTelegramObject(obj)
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

	def event_foreground(self, obj: object, nextHandler: Callable[[], None]) -> None:
		self._updateGestureBindings(obj)
		nextHandler()

	def event_gainFocus(self, obj: object, nextHandler: Callable[[], None]) -> None:
		# This also covers an already-open Telegram window after global plug-ins
		# are reloaded, and guards against a missed foreground event.
		#
		# The decision is taken from the foreground window rather than from the
		# focused object: a Telegram focus event can arrive late, once another
		# application is already in front, and binding on it would let these
		# shortcuts swallow keys in that application.
		try:
			foreground = api.getForegroundObject()
		except Exception:
			foreground = None
		if foreground is not None:
			self._updateGestureBindings(foreground)
		nextHandler()

	@script(description=_("Move focus to chat list"))
	def script_focusChatList(self, gesture: object) -> None:
		_telegramModule.focusChatList()

	@script(description=_("Open main menu"))
	def script_openMainMenu(self, gesture: object) -> None:
		_telegramModule.openMainMenu()

	@script(description=_("Show links in the current message"))
	def script_showMessageLinks(self, gesture: object) -> None:
		_telegramModule.showMessageLinks(gesture)

	@script(description=_("Switch chats and announce the chat name"))
	def script_switchChat(self, gesture: object) -> None:
		_telegramModule.switchChat(gesture)
