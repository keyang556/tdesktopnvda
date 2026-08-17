# A part of Telegram Desktop Accessibility for NVDA
# Copyright (C) 2026 Ken Chang
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""App module for Telegram Desktop."""

from __future__ import annotations

from typing import Any, NamedTuple, cast

import addonHandler
import api
import appModuleHandler
from comInterfaces.UIAutomationClient import IUIAutomationInvokePattern, tagPOINT
import controlTypes
from logHandler import log
from NVDAObjects.UIA import UIA
import ui
import UIAHandler


# Qualified loading from the companion global plug-in can execute this module
# outside NVDA's ordinary app-module importer. UnigramPlus also loads this file
# from a temporary module that is not registered in sys.modules, where NVDA's
# frame-based initTranslation cannot install attributes on the caller module.
# Resolve the owning add-on directly so both loading paths remain valid.
if "_" not in globals():
	_ = addonHandler.getCodeAddon().getTranslationsInstance().gettext


_CALL_BUTTON_CLASS_NAME = "Ui::CallButton"
_CHAT_LIST_CLASS_NAME = "Dialogs::InnerWidget"
_DIALOGS_WIDGET_CLASS_NAME = "Dialogs::Widget"
_ICON_BUTTON_CLASS_NAME = "Ui::IconButton"
_MAIN_WINDOW_CLASS_NAME = "MainWindow"
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


def _usableElement(value: Any) -> Any | None:
	"""Normalize a provider NULL COM element to ``None``.

	Telegram returns a false-valued COM pointer when a UIA query or raw-tree
	walk has no result. It is not Python ``None``, but every method call on it
	raises ``NULL COM pointer access``. Normalize it before choosing a lookup
	result so a missing sidebar button cannot hide the standard icon button.
	"""
	try:
		return value if value else None
	except Exception:
		return None


def _uiaElement(obj: object) -> Any | None:
	"""Return the raw UIA element for an NVDA object without walking its children."""
	try:
		return _usableElement(getattr(obj, "UIAElement"))
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


def _findFirstElement(
	element: Any,
	scope: int,
	conditions: list[Any],
	*,
	useCache: bool = True,
) -> Any | None:
	"""Run one provider-side UIA query instead of expanding NVDA objects recursively."""
	try:
		handler = _uiaHandler()
		client: Any = handler.clientObject
		condition = conditions[0] if len(conditions) == 1 else client.CreateAndConditionFromArray(conditions)
		if not useCache:
			# Telegram's Qt provider can return a BuildCache result whose cached
			# properties are readable but whose current COM pointer is NULL. Such
			# an element can be identified as the menu button yet cannot expose an
			# InvokePattern. Action targets therefore need a live query result.
			return _usableElement(element.FindFirst(scope, condition))
		return _usableElement(
			element.FindFirstBuildCache(
				scope,
				condition,
				handler.baseCacheRequest,
			),
		)
	except Exception:
		return None


def _findAllElements(element: Any, scope: int, conditions: list[Any]) -> tuple[Any, ...]:
	"""Collect every match of one provider-side UIA query, as live elements."""
	try:
		client: Any = _uiaHandler().clientObject
		condition = conditions[0] if len(conditions) == 1 else client.CreateAndConditionFromArray(conditions)
		found = _usableElement(element.FindAll(scope, condition))
		if found is None:
			return ()
		length = found.Length
	except Exception:
		return ()
	elements: list[Any] = []
	for index in range(length):
		try:
			match = _usableElement(found.GetElement(index))
		except Exception:
			continue
		if match is not None:
			elements.append(match)
	return tuple(elements)


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
	return _findFirstElement(
		element,
		UIAHandler.TreeScope_Subtree,
		conditions,
		useCache=False,
	)


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
		return _usableElement(client.RawViewWalker)
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
	return tuple(
		className
		for component in automationId.split(".")
		if (className := _normalizedRttiClassName(component))
	)


def _isFirstElementOfClass(element: Any, className: str) -> bool:
	"""Return True when no preceding raw-view sibling shares this class."""
	walker = _rawViewWalker()
	if walker is None:
		return False
	sibling = element
	for _step in range(_MAX_SIBLING_STEPS):
		try:
			sibling = _usableElement(walker.GetPreviousSiblingElement(sibling))
		except Exception:
			return False
		if sibling is None:
			return True
		if _rawNormalizedClassName(sibling) == className:
			# Qt can flatten title-bar and dialogs controls into one raw
			# sibling list. A prior title-bar IconButton does not make the
			# first Dialogs::Widget IconButton a later dialogs button.
			if (
				className != _ICON_BUTTON_CLASS_NAME
				or _DIALOGS_WIDGET_CLASS_NAME in _rawAutomationIdClassNames(sibling)
			):
				return False
	return False


def _rawElementSupportsInvoke(element: Any) -> bool:
	try:
		return element.GetCurrentPattern(UIAHandler.UIA_InvokePatternId) is not None
	except Exception:
		return False


def _isRawTelegramMainMenuButton(element: Any, *, directTopLeftHit: bool = False) -> bool:
	"""Identify the menu button without accepting nearby folder/icon buttons."""
	if (
		_rawElementProperty(element, UIAHandler.UIA_ControlTypePropertyId)
		!= UIAHandler.UIA_ButtonControlTypeId
		or _rawElementProperty(element, UIAHandler.UIA_IsOffscreenPropertyId) is not False
	):
		return False
	className = _rawNormalizedClassName(element)
	automationClasses = _rawAutomationIdClassNames(element)
	if not className:
		# Telegram 7.0.9 can omit both RTTI properties for every UIA object.
		# Only accept such an element when it is the object directly returned
		# from a source-derived top-left sample, never merely a neighbour.
		return directTopLeftHit and not automationClasses and _rawElementSupportsInvoke(element)
	if className not in (_SIDEBAR_BUTTON_CLASS_NAME, _ICON_BUTTON_CLASS_NAME):
		return False
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
				element = _usableElement(client.ElementFromPoint(tagPOINT(x, y)))
				for _step in range(_MAX_UIA_PARENT_STEPS):
					if element is None:
						break
					# Telegram constructs the real toggle before its transparent
					# MenuUnderButton hit area, then changes their stacking order.
					# UIA providers have exposed the toggle on either side of that
					# overlay, so inspect both adjacent raw-view siblings.
					candidates = [element]
					try:
						candidates.append(_usableElement(walker.GetPreviousSiblingElement(element)))
					except Exception:
						pass
					try:
						candidates.append(_usableElement(walker.GetNextSiblingElement(element)))
					except Exception:
						pass
					for candidate in candidates:
						if candidate is not None and _isRawTelegramMainMenuButton(
							candidate,
							directTopLeftHit=(candidate is element and yOffset <= 52),
						):
							return candidate
					element = _usableElement(walker.GetParentElement(element))
			except Exception:
				continue
	return None


class _CallPanelButtons(NamedTuple):
	"""Telegram's call controls, resolved from the panel's own button row."""

	answerHangup: Any | None = None
	declineCancel: Any | None = None
	microphone: Any | None = None
	camera: Any | None = None


def _visibleCallButtons(root: object) -> tuple[Any, ...]:
	"""Return the on-screen ``Ui::CallButton`` controls of one Telegram window."""
	element = _uiaElement(root)
	if element is None:
		return ()
	try:
		client: Any = _uiaHandler().clientObject
		conditions = [
			_rttiClassCondition(client, _CALL_BUTTON_CLASS_NAME),
			_propertyCondition(
				client,
				UIAHandler.UIA_ControlTypePropertyId,
				UIAHandler.UIA_ButtonControlTypeId,
			),
			_propertyCondition(client, UIAHandler.UIA_IsOffscreenPropertyId, False),
		]
	except Exception:
		return ()
	return _findAllElements(element, UIAHandler.TreeScope_Subtree, conditions)


def _isDeviceSelectionCorner(element: Any) -> bool:
	"""Return whether this button is the small corner button of another one."""
	walker = _rawViewWalker()
	if walker is None:
		return False
	try:
		parent = _usableElement(walker.GetParentElement(element))
	except Exception:
		return False
	return parent is not None and _rawNormalizedClassName(parent) == _CALL_BUTTON_CLASS_NAME


def _hasDeviceSelectionCorner(element: Any) -> bool:
	"""Return whether this button carries a device-selection corner button.

	Telegram gives exactly two of the call panel's buttons such a corner button:
	the camera and the microphone. It is the only difference between them and
	their neighbours that does not depend on Telegram's display language.
	"""
	try:
		client: Any = _uiaHandler().clientObject
		condition = _rttiClassCondition(client, _CALL_BUTTON_CLASS_NAME)
	except Exception:
		return False
	return (
		_findFirstElement(
			element,
			UIAHandler.TreeScope_Children,
			[condition],
			useCache=False,
		)
		is not None
	)


def _elementLeft(element: Any) -> float | None:
	"""Return a UIA element's screen x position, skipping empty rectangles."""
	rectangle = _rawElementProperty(element, UIAHandler.UIA_BoundingRectanglePropertyId)
	try:
		left, _top, width, _height = rectangle  # type: ignore[misc]
	except Exception:
		return None
	if not isinstance(left, (int, float)) or not isinstance(width, (int, float)) or width <= 0:
		return None
	return float(left)


def _lastButtonLeftOf(
	buttons: list[tuple[float, Any]],
	limit: float | None,
) -> tuple[float | None, Any | None]:
	"""Return the rightmost button of an x-sorted row that starts before ``limit``."""
	for left, element in reversed(buttons):
		if limit is None or left < limit:
			return left, element
	return None, None


def _callPanelButtons(root: object) -> _CallPanelButtons:
	"""Identify Telegram's call controls without reading a translated name.

	Telegram lays its call panel out as
	``Screencast - Camera - Cancel/Decline - Answer/Hangup/Redial - Mute``,
	with the add-people button after the microphone. Every one of them is a
	``Ui::CallButton``, so the camera and the microphone are recognized by
	their device-selection corner button and the rest by their place in that
	row. Camera and the microphone always hide together, so anything but
	exactly two corner buttons - or exactly zero, alongside the three plain
	buttons that remain while a local outgoing call awaits confirmation (a
	cornerless video trigger in the camera's slot, Cancel, and the shared
	Answer/Hangup/Redial button) - is a shape this add-on does not recognize,
	rather than a guess at one.
	"""
	plain: list[tuple[float, Any]] = []
	withCorner: list[tuple[float, Any]] = []
	for element in _visibleCallButtons(root):
		if _isDeviceSelectionCorner(element):
			continue
		left = _elementLeft(element)
		if left is None:
			continue
		(withCorner if _hasDeviceSelectionCorner(element) else plain).append((left, element))
	plain.sort(key=lambda entry: entry[0])
	withCorner.sort(key=lambda entry: entry[0])

	if not withCorner:
		if len(plain) != 3:
			return _CallPanelButtons()
		_videoTrigger, cancel, answerHangup = (element for _left, element in plain)
		return _CallPanelButtons(answerHangup=answerHangup, declineCancel=cancel)
	if len(withCorner) != 2:
		return _CallPanelButtons()
	(cameraLeft, camera), (microphoneLeft, microphone) = withCorner

	answerHangupLeft, answerHangup = _lastButtonLeftOf(plain, microphoneLeft)
	if answerHangupLeft is not None and answerHangupLeft <= cameraLeft:
		# Only screen sharing sits left of the camera; the shared answer button
		# is missing rather than standing there.
		answerHangupLeft, answerHangup = None, None

	declineLeft, declineCancel = (
		_lastButtonLeftOf(plain, answerHangupLeft) if answerHangup is not None else (None, None)
	)
	if declineLeft is not None and declineLeft <= cameraLeft:
		declineCancel = None

	return _CallPanelButtons(
		answerHangup=answerHangup,
		declineCancel=declineCancel,
		microphone=microphone,
		camera=camera,
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
		unknown = _usableElement(element.GetCurrentPattern(UIAHandler.UIA_InvokePatternId))
		if unknown is None:
			return False
		pattern = unknown.QueryInterface(IUIAutomationInvokePattern)
		pattern.Invoke()
		return True
	except Exception:
		log.debugWarning("Telegram main-menu InvokePattern failed", exc_info=True)
		return False


def _foregroundObject() -> object | None:
	try:
		return api.getForegroundObject()
	except Exception:
		return None


def _appName(obj: object) -> str:
	try:
		return obj.appModule.appName.casefold()
	except Exception:
		return ""


def _isTelegramMainWindow(obj: object) -> bool:
	return obj is not None and _normalizedClassName(obj) == _MAIN_WINDOW_CLASS_NAME


def _telegramMainWindow() -> object | None:
	"""Return Telegram's main window even when a same-process popup is in front."""
	root = _foregroundObject()
	if _isTelegramMainWindow(root):
		return root
	appName = _appName(root)
	if not appName:
		# Do not select an unrelated desktop window when the foreground object
		# cannot establish which application owns it.
		return root
	try:
		children = api.getDesktopObject().children
	except Exception:
		return root
	for child in children or ():
		if _isTelegramMainWindow(child) and _appName(child) == appName:
			return child
	return root


def _telegramWindows() -> tuple[object, ...]:
	"""Return Telegram's top-level windows, the foreground one first.

	A Telegram call runs in a window of its own, which the user can leave
	without ending the call, so the call commands cannot search only the window
	that happens to be in front.
	"""
	root = _foregroundObject()
	if root is None:
		return ()
	appName = _appName(root)
	if not appName:
		# Do not search unrelated desktop windows when the foreground object
		# cannot establish which application owns it.
		return (root,)
	windows = [root]
	try:
		children = api.getDesktopObject().children
	except Exception:
		return tuple(windows)
	for child in children or ():
		if child is not root and _appName(child) == appName:
			windows.append(child)
	return tuple(windows)


def _focusObject() -> object | None:
	try:
		return api.getFocusObject()
	except Exception:
		return None


class AppModule(appModuleHandler.AppModule):
	"""Label Telegram's unnamed controls.

	The add-on's commands are not defined here. NVDA would then list them in the
	Input Gestures dialog once per class, and the two entries share a category
	and description, so only one of them would survive and stay reassignable.
	``globalPlugins.telegramDesktop.GlobalPlugin`` owns them instead and calls
	the module level functions below.
	"""

	def event_gainFocus(self, obj: object, nextHandler: Any) -> None:
		_cleanTelegramControlName(obj)
		nextHandler()

	def event_focusEntered(self, obj: object, nextHandler: Any) -> None:
		# The menu container is announced as a focus ancestor, not a target.
		_cleanTelegramControlName(obj)
		nextHandler()


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
	root = _telegramMainWindow()
	pointButton = _findTelegramMainMenuButtonFromPoints(root) if root is not None else None
	log.debug("Telegram Alt+M point candidate found: %s", pointButton is not None)
	if pointButton is not None and _invokeElement(pointButton):
		return
	# A sampled element can disappear while Telegram relays out the left pane,
	# or its provider action can fail transiently. Preserve the established
	# subtree lookup as a real execution fallback, not just a lookup fallback.
	fallbackButton = _findTelegramMainMenuButton(root) if root is not None else None
	log.debug("Telegram Alt+M subtree candidate found: %s", fallbackButton is not None)
	if fallbackButton is not None and _invokeElement(fallbackButton):
		return
	ui.message(_("Main menu is not available"))


def _telegramCallPanel() -> _CallPanelButtons:
	"""Return the call controls of whichever Telegram window is showing a call."""
	for window in _telegramWindows():
		buttons = _callPanelButtons(window)
		if buttons.answerHangup is not None or buttons.microphone is not None:
			return buttons
	return _CallPanelButtons()


def _pressCallButton(button: Any | None) -> bool:
	"""Press a call control, reporting the action in Telegram's own wording.

	Each of these buttons is named after what pressing it does, so the name is
	read before the button is pressed. Reading it afterwards would race
	Telegram's own update of that name.
	"""
	if button is None:
		return False
	name = _elementName(button)
	if not _invokeElement(button):
		return False
	if name:
		ui.message(name)
	return True


def answerCall() -> None:
	"""Accept the call Telegram is ringing for."""
	buttons = _telegramCallPanel()
	# Telegram shares one button between answering and hanging up, and its
	# Cancel button (a pending outgoing call, or a busy redial offer) sits in
	# the same slot as Decline, so a neighbour alone does not prove there is a
	# ringing call to answer. While a local outgoing call awaits confirmation,
	# Telegram also replaces the camera with a cornerless "Start call" trigger
	# and hides the microphone button - requiring the microphone too keeps
	# this command from placing that pending call instead of reporting there
	# is nothing to answer.
	if (
		buttons.declineCancel is None
		or buttons.microphone is None
		or not _pressCallButton(buttons.answerHangup)
	):
		ui.message(_("No incoming call"))


def endCall() -> None:
	"""Decline the incoming Telegram call, or end the call in progress."""
	buttons = _telegramCallPanel()
	# While a call rings, the shared button answers it, so the separate decline
	# button is the one that hangs up.
	target = buttons.declineCancel if buttons.declineCancel is not None else buttons.answerHangup
	if not _pressCallButton(target):
		ui.message(_("Not in a call"))


def toggleCallMicrophone() -> None:
	"""Mute or unmute the microphone in Telegram's call."""
	if not _pressCallButton(_telegramCallPanel().microphone):
		ui.message(_("Not in a call"))


def toggleCallCamera() -> None:
	"""Turn the camera on or off in Telegram's call."""
	if not _pressCallButton(_telegramCallPanel().camera):
		ui.message(_("Not in a call"))
