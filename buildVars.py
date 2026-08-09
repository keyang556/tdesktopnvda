# Build customizations.

from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries
from site_scons.site_tools.NVDATool.utils import _


addon_info = AddonInfo(
	addon_name="telegramDesktop",
	addon_summary=_("Telegram Desktop Accessibility"),
	addon_description=_(
		"""Improves Telegram Desktop accessibility for NVDA users.

Adds Alt+1 to move focus to the chat list, Alt+M to open Telegram's main menu, Ctrl+Enter to open or choose links from the focused message, and chat-title announcements when switching chats with Ctrl+Tab. It also supplies useful names for otherwise unlabeled main-menu controls."""
	),
	addon_version="0.1.4",
	addon_changelog=_(
		"""Added Ctrl+Enter to open a message's only link directly or choose among multiple links. Also fixed Alt+1 and Alt+M across Telegram layouts and conflicting add-ons, labeled structural main-menu controls, and announced the current chat after Ctrl+Tab or Ctrl+Shift+Tab."""
	),
	addon_author="Ken Chang <lindsay714322@gmail.com>",
	addon_url=None,
	addon_sourceURL=None,
	addon_docFileName="readme.html",
	addon_minimumNVDAVersion="2024.1.0",
	addon_lastTestedNVDAVersion="2026.1.0",
	addon_updateChannel=None,
	addon_license="GNU General Public License version 2",
	addon_licenseURL=None,
)

pythonSources: list[str] = [
	"addon/appModules/*.py",
	"addon/globalPlugins/*.py",
]
i18nSources: list[str] = pythonSources + ["buildVars.py"]
excludedFiles: list[str] = [
	"**/__pycache__/*",
	"**/*.pyc",
	"**/*.pyo",
]
baseLanguage: str = "en"
markdownExtensions: list[str] = ["tables"]
brailleTables: BrailleTables = {}
symbolDictionaries: SymbolDictionaries = {}
