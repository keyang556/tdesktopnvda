# A part of Telegram Desktop Accessibility for NVDA
# Copyright (C) 2026 Ken Chang
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""App module for Telegram Desktop."""

from __future__ import annotations

from typing import Any, NamedTuple, cast

import api
import appModuleHandler
from comInterfaces.UIAutomationClient import tagPOINT
import controlTypes
import core
from keyboardHandler import KeyboardInputGesture
from NVDAObjects.UIA import UIA
from scriptHandler import script
import ui
import UIAHandler
import winUser


_CHAT_LIST_CLASS_NAME = "Dialogs::InnerWidget"
_DIALOGS_WIDGET_CLASS_NAME = "Dialogs::Widget"
_ICON_BUTTON_CLASS_NAME = "Ui::IconButton"
_MAIN_MENU_CLASS_NAME = "Window::MainMenu"
_SIDEBAR_BUTTON_CLASS_NAME = "Ui::SideBarButton"
_RTTI_CLASS_PREFIXES = ("class ", "struct ")
_CHAT_LIST_POINT_X_OFFSETS = (120, 200, 280)
_CHAT_LIST_POINT_Y_FRACTIONS = (0.35, 0.55, 0.75)
_MAX_UIA_PARENT_STEPS = 16
# Roughly one second of 25 ms polls while waiting for Alt to be released.
_MAX_ALT_RELEASE_POLLS = 40
_mainMenuCloseCounter = 0


class _ForegroundIdentity(NamedTuple):
	"""Which foreground window a delayed callback belongs to."""

	windowHandle: int | None
	root: object


class _PendingMainMenuClose(NamedTuple):
	"""The single main-menu close operation Alt+1 may have in flight."""

	token: int
	identity: _ForegroundIdentity | None


_pendingMainMenuClose: _PendingMainMenuClose | None = None


def _safeStringAttribute(obj: object, attribute: str) -> str:
	try:
		value = getattr(obj, attribute)
	except Exception:
		return ""
	return value if isinstance(value, str) else ""


def _normalizedRttiClassName(value: str) -> str:
	"""Return a Windows RTTI class name without its MSVC type prefix."""
	value = value.strip()
	for prefix in _RTTI_CLASS_PREFIXES:
		if value.startswith(prefix):
			return value[len(prefix) :]
	return value


def _normalizedClassName(obj: object) -> str:
	return _normalizedRttiClassName(_safeStringAttribute(obj, "UIAClassName"))


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
	"""Fall back to a provider-side subtree search for unusual layouts."""
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


def _isRawTelegramChatList(element: Any) -> bool:
	className = _rawElementProperty(element, UIAHandler.UIA_ClassNamePropertyId)
	return (
		isinstance(className, str)
		and _normalizedRttiClassName(className) == _CHAT_LIST_CLASS_NAME
		and _rawElementProperty(element, UIAHandler.UIA_ControlTypePropertyId)
		== UIAHandler.UIA_ListControlTypeId
		and _rawElementProperty(element, UIAHandler.UIA_IsOffscreenPropertyId) is False
	)


def _findTelegramChatListFromPoints(root: object) -> Any | None:
	"""Locate the chat list without asking Telegram to scan its full UIA tree.

	Telegram's dialogs pane occupies the left portion of its foreground window.
	UIA point lookup takes only a few milliseconds, while this provider's
	``FindFirst`` subtree query takes roughly half a second. Each hit is walked
	upward and validated by Telegram's language-independent RTTI class.
	"""
	try:
		location = root.location
		if location.width <= 0 or location.height <= 0:
			return None
		handler = _uiaHandler()
		client: Any = handler.clientObject
		walker = client.RawViewWalker
	except Exception:
		return None

	for xOffset in _CHAT_LIST_POINT_X_OFFSETS:
		x = round(location.left + min(xOffset, location.width * 0.3))
		for yFraction in _CHAT_LIST_POINT_Y_FRACTIONS:
			y = round(location.top + location.height * yFraction)
			try:
				element = client.ElementFromPoint(tagPOINT(x, y))
				for _step in range(_MAX_UIA_PARENT_STEPS):
					if element is None:
						break
					if _isRawTelegramChatList(element):
						return element
					element = walker.GetParentElement(element)
			except Exception:
				continue
	return None


def _findChatListItem(chatList: Any) -> Any | None:
	"""Prefer the selected chat row, then the first direct chat-list item."""
	selected = _findSelectedChatListItem(chatList)
	if selected is not None:
		return selected
	try:
		client: Any = _uiaHandler().clientObject
		itemCondition = _propertyCondition(
			client,
			UIAHandler.UIA_ControlTypePropertyId,
			UIAHandler.UIA_ListItemControlTypeId,
		)
	except Exception:
		return None
	return _findFirstElement(
		chatList,
		UIAHandler.TreeScope_Children,
		[itemCondition],
	)


def _findSelectedChatListItem(chatList: Any) -> Any | None:
	"""Return the selected direct chat-list item without falling back."""
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
	return _findFirstElement(
		chatList,
		UIAHandler.TreeScope_Children,
		[itemCondition, selectedCondition],
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


def _windowHandle(obj: object) -> int | None:
	"""Return the top-level window handle backing an NVDA object."""
	try:
		value = getattr(obj, "windowHandle")
	except Exception:
		return None
	return value if isinstance(value, int) else None


def _foregroundIdentity() -> _ForegroundIdentity | None:
	"""Capture what the current foreground window is, for a later callback.

	The window handle is the reliable half, but a provider need not expose one.
	NVDA keeps a single foreground object until the foreground actually
	changes, so the object itself identifies the window when its handle does
	not, and a delayed callback can still tell whether it is acting on the
	window that scheduled it.
	"""
	root = _foregroundObject()
	if root is None:
		return None
	return _ForegroundIdentity(_windowHandle(root), root)


def _isStillForeground(identity: _ForegroundIdentity | None) -> bool:
	"""Return True only while the captured window is still in the foreground."""
	if identity is None:
		return False
	current = _foregroundObject()
	if current is None:
		return False
	if identity.windowHandle is not None:
		return _windowHandle(current) == identity.windowHandle
	return current is identity.root


class AppModule(appModuleHandler.AppModule):
	@script(description=_("Move focus to chat list"), gesture="kb:alt+1")
	def script_focusChatList(self, gesture: object) -> None:
		focusChatList()

	@script(description=_("Open main menu"), gesture="kb:alt+m")
	def script_openMainMenu(self, gesture: object) -> None:
		root = _foregroundObject()
		button = _findTelegramMainMenuButton(root) if root is not None else None
		if button is None:
			ui.message(_("Main menu is not available"))
			return
		if not _invokeElement(button):
			ui.message(_("Main menu is not available"))


def _endPendingMainMenuClose(token: int) -> None:
	global _pendingMainMenuClose
	if _pendingMainMenuClose is not None and _pendingMainMenuClose.token == token:
		_pendingMainMenuClose = None


def _focusChatListAfterClosingMainMenu(token: int, identity: _ForegroundIdentity | None) -> None:
	"""Retry Alt+1 after Telegram has dismissed its modal main menu."""
	if _pendingMainMenuClose is None or _pendingMainMenuClose.token != token:
		return
	_endPendingMainMenuClose(token)
	focusChatList(closeMainMenu=False, identity=identity)


def _closeMainMenuAndFocusChatList(
	token: int,
	identity: _ForegroundIdentity | None,
	remainingPolls: int = _MAX_ALT_RELEASE_POLLS,
) -> None:
	"""Dismiss Telegram's main menu after Alt from Alt+1 is released."""
	if _pendingMainMenuClose is None or _pendingMainMenuClose.token != token:
		# This chain was superseded or already finished.
		return
	if not _isStillForeground(identity):
		# The window that started Alt+1 is no longer in the foreground, so
		# neither Escape nor the chat-list search may be aimed at whatever
		# replaced it.
		_endPendingMainMenuClose(token)
		return
	if winUser.getAsyncKeyState(winUser.VK_MENU) & 0x8000:
		if remainingPolls <= 0:
			# Alt looks stuck down. Sending Escape now would reach Windows as
			# Alt+Escape, so give up rather than wedging the shortcut.
			_endPendingMainMenuClose(token)
			return
		core.callLater(25, _closeMainMenuAndFocusChatList, token, identity, remainingPolls - 1)
		return
	currentFocus = _focusObject()
	if currentFocus is not None and _automationIdContainsClass(currentFocus, _MAIN_MENU_CLASS_NAME):
		try:
			KeyboardInputGesture.fromName("escape").send()
		except Exception:
			_endPendingMainMenuClose(token)
			ui.message(_("Chat list not found"))
			return
	core.callLater(100, _focusChatListAfterClosingMainMenu, token, identity)


def focusChatList(*, closeMainMenu: bool = True, identity: _ForegroundIdentity | None = None) -> None:
	"""Move focus to Telegram's selected or first chat row."""
	global _pendingMainMenuClose, _mainMenuCloseCounter
	if identity is not None and not _isStillForeground(identity):
		# A delayed retry outlived the window that requested it.
		return
	currentFocus = _focusObject()
	if (
		closeMainMenu
		and currentFocus is not None
		and _automationIdContainsClass(currentFocus, _MAIN_MENU_CLASS_NAME)
	):
		# Telegram removes the chat list from point hit-testing while its modal
		# main-menu layer is open. Wait until Windows reports that the Alt key
		# from Alt+1 has actually been released before sending Escape;
		# otherwise Windows interprets it as Alt+Escape and switches
		# applications. Then retry once after Qt updates its accessibility tree.
		# Auto-repeat fires this script many times while Alt+1 is held, so a
		# single close operation is tracked instead of one polling chain per
		# repeat; otherwise several callbacks each send Escape and the extra
		# presses reach Telegram's back/cancel handling after the menu closed.
		if _pendingMainMenuClose is not None:
			return
		originator = _foregroundIdentity()
		if originator is None:
			# Without an originating window there is nothing to aim Escape at,
			# and no way to tell later whether Telegram is still in front.
			ui.message(_("Chat list not found"))
			return
		_mainMenuCloseCounter += 1
		_pendingMainMenuClose = _PendingMainMenuClose(_mainMenuCloseCounter, originator)
		core.callLater(25, _closeMainMenuAndFocusChatList, *_pendingMainMenuClose)
		return
	try:
		currentParent = currentFocus.parent
	except Exception:
		currentParent = None
	if (
		currentFocus is not None
		and _safeRole(currentFocus) == controlTypes.Role.LISTITEM
		and isTelegramChatList(currentParent)
	):
		name = _elementName(_uiaElement(currentFocus))
		if name:
			ui.message(name)
		return

	root = _foregroundObject()
	chatList = _findTelegramChatListFromPoints(root) if root is not None else None
	if chatList is None and root is not None:
		chatList = _findTelegramChatList(root)
	if chatList is None:
		ui.message(_("Chat list not found"))
		return

	target = _findChatListItem(chatList)
	if target is None:
		ui.message(_("Chat list is empty"))
		return

	if _sameUIAElement(target, _uiaElement(currentFocus)):
		name = _elementName(target)
		if name:
			ui.message(name)
		return
	if not _setElementFocus(target):
		ui.message(_("Chat list not found"))
