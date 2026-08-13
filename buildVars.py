# Build customizations.

from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries
from site_scons.site_tools.NVDATool.utils import _


addon_info = AddonInfo(
	addon_name="telegramDesktop",
	addon_summary=_("Telegram Desktop Accessibility"),
	addon_description=_(
		"""Improves Telegram Desktop accessibility for NVDA users.

Adds Alt+1 to move focus to the chat list, Alt+M to open Telegram's main menu, Ctrl+Tab to announce the chat you switch to, and Ctrl+Enter to open the links and files a message holds. The add-on uses Telegram's stable UIA class information and leaves Telegram's native accessible names unchanged."""
	),
	addon_version="0.2.0",
	addon_changelog=_(
		"""Alt+1 is now instant on large accounts, works from inside the main menu, and repeats the current chat name. Alt+M finds its button in both left-pane layouts. Ctrl+Tab and Ctrl+Shift+Tab announce the chat you switch to. Ctrl+Enter opens the links, file paths and attachments in the focused message, and passes through unchanged outside a message."""
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
