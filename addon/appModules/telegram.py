# A part of Telegram Desktop Accessibility for NVDA
# Copyright (C) 2026 Ken Chang
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""App module for Telegram Desktop."""

from __future__ import annotations

import os
import re
from typing import Any, NamedTuple, cast
from urllib.parse import unquote
from urllib.request import url2pathname

import api
import appModuleHandler
from comInterfaces.UIAutomationClient import tagPOINT
from contentRecog import RecogImageInfo, RecognitionResult
from contentRecog.uwpOcr import UwpOcr
import controlTypes
import core
import displayModel
from keyboardHandler import KeyboardInputGesture
from locationHelper import RectLTRB
from logHandler import log
from NVDAObjects.UIA import UIA
import queueHandler
import screenBitmap
from scriptHandler import script
import textInfos
import ui
import UIAHandler
import winUser


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
# Telegram keeps its per-folder sidebar buttons inside a scrolled container,
# while the menu button above them is not scrolled with the folder list.
_SCROLLED_CONTAINER_CLASS_NAMES = ("Ui::ScrollArea", "Ui::ElasticScroll", "Ui::VerticalLayout")
_MAX_UIA_PARENT_STEPS = 16
_MAX_SIBLING_STEPS = 32
# Roughly one second of 25 ms polls while waiting for Alt to be released.
_MAX_ALT_RELEASE_POLLS = 40
_mainMenuCloseCounter = 0
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


class _PendingMainMenuClose(NamedTuple):
	"""The single main-menu close operation Alt+1 may have in flight."""

	token: int
	identity: _ForegroundIdentity | None


_pendingMainMenuClose: _PendingMainMenuClose | None = None


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


_HISTORY_LIST_CLASS_NAME = "HistoryView::ListWidget"
_HISTORY_INNER_CLASS_NAME = "HistoryInner"
_MESSAGE_LIST_AUTOMATION_ID = "ChatsList"
_MAX_MESSAGE_TREE_DEPTH = 4
_MAX_MESSAGE_TREE_NODES = 64
# One pass over the message text, so a span can only ever be one kind of thing.
_MESSAGE_TARGET_PATTERN = re.compile(
	r"(?P<uri>(?:(?:https?|ftp|tg|tonsite)://|mailto:)[^\s<>\u200e\u200f]+)"
	r"|(?P<fileUri>file:///[^\s<>\u200e\u200f]+)"
	r"|(?P<unc>\\\\[^\s\\/:*?\"<>|]+(?:\\[^\s\\/:*?\"<>|]+)+)"
	r"|(?P<drive>[A-Za-z]:[\\/][^\s<>\"|*?\u200e\u200f]*)"
	r"|(?P<www>www\.[^\s<>\u200e\u200f]+)"
	r"|(?P<email>(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+)"
	r"|(?P<domain>(?<![\w@.\\/-])(?:[\w-]+\.)+(?P<tld>[A-Za-z0-9]{2,24})"
	r"(?P<domainRest>[/?#][^\s<>\u200e\u200f]*)?)",
	re.IGNORECASE,
)
_URL_TRAILING_PUNCTUATION = ".,;:!?\"'\u2026"
# A scheme-less domain is only a link when Telegram would make it one. A path
# settles it; otherwise the last label has to be a top-level domain rather than
# a file extension, since "example.com" and "report.pdf" have the same shape.
_COMMON_TLDS = frozenset(
	"""
	com net org edu gov mil int info biz name pro xyz online site shop store
	tech blog cloud email live news work world dev app ai gg io co me tv cc
	ru de uk fr it es pl nl br jp cn in ua ca au us be ch at se no fi dk cz
	sk hu ro bg hr rs lt lv ee by kz vn th ph my sg nz za eg sa ae pk bd ng
	ke tr kr mx ar id ir il gr pt ly to sh st is ie lu md ge am az uz kg
	""".split(),
)
_ATTACHMENT_EXTENSIONS = frozenset(
	"""
	pdf doc docx xls xlsx ppt pptx odt ods odp rtf txt md csv json xml yaml
	yml zip rar 7z tar gz bz2 xz iso exe msi apk deb rpm dmg mp3 m4a ogg oga
	opus wav flac aac wma mp4 mkv avi mov webm wmv flv 3gp gif jpg jpeg png
	webp bmp tif tiff svg heic epub mobi fb2 djvu srt vtt torrent log ini cfg
	conf py js ts jsx tsx html htm css c h cpp hpp java kt rs go rb php sh
	ps1 bat psd ai eps sketch fig
	""".split(),
)
_ATTACHMENT_NAME_SEPARATOR = re.compile(r"\s*[,;\u2022\u00b7]\s*|\s{2,}")
_FORBIDDEN_FILE_NAME_CHARACTERS = re.compile(r"[\\/:*?\"<>|]")
_URL_PARTS = re.compile(r"^(?P<scheme>[A-Za-z][\w+.-]*:)(?P<slashes>//)?(?P<authority>[^/?#]*)(?P<rest>.*)$")
_TELEGRAM_DOWNLOAD_DIRECTORIES = (
	# Telegram Desktop's default download location, then the plain Downloads
	# folder that a reconfigured client most often points at.
	("Downloads", "Telegram Desktop"),
	("Downloads",),
	("Documents", "Telegram Desktop"),
)
_messageLinksDialog: Any | None = None


class _MessageTarget(NamedTuple):
	"""One thing in a message that Ctrl+Enter can open.

	``value`` is the URL or path for links and files, and the message's own
	accessible object for an attachment, which Telegram has to open itself
	when it has not been downloaded yet.
	"""

	kind: str
	label: str
	value: object


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


def _linkDedupKey(url: str) -> str:
	"""Fold only the parts of a URL that are defined to be case-insensitive.

	Paths and query values are case-sensitive, so folding a whole URL hides
	``/User`` behind ``/user`` and drops a link the message really contains.
	"""
	parts = _URL_PARTS.match(url)
	if parts is None:
		return url
	return "".join(
		(
			parts["scheme"].casefold(),
			parts["slashes"] or "",
			parts["authority"].casefold(),
			parts["rest"],
		),
	)


def _localPathFromFileUri(uri: str) -> str:
	"""Turn a ``file:///`` URL into the Windows path it names."""
	try:
		return url2pathname(unquote(uri[len("file:") :]))
	except Exception:
		return ""


def _attachmentFileName(text: str) -> str:
	"""Return the attachment file name a Telegram accessible name contains.

	Telegram describes a document as its file name followed by details such as
	the size, so each comma-separated part is considered on its own. A part
	holding a character Windows forbids in a file name is prose rather than a
	document, which keeps a sentence that merely ends in a URL out of this.
	"""
	for part in _ATTACHMENT_NAME_SEPARATOR.split(text.strip()):
		part = part.strip()
		if _FORBIDDEN_FILE_NAME_CHARACTERS.search(part):
			continue
		if "." in part and part.rpartition(".")[2].casefold() in _ATTACHMENT_EXTENSIONS:
			return part
	return ""


def _targetFromMatch(match: re.Match[str]) -> _MessageTarget | None:
	"""Classify one match from the message text, or discard it."""
	value = _stripTrailingUrlPunctuation(match.group(0))
	if not value:
		return None
	if match["uri"]:
		return _MessageTarget("link", value, value)
	if match["fileUri"]:
		path = _localPathFromFileUri(value)
		return _MessageTarget("file", path, path) if path else None
	if match["unc"] or match["drive"]:
		return _MessageTarget("file", value, value)
	if match["www"]:
		return _MessageTarget("link", f"https://{value}", f"https://{value}")
	if match["email"]:
		return _MessageTarget("link", f"mailto:{value}", f"mailto:{value}")
	if not match["domain"]:
		return None
	tld = (match["tld"] or "").casefold()
	if match["domainRest"] or tld in _COMMON_TLDS:
		return _MessageTarget("link", f"https://{value}", f"https://{value}")
	if tld in _ATTACHMENT_EXTENSIONS:
		return _MessageTarget("attachment", value, None)
	return None


def targetsFromMessageText(text: str) -> tuple[_MessageTarget, ...]:
	"""Extract the links, file paths and file names a message mentions."""
	targets: list[_MessageTarget] = []
	seen: set[tuple[str, str]] = set()
	for match in _MESSAGE_TARGET_PATTERN.finditer(text):
		target = _targetFromMatch(match)
		if target is None:
			continue
		key = (
			target.kind,
			_linkDedupKey(target.label) if target.kind == "link" else target.label.casefold(),
		)
		if key not in seen:
			seen.add(key)
			targets.append(target)
	return tuple(targets)


def linksFromMessageText(text: str) -> tuple[str, ...]:
	"""Extract unique, openable links from a message in reading order."""
	return tuple(target.label for target in targetsFromMessageText(text) if target.kind == "link")


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
	"""Return the RTTI class components of an element's UIA AutomationId."""
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
	"""Identify the menu button among the buttons that share its corner.

	A point hit lands on whatever Telegram painted there, and the class name
	alone does not separate the menu from its neighbours: the folder sidebar
	fills the same column with one ``Ui::SideBarButton`` per chat folder, and
	``Dialogs::Widget`` holds further ``Ui::IconButton``s. In both layouts the
	menu button is the first of its class in its container and sits outside the
	scrolled folder list, which is also the button the subtree lookup returns.
	Anything that cannot be identified this way is rejected so the caller falls
	back to that lookup instead of invoking the wrong action.
	"""
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


def _windowTitle(root: object) -> str:
	"""Read Telegram's current provider-side window name as it stands.

	NVDA objects cache UIA properties, so ``root.name`` can still describe the
	previous chat after Telegram has switched.  Query the underlying provider
	first and retain the NVDA property only as a fallback. The title is kept
	whole here: it is what tells one window state from the next, and reducing
	it first would hide a switch between two chats of the same name.
	"""
	element = _uiaElement(root)
	name = _rawElementProperty(element, UIAHandler.UIA_NamePropertyId) if element is not None else None
	if not isinstance(name, str) or not name:
		name = _safeStringAttribute(root, "name")
	if not isinstance(name, str):
		return ""
	return _normalizedTitleText(name)


def _windowChatTitle(root: object) -> str:
	"""Return the chat name Telegram's window title announces."""
	return _chatNameFromWindowTitle(_windowTitle(root))


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
	not, and a delayed callback can still tell whether it is acting on the
	window that scheduled it.
	not, and a delayed announcement can still tell whether it is still reading
	the window that switched chats.
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
		button = _findTelegramMainMenuButtonFromPoints(root) if root is not None else None
		if button is None and root is not None:
			button = _findTelegramMainMenuButton(root)
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

	@script(
		description=_("Show links and files in the current message"),
		gesture="kb:control+enter",
	)
	def script_showMessageLinks(self, gesture: object) -> None:
		showMessageLinks(gesture)


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
	# Telegram's window title also carries the global unread count, which
	# changes on its own while this waits. The chat name alone therefore
	# decides whether to speak: announcing every raw title change would tell
	# the user they had moved to another chat when a message merely arrived
	# somewhere else and Ctrl+Tab had not moved at all. The cost is that a
	# switch between two chats that share a name stays silent, which the title
	# cannot distinguish from no switch; a wrong announcement about where the
	# user is was judged worse than a missing one.
	chatName = _windowChatTitle(root)
	if chatName and chatName != context.previousWindowTitle:
		ui.message(chatName)
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


def _redactedLink(url: str) -> str:
	"""Describe a link for the log without the secrets it may carry.

	Password resets, signed downloads and OAuth callbacks keep their
	credentials in the path, query and fragment, and a URL can carry a user
	name and password in front of its host as well. NVDA logs are routinely
	shared to get help, so only the scheme and host are ever recorded.
	"""
	parts = _URL_PARTS.match(url)
	if parts is None:
		return "<link>"
	host = parts["authority"].rpartition("@")[2]
	return f"{parts['scheme']}{parts['slashes'] or ''}{host}"


def _openMessageLink(url: str) -> None:
	"""Open a link through its Windows-registered handler."""
	log.debug("Telegram opening message link for %s", _redactedLink(url))
	try:
		os.startfile(url)
	except Exception:
		ui.message(_("Unable to open link"))


def _messageDescendants(obj: object) -> tuple[object, ...]:
	"""Return a bounded view of a message's own accessible children.

	Only the message row is walked, and only a few levels of it, so this never
	turns into the recursive descendant expansion the shortcuts avoid.
	"""
	found: list[object] = []
	generation = [obj]
	for _depth in range(_MAX_MESSAGE_TREE_DEPTH):
		nextGeneration: list[object] = []
		for node in generation:
			try:
				children = list(getattr(node, "children"))
			except Exception:
				continue
			for child in children:
				if len(found) >= _MAX_MESSAGE_TREE_NODES:
					return tuple(found)
				found.append(child)
				nextGeneration.append(child)
		if not nextGeneration:
			break
		generation = nextGeneration
	return tuple(found)


def attachmentsFromMessage(focus: object) -> tuple[_MessageTarget, ...]:
	"""Return the documents Telegram exposes on the focused message.

	Only the message's own children are considered. The row's accessible name
	is the whole message, so reading a file name out of it would turn ordinary
	prose that happens to end in one into an attachment; a file name written
	in the text is picked up by the text pass instead.
	"""
	attachments: list[_MessageTarget] = []
	seen: set[str] = set()
	for node in _messageDescendants(focus):
		fileName = _attachmentFileName(_safeStringAttribute(node, "name"))
		key = fileName.casefold()
		if fileName and key not in seen:
			seen.add(key)
			attachments.append(_MessageTarget("attachment", fileName, node))
	return tuple(attachments)


def _downloadedAttachmentPath(fileName: str) -> str:
	"""Find an already-downloaded attachment in Telegram's download folders."""
	if not fileName or os.path.basename(fileName) != fileName:
		return ""
	try:
		home = os.path.expanduser("~")
	except Exception:
		return ""
	for directory in _TELEGRAM_DOWNLOAD_DIRECTORIES:
		candidate = os.path.join(home, *directory, fileName)
		try:
			if os.path.isfile(candidate):
				return candidate
		except Exception:
			continue
	return ""


def _openLocalFile(path: str) -> bool:
	log.debug("Telegram opening a message file named %s", os.path.basename(path))
	try:
		os.startfile(path)
		return True
	except Exception:
		return False


def _openMessageFile(path: str) -> None:
	"""Open a file path a message mentions, if it still exists."""
	try:
		exists = os.path.exists(path)
	except Exception:
		exists = False
	if not exists:
		ui.message(_("File not found"))
		return
	if not _openLocalFile(path):
		ui.message(_("Unable to open file"))


def _openMessageAttachment(target: _MessageTarget) -> None:
	"""Open a Telegram attachment, downloading it through Telegram if needed."""
	path = _downloadedAttachmentPath(target.label)
	if path:
		if _openLocalFile(path):
			return
		ui.message(_("Unable to open file"))
		return
	element = _uiaElement(target.value) if target.value is not None else None
	if element is not None and _invokeElement(element):
		# Telegram itself downloads the attachment and then opens it.
		return
	ui.message(_("File is not downloaded yet"))


def _openMessageTarget(target: _MessageTarget) -> None:
	if target.kind == "link":
		_openMessageLink(cast(str, target.value))
	elif target.kind == "file":
		_openMessageFile(cast(str, target.value))
	else:
		_openMessageAttachment(target)


def _showMessageLinksMenu(targets: tuple[_MessageTarget, ...]) -> None:
	"""Show a non-blocking NVDA-owned chooser containing the message targets."""
	global _messageLinksDialog
	log.debug("Telegram link chooser opening with %d item(s)", len(targets))
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
				_("Select a link or file to open"),
				_("Links and files in message"),
				[target.label for target in targets],
			)
			_messageLinksDialog = dialog
			dialog.SetSelection(0)
			selectedIndex = 0

			def onSelect(event: object) -> None:
				nonlocal selectedIndex
				selection = cast(Any, event).GetSelection()
				if 0 <= selection < len(targets):
					selectedIndex = selection

			def onOpen(event: object) -> None:
				selectedTarget = targets[selectedIndex]
				dialog.Close()
				wx.CallAfter(_openMessageTarget, selectedTarget)

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
		ui.message(_("Unable to show links and files"))


def _sendGesture(gesture: object) -> None:
	try:
		cast(Any, gesture).send()
	except Exception:
		pass


def _mergedMessageTargets(
	textTargets: tuple[_MessageTarget, ...],
	attachments: tuple[_MessageTarget, ...],
) -> tuple[_MessageTarget, ...]:
	"""Prefer an attachment Telegram can act on over the same bare file name."""
	byName = {target.label.casefold(): target for target in attachments}
	merged: list[_MessageTarget] = []
	used: set[str] = set()
	for target in textTargets:
		key = target.label.casefold()
		replacement = byName.get(key) if target.kind == "attachment" else None
		if replacement is not None:
			used.add(key)
			merged.append(replacement)
		else:
			merged.append(target)
	merged.extend(target for target in attachments if target.label.casefold() not in used)
	return tuple(merged)


def messageTargets(focus: object) -> tuple[_MessageTarget, ...]:
	"""Return everything Ctrl+Enter can open on the focused message."""
	element = _uiaElement(focus)
	text = _rawElementProperty(element, UIAHandler.UIA_NamePropertyId) if element is not None else None
	if not isinstance(text, str) or not text:
		text = _safeStringAttribute(focus, "name")
	return _mergedMessageTargets(targetsFromMessageText(text), attachmentsFromMessage(focus))


def showMessageLinks(gesture: object) -> None:
	"""Open what the focused message holds, preserving Ctrl+Enter elsewhere."""
	focus = _focusObject()
	if focus is None or not isTelegramMessage(focus):
		_sendGesture(gesture)
		return
	targets = messageTargets(focus)
	log.debug(
		"Telegram message holds %d link(s) and %d file(s)",
		sum(1 for target in targets if target.kind == "link"),
		sum(1 for target in targets if target.kind != "link"),
	)
	if not targets:
		ui.message(_("No links or files in this message"))
		return
	if len(targets) == 1:
		_openMessageTarget(targets[0])
		return
	core.callLater(0, _showMessageLinksMenu, targets)
