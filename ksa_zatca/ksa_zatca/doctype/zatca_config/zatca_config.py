# Copyright (c) 2024, Ahmed Osama Ali and contributors
# For license information, please see license.txt

import frappe
import os
import subprocess
from frappe.model.document import Document
import requests
import base64

class ZatcaConfig(Document):
    @frappe.whitelist()
    def generate_keys(self):
        auto_name = _generate_auto_name(self)
        generate_and_store_keys(self, auto_name)
        generate_and_store_csr(self, auto_name)
        _delete_file(self,auto_name)
        self.save()

    @frappe.whitelist()
    def get_csid_credintial(self):
        auto_name = _generate_auto_name(self)
        get_csid(self,auto_name)
        _delete_file_csid(self,auto_name)
        self.save()
    
    @frappe.whitelist()
    def get_production_csid(self):
        auto_name = _generate_auto_name(self)
        get_prod_csid(self,auto_name)
        _delete_file_csid(self,auto_name)
        self.save()

    @frappe.whitelist()
    def enable_zatca_sdk(self):
        # export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin:/home/frappe/frappe-bench/apps/ksa_zatca/ksa_zatca/FATOORA_HOME/Apps/:/home/frappe/frappe-bench/apps/ksa_zatca/ksa_zatca/FATOORA_HOME/Apps/
        # export FATOORA_HOME=/home/frappe/frappe-bench/apps/ksa_zatca/ksa_zatca/FATOORA_HOME/Apps
        # export SDK_CONFIG=/home/frappe/frappe-bench/apps/ksa_zatca/ksa_zatca/FATOORA_HOME/Configuration/config.json
        # export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin:/home/frappe/frappe-bench/apps/ksa_zatca/ksa_zatca/FATOORA_HOME/Apps/:/home/frappe/frappe-bench/apps/ksa_zatca/ksa_zatca/FATOORA_HOME/Apps/
        # export FATOORA_HOME=/home/frappe/frappe-bench/apps/ksa_zatca/ksa_zatca/FATOORA_HOME/Apps
        # export SDK_CONFIG=/home/frappe/frappe-bench/apps/ksa_zatca/ksa_zatca/FATOORA_HOME/Configuration/config.json

        output = subprocess.run(["fatoora", "-help"], capture_output=True, text=True)
        frappe.msgprint(str(output.stdout))
    
    @frappe.whitelist()
    def reset_zatca_config(self):
        _delete_file_doc(self)
        self.requestid, self.csid_key, self.csid_key_des= '','',''
        self.certificate,self.certificate_des = '',''
        self.secret,self.secret_des = '',''
        self.private_key,self.private_key_des = '',''
        self.public_key,self.public_key_des = '',''
        self.csr_key,self.csr_config = '',''
        self.csr_key_des,self.csrconfig_des = '',''
        self.icv = 1
        self.pih = 'NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ=='
        self.comp_csid = 0
        self.prod_csid = 0
        self.save()
        self.reload()
        return 'Document Reseted Successfully!'
        


def _execute_in_shell(cmd, verbose=False, low_priority=False, check_exit_code=False):
                # using Popen instead of os.system - as recommended by python docs
                import shlex
                import tempfile
                from subprocess import Popen
                env_variables = {"MY_VARIABLE": "some_value", "ANOTHER_VARIABLE": "another_value"}
                if isinstance(cmd, list):
                    # ensure it's properly escaped; only a single string argument executes via shell
                    cmd = shlex.join(cmd)
                    # process = subprocess.Popen(command_sign_invoice, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env_variables)               
                with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                    kwargs = {"shell": True, "stdout": stdout, "stderr": stderr}
                    if low_priority:
                        kwargs["preexec_fn"] = lambda: os.nice(10)
                    p = Popen(cmd, **kwargs)
                    exit_code = p.wait()
                    stdout.seek(0)
                    out = stdout.read()
                    stderr.seek(0)
                    err = stderr.read()
                failed = check_exit_code and exit_code

                if verbose or failed:
                    if err:
                        frappe.msgprint(err)
                    if out:
                        frappe.msgprint(out)
                if failed:
                    raise Exception("Command failed")
                return err, out



def get_csid(self,auto_name):
    name = frappe.db.get_value("File", {"file_url": self.csr_key},"name")
    csr_contents = frappe.get_doc("File", name).get_content()
    csr = base64.b64encode(csr_contents.encode("utf-8")).decode("utf-8")
    headers = {
        'accept': 'application/json',
        'OTP': str(self.otp),
        'Accept-Version': 'V2',
        'Content-Type': 'application/json',
    }
    json_data = {
        'csr': '000',
    }
    json_data['csr'] = csr
    response = requests.post(
        f'{get_base_url(self)}/compliance',
        headers=headers,
        json=json_data,
    )
    if response.status_code == 200:
        csid = response.json()
        binarySecurityToken = response.json()['binarySecurityToken']
        decoded_token = base64.b64decode(binarySecurityToken).decode('utf-8')
        secret = response.json()['secret']

        self.requestid = response.json()['requestID']
        
        self.csid_key,self.csid_key_des= _store_file(self,f'{auto_name}_csid.txt',binarySecurityToken)
        
        self.certificate,self.certificate_des = _store_file(self,f'{auto_name}_certificate.txt',decoded_token)

        self.secret,self.secret_des= _store_file(self,f'{auto_name}_secret.txt',secret)
        self.comp_csid = 1
    else:
        # frappe.throw(f"Error: received {response.status_code} status code with message {response.json()['dispositionMessage']}")
        frappe.throw(f"Error: received {response.status_code} status code with message {response.text}")

def get_prod_csid(self,auto_name):
    frappe.errprint(self.csid_key_des)
    frappe.errprint(self.secret_des)
    auth = base64.b64encode(f"{self.csid_key_des}:{self.secret_des}".encode()).decode('utf-8')
    frappe.errprint(auth)
    headers = {
        'Accept': 'application/json',
        'Accept-Version': 'V2',
        'Accept-Language': 'en',
        'Content-Type': 'application/json',
        'Authorization': f'Basic {auth}'
    }
    json_data = {
        'compliance_request_id': '000',
    }
    json_data['compliance_request_id'] = self.requestid
    response = requests.post(
        f'{get_base_url(self)}/production/csids',
        headers=headers,
        json=json_data,
    )
    if response.status_code == 200:
        csid = response.json()
        binarySecurityToken = response.json()['binarySecurityToken']
        decoded_token = base64.b64decode(binarySecurityToken).decode('utf-8')
        secret = response.json()['secret']

        self.requestid = response.json()['requestID']
        
        _delete_compliance_files(self,auto_name)
        
        self.csid_key,self.csid_key_des= _store_file(self,f'{auto_name}_csid.txt',binarySecurityToken)
        
        self.certificate,self.certificate_des = _store_file(self,f'{auto_name}_certificate.txt',decoded_token)

        self.secret,self.secret_des= _store_file(self,f'{auto_name}_secret.txt',secret)
        self.prod_csid = 1
    else:
        # frappe.throw(f"Error: received {response.status_code} status code with message {response.json()['dispositionMessage']}")
        frappe.throw(f"Error: received {response.status_code} status code with message {response.text}")


def _delete_file_doc(self):
    file_urls = [self.private_key, self.public_key, self.csr_config, self.csr_key, self.csid_key, self.certificate, self.secret]
    for file_url in file_urls:
        file_doc = frappe.get_all("File", filters={"attached_to_doctype": "ZATCA Config", "file_url": file_url}, limit=1)
        if file_doc:
            frappe.delete_doc("File", file_doc[0].name)
    frappe.db.commit()

def _delete_compliance_files(self,auto_name):
    file_urls = [self.csid_key, self.certificate, self.secret]
    for file_url in file_urls:
        file_doc = frappe.get_all("File", filters={"attached_to_doctype": "ZATCA Config", "file_url": file_url}, limit=1)
        if file_doc:
            frappe.delete_doc("File", file_doc[0].name)
    frappe.db.commit()

def generate_and_store_keys(self, auto_name):
    # Generate private key
    # subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-out", f"{auto_name}_private_key.pem", "-pkeyopt", "rsa_keygen_bits:2048"])
    # Generate ec private key
    subprocess.run(["openssl", "ecparam", "-name", "secp256k1", "-genkey", "-noout", "-out", f"{auto_name}_private_key.pem"])
    self.private_key,self.private_key_des = _store_file(self, f"{auto_name}_private_key.pem")
    # Generate public key
    # subprocess.run(["openssl", "rsa", "-pubout", "-in", f"{auto_name}_private_key.pem", "-out", f"{auto_name}_public_key.pem"])
    # Generate ec public key
    subprocess.run(["openssl", "ec", "-in", f"{auto_name}_private_key.pem", "-pubout", "-out", f"{auto_name}_public_key.pem"])
    self.public_key,self.public_key_des = _store_file(self, f"{auto_name}_public_key.pem")
    
def generate_and_store_csr(self, auto_name):
    # create CSR config file for zaTCA CSR
    create_csr_config(self, auto_name)
    self.csr_config,self.csrconfig_des = _store_file(self, f"{auto_name}_csr.cnf")
    # Generate CSR using the config file
    subprocess.run(["openssl", "req", "-new", "-sha256", "-key", f"{auto_name}_private_key.pem", "-extensions", "v3_req","-config",f"{auto_name}_csr.cnf", "-out",f"{auto_name}_csr.csr"])
    self.csr_key,self.csr_key_des = _store_file(self, f"{auto_name}_csr.csr")

def _generate_auto_name(self):
        return self.company.replace(" ", "_").lower() + "_" + frappe.utils.nowdate().replace("-", "")

def create_csr_config(self, auto_name):
    # Template Name for sandbox : TESTZATCA-Signing-Code
    # Template Name for simulation : PREZATCA-Signing-Code
    # Template Name for production : ZATCA-Signing-Code
    with open(f"{auto_name}_csr.cnf", "w") as file:
            file.write(f"""oid_section= OIDS
                        [ OIDS ]
                        certificateTemplateName= 1.3.6.1.4.1.311.20.2
                        [req]
                        default_bits=2048
                        emailAddress={self.email}
                        req_extensions=v3_req
                        x509_extensions=v3_Ca
                        prompt=no
                        default_md=sha256
                        req_extensions=req_ext
                        distinguished_name=req_distinguished_name

                        [req_distinguished_name]
                        C={self.country_name}
                        OU={self.company}
                        O=Zatca
                        CN=127.0.0.1

                        [v3_req]
                        basicConstraints = CA:FALSE
                        keyUsage = nonRepudiation, digitalSignature, keyEncipherment


                        [req_ext]
                        certificateTemplateName = ASN1:PRINTABLESTRING:{self.certificate_template_name}
                        subjectAltName = dirName:alt_names

                        [alt_names]
                        SN={self.egs_serial_number}
                        UID={self.organization_identifier}
                        title={self.invoice_type}
                        registeredAddress={self.location}
                        businessCategory={self.industry}
                          """.replace("\t", ""))
            file.close()

def _store_file(self, file_name, content=None):
    if content:
        file_doc = frappe.new_doc("File")
        file_doc.file_name = file_name
        file_doc.content = content
        file_doc.ref_doctype = "ZATCA Config"
        file_doc.ref_docname = self.name
        file_doc.is_private = 1
        file_doc.save()
        return file_doc.file_url,file_doc.content
    else:
        with open(file_name, "r") as file:
            content = file.read()
            file_doc = frappe.new_doc("File")
            file_doc.file_name = file_name
            file_doc.content = content
            file_doc.ref_doctype = "ZATCA Config"
            file_doc.ref_docname = self.name
            file_doc.is_private = 1
            file_doc.save()
            return file_doc.file_url,file_doc.content
        
def _delete_file(self,auto_name):
    subprocess.run(["rm", f"{auto_name}_private_key.pem"])
    subprocess.run(["rm", f"{auto_name}_public_key.pem"])
    subprocess.run(["rm", f"{auto_name}_csr.cnf"])
    subprocess.run(["rm", f"{auto_name}_csr.csr"])

def _delete_file_csid(self,auto_name):
    subprocess.run(["rm", f"{auto_name}_csid.txt"])
    subprocess.run(["rm", f"{auto_name}certificate.txt"])
    subprocess.run(["rm", f"{auto_name}_secret.txt"])
    
def get_base_url(self):
    if self.environment == 'Simulation':
        return self.simulation_url
    elif self.environment == 'Production':
        return self.production_url
    elif self.environment == 'Sandbox':
        return self.sandbox_url
        