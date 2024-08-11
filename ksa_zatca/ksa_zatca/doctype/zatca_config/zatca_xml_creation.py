import frappe
from frappe import _
from lxml import etree
import xml
import xml.dom.minidom as minidom
import qrcode
import base64
import uuid
import hashlib
import re
import ecdsa
from base64 import b64encode
from pyqrcode import create as qr_create
import os
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography import x509
from datetime import datetime
import io


ns_map = {
    # '': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    'sig': 'urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2',
    'sac': 'urn:oasis:names:specification:ubl:schema:xsd:SignatureAggregateComponents-2',
    'sbc': 'urn:oasis:names:specification:ubl:schema:xsd:SignatureBasicComponents-2',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
    'xades': 'http://uri.etsi.org/01903/v1.3.2#'
}

def read_xml_file(data):
    if data.get('invoice_type','') == '0100000':
        tree = etree.parse(frappe.get_app_path('ksa_zatca','fatoora/standard.xml'))
    else:
        tree = etree.parse(frappe.get_app_path('ksa_zatca','fatoora/simplified.xml'))
        
    root = tree.getroot()
    return root

def fill_basic_data(root,data):
    invoice_name=root.find('cbc:ID',ns_map)
    invoice_name.text = data.get('invoice_name','S000')
    invoice_uuid = root.find('.//cbc:UUID',ns_map)
    invoice_uuid.text = data.get('uuid','None')
    invoice_date = root.find('.//cbc:IssueDate',ns_map)
    invoice_date.text = data.get('invoice_date','2024-02-23')
    invoice_time = root.find('.//cbc:IssueTime',ns_map)
    invoice_time.text = data.get('invoice_time','12:00:00')
    invoice_type_code = root.find('.//cbc:InvoiceTypeCode',ns_map)
    invoice_type_code.text = data.get('invoice_type_code', '388')
    invoice_type_code.set('name',data.get('invoice_type', '0500000'))
    invoice_document_currency = root.find('.//cbc:DocumentCurrencyCode',ns_map)
    invoice_document_currency.text = data.get('invoice_currency', 'SAR')
    invoice_tax_currency = root.find('.//cbc:TaxCurrencyCode',ns_map)
    invoice_tax_currency.text = data.get('tax_currency', 'SAR')
    if data.get('invoice_type_code') != '388':
        billing_reference = etree.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}BillingReference")
        invoice_document_reference = etree.SubElement(billing_reference, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}InvoiceDocumentReference")
        invoice_document_reference_id = etree.SubElement(invoice_document_reference, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID")
        invoice_document_reference_id.text = data.get('billing_ref','None')
        billing_reference.tail = '\n' + ' '*4
        etree.indent(billing_reference,space=' '*4,level=1)
        
        # Find the index of TaxCurrencyCode and insert BillingReference after it
        index_tax_currency = root.index(invoice_tax_currency)
        root.insert(index_tax_currency + 1, billing_reference)
    invoice_icv = root.find('.//cac:AdditionalDocumentReference[cbc:ID="ICV"]/cbc:UUID', ns_map)
    invoice_icv.text = data.get('icv', '1')
    invoice_pih = root.find('.//cac:AdditionalDocumentReference[cbc:ID="PIH"]/cac:Attachment/cbc:EmbeddedDocumentBinaryObject',ns_map)
    invoice_pih.text = data.get('pih', 'NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ==')
    return root

def fill_supplier_customer_data(root,data):
    seller_cr = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID', ns_map)
    seller_cr.text = data.get('seller_cr','31111121113')
    seller_st = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:StreetName', ns_map)
    seller_st.text = data.get('seller_st','Ali st')
    seller_bn = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:BuildingNumber', ns_map)
    seller_bn.text = data.get('seller_bn','63153')
    seller_d = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:CitySubdivisionName', ns_map)
    seller_d.text = data.get('seller_d','flowers district')
    seller_city = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:CityName', ns_map)
    seller_city.text = data.get('seller_city','Riyadh')
    seller_pz = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:PostalZone', ns_map)
    seller_pz.text = data.get('seller_pz','13203')
    seller_c = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cac:Country/cbc:IdentificationCode', ns_map)
    seller_c.text = data.get('seller_c','SA')
    seller_id = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID', ns_map)
    seller_id.text = data.get('seller_id','331131300003')
    seller_name = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName', ns_map)
    seller_name.text = data.get('seller_name','Amr Alaa')
    #
    if data.get('invoice_type') == '0100000':
        customer_cr = root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID', ns_map)
        customer_cr.text = data.get('customer_cr','31111121113')
        customer_st = root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PostalAddress/cbc:StreetName', ns_map)
        customer_st.text = data.get('customer_st','Ali st')
        customer_bn = root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PostalAddress/cbc:BuildingNumber', ns_map)
        customer_bn.text = data.get('customer_bn','63153')
        customer_d = root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PostalAddress/cbc:CitySubdivisionName', ns_map)
        customer_d.text = data.get('customer_d','flowers district')
        customer_city = root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PostalAddress/cbc:CityName', ns_map)
        customer_city.text = data.get('customer_city','Riyadh')
        customer_pz = root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PostalAddress/cbc:PostalZone', ns_map)
        customer_pz.text = data.get('customer_pz','13203')
        customer_c = root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PostalAddress/cac:Country/cbc:IdentificationCode', ns_map)
        customer_c.text = data.get('customer_c','SA')
        customer_id = root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID', ns_map) #
        customer_id.text = data.get('customer_id','331131300003')
        customer_name = root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName', ns_map)
        customer_name.text = data.get('customer_name','Amr Alaa')
        
    if data.get('invoice_type_code') == '388' and data.get('invoice_type') == '0100000':
        accounting_customer_party = root.find('.//cac:AccountingCustomerParty', ns_map)
        delivery = etree.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Delivery")
        delivery_date = etree.SubElement(delivery, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ActualDeliveryDate")
        delivery_date.text = data.get('invoice_date','2024-02-23')
        delivery.tail = '\n' + ' '*4
        etree.indent(delivery,space=' '*4,level=1)
        
        index_accounting_customer_party = root.index(accounting_customer_party)
        root.insert(index_accounting_customer_party + 1, delivery)
    
    if data.get('invoice_type_code') != '388':
        accounting_customer_party = root.find('.//cac:AccountingCustomerParty', ns_map)
        payment_means = etree.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PaymentMeans")
        payment_means_code = etree.SubElement(payment_means, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}PaymentMeansCode")
        payment_means_code.text = "10"
        instruction_note = etree.SubElement(payment_means, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}InstructionNote")
        instruction_note.text = data.get('return_reason','None')
        payment_means.tail = '\n' + ' '*4
        etree.indent(payment_means,space=' '*4,level=1)
        
        index_accounting_customer_party = root.index(accounting_customer_party)
        root.insert(index_accounting_customer_party + 1, payment_means)
    
    return root

def fill_allowance_charge(root,data):
    for tax in data.get('tax_subtotal',[]):
        allowance_charge = etree.Element("{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AllowanceCharge")
        
        charge_indicator = etree.SubElement(allowance_charge, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ChargeIndicator")
        charge_indicator.text = "false"
        
        allowance_charge_reason = etree.SubElement(allowance_charge, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}AllowanceChargeReason")
        allowance_charge_reason.text = "discount"
        
        amount = etree.SubElement(allowance_charge, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Amount")
        amount.set("currencyID", "SAR")
        amount.text = str(round(abs(tax['discount']),2))
        # if tax["tax_category_id"] == "S":
        #     amount.text = data.get('allowance_total_amount', '0')
        # else:
        #     amount.text = '0'
        
        tax_category = etree.SubElement(allowance_charge, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxCategory")
        tax_category_id = etree.SubElement(tax_category, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID")
        tax_category_id.set("schemeID", "UN/ECE 5305")
        tax_category_id.set("schemeAgencyID", "6")
        tax_category_id.text = tax["tax_category_id"]
        
        percent = etree.SubElement(tax_category, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Percent")
        percent.text = str(tax["tax_rate"])
        
        tax_scheme = etree.SubElement(tax_category, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxScheme")
        tax_scheme_id = etree.SubElement(tax_scheme, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID")
        tax_scheme_id.set("schemeID", "UN/ECE 5153")
        tax_scheme_id.set("schemeAgencyID", "6")
        tax_scheme_id.text = "VAT"
        
        etree.indent(allowance_charge,space=' '*4,level=1)
        allowance_charge.tail = '\n' + ' '*4
        delivery = root.find(".//cac:Delivery", ns_map)
        customer_tag = root.find(".//cac:AccountingCustomerParty", ns_map)
        if delivery is not None:
            if data.get('invoice_type_code') == '388':
                root.insert(root.index(delivery)+1,allowance_charge)
            else:
                root.insert(root.index(delivery)+2,allowance_charge)
        elif data.get('invoice_type_code') == '388':
            root.insert(root.index(customer_tag)+1,allowance_charge)
        else:
            root.insert(root.index(customer_tag)+2,allowance_charge)
    return root

def fill_taxes_data(root, data):
    tax_totals = root.findall('.//cac:TaxTotal', ns_map)

    # Update base total tax amount
    base_total_tax_amount = tax_totals[0].find('.//cbc:TaxAmount', ns_map)
    base_total_tax_amount.text = data.get('base_total_tax_amount', '0')
    base_total_tax_amount.set('currencyID', data.get('tax_currency', 'SAR'))

    # Update total tax amount
    total_tax_amount = tax_totals[-1].find('.//cbc:TaxAmount', ns_map)
    total_tax_amount.text = data.get('total_tax_amount', '0')
    total_tax_amount.set('currencyID', data.get('invoice_currency', 'SAR'))
    # Add tail before subtax
    total_tax_amount.tail = '\n' + ' '*8
    
    # Loop to add tax subtotals / add suitable tails
    for tax_subtotal_data in data.get('tax_subtotal', []):
        # Create tax subtotal element with the correct namespace
        tax_subtotal = etree.Element('{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxSubtotal')
        
        # Create and set taxable amount
        taxable_amount = etree.SubElement(tax_subtotal, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxableAmount')
        # if tax_subtotal_data.get('tax_category_id') == "S":
        #     taxable_amount.text = str(tax_subtotal_data.get('taxable_amount', '0') - data.get('discount_amount'))
        # else:
        taxable_amount.text = str(tax_subtotal_data.get('taxable_amount', '0'))
        taxable_amount.set('currencyID', data.get('invoice_currency', 'SAR'))

        # Create and set tax amount
        tax_amount = etree.SubElement(tax_subtotal, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxAmount')
        tax_amount.text = str(tax_subtotal_data.get('tax_amount', '0'))
        tax_amount.set('currencyID', data.get('invoice_currency', 'SAR'))

        # Create and set tax category
        tax_category = etree.SubElement(tax_subtotal, '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxCategory')
        tax_category_id = etree.SubElement(tax_category, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID')
        tax_category_id.text = tax_subtotal_data.get('tax_category_id', 'S')
        tax_category_id.set('schemeID', 'UN/ECE 5305')
        tax_category_id.set('schemeAgencyID', '6')
        tax_category_percent = etree.SubElement(tax_category, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Percent')
        tax_category_percent.text = str(tax_subtotal_data.get('tax_rate', '15.00'))
        if tax_subtotal_data.get('tax_category_id') !="S":
            tax_category_exemption_reason_code = etree.SubElement(tax_category, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxExemptionReasonCode')
            tax_category_exemption_reason_code.text = tax_subtotal_data.get('tax_exemption_reason_code')
            tax_category_exemption_reason = etree.SubElement(tax_category, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxExemptionReason')
            tax_category_exemption_reason.text = tax_subtotal_data.get('tax_exemption_reason_text')

        # Create and set tax scheme
        tax_scheme = etree.SubElement(tax_category, '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxScheme')
        tax_scheme_id = etree.SubElement(tax_scheme, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID')
        tax_scheme_id.text ='VAT'
        tax_scheme_id.set('schemeID', 'UN/ECE 5305')
        tax_scheme_id.set('schemeAgencyID', '6')
        
        # Indent the tag
        etree.indent(tax_subtotal,space=' '*4,level=2)
        # Fix tag tail
        tax_subtotal.tail = '\n' + ' '*8 if data.get('tax_subtotal', [])[-1] != tax_subtotal_data else '\n' + ' '*4
        # Insert the tax subtotal element into the tax totals
        tax_totals[-1].insert(len(tax_totals[-1]), tax_subtotal)

    return root

def fill_totals_data(root,data):
    # Find LegalMonetaryTotal element
    legal_monetary_total = root.find('.//cac:LegalMonetaryTotal', ns_map)
    
    # Find and fill LineExtensionAmount
    line_extension_amount = legal_monetary_total.find('.//cbc:LineExtensionAmount', ns_map)
    line_extension_amount.text = data.get('line_extension_amount', '0.00')
    line_extension_amount.set('currencyID', data.get('invoice_currency', 'SAR'))

    # Find and fill TaxExclusiveAmount
    tax_exclusive_amount = legal_monetary_total.find('.//cbc:TaxExclusiveAmount', ns_map)
    tax_exclusive_amount.text = data.get('tax_exclusive_amount', '0.00')
    tax_exclusive_amount.set('currencyID', data.get('invoice_currency', 'SAR'))

    # Find and fill TaxInclusiveAmount
    tax_inclusive_amount = legal_monetary_total.find('.//cbc:TaxInclusiveAmount', ns_map)
    tax_inclusive_amount.text = data.get('tax_inclusive_amount', '0.00')
    tax_inclusive_amount.set('currencyID', data.get('invoice_currency', 'SAR'))

    # Find and fill AllowanceTotalAmount
    allowance_total_amount = legal_monetary_total.find('.//cbc:AllowanceTotalAmount', ns_map)
    allowance_total_amount.text = data.get('allowance_total_amount', '0.00')
    allowance_total_amount.set('currencyID', data.get('invoice_currency', 'SAR'))

    # Find and fill PrepaidAmount
    prepaid_amount = legal_monetary_total.find('.//cbc:PrepaidAmount', ns_map)
    prepaid_amount.text = data.get('prepaid_amount', '0.00')
    prepaid_amount.set('currencyID', data.get('invoice_currency', 'SAR'))

    # Find and fill PayableAmount
    payable_amount = legal_monetary_total.find('.//cbc:PayableAmount', ns_map)
    payable_amount.text = data.get('payable_amount', '0.00')
    payable_amount.set('currencyID', data.get('invoice_currency', 'SAR'))

    return root
    
def fill_items_data(root,data):
    legal_monetary_total = root.find('.//cac:LegalMonetaryTotal', ns_map)
    legal_monetary_total.tail = '\n' + ' '*4
    
    # Loop through each item in the dummy data
    for idx, item_data in enumerate(data.get('items', [])):
        # Create a new InvoiceLine element
        invoice_line = etree.SubElement(root, '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}InvoiceLine')

        # Create and set the ID element
        line_id = etree.SubElement(invoice_line, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID')
        line_id.text = item_data.get('id')

        # Create and set the InvoicedQuantity element
        invoiced_quantity = etree.SubElement(invoice_line, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}InvoicedQuantity')
        invoiced_quantity.set('unitCode', item_data.get('unit_code', 'PCE'))
        invoiced_quantity.text = item_data.get('quantity')

        # Create and set the LineExtensionAmount element
        line_extension_amount = etree.SubElement(invoice_line, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}LineExtensionAmount')
        line_extension_amount.set('currencyID', item_data.get('invoice_currency', 'SAR'))
        line_extension_amount.text = item_data.get('line_extension_amount')

        # Create the TaxTotal element
        tax_total = etree.SubElement(invoice_line, '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxTotal')

        # Create and set the TaxAmount element inside TaxTotal
        tax_amount = etree.SubElement(tax_total, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxAmount')
        tax_amount.set('currencyID', item_data.get('invoice_currency', 'SAR'))
        tax_amount.text = item_data.get('tax_amount')

        # Create and set the RoundingAmount element inside TaxTotal
        rounding_amount = etree.SubElement(tax_total, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}RoundingAmount')
        rounding_amount.set('currencyID', item_data.get('invoice_currency', 'SAR'))
        rounding_amount.text = item_data.get('rounding_amount')

        # Create the Item element
        item = etree.SubElement(invoice_line, '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Item')

        # Create and set the Name element
        item_name = etree.SubElement(item, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Name')
        item_name.text = item_data.get('name')

        # Create the ClassifiedTaxCategory element
        classified_tax_category = etree.SubElement(item, '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}ClassifiedTaxCategory')

        # Create and set the ID element
        tax_category_id = etree.SubElement(classified_tax_category, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID')
        tax_category_id.text = item_data.get('tax_category_id')

        # Create and set the Percent element
        tax_percent = etree.SubElement(classified_tax_category, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Percent')
        tax_percent.text = item_data.get('tax_percent')

        # Create the TaxScheme element
        tax_scheme = etree.SubElement(classified_tax_category, '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxScheme')

        # Create and set the ID element inside TaxScheme
        tax_scheme_id = etree.SubElement(tax_scheme, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID')
        tax_scheme_id.text = item_data.get('tax_scheme_id')

        # Create the Price element
        price = etree.SubElement(invoice_line, '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Price')

        # Create and set the PriceAmount element inside Price
        price_amount = etree.SubElement(price, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}PriceAmount')
        price_amount.set('currencyID', item_data.get('invoice_currency', 'SAR'))
        price_amount.text = item_data.get('price_amount')

        # Create the AllowanceCharge element inside Price
        allowance_charge = etree.SubElement(price, '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AllowanceCharge')

        # Create and set the ChargeIndicator element inside AllowanceCharge
        charge_indicator = etree.SubElement(allowance_charge, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ChargeIndicator')
        charge_indicator.text = 'true'

        # Create and set the AllowanceChargeReason element inside AllowanceCharge
        allowance_charge_reason = etree.SubElement(allowance_charge, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}AllowanceChargeReason')
        allowance_charge_reason.text = item_data.get('allowance_charge_reason', 'discount')

        # Create and set the Amount element inside AllowanceCharge
        allowance_charge_amount = etree.SubElement(allowance_charge, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Amount')
        allowance_charge_amount.set('currencyID', item_data.get('invoice_currency', 'SAR'))
        allowance_charge_amount.text = item_data.get('allowance_charge_amount', '0.00')
        
        # Indent the tag
        etree.indent(invoice_line,space=' '*4,level=1)
        # Fix tag tail
        # invoice_line.tail = '\n' + ' '*8 if data.get('items', [])[-1] == item_data else ''
        if idx == len(data.get('items', [])) - 1:
            invoice_line.tail = '\n'
        else:
            invoice_line.tail = '\n' + ' ' * 4

        root.insert(root.index(legal_monetary_total) + idx + 1, invoice_line)

    # Return the root element
    return root

def hex_to_base64(hex_string):
    byte_array = bytearray.fromhex(hex_string)
    base64_val = base64.b64encode(byte_array)
    return base64_val

# def hash_invoice(root, dummy_data):
#     # Remove specified tags using XPath
#     tags_to_remove = [
#         '//*[local-name()="UBLExtensions"]',
#         '//*[local-name()="AdditionalDocumentReference"][cbc:ID[normalize-space(text()) = "QR"]]',
#         '//*[local-name()="Signature"]'
#     ]
#     for xpath in tags_to_remove:
#         for element in root.xpath(xpath, namespaces=ns_map):
#             element.getparent().remove(element)

#     # Remove XML version
#     xml_str = etree.tostring(root, encoding="unicode", xml_declaration=False)

#     # Canonicalize the invoice using the C14N11 standard
#     canonical_xml = etree.tostring(root, method="c14n", exclusive=True, with_comments=False)

#     # Hash the new invoice body using SHA-256
#     hash_value = hashlib.sha256(canonical_xml).digest()

#     # Convert hashed value to hex string
#     hex_hash = hash_value.hex()

#     # Convert hex string to base64
#     base64_hash = hex_to_base64(hex_hash)
    
#     dummy_data['invoice_hash_hex'] = hex_hash
#     dummy_data['invoice_hash_encoded'] = base64_hash

#     return base64_hash

def hash_invoice(root, dummy_data):
    # Remove specified tags using XPath
    tags_to_remove = [
        '//*[local-name()="UBLExtensions"]',
        '//*[local-name()="AdditionalDocumentReference"][cbc:ID[normalize-space(text()) = "QR"]]',
        '//*[local-name()="Signature"]'
    ]
    for xpath in tags_to_remove:
        for element in root.xpath(xpath, namespaces=ns_map):
            element.getparent().remove(element)

    # Convert the root to a minidom document
    xml_str = etree.tostring(root, method="c14n")
    # Canonicalize the invoice using the C14N11 standard
    dom = minidom.parseString(xml_str)

    if dummy_data.get('invoice_type_code') != '388':
        payment_means_code = dom.getElementsByTagName('cbc:PaymentMeansCode')[0]
        payment_means_code.appendChild(dom.createTextNode(""))
    # Find the profileid tag
    profileid_tag = dom.getElementsByTagName('cbc:ProfileID')[0]

    # # Insert a text node before the profileid tag
    text_node1 = dom.createTextNode("\n    ")
    text_node2 = dom.createTextNode("\n    ")
    profileid_tag.parentNode.insertBefore(text_node1, profileid_tag)
    profileid_tag.parentNode.insertBefore(text_node2, profileid_tag)
    
    
    # Get the XML string representation after modification
    modified_xml_str = dom.childNodes[0].toprettyxml(indent='', newl='')
    
    with open('result.xml','w') as f:
        f.write(modified_xml_str)


    # Hash the new invoice body using SHA-256
    hash_value = hashlib.sha256(modified_xml_str.encode()).digest()

    # Convert hashed value to hex string
    hex_hash = hash_value.hex()

    # Convert hex string to base64
    base64_hash = hex_to_base64(hex_hash)
    
    dummy_data['invoice_hash_hex'] = hex_hash
    dummy_data['invoice_hash_encoded'] = base64_hash.decode()

    return dummy_data

def sign_invoice_hash(dummy_data):
    private_key = dummy_data.get('private_key')
    invoice_hash = dummy_data.get('invoice_hash_hex')
    
    # Get private key Bytes (pk object from pem)
    private_key_bytes = serialization.load_pem_private_key(
        private_key.encode(),
        password=None,  # Assuming the private key is not encrypted
        backend=default_backend()
    )
    
    # Sign the hash
    signature = private_key_bytes.sign(invoice_hash.encode(),ec.ECDSA(hashes.SHA256()))
    dummy_data['signing_time'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Encode the signature to base64
    base64_signature = base64.b64encode(signature)

    dummy_data['ecdsa_signature'] = base64_signature.decode()
    
    return dummy_data

def generate_certificate_hash(dummy_data):
    certificate = dummy_data.get('certificate')
    
    cert = f"-----BEGIN CERTIFICATE-----\n{certificate}\n-----END CERTIFICATE-----"

    cert_x509 = x509.load_pem_x509_certificate(cert.encode())
    
    # issuer_name = "CN="
    # for name in cert_x509.issuer:
    #     if name.oid == x509.NameOID.COMMON_NAME:
    #         issuer_name += name.value
    # issuer_name = cert_x509.issuer.rfc4514_string().replace('=', ' = ')
    issuer_name = cert_x509.issuer.rfc4514_string().replace(',', ', ')
    # issuer_name = cert_x509.subject.rfc4514_string()
    
    dummy_data['issuer_name'] = issuer_name
    dummy_data['serial_number'] = str(cert_x509.serial_number)

    public_key = cert_x509.public_key()
    public_key_pem= public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    public_key_str = public_key_pem.replace('-----BEGIN PUBLIC KEY-----\n','')
    public_key_str = public_key_str.replace('-----END PUBLIC KEY-----\n','')
    ecdsa_public_key = public_key_str
    
    dummy_data['cert_public_key'] = ecdsa_public_key
    
    signature = cert_x509.signature.hex()
    dummy_data['cert_signature'] = signature   
    
    # Hash the certificate using SHA-256
    hashed_certificate = hashlib.sha256(certificate.encode('utf-8')).hexdigest()

    # Encode the hashed certificate using base64
    encoded_hashed_certificate = base64.b64encode(hashed_certificate.encode()).decode('utf-8')
    
    dummy_data['certificate_hash'] = encoded_hashed_certificate
    
    return dummy_data

def fill_signed_properties_tag(root, data):
    # XPath expressions for each field
    digest_value_xpath = "./ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/sig:UBLDocumentSignatures/sac:SignatureInformation/ds:Signature/ds:Object/xades:QualifyingProperties/xades:SignedProperties/xades:SignedSignatureProperties/xades:SigningCertificate/xades:Cert/xades:CertDigest/ds:DigestValue"
    signing_time_xpath = "./ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/sig:UBLDocumentSignatures/sac:SignatureInformation/ds:Signature/ds:Object/xades:QualifyingProperties/xades:SignedProperties/xades:SignedSignatureProperties/xades:SigningTime"
    issuer_name_xpath = "./ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/sig:UBLDocumentSignatures/sac:SignatureInformation/ds:Signature/ds:Object/xades:QualifyingProperties/xades:SignedProperties/xades:SignedSignatureProperties/xades:SigningCertificate/xades:Cert/xades:IssuerSerial/ds:X509IssuerName"
    serial_number_xpath = "./ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/sig:UBLDocumentSignatures/sac:SignatureInformation/ds:Signature/ds:Object/xades:QualifyingProperties/xades:SignedProperties/xades:SignedSignatureProperties/xades:SigningCertificate/xades:Cert/xades:IssuerSerial/ds:X509SerialNumber"

    # Find elements using XPath expressions
    digest_value_elem = root.find(digest_value_xpath, ns_map)
    signing_time_elem = root.find(signing_time_xpath, ns_map)
    issuer_name_elem = root.find(issuer_name_xpath, ns_map)
    serial_number_elem = root.find(serial_number_xpath, ns_map)

    # Set text content of found elements
    digest_value_elem.text = data.get('certificate_hash', '')
    signing_time_elem.text = data.get('signing_time', '')
    issuer_name_elem.text = data.get('issuer_name', '')
    serial_number_elem.text = data.get('serial_number', '')

    return root

def hash_signed_properties_tag(data):
    dom = minidom.parse(frappe.get_app_path('ksa_zatca','fatoora/signed_property_tag.xml'))

    # Find elements corresponding to the fields to be filled
    signing_time_elem = dom.getElementsByTagName('xades:SigningTime')
    issuer_name_elem = dom.getElementsByTagName('ds:X509IssuerName')
    serial_number_elem = dom.getElementsByTagName('ds:X509SerialNumber')
    digest_value_elem = dom.getElementsByTagName('ds:DigestValue')

    # Fill in the tags with the provided data
    signing_time_elem[0].appendChild(dom.createTextNode(data.get('signing_time', '')))
    issuer_name_elem[0].appendChild(dom.createTextNode(data.get('issuer_name', '')))
    serial_number_elem[0].appendChild(dom.createTextNode(data.get('serial_number', '')))
    digest_value_elem[0].appendChild(dom.createTextNode(data.get('certificate_hash', '')))
    
    # Serialize the XML content
    xml_content = dom.childNodes[0].toprettyxml(indent="",newl="")

    # Hash the serialized XML content using SHA-256
    hashed_value = hashlib.sha256(xml_content.encode()).hexdigest()

    # Encode the hashed value using base64
    base64_encoded_hash = base64.b64encode(hashed_value.encode()).decode()

    data['signed_property_hash'] = base64_encoded_hash
    
    return data

def generate_qr_code(data):
    # TLV conversion for Seller's Name, VAT Number, Time Stamp, Invoice Amount, VAT Amount
    tlv_array = []

    # Seller's Name
    seller_name = data.get('seller_name', '')
    tag = bytes([1]).hex()
    length = bytes([len(seller_name.encode('utf-8'))]).hex()
    value = seller_name.encode('utf-8').hex()
    tlv_array.append(''.join([tag, length, value]))

    # VAT Number
    vat_number = data.get('seller_id', '')
    tag = bytes([2]).hex()
    length = bytes([len(vat_number.encode('utf-8'))]).hex()
    value = vat_number.encode('utf-8').hex()
    tlv_array.append(''.join([tag, length, value]))

    # Time Stamp
    date_obj = datetime.strptime(data.get('invoice_date', ''), '%Y-%m-%d')
    time_obj = datetime.strptime(data.get('invoice_time', ''), '%H:%M:%S').time()

    # Combine date and time into a single datetime object
    combined_datetime = datetime.combine(date_obj, time_obj)

    # Format the combined datetime as ISO 8601 with 'Z' at the end
    iso_timestamp = combined_datetime.strftime('%Y-%m-%dT%H:%M:%S')
    tag = bytes([3]).hex()
    length = bytes([len(iso_timestamp.encode('utf-8'))]).hex()
    value = iso_timestamp.encode('utf-8').hex()
    tlv_array.append(''.join([tag, length, value]))

    # Invoice Amount
    invoice_amount = data.get('tax_inclusive_amount', '')
    tag = bytes([4]).hex()
    length = bytes([len(invoice_amount.encode('utf-8'))]).hex()
    value = invoice_amount.encode('utf-8').hex()
    tlv_array.append(''.join([tag, length, value]))

    # VAT Amount
    vat_amount = data.get('total_tax_amount', '')
    tag = bytes([5]).hex()
    length = bytes([len(vat_amount.encode('utf-8'))]).hex()
    value = vat_amount.encode('utf-8').hex()
    tlv_array.append(''.join([tag, length, value]))

    # Hash of XML invoice
    invoice_hash = data.get('invoice_hash_encoded', '')
    tag = bytes([6]).hex()
    length = bytes([len(invoice_hash.encode('utf-8'))]).hex()
    value = invoice_hash.encode('utf-8').hex()
    tlv_array.append(''.join([tag, length, value]))

    # ECDSA signature
    ecdsa_signature = data.get('ecdsa_signature', '')
    tag = bytes([7]).hex()
    length = bytes([len(ecdsa_signature.encode('utf-8'))]).hex()
    value = ecdsa_signature.encode('utf-8').hex()
    tlv_array.append(''.join([tag, length, value]))

    # ECDSA Certificate public key
    ecdsa_public_key = data.get('cert_public_key', '')
    tag = bytes([8]).hex()
    length = bytes([len(base64.b64decode(ecdsa_public_key.encode('utf-8')))]).hex()
    value = base64.b64decode(ecdsa_public_key.encode('utf-8')).hex()
    tlv_array.append(''.join([tag, length, value]))
    
    # ECDSA Certificate Signature
    ecdsa_cert_signature = data.get('cert_signature', '')
    tag = bytes([9]).hex()
    length = bytes([len(bytes.fromhex(ecdsa_cert_signature))]).hex()
    value = bytes.fromhex(ecdsa_cert_signature).hex()
    tlv_array.append(''.join([tag, length, value]))

    # Joining bytes into one
    tlv_buff = ''.join(tlv_array)

    # base64 conversion for QR Code
    base64_string = b64encode(bytes.fromhex(tlv_buff)).decode()

     # Creating QR Code image
    data["ksa_einv_qr"] =  attach_qr_code(base64_string,data.get('invoice_name',''))

    data['qrcode'] = base64_string
    # data['qrcode-url'] = _file.file_url
    return data
    # Return the URL of the saved QR Code image file
    # return _file.file_url

def attach_qr_code(qrcode_base64,invoice_name,cleared=False):
    qr_image = io.BytesIO()
    url = qr_create(qrcode_base64, error='L')
    url.png(qr_image, scale=2, quiet_zone=1)

    # Saving QR Code image as a file
    if cleared:
        filename = f"CLEARED-QR-CODE-{invoice_name}.png".replace(os.path.sep, "__")
    else:
        filename = f"QR-CODE-{invoice_name}.png".replace(os.path.sep, "__")
    _file = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "content": qr_image.getvalue(),
        "is_private": 0,
        "attached_to_doctype": "Sales Invoice",
		"attached_to_name": invoice_name,
		"attached_to_field": "ksa_einv_qr"
    })
    _file.save()
    return _file.file_url

def final_invoice(root,data):
    invoice_hash = root.find("./ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/sig:UBLDocumentSignatures/sac:SignatureInformation/ds:Signature/ds:SignedInfo/ds:Reference[@Id='invoiceSignedData']/ds:DigestValue",ns_map)
    invoice_hash.text = data.get('invoice_hash_encoded','')
    invoice_signed_property_hash = root.find("./ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/sig:UBLDocumentSignatures/sac:SignatureInformation/ds:Signature/ds:SignedInfo/ds:Reference[@URI='#xadesSignedProperties']/ds:DigestValue",ns_map)
    invoice_signed_property_hash.text = data.get('signed_property_hash','')
    invoice_signature = root.find("./ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/sig:UBLDocumentSignatures/sac:SignatureInformation/ds:Signature/ds:SignatureValue",ns_map)
    invoice_signature.text = data.get('ecdsa_signature','')
    invoice_x509certificate = root.find("./ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/sig:UBLDocumentSignatures/sac:SignatureInformation/ds:Signature/ds:KeyInfo/ds:X509Data/ds:X509Certificate",ns_map)
    invoice_x509certificate.text = data.get('certificate','')
    invoice_qrcode = root.find('.//cac:AdditionalDocumentReference[cbc:ID="QR"]/cac:Attachment/cbc:EmbeddedDocumentBinaryObject',ns_map)
    invoice_qrcode.text = data.get('qrcode','')
    return root