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


def _safeRole(obj: object) -> controlTypes.Role | None:
	try:
		return obj.role
	except (AttributeError, COMError, RuntimeError):
		return None


def _normalizedName(obj: object) -> str:
	try:
		name = obj.name
	except (AttributeError, COMError, RuntimeError):
		return ""
	return (name or "").strip().casefold()


def isTelegramChatListItem(obj: object) -> bool:
	"""Return True for Telegram's chat-list rows exposed as UIA ListItem objects."""
	if not isinstance(obj, UIA) or _safeRole(obj) != controlTypes.Role.LISTITEM:
		return False

	try:
		parent = obj.parent
	except (AttributeError, COMError, RuntimeError):
		return False

	return (
		isinstance(parent, UIA)
		and _safeRole(parent) == controlTypes.Role.LIST
		and _normalizedName(parent) in _CHAT_LIST_CONTAINER_NAMES
	)


class TelegramChatListItem(ListItem):
	"""Avoid Telegram 6.8.x's broken SelectionItemPattern container lookup."""

	def _get_selectionContainer(self) -> None:
		# NVDA only needs this during focus speech to suppress redundant "selected".
		# Telegram's Qt UIA provider can raise COMError here, aborting chat row speech.
		return None


class AppModule(appModuleHandler.AppModule):
	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if ListItem in clsList and isTelegramChatListItem(obj):
			clsList.insert(0, TelegramChatListItem)
