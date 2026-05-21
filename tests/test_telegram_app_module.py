from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "addon" / "appModules" / "telegram.py"


class _Role:
	LIST = "list"
	LISTITEM = "listItem"
	BUTTON = "button"
	EDITABLETEXT = "editableText"


class _State:
	FOCUSABLE = "focusable"


class _FakeUIA:
	def __init__(self, *, role=None, name="", parent=None, states=None):
		self.role = role
		self.name = name
		self.parent = parent
		self.states = set(states or ())

	def _get_states(self):
		return self.states


class _FakeListItem(_FakeUIA):
	pass


class _PassthroughGesture:
	def __init__(self):
		self.sent = False

	def send(self):
		self.sent = True


def _loadTelegramModule():
	api = types.ModuleType("api")
	api.focusObject = None
	api.getFocusObject = lambda: api.focusObject

	appModuleHandler = types.ModuleType("appModuleHandler")
	appModuleHandler.AppModule = object

	comtypes = types.ModuleType("comtypes")
	comtypes.COMError = RuntimeError

	controlTypes = types.ModuleType("controlTypes")
	controlTypes.Role = _Role
	controlTypes.State = _State

	nvdaObjects = types.ModuleType("NVDAObjects")
	uiaModule = types.ModuleType("NVDAObjects.UIA")
	uiaModule.UIA = _FakeUIA
	uiaModule.ListItem = _FakeListItem

	sentKeyboardGestures = []
	keyboardHandler = types.ModuleType("keyboardHandler")

	class _FakeKeyboardInputGesture:
		@staticmethod
		def fromName(name):
			return types.SimpleNamespace(send=lambda: sentKeyboardGestures.append(name))

	keyboardHandler.KeyboardInputGesture = _FakeKeyboardInputGesture

	stubs = {
		"api": api,
		"appModuleHandler": appModuleHandler,
		"comtypes": comtypes,
		"controlTypes": controlTypes,
		"keyboardHandler": keyboardHandler,
		"NVDAObjects": nvdaObjects,
		"NVDAObjects.UIA": uiaModule,
	}
	previous = {name: sys.modules.get(name) for name in stubs}
	sys.modules.update(stubs)
	try:
		spec = importlib.util.spec_from_file_location("telegram_app_module_under_test", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader is not None
		spec.loader.exec_module(module)
		module._testApi = api
		module._testSentKeyboardGestures = sentKeyboardGestures
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

	def test_chat_list_item_is_detected_by_parent_list_name(self):
		parent = _FakeUIA(role=_Role.LIST, name="\u804a\u5929\u5ba4")
		item = _FakeUIA(role=_Role.LISTITEM, name="Alice", parent=parent)

		self.assertTrue(self.module.isTelegramChatListItem(item))

	def test_chat_list_container_is_detected_by_name(self):
		listObj = _FakeUIA(role=_Role.LIST, name="Chats")

		self.assertTrue(self.module.isTelegramChatList(listObj))

	def test_message_list_container_is_detected_by_name(self):
		listObj = _FakeUIA(role=_Role.LIST, name="Messages")

		self.assertTrue(self.module.isTelegramMessageList(listObj))

	def test_non_chat_list_item_is_not_detected(self):
		parent = _FakeUIA(role=_Role.LIST, name="Settings")
		item = _FakeUIA(role=_Role.LISTITEM, name="Appearance", parent=parent)

		self.assertFalse(self.module.isTelegramChatListItem(item))

	def test_chat_list_forward_tab_entry_point_is_detected(self):
		button = _FakeUIA(role=_Role.BUTTON, name="\u7de8\u8f2f")

		self.assertTrue(self.module.isTelegramChatListForwardTabEntryPoint(button))

	def test_chat_list_forward_tab_entry_point_requires_button_role(self):
		obj = _FakeUIA(role=_Role.LISTITEM, name="\u7de8\u8f2f")

		self.assertFalse(self.module.isTelegramChatListForwardTabEntryPoint(obj))

	def test_message_composer_is_detected(self):
		obj = _FakeUIA(role=_Role.EDITABLETEXT, name="Write a message...")

		self.assertTrue(self.module.isTelegramMessageComposer(obj))

	def test_tab_from_chat_list_entry_button_sends_shift_tab(self):
		button = _FakeUIA(role=_Role.BUTTON, name="\u7de8\u8f2f")
		appModule = self.module.AppModule()
		appModule.event_gainFocus(button, lambda: None)
		self.module._testApi.focusObject = button
		gesture = _PassthroughGesture()

		appModule.script_tab(gesture)

		self.assertFalse(gesture.sent)
		self.assertEqual(self.module._testSentKeyboardGestures, ["shift+tab"])

	def test_tab_from_chat_list_entry_button_after_chat_list_passes_through(self):
		chatList = _FakeUIA(role=_Role.LIST, name="Chats")
		button = _FakeUIA(role=_Role.BUTTON, name="\u7de8\u8f2f")
		appModule = self.module.AppModule()
		appModule.event_gainFocus(chatList, lambda: None)
		appModule.event_gainFocus(button, lambda: None)
		self.module._testApi.focusObject = button
		gesture = _PassthroughGesture()

		appModule.script_tab(gesture)

		self.assertTrue(gesture.sent)
		self.assertEqual(self.module._testSentKeyboardGestures, [])

	def test_tab_from_message_composer_edit_button_passes_through(self):
		composer = _FakeUIA(role=_Role.EDITABLETEXT, name="Write a message...")
		button = _FakeUIA(role=_Role.BUTTON, name="Edit")
		appModule = self.module.AppModule()
		appModule.event_gainFocus(composer, lambda: None)
		appModule.event_gainFocus(button, lambda: None)
		self.module._testApi.focusObject = button
		gesture = _PassthroughGesture()

		appModule.script_tab(gesture)

		self.assertTrue(gesture.sent)
		self.assertEqual(self.module._testSentKeyboardGestures, [])

	def test_tab_outside_chat_list_entry_button_passes_through(self):
		button = _FakeUIA(role=_Role.BUTTON, name="Settings")
		appModule = self.module.AppModule()
		appModule.event_gainFocus(button, lambda: None)
		self.module._testApi.focusObject = button
		gesture = _PassthroughGesture()

		appModule.script_tab(gesture)

		self.assertTrue(gesture.sent)
		self.assertEqual(self.module._testSentKeyboardGestures, [])

	def test_chat_list_overlay_is_inserted_for_list_container(self):
		listObj = _FakeUIA(role=_Role.LIST, name="Chats")
		classes = [self.module.UIA]

		self.module.AppModule().chooseNVDAObjectOverlayClasses(listObj, classes)

		self.assertIs(classes[0], self.module.TelegramChatList)

	def test_message_list_overlay_is_inserted_for_list_container(self):
		listObj = _FakeUIA(role=_Role.LIST, name="Messages")
		classes = [self.module.UIA]

		self.module.AppModule().chooseNVDAObjectOverlayClasses(listObj, classes)

		self.assertIs(classes[0], self.module.TelegramMessageList)

	def test_list_overlay_preserves_existing_states_and_adds_focusable(self):
		listObj = self.module.TelegramChatList(role=_Role.LIST, name="Chats", states={"selected"})

		self.assertEqual(listObj._get_states(), {"selected", _State.FOCUSABLE})

	def test_overlay_is_inserted_only_for_chat_rows(self):
		parent = _FakeUIA(role=_Role.LIST, name="Chats")
		item = _FakeUIA(role=_Role.LISTITEM, name="Alice", parent=parent)
		classes = [self.module.ListItem]

		self.module.AppModule().chooseNVDAObjectOverlayClasses(item, classes)

		self.assertIs(classes[0], self.module.TelegramChatListItem)

	def test_message_list_item_overlay_is_inserted(self):
		parent = _FakeUIA(role=_Role.LIST, name="Messages")
		item = _FakeUIA(role=_Role.LISTITEM, name="Hello", parent=parent)
		classes = [self.module.ListItem]

		self.module.AppModule().chooseNVDAObjectOverlayClasses(item, classes)

		self.assertIs(classes[0], self.module.TelegramMessageListItem)

	def test_country_select_list_item_is_detected_by_parent_list_name(self):
		parent = _FakeUIA(role=_Role.LIST, name="Select Country")
		item = _FakeUIA(role=_Role.LISTITEM, name="United States, +1", parent=parent)

		self.assertTrue(self.module.isTelegramCountrySelectListItem(item))

	def test_country_select_list_item_is_detected_by_russian_parent_list_name(self):
		parent = _FakeUIA(role=_Role.LIST, name="\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0441\u0442\u0440\u0430\u043d\u0443")
		item = _FakeUIA(role=_Role.LISTITEM, name="\u0422\u0430\u0439\u0432\u0430\u043d\u044c, +886", parent=parent)

		self.assertTrue(self.module.isTelegramCountrySelectListItem(item))

	def test_country_select_overlay_is_inserted(self):
		parent = _FakeUIA(role=_Role.LIST, name="Select Country")
		item = _FakeUIA(role=_Role.LISTITEM, name="Taiwan, +886", parent=parent)
		classes = [self.module.ListItem]

		self.module.AppModule().chooseNVDAObjectOverlayClasses(item, classes)

		self.assertIs(classes[0], self.module.TelegramCountrySelectListItem)

	def test_country_select_overlay_is_not_inserted_for_other_lists(self):
		parent = _FakeUIA(role=_Role.LIST, name="Settings")
		item = _FakeUIA(role=_Role.LISTITEM, name="Taiwan, +886", parent=parent)
		classes = [self.module.ListItem]

		self.module.AppModule().chooseNVDAObjectOverlayClasses(item, classes)

		self.assertIs(classes[0], self.module.ListItem)

	def test_overlay_disables_selection_container_lookup(self):
		row = self.module.TelegramChatListItem(role=_Role.LISTITEM, name="Alice")

		self.assertIsNone(row._get_selectionContainer())

	def test_country_select_overlay_disables_selection_container_lookup(self):
		row = self.module.TelegramCountrySelectListItem(role=_Role.LISTITEM, name="Taiwan, +886")

		self.assertIsNone(row._get_selectionContainer())

	def test_message_list_overlay_disables_selection_container_lookup(self):
		row = self.module.TelegramMessageListItem(role=_Role.LISTITEM, name="Hello")

		self.assertIsNone(row._get_selectionContainer())


if __name__ == "__main__":
	unittest.main()
