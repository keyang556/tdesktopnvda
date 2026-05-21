# Build customizations.

from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries
from site_scons.site_tools.NVDATool.utils import _


addon_info = AddonInfo(
	addon_name="telegramDesktop",
	addon_summary=_("Telegram Desktop Accessibility"),
	addon_description=_(
		"""Improves Telegram Desktop accessibility for NVDA users.

This release fixes Tab focus entry and focus announcements for Telegram chat and message lists when Telegram exposes non-focusable UIA list containers or broken selection containers, and applies the same row protection to the phone number country selection dialog."""
	),
	addon_version="0.1.1",
	addon_changelog=_(
		"""Fixed chat and message list focus speech in Telegram Desktop 6.8.3 and later by restoring focusable UIA list containers and avoiding failing selection container queries."""
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
markdownExtensions: list[str] = []
brailleTables: BrailleTables = {}
symbolDictionaries: SymbolDictionaries = {}
