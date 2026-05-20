# Build customizations.

from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries
from site_scons.site_tools.NVDATool.utils import _


addon_info = AddonInfo(
	addon_name="telegramDesktop",
	addon_summary=_("Telegram Desktop accessibility enhancements"),
	addon_description=_(
		"""Improves NVDA support for Telegram Desktop.

This release fixes chat list focus announcements when Telegram exposes a broken UIA selection container."""
	),
	addon_version="0.1.0",
	addon_changelog=_(
		"""Fixed chat list item focus speech in Telegram Desktop 6.8.x by avoiding a failing UIA selection container query."""
	),
	addon_author="chang",
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
markdownExtensions: list[str] = []
brailleTables: BrailleTables = {}
symbolDictionaries: SymbolDictionaries = {}
