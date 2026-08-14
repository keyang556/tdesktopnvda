# A part of Telegram Desktop Accessibility for NVDA
# Copyright (C) 2026 Ken Chang
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""App module for Telegram Desktop."""

from __future__ import annotations

from typing import Any, cast

import addonHandler
import api
import appModuleHandler
from comInterfaces.UIAutomationClient import IUIAutomationInvokePattern, tagPOINT
import controlTypes
from NVDAObjects.UIA import UIA
from scriptHandler import script
import ui
import UIAHandler


# Qualified loading from the companion global plug-in can execute this module
# outside NVDA's ordinary app-module importer. Avoid double initialization on
# reload while ensuring translated strings are available in both paths.
if "_" not in globals():
	addonHandler.initTranslation()


_CHAT_LIST_CLASS_NAME = "Dialogs::InnerWidget"
_DIALOGS_WIDGET_CLASS_NAME = "Dialogs::Widget"
_ICON_BUTTON_CLASS_NAME = "Ui::IconButton"
_SIDEBAR_BUTTON_CLASS_NAME = "Ui::SideBarButton"
_RTTI_CLASS_PREFIXES = ("class ", "struct ")
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
_MAIN_MENU_POINT_X_OFFSETS = (32, 56, 80)
# The standard toggle occupies y=7..47 in Telegram's 40 px style, while the
# folder-sidebar button extends farther down. Sample both regions.
_MAIN_MENU_POINT_Y_OFFSETS = (24, 40, 52, 76, 100)
# Telegram keeps folder buttons inside a scrolled container, while the menu
# button above them is outside it.
_SCROLLED_CONTAINER_CLASS_NAMES = ("Ui::ScrollArea", "Ui::ElasticScroll", "Ui::VerticalLayout")
_MAX_UIA_PARENT_STEPS = 16
_MAX_SIBLING_STEPS = 32
# The suggestion strip keeps its wording in child labels. Keep this walk small
# so a focus event can never expand a meaningful part of Telegram's UIA tree.
_MAX_SUGGESTION_TEXT_NODES = 24
_MAX_SUGGESTION_TEXT_DEPTH = 4


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


def _isRttiClassChain(value: str) -> bool:
	"""Return whether ``value`` consists only of RTTI class components."""
	if not value:
		return False
	return all(_isRttiClassComponent(component) for component in value.split("."))


def _isRttiClassComponent(component: str) -> bool:
	component = component.strip()
	for prefix in _RTTI_CLASS_PREFIXES:
		if component.startswith(prefix):
			bareName = component[len(prefix) :]
			# Ordinary wording such as "class of 99" is not an RTTI type.
			return bool(bareName) and not any(character.isspace() for character in bareName)
	return False


def _automationIdClassNames(automationId: str) -> tuple[str, ...]:
	"""Return Telegram's RTTI class components from a UIA AutomationId."""
	return tuple(
		component.strip().removeprefix("class ").removeprefix("struct ")
		for component in automationId.split(".")
		if component.strip()
	)


def _setObjectName(obj: object, name: str) -> None:
	try:
		obj.name = name
	except Exception:
		pass


def _providerName(obj: object) -> str:
	"""Return Telegram's provider name, excluding RTTI placeholders."""
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
	try:
		return tuple(children) if children else ()
	except Exception:
		return ()


def _suggestionText(obj: object) -> str:
	"""Read a suggestion strip's wording from a bounded set of descendants."""
	parts: list[str] = []
	seen: set[str] = set()
	pending: list[tuple[object, int]] = [(obj, 0)]
	visited = 0
	while pending and visited < _MAX_SUGGESTION_TEXT_NODES:
		node, depth = pending.pop(0)
		visited += 1
		if node is not obj:
			text = _safeStringAttribute(node, "name").strip()
			key = text.casefold()
			if text and not _isRttiClassChain(text) and key not in seen:
				seen.add(key)
				parts.append(text)
		if depth < _MAX_SUGGESTION_TEXT_DEPTH:
			pending.extend((child, depth + 1) for child in _childObjects(node))
	return ", ".join(parts)


def _ownClassName(obj: object, automationClasses: tuple[str, ...]) -> str:
	"""Return the control's class, rather than any ancestor in its ID chain."""
	return _normalizedClassName(obj) or (automationClasses[-1] if automationClasses else "")


def _cleanTelegramControlName(obj: object) -> None:
	"""Fill missing names for known Telegram controls before NVDA speaks."""
	automationId = _safeStringAttribute(obj, "UIAAutomationId")
	providerName = _providerName(obj)

	composerFallback = _COMPOSER_AUTOMATION_ID_NAMES.get(automationId)
	if composerFallback is not None:
		_setObjectName(obj, providerName or composerFallback)
		return

	automationClasses = _automationIdClassNames(automationId)
	if _TOP_BAR_SUGGESTION_CLASS_NAME in automationClasses:
		if _ownClassName(obj, automationClasses) == _TOP_BAR_SUGGESTION_CLASS_NAME:
			fallback = _suggestionText(obj) or _("Telegram suggestion")
		else:
			fallback = _("Dismiss suggestion")
		_setObjectName(obj, providerName or fallback)
		return

	# A real provider name always wins. Only known unnamed menu controls are
	# filled, using the object's own class to avoid naming every menu ancestor.
	if providerName:
		# An NVDA overlay may have dropped the provider's useful cached name.
		_setObjectName(obj, providerName)
		return
	menuName = _MAIN_MENU_CLASS_NAMES.get(_ownClassName(obj, automationClasses))
	if menuName is not None:
		_setObjectName(obj, menuName)
		return

	if _isRttiClassChain(_safeStringAttribute(obj, "name").strip()):
		# Announcing the role alone is preferable to spelling a C++ class path.
		_setObjectName(obj, "")


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


def _rawElementProperty(element: Any, propertyId: int) -> object | None:
	try:
		return element.GetCurrentPropertyValue(propertyId)
	except Exception:
		return None


def _rawViewWalker() -> Any | None:
	try:
		client: Any = _uiaHandler().clientObject
		return client.RawViewWalker
	except Exception:
		return None


def _rawNormalizedClassName(element: Any) -> str:
	className = _rawElementProperty(element, UIAHandler.UIA_ClassNamePropertyId)
	return _normalizedRttiClassName(className) if isinstance(className, str) else ""


def _rawAutomationIdClassNames(element: Any) -> tuple[str, ...]:
	"""Return the RTTI class components of a raw element's AutomationId."""
	automationId = _rawElementProperty(element, UIAHandler.UIA_AutomationIdPropertyId)
	if not isinstance(automationId, str):
		return ()
	return tuple(_normalizedRttiClassName(component) for component in automationId.split("."))


def _isFirstElementOfClass(element: Any, className: str) -> bool:
	"""Return True when no preceding raw-view sibling shares this class."""
	walker = _rawViewWalker()
	if walker is None:
		return False
	sibling = element
	for _step in range(_MAX_SIBLING_STEPS):
		try:
			sibling = walker.GetPreviousSiblingElement(sibling)
		except Exception:
			return False
		if sibling is None:
			return True
		if _rawNormalizedClassName(sibling) == className:
			return False
	return False


def _isRawTelegramMainMenuButton(element: Any) -> bool:
	"""Identify the menu button without accepting nearby folder/icon buttons."""
	if (
		_rawElementProperty(element, UIAHandler.UIA_ControlTypePropertyId)
		!= UIAHandler.UIA_ButtonControlTypeId
		or _rawElementProperty(element, UIAHandler.UIA_IsOffscreenPropertyId) is not False
	):
		return False
	className = _rawNormalizedClassName(element)
	if className not in (_SIDEBAR_BUTTON_CLASS_NAME, _ICON_BUTTON_CLASS_NAME):
		return False
	automationClasses = _rawAutomationIdClassNames(element)
	if any(component in _SCROLLED_CONTAINER_CLASS_NAMES for component in automationClasses):
		return False
	if className == _ICON_BUTTON_CLASS_NAME and _DIALOGS_WIDGET_CLASS_NAME not in automationClasses:
		return False
	return _isFirstElementOfClass(element, className)


def _findTelegramMainMenuButtonFromPoints(root: object) -> Any | None:
	"""Locate Telegram's top-left menu button without a subtree query."""
	try:
		location = root.location
		if location.width <= 0 or location.height <= 0:
			return None
		client: Any = _uiaHandler().clientObject
		walker = client.RawViewWalker
	except Exception:
		return None

	for xOffset in _MAIN_MENU_POINT_X_OFFSETS:
		x = round(location.left + min(xOffset, location.width * 0.25))
		for yOffset in _MAIN_MENU_POINT_Y_OFFSETS:
			y = round(location.top + min(yOffset, location.height * 0.25))
			try:
				element = client.ElementFromPoint(tagPOINT(x, y))
				for _step in range(_MAX_UIA_PARENT_STEPS):
					if element is None:
						break
					# Telegram constructs the real toggle before its transparent
					# MenuUnderButton hit area, then changes their stacking order.
					# UIA providers have exposed the toggle on either side of that
					# overlay, so inspect both adjacent raw-view siblings.
					candidates = [element]
					try:
						candidates.append(walker.GetPreviousSiblingElement(element))
					except Exception:
						pass
					try:
						candidates.append(walker.GetNextSiblingElement(element))
					except Exception:
						pass
					for candidate in candidates:
						if candidate is not None and _isRawTelegramMainMenuButton(candidate):
							return candidate
					element = walker.GetParentElement(element)
			except Exception:
				continue
	return None


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
		pattern = unknown.QueryInterface(IUIAutomationInvokePattern)
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
	def event_gainFocus(self, obj: object, nextHandler: Any) -> None:
		_cleanTelegramControlName(obj)
		nextHandler()

	def event_focusEntered(self, obj: object, nextHandler: Any) -> None:
		# The menu container is announced as a focus ancestor, not a target.
		_cleanTelegramControlName(obj)
		nextHandler()

	@script(description=_("Move focus to chat list"), gesture="kb:alt+1")
	def script_focusChatList(self, gesture: object) -> None:
		focusChatList()

	@script(description=_("Open main menu"), gesture="kb:alt+m")
	def script_openMainMenu(self, gesture: object) -> None:
		openMainMenu()


def focusChatList() -> None:
	"""Move focus to Telegram's selected chat, or its first chat."""
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


def openMainMenu() -> None:
	"""Invoke Telegram's native main-menu button."""
	root = _foregroundObject()
	pointButton = _findTelegramMainMenuButtonFromPoints(root) if root is not None else None
	if pointButton is not None and _invokeElement(pointButton):
		return
	# A sampled element can disappear while Telegram relays out the left pane,
	# or its provider action can fail transiently. Preserve the established
	# subtree lookup as a real execution fallback, not just a lookup fallback.
	fallbackButton = _findTelegramMainMenuButton(root) if root is not None else None
	if fallbackButton is not None and _invokeElement(fallbackButton):
		return
	ui.message(_("Main menu is not available"))
