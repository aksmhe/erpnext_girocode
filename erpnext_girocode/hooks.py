app_name = "erpnext_girocode"
app_title = "GiroCode"
app_publisher = "AffiKSys"
app_description = "GiroCode (EPC-QR-Code) für SEPA-Überweisungen auf Rechnungen, lokal erzeugt"
app_email = "m.heide@affiksys.com"
app_license = "mit"

# Jinja-Funktionen für Druckformate: get_girocode_data(doc) und get_girocode(doc)
jinja = {
	"methods": [
		"erpnext_girocode.jinja.get_girocode_data",
		"erpnext_girocode.jinja.get_girocode",
	],
}
