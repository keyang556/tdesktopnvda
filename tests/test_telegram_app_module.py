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


class _FakeClient:
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
	):
		self.role = role
		self.name = name
		self.UIAClassName = className
		self.UIAAutomationId = automationId
		self.states = set(states or ())
		self.children = list(children or ())
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

	def fakeScript(*, description, gesture):
		def decorator(function):
			function.__doc__ = description
			function.gesture = gesture
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

	stubs = {
		"api": api,
		"appModuleHandler": appModuleHandler,
		"controlTypes": controlTypes,
		"NVDAObjects": nvdaObjects,
		"NVDAObjects.UIA": uiaModule,
		"scriptHandler": scriptHandler,
		"ui": ui,
		"UIAHandler": uiaHandler,
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


if __name__ == "__main__":
	unittest.main()
