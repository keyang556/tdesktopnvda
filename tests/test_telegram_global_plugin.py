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
		automationId="",
		className="",
		role=None,
		providerName="",
		exposedName=None,
		appName="telegram",
		children=(),
	):
		self.appModule = types.SimpleNamespace(appName=appName)
		self.UIAAutomationId = automationId
		self.UIAClassName = className
		self.UIAElement = _FakeElement(providerName)
		self.role = role
		self.name = providerName if exposedName is None else exposedName
		self.children = tuple(children)


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

	importlibStub = types.ModuleType("importlib")
	importlibStub.reloadCalls = []

	def reloadModule(module):
		importlibStub.reloadCalls.append(module)
		return module

	importlibStub.reload = reloadModule

	uiaHandler = types.ModuleType("UIAHandler")
	uiaHandler.UIA_NamePropertyId = "name"

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

	def test_an_unknown_main_menu_control_is_left_unnamed(self):
		obj = _FakeObject(
			automationId="class Window::MainMenu.class Ui::RippleButton",
			className="class Ui::RippleButton",
			role=_Role.BUTTON,
		)

		self.module._cleanTelegramControlName(obj)

		self.assertEqual(obj.name, "")

	def test_menu_ancestors_are_not_all_named_main_menu(self):
		"""Naming every level made NVDA repeat "Main menu" once per Tab step."""
		ancestors = [
			_FakeObject(
				automationId=f"class MainWindow.class Window::MainMenu.class {className}",
				className=f"class {className}",
				role=_Role.GROUPING,
			)
			for className in ("Ui::RpWidget", "Ui::ScrollArea", "Ui::LayerStackWidget")
		]

		for ancestor in ancestors:
			self.module.GlobalPlugin().event_focusEntered(ancestor, lambda: None)

		self.assertEqual([ancestor.name for ancestor in ancestors], ["", "", ""])

	def test_the_menu_container_itself_is_still_named(self):
		obj = _FakeObject(
			automationId="class MainWindow.class Ui::LayerStackWidget.class Window::MainMenu",
			className="class Window::MainMenu",
			role=_Role.GROUPING,
		)

		self.module.GlobalPlugin().event_focusEntered(obj, lambda: None)

		self.assertEqual(obj.name, "translated:Main menu")

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

	def test_class_chain_provider_name_does_not_block_the_label(self):
		chain = "class MainWindow.class Dialogs::Widget.class Dialogs::TopBarSuggestionContent"
		obj = _FakeObject(
			automationId=chain,
			className="class Dialogs::TopBarSuggestionContent",
			role=_Role.BUTTON,
			providerName=chain,
		)

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "translated:Telegram suggestion")

	def test_top_bar_suggestion_is_named_from_its_own_text(self):
		obj = _FakeObject(
			automationId=("class MainWindow.class Dialogs::Widget.class Dialogs::TopBarSuggestionContent"),
			className="class Dialogs::TopBarSuggestionContent",
			role=_Role.BUTTON,
			children=[
				_FakeObject(className="class Ui::FlatLabel", exposedName="Your Premium expires soon"),
				_FakeObject(
					className="class Ui::RpWidget",
					exposedName="",
					children=[_FakeObject(exposedName="Renew now")],
				),
			],
		)

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "Your Premium expires soon, Renew now")

	def test_suggestion_text_ignores_class_chain_labels_and_repeats(self):
		obj = _FakeObject(
			automationId=("class MainWindow.class Dialogs::Widget.class Dialogs::TopBarSuggestionContent"),
			className="class Dialogs::TopBarSuggestionContent",
			role=_Role.BUTTON,
			children=[
				_FakeObject(exposedName="class Ui::FlatLabel"),
				_FakeObject(exposedName="Set your birthday"),
				_FakeObject(exposedName="Set your birthday"),
			],
		)

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "Set your birthday")

	def test_unknown_control_stops_announcing_its_class_chain(self):
		chain = "class MainWindow.class Ui::RpWidget.class Ui::IconButton"
		obj = _FakeObject(automationId=chain, className="class Ui::IconButton", role=_Role.BUTTON)
		obj.name = chain

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "")

	def test_a_real_name_containing_dots_is_left_alone(self):
		obj = _FakeObject(
			automationId="class MainWindow.class Ui::RpWidget",
			className="class Ui::RpWidget",
			role=_Role.BUTTON,
			providerName="holiday.photo.jpg",
		)

		self.module.GlobalPlugin().event_gainFocus(obj, lambda: None)

		self.assertEqual(obj.name, "holiday.photo.jpg")

	def test_rtti_class_chain_detection(self):
		self.assertTrue(self.module._isRttiClassChain("class Ui::IconButton"))
		self.assertTrue(self.module._isRttiClassChain("class MainWindow.struct Dialogs::Widget"))
		self.assertFalse(self.module._isRttiClassChain(""))
		self.assertFalse(self.module._isRttiClassChain("Send a Gift"))
		self.assertFalse(self.module._isRttiClassChain("class of 99"))
		self.assertFalse(self.module._isRttiClassChain("class MainWindow.Send a Gift"))


if __name__ == "__main__":
	unittest.main()
