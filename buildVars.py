# Build customizations.

from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries
from site_scons.site_tools.NVDATool.utils import _


addon_info = AddonInfo(
	addon_name="telegramDesktop",
	addon_summary=_("Telegram Desktop Accessibility"),
	addon_description=_(
		"""Improves Telegram Desktop accessibility for NVDA users.

Adds Alt+1 to move focus to the chat list and Alt+M to open Telegram's main menu. The add-on uses Telegram's stable UIA class information and leaves Telegram's native accessible names unchanged."""
	),
	addon_version="0.1.3",
	addon_changelog=_(
		"""Fixed Alt+M in Telegram's folder-sidebar layout and fixed an NVDA freeze by replacing recursive object-tree traversal with provider-side UIA queries."""
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
