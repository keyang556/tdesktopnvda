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
	def __init__(self, *, appName="telegram"):
		self.appModule = types.SimpleNamespace(appName=appName)


def _loadGlobalPluginModule():
	addonHandler = types.ModuleType("addonHandler")
	addonHandler.translationCalls = 0
	telegramModule = types.SimpleNamespace(
		calls=[],
	)
	telegramModule.focusChatList = lambda: telegramModule.calls.append("focusChatList")
	telegramModule.openMainMenu = lambda: telegramModule.calls.append("openMainMenu")
	telegramModule.showMessageLinks = lambda gesture: telegramModule.calls.append("showMessageLinks")
	telegramModule.switchChat = lambda gesture: telegramModule.calls.append("switchChat")
	codeAddon = types.SimpleNamespace(
		loadModuleCalls=[],
	)

	def loadModule(name):
		codeAddon.loadModuleCalls.append(name)
		return telegramModule

	codeAddon.loadModule = loadModule
	addonHandler.getCodeAddon = lambda: codeAddon

	def initTranslation():
		addonHandler.translationCalls += 1
		sys._getframe(1).f_globals["_"] = lambda message: f"translated:{message}"

	addonHandler.initTranslation = initTranslation

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
	importlibStub.reloadCalls = []

	def reloadModule(module):
		importlibStub.reloadCalls.append(module)
		return module

	importlibStub.reload = reloadModule

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
		assert spec.loader is not None
		spec.loader.exec_module(module)
		module._testAddonHandler = addonHandler
		module._testCodeAddon = codeAddon
		module._testImportlib = importlibStub
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

	def test_owned_app_module_is_loaded_and_refreshed_once(self):
		self.assertEqual(self.module._testCodeAddon.loadModuleCalls, ["appModules.telegram"])
		self.assertEqual(len(self.module._testImportlib.reloadCalls), 1)
		self.assertEqual(self.module._testAddonHandler.translationCalls, 1)

	def test_gestures_are_bound_while_telegram_is_foreground(self):
		plugin = self.module.GlobalPlugin()

		plugin._updateGestureBindings(_FakeObject())

		self.assertEqual(
			plugin.boundGestures,
			{
				"kb:alt+1": "focusChatList",
				"kb:alt+m": "openMainMenu",
				"kb:control+enter": "showMessageLinks",
				"kb:control+tab": "switchChat",
				"kb:control+shift+tab": "switchChat",
			},
		)

	def test_gestures_are_released_in_other_applications(self):
		plugin = self.module.GlobalPlugin()
		plugin._updateGestureBindings(_FakeObject())

		plugin.event_foreground(_FakeObject(appName="notepad"), lambda: None)

		self.assertEqual(plugin.boundGestures, {})

	def test_gestures_are_bound_when_telegram_is_already_focused_on_reload(self):
		plugin = self.module.GlobalPlugin()
		self.module.api.foregroundObject = _FakeObject()

		plugin.event_gainFocus(_FakeObject(), lambda: None)

		self.assertIn("kb:alt+1", plugin.boundGestures)

	def test_a_late_telegram_focus_event_does_not_bind_over_another_application(self):
		plugin = self.module.GlobalPlugin()
		plugin._updateGestureBindings(_FakeObject(appName="notepad"))
		self.module.api.foregroundObject = _FakeObject(appName="notepad")

		plugin.event_gainFocus(_FakeObject(), lambda: None)

		self.assertEqual(plugin.boundGestures, {})

	def test_an_unreadable_foreground_leaves_the_bindings_alone(self):
		plugin = self.module.GlobalPlugin()
		self.module.api.foregroundObject = _FakeObject()
		plugin.event_gainFocus(_FakeObject(), lambda: None)

		def raiseError():
			raise RuntimeError("no foreground")

		self.module.api.getForegroundObject = raiseError
		plugin.event_gainFocus(_FakeObject(appName="notepad"), lambda: None)

		self.assertIn("kb:alt+1", plugin.boundGestures)

	def test_repeated_updates_do_not_rebind_or_raise(self):
		plugin = self.module.GlobalPlugin()
		plugin._updateGestureBindings(_FakeObject())
		plugin._updateGestureBindings(_FakeObject())
		plugin._updateGestureBindings(_FakeObject(appName="notepad"))
		plugin._updateGestureBindings(_FakeObject(appName="notepad"))

		self.assertEqual(plugin.boundGestures, {})

	def test_scripts_delegate_to_the_owned_app_module(self):
		plugin = self.module.GlobalPlugin()

		plugin.script_focusChatList(None)
		plugin.script_openMainMenu(None)
		plugin.script_showMessageLinks(None)
		plugin.script_switchChat(None)

		self.assertEqual(
			self.module._testTelegramModule.calls,
			["focusChatList", "openMainMenu", "showMessageLinks", "switchChat"],
		)

	def test_objects_without_an_app_module_are_ignored(self):
		plugin = self.module.GlobalPlugin()

		plugin._updateGestureBindings(object())

		self.assertEqual(plugin.boundGestures, {})


if __name__ == "__main__":
	unittest.main()
