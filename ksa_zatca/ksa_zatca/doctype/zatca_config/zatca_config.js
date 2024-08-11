// Copyright (c) 2024, Ahmed Osama Ali and contributors
// For license information, please see license.txt

frappe.ui.form.on('Zatca Config', {
    refresh: function(frm) {
        if (frm.doc.comp_csid == 0 && frm.doc.prod_csid == 0) {
            frm.add_custom_button('Generate Keys', function() {
                frm.call('generate_keys').then(r => {
                   if (r.message) {
                       frappe.msgprint(r.message);
                   }
                   frm.reload_doc();
               });
            });
            frm.add_custom_button('GET CSID', function() {
                frm.call('get_csid_credintial').then(r => {
                   if (r.message) {
                       frappe.msgprint(r.message);
                   }
                   frm.reload_doc();
               });
            });
        }
        if (frm.doc.comp_csid == 1 && frm.doc.prod_csid == 0) {
            frm.add_custom_button('GET Production CSID', function() {
                frm.call('get_production_csid').then(r => {
                   if (r.message) {
                       frappe.msgprint(r.message);
                   }
                   frm.reload_doc();
               });
            });
        }
        frm.add_custom_button('Reset Config', function() {
            frm.call('reset_zatca_config').then(r => {
               if (r.message) {
                   frappe.msgprint(r.message);
               }
               frm.reload_doc();
           });
        });
        // frm.add_custom_button('Enable Zatca SDK', function() {
        //     frm.call('enable_zatca_sdk').then(r => {
        //        if (r.message) {
        //            frappe.msgprint(r.message);
        //        }
        //    });
        // });
       
    },
    environment: function(frm) {
        if (frm.doc.environment == 'Production'){
            frm.set_value('certificate_template_name','ZATCA-Code-Signing')
        }else {
            frm.set_value('certificate_template_name','PREZATCA-Code-Signing')
        }
    }
});
