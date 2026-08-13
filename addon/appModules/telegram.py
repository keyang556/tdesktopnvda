# A part of Telegram Desktop Accessibility for NVDA
# Copyright (C) 2026 Ken Chang
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""App module for Telegram Desktop."""

from __future__ import annotations

import os
import re
from typing import Any, cast

import api
import appModuleHandler
import controlTypes
import core
from logHandler import log
from NVDAObjects.UIA import UIA
from scriptHandler import script
import ui
import UIAHandler


_CHAT_LIST_CLASS_NAME = "Dialogs::InnerWidget"
_DIALOGS_WIDGET_CLASS_NAME = "Dialogs::Widget"
_ICON_BUTTON_CLASS_NAME = "Ui::IconButton"
_SIDEBAR_BUTTON_CLASS_NAME = "Ui::SideBarButton"
_HISTORY_LIST_CLASS_NAME = "HistoryView::ListWidget"
_HISTORY_INNER_CLASS_NAME = "HistoryInner"
_MESSAGE_LIST_AUTOMATION_ID = "ChatsList"
_RTTI_CLASS_PREFIXES = ("class ", "struct ")
_MAX_UIA_PARENT_STEPS = 16
_LINK_PATTERN = re.compile(
	r"(?P<uri>(?:(?:https?|ftp|tg|tonsite)://|mailto:)[^\s<>\u200e\u200f]+)"
	r"|(?P<www>www\.[^\s<>\u200e\u200f]+)"
	r"|(?P<email>(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+)",
	re.IGNORECASE,
)
_URL_TRAILING_PUNCTUATION = ".,;:!?\"'\u2026"
_messageLinksDialog: Any | None = None


def _safeStringAttribute(obj: object, attribute: str) -> str:
	try:
		value = getattr(obj, attribute)
	except Exception:
		return ""
	return value if isinstance(value, str) else ""


def _normalizedClassName(obj: object) -> str:
	"""Return a Windows RTTI class name without its MSVC ``class`` prefix."""
	value = _safeStringAttribute(obj, "UIAClassName").strip()
	for prefix in _RTTI_CLASS_PREFIXES:
		if value.startswith(prefix):
			return value[len(prefix) :]
	return value


def _automationIdContainsClass(obj: object, className: str) -> bool:
	"""Check one component of Telegram's RTTI-based UIA AutomationId chain."""
	value = _safeStringAttribute(obj, "UIAAutomationId")
	return any(
		component.removeprefix("class ").removeprefix("struct ") == className
		for component in value.split(".")
	)


def _safeRole(obj: object) -> controlTypes.Role | None:
	try:
		role = getattr(obj, "role")
	except Exception:
		return None
	return role if isinstance(role, controlTypes.Role) else None


def _safeStates(obj: object) -> frozenset[controlTypes.State]:
	try:
		states = getattr(obj, "states")
		return frozenset(state for state in states if isinstance(state, controlTypes.State))
	except Exception:
		return frozenset()


def isTelegramChatList(obj: object) -> bool:
	"""Return True for Telegram's chat list, independent of display language."""
	return (
		isinstance(obj, UIA)
		and _safeRole(obj) == controlTypes.Role.LIST
		and _normalizedClassName(obj) == _CHAT_LIST_CLASS_NAME
	)


def isTelegramMainMenuButton(obj: object) -> bool:
	"""Return True for the main menu button in Telegram's dialogs widget."""
	if not isinstance(obj, UIA) or _normalizedClassName(obj) != _ICON_BUTTON_CLASS_NAME:
		return False
	if not _automationIdContainsClass(obj, _DIALOGS_WIDGET_CLASS_NAME):
		return False

	role = _safeRole(obj)
	menuRoles = {
		getattr(controlTypes.Role, "MENUBUTTON", None),
		getattr(controlTypes.Role, "DROPDOWNBUTTON", None),
	}
	if role in menuRoles - {None}:
		return True

	# Some UIA provider versions expose QAccessible::ButtonMenu as a regular
	# button with the has-popup state instead of NVDA's menu-button role.
	hasPopupState = getattr(controlTypes.State, "HASPOPUP", None)
	return (
		role == controlTypes.Role.BUTTON and hasPopupState is not None and hasPopupState in _safeStates(obj)
	)


def isTelegramMessage(obj: object) -> bool:
	"""Return True for a focused message row in supported Telegram clients."""
	if _safeRole(obj) != controlTypes.Role.LISTITEM:
		return False
	ancestor = obj
	seen: set[int] = set()
	for _step in range(_MAX_UIA_PARENT_STEPS):
		try:
			ancestor = getattr(ancestor, "parent")
		except Exception:
			return False
		if ancestor is None or id(ancestor) in seen:
			return False
		seen.add(id(ancestor))
		automationId = _safeStringAttribute(ancestor, "UIAAutomationId")
		className = _normalizedClassName(ancestor)
		if (
			automationId == _MESSAGE_LIST_AUTOMATION_ID
			or className == _HISTORY_LIST_CLASS_NAME
			or _automationIdContainsClass(ancestor, _HISTORY_INNER_CLASS_NAME)
		):
			return True
	return False


def _stripTrailingUrlPunctuation(value: str) -> str:
	"""Remove sentence punctuation without damaging balanced URL brackets."""
	value = value.rstrip(_URL_TRAILING_PUNCTUATION)
	for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
		while value.endswith(closing) and value.count(closing) > value.count(opening):
			value = value[:-1]
	return value


def linksFromMessageText(text: str) -> tuple[str, ...]:
	"""Extract unique, openable links from a message in reading order."""
	links: list[str] = []
	seen: set[str] = set()
	for match in _LINK_PATTERN.finditer(text):
		value = _stripTrailingUrlPunctuation(match.group(0))
		if not value:
			continue
		if match.lastgroup == "www":
			value = f"https://{value}"
		elif match.lastgroup == "email":
			value = f"mailto:{value}"
		key = value.casefold()
		if key not in seen:
			seen.add(key)
			links.append(value)
	return tuple(links)


def _uiaElement(obj: object) -> Any | None:
	"""Return the raw UIA element for an NVDA object without walking its children."""
	try:
		return getattr(obj, "UIAElement")
	except Exception:
		return None


def _uiaHandler() -> Any:
	"""Return NVDA's initialized UIA handler with its runtime-only members."""
	return cast(Any, UIAHandler.handler)


def _propertyCondition(client: Any, propertyId: int, value: object) -> Any:
	return client.CreatePropertyCondition(propertyId, value)


def _rttiClassCondition(client: Any, className: str) -> Any:
	"""Match both Qt's current class name and its MSVC RTTI variants."""
	conditions = [
		_propertyCondition(client, UIAHandler.UIA_ClassNamePropertyId, candidate)
		for candidate in (className, f"class {className}", f"struct {className}")
	]
	return client.CreateOrConditionFromArray(conditions)


def _findFirstElement(element: Any, scope: int, conditions: list[Any]) -> Any | None:
	"""Run one provider-side UIA query instead of expanding NVDA objects recursively."""
	try:
		handler = _uiaHandler()
		client: Any = handler.clientObject
		condition = conditions[0] if len(conditions) == 1 else client.CreateAndConditionFromArray(conditions)
		return element.FindFirstBuildCache(
			scope,
			condition,
			handler.baseCacheRequest,
		)
	except Exception:
		return None


def _findTelegramChatList(root: object) -> Any | None:
	element = _uiaElement(root)
	if element is None:
		return None
	try:
		client: Any = _uiaHandler().clientObject
		conditions = [
			_rttiClassCondition(client, _CHAT_LIST_CLASS_NAME),
			_propertyCondition(
				client,
				UIAHandler.UIA_ControlTypePropertyId,
				UIAHandler.UIA_ListControlTypeId,
			),
			_propertyCondition(client, UIAHandler.UIA_IsOffscreenPropertyId, False),
		]
	except Exception:
		return None
	return _findFirstElement(element, UIAHandler.TreeScope_Subtree, conditions)


def _rawElementProperty(element: Any, propertyId: int) -> object | None:
	try:
		return element.GetCurrentPropertyValue(propertyId)
	except Exception:
		return None


def _findChatListItem(chatList: Any) -> Any | None:
	"""Prefer the selected chat row, then the first direct chat-list item."""
	try:
		client: Any = _uiaHandler().clientObject
		itemCondition = _propertyCondition(
			client,
			UIAHandler.UIA_ControlTypePropertyId,
			UIAHandler.UIA_ListItemControlTypeId,
		)
		selectedCondition = _propertyCondition(
			client,
			UIAHandler.UIA_SelectionItemIsSelectedPropertyId,
			True,
		)
	except Exception:
		return None
	selected = _findFirstElement(
		chatList,
		UIAHandler.TreeScope_Children,
		[itemCondition, selectedCondition],
	)
	if selected is not None:
		return selected
	return _findFirstElement(
		chatList,
		UIAHandler.TreeScope_Children,
		[itemCondition],
	)


def _findVisibleButtonByClass(
	element: Any,
	className: str,
	*,
	requireDialogsWidget: bool,
) -> Any | None:
	try:
		client: Any = _uiaHandler().clientObject
		conditions = [
			_rttiClassCondition(client, className),
			_propertyCondition(
				client,
				UIAHandler.UIA_ControlTypePropertyId,
				UIAHandler.UIA_ButtonControlTypeId,
			),
			_propertyCondition(client, UIAHandler.UIA_IsOffscreenPropertyId, False),
		]
		if requireDialogsWidget:
			conditions.append(
				client.CreatePropertyConditionEx(
					UIAHandler.UIA_AutomationIdPropertyId,
					_DIALOGS_WIDGET_CLASS_NAME,
					UIAHandler.PropertyConditionFlags_MatchSubstring,
				),
			)
	except Exception:
		return None
	return _findFirstElement(element, UIAHandler.TreeScope_Subtree, conditions)


def _findTelegramMainMenuButton(root: object) -> Any | None:
	"""Find Telegram's main-menu button in either supported left-pane layout.

	When the folder sidebar is visible, Telegram hides the dialogs icon button
	and exposes the menu as the first ``Ui::SideBarButton``. Without that
	sidebar, the menu is the first visible ``Ui::IconButton`` in
	``Dialogs::Widget``. Qt maps both menu and ordinary buttons to the same UIA
	control type, so the concrete Telegram class and provider order are needed.
	"""
	element = _uiaElement(root)
	if element is None:
		return None
	sidebarButton = _findVisibleButtonByClass(
		element,
		_SIDEBAR_BUTTON_CLASS_NAME,
		requireDialogsWidget=False,
	)
	if sidebarButton is not None:
		return sidebarButton
	return _findVisibleButtonByClass(
		element,
		_ICON_BUTTON_CLASS_NAME,
		requireDialogsWidget=True,
	)


def _sameUIAElement(left: Any, right: Any) -> bool:
	if left is None or right is None:
		return False
	try:
		client: Any = _uiaHandler().clientObject
		return bool(client.CompareElements(left, right))
	except Exception:
		return False


def _elementName(element: Any) -> str:
	try:
		value = element.cachedName
	except Exception:
		try:
			value = element.GetCurrentPropertyValue(UIAHandler.UIA_NamePropertyId)
		except Exception:
			return ""
	return value if isinstance(value, str) else ""


def _setElementFocus(element: Any) -> bool:
	try:
		element.SetFocus()
		return True
	except Exception:
		return False


def _invokeElement(element: Any) -> bool:
	try:
		unknown = element.GetCurrentPattern(UIAHandler.UIA_InvokePatternId)
		pattern = unknown.QueryInterface(UIAHandler.IUIAutomationInvokePattern)
		pattern.Invoke()
		return True
	except Exception:
		return False


def _foregroundObject() -> object | None:
	try:
		return api.getForegroundObject()
	except Exception:
		return None


def _focusObject() -> object | None:
	try:
		return api.getFocusObject()
	except Exception:
		return None


class AppModule(appModuleHandler.AppModule):
	@script(description=_("Move focus to chat list"), gesture="kb:alt+1")
	def script_focusChatList(self, gesture: object) -> None:
		root = _foregroundObject()
		chatList = _findTelegramChatList(root) if root is not None else None
		if chatList is None:
			ui.message(_("Chat list not found"))
			return

		target = _findChatListItem(chatList)
		if target is None:
			ui.message(_("Chat list is empty"))
			return

		if _sameUIAElement(target, _uiaElement(_focusObject())):
			name = _elementName(target)
			if name:
				ui.message(name)
			return
		if not _setElementFocus(target):
			ui.message(_("Chat list not found"))

	@script(description=_("Open main menu"), gesture="kb:alt+m")
	def script_openMainMenu(self, gesture: object) -> None:
		root = _foregroundObject()
		button = _findTelegramMainMenuButton(root) if root is not None else None
		if button is None:
			ui.message(_("Main menu is not available"))
			return
		if not _invokeElement(button):
			ui.message(_("Main menu is not available"))

	@script(description=_("Show links in the current message"), gesture="kb:control+enter")
	def script_showMessageLinks(self, gesture: object) -> None:
		showMessageLinks(gesture)


def _openMessageLink(url: str) -> None:
	"""Open a link through its Windows-registered handler."""
	log.debug("Telegram opening message link: %s", url)
	try:
		os.startfile(url)
	except Exception:
		ui.message(_("Unable to open link"))


def _showMessageLinksMenu(links: tuple[str, ...]) -> None:
	"""Show a non-blocking NVDA-owned chooser containing the message links."""
	global _messageLinksDialog
	log.debug("Telegram link chooser opening with %d item(s)", len(links))
	try:
		import gui
		import wx

		if _messageLinksDialog is not None:
			_messageLinksDialog.Destroy()
			_messageLinksDialog = None

		gui.mainFrame.prePopup()
		try:
			dialog = wx.SingleChoiceDialog(
				gui.mainFrame,
				_("Select a link to open"),
				_("Links in message"),
				list(links),
			)
			_messageLinksDialog = dialog
			dialog.SetSelection(0)
			selectedIndex = 0

			def onSelect(event: object) -> None:
				nonlocal selectedIndex
				selection = cast(Any, event).GetSelection()
				if 0 <= selection < len(links):
					selectedIndex = selection

			def onOpen(event: object) -> None:
				selectedUrl = links[selectedIndex]
				dialog.Close()
				wx.CallAfter(_openMessageLink, selectedUrl)

			def onClose(event: object) -> None:
				global _messageLinksDialog
				if _messageLinksDialog is dialog:
					_messageLinksDialog = None
				cast(Any, event).Skip()

			dialog.Bind(wx.EVT_LISTBOX, onSelect)
			dialog.Bind(wx.EVT_BUTTON, onOpen, id=wx.ID_OK)
			dialog.Bind(wx.EVT_CLOSE, onClose)
			dialog.Show()
			dialog.Raise()
		finally:
			gui.mainFrame.postPopup()
	except Exception:
		log.exception("Telegram link chooser failed to open")
		ui.message(_("Unable to show links"))


def _sendGesture(gesture: object) -> None:
	try:
		cast(Any, gesture).send()
	except Exception:
		pass


def showMessageLinks(gesture: object) -> None:
	"""Show all links in the focused message, preserving Ctrl+Enter elsewhere."""
	focus = _focusObject()
	if focus is None or not isTelegramMessage(focus):
		_sendGesture(gesture)
		return
	element = _uiaElement(focus)
	text = _rawElementProperty(element, UIAHandler.UIA_NamePropertyId) if element is not None else None
	if not isinstance(text, str) or not text:
		text = _safeStringAttribute(focus, "name")
	links = linksFromMessageText(text)
	log.debug("Telegram link menu extracted links: %r", links)
	if not links:
		ui.message(_("No links in this message"))
		return
	if len(links) == 1:
		_openMessageLink(links[0])
		return
	core.callLater(0, _showMessageLinksMenu, links)
