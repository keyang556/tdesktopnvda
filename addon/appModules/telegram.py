# A part of Telegram Desktop Accessibility for NVDA
# Copyright (C) 2026 chang
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""App module for Telegram Desktop."""

from __future__ import annotations

import appModuleHandler
from comtypes import COMError
import controlTypes
from NVDAObjects.UIA import ListItem, UIA


_CHAT_LIST_CONTAINER_NAMES = frozenset(
	{
		"chats",
		"chat list",
		"recent chats",
		"\u804a\u5929\u5ba4",
		"\u804a\u5929",
	}
)

_COUNTRY_SELECT_CONTAINER_NAMES = frozenset(
	{
		"select country",
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


def isTelegramChatListItem(obj: object) -> bool:
	"""Return True for Telegram's chat-list rows exposed as UIA ListItem objects."""
	return _isTelegramListItemInNamedList(obj, _CHAT_LIST_CONTAINER_NAMES)


def isTelegramCountrySelectListItem(obj: object) -> bool:
	"""Return True for Telegram's country selector rows exposed as UIA ListItem objects."""
	return _isTelegramListItemInNamedList(obj, _COUNTRY_SELECT_CONTAINER_NAMES)


class TelegramSelectionContainerSafeListItem(ListItem):
	"""Avoid Telegram 6.8.x's broken SelectionItemPattern container lookup."""

	def _get_selectionContainer(self) -> None:
		# NVDA only needs this during focus speech to suppress redundant "selected".
		# Telegram's Qt UIA provider can raise COMError here, aborting focus speech.
		return None


class TelegramChatListItem(TelegramSelectionContainerSafeListItem):
	"""Chat-list row with safe focus speech."""


class TelegramCountrySelectListItem(TelegramSelectionContainerSafeListItem):
	"""Country selector row with safe focus speech."""


class AppModule(appModuleHandler.AppModule):
	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if ListItem not in clsList:
			return

		if isTelegramChatListItem(obj):
			clsList.insert(0, TelegramChatListItem)
		elif isTelegramCountrySelectListItem(obj):
			clsList.insert(0, TelegramCountrySelectListItem)
