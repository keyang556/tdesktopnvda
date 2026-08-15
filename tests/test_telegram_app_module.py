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
	GROUPING = "grouping"
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

	@staticmethod
	def _siblings(element):
		return element.parent.children if element.parent is not None else [element]

	def GetPreviousSiblingElement(self, element):
		siblings = self._siblings(element)
		index = siblings.index(element)
		return siblings[index - 1] if index > 0 else None

	def GetNextSiblingElement(self, element):
		siblings = self._siblings(element)
		index = siblings.index(element)
		return siblings[index + 1] if index + 1 < len(siblings) else None


class _FakeNullElement:
	"""Behave like comtypes' non-None NULL interface pointer."""

	def __bool__(self):
		return False

	def __getattr__(self, name):
		raise ValueError("NULL COM pointer access")


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
		providerName=None,
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
		self.providerName = name if providerName is None else providerName
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
			_NAME: self.providerName,
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

	def FindFirst(self, scope, condition):
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


def _loadTelegramModule(*, injectTranslation=True):
	addonHandler = types.ModuleType("addonHandler")
	addonHandler.initTranslation = lambda: None
	translations = types.SimpleNamespace(gettext=lambda message: f"translated:{message}")
	addonHandler.getCodeAddon = lambda: types.SimpleNamespace(
		getTranslationsInstance=lambda: translations,
	)

	api = types.ModuleType("api")
	api.focusObject = None
	api.foregroundObject = None
	api.getFocusObject = lambda: api.focusObject
	api.getForegroundObject = lambda: api.foregroundObject
	api.desktopObject = types.SimpleNamespace(children=[])
	api.getDesktopObject = lambda: api.desktopObject

	appModuleHandler = types.ModuleType("appModuleHandler")
	appModuleHandler.AppModule = object

	controlTypes = types.ModuleType("controlTypes")
	controlTypes.Role = _Role
	controlTypes.State = _State

	logHandler = types.ModuleType("logHandler")
	logHandler.log = types.SimpleNamespace(
		debug=lambda *args, **kwargs: None,
		debugWarning=lambda *args, **kwargs: None,
	)

	nvdaObjects = types.ModuleType("NVDAObjects")
	uiaModule = types.ModuleType("NVDAObjects.UIA")
	uiaModule.UIA = _FakeUIA

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
	uiaClient.IUIAutomationInvokePattern = object
	uiaClient.tagPOINT = lambda x, y: types.SimpleNamespace(x=x, y=y)

	stubs = {
		"addonHandler": addonHandler,
		"api": api,
		"appModuleHandler": appModuleHandler,
		"comInterfaces": comInterfaces,
		"comInterfaces.UIAutomationClient": uiaClient,
		"controlTypes": controlTypes,
		"logHandler": logHandler,
		"NVDAObjects": nvdaObjects,
		"NVDAObjects.UIA": uiaModule,
		"ui": ui,
		"UIAHandler": uiaHandler,
	}
	previous = {name: sys.modules.get(name) for name in stubs}
	sys.modules.update(stubs)
	try:
		spec = importlib.util.spec_from_file_location("telegram_app_module_under_test", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		if injectTranslation:
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

	def test_unregistered_fallback_module_loads_its_addon_translation(self):
		module = _loadTelegramModule(injectTranslation=False)

		self.assertEqual(module._MAIN_MENU_CLASS_NAMES["Window::MainMenu"], "translated:Main menu")

	def test_profile_label_is_applied_before_focus_announcement(self):
		obj = _FakeUIA(
			automationId="class Window::MainMenu.class Ui::UserpicButton",
			className="class Ui::UserpicButton",
			role=_Role.BUTTON,
		)
		observedNames = []

		self.module.AppModule().event_gainFocus(obj, lambda: observedNames.append(obj.name))

		self.assertEqual(observedNames, ["Profile"])

	def test_accounts_label_is_applied_before_focus_announcement(self):
		obj = _FakeUIA(
			automationId="class Window::MainMenu.class Window::MainMenu::ToggleAccountsButton",
			className="class Window::MainMenu::ToggleAccountsButton",
			role=_Role.BUTTON,
		)

		self.module.AppModule().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "Accounts")

	def test_only_the_main_menu_container_itself_is_named(self):
		menu = _FakeUIA(
			automationId="class MainWindow.class Ui::LayerStackWidget.class Window::MainMenu",
			className="class Window::MainMenu",
			role=_Role.GROUPING,
		)
		ancestor = _FakeUIA(
			automationId="class MainWindow.class Window::MainMenu.class Ui::ScrollArea",
			className="class Ui::ScrollArea",
			role=_Role.GROUPING,
		)

		appModule = self.module.AppModule()
		appModule.event_focusEntered(menu, lambda: None)
		appModule.event_focusEntered(ancestor, lambda: None)

		self.assertEqual(menu.name, "Main menu")
		self.assertEqual(ancestor.name, "")

	def test_existing_provider_name_is_preserved(self):
		obj = _FakeUIA(
			automationId="class Window::MainMenu.class Ui::UserpicButton",
			className="class Ui::UserpicButton",
			role=_Role.BUTTON,
			name="",
			providerName="Telegram profile",
		)

		self.module._cleanTelegramControlName(obj)

		self.assertEqual(obj.name, "Telegram profile")

	def test_composer_buttons_use_provider_name_or_translated_fallback(self):
		stickers = _FakeUIA(
			automationId="ButtonStickers",
			role=_Role.BUTTON,
			providerName="Emoji and stickers",
		)
		voice = _FakeUIA(automationId="btnVoiceMessage", role=_Role.BUTTON)

		self.module._cleanTelegramControlName(stickers)
		self.module._cleanTelegramControlName(voice)

		self.assertEqual(stickers.name, "Emoji and stickers")
		self.assertEqual(voice.name, "Record voice message")

	def test_suggestion_uses_unique_descendant_text(self):
		obj = _FakeUIA(
			automationId="class MainWindow.class Dialogs::TopBarSuggestionContent",
			className="class Dialogs::TopBarSuggestionContent",
			children=[
				_FakeUIA(name="Your Premium expires soon"),
				_FakeUIA(name="Your Premium expires soon"),
				_FakeUIA(name="Renew now"),
			],
		)

		self.module._cleanTelegramControlName(obj)

		self.assertEqual(obj.name, "Your Premium expires soon, Renew now")

	def test_suggestion_and_dismiss_button_have_safe_fallbacks(self):
		suggestion = _FakeUIA(
			automationId="class MainWindow.class Dialogs::TopBarSuggestionContent",
			className="class Dialogs::TopBarSuggestionContent",
		)
		dismiss = _FakeUIA(
			automationId=("class MainWindow.class Dialogs::TopBarSuggestionContent.class Ui::IconButton"),
			className="class Ui::IconButton",
		)

		self.module._cleanTelegramControlName(suggestion)
		self.module._cleanTelegramControlName(dismiss)

		self.assertEqual(suggestion.name, "Telegram suggestion")
		self.assertEqual(dismiss.name, "Dismiss suggestion")

	def test_class_chain_provider_name_does_not_block_known_label(self):
		chain = "class Window::MainMenu.class Ui::UserpicButton"
		obj = _FakeUIA(
			automationId=chain,
			className="class Ui::UserpicButton",
			name=chain,
			providerName=chain,
		)

		self.module._cleanTelegramControlName(obj)

		self.assertEqual(obj.name, "Profile")

	def test_unknown_control_stops_announcing_rtti_chain(self):
		chain = "class MainWindow.class Ui::RpWidget.class Ui::IconButton"
		obj = _FakeUIA(automationId=chain, className="class Ui::IconButton", name=chain)

		self.module._cleanTelegramControlName(obj)

		self.assertEqual(obj.name, "")

	def test_rtti_chain_detection_does_not_consume_ordinary_names(self):
		self.assertTrue(self.module._isRttiClassChain("class MainWindow.struct Dialogs::Widget"))
		self.assertFalse(self.module._isRttiClassChain(""))
		self.assertFalse(self.module._isRttiClassChain("class of 99"))
		self.assertFalse(self.module._isRttiClassChain("holiday.photo.jpg"))

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

		self.module.focusChatList()

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

		self.module.focusChatList()

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

		self.module.focusChatList()

		self.assertEqual(self.module._testUi.messages, ["Saved Messages"])

	def test_alt_1_reports_empty_chat_list(self):
		self.module._testApi.foregroundObject = _FakeUIA(
			role=_Role.LIST,
			className="class Dialogs::InnerWidget",
		)

		self.module.focusChatList()

		self.assertEqual(self.module._testUi.messages, ["Chat list is empty"])

	def test_alt_1_does_not_match_localized_name_without_class(self):
		self.module._testApi.foregroundObject = _FakeUIA(role=_Role.LIST, name="Chats")

		self.module.focusChatList()

		self.assertEqual(self.module._testUi.messages, ["Chat list not found"])

	def test_alt_1_contains_native_provider_query_failure(self):
		self.module._testApi.foregroundObject = _FakeUIA(failQuery=True)

		self.module.focusChatList()

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

		self.module.openMainMenu()

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

		self.module.openMainMenu()

		self.assertEqual(sidebarMenu.actionCount, 1)
		self.assertEqual(search.actionCount, 0)

	def test_point_lookup_accepts_both_main_menu_layouts(self):
		sidebarMenu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::SideBarButton",
			automationId="class MainWindow.class Ui::RpWidget.class Ui::SideBarButton",
		)
		dialogsMenu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::RpWidget.class Ui::IconButton",
		)
		_FakeUIA(children=[sidebarMenu])
		_FakeUIA(children=[dialogsMenu])

		self.assertTrue(self.module._isRawTelegramMainMenuButton(sidebarMenu))
		self.assertTrue(self.module._isRawTelegramMainMenuButton(dialogsMenu))

	def test_point_lookup_rejects_offscreen_and_unrelated_buttons(self):
		offscreen = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::SideBarButton",
			automationId="class MainWindow.class Ui::SideBarButton",
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

	def test_point_lookup_rejects_later_and_scrolled_sidebar_buttons(self):
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
		scrolledFolder = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::SideBarButton",
			automationId=(
				"class MainWindow.class Ui::ScrollArea.class Ui::VerticalLayout.class Ui::SideBarButton"
			),
		)
		_FakeUIA(children=[menu, folder])
		_FakeUIA(children=[scrolledFolder])

		self.assertTrue(self.module._isRawTelegramMainMenuButton(menu))
		self.assertFalse(self.module._isRawTelegramMainMenuButton(folder))
		self.assertFalse(self.module._isRawTelegramMainMenuButton(scrolledFolder))

	def test_point_lookup_invokes_first_menu_without_subtree_query(self):
		menu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
		)
		window = _FakeUIA(children=[menu], failQuery=True)
		window.location = types.SimpleNamespace(left=0, top=0, width=1200, height=800)
		self.module._testApi.foregroundObject = window
		self.module._uiaHandler().clientObject.ElementFromPoint = lambda point: menu

		self.module.openMainMenu()

		self.assertEqual(menu.actionCount, 1)
		self.assertEqual(self.module._testUi.messages, [])

	def test_standard_layout_samples_inside_the_40_pixel_toggle(self):
		menu = _FakeUIA(
			role=_Role.BUTTON,
			# Telegram 7.0.9 exposes neither property in the attached NVDA log.
			className="",
			automationId="",
		)
		searchControls = _FakeUIA(children=[menu], failQuery=True)
		searchControls.location = types.SimpleNamespace(left=0, top=0, width=1200, height=800)
		self.module._testApi.foregroundObject = searchControls
		self.module._uiaHandler().clientObject.ElementFromPoint = (
			lambda point: menu if 7 <= point.x <= 47 and 7 <= point.y <= 47 else searchControls
		)

		self.module.openMainMenu()

		self.assertEqual(menu.actionCount, 1)
		self.assertEqual(self.module._testUi.messages, [])

	def test_metadata_free_button_is_accepted_only_as_direct_point_hit(self):
		button = _FakeUIA(role=_Role.BUTTON)

		self.assertFalse(self.module._isRawTelegramMainMenuButton(button))
		self.assertTrue(self.module._isRawTelegramMainMenuButton(button, directTopLeftHit=True))

	def test_direct_standard_menu_ignores_flattened_prior_icon_sibling(self):
		priorTitleBarIcon = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class MainWindow.class Ui::Platform::TitleWidget.class Ui::IconButton",
		)
		menu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class MainWindow.class Dialogs::Widget.class Ui::IconButton",
		)
		_FakeUIA(children=[priorTitleBarIcon, menu])

		self.assertTrue(self.module._isRawTelegramMainMenuButton(menu))
		self.assertTrue(self.module._isRawTelegramMainMenuButton(menu, directTopLeftHit=True))

	def test_point_lookup_checks_button_beside_transparent_overlay(self):
		overlay = _FakeUIA(
			role=_Role.GROUPING,
			className="class Ui::RpWidget",
			automationId="class Dialogs::Widget.class MenuUnderButton",
		)
		menu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
		)
		# Telegram constructs the toggle first and the transparent hit area
		# second, then stacks the latter underneath visually.
		window = _FakeUIA(children=[menu, overlay], failQuery=True)
		window.location = types.SimpleNamespace(left=0, top=0, width=1200, height=800)
		self.module._testApi.foregroundObject = window
		self.module._uiaHandler().clientObject.ElementFromPoint = lambda point: overlay

		self.module.openMainMenu()

		self.assertEqual(menu.actionCount, 1)
		self.assertEqual(self.module._testUi.messages, [])

	def test_point_lookup_opens_compact_and_expanded_folder_sidebars(self):
		for sidebarWidth in (64, 240):
			with self.subTest(sidebarWidth=sidebarWidth):
				menu = _FakeUIA(
					role=_Role.BUTTON,
					className="class Ui::SideBarButton",
					automationId="class MainWindow.class Ui::RpWidget.class Ui::SideBarButton",
				)
				window = _FakeUIA(children=[menu], failQuery=True)
				window.location = types.SimpleNamespace(left=0, top=0, width=sidebarWidth + 900, height=800)
				self.module._testApi.foregroundObject = window
				self.module._uiaHandler().clientObject.ElementFromPoint = lambda point: menu

				self.module.openMainMenu()

				self.assertEqual(menu.actionCount, 1)
		self.assertEqual(self.module._testUi.messages, [])

	def test_point_action_failure_retries_with_subtree_button(self):
		stalePointButton = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
			failAction=True,
		)
		fallbackMenu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
		)
		window = _FakeUIA(children=[fallbackMenu])
		window.location = types.SimpleNamespace(left=0, top=0, width=1200, height=800)
		self.module._testApi.foregroundObject = window
		self.module._uiaHandler().clientObject.ElementFromPoint = lambda point: stalePointButton

		self.module.openMainMenu()

		self.assertEqual(fallbackMenu.actionCount, 1)
		self.assertEqual(self.module._testUi.messages, [])

	def test_subtree_menu_query_returns_a_live_actionable_element(self):
		menu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
		)
		window = _FakeUIA(children=[menu])
		window.location = types.SimpleNamespace(left=0, top=0, width=1200, height=800)
		window.FindFirstBuildCache = lambda *args: (_ for _ in ()).throw(
			AssertionError("action lookup must not return a cached-only element"),
		)
		self.module._testApi.foregroundObject = window
		self.module._uiaHandler().clientObject.ElementFromPoint = lambda point: window

		self.module.openMainMenu()

		self.assertEqual(menu.actionCount, 1)
		self.assertEqual(self.module._testUi.messages, [])

	def test_null_sidebar_query_falls_through_to_standard_icon_button(self):
		menu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
		)
		window = _FakeUIA(children=[menu])
		originalFindFirst = window.FindFirst

		def findFirst(scope, condition):
			result = originalFindFirst(scope, condition)
			return result if result is not None else _FakeNullElement()

		window.FindFirst = findFirst

		self.assertIs(self.module._findTelegramMainMenuButton(window), menu)

	def test_point_lookup_treats_null_previous_sibling_as_tree_boundary(self):
		menu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
		)
		window = _FakeUIA(children=[menu], failQuery=True)
		window.location = types.SimpleNamespace(left=0, top=0, width=1200, height=800)
		client = self.module._uiaHandler().clientObject
		baseWalker = client.RawViewWalker

		class NullTerminatedWalker:
			def GetParentElement(self, element):
				return baseWalker.GetParentElement(element) or _FakeNullElement()

			def GetPreviousSiblingElement(self, element):
				return baseWalker.GetPreviousSiblingElement(element) or _FakeNullElement()

			def GetNextSiblingElement(self, element):
				return baseWalker.GetNextSiblingElement(element) or _FakeNullElement()

		client.RawViewWalker = NullTerminatedWalker()
		self.addCleanup(setattr, client, "RawViewWalker", baseWalker)
		client.ElementFromPoint = lambda point: menu
		self.module._testApi.foregroundObject = window

		self.module.openMainMenu()

		self.assertEqual(menu.actionCount, 1)
		self.assertEqual(self.module._testUi.messages, [])

	def test_popup_foreground_uses_same_app_main_window(self):
		menu = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
		)
		mainWindow = _FakeUIA(className="class MainWindow", children=[menu])
		mainWindow.location = types.SimpleNamespace(left=0, top=0, width=1200, height=800)
		popup = _FakeUIA(className="class NotificationWindow")
		appModule = types.SimpleNamespace(appName="telegram")
		mainWindow.appModule = appModule
		popup.appModule = appModule
		self.module._testApi.foregroundObject = popup
		self.module._testApi.desktopObject.children = [mainWindow]
		self.module._uiaHandler().clientObject.ElementFromPoint = lambda point: menu

		self.module.openMainMenu()

		self.assertEqual(menu.actionCount, 1)
		self.assertEqual(self.module._testUi.messages, [])

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

		self.module.openMainMenu()

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

		self.module.openMainMenu()

		self.assertEqual(button.actionCount, 0)
		self.assertEqual(self.module._testUi.messages, ["Main menu is not available"])

	def test_alt_m_reports_when_main_menu_is_unavailable(self):
		self.module._testApi.foregroundObject = _FakeUIA()

		self.module.openMainMenu()

		self.assertEqual(self.module._testUi.messages, ["Main menu is not available"])

	def test_alt_m_contains_provider_action_failure(self):
		button = _FakeUIA(
			role=_Role.BUTTON,
			className="class Ui::IconButton",
			automationId="class Dialogs::Widget.class Ui::IconButton",
			failAction=True,
		)
		self.module._testApi.foregroundObject = button

		self.module.openMainMenu()

		self.assertEqual(self.module._testUi.messages, ["Main menu is not available"])

	def test_shortcut_commands_do_not_expand_recursive_descendants(self):
		chat = _FakeUIA(role=_Role.LISTITEM, name="Alice")
		chatList = _FakeUIA(
			role=_Role.LIST,
			className="class Dialogs::InnerWidget",
			children=[chat],
		)
		self.module._testApi.foregroundObject = _FakeUIA(children=[chatList])

		self.module.focusChatList()

		self.assertTrue(chat.focused)

	def test_app_module_leaves_the_commands_to_the_global_plugin(self):
		# Defining them here as well would put a second, identically described
		# entry in NVDA's Input Gestures dialog, where only one of the two can
		# be reassigned.
		self.assertFalse(
			[name for name in dir(self.module.AppModule) if name.startswith("script_")],
		)


if __name__ == "__main__":
	unittest.main()
