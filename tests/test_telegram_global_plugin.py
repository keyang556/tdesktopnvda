from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "addon" / "globalPlugins" / "telegramDesktop.py"


class _FakeGlobalPlugin:
	def __init__(self):
		self.boundGestures = {}

	def bindGestures(self, gestures):
		self.boundGestures.update(gestures)

	def removeGestureBinding(self, gesture):
		if gesture not in self.boundGestures:
			raise LookupError(gesture)
		del self.boundGestures[gesture]


class _FakeObject:
	def __init__(self, appName="telegram"):
		self.appModule = types.SimpleNamespace(appName=appName)
		self.name = ""


def _loadGlobalPluginModule():
	telegramModule = types.ModuleType("qualifiedTelegramAppModule")
	telegramModule.calls = []
	telegramModule.focusChatList = lambda: telegramModule.calls.append("focus")
	telegramModule.openMainMenu = lambda: telegramModule.calls.append("menu")
	telegramModule._cleanTelegramControlName = lambda obj: setattr(obj, "name", "cleaned")

	codeAddon = types.SimpleNamespace(loadModule=lambda name: telegramModule)
	addonHandler = types.ModuleType("addonHandler")
	addonHandler.initTranslation = lambda: None
	addonHandler.getCodeAddon = lambda: codeAddon

	api = types.ModuleType("api")
	api.foregroundObject = None
	api.getForegroundObject = lambda: api.foregroundObject

	globalPluginHandler = types.ModuleType("globalPluginHandler")
	globalPluginHandler.GlobalPlugin = _FakeGlobalPlugin

	def fakeScript(*, description):
		def decorator(function):
			function.__doc__ = description
			return function

		return decorator

	scriptHandler = types.ModuleType("scriptHandler")
	scriptHandler.script = fakeScript

	importlibStub = types.ModuleType("importlib")
	importlibStub.reload = lambda module: module

	stubs = {
		"addonHandler": addonHandler,
		"api": api,
		"globalPluginHandler": globalPluginHandler,
		"importlib": importlibStub,
		"scriptHandler": scriptHandler,
	}
	previous = {name: sys.modules.get(name) for name in stubs}
	sys.modules.update(stubs)
	try:
		spec = importlib.util.spec_from_file_location("telegram_global_plugin_under_test", MODULE_PATH)
		module = importlib.util.module_from_spec(spec)
		module._ = lambda message: message
		assert spec.loader is not None
		spec.loader.exec_module(module)
		module._testApi = api
		module._testTelegramModule = telegramModule
		return module
	finally:
		for name, value in previous.items():
			if value is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = value


class TelegramGlobalPluginTests(unittest.TestCase):
	def setUp(self):
		self.module = _loadGlobalPluginModule()

	def test_binds_only_the_two_commands_while_telegram_is_foreground(self):
		self.module._testApi.foregroundObject = _FakeObject()

		plugin = self.module.GlobalPlugin()

		self.assertEqual(
			plugin.boundGestures,
			{"kb:alt+1": "focusChatList", "kb:alt+m": "openMainMenu"},
		)

	def test_foreground_change_removes_global_bindings(self):
		self.module._testApi.foregroundObject = _FakeObject()
		plugin = self.module.GlobalPlugin()

		plugin.event_foreground(_FakeObject("notepad"), lambda: None)

		self.assertEqual(plugin.boundGestures, {})

	def test_unreadable_foreground_fails_closed_on_focus(self):
		self.module._testApi.foregroundObject = _FakeObject()
		plugin = self.module.GlobalPlugin()
		self.module._testApi.getForegroundObject = lambda: (_ for _ in ()).throw(RuntimeError())

		plugin.event_gainFocus(_FakeObject(), lambda: None)

		self.assertEqual(plugin.boundGestures, {})

	def test_commands_forward_to_this_addons_qualified_app_module(self):
		plugin = self.module.GlobalPlugin()

		plugin.script_focusChatList(None)
		plugin.script_openMainMenu(None)

		self.assertEqual(self.module._testTelegramModule.calls, ["focus", "menu"])

	def test_telegram_name_is_cleaned_before_focus_continues(self):
		obj = _FakeObject()
		observedNames = []

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: observedNames.append(obj.name))

		self.assertEqual(observedNames, ["cleaned"])

	def test_non_telegram_object_is_never_renamed(self):
		obj = _FakeObject("notepad")

		self.module.GlobalPlugin().event_focusEntered(obj, lambda: None)

		self.assertEqual(obj.name, "")


if __name__ == "__main__":
	unittest.main()
