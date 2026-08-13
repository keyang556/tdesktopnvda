from __future__ import annotations

from enum import Enum
import importlib.util
from pathlib import Path
import sys
import types
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "addon" / "appModules" / "telegram.py"

_CLASS_NAME = "className"
_AUTOMATION_ID = "automationId"
_CONTROL_TYPE = "controlType"
_IS_OFFSCREEN = "isOffscreen"
_IS_SELECTED = "isSelected"
_NAME = "name"

_BUTTON_CONTROL = "buttonControl"
_LIST_CONTROL = "listControl"
_LIST_ITEM_CONTROL = "listItemControl"

_TREE_SCOPE_CHILDREN = 2
_TREE_SCOPE_DESCENDANTS = 4
_TREE_SCOPE_SUBTREE = 7


class _Role(Enum):
	LIST = "list"
	LISTITEM = "listItem"
	BUTTON = "button"
	MENUBUTTON = "menuButton"
	DROPDOWNBUTTON = "dropDownButton"


class _State(Enum):
	SELECTED = "selected"
	HASPOPUP = "hasPopup"


class _FakeCondition:
	def __init__(self, predicate):
		self._predicate = predicate

	def matches(self, element):
		return self._predicate(element)


class _FakeWalker:
	def GetParentElement(self, element):
		return element.parent

	def _siblings(self, element):
		parent = element.parent
		return parent.children if parent is not None else [element]

	def GetPreviousSiblingElement(self, element):
		siblings = self._siblings(element)
		index = siblings.index(element)
		return siblings[index - 1] if index > 0 else None

	def GetNextSiblingElement(self, element):
		siblings = self._siblings(element)
		index = siblings.index(element)
		return siblings[index + 1] if index + 1 < len(siblings) else None


class _FakeClient:
	RawViewWalker = _FakeWalker()

	def CreatePropertyCondition(self, propertyId, value):
		return _FakeCondition(lambda element: element.propertyValue(propertyId) == value)

	def CreatePropertyConditionEx(self, propertyId, value, flags):
		assert flags == 2
		return _FakeCondition(lambda element: value in str(element.propertyValue(propertyId)))

	def CreateAndConditionFromArray(self, conditions):
		return _FakeCondition(lambda element: all(condition.matches(element) for condition in conditions))

	def CreateOrConditionFromArray(self, conditions):
		return _FakeCondition(lambda element: any(condition.matches(element) for condition in conditions))

	def CompareElements(self, left, right):
		return left is right


class _FakeInvokePattern:
	def __init__(self, element):
		self._element = element

	def QueryInterface(self, interface):
		return self

	def Invoke(self):
		if self._element.failAction:
			raise RuntimeError("provider action failed")
		self._element.actionCount += 1


class _FakeUIA:
	def __init__(
		self,
		*,
		role=None,
		name="",
		className="",
		automationId="",
		states=None,
		children=None,
		isOffscreen=False,
		failQuery=False,
		failAction=False,
		failFocus=False,
		windowHandle=1,
	):
		self.windowHandle = windowHandle
		self.role = role
		self.name = name
		self.UIAClassName = className
		self.UIAAutomationId = automationId
		self.states = set(states or ())
		self.children = list(children or ())
		self.parent = None
		for child in self.children:
			child.parent = self
		self.isOffscreen = isOffscreen
		self.failQuery = failQuery
		self.failAction = failAction
		self.failFocus = failFocus
		self.focused = False
		self.actionCount = 0
		self.UIAElement = self

	@property
	def cachedName(self):
		return self.name

	@property
	def recursiveDescendants(self):
		raise AssertionError("scripts must not expand recursiveDescendants")

	def propertyValue(self, propertyId):
		controlTypes = {
			_Role.BUTTON: _BUTTON_CONTROL,
			_Role.MENUBUTTON: _BUTTON_CONTROL,
			_Role.DROPDOWNBUTTON: _BUTTON_CONTROL,
			_Role.LIST: _LIST_CONTROL,
			_Role.LISTITEM: _LIST_ITEM_CONTROL,
		}
		values = {
			_CLASS_NAME: self.UIAClassName,
			_AUTOMATION_ID: self.UIAAutomationId,
			_CONTROL_TYPE: controlTypes.get(self.role),
			_IS_OFFSCREEN: self.isOffscreen,
			_IS_SELECTED: _State.SELECTED in self.states,
			_NAME: self.name,
		}
		return values.get(propertyId)

	def _descendants(self):
		for child in self.children:
			yield child
			yield from child._descendants()

	def FindFirstBuildCache(self, scope, condition, cacheRequest):
		if self.failQuery:
			raise RuntimeError("provider query failed")
		if scope == _TREE_SCOPE_CHILDREN:
			nodes = iter(self.children)
		elif scope == _TREE_SCOPE_DESCENDANTS:
			nodes = self._descendants()
		elif scope == _TREE_SCOPE_SUBTREE:
			nodes = iter((self, *self._descendants()))
		else:
			raise AssertionError(f"unexpected tree scope: {scope}")
		return next((node for node in nodes if condition.matches(node)), None)

	def GetCurrentPropertyValue(self, propertyId):
		return self.propertyValue(propertyId)

	def GetCurrentPattern(self, patternId):
		return _FakeInvokePattern(self)

	def SetFocus(self):
		if self.failFocus:
			raise RuntimeError("provider focus failed")
		self.focused = True


def _loadTelegramModule():
	api = types.ModuleType("api")
	api.focusObject = None
	api.foregroundObject = None
	api.getFocusObject = lambda: api.focusObject
	api.getForegroundObject = lambda: api.foregroundObject

	appModuleHandler = types.ModuleType("appModuleHandler")
	appModuleHandler.AppModule = object

	controlTypes = types.ModuleType("controlTypes")
	controlTypes.Role = _Role
	controlTypes.State = _State

	nvdaObjects = types.ModuleType("NVDAObjects")
	uiaModule = types.ModuleType("NVDAObjects.UIA")
	uiaModule.UIA = _FakeUIA

	def fakeScript(*, description, gesture=None, gestures=None):
		def decorator(function):
			function.__doc__ = description
			function.gesture = gesture
			function.gestures = gestures
			return function

		return decorator

	scriptHandler = types.ModuleType("scriptHandler")
	scriptHandler.script = fakeScript

	ui = types.ModuleType("ui")
	ui.messages = []
	ui.message = ui.messages.append

	uiaHandler = types.ModuleType("UIAHandler")
	uiaHandler.UIA_ClassNamePropertyId = _CLASS_NAME
	uiaHandler.UIA_AutomationIdPropertyId = _AUTOMATION_ID
	uiaHandler.UIA_ControlTypePropertyId = _CONTROL_TYPE
	uiaHandler.UIA_IsOffscreenPropertyId = _IS_OFFSCREEN
	uiaHandler.UIA_SelectionItemIsSelectedPropertyId = _IS_SELECTED
	uiaHandler.UIA_NamePropertyId = _NAME
	uiaHandler.UIA_ButtonControlTypeId = _BUTTON_CONTROL
	uiaHandler.UIA_ListControlTypeId = _LIST_CONTROL
	uiaHandler.UIA_ListItemControlTypeId = _LIST_ITEM_CONTROL
	uiaHandler.UIA_InvokePatternId = "invokePattern"
	uiaHandler.IUIAutomationInvokePattern = object
	uiaHandler.PropertyConditionFlags_MatchSubstring = 2
	uiaHandler.TreeScope_Children = _TREE_SCOPE_CHILDREN
	uiaHandler.TreeScope_Descendants = _TREE_SCOPE_DESCENDANTS
	uiaHandler.TreeScope_Subtree = _TREE_SCOPE_SUBTREE
	uiaHandler.handler = types.SimpleNamespace(
		clientObject=_FakeClient(),
		baseCacheRequest=object(),
	)

	comInterfaces = types.ModuleType("comInterfaces")
	uiaClient = types.ModuleType("comInterfaces.UIAutomationClient")
	uiaClient.tagPOINT = lambda x, y: types.SimpleNamespace(x=x, y=y)
	contentRecog = types.ModuleType("contentRecog")
	contentRecog.RecogImageInfo = type("RecogImageInfo", (), {})
	contentRecog.RecognitionResult = object
	uwpOcr = types.ModuleType("contentRecog.uwpOcr")
	uwpOcr.UwpOcr = type("UwpOcr", (), {})

	core = types.ModuleType("core")
	core.calls = []
	core.callLater = lambda delay, function, *args: core.calls.append((delay, function, args))

	keyboardHandler = types.ModuleType("keyboardHandler")
	keyboardHandler.KeyboardInputGesture = type("KeyboardInputGesture", (), {})

	winUser = types.ModuleType("winUser")
	winUser.VK_MENU = 0x12
	winUser.getAsyncKeyState = lambda key: 0
	displayModel = types.ModuleType("displayModel")
	displayModel.calls = []
	# None reproduces a machine where the display model cannot be read.
	displayModel.paintedText = None

	class _FakeDisplayModelTextInfo:
		def __init__(self, obj, position, limitRect=None):
			displayModel.calls.append((obj, position, limitRect))
			if displayModel.paintedText is None:
				raise RuntimeError("display model unavailable in isolated tests")
			self.text = displayModel.paintedText

	displayModel.DisplayModelTextInfo = _FakeDisplayModelTextInfo

	textInfos = types.ModuleType("textInfos")
	textInfos.POSITION_ALL = "positionAll"

	locationHelper = types.ModuleType("locationHelper")

	class _RectLTRB:
		def __init__(self, left, top, right, bottom):
			self.left = left
			self.top = top
			self.right = right
			self.bottom = bottom

	locationHelper.RectLTRB = _RectLTRB

	queueHandler = types.ModuleType("queueHandler")
	queueHandler.eventQueue = object()
	queueHandler.queueFunction = lambda queue, function, *args: function(*args)

	screenBitmap = types.ModuleType("screenBitmap")
	screenBitmap.ScreenBitmap = type("ScreenBitmap", (), {})
	logHandler = types.ModuleType("logHandler")
	logHandler.log = types.SimpleNamespace(
		debug=lambda *args, **kwargs: None,
		exception=lambda *args, **kwargs: None,
	)

	stubs = {
		"api": api,
		"appModuleHandler": appModuleHandler,
		"comInterfaces": comInterfaces,
		"comInterfaces.UIAutomationClient": uiaClient,
		"contentRecog": contentRecog,
		"contentRecog.uwpOcr": uwpOcr,
		"controlTypes": controlTypes,
		"core": core,
		"keyboardHandler": keyboardHandler,
		"displayModel": displayModel,
		"locationHelper": locationHelper,
		"logHandler": logHandler,
		"NVDAObjects": nvdaObjects,
		"NVDAObjects.UIA": uiaModule,
		"queueHandler": queueHandler,
		"screenBitmap": screenBitmap,
		"scriptHandler": scriptHandler,
		"textInfos": textInfos,
		"ui": ui,
		"UIAHandler": uiaHandler,
		"winUser": winUser,
	}
	previous = {name: sys.modules.get(name) for name in stubs}
	sys.modules.update(stubs)
	try:
		spec = importlib.util.spec_from_file_location("telegram_app_module_under_test", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		module._ = lambda message: message
		assert spec.loader is not None
		spec.loader.exec_module(module)
		module._testApi = api
		module._testCore = core
		module._testDisplayModel = displayModel
		module._testUi = ui
		return module
	finally:
		for name, value in previous.items():
			if value is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = value


class TelegramAppModuleTests(unittest.TestCase):
	def setUp(self):
		self.module = _loadTelegramModule()

	def test_chat_list_is_detected_by_msvc_rtti_class_name(self):
		chatList = _FakeUIA(role=_Role.LIST, name="聊天", className="class Dialogs::InnerWidget")

		self.assertTrue(self.module.isTelegramChatList(chatList))

	def test_chat_list_detection_does_not_depend_on_accessible_name(self):
		chatList = _FakeUIA(role=_Role.LIST, name="Chats", className="class Settings::InnerWidget")

		self.assertFalse(self.module.isTelegramChatList(chatList))

	def test_chat_list_detection_requires_list_role(self):
		obj = _FakeUIA(role=_Role.BUTTON, className="class Dialogs::InnerWidget")

		self.assertFalse(self.module.isTelegramChatList(obj))

	def test_alt_1_focuses_selected_chat_and_preserves_telegram_name(self):
		first = _FakeUIA(role=_Role.LISTITEM, name="Alice")
		selected = _FakeUIA(role=_Role.LISTITEM, name="已儲存的訊息", states={_State.SELECTED})
		chatList = _FakeUIA(
			role=_Role.LIST,
			name="聊天",
			className="class Dialogs::InnerWidget",
			children=[first, selected],
		)
		self.module._testApi.foregroundObject = _FakeUIA(children=[chatList])

		self.module.AppModule().script_focusChatList(None)

		self.assertFalse(first.focused)
		self.assertTrue(selected.focused)
		self.assertEqual(selected.name, "已儲存的訊息")

	def test_alt_1_falls_back_to_first_chat(self):
		first = _FakeUIA(role=_Role.LISTITEM, name="Alice")
		chatList = _FakeUIA(
			role=_Role.LIST,
			className="Dialogs::InnerWidget",
			children=[first],
		)
		self.module._testApi.foregroundObject = chatList

		self.module.AppModule().script_focusChatList(None)

		self.assertTrue(first.focused)

	def test_alt_1_repeats_current_telegram_chat_name(self):
		current = _FakeUIA(role=_Role.LISTITEM, name="Saved Messages")
		chatList = _FakeUIA(
			role=_Role.LIST,
			className="class Dialogs::InnerWidget",
			children=[current],
		)
		self.module._testApi.foregroundObject = chatList
		self.module._testApi.focusObject = current

		self.module.AppModule().script_focusChatList(None)

		self.assertEqual(self.module._testUi.messages, ["Saved Messages"])

	def test_alt_1_repeats_current_chat_name_without_searching_again(self):
		current = _FakeUIA(role=_Role.LISTITEM, name="Saved Messages")
		_FakeUIA(
			role=_Role.LIST,
			className="class Dialogs::InnerWidget",
			children=[current],
		)
		self.module._testApi.focusObject = current
		self.module._testApi.foregroundObject = _FakeUIA(failQuery=True)

		self.module.AppModule().script_focusChatList(None)

		self.assertEqual(self.module._testUi.messages, ["Saved Messages"])

	def _focusOpenMainMenu(self, windowHandle=1):
		self.module._testApi.foregroundObject = _FakeUIA(windowHandle=windowHandle)
		self.module._testApi.focusObject = _FakeUIA(
			role=_Role.BUTTON,
			automationId="class Window::MainMenu.class Ui::IconButton",
			windowHandle=windowHandle,
		)

	def test_alt_1_closes_the_main_menu_before_looking_for_the_chat_list(self):
		self._focusOpenMainMenu()

		self.module.AppModule().script_focusChatList(None)

		self.assertEqual(len(self.module._testCore.calls), 1)
		_, callback, _args = self.module._testCore.calls[0]
		self.assertIs(callback, self.module._closeMainMenuAndFocusChatList)

	def test_alt_1_waits_for_the_alt_key_before_sending_escape(self):
		self._focusOpenMainMenu()
		self.module.winUser.getAsyncKeyState = lambda key: 0x8000
		self.module.AppModule().script_focusChatList(None)
		self.module._testCore.calls.clear()
		token, identity = self.module._pendingMainMenuClose

		self.module._closeMainMenuAndFocusChatList(token, identity)

		self.assertEqual(len(self.module._testCore.calls), 1)
		_, callback, _args = self.module._testCore.calls[0]
		self.assertIs(callback, self.module._closeMainMenuAndFocusChatList)

	def test_held_alt_1_schedules_a_single_menu_close(self):
		self._focusOpenMainMenu()
		appModule = self.module.AppModule()

		for _repeat in range(5):
			appModule.script_focusChatList(None)

		self.assertEqual(len(self.module._testCore.calls), 1)

	def test_superseded_menu_close_callback_does_nothing(self):
		self._focusOpenMainMenu()
		self.module.AppModule().script_focusChatList(None)
		token, identity = self.module._pendingMainMenuClose
		self.module._pendingMainMenuClose = None
		self.module._testCore.calls.clear()

		self.module._closeMainMenuAndFocusChatList(token, identity)

		self.assertEqual(self.module._testCore.calls, [])
		self.assertEqual(self.module._testUi.messages, [])

	def test_menu_close_is_abandoned_when_another_window_takes_the_foreground(self):
		self._focusOpenMainMenu(windowHandle=11)
		self.module.AppModule().script_focusChatList(None)
		token, identity = self.module._pendingMainMenuClose
		self.module._testCore.calls.clear()
		self.module._testApi.foregroundObject = _FakeUIA(windowHandle=22)

		self.module._closeMainMenuAndFocusChatList(token, identity)

		self.assertEqual(self.module._testCore.calls, [])
		self.assertEqual(self.module._testUi.messages, [])
		self.assertIsNone(self.module._pendingMainMenuClose)

	def test_menu_close_is_abandoned_when_the_window_exposes_no_handle(self):
		# A provider that reports no window handle must not disable the guard.
		self._focusOpenMainMenu(windowHandle=None)
		self.module.AppModule().script_focusChatList(None)
		token, identity = self.module._pendingMainMenuClose
		self.module._testCore.calls.clear()
		self.module._testApi.foregroundObject = _FakeUIA(windowHandle=None)

		self.module._closeMainMenuAndFocusChatList(token, identity)

		self.assertEqual(self.module._testCore.calls, [])
		self.assertEqual(self.module._testUi.messages, [])
		self.assertIsNone(self.module._pendingMainMenuClose)

	def test_delayed_retry_is_abandoned_when_another_window_takes_the_foreground(self):
		identity = self.module._ForegroundIdentity(11, _FakeUIA(windowHandle=11))
		self.module._testApi.foregroundObject = _FakeUIA(windowHandle=22)

		self.module.focusChatList(closeMainMenu=False, identity=identity)

		self.assertEqual(self.module._testUi.messages, [])

	def test_alt_1_reports_empty_chat_list(self):
		self.module._testApi.foregroundObject = _FakeUIA(
			role=_Role.LIST,
			className="class Dialogs::InnerWidget",
		)

		self.module.AppModule().script_focusChatList(None)

		self.assertEqual(self.module._testUi.messages, ["Chat list is empty"])

	def test_alt_1_does_not_match_localized_name_without_class(self):
		self.module._testApi.foregroundObject = _FakeUIA(role=_Role.LIST, name="Chats")

		self.module.AppModule().script_focusChatList(None)

		self.assertEqual(self.module._testUi.messages, ["Chat list not found"])

	def test_alt_1_contains_native_provider_query_failure(self):
		self.module._testApi.foregroundObject = _FakeUIA(failQuery=True)

		self.module.AppModule().script_focusChatList(None)

		self.assertEqual(self.module._testUi.messages, ["Chat list not found"])

	def test_main_menu_is_detected_by_role_class_and_dialogs_chain(self):
		button = _FakeUIA(
			role=_Role.MENUBUTTON,
			name="主選單",
			className="class Ui::IconButton",
			automationId="class Window::MainWindow.class Dialogs::Widget.class Ui::RpWidget.class Ui::IconButton",
		)

		self.assertTrue(self.module.isTelegramMainMenuButton(button))

	def test_main_menu_regular_button_with_has_popup_is_supported(self):
		button = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
			states={_State.HASPOPUP},
		)

		self.assertTrue(self.module.isTelegramMainMenuButton(button))

	def test_other_menu_button_is_not_mistaken_for_main_menu(self):
		button = _FakeUIA(
			role=_Role.MENUBUTTON,
			className="class Ui::IconButton",
			automationId="class Calls::Panel.class Ui::IconButton",
		)

		self.assertFalse(self.module.isTelegramMainMenuButton(button))

	def test_alt_m_activates_first_matching_button_without_changing_name(self):
		button = _FakeUIA(
			role=_Role.BUTTON,
			name="主選單",
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::RpWidget.class Ui::IconButton",
		)
		other = _FakeUIA(
			role=_Role.BUTTON,
			name="搜尋",
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::RpWidget.class Ui::IconButton",
		)
		self.module._testApi.foregroundObject = _FakeUIA(children=[button, other])

		self.module.AppModule().script_openMainMenu(None)

		self.assertEqual(button.actionCount, 1)
		self.assertEqual(other.actionCount, 0)
		self.assertEqual(button.name, "主選單")

	def test_alt_m_prefers_folder_sidebar_main_menu_over_search_button(self):
		search = _FakeUIA(
			role=_Role.BUTTON,
			name="搜尋",
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::RpWidget.class Ui::IconButton",
		)
		sidebarMenu = _FakeUIA(
			role=_Role.BUTTON,
			name="主選單",
			className="class Ui::SideBarButton",
			automationId="class Ui::RpWidget.class Ui::SideBarButton",
		)
		self.module._testApi.foregroundObject = _FakeUIA(children=[search, sidebarMenu])

		self.module.AppModule().script_openMainMenu(None)

		self.assertEqual(sidebarMenu.actionCount, 1)
		self.assertEqual(search.actionCount, 0)

	def test_point_lookup_accepts_both_main_menu_layouts(self):
		sidebarMenu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::SideBarButton",
			automationId="class MainWindow.class Ui::RpWidget.class Ui::SideBarButton",
		)
		_FakeUIA(children=[sidebarMenu])
		dialogsMenu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::RpWidget.class Ui::IconButton",
		)
		_FakeUIA(children=[dialogsMenu])

		self.assertTrue(self.module._isRawTelegramMainMenuButton(sidebarMenu))
		self.assertTrue(self.module._isRawTelegramMainMenuButton(dialogsMenu))

	def test_point_lookup_rejects_offscreen_and_unrelated_buttons(self):
		offscreen = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::SideBarButton",
			isOffscreen=True,
		)
		unrelated = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Calls::Panel.class Ui::IconButton",
		)
		notAButton = _FakeUIA(role=_Role.LIST, className="class Ui::SideBarButton")
		for element in (offscreen, unrelated, notAButton):
			_FakeUIA(children=[element])

		self.assertFalse(self.module._isRawTelegramMainMenuButton(offscreen))
		self.assertFalse(self.module._isRawTelegramMainMenuButton(unrelated))
		self.assertFalse(self.module._isRawTelegramMainMenuButton(notAButton))

	def test_point_lookup_rejects_later_sidebar_folder_buttons(self):
		menu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::SideBarButton",
			automationId="class MainWindow.class Ui::RpWidget.class Ui::SideBarButton",
		)
		folder = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::SideBarButton",
			automationId="class MainWindow.class Ui::RpWidget.class Ui::SideBarButton",
		)
		_FakeUIA(children=[menu, folder])

		self.assertTrue(self.module._isRawTelegramMainMenuButton(menu))
		self.assertFalse(self.module._isRawTelegramMainMenuButton(folder))

	def test_point_lookup_rejects_scrolled_sidebar_folder_buttons(self):
		folder = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::SideBarButton",
			automationId=(
				"class MainWindow.class Ui::RpWidget.class Ui::ScrollArea."
				"class Ui::VerticalLayout.class Ui::SideBarButton"
			),
		)
		_FakeUIA(children=[folder])

		self.assertFalse(self.module._isRawTelegramMainMenuButton(folder))

	def test_point_lookup_falls_back_when_a_neighbouring_button_is_hit(self):
		menu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
		)
		neighbour = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
		)
		window = _FakeUIA(children=[menu, neighbour])
		window.location = types.SimpleNamespace(left=0, top=0, width=1200, height=800)
		self.module._testApi.foregroundObject = window
		self.module._uiaHandler().clientObject.ElementFromPoint = lambda point: neighbour

		self.module.AppModule().script_openMainMenu(None)

		self.assertEqual(menu.actionCount, 1)
		self.assertEqual(neighbour.actionCount, 0)

	def test_alt_m_ignores_offscreen_button(self):
		button = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
			isOffscreen=True,
		)
		self.module._testApi.foregroundObject = _FakeUIA(children=[button])

		self.module.AppModule().script_openMainMenu(None)

		self.assertEqual(button.actionCount, 0)
		self.assertEqual(self.module._testUi.messages, ["Main menu is not available"])

	def test_alt_m_reports_when_main_menu_is_unavailable(self):
		self.module._testApi.foregroundObject = _FakeUIA()

		self.module.AppModule().script_openMainMenu(None)

		self.assertEqual(self.module._testUi.messages, ["Main menu is not available"])

	def test_alt_m_contains_provider_action_failure(self):
		button = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
			failAction=True,
		)
		self.module._testApi.foregroundObject = button

		self.module.AppModule().script_openMainMenu(None)

		self.assertEqual(self.module._testUi.messages, ["Main menu is not available"])

	def test_shortcut_scripts_do_not_expand_recursive_descendants(self):
		chat = _FakeUIA(role=_Role.LISTITEM, name="Alice")
		chatList = _FakeUIA(
			role=_Role.LIST,
			className="class Dialogs::InnerWidget",
			children=[chat],
		)
		self.module._testApi.foregroundObject = _FakeUIA(children=[chatList])

		self.module.AppModule().script_focusChatList(None)

		self.assertTrue(chat.focused)

	def test_shortcut_gestures_match_unigram_plus(self):
		self.assertEqual(self.module.AppModule.script_focusChatList.gesture, "kb:alt+1")
		self.assertEqual(self.module.AppModule.script_openMainMenu.gesture, "kb:alt+m")
		self.assertEqual(
			self.module.AppModule.script_switchChat.gestures,
			("kb:control+tab", "kb:control+shift+tab"),
		)

	def test_control_tab_announces_updated_window_chat_title(self):
		window = _FakeUIA(name="\u200eOld chat")
		self.module._testApi.foregroundObject = window

		class _Gesture:
			def send(self):
				window.name = "\u200eSaved Messages"

		self.module.switchChat(_Gesture())
		self.assertEqual(len(self.module._testCore.calls), 1)
		_, callback, args = self.module._testCore.calls.pop()
		callback(*args)

		self.assertEqual(self.module._testUi.messages, ["Saved Messages"])

	def test_control_tab_reads_current_provider_name_instead_of_cached_name(self):
		providerWindow = _FakeUIA(name="Old chat")
		window = _FakeUIA(name="Old chat")
		window.UIAElement = providerWindow
		self.module._testApi.foregroundObject = window

		class _Gesture:
			def send(self):
				providerWindow.name = "Saved Messages"

		self.module.switchChat(_Gesture())
		_, callback, args = self.module._testCore.calls.pop()
		callback(*args)

		self.assertEqual(self.module._testUi.messages, ["Saved Messages"])

	def test_control_tab_uses_painted_title_when_window_name_is_stale(self):
		window = _FakeUIA(name="Old chat")
		self.module._testApi.foregroundObject = window
		painted = ["Old chat"]
		self.module._paintedChatTitle = lambda root: painted[0]

		class _Gesture:
			def send(self):
				painted[0] = "Saved Messages"

		self.module.switchChat(_Gesture())
		_, callback, args = self.module._testCore.calls.pop()
		callback(*args)

		self.assertEqual(self.module._testUi.messages, ["Saved Messages"])

	def test_control_tab_never_announces_previous_title_after_retries(self):
		window = _FakeUIA(name="Old chat")
		self.module._testApi.foregroundObject = window
		self.module._paintedChatTitle = lambda root: "Old chat"
		self.module._recognizePaintedChatTitle = lambda *args: False

		class _Gesture:
			def send(self):
				pass

		self.module.switchChat(_Gesture())
		while self.module._testCore.calls:
			_, callback, args = self.module._testCore.calls.pop(0)
			callback(*args)

		self.assertEqual(self.module._testUi.messages, [])

	def test_control_tab_does_not_speak_a_painted_title_it_could_not_read_before(self):
		# The display model was unreadable when the switch started, so the first
		# painted title it does return proves nothing on its own; here it still
		# shows the chat the user was already in.
		window = _FakeUIA(name="Old chat - Telegram")
		self.module._testApi.foregroundObject = window
		painted = [""]
		self.module._paintedChatTitle = lambda root: painted[0]
		self.module._recognizePaintedChatTitle = lambda *args: False

		class _Gesture:
			def send(self):
				painted[0] = "Old chat"

		self.module.switchChat(_Gesture())
		while self.module._testCore.calls:
			_, callback, args = self.module._testCore.calls.pop(0)
			callback(*args)

		self.assertEqual(self.module._testUi.messages, [])

	def test_control_tab_speaks_a_painted_title_that_differs_from_the_window_name(self):
		window = _FakeUIA(name="Old chat - Telegram")
		self.module._testApi.foregroundObject = window
		painted = [""]
		self.module._paintedChatTitle = lambda root: painted[0]
		self.module._recognizePaintedChatTitle = lambda *args: False

		class _Gesture:
			def send(self):
				painted[0] = "Saved Messages"

		self.module.switchChat(_Gesture())
		_, callback, args = self.module._testCore.calls.pop(0)
		callback(*args)

		self.assertEqual(self.module._testUi.messages, ["Saved Messages"])

	def test_control_tab_stays_silent_when_only_the_unread_count_changed(self):
		# Telegram's window title carries the global unread count, which moves
		# on its own. Speaking that change would tell the user they had
		# switched chats when Ctrl+Tab had not moved at all.
		window = _FakeUIA(name="Old chat - Telegram")
		self.module._testApi.foregroundObject = window
		self.module._paintedChatTitle = lambda root: ""
		self.module._recognizePaintedChatTitle = lambda *args: False

		class _Gesture:
			def send(self):
				window.name = "(1) Old chat - Telegram"

		self.module.switchChat(_Gesture())
		while self.module._testCore.calls:
			_, callback, args = self.module._testCore.calls.pop(0)
			callback(*args)

		self.assertEqual(self.module._testUi.messages, [])

	def test_control_tab_does_not_report_a_stale_window_title_as_a_new_chat(self):
		# The window name keeps Telegram's own decorations while the painted
		# header and OCR expose the bare chat name, so the two must never be
		# compared with each other.
		window = _FakeUIA(name="(3) Old chat - Telegram")
		self.module._testApi.foregroundObject = window
		self.module._paintedChatTitle = lambda root: "Old chat"
		self.module._recognizePaintedChatTitle = lambda *args: False

		class _Gesture:
			def send(self):
				pass

		self.module.switchChat(_Gesture())
		while self.module._testCore.calls:
			_, callback, args = self.module._testCore.calls.pop(0)
			callback(*args)

		self.assertEqual(self.module._testUi.messages, [])

	def test_window_titles_are_reduced_to_the_chat_name(self):
		self.assertEqual(
			self.module._windowChatTitle(_FakeUIA(name="(12) Saved Messages — Telegram")),
			"Saved Messages",
		)
		self.assertEqual(
			self.module._windowChatTitle(_FakeUIA(name="Saved Messages - Telegram Desktop")),
			"Saved Messages",
		)
		self.assertEqual(self.module._windowChatTitle(_FakeUIA(name="Saved Messages")), "Saved Messages")

	def test_painted_title_limits_the_display_model_to_the_title_rectangle(self):
		rect = self.module.RectLTRB(10, 20, 300, 60)
		self.module._chatTitleRect = lambda root: rect
		self.module._testDisplayModel.paintedText = "\n Saved Messages \nunread\n"
		window = _FakeUIA()

		self.assertEqual(self.module._paintedChatTitle(window), "Saved Messages")
		self.assertEqual(
			self.module._testDisplayModel.calls,
			[(window, self.module.textInfos.POSITION_ALL, rect)],
		)

	def test_control_tab_abandons_the_announcement_without_a_window_handle(self):
		# A provider that reports no window handle must not disable the guard.
		window = _FakeUIA(name="Old chat", windowHandle=None)
		self.module._testApi.foregroundObject = window
		self.module._paintedChatTitle = lambda root: ""

		class _Gesture:
			def send(self):
				pass

		self.module.switchChat(_Gesture())
		self.module._testApi.foregroundObject = _FakeUIA(name="Another application", windowHandle=None)
		while self.module._testCore.calls:
			_, callback, args = self.module._testCore.calls.pop(0)
			callback(*args)

		self.assertEqual(self.module._testUi.messages, [])

	def test_control_tab_abandons_the_announcement_when_telegram_loses_focus(self):
		window = _FakeUIA(name="Old chat", windowHandle=11)
		self.module._testApi.foregroundObject = window
		self.module._paintedChatTitle = lambda root: ""

		class _Gesture:
			def send(self):
				pass

		self.module.switchChat(_Gesture())
		self.module._testApi.foregroundObject = _FakeUIA(name="Another application", windowHandle=22)
		while self.module._testCore.calls:
			_, callback, args = self.module._testCore.calls.pop(0)
			callback(*args)

		self.assertEqual(self.module._testUi.messages, [])

	def test_control_tab_does_not_announce_when_telegram_rejects_the_gesture(self):
		self.module._testApi.foregroundObject = _FakeUIA(name="Old chat")

		class _Gesture:
			def send(self):
				raise RuntimeError("gesture rejected")

		self.module.switchChat(_Gesture())

		self.assertEqual(self.module._testCore.calls, [])
		self.assertEqual(self.module._testUi.messages, [])
		self.assertEqual(self.module.AppModule.script_showMessageLinks.gesture, "kb:control+enter")

	def test_link_extraction_preserves_order_and_removes_message_punctuation(self):
		text = (
			"Android: https://play.google.com/store/apps/details?id=app, "
			"iOS: https://apps.apple.com/app/id123. "
			"Windows: https://example.com/download_(stable)."
		)

		self.assertEqual(
			self.module.linksFromMessageText(text),
			(
				"https://play.google.com/store/apps/details?id=app",
				"https://apps.apple.com/app/id123",
				"https://example.com/download_(stable)",
			),
		)

	def test_link_extraction_normalizes_www_and_email_and_deduplicates(self):
		text = "www.example.com Help@Example.com https://EXAMPLE.com https://example.com"

		self.assertEqual(
			self.module.linksFromMessageText(text),
			("https://www.example.com", "mailto:Help@Example.com", "https://EXAMPLE.com"),
		)

	def test_link_deduplication_keeps_case_sensitive_url_components(self):
		text = "https://example.com/User and https://example.com/user"

		self.assertEqual(
			self.module.linksFromMessageText(text),
			("https://example.com/User", "https://example.com/user"),
		)

	def test_link_extraction_recognizes_scheme_less_telegram_links(self):
		self.assertEqual(
			self.module.linksFromMessageText("Read example.com/path?q=1 today"),
			("https://example.com/path?q=1",),
		)
		self.assertEqual(
			self.module.linksFromMessageText("Read example.com today"),
			("https://example.com",),
		)
		self.assertEqual(
			self.module.linksFromMessageText("Deploy to my-host.example.co.uk now"),
			("https://my-host.example.co.uk",),
		)

	def test_link_extraction_does_not_treat_a_file_name_as_a_domain(self):
		self.assertEqual(self.module.linksFromMessageText("Here is report.pdf"), ())
		self.assertEqual(
			[target.kind for target in self.module.targetsFromMessageText("Here is report.pdf")],
			["attachment"],
		)

	def test_logging_never_records_the_path_or_query_of_a_link(self):
		redacted = self.module._redactedLink("https://example.com/reset?token=secret#part")

		self.assertEqual(redacted, "https://example.com")
		self.assertNotIn("secret", redacted)

	def test_logging_never_records_the_credentials_in_a_link(self):
		redacted = self.module._redactedLink("https://user:password@example.com/path")

		self.assertEqual(redacted, "https://example.com")
		self.assertNotIn("password", redacted)

	def test_file_paths_in_message_text_become_openable_targets(self):
		text = (
			"Local C:\\Users\\me\\Reports\\q3.pdf and "
			"\\\\server\\share\\notes.txt and "
			"file:///C:/Users/me/plan%20b.txt"
		)

		self.assertEqual(
			[(target.kind, target.value) for target in self.module.targetsFromMessageText(text)],
			[
				("file", "C:\\Users\\me\\Reports\\q3.pdf"),
				("file", "\\\\server\\share\\notes.txt"),
				("file", "C:\\Users\\me\\plan b.txt"),
			],
		)

	def test_attachment_file_name_is_read_from_a_telegram_document_name(self):
		self.assertEqual(
			self.module._attachmentFileName("Quarterly report.pdf, 1.2 MB"),
			"Quarterly report.pdf",
		)
		self.assertEqual(self.module._attachmentFileName("A message without a document"), "")

	def test_control_enter_offers_the_attachment_of_the_focused_message(self):
		document = _FakeUIA(name="Quarterly report.pdf, 1.2 MB")
		message = _FakeUIA(role=_Role.LISTITEM, name="Here it is", children=[document])
		_FakeUIA(role=_Role.LIST, automationId="ChatsList", children=[message])
		self.module._testApi.focusObject = message

		targets = self.module.messageTargets(message)

		self.assertEqual(
			[(target.kind, target.label) for target in targets],
			[("attachment", "Quarterly report.pdf")],
		)
		self.assertIs(targets[0].value, document)

	def test_downloaded_attachment_is_opened_from_disk(self):
		opened = []
		self.module._downloadedAttachmentPath = lambda name: "C:\\Downloads\\report.pdf"
		self.module._openLocalFile = lambda path: opened.append(path) or True
		document = _FakeUIA(name="report.pdf")

		self.module._openMessageAttachment(self.module._MessageTarget("attachment", "report.pdf", document))

		self.assertEqual(opened, ["C:\\Downloads\\report.pdf"])
		self.assertEqual(document.actionCount, 0)

	def test_attachment_that_is_not_downloaded_is_opened_through_telegram(self):
		self.module._downloadedAttachmentPath = lambda name: ""
		document = _FakeUIA(name="report.pdf")

		self.module._openMessageAttachment(self.module._MessageTarget("attachment", "report.pdf", document))

		self.assertEqual(document.actionCount, 1)
		self.assertEqual(self.module._testUi.messages, [])

	def test_attachment_without_a_download_or_provider_action_is_reported(self):
		self.module._downloadedAttachmentPath = lambda name: ""

		self.module._openMessageAttachment(self.module._MessageTarget("attachment", "report.pdf", None))

		self.assertEqual(self.module._testUi.messages, ["File is not downloaded yet"])

	def test_control_enter_offers_links_and_files_together(self):
		document = _FakeUIA(name="report.pdf, 1.2 MB")
		message = _FakeUIA(
			role=_Role.LISTITEM,
			name="See https://example.com/docs and report.pdf",
			children=[document],
		)
		_FakeUIA(role=_Role.LIST, automationId="ChatsList", children=[message])
		self.module._testApi.focusObject = message

		self.module.AppModule().script_showMessageLinks(None)

		_, callback, args = self.module._testCore.calls[0]
		self.assertIs(callback, self.module._showMessageLinksMenu)
		self.assertEqual(
			[(target.kind, target.label) for target in args[0]],
			[("link", "https://example.com/docs"), ("attachment", "report.pdf")],
		)
		# The named attachment resolves to the object Telegram can act on.
		self.assertIs(args[0][1].value, document)

	def test_control_enter_shows_all_links_from_unigram_message(self):
		message = _FakeUIA(
			role=_Role.LISTITEM,
			name="First https://one.example/path and https://two.example/path",
		)
		_FakeUIA(role=_Role.LIST, automationId="ChatsList", children=[message])
		self.module._testApi.focusObject = message

		class _Gesture:
			sent = False

			def send(self):
				self.sent = True

		gesture = _Gesture()
		self.module.AppModule().script_showMessageLinks(gesture)

		self.assertFalse(gesture.sent)
		self.assertEqual(len(self.module._testCore.calls), 1)
		_, callback, args = self.module._testCore.calls[0]
		self.assertIs(callback, self.module._showMessageLinksMenu)
		self.assertEqual(
			[target.label for target in args[0]],
			["https://one.example/path", "https://two.example/path"],
		)

	def test_control_enter_supports_qt_history_message_list(self):
		message = _FakeUIA(role=_Role.LISTITEM, name="https://example.com")
		_FakeUIA(role=_Role.LIST, className="class HistoryView::ListWidget", children=[message])
		self.module._testApi.focusObject = message
		opened = []
		self.module._openMessageLink = opened.append

		self.module.AppModule().script_showMessageLinks(None)

		self.assertEqual(opened, ["https://example.com"])
		self.assertEqual(self.module._testCore.calls, [])

	def test_control_enter_finds_message_list_through_accessibility_wrappers(self):
		message = _FakeUIA(role=_Role.LISTITEM, name="https://example.com")
		wrapper = _FakeUIA(children=[message])
		_FakeUIA(role=_Role.LIST, automationId="ChatsList", children=[wrapper])
		self.module._testApi.focusObject = message
		opened = []
		self.module._openMessageLink = opened.append

		self.module.AppModule().script_showMessageLinks(None)

		self.assertEqual(opened, ["https://example.com"])
		self.assertEqual(self.module._testCore.calls, [])

	def test_control_enter_supports_live_qt_history_inner_hierarchy(self):
		message = _FakeUIA(role=_Role.LISTITEM, name="https://example.com")
		_FakeUIA(
			automationId=(
				"class MainWindow.class Ui::RpWidget.class MainWidget."
				"class HistoryWidget.class Ui::ElasticScroll.class HistoryInner"
			),
			children=[message],
		)
		self.module._testApi.focusObject = message
		opened = []
		self.module._openMessageLink = opened.append

		self.module.AppModule().script_showMessageLinks(None)

		self.assertEqual(opened, ["https://example.com"])
		self.assertEqual(self.module._testCore.calls, [])

	def test_multiple_link_chooser_opens_live_second_selection(self):
		class _Dialog:
			def __init__(self):
				self.bindings = {}

			def SetSelection(self, selection):
				self.selection = selection

			def Bind(self, eventType, handler, id=None):
				self.bindings[(eventType, id)] = handler

			def Show(self):
				pass

			def Raise(self):
				pass

			def Close(self):
				pass

			def Destroy(self):
				pass

		class _SelectionEvent:
			def GetSelection(self):
				return 1

		dialog = _Dialog()
		wx = types.ModuleType("wx")
		wx.EVT_BUTTON = "button"
		wx.EVT_CLOSE = "close"
		wx.EVT_LISTBOX = "listbox"
		wx.ID_OK = 1
		wx.CallAfter = lambda callback, *args: callback(*args)
		wx.SingleChoiceDialog = lambda *args: dialog
		gui = types.ModuleType("gui")
		gui.mainFrame = types.SimpleNamespace(
			prePopup=lambda: None,
			postPopup=lambda: None,
		)
		previousGui = sys.modules.get("gui")
		previousWx = sys.modules.get("wx")
		sys.modules["gui"] = gui
		sys.modules["wx"] = wx
		opened = []
		self.module._openMessageTarget = lambda target: opened.append(target.label)
		targets = (
			self.module._MessageTarget("link", "https://one.example", "https://one.example"),
			self.module._MessageTarget("link", "https://two.example", "https://two.example"),
		)
		try:
			self.module._showMessageLinksMenu(targets)
			dialog.bindings[(wx.EVT_LISTBOX, None)](_SelectionEvent())
			dialog.bindings[(wx.EVT_BUTTON, wx.ID_OK)](object())
		finally:
			if previousGui is None:
				sys.modules.pop("gui", None)
			else:
				sys.modules["gui"] = previousGui
			if previousWx is None:
				sys.modules.pop("wx", None)
			else:
				sys.modules["wx"] = previousWx

		self.assertEqual(opened, ["https://two.example"])

	def test_control_enter_reports_message_without_links(self):
		message = _FakeUIA(role=_Role.LISTITEM, name="A message without a link")
		_FakeUIA(role=_Role.LIST, automationId="ChatsList", children=[message])
		self.module._testApi.focusObject = message

		self.module.AppModule().script_showMessageLinks(None)

		self.assertEqual(self.module._testUi.messages, ["No links or files in this message"])
		self.assertEqual(self.module._testCore.calls, [])

	def test_control_enter_passes_through_outside_message_list(self):
		self.module._testApi.focusObject = _FakeUIA(role=_Role.BUTTON, name="Send")

		class _Gesture:
			sent = False

			def send(self):
				self.sent = True

		gesture = _Gesture()
		self.module.AppModule().script_showMessageLinks(gesture)

		self.assertTrue(gesture.sent)
		self.assertEqual(self.module._testCore.calls, [])


if __name__ == "__main__":
	unittest.main()
