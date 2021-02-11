# -*- coding: utf-8 -*-
# Copyright (c) 2019, IT-Geräte und IT-Lösungen wie Server, Rechner, Netzwerke und E-Mailserver sowie auch Backups, and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt
import fileinput
from frappe import _

import json

@frappe.whitelist()
def make_sales_invoice(source_name, item_code=None, customer=None, project=None):
	target = frappe.new_doc("Sales Invoice")
	total_hours = 0
	timesheet_list = frappe.db.sql("""SELECT `name` FROM `tabTimesheet` WHERE `issue` = '{issue}'""".format(issue=source_name), as_dict=1)
	
	for _timesheet in timesheet_list:
		timesheet = frappe.get_doc('Timesheet', _timesheet.name)
		if timesheet.total_billable_hours:
			if not timesheet.total_billable_hours == timesheet.total_billed_hours:
				hours = flt(timesheet.total_billable_hours) - flt(timesheet.total_billed_hours)
				billing_amount = flt(timesheet.total_billable_amount) - flt(timesheet.total_billed_amount)
				
				target.append('timesheets', {
					'time_sheet': timesheet.name,
					'billing_hours': hours,
					'billing_amount': billing_amount
				})
				
				total_hours += hours
				
	if customer:
		target.customer = customer
		
	if project:
		target.project = project

	if item_code:
		target.append('items', {
			'item_code': item_code,
			'qty': total_hours
		})
		
	return target
	
@frappe.whitelist()
def relink_email(doctype, name, issue):
    """Relink Email and copy comments to Issue.

    params:
    doctype -- Doctype of the reference document
    name -- Name of the reference document
    ticket_name -- Name of the Issue
    """
    comm_list = frappe.get_list("Communication", filters={
        "reference_doctype": doctype,
        "reference_name": name
    })

    for email in comm_list:
        frappe.email.relink(
            name=email.name,
            reference_doctype="Issue",
            reference_name=issue
        )

    # copy comments
    doc = frappe.get_doc(doctype, name)
    ticket = frappe.get_doc("Issue", issue)

    if doc._comments:
        for comment in json.loads(doc._comments):
            ticket.add_comment('Comment', 'Copied comment from Task <a href="/desk#Form/Task/' + doc.name + '">' + doc.name + '</a>:<br>' + comment["comment"])
			
@frappe.whitelist()
def get_it_management_table(customer=None, type=None, status=None):
	results = []
	filter = ''
	if customer or type or status:
		filter = ' WHERE '
	if customer:
		filter += " `customer` = '{customer}'".format(customer=customer)
	if type:
		if customer:
			filter += " AND `type` = '{type}'".format(type=type)
		else:
			filter += " `type` = '{type}'".format(type=type)
	if status:
		if customer or type:
			filter += " AND `status` = '{status}'".format(status=status)
		else:
			filter += " `status` = '{status}'".format(status=status)
			
	#search it checklist
	it_checklist_results = frappe.db.sql("""SELECT
											`name` AS `reference`,
											`name` AS `Link Name`,
											`customer` AS `Customer`,
											`type` AS `Type`,
											`status` AS `Status`
											FROM `tabIT Checklist`{filter}""".format(filter=filter), as_dict=True)
											
	for it_checklist_result in it_checklist_results:
		results.append(it_checklist_result)
	
	if results:
		return results
	else:
		return False
		
@frappe.whitelist()
def get_it_management_table_from_source(source="IT Checklist", reference=None):
	return frappe.get_doc(source, reference).it_management_table
	
@frappe.whitelist() #TODO Remove this... is being called via Sales Invoice -> Get items from -> ...
def get_timesheets_from_source(source, source_ref):
	if source == 'Project':
		return frappe.db.sql("""SELECT `name`, `parent`, `billing_hours`, `billing_amount` AS `billing_amt`
				FROM `tabTimesheet Detail` WHERE `parenttype` = 'Timesheet' AND `docstatus` = 1 AND `project` = '{project}' AND `billable` = 1
				AND `sales_invoice` IS NULL""".format(project=source_ref), as_dict=True)
				
	if source == 'Task':
		return frappe.db.sql("""SELECT `name`, `parent`, `billing_hours`, `billing_amount` AS `billing_amt`
				FROM `tabTimesheet Detail` WHERE `parenttype` = 'Timesheet' AND `docstatus` = 1 AND `task` = '{task}' AND `billable` = 1
				AND `sales_invoice` IS NULL""".format(task=source_ref), as_dict=True)
				
	if source == 'Issue':
		return frappe.db.sql("""SELECT `name`, `parent`, `billing_hours`, `billing_amount` AS `billing_amt`
				FROM `tabTimesheet Detail` WHERE `parenttype` = 'Timesheet' AND `docstatus` = 1 AND `billable` = 1
				AND `sales_invoice` IS NULL AND `parent` IN(SELECT `name` FROM `tabTimesheet` WHERE `issue` = '{issue}')""".format(issue=source_ref), as_dict=True)
				
	if source == 'IT Service Report':
		it_service_report = frappe.get_doc("IT Service Report", source_ref)
		ts = frappe.get_doc("Timesheet", it_service_report.timesheet)
		if ts:
			return frappe.db.sql("""SELECT `name`, `parent`, `billing_hours`, `billing_amount` AS `billing_amt`
				FROM `tabTimesheet Detail` WHERE `parenttype` = 'Timesheet' AND `docstatus` = 1 AND `billable` = 1
				AND `sales_invoice` IS NULL AND `parent` = '{ts}'""".format(ts=ts.name), as_dict=True)
		else:
			return []

@frappe.whitelist()
def add_sales_invoice_timesheets(data):
	try:
		if(isinstance(data,str)):
			data = json.loads(data)
		
		print(data)

		#Remove all existing Timesheets from Sales Invoice if Tasks have been selecte
		if len(data["tasks"]) > 0:
			print(data["names_of_timesheets_detail_in_sales_invoice"])
			for sits in data["names_of_timesheets_detail_in_sales_invoice"]:
				print("Deleteing: " + str(sits))
				doc = frappe.get_doc("Sales Invoice Timesheet",sits)
				doc.delete()

		#Get Timesheet Details of the Tasks
		for task in data["tasks"]:
			tsdetails = frappe.db.sql("""SELECT `name`, `parent`, `billing_hours`, `billing_amount` AS `billing_amt`
					FROM `tabTimesheet Detail` WHERE `parenttype` = 'Timesheet' AND `docstatus` = 1 AND `task` = '{task}' AND `billable` = 1
					AND `sales_invoice` IS NULL""".format(task=task["task"]), as_dict=True)

			for tsdetail in tsdetails:
				#Insert selected Timesheets to Sales Invoice
				doc = frappe.get_doc('Sales Invoice', data["sales invoice"])
				doc.append('timesheets', {
					'time_sheet': tsdetail["parent"],
					'billing_hours': tsdetail["billing_hours"],
					'billing_amount': tsdetail["billing_amt"],
					'timesheet_detail': tsdetail["name"],
					'owner' : frappe.session.user
				})
				doc.save()
		
		#If Pull Timesheets on Save not active: Delete all Timesheets from DB
		if(data["pull_timesheets_on_save"] == 0):
			print("deleting timesheets")
			frappe.db.sql("""DELETE FROM `tabSales Invoice Timesheet` 
					WHERE parent LIKE '{sales_invoice}';""".format(sales_invoice=data["sales invoice"]), as_dict=True)
		
		return "Done"
	except Exception as ex:
		frappe.throw(str(ex), ex, "Error while saving or while adding timesheets.")

def finditer_with_line_numbers(pattern, string, flags=0):
    '''
    A version of 're.finditer' that returns '(match, line_number)' pairs.
    '''
    import re

    matches = list(re.finditer(pattern, string, flags))
    if not matches:
        return []

    end = matches[-1].start()
    # -1 so a failed 'rfind' maps to the first line.
    newline_table = {-1: 0}
    for i, m in enumerate(re.finditer(r'\n', string), 1):
        # don't find newlines past our last match
        offset = m.start()
        if offset > end:
            break
        newline_table[offset] = i

    # Failing to find the newline is OK, -1 maps to 0.
    for m in matches:
        newline_offset = string.rfind('\n', 0, m.start())
        line_number = newline_table[newline_offset]
        yield (m, line_number)
			
@frappe.whitelist()
def turn_off_auto_fetching_timesheets():
	js_file = open("/home/marius/frappe-bench/apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.js", 'r+')

	js_file_content_string = js_file.read()

	#Source: https://stackoverflow.com/questions/16673778/python-regex-match-in-multiline-but-still-want-to-get-the-line-number
	for match in finditer_with_line_numbers(r"frappe.ui.form.on('Sales Invoice Timesheet'",js_file_content_string):
    		print(match)
			
	"""
	js_file_content = js_file.readlines()
	if js_file_content[831] == "/* frappe.ui.form.on('Sales Invoice Timesheet', {\n":
		frappe.throw(_("Diese Funktion wurde bereits ausgeführt."))
	else:
		if js_file_content[825] == "frappe.ui.form.on('Sales Invoice Timesheet', {\n":
			js_file_content[825] = "/* frappe.ui.form.on('Sales Invoice Timesheet', {\n"
			js_file_content[847] = "}) */\n"
			js_file.seek(0)
			js_file.truncate()
			for line in js_file_content:
				js_file.write(line)
			js_file.close()
			
			py_file = open("/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py", 'r+')
			py_file_content = py_file.readlines()
			if py_file_content[644] == "		self.set('timesheets', [])\n":
				py_file_content[644] = "		# self.set('timesheets', [])\n"
				py_file_content[645] = "		# if self.project:\n"
				py_file_content[646] = "			# for data in get_projectwise_timesheet_data(self.project):\n"
				py_file_content[647] = "				# self.append('timesheets', {\n"
				py_file_content[648] = "						# 'time_sheet': data.parent,\n"
				py_file_content[649] = "						# 'billing_hours': data.billing_hours,\n"
				py_file_content[650] = "						# 'billing_amount': data.billing_amt,\n"
				py_file_content[651] = "						# 'timesheet_detail': data.name\n"
				py_file_content[652] = "					# })\n"
				py_file_content[653] = "			# self.calculate_billing_amount_for_timesheet()\n"
				py_file_content[654] = "		return\n"
				
				py_file.seek(0)
				py_file.truncate()
				for line in py_file_content:
					py_file.write(line)
				py_file.close()
				return _("Die Files (sales_invoice.js und sales_invoice.py) wurden erfolgreich überschrieben")
			else:
				frappe.throw(_("Achtung, hier (sales_invoice.py) scheint etwas nicht zu stimmen!"))
		else:
			frappe.throw(_("Achtung, hier (sales_invoice.js) scheint etwas nicht zu stimmen!"))
	"""

@frappe.whitelist()
def for_every_customer_create_default_landscape():
	print("method called")
	
	cs = frappe.db.get_all('Customer',filters={}, fields=['name','customer_name','it_landscape'],page_length=10000,as_list=False)
	idx = 0
	for c in cs:
		idx += 1
		if c["it_landscape"] == None:
			try:
				doc = frappe.get_doc({
					"doctype" : "IT Landscape",
					"title" : c["customer_name"] + " " + str(idx),
					"customer" : c["name"]
				})
				doc.insert()
				frappe.db.commit()
				frappe.db.set_value('Customer',c["name"],{

					'it_landscape': doc.name

				})
				frappe.db.commit()
				print("Inserted " + str(doc.title))
			except Exception as ex:
				#Check  duplicate (TODO is probably unnessecary)
				dups = frappe.db.get_call('Customer',filters={'customer_name':c["customer_name"]}, fields=['name'], page_length=10000,as_list=False)
				print("Exception Duplicate Customer: " + str(dups))
				if(len(dups) > 1):
					pass
				else:
					frappe.throw(str(ex))
					return

	frappe.msgprint(
		msg='Done',
		title='Done'
	)
	return

@frappe.whitelist()
def for_every_doctype_set_it_landscape_from_customer():
	try:
		doctypes = ['Configuration Item','Solution','IT Backup','Location Room','Issue','Maintenance Visit', 'IT Checklist','Licence','Software Instance',
					'User Account', 'User Group', 'Subnet', 'Project', 'Task'
		]
		for doctype in doctypes:
			print(doctype)
			docs = frappe.db.get_all(doctype,filters={}, fields=['name','it_landscape','customer'],page_length=10000,as_list=False)
			for doc in docs:
				if (doc["it_landscape"] == None) and (doc["customer"] != None):
					it_landscape = frappe.db.get_value("Customer",doc["customer"],'it_landscape')
					print(str(it_landscape))
					frappe.db.set_value(doctype,doc["name"],'it_landscape',it_landscape)
					frappe.db.commit()
		frappe.msgprint(
			msg='Done',
			title='Done'
		)
	except Exception as ex:
		frappe.throw(str(ex))
		return

	return


@frappe.whitelist()
def combined_solution_status(data):
	"""
	This Rest-API Method combines the status of selected documents into one status. The selection has yet not been defined.
	For testing just two doctypes namely Configuration Item and Software Instance,

	Called from public/js/issue.js

	Parameter data e.g.:
	{
		'data' : {
			"solutions" : e,
			"manual_doctype_selection" : ["Configuration Item", "Software Instance"]
		}
	}
	"""
	# Check if called from client side (not necessary)
	if(isinstance(data,str)):
		data = json.loads(data)

	print("Logging for combined_solution_status rest-api request.")
	print(data)

	# Solution names to be checked
	result = []
	for solution in data["solutions"]:
    	
		doc_solution = frappe.get_doc("Solution", solution)

		"""
		My approach (unfinished):

		# If selection is passed as parameter
		if( "manual_doctype_selection" in data ):
				doctype_selection = data["manual_doctype_selection"]
				for doctype in doctype_selection:
					#doc = frappe.desk.form.load.getdoc(doc_origin["doctype"], doc_origin["name"])
					#help(doc_solution)
					
					# Inspecting different objects with inspect instead of debugging
					import inspect
					inspect.getdoc(doc_solution)

					for name, data in inspect.getmembers(doc_solution):
						if name == '__builtins__':
							continue
						print('%s :' % name, repr(data))

					# Quellen: https://stackoverflow.com/questions/39260407/inspecting-python-objects
					
					# Nächster Schritt: Überprüfen, ob childtables anhand des Typs "Array" erkannt werden können. Danach den doctype/namen auslesen und den status aus der Datenbank ziehen.
					#frappe.desk.notifications.get_open_count("Solution",doc_solution.name, items=["Configuration Item"]) #This gets the dashboard counts
					#meta = frappe.model.meta.get_meta("Solution") 
					#links = meta.get_dashboard_data() #Can i get the get_dashboard_data for doctype? beta would be to parse it from javascript.

					# Getting docs as_dict and then printing values
					for key,value in doc_solution.as_dict().items():
    						print(type(value))

		# If selection is not passed pull Issue Dashboard Doctypes
		else:
				return "No doctype selection made."

		"""

		"""
		Approach taken from frappe.desk.notifications.get_open_count() as found by inspecting Network Tab in Firefox Developer Tools when loading a Solution page.
		"""
		doctype = "Solution" ##Change
		name = doc_solution.name ##Change
		items = [] ##Change

		if frappe.flags.in_migrate or frappe.flags.in_install:
			return {
			"count": []
		}

		frappe.has_permission(doc=frappe.get_doc(doctype, name), throw=True)

		meta = frappe.get_meta(doctype)
		links = meta.get_dashboard_data()

		# compile all items in a list
		if not items:
			for group in links.transactions:
				items.extend(group.get("items"))

		if not isinstance(items, list):
			items = json.loads(items)

		sum_stati = 0
		len_docs = 0
		print(items)
		for d in items:
			if d in links.get("internal_links", {}):
				# internal link
				continue

			filters = frappe.desk.notifications.get_filters_for(d)   ## Change: Here I had to add the full path to method get_filters_for(d)
			fieldname = links.get("non_standard_fieldnames", {}).get(d, links.get('fieldname'))

			docs = frappe.get_all(d, fields=["name","docstatus"],
				filters={fieldname: name}, limit=100, distinct=True, ignore_ifnull=True)
			print(docs)

			#Sum status of one dashboard entry
			sum_status = 0
			for doc in docs:
				sum_status += doc.docstatus

			#Sum status of all dashboard entries
			sum_stati += sum_status
			len_docs += len(docs)

		# Calculate combined status for one solution
		combined_status = 0
		combined_status_color = "grey"
		if(len_docs != 0):
			combined_status = sum_stati / len_docs
			if(combined_status == 0):
				combined_status_color = "green"
			elif(combined_status == 1):
				combined_status_color = "orange"
			elif(combined_status == 2):
				combined_status_color = "red"

		result.append({ "name" : name, "combined_status" : combined_status, "combined_status_color" : combined_status_color})

		module = frappe.get_meta_module(doctype)
		if hasattr(module, "get_timeline_data"):
			out["timeline_data"] = module.get_timeline_data(doctype, name)


	# TODO:
	# In allen doctypes auf dem Solution dashboard das feld Status vereinheitlichen.
	# Für jedes dieser Statusfelder ein Farbmapping erstellen. Doppelte Belegung möglich
	# Tabelle in Form:
	# -----------------------------------------------------------
	# - Stati                            - Farbe                            -
	# -----------------------------------------------------------
	# - Implementing             - orange                          -
	# - Running                      - green                            -
	# - Issue                            - red                               -
	# - Obsolet                        - grey                             -
	# -----------------------------------------------------------

	return result

   
   