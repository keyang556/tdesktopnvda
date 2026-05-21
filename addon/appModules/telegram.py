# A part of Telegram Desktop Accessibility for NVDA
# Copyright (C) 2026 chang
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""App module for Telegram Desktop."""

from __future__ import annotations

import api
import appModuleHandler
from comtypes import COMError
import controlTypes
from keyboardHandler import KeyboardInputGesture
from NVDAObjects.UIA import ListItem, UIA


_CHAT_LIST_FORWARD_TAB_ENTRY_BUTTON_NAMES = frozenset(
	{
		"edit",
		"\u0438\u0437\u043c\u0435\u043d\u0438\u0442\u044c",
		"\u0440\u0435\u0434\u0430\u043a\u0442\u0438\u0440\u043e\u0432\u0430\u0442\u044c",
		"\u7de8\u8f2f",
		"\u7f16\u8f91",
	}
)

_CHAT_LIST_CONTAINER_NAMES = frozenset(
	{
		"chats",
		"chat list",
		"recent chats",
		"\u0447\u0430\u0442\u044b",
		"\u043d\u0435\u0434\u0430\u0432\u043d\u0438\u0435 \u0447\u0430\u0442\u044b",
		"\u804a\u5929\u5ba4",
		"\u804a\u5929",
	}
)

_MESSAGE_LIST_CONTAINER_NAMES = frozenset(
	{
		"messages",
		"message list",
		"\u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f",
		"\u8a0a\u606f",
		"\u6d88\u606f",
	}
)

_COUNTRY_SELECT_CONTAINER_NAMES = frozenset(
	{
		"select country",
		"\u0432\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0441\u0442\u0440\u0430\u043d\u0443",
		"\u0432\u044b\u0431\u043e\u0440 \u0441\u0442\u0440\u0430\u043d\u044b",
		"\u9078\u64c7\u570b\u5bb6",
		"\u9009\u62e9\u56fd\u5bb6",
	}
)


def _safeRole(obj: object) -> controlTypes.Role | None:
	try:
		return obj.role
	except (AttributeError, COMError, RuntimeError):
		return None


def _safeParent(obj: object) -> object | None:
	try:
		return obj.parent
	except (AttributeError, COMError, RuntimeError):
		return None


def _normalizedName(obj: object) -> str:
	try:
		name = obj.name
	except (AttributeError, COMError, RuntimeError):
		return ""
	return (name or "").strip().casefold()


def _sendKeyboardGesture(name: str) -> bool:
	try:
		KeyboardInputGesture.fromName(name).send()
	except Exception:
		return False
	return True


def _isTelegramListItemInNamedList(obj: object, containerNames: frozenset[str]) -> bool:
	if not isinstance(obj, UIA) or _safeRole(obj) != controlTypes.Role.LISTITEM:
		return False

	parent = _safeParent(obj)
	if not isinstance(parent, UIA):
		return False

	return (
		_safeRole(parent) == controlTypes.Role.LIST
		and _normalizedName(parent) in containerNames
	)


def _isTelegramNamedList(obj: object, containerNames: frozenset[str]) -> bool:
	return (
		isinstance(obj, UIA)
		and _safeRole(obj) == controlTypes.Role.LIST
		and _normalizedName(obj) in containerNames
	)


def isTelegramChatListForwardTabEntryPoint(obj: object) -> bool:
	"""Return True for the button just before Telegram's chat list in reverse Tab order."""
	return (
		isinstance(obj, UIA)
		and _safeRole(obj) == controlTypes.Role.BUTTON
		and _normalizedName(obj) in _CHAT_LIST_FORWARD_TAB_ENTRY_BUTTON_NAMES
	)


def isTelegramChatList(obj: object) -> bool:
	"""Return True for Telegram's chat-list container exposed as a UIA List."""
	return _isTelegramNamedList(obj, _CHAT_LIST_CONTAINER_NAMES)


def isTelegramMessageList(obj: object) -> bool:
	"""Return True for Telegram's message-list container exposed as a UIA List."""
	return _isTelegramNamedList(obj, _MESSAGE_LIST_CONTAINER_NAMES)


def isTelegramChatListItem(obj: object) -> bool:
	"""Return True for Telegram's chat-list rows exposed as UIA ListItem objects."""
	return _isTelegramListItemInNamedList(obj, _CHAT_LIST_CONTAINER_NAMES)


def isTelegramMessageListItem(obj: object) -> bool:
	"""Return True for Telegram's message-list rows exposed as UIA ListItem objects."""
	return _isTelegramListItemInNamedList(obj, _MESSAGE_LIST_CONTAINER_NAMES)


def isTelegramCountrySelectListItem(obj: object) -> bool:
	"""Return True for Telegram's country selector rows exposed as UIA ListItem objects."""
	return _isTelegramListItemInNamedList(obj, _COUNTRY_SELECT_CONTAINER_NAMES)


class TelegramFocusableList(UIA):
	"""Restore NVDA focusability for Telegram 6.8.3 list containers."""

	def _get_states(self) -> set[controlTypes.State]:
		try:
			baseStates = super()._get_states()
		except (AttributeError, COMError, RuntimeError):
			states = set()
		else:
			states = set(baseStates or ())
		states.add(controlTypes.State.FOCUSABLE)
		return states


class TelegramChatList(TelegramFocusableList):
	"""Chat-list container reachable with Tab."""


class TelegramMessageList(TelegramFocusableList):
	"""Message-list container reachable with Tab."""


class TelegramSelectionContainerSafeListItem(ListItem):
	"""Avoid Telegram 6.8.3+'s broken SelectionItemPattern container lookup."""

	def _get_selectionContainer(self) -> None:
		# NVDA only needs this during focus speech to suppress redundant "selected".
		# Telegram's Qt UIA provider can raise COMError here, aborting focus speech.
		return None


class TelegramChatListItem(TelegramSelectionContainerSafeListItem):
	"""Chat-list row with safe focus speech."""


class TelegramMessageListItem(TelegramSelectionContainerSafeListItem):
	"""Message-list row with safe focus speech."""


class TelegramCountrySelectListItem(TelegramSelectionContainerSafeListItem):
	"""Country selector row with safe focus speech."""


class AppModule(appModuleHandler.AppModule):
	_chatListTabEntryReachedFromChatList = False
	_lastFocusWasChatList = False

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if isTelegramChatList(obj):
			clsList.insert(0, TelegramChatList)
		elif isTelegramMessageList(obj):
			clsList.insert(0, TelegramMessageList)

		if ListItem in clsList:
			if isTelegramChatListItem(obj):
				clsList.insert(0, TelegramChatListItem)
			elif isTelegramMessageListItem(obj):
				clsList.insert(0, TelegramMessageListItem)
			elif isTelegramCountrySelectListItem(obj):
				clsList.insert(0, TelegramCountrySelectListItem)

	def event_gainFocus(self, obj, nextHandler):
		lastFocusWasChatList = getattr(self, "_lastFocusWasChatList", False)
		self._chatListTabEntryReachedFromChatList = (
			lastFocusWasChatList and isTelegramChatListForwardTabEntryPoint(obj)
		)
		self._lastFocusWasChatList = isTelegramChatList(obj) or isTelegramChatListItem(obj)
		nextHandler()

	def script_tab(self, gesture):
		try:
			focus = api.getFocusObject()
		except Exception:
			focus = None

		if isTelegramChatListForwardTabEntryPoint(focus):
			if not getattr(self, "_chatListTabEntryReachedFromChatList", False):
				# Telegram 6.8.3 skips the chat list in forward Tab order, while Shift+Tab reaches it.
				if _sendKeyboardGesture("shift+tab"):
					return
			self._chatListTabEntryReachedFromChatList = False

		gesture.send()

	__gestures = {
		"kb:tab": "tab",
	}
