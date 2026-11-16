"""Jinja methods for print formats.

Usage in a print format (e.g. Sales Invoice):

    {% set gc = get_girocode_data(doc) %}
    {% if gc %}
        <img src="{{ gc.qr }}" style="width: 30mm; height: 30mm;">
        IBAN {{ gc.iban_formatted }}, BIC {{ gc.bic }}, {{ gc.reference }}
    {% endif %}

All data (beneficiary, IBAN, BIC) is read from the company's Bank Account
in ERPNext. Nothing is hard-coded and nothing is sent to external services.
"""

import frappe
from frappe.utils import flt

from erpnext_girocode import epc


def _get(doc, field, default=None):
	if isinstance(doc, dict):
		return doc.get(field, default)
	return getattr(doc, field, default)


def _find_bank_account(company: str, bank_account: str | None = None):
	"""Return the Bank Account to print: the given one, otherwise the company's
	default account with an IBAN, otherwise any active company account with an IBAN."""
	fields = ["name", "bank", "iban", "branch_code", "company"]
	if bank_account:
		row = frappe.db.get_value("Bank Account", bank_account, fields, as_dict=True)
		if row and epc.is_valid_iban(row.iban):
			return row
		return None

	rows = frappe.get_all(
		"Bank Account",
		filters={"company": company, "is_company_account": 1, "disabled": 0, "iban": ["is", "set"]},
		fields=[*fields, "is_default"],
		order_by="is_default desc, creation asc",
	)
	for row in rows:
		if epc.is_valid_iban(row.iban):
			return row
	return None


def _get_bic(bank_account) -> str:
	"""BIC from the Bank's SWIFT number, otherwise from the Bank Account's branch code."""
	bic = ""
	if bank_account.bank:
		bic = epc.clean_bic(frappe.db.get_value("Bank", bank_account.bank, "swift_number"))
	return bic or epc.clean_bic(bank_account.branch_code)


def _get_amount(doc) -> float:
	"""Open amount of the document; for drafts the (rounded) grand total."""
	outstanding = _get(doc, "outstanding_amount")
	if outstanding is not None and (_get(doc, "docstatus") == 1 or flt(outstanding) > 0):
		return flt(outstanding, 2)
	total = _get(doc, "rounded_total") if not _get(doc, "disable_rounded_total") else None
	return flt(total or _get(doc, "grand_total"), 2)


def get_girocode_data(
	doc,
	bank_account: str | None = None,
	text: str | None = None,
	name: str | None = None,
	with_amount: bool = True,
	hide_when_paid: bool = True,
	scale: int = 4,
):
	"""Return a dict with the QR code (SVG data URI) and the payment details,
	or None if no GiroCode can be printed for this document.

	No GiroCode is printed for: currencies other than EUR, return/credit notes,
	cancelled documents, missing or invalid IBAN and (with `hide_when_paid`)
	submitted documents without an open amount.

	Arguments:
		doc: the document (e.g. Sales Invoice) in the print format
		bank_account: name of a Bank Account; default: the company's default account
		text: remittance text; default: the document name (e.g. the invoice number)
		name: beneficiary; default: the company name
		with_amount: put the open amount into the code
		hide_when_paid: print nothing if a submitted document is fully paid
		scale: size of one QR module in the SVG (the print size is set with CSS)
	"""
	try:
		if _get(doc, "docstatus") == 2 or _get(doc, "is_return"):
			return None
		if (_get(doc, "currency") or "EUR") != "EUR":
			return None

		company = _get(doc, "company")
		account = _find_bank_account(company, bank_account)
		if not account:
			return None

		amount = _get_amount(doc) if with_amount else None
		if hide_when_paid and _get(doc, "docstatus") == 1 and flt(_get(doc, "outstanding_amount")) <= 0:
			return None

		beneficiary = name or frappe.db.get_value("Company", company, "company_name") or company
		reference = text or _get(doc, "name") or ""
		bic = _get_bic(account)

		payload = epc.build_payload(
			name=beneficiary,
			iban=account.iban,
			amount=amount,
			bic=bic,
			text=reference,
		)
		amount_text = epc.format_amount(amount)
		return frappe._dict(
			qr=epc.svg_data_uri(payload, scale=scale),
			payload=payload,
			name=epc._one_line(beneficiary, epc.MAX_NAME),
			iban=epc.clean_iban(account.iban),
			iban_formatted=epc.format_iban(account.iban),
			bic=bic,
			bank=account.bank,
			bank_account=account.name,
			amount=flt(amount_text[3:]) if amount_text else None,
			reference=epc._one_line(reference, epc.MAX_TEXT),
		)
	except Exception:
		# A missing QR code must never break printing.
		frappe.log_error(title="GiroCode", reference_doctype=_get(doc, "doctype"), reference_name=_get(doc, "name"))
		return None


def get_girocode(doc, **kwargs) -> str:
	"""Return only the QR code as an SVG data URI, or '' if none can be printed."""
	data = get_girocode_data(doc, **kwargs)
	return data.qr if data else ""
