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

	@script(
		description=_("Show links and files in the current message"),
		gesture="kb:control+enter",
	)
	def script_showMessageLinks(self, gesture: object) -> None:
		showMessageLinks(gesture)


def _redactedLink(url: str) -> str:
	"""Describe a link for the log without the secrets it may carry.

	Password resets, signed downloads and OAuth callbacks keep their
	credentials in the path, query and fragment, and NVDA logs are routinely
	shared to get help, so only the scheme and host are ever recorded.
	"""
	parts = _URL_PARTS.match(url)
	if parts is None:
		return "<link>"
	return f"{parts['scheme']}{parts['slashes'] or ''}{parts['authority']}"


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
