"""Tests for the EPC payload. They need no Frappe site:

    python -m unittest erpnext_girocode.tests.test_epc
"""

import unittest

from erpnext_girocode import epc

# Public sample IBAN from the EPC/Bundesbank documentation
IBAN = "DE89370400440532013000"


class TestEPC(unittest.TestCase):
	def test_payload_full(self):
		payload = epc.build_payload(
			name="Muster GmbH", iban="DE89 3704 0044 0532 0130 00", amount=123.45, bic="COBADEFFXXX", text="RE-2026-0001"
		)
		self.assertEqual(
			payload,
			"BCD\n002\n1\nSCT\nCOBADEFFXXX\nMuster GmbH\nDE89370400440532013000\nEUR123.45\n\n\nRE-2026-0001",
		)

	def test_amount_format(self):
		self.assertEqual(epc.format_amount(160), "EUR160.00")
		self.assertEqual(epc.format_amount("0.005"), "EUR0.01")
		self.assertEqual(epc.format_amount(0), "")
		self.assertEqual(epc.format_amount(-5), "")
		self.assertEqual(epc.format_amount(None), "")
		with self.assertRaises(epc.EPCError):
			epc.format_amount(1_000_000_000)

	def test_no_amount_no_bic(self):
		payload = epc.build_payload(name="Muster", iban=IBAN, amount=0, text="X")
		self.assertEqual(payload.split("\n")[4], "")
		self.assertEqual(payload.split("\n")[7], "")

	def test_trailing_fields_dropped(self):
		payload = epc.build_payload(name="Muster", iban=IBAN)
		self.assertEqual(payload, "BCD\n002\n1\nSCT\n\nMuster\nDE89370400440532013000")

	def test_text_limits_and_umlauts(self):
		payload = epc.build_payload(name="Müller & Söhne\nGbR " + "x" * 80, iban=IBAN, text="a" * 200)
		lines = payload.split("\n")
		self.assertEqual(len(lines[5]), 70)
		self.assertTrue(lines[5].startswith("Müller & Söhne GbR"))
		self.assertEqual(len(lines[10]), 140)

	def test_payload_max_331_bytes(self):
		payload = epc.build_payload(name="Ä" * 70, iban=IBAN, amount=1, bic="COBADEFFXXX", text="ä" * 140)
		self.assertLessEqual(len(payload.encode("utf-8")), 331)
		self.assertTrue(payload.split("\n")[10].startswith("ää"))

	def test_reference_wins_over_text(self):
		lines = epc.build_payload(name="M", iban=IBAN, text="abc", reference="RF18 5390 0754 7034").split("\n")
		self.assertEqual(lines[9], "RF18539007547034")
		self.assertEqual(len(lines), 10)  # no text line

	def test_invalid_iban(self):
		with self.assertRaises(epc.EPCError):
			epc.build_payload(name="M", iban="DE89370400440532013001")
		self.assertFalse(epc.is_valid_iban(""))

	def test_bic(self):
		self.assertEqual(epc.clean_bic("cmcidedd"), "CMCIDEDD")
		self.assertEqual(epc.clean_bic("123"), "")

	def test_format_iban(self):
		self.assertEqual(epc.format_iban(IBAN), "DE89 3704 0044 0532 0130 00")

	def test_svg(self):
		uri = epc.svg_data_uri(epc.build_payload(name="M", iban=IBAN, amount=1))
		self.assertTrue(uri.startswith("data:image/svg+xml;base64,"))


if __name__ == "__main__":
	unittest.main()
