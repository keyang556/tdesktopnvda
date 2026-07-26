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
from contentRecog import RecogImageInfo, RecognitionResult
from contentRecog.uwpOcr import UwpOcr
import core
import displayModel
from keyboardHandler import KeyboardInputGesture
from locationHelper import RectLTRB
from NVDAObjects.UIA import UIA
import queueHandler
import screenBitmap
from scriptHandler import script
import ui
import UIAHandler
import winUser


addonHandler.initTranslation()


_CHAT_LIST_CLASS_NAME = "Dialogs::InnerWidget"
_DIALOGS_WIDGET_CLASS_NAME = "Dialogs::Widget"
_ICON_BUTTON_CLASS_NAME = "Ui::IconButton"
_MAIN_MENU_CLASS_NAME = "Window::MainMenu"
_SIDEBAR_BUTTON_CLASS_NAME = "Ui::SideBarButton"
_HISTORY_TOP_BAR_CLASS_NAME = "HistoryView::TopBarWidget"
_RTTI_CLASS_PREFIXES = ("class ", "struct ")
_CHAT_LIST_POINT_X_OFFSETS = (120, 200, 280)
_CHAT_LIST_POINT_Y_FRACTIONS = (0.35, 0.55, 0.75)
_MAIN_MENU_POINT_X_OFFSETS = (32, 56, 80)
_MAIN_MENU_POINT_Y_OFFSETS = (52, 76, 100)
_MAX_UIA_PARENT_STEPS = 16
_CHAT_SWITCH_ANNOUNCEMENT_DELAY_MS = 200
_CHAT_SWITCH_ANNOUNCEMENT_RETRY_MS = 100
_CHAT_SWITCH_ANNOUNCEMENT_RETRIES = 4
_CHAT_TITLE_FORMATTING_TRANSLATION = str.maketrans(
	"",
	"",
	"\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069",
)


_chatSwitchGeneration = 0
_chatTitleRecognizer: UwpOcr | None = None


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


def _findHistoryTopBarButton(root: object) -> Any | None:
	"""Return the leftmost accessible button bordering the painted chat title."""
	element = _uiaElement(root)
	if element is None:
		return None
	try:
		client: Any = _uiaHandler().clientObject
		conditions = [
			_rttiClassCondition(client, _ICON_BUTTON_CLASS_NAME),
			_propertyCondition(
				client,
				UIAHandler.UIA_ControlTypePropertyId,
				UIAHandler.UIA_ButtonControlTypeId,
			),
			_propertyCondition(client, UIAHandler.UIA_IsOffscreenPropertyId, False),
			client.CreatePropertyConditionEx(
				UIAHandler.UIA_AutomationIdPropertyId,
				_HISTORY_TOP_BAR_CLASS_NAME,
				UIAHandler.PropertyConditionFlags_MatchSubstring,
			),
		]
	except Exception:
		return None
	return _findFirstElement(element, UIAHandler.TreeScope_Subtree, conditions)


def _chatTitleRect(root: object) -> RectLTRB | None:
	"""Return the screen rectangle containing Telegram's painted chat title."""
	chatList = _findTelegramChatListFromPoints(root)
	if chatList is None:
		chatList = _findTelegramChatList(root)
	topBarButton = _findHistoryTopBarButton(root)
	if chatList is None or topBarButton is None:
		return ""
	try:
		chatListLocation = UIA(UIAElement=chatList).location
		buttonLocation = UIA(UIAElement=topBarButton).location
		left = chatListLocation.right
		right = buttonLocation.left
		top = buttonLocation.top
		bottom = buttonLocation.bottom
		if right <= left or bottom <= top:
			return None
		return RectLTRB(left, top, right, bottom)
	except Exception:
		return None


def _paintedChatTitle(root: object) -> str:
	"""Read Telegram's painted conversation title through NVDA's display model."""
	rect = _chatTitleRect(root)
	if rect is None:
		return ""
	try:
		info = displayModel.DisplayModelTextInfo(
			root,
			rect,
		)
		lines = (line.strip() for line in info.text.splitlines())
		return next((line for line in lines if line), "")
	except Exception:
		return ""


def _windowChatTitle(root: object) -> str:
	"""Read the current chat title exposed as Telegram's window name."""
	try:
		name = cast(Any, root).name
	except Exception:
		return ""
	if not isinstance(name, str):
		return ""
	return name.translate(_CHAT_TITLE_FORMATTING_TRANSLATION).strip()


def _recognitionTitle(result: RecognitionResult | Exception) -> str:
	if isinstance(result, Exception):
		return ""
	try:
		lines = (line.strip() for line in result.text.splitlines())
	except Exception:
		return ""
	return next((line for line in lines if line), "")


def _handleChatTitleRecognition(
	result: RecognitionResult | Exception,
	generation: int,
	previousTitle: str,
	retriesRemaining: int,
) -> None:
	"""Handle the asynchronous OCR result on NVDA's main event queue."""
	if generation != _chatSwitchGeneration:
		return
	title = _recognitionTitle(result)
	if title and (title != previousTitle or retriesRemaining <= 0):
		ui.message(title)
		return
	if retriesRemaining > 0:
		core.callLater(
			_CHAT_SWITCH_ANNOUNCEMENT_RETRY_MS,
			_announceSwitchedChat,
			generation,
			previousTitle,
			retriesRemaining - 1,
		)


def _recognizePaintedChatTitle(
	root: object,
	generation: int,
	previousTitle: str,
	retriesRemaining: int,
) -> bool:
	"""Start Windows OCR for Telegram's small painted title rectangle."""
	global _chatTitleRecognizer
	rect = _chatTitleRect(root)
	if rect is None:
		return False
	try:
		recognizer = UwpOcr()
		width = rect.right - rect.left
		height = rect.bottom - rect.top
		imageInfo = RecogImageInfo.createFromRecognizer(
			rect.left,
			rect.top,
			width,
			height,
			recognizer,
		)
		bitmap = screenBitmap.ScreenBitmap(
			imageInfo.recogWidth,
			imageInfo.recogHeight,
		)
		pixels = bitmap.captureImage(
			imageInfo.screenLeft,
			imageInfo.screenTop,
			imageInfo.screenWidth,
			imageInfo.screenHeight,
		)
	except Exception:
		return False

	_chatTitleRecognizer = recognizer

	def onResult(result: RecognitionResult | Exception) -> None:
		queueHandler.queueFunction(
			queueHandler.eventQueue,
			_handleChatTitleRecognition,
			result,
			generation,
			previousTitle,
			retriesRemaining,
		)

	try:
		recognizer.recognize(pixels, imageInfo, onResult)
	except Exception:
		return False
	return True


def _isRawTelegramMainMenuButton(element: Any) -> bool:
	if (
		_rawElementProperty(element, UIAHandler.UIA_ControlTypePropertyId)
		!= UIAHandler.UIA_ButtonControlTypeId
		or _rawElementProperty(element, UIAHandler.UIA_IsOffscreenPropertyId) is not False
	):
		return False
	className = _rawElementProperty(element, UIAHandler.UIA_ClassNamePropertyId)
	if not isinstance(className, str):
		return False
	className = _normalizedRttiClassName(className)
	if className == _SIDEBAR_BUTTON_CLASS_NAME:
		return True
	if className != _ICON_BUTTON_CLASS_NAME:
		return False
	automationId = _rawElementProperty(element, UIAHandler.UIA_AutomationIdPropertyId)
	return isinstance(automationId, str) and _DIALOGS_WIDGET_CLASS_NAME in automationId


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
					# Telegram places a transparent MenuUnderButton group over
					# the actual icon button. In the raw UIA view, that button is
					# the group's next sibling rather than its point-hit ancestor.
					candidates = [element]
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
	@script(description=_("Move focus to chat list"), gesture="kb:alt+1")
	def script_focusChatList(self, gesture: object) -> None:
		focusChatList()

	@script(description=_("Open main menu"), gesture="kb:alt+m")
	def script_openMainMenu(self, gesture: object) -> None:
		openMainMenu()

	@script(
		description=_("Switch chats and announce the chat name"),
		gestures=("kb:control+tab", "kb:control+shift+tab"),
	)
	def script_switchChat(self, gesture: object) -> None:
		switchChat(gesture)


def _focusChatListAfterClosingMainMenu() -> None:
	"""Retry Alt+1 after Telegram has dismissed its modal main menu."""
	focusChatList(closeMainMenu=False)


def _closeMainMenuAndFocusChatList() -> None:
	"""Dismiss Telegram's main menu after Alt from Alt+1 is released."""
	if winUser.getAsyncKeyState(winUser.VK_MENU) & 0x8000:
		core.callLater(25, _closeMainMenuAndFocusChatList)
		return
	currentFocus = _focusObject()
	if currentFocus is not None and _automationIdContainsClass(currentFocus, _MAIN_MENU_CLASS_NAME):
		try:
			KeyboardInputGesture.fromName("escape").send()
		except Exception:
			ui.message(_("Chat list not found"))
			return
	core.callLater(100, _focusChatListAfterClosingMainMenu)


def focusChatList(*, closeMainMenu: bool = True) -> None:
	"""Move focus to Telegram's selected or first chat row."""
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
		core.callLater(25, _closeMainMenuAndFocusChatList)
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


def openMainMenu() -> None:
	"""Invoke Telegram's main-menu button."""
	root = _foregroundObject()
	button = _findTelegramMainMenuButtonFromPoints(root) if root is not None else None
	if button is None and root is not None:
		button = _findTelegramMainMenuButton(root)
	if button is None:
		ui.message(_("Main menu is not available"))
		return
	if not _invokeElement(button):
		ui.message(_("Main menu is not available"))


def _announceSwitchedChat(
	generation: int,
	previousTitle: str,
	retriesRemaining: int,
) -> None:
	"""Wait for Telegram's window title to update, then announce it."""
	if generation != _chatSwitchGeneration:
		return
	root = _foregroundObject()
	title = _windowChatTitle(root) if root is not None else ""
	if not title and root is not None:
		title = _paintedChatTitle(root)
	if title and (title != previousTitle or retriesRemaining <= 0):
		ui.message(title)
		return
	if root is not None and _recognizePaintedChatTitle(
		root,
		generation,
		previousTitle,
		retriesRemaining,
	):
		return
	if retriesRemaining > 0:
		core.callLater(
			_CHAT_SWITCH_ANNOUNCEMENT_RETRY_MS,
			_announceSwitchedChat,
			generation,
			previousTitle,
			retriesRemaining - 1,
		)


def switchChat(gesture: object) -> None:
	"""Pass through Telegram's chat switch, then announce its new chat name."""
	global _chatSwitchGeneration
	root = _foregroundObject()
	previousTitle = _windowChatTitle(root) if root is not None else ""
	if not previousTitle and root is not None:
		previousTitle = _paintedChatTitle(root)
	try:
		cast(Any, gesture).send()
	except Exception:
		return
	_chatSwitchGeneration += 1
	generation = _chatSwitchGeneration
	core.callLater(
		_CHAT_SWITCH_ANNOUNCEMENT_DELAY_MS,
		_announceSwitchedChat,
		generation,
		previousTitle,
		_CHAT_SWITCH_ANNOUNCEMENT_RETRIES,
	)
