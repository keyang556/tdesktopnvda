from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "addon" / "globalPlugins" / "telegramDesktop.py"

ADDON_SUMMARY = "Telegram Desktop Accessibility"


class _FakeGlobalPlugin:
	pass


class _FakeObject:
	def __init__(self, appName="telegram"):
		self.appModule = types.SimpleNamespace(appName=appName)
		self.name = ""


class _FakeGesture:
	"""A keyboard gesture that records whether NVDA passed it to the application."""

	def __init__(self):
		self.sent = 0

	def send(self):
		self.sent += 1


class _UnsendableGesture:
	"""A gesture source such as braille, which cannot be sent to the application."""

	def send(self):
		raise NotImplementedError


def _loadGlobalPluginModule():
	telegramModule = types.ModuleType("qualifiedTelegramAppModule")
	telegramModule.calls = []
	telegramModule.focusChatList = lambda: telegramModule.calls.append("focus")
	telegramModule.openMainMenu = lambda: telegramModule.calls.append("menu")
	telegramModule.answerCall = lambda: telegramModule.calls.append("answer")
	telegramModule.endCall = lambda: telegramModule.calls.append("end")
	telegramModule.toggleCallMicrophone = lambda: telegramModule.calls.append("microphone")
	telegramModule.toggleCallCamera = lambda: telegramModule.calls.append("camera")
	telegramModule._cleanTelegramControlName = lambda obj: setattr(obj, "name", "cleaned")

	codeAddon = types.SimpleNamespace(
		loadModule=lambda name: telegramModule,
		manifest={"summary": ADDON_SUMMARY},
	)
	addonHandler = types.ModuleType("addonHandler")
	addonHandler.initTranslation = lambda: None
	addonHandler.getCodeAddon = lambda: codeAddon

	api = types.ModuleType("api")
	api.foregroundObject = None
	api.getForegroundObject = lambda: api.foregroundObject

	globalPluginHandler = types.ModuleType("globalPluginHandler")
	globalPluginHandler.GlobalPlugin = _FakeGlobalPlugin

	logHandler = types.ModuleType("logHandler")
	logHandler.log = types.SimpleNamespace(debugWarning=lambda *args, **kwargs: None)

	def fakeScript(*, description, gesture=None, gestures=None, **kwargs):
		"""Mirror the parts of NVDA's script decorator this add-on relies on."""
		collected = list(gestures or [])
		if gesture is not None:
			collected.append(gesture)

		def decorator(function):
			function.__doc__ = description
			function.gestures = collected
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
		"logHandler": logHandler,
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
		self.module._testApi.foregroundObject = _FakeObject()

	def test_default_gestures_are_declared_so_nvda_can_reassign_them(self):
		self.assertEqual(self.module.GlobalPlugin.script_focusChatList.gestures, ["kb:alt+1"])
		self.assertEqual(self.module.GlobalPlugin.script_openMainMenu.gestures, ["kb:alt+m"])
		self.assertEqual(self.module.GlobalPlugin.script_answerCall.gestures, ["kb:alt+y"])
		self.assertEqual(self.module.GlobalPlugin.script_endCall.gestures, ["kb:alt+n"])
		self.assertEqual(
			self.module.GlobalPlugin.script_toggleCallMicrophone.gestures,
			["kb:alt+a"],
		)
		self.assertEqual(self.module.GlobalPlugin.script_toggleCallCamera.gestures, ["kb:alt+v"])

	def test_every_default_gesture_is_used_once(self):
		gestures = [
			gesture
			for name in dir(self.module.GlobalPlugin)
			if name.startswith("script_")
			for gesture in getattr(self.module.GlobalPlugin, name).gestures
		]

		self.assertCountEqual(gestures, set(gestures))

	def test_commands_are_grouped_under_this_addon_in_the_gesture_editor(self):
		self.assertEqual(self.module.GlobalPlugin.scriptCategory, ADDON_SUMMARY)

	def test_commands_are_described_for_the_gesture_editor(self):
		descriptions = [
			getattr(self.module.GlobalPlugin, name).__doc__
			for name in dir(self.module.GlobalPlugin)
			if name.startswith("script_")
		]

		self.assertEqual(
			self.module.GlobalPlugin.script_focusChatList.__doc__,
			"Move focus to chat list",
		)
		self.assertEqual(self.module.GlobalPlugin.script_openMainMenu.__doc__, "Open main menu")
		self.assertEqual(
			self.module.GlobalPlugin.script_answerCall.__doc__,
			"Answer the incoming call",
		)
		self.assertTrue(all(descriptions))

	def test_commands_forward_to_this_addons_qualified_app_module(self):
		plugin = self.module.GlobalPlugin()

		plugin.script_focusChatList(_FakeGesture())
		plugin.script_openMainMenu(_FakeGesture())
		plugin.script_answerCall(_FakeGesture())
		plugin.script_endCall(_FakeGesture())
		plugin.script_toggleCallMicrophone(_FakeGesture())
		plugin.script_toggleCallCamera(_FakeGesture())

		self.assertEqual(
			self.module._testTelegramModule.calls,
			["focus", "menu", "answer", "end", "microphone", "camera"],
		)

	def test_commands_do_nothing_outside_telegram(self):
		self.module._testApi.foregroundObject = _FakeObject("notepad")
		plugin = self.module.GlobalPlugin()
		gestures = [_FakeGesture() for _index in range(6)]

		plugin.script_focusChatList(gestures[0])
		plugin.script_openMainMenu(gestures[1])
		plugin.script_answerCall(gestures[2])
		plugin.script_endCall(gestures[3])
		plugin.script_toggleCallMicrophone(gestures[4])
		plugin.script_toggleCallCamera(gestures[5])

		self.assertEqual(self.module._testTelegramModule.calls, [])
		self.assertEqual([gesture.sent for gesture in gestures], [1] * len(gestures))

	def test_gesture_reaches_the_application_outside_telegram(self):
		self.module._testApi.foregroundObject = _FakeObject("notepad")
		gesture = _FakeGesture()

		self.module.GlobalPlugin().script_focusChatList(gesture)

		self.assertEqual(gesture.sent, 1)

	def test_gesture_is_kept_from_the_application_inside_telegram(self):
		gesture = _FakeGesture()

		self.module.GlobalPlugin().script_focusChatList(gesture)

		self.assertEqual(gesture.sent, 0)

	def test_unsendable_gesture_does_not_break_the_command(self):
		self.module._testApi.foregroundObject = _FakeObject("notepad")

		self.module.GlobalPlugin().script_openMainMenu(_UnsendableGesture())

		self.assertEqual(self.module._testTelegramModule.calls, [])

	def test_unreadable_foreground_fails_closed(self):
		plugin = self.module.GlobalPlugin()
		self.module._testApi.getForegroundObject = lambda: (_ for _ in ()).throw(RuntimeError())
		gesture = _FakeGesture()

		plugin.script_focusChatList(gesture)

		self.assertEqual(self.module._testTelegramModule.calls, [])
		self.assertEqual(gesture.sent, 1)

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
