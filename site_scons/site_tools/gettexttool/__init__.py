"""This tool allows generation of gettext .mo compiled files, pot files from source code files
and pot files for merging.

Three new builders are added into the constructed environment:

- gettextMoFile: generates .mo file from a .po file.
- gettextPotFile: Generates .pot file from source code files.
- gettextMergePotFile: Creates a .pot file appropriate for merging into existing .po files.

To properly configure get text, define the following variables:

- gettext_package_bugs_address
- gettext_package_name
- gettext_package_version


"""

import ast
import struct
from pathlib import Path

from SCons.Action import Action


def exists(env):
	return True


XGETTEXT_COMMON_ARGS = (
	"--msgid-bugs-address='$gettext_package_bugs_address' "
	"--package-name='$gettext_package_name' "
	"--package-version='$gettext_package_version' "
	"--keyword=pgettext:1c,2 "
	"-c -o $TARGET $SOURCES"
)


def _unquotePoString(line: str, lineNo: int) -> str:
	try:
		value = ast.literal_eval(line)
	except (SyntaxError, ValueError) as e:
		raise ValueError(f"Invalid PO string literal on line {lineNo}: {line}") from e
	if not isinstance(value, str):
		raise ValueError(f"Invalid PO string literal on line {lineNo}: {line}")
	return value


def _readPoCatalog(source: Path) -> dict[str, str]:
	messages: dict[str, str] = {}
	msgctxt: str | None = None
	msgid: str | None = None
	msgidPlural: str | None = None
	msgstrs: dict[int, str] = {}
	activeField: tuple[str, int | None] | None = None
	isFuzzy = False

	def finishEntry():
		nonlocal msgctxt, msgid, msgidPlural, msgstrs, activeField, isFuzzy
		if msgid is not None and not isFuzzy:
			key = msgid if msgctxt is None else f"{msgctxt}\x04{msgid}"
			if msgidPlural is not None:
				key = f"{key}\x00{msgidPlural}"
				message = "\x00".join(msgstrs.get(index, "") for index in sorted(msgstrs))
			else:
				message = msgstrs.get(0, "")
			messages[key] = message
		msgctxt = None
		msgid = None
		msgidPlural = None
		msgstrs = {}
		activeField = None
		isFuzzy = False

	def appendToActive(value: str):
		nonlocal msgctxt, msgid, msgidPlural
		if activeField is None:
			raise ValueError(f"PO continuation without an active field in {source}")
		field, index = activeField
		if field == "msgctxt":
			msgctxt = (msgctxt or "") + value
		elif field == "msgid":
			msgid = (msgid or "") + value
		elif field == "msgid_plural":
			msgidPlural = (msgidPlural or "") + value
		elif field == "msgstr":
			assert index is not None
			msgstrs[index] = msgstrs.get(index, "") + value

	for lineNo, rawLine in enumerate(source.read_text(encoding="utf-8-sig").splitlines(), start=1):
		line = rawLine.strip()
		if not line:
			finishEntry()
			continue
		if line.startswith("#,") and "fuzzy" in line.split(",", 1)[1]:
			isFuzzy = True
			continue
		if line.startswith("#"):
			continue
		if line.startswith('"'):
			appendToActive(_unquotePoString(line, lineNo))
			continue
		if line.startswith("msgctxt "):
			msgctxt = _unquotePoString(line[8:].strip(), lineNo)
			activeField = ("msgctxt", None)
			continue
		if line.startswith("msgid_plural "):
			msgidPlural = _unquotePoString(line[13:].strip(), lineNo)
			activeField = ("msgid_plural", None)
			continue
		if line.startswith("msgid "):
			if msgid is not None:
				finishEntry()
			msgid = _unquotePoString(line[6:].strip(), lineNo)
			activeField = ("msgid", None)
			continue
		if line.startswith("msgstr["):
			indexText, valueText = line[7:].split("]", 1)
			index = int(indexText)
			msgstrs[index] = _unquotePoString(valueText.strip(), lineNo)
			activeField = ("msgstr", index)
			continue
		if line.startswith("msgstr "):
			msgstrs[0] = _unquotePoString(line[7:].strip(), lineNo)
			activeField = ("msgstr", 0)
			continue
		raise ValueError(f"Unsupported PO syntax on line {lineNo}: {rawLine}")
	finishEntry()
	return messages


def _writeMoCatalog(messages: dict[str, str], target: Path):
	keys = sorted(messages, key=lambda key: key.encode("utf-8"))
	ids = [key.encode("utf-8") for key in keys]
	strs = [messages[key].encode("utf-8") for key in keys]
	count = len(keys)
	keystart = 7 * 4 + count * 16
	valuestart = keystart + sum(len(messageId) + 1 for messageId in ids)

	keyOffsets: list[tuple[int, int]] = []
	offset = keystart
	for messageId in ids:
		keyOffsets.append((len(messageId), offset))
		offset += len(messageId) + 1

	valueOffsets: list[tuple[int, int]] = []
	offset = valuestart
	for messageStr in strs:
		valueOffsets.append((len(messageStr), offset))
		offset += len(messageStr) + 1

	output = [
		struct.pack("<Iiiiiii", 0x950412DE, 0, count, 7 * 4, 7 * 4 + count * 8, 0, 0),
		*(struct.pack("<ii", length, offset) for length, offset in keyOffsets),
		*(struct.pack("<ii", length, offset) for length, offset in valueOffsets),
		b"\x00".join(ids),
		b"\x00",
		b"\x00".join(strs),
		b"\x00",
	]
	target.parent.mkdir(parents=True, exist_ok=True)
	target.write_bytes(b"".join(output))


def _compileMo(target, source, env):
	messages = _readPoCatalog(Path(str(source[0])))
	_writeMoCatalog(messages, Path(str(target[0])))
	return None


def generate(env):
	env.SetDefault(gettext_package_bugs_address="example@example.com")
	env.SetDefault(gettext_package_name="")
	env.SetDefault(gettext_package_version="")

	env["BUILDERS"]["gettextMoFile"] = env.Builder(
		action=Action(_compileMo, "Compiling translation $SOURCE"),
		suffix=".mo",
		src_suffix=".po",
	)

	env["BUILDERS"]["gettextPotFile"] = env.Builder(
		action=Action("xgettext " + XGETTEXT_COMMON_ARGS, "Generating pot file $TARGET"),
		suffix=".pot",
	)

	env["BUILDERS"]["gettextMergePotFile"] = env.Builder(
		action=Action(
			"xgettext " + "--omit-header --no-location " + XGETTEXT_COMMON_ARGS,
			"Generating pot file $TARGET",
		),
		suffix=".pot",
	)
