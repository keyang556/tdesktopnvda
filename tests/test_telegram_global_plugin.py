from __future__ import annotations

from enum import Enum
import importlib.util
from pathlib import Path
import sys
import types
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "addon" / "globalPlugins" / "telegramDesktop.py"


class _Role(Enum):
	BUTTON = "button"
	GROUPING = "grouping"


class _FakeGlobalPlugin:
	def __init__(self):
		self.boundGestures = {}

	def bindGestures(self, gestures):
		self.boundGestures.update(gestures)

	def removeGestureBinding(self, gesture):
		if gesture not in self.boundGestures:
			raise LookupError(gesture)
		del self.boundGestures[gesture]


class _FakeElement:
	def __init__(self, name=""):
		self.CurrentName = name

	def GetCurrentPropertyValue(self, propertyId):
		return self.CurrentName


class _FakeObject:
	def __init__(
		self,
		*,
		automationId,
		className,
		role,
		providerName="",
		exposedName=None,
		appName="telegram",
	):
		self.appModule = types.SimpleNamespace(appName=appName)
		self.UIAAutomationId = automationId
		self.UIAClassName = className
		self.UIAElement = _FakeElement(providerName)
		self.role = role
		self.name = providerName if exposedName is None else exposedName


def _loadGlobalPluginModule():
	addonHandler = types.ModuleType("addonHandler")
	addonHandler.translationCalls = 0
	telegramModule = types.SimpleNamespace(
		focusChatList=lambda: None,
		openMainMenu=lambda: None,
		showMessageLinks=lambda gesture: None,
		switchChat=lambda gesture: None,
	)
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

	controlTypes = types.ModuleType("controlTypes")
	controlTypes.Role = _Role

	globalPluginHandler = types.ModuleType("globalPluginHandler")
	globalPluginHandler.GlobalPlugin = _FakeGlobalPlugin

	def fakeScript(*, description):
		def decorator(function):
			function.__doc__ = description
			return function

		return decorator

	scriptHandler = types.ModuleType("scriptHandler")
	scriptHandler.script = fakeScript

	uiaHandler = types.ModuleType("UIAHandler")
	uiaHandler.UIA_NamePropertyId = "name"

	importlibStub = types.ModuleType("importlib")
	importlibStub.reloadCalls = []

	def reloadModule(module):
		importlibStub.reloadCalls.append(module)
		return module

	importlibStub.reload = reloadModule

	stubs = {
		"addonHandler": addonHandler,
		"api": api,
		"controlTypes": controlTypes,
		"globalPluginHandler": globalPluginHandler,
		"importlib": importlibStub,
		"scriptHandler": scriptHandler,
		"UIAHandler": uiaHandler,
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

	def test_control_enter_is_bound_while_telegram_is_foreground(self):
		foreground = _FakeObject(
			automationId="",
			className="",
			role=_Role.BUTTON,
		)
		plugin = self.module.GlobalPlugin()
		plugin._updateGestureBindings(foreground)

		self.assertEqual(plugin.boundGestures["kb:control+enter"], "showMessageLinks")

	def test_profile_label_is_applied_before_focus_announcement(self):
		obj = _FakeObject(
			automationId="class Window::MainMenu.class Ui::UserpicButton",
			className="class Ui::UserpicButton",
			role=_Role.BUTTON,
		)
		observedNames = []

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: observedNames.append(obj.name))

		self.assertEqual(observedNames, ["translated:Profile"])

	def test_accounts_label_is_applied_before_focus_announcement(self):
		obj = _FakeObject(
			automationId=("class Window::MainMenu.class Window::MainMenu::ToggleAccountsButton"),
			className="class Window::MainMenu::ToggleAccountsButton",
			role=_Role.BUTTON,
		)
		observedNames = []

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: observedNames.append(obj.name))

		self.assertEqual(observedNames, ["translated:Accounts"])

	def test_main_menu_group_is_labeled_before_focus_entered_announcement(self):
		obj = _FakeObject(
			automationId="class Window::MainMenu",
			className="class Window::MainMenu",
			role=_Role.GROUPING,
		)
		observedNames = []

		self.module.GlobalPlugin().event_focusEntered(obj, lambda: observedNames.append(obj.name))

		self.assertEqual(observedNames, ["translated:Main menu"])

	def test_existing_provider_name_is_preserved(self):
		obj = _FakeObject(
			automationId="class Window::MainMenu.class Ui::UserpicButton",
			className="class Ui::UserpicButton",
			role=_Role.BUTTON,
			providerName="Telegram profile",
		)

		self.module._cleanTelegramControlName(obj)

		self.assertEqual(obj.name, "Telegram profile")

	def test_non_telegram_control_is_not_renamed(self):
		obj = _FakeObject(
			automationId="class Window::MainMenu.class Ui::UserpicButton",
			className="class Ui::UserpicButton",
			role=_Role.BUTTON,
			appName="otherApp",
		)

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "")

	def test_stickers_button_uses_current_provider_name(self):
		obj = _FakeObject(
			automationId="ButtonStickers",
			className="ToggleButton",
			role=_Role.BUTTON,
			providerName="Emoji, stickers, GIFs, and more",
			exposedName="",
		)

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "Emoji, stickers, GIFs, and more")

	def test_stickers_button_has_translated_fallback(self):
		obj = _FakeObject(
			automationId="ButtonStickers",
			className="ToggleButton",
			role=_Role.BUTTON,
		)

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "translated:Emoji, stickers, and GIFs")

	def test_voice_message_button_has_translated_fallback(self):
		obj = _FakeObject(
			automationId="btnVoiceMessage",
			className="ToggleButton",
			role=_Role.BUTTON,
		)

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "translated:Record voice message")

	def test_top_bar_suggestion_has_translated_fallback(self):
		obj = _FakeObject(
			automationId=("class MainWindow.class Dialogs::Widget.class Dialogs::TopBarSuggestionContent"),
			className="class Dialogs::TopBarSuggestionContent",
			role=_Role.BUTTON,
		)

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "translated:Telegram suggestion")

	def test_top_bar_suggestion_close_button_has_translated_fallback(self):
		obj = _FakeObject(
			automationId=(
				"class MainWindow.class Dialogs::Widget."
				"class Dialogs::TopBarSuggestionContent.class Ui::IconButton"
			),
			className="class Ui::IconButton",
			role=_Role.BUTTON,
		)

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "translated:Dismiss suggestion")

	def test_top_bar_suggestion_provider_name_is_preserved(self):
		obj = _FakeObject(
			automationId=("class MainWindow.class Dialogs::Widget.class Dialogs::TopBarSuggestionContent"),
			className="class Dialogs::TopBarSuggestionContent",
			role=_Role.BUTTON,
			providerName="Review new login",
			exposedName="",
		)

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "Review new login")


if __name__ == "__main__":
	unittest.main()
