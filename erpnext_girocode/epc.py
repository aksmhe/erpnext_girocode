"""EPC QR code (GiroCode) for SEPA credit transfers.

Implements the payload of the European Payments Council guideline
EPC069-12 "Quick Response Code: Guidelines to Enable Data Capture for the
Initiation of a SEPA Credit Transfer", version 002, character set UTF-8.

This module does not depend on Frappe, so it can be tested on its own.
The QR code is created locally with `pyqrcode` (a Frappe dependency).
No data leaves the server.
"""

import base64
import io
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MAX_NAME = 70
MAX_TEXT = 140
MAX_INFO = 70
MAX_PAYLOAD_BYTES = 331
MIN_AMOUNT = Decimal("0.01")
MAX_AMOUNT = Decimal("999999999.99")

BIC_RE = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$")
IBAN_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$")
PURPOSE_RE = re.compile(r"^[A-Z0-9]{4}$")


class EPCError(ValueError):
	"""Raised when the data cannot be put into a valid EPC QR code."""


def clean_iban(iban: str | None) -> str:
	return re.sub(r"\s+", "", iban or "").upper()


def is_valid_iban(iban: str | None) -> bool:
	"""Check format and checksum (ISO 13616, mod 97)."""
	iban = clean_iban(iban)
	if not IBAN_RE.match(iban):
		return False
	rearranged = iban[4:] + iban[:4]
	digits = "".join(str(int(ch, 36)) for ch in rearranged)
	return int(digits) % 97 == 1


def format_iban(iban: str | None) -> str:
	"""Group an IBAN in blocks of four for printing, e.g. 'DE54 3002 0900 ...'."""
	iban = clean_iban(iban)
	return " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))


def clean_bic(bic: str | None) -> str:
	bic = re.sub(r"\s+", "", bic or "").upper()
	return bic if BIC_RE.match(bic) else ""


def _one_line(value, max_len: int) -> str:
	"""Remove line breaks and surplus spaces, then cut to max_len characters."""
	value = re.sub(r"\s+", " ", str(value or "")).strip()
	return value[:max_len].rstrip()


def format_amount(amount) -> str:
	"""Return 'EUR123.45', or '' if there is no positive amount."""
	if amount in (None, ""):
		return ""
	try:
		value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
	except (InvalidOperation, ValueError):
		raise EPCError(f"Invalid amount: {amount!r}")
	if value < MIN_AMOUNT:
		return ""
	if value > MAX_AMOUNT:
		raise EPCError(f"Amount too large for an EPC QR code: {value}")
	return f"EUR{value}"


def build_payload(
	name: str,
	iban: str,
	amount=None,
	bic: str | None = None,
	text: str | None = None,
	reference: str | None = None,
	purpose: str | None = None,
	info: str | None = None,
) -> str:
	"""Build the text content of an EPC QR code (version 002, UTF-8, SCT).

	- `amount` is only written when it is greater than 0.
	- Use either `text` (unstructured remittance, max. 140 characters)
	  or `reference` (structured creditor reference, e.g. RF..., max. 35),
	  not both. If both are given, `reference` wins.
	"""
	name = _one_line(name, MAX_NAME)
	if not name:
		raise EPCError("Beneficiary name is missing")

	iban = clean_iban(iban)
	if not is_valid_iban(iban):
		raise EPCError(f"Invalid IBAN: {iban!r}")

	reference = re.sub(r"\s+", "", reference or "").upper()[:35]
	text = "" if reference else _one_line(text, MAX_TEXT)
	purpose = (purpose or "").strip().upper()
	if purpose and not PURPOSE_RE.match(purpose):
		raise EPCError(f"Invalid purpose code: {purpose!r}")

	lines = [
		"BCD",
		"002",
		"1",  # UTF-8
		"SCT",
		clean_bic(bic),
		name,
		iban,
		format_amount(amount),
		purpose,
		reference,
		text,
		_one_line(info, MAX_INFO),
	]
	# trailing empty fields may be left out
	while lines and lines[-1] == "":
		lines.pop()

	payload = "\n".join(lines)
	# The whole payload may have at most 331 bytes. Umlauts take 2 bytes in
	# UTF-8, so a long remittance text is shortened until it fits.
	while len(payload.encode("utf-8")) > MAX_PAYLOAD_BYTES and len(lines) > 10 and lines[10]:
		lines[10] = lines[10][:-1].rstrip()
		payload = "\n".join(lines)
	if len(payload.encode("utf-8")) > MAX_PAYLOAD_BYTES:
		raise EPCError("EPC QR code payload is longer than 331 bytes")
	return payload


def make_qr(payload: str):
	"""Return a pyqrcode object with the settings the EPC guideline requires
	(error correction level M, byte mode, UTF-8)."""
	import pyqrcode

	return pyqrcode.create(payload, error="M", mode="binary", encoding="utf-8")


def svg_data_uri(payload: str, scale: int = 4, quiet_zone: int = 4) -> str:
	"""Return the QR code as an SVG data URI for an <img src="...">."""
	stream = io.BytesIO()
	make_qr(payload).svg(stream, scale=scale, quiet_zone=quiet_zone, xmldecl=False)
	return "data:image/svg+xml;base64," + base64.b64encode(stream.getvalue()).decode()
