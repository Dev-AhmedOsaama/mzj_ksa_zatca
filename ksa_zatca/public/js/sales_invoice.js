
frappe.ui.form.on("Sales Invoice", {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.custom_cleared == 0) {
                frm.add_custom_button(__("Zatca"), function() {
                    frm.call({
                        method:"ksa_zatca.ksa_zatca.doctype.zatca_config.zatca_invoice.zatca_Call",
                        args: {
                            "invoice_number": frm.doc.name
                        },
                        freeze:true,
                        freeze_message: __("Sending Zatca Request..."),
                        callback: function(response) {
                            if (response.message) {  
                                frappe.msgprint(response.message);
                                frm.reload_doc();
                            }
                            frm.reload_doc();
                        }

                    });
                    frm.reload_doc();
                }, __("Phase-2"));
        }   
    }
});
frappe.ui.form.on("Sales Invoice Item", {
    item_tax_template(frm, cdt, cdn){
        item = frappe.get_doc(cdt, cdn)
        frm.set_query('custom_tax_exemption_reason','items', ()=>{
            return {
                filters:{
                    tax_category: item.custom_item_tax_category
                }
            }
        })
    }
})
