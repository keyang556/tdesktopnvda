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


class _FakeUIA:
	def __init__(self, *, role=None, name="", parent=None):
		self.role = role
		self.name = name
		self.parent = parent


class _FakeListItem(_FakeUIA):
	pass


def _loadTelegramModule():
	appModuleHandler = types.ModuleType("appModuleHandler")
	appModuleHandler.AppModule = object

	comtypes = types.ModuleType("comtypes")
	comtypes.COMError = RuntimeError

	controlTypes = types.ModuleType("controlTypes")
	controlTypes.Role = _Role

	nvdaObjects = types.ModuleType("NVDAObjects")
	uiaModule = types.ModuleType("NVDAObjects.UIA")
	uiaModule.UIA = _FakeUIA
	uiaModule.ListItem = _FakeListItem

	stubs = {
		"appModuleHandler": appModuleHandler,
		"comtypes": comtypes,
		"controlTypes": controlTypes,
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

	def test_non_chat_list_item_is_not_detected(self):
		parent = _FakeUIA(role=_Role.LIST, name="Settings")
		item = _FakeUIA(role=_Role.LISTITEM, name="Appearance", parent=parent)

		self.assertFalse(self.module.isTelegramChatListItem(item))

	def test_overlay_is_inserted_only_for_chat_rows(self):
		parent = _FakeUIA(role=_Role.LIST, name="Chats")
		item = _FakeUIA(role=_Role.LISTITEM, name="Alice", parent=parent)
		classes = [self.module.ListItem]

		self.module.AppModule().chooseNVDAObjectOverlayClasses(item, classes)

		self.assertIs(classes[0], self.module.TelegramChatListItem)

	def test_country_select_list_item_is_detected_by_parent_list_name(self):
		parent = _FakeUIA(role=_Role.LIST, name="Select Country")
		item = _FakeUIA(role=_Role.LISTITEM, name="United States, +1", parent=parent)

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


if __name__ == "__main__":
	unittest.main()
