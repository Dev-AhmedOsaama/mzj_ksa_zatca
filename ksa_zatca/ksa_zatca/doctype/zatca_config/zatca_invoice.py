import frappe
import os
from xml.etree import ElementTree as ET
# import all the functions from the zatca_xml.py file
from ksa_zatca.ksa_zatca.doctype.zatca_config.zatca_xml import create_xml,salesinvoice_data,invoice_Typecode_Compliance,invoice_Typecode_Simplified,invoice_Typecode_Standard,doc_Reference,additional_Reference,company_Data,customer_Data,delivery_And_PaymentMeans,tax_Data,item_data,xml_structuring
from ksa_zatca.ksa_zatca.doctype.zatca_config.zatca_xml_creation import read_xml_file,fill_basic_data,fill_taxes_data,fill_supplier_customer_data,fill_totals_data,fill_items_data,fill_signed_properties_tag,hash_invoice,sign_invoice_hash,generate_certificate_hash,hash_signed_properties_tag,generate_qr_code,final_invoice,fill_allowance_charge,attach_qr_code
from ksa_zatca.ksa_zatca.doctype.zatca_config.zatca_config import get_base_url
import re
from datetime import datetime
from lxml import etree
import subprocess
import copy
import base64
import uuid
import requests

    
@frappe.whitelist()
def zatca_Call(invoice_number='ACC-SINV-2024-00017'):
    if not frappe.db.exists("Sales Invoice", invoice_number):
        frappe.throw("Invoice Number is NOT Valid:  " + str(invoice_number))
    
    dummy_data = generate_data_dict(invoice_number)
    
    if dummy_data['request_status'] == 3:
        frappe.throw("Please Do The Compliance First.")
    
    # Initialize root with standard invoice structure
    root = read_xml_file(dummy_data)
    
    # Fill in data
    root = fill_basic_data(root,dummy_data)
    root = fill_supplier_customer_data(root,dummy_data)
    if float(dummy_data.get('allowance_total_amount')) > 0 :
        root = fill_allowance_charge(root,dummy_data)
    root = fill_taxes_data(root,dummy_data)
    root = fill_totals_data(root,dummy_data)
    root = fill_items_data(root,dummy_data)
    dummy_data = hash_invoice(copy.deepcopy(root),dummy_data)
    dummy_data = sign_invoice_hash(dummy_data)
    dummy_data = generate_certificate_hash(dummy_data)
    root = fill_signed_properties_tag(root,dummy_data)
    dummy_data = hash_signed_properties_tag(dummy_data)
    dummy_data = generate_qr_code(dummy_data)
    root = final_invoice(root,dummy_data)
    
    invoice_encoded = base64.b64encode(etree.tostring(root,encoding='utf-8'))
    dummy_data['invoice_encoded'] = invoice_encoded
    
    zatca_request(dummy_data)
        
    # Generate xml name
    xml_name = generate_xml_name(dummy_data)
    
    # Write root to XML file
    root.getroottree().write(xml_name, encoding='utf-8')
    _store_xml_file(dummy_data.get("invoice_name",""),xml_name)
    _delete_xml_file(xml_name)
    

def generate_data_dict(doc_name):
    # Get Required Docs
    sales_invoice = frappe.get_doc("Sales Invoice", doc_name)
    company = frappe.get_doc("Company", sales_invoice.get('company'))
    customer = frappe.get_doc("Customer", sales_invoice.get('customer'))
    zatca_config = frappe.get_doc("Zatca Config", company.get('name'))
    
    company_address = None
    customer_address = None
    if sales_invoice.get('company_address'):
        company_address = frappe.get_doc("Address", sales_invoice.get('company_address'))
    else:
        frappe.throw("Please Provide Company Address.")
    if sales_invoice.get('customer_address'):
        customer_address = frappe.get_doc("Address", sales_invoice.get('customer_address'))
    
    data = {}
    # Invoice Type
    if sales_invoice.get('is_return') == 1:
        data['invoice_type_code'] = '381'
    elif sales_invoice.get('is_debit_note') == 1:
        data['invoice_type_code'] = '383'
    else :
        data['invoice_type_code'] = '388'
    if customer.get('customer_type') == 'Individual':
        data['invoice_type'] = '0200000'
    else :
        data['invoice_type'] = '0100000'
    
    # Sales Invoice Data
    data['invoice_name'] = doc_name
    data['invoice_date'] = str(sales_invoice.get('posting_date'))
    posting_time = sales_invoice.get('posting_time')
    total_seconds = posting_time.total_seconds()

    # Convert total seconds to hours, minutes, and seconds
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    # Format the time string
    time_str = f"{hours:02d}:{minutes:02d}:{seconds:09.6f}"
    # Parse the formatted time string
    time_obj = datetime.strptime(time_str, "%H:%M:%S.%f")
    # Convert the time object to the desired format
    data['invoice_time'] = time_obj.strftime("%H:%M:%S")
    
    data['uuid'] = str(uuid.uuid4())
    data['invoice_currency'] = sales_invoice.get('currency')
    
    if company.get('default_currency') in [None,''] and data['invoice_type'] == '0100000':
        frappe.throw("Please Enter Company Default Currency")
    else:
        data['tax_currency'] = company.get('default_currency')
        
    data['billing_ref'] = sales_invoice.get('return_against','')
    data['return_reason'] = sales_invoice.get('custom_return_reason','')
    data['discount_amount'] = sales_invoice.get('discount_amount','0')
    # Items
    data['items'] = []
    for item in sales_invoice.get('items'):
        d = {}
        d['id'] = str(item.get('idx'))
        d['quantity'] = str(abs(item.get('qty')))
        d['line_extension_amount'] = str(abs(item.get('amount')))
        d['tax_amount'] = str(round(abs(item.get('tax_amount') ),2))
        # d['rounding_amount'] = str(abs(item.get('total_amount')) )
        d['rounding_amount'] = str(round(abs(item.get('amount')) + abs(item.get('tax_amount')),2))
        d['name'] = item.get('item_name')
        d['tax_category_id'] = item.get('custom_item_tax_category')
        d['tax_percent'] = str(item.get('tax_rate') )
        d['tax_scheme_id'] = 'VAT'
        d['price_amount'] = str(item.get('rate'))
        d['allowance_charge_reason'] = 'discount'
        d['allowance_charge_amount'] = str(item.get('discount_amount'))
        data['items'].append(d)
    # Taxes
    data['tax_subtotal'] = get_taxes(sales_invoice)
    data['base_total_tax_amount'] = str(abs(sales_invoice.get('base_total_taxes_and_charges')))
    data['total_tax_amount'] = str(abs(sales_invoice.get('total_taxes_and_charges')))
    # Totals
    data['line_extension_amount'] = str(abs(sales_invoice.get('total')))
    data['tax_exclusive_amount'] = str(abs(sales_invoice.get('net_total')))
    data['tax_inclusive_amount'] = str(abs(sales_invoice.get('grand_total')))
    data['allowance_total_amount'] = str(abs(sales_invoice.get('discount_amount'))) or '0'
    data['prepaid_amount'] = str(abs(sales_invoice.get('paid_amount')))
    data['payable_amount'] = str(abs(sales_invoice.get('outstanding_amount')))
    
    
    # Customer Data
    data['customer_name'] = customer.get('name')
    if customer.get('tax_id') in [None,''] and data['invoice_type'] == '0100000':
        frappe.throw("Please Enter Customer Tax ID")
    else:
        data['customer_id'] = customer.get('tax_id')
    if customer.get('custom_commercial_register') in [None,''] and data['invoice_type'] == '0100000':
        frappe.throw("Please Enter Customer Commercial Register")
    else:
        data['customer_cr'] = customer.get('custom_commercial_register')
    if customer_address not in [None,'']:
        
        data['customer_c'] = frappe.get_doc("Country",customer_address.get('country')).code.upper()
        data['customer_city'] = customer_address.get('city')
        if customer_address.get('custom_district') in [None,''] and data['invoice_type'] == '0100000':
            frappe.throw("Please Enter Customer District")
        else:
            data['customer_d'] = customer_address.get('custom_district')
        if customer_address.get('custom_street_name') in [None,''] and data['invoice_type'] == '0100000':
            frappe.throw("Please Enter Customer Street Name")
        else:
            data['customer_st'] = customer_address.get('custom_street_name')
        if customer_address.get('custom_building_number') in [None,''] and data['invoice_type'] == '0100000':
            frappe.throw("Please Enter Customer Building Number")
        else:
            data['customer_bn'] = customer_address.get('custom_building_number')
        if customer_address.get('pincode') in [None,''] and data['invoice_type'] == '0100000':
            frappe.throw("Please Enter Customer Postal Code")
        else:
            data['customer_pz'] = customer_address.get('pincode')
    
    # Company Data
    data['seller_name'] = company.get('name')
    if company.get('tax_id') in [None,''] and data['invoice_type'] == '0100000':
        frappe.throw("Please Enter Company Tax ID")
    else:
        data['seller_id'] = company.get('tax_id')
    if company.get('custom_commercial_register') in [None,''] and data['invoice_type'] == '0100000':
        frappe.throw("Please Enter Company Commercial Register")
    else:
        data['seller_cr'] = company.get('custom_commercial_register')
    if company_address not in [None,'']:
        data['seller_c'] = frappe.get_doc("Country",company_address.get('country')).code.upper()
        data['seller_city'] = company_address.get('city')
        if company_address.get('custom_district') in [None,''] and data['invoice_type'] == '0100000':
            frappe.throw("Please Enter Company District")
        else:
            data['seller_d'] = company_address.get('custom_district')
        if company_address.get('custom_street_name') in [None,''] and data['invoice_type'] == '0100000':
            frappe.throw("Please Enter Company Street Name")
        else:
            data['seller_st'] = company_address.get('custom_street_name')
        if company_address.get('custom_building_number') in [None,''] and data['invoice_type'] == '0100000':
            frappe.throw("Please Enter Company Building Number")
        else:
            data['seller_bn'] = company_address.get('custom_building_number')
        if company_address.get('pincode') in [None,''] and data['invoice_type'] == '0100000':
            frappe.throw("Please Enter Company Postal Code")
        else:
            data['seller_pz'] = company_address.get('pincode')
    
    # Zatca Config Data
    data['icv'] = str(zatca_config.get('icv'))
    data['pih'] = zatca_config.get('pih')
    data['private_key'] = zatca_config.get('private_key_des')
    data['certificate'] = zatca_config.get('certificate_des')
    data['token'] = zatca_config.get('csid_key_des')

    data['secret'] = zatca_config.get('secret_des')
    data['url'] = get_base_url(zatca_config)
    if zatca_config.get('prod_csid',0) == 1 :
        data['request_status'] = 1
        if data['invoice_type'] == '0100000':
            data['request_type'] = 1
        else:
            data['request_type'] = 2
    elif zatca_config.get('comp_csid',0) == 1:
        data['request_status'] = 2
        if data['invoice_type'] == '0100000':
            data['request_type'] = 1
        else:
            data['request_type'] = 2
    else:
        data['request_status'] = 3

    return data

def get_taxes(invoice):
    taxes_list = []
    
    for item in invoice.get('items'):
        tax_template = item.get('item_tax_template', '')
        tax_rate = float(item.get('tax_rate', 0))
        taxable_amount = float(item.get('net_amount', 0))
        discount = float(item.get('amount') - item.get('net_amount'))
        tax_amount = float(item.get('tax_amount', 0))
        tax_category_id = item.get('custom_item_tax_category', '')
        tax_exemption_reason_code = item.get('custom_tax_exemption_reason','')
        if tax_category_id == 'O':
            tax_exemption_reason_text = item.get('custom_out_of_scope_exemption_reason','')
        else:
            tax_exemption_reason_text = item.get('custom_tax_exemption_reason_text','')

        # Check if tax_template already exists in the taxes_list
        tax_found = False
        for tax_dict in taxes_list:
            if tax_dict['tax_template'] == tax_template:
                tax_dict['taxable_amount'] += taxable_amount
                tax_dict['tax_amount'] += tax_amount
                tax_dict['discount'] += discount
                tax_found = True
                break

        if not tax_found:
            tax_dict = {
                'tax_template': tax_template,
                'taxable_amount': abs(taxable_amount),
                'tax_rate': tax_rate,
                'tax_category_id': tax_category_id,
                'tax_amount': abs(tax_amount),
                'tax_exemption_reason_code':tax_exemption_reason_code,
                'tax_exemption_reason_text':tax_exemption_reason_text,
                'discount':discount
                }
            taxes_list.append(tax_dict)
    return taxes_list

def generate_xml_name(dummy_data):
    # Extract data from the dummy_data dictionary
    seller_vat_number = dummy_data.get("seller_id", "")
    invoice_issue_date = dummy_data.get("invoice_date", "")
    invoice_issue_time = dummy_data.get("invoice_time", "")
    invoice_number = dummy_data.get("invoice_name", "")

    # Remove non-alphanumeric characters from the invoice number and replace them with a dash "-"
    clean_invoice_number = re.sub(r'\W+', '-', invoice_number)

    # Format invoice issue date and time
    formatted_issue_date = invoice_issue_date.replace("-", "")
    formatted_issue_time = invoice_issue_time.replace(":", "")

    # Construct the invoice name
    xml_name = f"{seller_vat_number}_{formatted_issue_date}T{formatted_issue_time}_{clean_invoice_number}.xml"

    return xml_name

def _store_xml_file(invoice_name,file_name, content=None):
    if content:
        file_doc = frappe.new_doc("File")
        file_doc.file_name = file_name
        file_doc.content = content
        file_doc.attached_to_doctype = "Sales Invoice"
        file_doc.attached_to_name = invoice_name
        file_doc.is_private = 1
        file_doc.save()
        # return file_doc.file_url,file_doc.content
    else:
        with open(file_name, "r") as file:
            content = file.read()
            file_doc = frappe.new_doc("File")
            file_doc.file_name = file_name
            file_doc.content = content
            file_doc.attached_to_doctype = "Sales Invoice"
            file_doc.attached_to_name = invoice_name
            file_doc.is_private = 1
            file_doc.save()
            # return file_doc.file_url,file_doc.content

def _delete_xml_file(xml_name):
    subprocess.run(["rm", xml_name])

def zatca_request(data):
    auth = base64.b64encode(f"{data.get('token')}:{data.get('secret')}".encode()).decode()
    if data['request_status'] == 2:
        url = f"{data.get('url')}/compliance/invoices"
    elif data['request_status'] == 1:
        if data['request_type'] == 2:
            url = f"{data.get('url')}/invoices/reporting/single"
        else:
            url = f"{data.get('url')}/invoices/clearance/single"
            
    headers = {
        'Accept': 'application/json',
        'Accept-Version': 'V2',
        'Accept-Language': 'en',
        'Content-Type': 'application/json',
        'Authorization': f'Basic {auth}'
    }
    body = {
        'invoiceHash' : data.get('invoice_hash_encoded'),
        'uuid' : data.get('uuid'),
        'invoice' : data.get('invoice_encoded').decode()
    }

    try:
        response = requests.post(
            url=url,
            headers=headers,
            json=body
        )
        if response.status_code in [200,202,400]:
            zatca_config = frappe.get_doc('Zatca Config', data.get('seller_name'))
            zatca_config.icv += 1
            zatca_config.pih = data.get('invoice_hash_encoded')
            zatca_config.save()
            
            if response.status_code in [200,202]:
                sales_invoice = frappe.get_doc('Sales Invoice',data.get('invoice_name'))
                sales_invoice.ksa_einv_qr = data.get('ksa_einv_qr')
                sales_invoice.custom_cleared = 1
                frappe.errprint(data['request_type'])
                frappe.errprint(data['request_status'])
                if data['request_status'] == 1:
                    if data['request_type'] == 1:
                        sales_invoice.custom_clearance_status = "Cleared"
                    elif data['request_type'] == 2:
                        sales_invoice.custom_clearance_status = "Reported"
                else:
                    if data['request_type'] == 1:
                        sales_invoice.custom_clearance_status = "compliance cleared"
                    elif data['request_type'] == 2:
                        sales_invoice.custom_clearance_status = "compliance reported"
                sales_invoice.save()
            
            frappe.errprint(response.text)
            if data['request_type'] == 1:
                frappe.msgprint(("Clearance Status: {0}").format(response.json().get('clearanceStatus')))
                if response.json().get('clearedInvoice'):
                    invoice = base64.b64decode(response.json().get('clearedInvoice'))
                    root = etree.fromstring(invoice)
                    qr_code_tag = root.find('.//cac:AdditionalDocumentReference[cbc:ID="QR"]/cac:Attachment/cbc:EmbeddedDocumentBinaryObject',{"cbc":"urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2","cac":"urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"})
                    base64_qrcode = qr_code_tag.text
                    # Generate xml name
                    xml_name = "CLEARED_" + data.get('invoice_name') + '.xml'
                    
                    # Write root to XML file
                    root.getroottree().write(xml_name, encoding='utf-8')
                    _store_xml_file(data.get("invoice_name",""),xml_name,invoice)
                    _delete_xml_file(xml_name+'.xml')
                    
                    # Create Qrcode for Cleared Invoice
                    qu_url = attach_qr_code(base64_qrcode,data.get('invoice_name'),True)
                    sales_invoice.ksa_einv_qr = qu_url
                    sales_invoice.save()
                    
            elif data['request_type'] == 2:
                frappe.msgprint(("Reporting Status: {0}").format(response.json().get('reportingStatus')))
                    
            else:
                frappe.msgprint(("Validation Status: {0}").format(response.json()))
            
            if response.json().get('warningMessages'):
                frappe.msgprint("You Have A Few Warnings")
                for message in response.json().get('warningMessages'):
                    frappe.msgprint(str(message))
            if response.json().get('errorMessages'):
                frappe.msgprint("You Have A Few Errors")
                for message in response.json().get('errorMessages'):
                    frappe.msgprint(str(message))
        
        else:
            frappe.errprint(response.status_code)
            frappe.errprint(response.text)
            frappe.msgprint(str(response.status_code))
            frappe.msgprint(str(response.text))
    except requests.exceptions.ConnectionError:
        frappe.throw(('Connection Error Please Try Again After Some Time.'))
    except Exception as e:
        frappe.throw('Exception Occurred: {0}'.format(e))
        frappe.errprint(e)

#{'invoice_name': 'ACC-SINV-2024-00007-1', 'invoice_date': datetime.date(2024, 3, 8), 'invoice_time': datetime.timedelta(seconds=3420), 'invoice_currency': 'SAR', 'tax_currency': None, 'items': [{'id': 1, 'quantity': 2.0, 'line_extension_amount': 1600.0, 'tax_amount': 240.0, 'rounding_amount': 1840.0, 'name': 'T-shirt', 'tax_category_id': 'S', 'tax_percent': 15.0, 'tax_scheme_id': 'VAT', 'price_amount': 800.0, 'allowance_charge_reason': 'discount', 'allowance_charge_amount': 0.0}, {'id': 2, 'quantity': 1.0, 'line_extension_amount': 800.0, 'tax_amount': 120.0, 'rounding_amount': 920.0, 'name': 'Laptop', 'tax_category_id': 'S', 'tax_percent': 15.0, 'tax_scheme_id': 'VAT', 'price_amount': 800.0, 'allowance_charge_reason': 'discount', 'allowance_charge_amount': 0.0}, {'id': 3, 'quantity': 1.0, 'line_extension_amount': 500.0, 'tax_amount': 0.0, 'rounding_amount': 500.0, 'name': 'Book', 'tax_category_id': 'Z', 'tax_percent': 0.0, 'tax_scheme_id': 'VAT', 'price_amount': 500.0, 'allowance_charge_reason': 'discount', 'allowance_charge_amount': 0.0}, {'id': 4, 'quantity': 1.0, 'line_extension_amount': 100.0, 'tax_amount': 0.0, 'rounding_amount': 100.0, 'name': 'Sneakers', 'tax_category_id': 'E', 'tax_percent': 0.0, 'tax_scheme_id': 'VAT', 'price_amount': 100.0, 'allowance_charge_reason': 'discount', 'allowance_charge_amount': 0.0}], 'taxes': [{'15 - TSD': {'taxable_amount': 2400.0, 'tax_rate': 15.0, 'tax_category_id': 'S', 'tax_amount': 360.0}, 'Zero - TSD': {'taxable_amount': 500.0, 'tax_rate': 0.0, 'tax_category_id': 'Z', 'tax_amount': 0.0}, 'Exempted - TSD': {'taxable_amount': 100.0, 'tax_rate': 0.0, 'tax_category_id': 'E', 'tax_amount': 0.0}}], 'invoice_type_code': '388', 'invoice_type': '0100000', 'customer_name': 'Grant Plastics Ltd.', 'customer_id': None, 'customer_cr': None, 'customer_c': None, 'customer_city': 'الدمام', 'customer_d': None, 'customer_st': None, 'customer_bn': None, 'customer_pz': None, 'seller_name': 'Trigger Solutions (Demo)', 'seller_id': '300000000000003', 'seller_cr': None, 'seller_c': 'Saudi Arabia', 'seller_city': 'الرياض', 'seller_d': None, 'seller_st': None, 'seller_bn': None, 'seller_pz': None, 'icv': 1, 'pih': 'NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ==', 'private_key': '-----BEGIN EC PRIVATE KEY-----\nMHQCAQEEII8Q6n68KYSQNPtHvC+JYfyROiynn1DvctQAk7CBzAR8oAcGBSuBBAAK\noUQDQgAEWCfGiBQwiNfwXcJcO0oXMBb7VpARe5L61g/c80GT2IP0UaC2JgrlOFuo\nTTFNK67kETVq4M5suNWe2tLSsRLRBg==\n-----END EC PRIVATE KEY-----\n', 'certificate': 'MIICJTCCAcugAwIBAgIGAY4Zk6g8MAoGCCqGSM49BAMCMBUxEzARBgNVBAMMCmVJbnZvaWNpbmcwHhcNMjQwMzA3MTU0MTI2WhcNMjkwMzA2MjEwMDAwWjBUMQswCQYDVQQGEwJTQTEhMB8GA1UECwwYVHJpZ2dlciBTb2x1dGlvbnMgKERlbW8pMQ4wDAYDVQQKDAVaYXRjYTESMBAGA1UEAwwJMTI3LjAuMC4xMFYwEAYHKoZIzj0CAQYFK4EEAAoDQgAEWCfGiBQwiNfwXcJcO0oXMBb7VpARe5L61g/c80GT2IP0UaC2JgrlOFuoTTFNK67kETVq4M5suNWe2tLSsRLRBqOByjCBxzAMBgNVHRMBAf8EAjAAMIG2BgNVHREEga4wgaukgagwgaUxJDAiBgNVBAQMGzEtVFNUfDItVFNUfDMtZWQyMmYxZDgtZTZhMjEfMB0GCgmSJomT8ixkAQEMDzM5OTk5OTk5OTkwMDAwMzENMAsGA1UEDAwEMTEwMDERMA8GA1UEGgwIUlJSRDI5MjkxOjA4BgNVBA8MMcOYwqPDmcKGw5jCtMOYwrfDmMKpIMOYwqrDmcKIw5jCscOZworDmMKvw5jCp8OYwqowCgYIKoZIzj0EAwIDSAAwRQIhAK5La7GtqeSukilZr5mQprJ8/fA/uFj/9I9EMDKTlX6ZAiBJaZILCoZUsQvVqiWvf3V8ro5eNjW1PYWXYTCDi/SV5g==', 'token': 'TUlJQ0pUQ0NBY3VnQXdJQkFnSUdBWTRaazZnOE1Bb0dDQ3FHU000OUJBTUNNQlV4RXpBUkJnTlZCQU1NQ21WSmJuWnZhV05wYm1jd0hoY05NalF3TXpBM01UVTBNVEkyV2hjTk1qa3dNekEyTWpFd01EQXdXakJVTVFzd0NRWURWUVFHRXdKVFFURWhNQjhHQTFVRUN3d1lWSEpwWjJkbGNpQlRiMngxZEdsdmJuTWdLRVJsYlc4cE1RNHdEQVlEVlFRS0RBVmFZWFJqWVRFU01CQUdBMVVFQXd3Sk1USTNMakF1TUM0eE1GWXdFQVlIS29aSXpqMENBUVlGSzRFRUFBb0RRZ0FFV0NmR2lCUXdpTmZ3WGNKY08wb1hNQmI3VnBBUmU1TDYxZy9jODBHVDJJUDBVYUMySmdybE9GdW9UVEZOSzY3a0VUVnE0TTVzdU5XZTJ0TFNzUkxSQnFPQnlqQ0J4ekFNQmdOVkhSTUJBZjhFQWpBQU1JRzJCZ05WSFJFRWdhNHdnYXVrZ2Fnd2dhVXhKREFpQmdOVkJBUU1HekV0VkZOVWZESXRWRk5VZkRNdFpXUXlNbVl4WkRndFpUWmhNakVmTUIwR0NnbVNKb21UOGl4a0FRRU1Eek01T1RrNU9UazVPVGt3TURBd016RU5NQXNHQTFVRURBd0VNVEV3TURFUk1BOEdBMVVFR2d3SVVsSlNSREk1TWpreE9qQTRCZ05WQkE4TU1jT1l3cVBEbWNLR3c1akN0TU9Zd3JmRG1NS3BJTU9Zd3FyRG1jS0l3NWpDc2NPWndvckRtTUt2dzVqQ3A4T1l3cW93Q2dZSUtvWkl6ajBFQXdJRFNBQXdSUUloQUs1TGE3R3RxZVN1a2lsWnI1bVFwcko4L2ZBL3VGai85STlFTURLVGxYNlpBaUJKYVpJTENvWlVzUXZWcWlXdmYzVjhybzVlTmpXMVBZV1hZVENEaS9TVjVnPT0=', 'secret': 'CWddDCq4BvRC6rsPwp1VFoBM6Y+ipNZkkXiDQY+GpMM=', 'url': 'https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal/'}