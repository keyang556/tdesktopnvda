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
import UIAHandler


addonHandler.initTranslation()

_TELEGRAM_APP_NAME = "telegram"
_TELEGRAM_GESTURES = {
	"kb:alt+1": "focusChatList",
	"kb:alt+m": "openMainMenu",
	"kb:control+enter": "showMessageLinks",
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
_MAIN_MENU_CLASS_NAME = "Window::MainMenu"
_RTTI_CLASS_PREFIXES = ("class ", "struct ")
# The suggestion strip keeps its wording in child labels, so a small bounded
# walk is enough to read it without touching the whole chat window.
_MAX_SUGGESTION_TEXT_NODES = 24
_MAX_SUGGESTION_TEXT_DEPTH = 4

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


def _safeStringAttribute(obj: object, attribute: str) -> str:
	try:
		value = getattr(obj, attribute)
	except Exception:
		return ""
	return value if isinstance(value, str) else ""


def _normalizedClassName(obj: object) -> str:
	className = _safeStringAttribute(obj, "UIAClassName").strip()
	return className.removeprefix("class ").removeprefix("struct ")


def _isRttiClassChain(value: str) -> bool:
	"""Report whether a string is nothing but Telegram's RTTI class path.

	A widget Telegram never named can reach NVDA carrying its C++ class chain,
	such as ``class MainWindow.class Dialogs::TopBarSuggestionContent``. That is
	a placeholder rather than a name, so it must not block a real label.
	"""
	if not value:
		return False
	return all(_isRttiClassComponent(component) for component in value.split("."))


def _isRttiClassComponent(component: str) -> bool:
	component = component.strip()
	for prefix in _RTTI_CLASS_PREFIXES:
		if component.startswith(prefix):
			# A C++ type name carries no spaces, which keeps ordinary wording
			# such as "class of 99" from being mistaken for a class chain.
			bareName = component[len(prefix) :]
			return bool(bareName) and not any(character.isspace() for character in bareName)
	return False


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


def _providerName(obj: object) -> str:
	"""Return the name Telegram's UIA provider exposes, if it is a real one.

	The underlying element is read rather than the NVDA object because the
	voice-message button changes modes and some NVDA overlays drop the provider
	name. An RTTI class chain is discarded: it means Telegram named nothing.
	"""
	try:
		rawName = obj.UIAElement.GetCurrentPropertyValue(UIAHandler.UIA_NamePropertyId)
	except Exception:
		try:
			rawName = obj.UIAElement.CurrentName
		except Exception:
			rawName = ""
	if not isinstance(rawName, str):
		return ""
	rawName = rawName.strip()
	return "" if _isRttiClassChain(rawName) else rawName


def _childObjects(obj: object) -> tuple[object, ...]:
	try:
		children = obj.children
	except Exception:
		return ()
	return tuple(children) if children else ()


def _suggestionText(obj: object) -> str:
	"""Read the suggestion strip's wording out of its descendant labels."""
	parts: list[str] = []
	seen: set[str] = set()
	pending: list[tuple[object, int]] = [(obj, 0)]
	visited = 0
	while pending and visited < _MAX_SUGGESTION_TEXT_NODES:
		node, depth = pending.pop(0)
		visited += 1
		if node is not obj:
			text = _safeStringAttribute(node, "name").strip()
			if text and not _isRttiClassChain(text) and text.casefold() not in seen:
				seen.add(text.casefold())
				parts.append(text)
		if depth < _MAX_SUGGESTION_TEXT_DEPTH:
			pending.extend((child, depth + 1) for child in _childObjects(node))
	return ", ".join(parts)


def _ownClassName(obj: object, automationClasses: tuple[str, ...]) -> str:
	"""Return the control's own Telegram class, not one of its ancestors'.

	The AutomationId is a chain running from the window down to the control, so
	its last component is the control itself.
	"""
	return _normalizedClassName(obj) or (automationClasses[-1] if automationClasses else "")


def _mainMenuName(obj: object, automationClasses: tuple[str, ...]) -> str | None:
	"""Name the main menu's own unnamed controls, and nothing else.

	Matching on the object's own class rather than anywhere in its ancestry
	matters: opening the menu puts eight nested containers in the focus
	ancestry, and naming every one of them made NVDA announce "Main menu" once
	per level on each Tab. Everything else in the menu Telegram names itself.
	"""
	return _MAIN_MENU_CLASS_NAMES.get(_ownClassName(obj, automationClasses))


def _cleanTelegramControlName(obj: object) -> None:
	"""Supply useful names for known Telegram controls before speech."""
	if not _isTelegramObject(obj):
		return
	try:
		automationId = obj.UIAAutomationId
	except Exception:
		return
	if not isinstance(automationId, str):
		automationId = ""
	providerName = _providerName(obj)
	# A name Telegram really provides always wins; the add-on only fills gaps.
	composerFallback = _COMPOSER_AUTOMATION_ID_NAMES.get(automationId)
	if composerFallback is not None:
		_setObjectName(obj, providerName or composerFallback)
		return
	automationClasses = _automationIdClassNames(automationId)
	if _TOP_BAR_SUGGESTION_CLASS_NAME in automationClasses:
		if _ownClassName(obj, automationClasses) == _TOP_BAR_SUGGESTION_CLASS_NAME:
			# The strip carries its wording in child labels, so read that rather
			# than announcing a generic placeholder.
			fallback = _suggestionText(obj) or _("Telegram suggestion")
		else:
			fallback = _("Dismiss suggestion")
		_setObjectName(obj, providerName or fallback)
		return
	if providerName:
		# Some NVDA overlays expose an empty cached name even though Telegram's
		# underlying UIA element has a useful one. Preserve that provider name on
		# the object before focus speech is built.
		_setObjectName(obj, providerName)
		return
	mainMenuName = _mainMenuName(obj, automationClasses)
	if mainMenuName is not None:
		_setObjectName(obj, mainMenuName)
		return
	if _isRttiClassChain(_safeStringAttribute(obj, "name").strip()):
		# Nothing better to offer, but NVDA should say "button" rather than
		# spell out a C++ class path.
		_setObjectName(obj, "")


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
		# Fail closed if NVDA cannot identify the foreground application: leaving
		# Telegram's global shortcuts bound could swallow those keys elsewhere.
		self._updateGestureBindings(foreground)
		# Labels must be in place before NVDA's focus handler builds speech.
		# This runs whatever the foreground turned out to be, because naming a
		# Telegram control is safe regardless of which window is in front.
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

	@script(description=_("Show links in the current message"))
	def script_showMessageLinks(self, gesture: object) -> None:
		_telegramModule.showMessageLinks(gesture)

	@script(description=_("Switch chats and announce the chat name"))
	def script_switchChat(self, gesture: object) -> None:
		_telegramModule.switchChat(gesture)
