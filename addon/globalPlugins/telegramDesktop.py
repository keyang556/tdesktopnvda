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
import controlTypes
import globalPluginHandler
from scriptHandler import script
import UIAHandler


addonHandler.initTranslation()

_TELEGRAM_APP_NAME = "telegram"
_TELEGRAM_GESTURES = {
	"kb:alt+1": "focusChatList",
	"kb:alt+m": "openMainMenu",
	"kb:control+tab": "switchChat",
	"kb:control+shift+tab": "switchChat",
}
_MAIN_MENU_CLASS_NAMES = {
	"Window::MainMenu": _("Main menu"),
	"Ui::UserpicButton": _("Profile"),
	"Window::MainMenu::ToggleAccountsButton": _("Accounts"),
}
_COMPOSER_AUTOMATION_ID_NAMES = {
	"ButtonStickers": _("Emoji, stickers, and GIFs"),
	"btnVoiceMessage": _("Record voice message"),
}
_TOP_BAR_SUGGESTION_CLASS_NAME = "Dialogs::TopBarSuggestionContent"

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


def _normalizedClassName(obj: object) -> str:
	try:
		className = obj.UIAClassName.strip()
	except Exception:
		return ""
	return className.removeprefix("class ").removeprefix("struct ")


def _automationIdClassNames(automationId: str) -> tuple[str, ...]:
	"""Return Telegram's RTTI class components from a UIA AutomationId."""
	return tuple(
		component.removeprefix("class ").removeprefix("struct ") for component in automationId.split(".")
	)


def _setObjectName(obj: object, name: str) -> None:
	try:
		obj.name = name
	except Exception:
		pass


def _cleanTelegramControlName(obj: object) -> None:
	"""Supply useful names for known Telegram controls before speech."""
	if not _isTelegramObject(obj):
		return
	try:
		automationId = obj.UIAAutomationId
	except Exception:
		return
	try:
		rawName = obj.UIAElement.GetCurrentPropertyValue(UIAHandler.UIA_NamePropertyId)
	except Exception:
		try:
			rawName = obj.UIAElement.CurrentName
		except Exception:
			rawName = ""
	composerFallback = (
		_COMPOSER_AUTOMATION_ID_NAMES.get(automationId) if isinstance(automationId, str) else None
	)
	if composerFallback is not None:
		# Prefer Telegram's provider name because the voice-message control can
		# change modes. Some NVDA object overlays fail to expose that name even
		# though the underlying UIA element still has it.
		_setObjectName(obj, rawName if isinstance(rawName, str) and rawName else composerFallback)
		return
	if isinstance(automationId, str):
		automationClasses = _automationIdClassNames(automationId)
		if _TOP_BAR_SUGGESTION_CLASS_NAME in automationClasses:
			fallback = (
				_("Telegram suggestion")
				if _normalizedClassName(obj) == _TOP_BAR_SUGGESTION_CLASS_NAME
				else _("Dismiss suggestion")
			)
			_setObjectName(obj, rawName if isinstance(rawName, str) and rawName else fallback)
			return
	if rawName or not isinstance(automationId, str) or "Window::MainMenu" not in automationId:
		return

	automationClasses = _automationIdClassNames(automationId)
	name = next(
		(
			_MAIN_MENU_CLASS_NAMES[className]
			for className in reversed(automationClasses)
			if className in _MAIN_MENU_CLASS_NAMES
		),
		None,
	)
	if name is None:
		name = _MAIN_MENU_CLASS_NAMES.get(_normalizedClassName(obj))
	if name is None:
		try:
			role = obj.role
		except Exception:
			role = None
		name = _("Menu item") if role == controlTypes.Role.BUTTON else _("Main menu")
	_setObjectName(obj, name)


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
		self._updateGestureBindings(obj)
		# Labels must be in place before NVDA's focus handler builds speech.
		_cleanTelegramControlName(obj)
		nextHandler()

	def event_focusEntered(self, obj: object, nextHandler: Callable[[], None]) -> None:
		# Menu containers are announced as focus ancestors rather than direct
		# focus targets, so label them on focusEntered as well.
		_cleanTelegramControlName(obj)
		nextHandler()

	@script(description=_("Move focus to chat list"))
	def script_focusChatList(self, gesture: object) -> None:
		_telegramModule.focusChatList()

	@script(description=_("Open main menu"))
	def script_openMainMenu(self, gesture: object) -> None:
		_telegramModule.openMainMenu()

	@script(description=_("Switch chats and announce the chat name"))
	def script_switchChat(self, gesture: object) -> None:
		_telegramModule.switchChat(gesture)
