# A part of Telegram Desktop Accessibility for NVDA
# Copyright (C) 2026 Ken Chang
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""App module for Telegram Desktop."""

from __future__ import annotations

import re
from typing import Any, NamedTuple, cast

import api
import appModuleHandler
import controlTypes
from contentRecog import RecogImageInfo, RecognitionResult
from contentRecog.uwpOcr import UwpOcr
import core
import displayModel
from locationHelper import RectLTRB
from NVDAObjects.UIA import UIA
import queueHandler
import screenBitmap
from scriptHandler import script
import textInfos
import ui
import UIAHandler


_CHAT_LIST_CLASS_NAME = "Dialogs::InnerWidget"
_DIALOGS_WIDGET_CLASS_NAME = "Dialogs::Widget"
_ICON_BUTTON_CLASS_NAME = "Ui::IconButton"
_SIDEBAR_BUTTON_CLASS_NAME = "Ui::SideBarButton"
_HISTORY_TOP_BAR_CLASS_NAME = "HistoryView::TopBarWidget"
_RTTI_CLASS_PREFIXES = ("class ", "struct ")
_CHAT_SWITCH_ANNOUNCEMENT_DELAY_MS = 200
_CHAT_SWITCH_ANNOUNCEMENT_RETRY_MS = 100
_CHAT_SWITCH_ANNOUNCEMENT_RETRIES = 4
_CHAT_TITLE_FORMATTING_TRANSLATION = str.maketrans(
	"",
	"",
	"\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069",
)
# Telegram prefixes its window title with the unread count and appends its own
# application name; the painted header and OCR expose neither.
_UNREAD_COUNT_PREFIX = re.compile(r"^\(\d+\)\s*")
_WINDOW_TITLE_SUFFIX = re.compile(r"\s*[-\u2013\u2014]\s*Telegram(?:\s+Desktop)?$")


_chatSwitchGeneration = 0
_chatTitleRecognizer: UwpOcr | None = None


class _ForegroundIdentity(NamedTuple):
	"""Which foreground window a delayed callback belongs to."""

	windowHandle: int | None
	root: object


class _ChatSwitchContext(NamedTuple):
	"""What one Ctrl+Tab needs in order to announce its own result later.

	Each title source is kept separately: the window name carries decorations
	that the painted header and OCR never show, so comparing a title against
	the previous value of a *different* source reports a change that did not
	happen and announces the chat the user just left.
	"""

	generation: int
	identity: _ForegroundIdentity | None
	previousWindowTitle: str
	previousPaintedTitle: str


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
	chatList = _findTelegramChatList(root)
	topBarButton = _findHistoryTopBarButton(root)
	if chatList is None or topBarButton is None:
		return None
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


def _firstNonEmptyLine(text: str) -> str:
	lines = (_normalizedTitleText(line) for line in text.splitlines())
	return next((line for line in lines if line), "")


def _normalizedTitleText(value: str) -> str:
	"""Drop the bidirectional formatting Telegram wraps around chat names."""
	return value.translate(_CHAT_TITLE_FORMATTING_TRANSLATION).strip()


def _chatNameFromWindowTitle(value: str) -> str:
	"""Reduce a window title to the bare chat name the other sources report."""
	value = _normalizedTitleText(value)
	value = _UNREAD_COUNT_PREFIX.sub("", value)
	return _WINDOW_TITLE_SUFFIX.sub("", value).strip()


def _paintedChatTitle(root: object) -> str:
	"""Read Telegram's painted conversation title through NVDA's display model."""
	rect = _chatTitleRect(root)
	if rect is None:
		return ""
	try:
		# DisplayModelTextInfo takes a text position, and confines itself to the
		# chat-title rectangle through its limit rectangle. Passing the
		# rectangle as the position raises, which would silently reduce this to
		# an empty result on every machine.
		info = displayModel.DisplayModelTextInfo(
			root,
			textInfos.POSITION_ALL,
			limitRect=rect,
		)
		return _firstNonEmptyLine(info.text)
	except Exception:
		return ""


def _windowChatTitle(root: object) -> str:
	"""Read Telegram's current provider-side window name.

	NVDA objects cache UIA properties, so ``root.name`` can still describe the
	previous chat after Telegram has switched.  Query the underlying provider
	first and retain the NVDA property only as a fallback.
	"""
	element = _uiaElement(root)
	name = _rawElementProperty(element, UIAHandler.UIA_NamePropertyId) if element is not None else None
	if not isinstance(name, str) or not name:
		name = _safeStringAttribute(root, "name")
	if not isinstance(name, str):
		return ""
	return _chatNameFromWindowTitle(name)


def _recognitionTitle(result: RecognitionResult | Exception) -> str:
	if isinstance(result, Exception):
		return ""
	try:
		return _firstNonEmptyLine(result.text)
	except Exception:
		return ""


def _handleChatTitleRecognition(
	result: RecognitionResult | Exception,
	context: _ChatSwitchContext,
	retriesRemaining: int,
) -> None:
	"""Handle the asynchronous OCR result on NVDA's main event queue."""
	if context.generation != _chatSwitchGeneration or _telegramWindow(context) is None:
		return
	title = _recognitionTitle(result)
	if title and title != context.previousPaintedTitle:
		ui.message(title)
		return
	if retriesRemaining > 0:
		core.callLater(
			_CHAT_SWITCH_ANNOUNCEMENT_RETRY_MS,
			_announceSwitchedChat,
			context,
			retriesRemaining - 1,
		)


def _recognizePaintedChatTitle(
	root: object,
	context: _ChatSwitchContext,
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
			context,
			retriesRemaining,
		)

	try:
		recognizer.recognize(pixels, imageInfo, onResult)
	except Exception:
		return False
	return True


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
	not, and a delayed announcement can still tell whether it is still reading
	the window that switched chats.
	"""
	root = _foregroundObject()
	if root is None:
		return None
	return _ForegroundIdentity(_windowHandle(root), root)


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

	@script(
		description=_("Switch chats and announce the chat name"),
		gestures=("kb:control+tab", "kb:control+shift+tab"),
	)
	def script_switchChat(self, gesture: object) -> None:
		switchChat(gesture)


def _telegramWindow(context: _ChatSwitchContext) -> object | None:
	"""Return the foreground window only while it is the one that switched.

	Every announcement here runs after a delay, a retry, or an OCR round trip.
	Alt+Tab during any of those would otherwise make this read the title of
	whatever took the foreground and announce it as the new chat, and aim the
	display-model and OCR work at that window too.
	"""
	identity = context.identity
	if identity is None:
		return None
	root = _foregroundObject()
	if root is None:
		return None
	if identity.windowHandle is not None:
		return root if _windowHandle(root) == identity.windowHandle else None
	return root if root is identity.root else None


def _announceSwitchedChat(context: _ChatSwitchContext, retriesRemaining: int) -> None:
	"""Wait for Telegram's window title to update, then announce it."""
	if context.generation != _chatSwitchGeneration:
		return
	root = _telegramWindow(context)
	if root is None:
		return
	title = _windowChatTitle(root)
	if title and title != context.previousWindowTitle:
		ui.message(title)
		return
	# Telegram does not update its top-level UIA name in every environment.
	# Try its painted header even when a non-empty but stale window name exists.
	title = _paintedChatTitle(root)
	if title and title != context.previousPaintedTitle:
		ui.message(title)
		return
	if _recognizePaintedChatTitle(root, context, retriesRemaining):
		return
	if retriesRemaining > 0:
		core.callLater(
			_CHAT_SWITCH_ANNOUNCEMENT_RETRY_MS,
			_announceSwitchedChat,
			context,
			retriesRemaining - 1,
		)


def switchChat(gesture: object) -> None:
	"""Pass through Telegram's chat switch, then announce its new chat name."""
	global _chatSwitchGeneration
	root = _foregroundObject()
	previousWindowTitle = _windowChatTitle(root) if root is not None else ""
	previousPaintedTitle = _paintedChatTitle(root) if root is not None else ""
	identity = _foregroundIdentity()
	try:
		cast(Any, gesture).send()
	except Exception:
		return
	if identity is None:
		# Without an originating window, a later callback could not tell
		# Telegram apart from whatever else takes the foreground.
		return
	_chatSwitchGeneration += 1
	core.callLater(
		_CHAT_SWITCH_ANNOUNCEMENT_DELAY_MS,
		_announceSwitchedChat,
		_ChatSwitchContext(
			_chatSwitchGeneration,
			identity,
			previousWindowTitle,
			previousPaintedTitle,
		),
		_CHAT_SWITCH_ANNOUNCEMENT_RETRIES,
	)
