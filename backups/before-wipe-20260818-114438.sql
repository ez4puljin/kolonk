--
-- PostgreSQL database dump
--

\restrict 4JewKZhonZgsP85oG5RZX7jQpblwpDbzeZdlpipW0dpYupOYXShNs9zhV4X7XdP

-- Dumped from database version 17.11
-- Dumped by pg_dump version 17.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_role_id_fkey;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_branch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.totalizer_readings DROP CONSTRAINT IF EXISTS totalizer_readings_shift_id_fkey;
ALTER TABLE IF EXISTS ONLY public.totalizer_readings DROP CONSTRAINT IF EXISTS totalizer_readings_recorded_by_fkey;
ALTER TABLE IF EXISTS ONLY public.totalizer_readings DROP CONSTRAINT IF EXISTS totalizer_readings_nozzle_id_fkey;
ALTER TABLE IF EXISTS ONLY public.tanks DROP CONSTRAINT IF EXISTS tanks_fuel_id_fkey;
ALTER TABLE IF EXISTS ONLY public.tanks DROP CONSTRAINT IF EXISTS tanks_branch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.tank_movements DROP CONSTRAINT IF EXISTS tank_movements_tank_id_fkey;
ALTER TABLE IF EXISTS ONLY public.shifts DROP CONSTRAINT IF EXISTS shifts_opened_by_fkey;
ALTER TABLE IF EXISTS ONLY public.shifts DROP CONSTRAINT IF EXISTS shifts_closed_by_fkey;
ALTER TABLE IF EXISTS ONLY public.shifts DROP CONSTRAINT IF EXISTS shifts_branch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.shift_tank_levels DROP CONSTRAINT IF EXISTS shift_tank_levels_tank_id_fkey;
ALTER TABLE IF EXISTS ONLY public.shift_tank_levels DROP CONSTRAINT IF EXISTS shift_tank_levels_shift_id_fkey;
ALTER TABLE IF EXISTS ONLY public.shift_price_marks DROP CONSTRAINT IF EXISTS shift_price_marks_shift_id_fkey;
ALTER TABLE IF EXISTS ONLY public.shift_price_marks DROP CONSTRAINT IF EXISTS shift_price_marks_nozzle_id_fkey;
ALTER TABLE IF EXISTS ONLY public.shift_price_marks DROP CONSTRAINT IF EXISTS shift_price_marks_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.shift_closings DROP CONSTRAINT IF EXISTS shift_closings_shift_id_fkey;
ALTER TABLE IF EXISTS ONLY public.shift_closings DROP CONSTRAINT IF EXISTS shift_closings_oil_sale_id_fkey;
ALTER TABLE IF EXISTS ONLY public.shift_closings DROP CONSTRAINT IF EXISTS shift_closings_fuel_sale_id_fkey;
ALTER TABLE IF EXISTS ONLY public.shift_closings DROP CONSTRAINT IF EXISTS shift_closings_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.shift_closings DROP CONSTRAINT IF EXISTS shift_closings_approved_by_fkey;
ALTER TABLE IF EXISTS ONLY public.shift_attachments DROP CONSTRAINT IF EXISTS shift_attachments_uploaded_by_fkey;
ALTER TABLE IF EXISTS ONLY public.shift_attachments DROP CONSTRAINT IF EXISTS shift_attachments_shift_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sales DROP CONSTRAINT IF EXISTS sales_shift_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sales DROP CONSTRAINT IF EXISTS sales_customer_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sales DROP CONSTRAINT IF EXISTS sales_contract_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sales DROP CONSTRAINT IF EXISTS sales_cashier_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sales DROP CONSTRAINT IF EXISTS sales_branch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sale_items DROP CONSTRAINT IF EXISTS sale_items_tank_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sale_items DROP CONSTRAINT IF EXISTS sale_items_sale_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sale_items DROP CONSTRAINT IF EXISTS sale_items_pump_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sale_items DROP CONSTRAINT IF EXISTS sale_items_product_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sale_items DROP CONSTRAINT IF EXISTS sale_items_nozzle_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sale_items DROP CONSTRAINT IF EXISTS sale_items_fuel_id_fkey;
ALTER TABLE IF EXISTS ONLY public.role_permissions DROP CONSTRAINT IF EXISTS role_permissions_role_id_fkey;
ALTER TABLE IF EXISTS ONLY public.role_permissions DROP CONSTRAINT IF EXISTS role_permissions_permission_id_fkey;
ALTER TABLE IF EXISTS ONLY public.refunds DROP CONSTRAINT IF EXISTS refunds_shift_id_fkey;
ALTER TABLE IF EXISTS ONLY public.refunds DROP CONSTRAINT IF EXISTS refunds_sale_id_fkey;
ALTER TABLE IF EXISTS ONLY public.refunds DROP CONSTRAINT IF EXISTS refunds_requested_by_fkey;
ALTER TABLE IF EXISTS ONLY public.refunds DROP CONSTRAINT IF EXISTS refunds_decided_by_fkey;
ALTER TABLE IF EXISTS ONLY public.refund_items DROP CONSTRAINT IF EXISTS refund_items_sale_item_id_fkey;
ALTER TABLE IF EXISTS ONLY public.refund_items DROP CONSTRAINT IF EXISTS refund_items_refund_id_fkey;
ALTER TABLE IF EXISTS ONLY public.purchases DROP CONSTRAINT IF EXISTS purchases_supplier_id_fkey;
ALTER TABLE IF EXISTS ONLY public.purchases DROP CONSTRAINT IF EXISTS purchases_posted_by_fkey;
ALTER TABLE IF EXISTS ONLY public.purchases DROP CONSTRAINT IF EXISTS purchases_ap_invoice_id_fkey;
ALTER TABLE IF EXISTS ONLY public.purchase_items DROP CONSTRAINT IF EXISTS purchase_items_purchase_id_fkey;
ALTER TABLE IF EXISTS ONLY public.purchase_items DROP CONSTRAINT IF EXISTS purchase_items_product_id_fkey;
ALTER TABLE IF EXISTS ONLY public.pumps DROP CONSTRAINT IF EXISTS pumps_branch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.pump_nozzles DROP CONSTRAINT IF EXISTS pump_nozzles_tank_id_fkey;
ALTER TABLE IF EXISTS ONLY public.pump_nozzles DROP CONSTRAINT IF EXISTS pump_nozzles_pump_id_fkey;
ALTER TABLE IF EXISTS ONLY public.pump_nozzles DROP CONSTRAINT IF EXISTS pump_nozzles_fuel_id_fkey;
ALTER TABLE IF EXISTS ONLY public.products DROP CONSTRAINT IF EXISTS products_category_id_fkey;
ALTER TABLE IF EXISTS ONLY public.product_branch_stocks DROP CONSTRAINT IF EXISTS product_branch_stocks_product_id_fkey;
ALTER TABLE IF EXISTS ONLY public.product_branch_stocks DROP CONSTRAINT IF EXISTS product_branch_stocks_branch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.price_changes DROP CONSTRAINT IF EXISTS price_changes_requested_by_fkey;
ALTER TABLE IF EXISTS ONLY public.price_changes DROP CONSTRAINT IF EXISTS price_changes_product_id_fkey;
ALTER TABLE IF EXISTS ONLY public.price_changes DROP CONSTRAINT IF EXISTS price_changes_fuel_id_fkey;
ALTER TABLE IF EXISTS ONLY public.price_changes DROP CONSTRAINT IF EXISTS price_changes_decided_by_fkey;
ALTER TABLE IF EXISTS ONLY public.payroll_periods DROP CONSTRAINT IF EXISTS payroll_periods_approved_by_fkey;
ALTER TABLE IF EXISTS ONLY public.payroll_lines DROP CONSTRAINT IF EXISTS payroll_lines_period_id_fkey;
ALTER TABLE IF EXISTS ONLY public.payroll_lines DROP CONSTRAINT IF EXISTS payroll_lines_employee_id_fkey;
ALTER TABLE IF EXISTS ONLY public.payments DROP CONSTRAINT IF EXISTS payments_sale_id_fkey;
ALTER TABLE IF EXISTS ONLY public.payments DROP CONSTRAINT IF EXISTS payments_contract_id_fkey;
ALTER TABLE IF EXISTS ONLY public.journal_lines DROP CONSTRAINT IF EXISTS journal_lines_entry_id_fkey;
ALTER TABLE IF EXISTS ONLY public.journal_lines DROP CONSTRAINT IF EXISTS journal_lines_account_code_fkey;
ALTER TABLE IF EXISTS ONLY public.journal_entries DROP CONSTRAINT IF EXISTS journal_entries_posted_by_fkey;
ALTER TABLE IF EXISTS ONLY public.inventory_transactions DROP CONSTRAINT IF EXISTS inventory_transactions_product_id_fkey;
ALTER TABLE IF EXISTS ONLY public.fuel_receipts DROP CONSTRAINT IF EXISTS fuel_receipts_tank_id_fkey;
ALTER TABLE IF EXISTS ONLY public.fuel_receipts DROP CONSTRAINT IF EXISTS fuel_receipts_supplier_id_fkey;
ALTER TABLE IF EXISTS ONLY public.fuel_receipts DROP CONSTRAINT IF EXISTS fuel_receipts_posted_by_fkey;
ALTER TABLE IF EXISTS ONLY public.fuel_receipts DROP CONSTRAINT IF EXISTS fuel_receipts_fuel_id_fkey;
ALTER TABLE IF EXISTS ONLY public.fuel_receipts DROP CONSTRAINT IF EXISTS fuel_receipts_ap_invoice_id_fkey;
ALTER TABLE IF EXISTS ONLY public.purchases DROP CONSTRAINT IF EXISTS fk_purchases_branch;
ALTER TABLE IF EXISTS ONLY public.products DROP CONSTRAINT IF EXISTS fk_products_bulk_product_id;
ALTER TABLE IF EXISTS ONLY public.price_changes DROP CONSTRAINT IF EXISTS fk_price_changes_branch;
ALTER TABLE IF EXISTS ONLY public.inventory_transactions DROP CONSTRAINT IF EXISTS fk_inventory_tx_branch;
ALTER TABLE IF EXISTS ONLY public.expenses DROP CONSTRAINT IF EXISTS fk_expenses_bank_account_id;
ALTER TABLE IF EXISTS ONLY public.ar_payments DROP CONSTRAINT IF EXISTS fk_ar_payments_bank_account_id;
ALTER TABLE IF EXISTS ONLY public.expenses DROP CONSTRAINT IF EXISTS expenses_supplier_id_fkey;
ALTER TABLE IF EXISTS ONLY public.expenses DROP CONSTRAINT IF EXISTS expenses_shift_id_fkey;
ALTER TABLE IF EXISTS ONLY public.expenses DROP CONSTRAINT IF EXISTS expenses_posted_by_fkey;
ALTER TABLE IF EXISTS ONLY public.expenses DROP CONSTRAINT IF EXISTS expenses_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.expenses DROP CONSTRAINT IF EXISTS expenses_branch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.expenses DROP CONSTRAINT IF EXISTS expenses_ap_invoice_id_fkey;
ALTER TABLE IF EXISTS ONLY public.expenses DROP CONSTRAINT IF EXISTS expenses_account_code_fkey;
ALTER TABLE IF EXISTS ONLY public.employees DROP CONSTRAINT IF EXISTS employees_user_id_fkey;
ALTER TABLE IF EXISTS ONLY public.employees DROP CONSTRAINT IF EXISTS employees_branch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.employee_advances DROP CONSTRAINT IF EXISTS employee_advances_employee_id_fkey;
ALTER TABLE IF EXISTS ONLY public.employee_advances DROP CONSTRAINT IF EXISTS employee_advances_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.ebarimt_queue DROP CONSTRAINT IF EXISTS ebarimt_queue_sale_id_fkey;
ALTER TABLE IF EXISTS ONLY public.contracts DROP CONSTRAINT IF EXISTS contracts_customer_id_fkey;
ALTER TABLE IF EXISTS ONLY public.branches DROP CONSTRAINT IF EXISTS branches_manager_id_fkey;
ALTER TABLE IF EXISTS ONLY public.branch_prices DROP CONSTRAINT IF EXISTS branch_prices_product_id_fkey;
ALTER TABLE IF EXISTS ONLY public.branch_prices DROP CONSTRAINT IF EXISTS branch_prices_fuel_id_fkey;
ALTER TABLE IF EXISTS ONLY public.branch_prices DROP CONSTRAINT IF EXISTS branch_prices_branch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.branch_payment_methods DROP CONSTRAINT IF EXISTS branch_payment_methods_branch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_transactions DROP CONSTRAINT IF EXISTS bank_transactions_statement_id_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_transactions DROP CONSTRAINT IF EXISTS bank_transactions_expense_id_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_transactions DROP CONSTRAINT IF EXISTS bank_transactions_expense_account_code_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_transactions DROP CONSTRAINT IF EXISTS bank_transactions_customer_id_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_transactions DROP CONSTRAINT IF EXISTS bank_transactions_contract_id_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_transactions DROP CONSTRAINT IF EXISTS bank_transactions_ar_payment_id_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_statements DROP CONSTRAINT IF EXISTS bank_statements_uploaded_by_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_statements DROP CONSTRAINT IF EXISTS bank_statements_fee_expense_id_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_statements DROP CONSTRAINT IF EXISTS bank_statements_bank_account_id_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_statement_config DROP CONSTRAINT IF EXISTS bank_statement_config_settlement_customer_id_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_statement_config DROP CONSTRAINT IF EXISTS bank_statement_config_settlement_contract_id_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_statement_config DROP CONSTRAINT IF EXISTS bank_statement_config_fee_account_code_fkey;
ALTER TABLE IF EXISTS ONLY public.bank_accounts DROP CONSTRAINT IF EXISTS bank_accounts_branch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.audit_logs DROP CONSTRAINT IF EXISTS audit_logs_user_id_fkey;
ALTER TABLE IF EXISTS ONLY public.ar_payments DROP CONSTRAINT IF EXISTS ar_payments_customer_id_fkey;
ALTER TABLE IF EXISTS ONLY public.ar_payments DROP CONSTRAINT IF EXISTS ar_payments_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.ar_payments DROP CONSTRAINT IF EXISTS ar_payments_contract_id_fkey;
ALTER TABLE IF EXISTS ONLY public.ar_payments DROP CONSTRAINT IF EXISTS ar_payments_ar_invoice_id_fkey;
ALTER TABLE IF EXISTS ONLY public.ar_invoices DROP CONSTRAINT IF EXISTS ar_invoices_customer_id_fkey;
ALTER TABLE IF EXISTS ONLY public.ar_invoices DROP CONSTRAINT IF EXISTS ar_invoices_contract_id_fkey;
ALTER TABLE IF EXISTS ONLY public.ap_payments DROP CONSTRAINT IF EXISTS ap_payments_supplier_id_fkey;
ALTER TABLE IF EXISTS ONLY public.ap_payments DROP CONSTRAINT IF EXISTS ap_payments_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.ap_payments DROP CONSTRAINT IF EXISTS ap_payments_ap_invoice_id_fkey;
ALTER TABLE IF EXISTS ONLY public.ap_invoices DROP CONSTRAINT IF EXISTS ap_invoices_supplier_id_fkey;
DROP INDEX IF EXISTS public.ix_users_branch_id;
DROP INDEX IF EXISTS public.ix_totalizer_readings_shift_id;
DROP INDEX IF EXISTS public.ix_totalizer_readings_nozzle_id;
DROP INDEX IF EXISTS public.ix_tanks_branch_id;
DROP INDEX IF EXISTS public.ix_tank_movements_tank_id;
DROP INDEX IF EXISTS public.ix_sync_outbox_processed_at;
DROP INDEX IF EXISTS public.ix_sync_outbox_aggregate_type;
DROP INDEX IF EXISTS public.ix_shifts_status;
DROP INDEX IF EXISTS public.ix_shifts_number;
DROP INDEX IF EXISTS public.ix_shifts_branch_id;
DROP INDEX IF EXISTS public.ix_shift_price_marks_shift_id;
DROP INDEX IF EXISTS public.ix_shift_price_marks_nozzle_id;
DROP INDEX IF EXISTS public.ix_shift_attachments_shift_id;
DROP INDEX IF EXISTS public.ix_settings_key;
DROP INDEX IF EXISTS public.ix_sales_status;
DROP INDEX IF EXISTS public.ix_sales_shift_id;
DROP INDEX IF EXISTS public.ix_sales_number;
DROP INDEX IF EXISTS public.ix_sales_completed_at;
DROP INDEX IF EXISTS public.ix_sales_branch_id;
DROP INDEX IF EXISTS public.ix_sale_items_sale_id;
DROP INDEX IF EXISTS public.ix_refunds_status;
DROP INDEX IF EXISTS public.ix_refunds_sale_id;
DROP INDEX IF EXISTS public.ix_refund_items_refund_id;
DROP INDEX IF EXISTS public.ix_purchases_status;
DROP INDEX IF EXISTS public.ix_purchases_number;
DROP INDEX IF EXISTS public.ix_purchases_branch_id;
DROP INDEX IF EXISTS public.ix_purchase_items_purchase_id;
DROP INDEX IF EXISTS public.ix_pumps_branch_id;
DROP INDEX IF EXISTS public.ix_products_name_mn;
DROP INDEX IF EXISTS public.ix_products_bulk_product_id;
DROP INDEX IF EXISTS public.ix_products_barcode;
DROP INDEX IF EXISTS public.ix_product_branch_stocks_product_id;
DROP INDEX IF EXISTS public.ix_product_branch_stocks_branch_id;
DROP INDEX IF EXISTS public.ix_price_changes_status;
DROP INDEX IF EXISTS public.ix_price_changes_branch_id;
DROP INDEX IF EXISTS public.ix_payroll_periods_year;
DROP INDEX IF EXISTS public.ix_payroll_periods_status;
DROP INDEX IF EXISTS public.ix_payroll_periods_month;
DROP INDEX IF EXISTS public.ix_payments_sale_id;
DROP INDEX IF EXISTS public.ix_payments_method;
DROP INDEX IF EXISTS public.ix_journal_lines_entry_id;
DROP INDEX IF EXISTS public.ix_journal_lines_dim_supplier_id;
DROP INDEX IF EXISTS public.ix_journal_lines_dim_fuel_id;
DROP INDEX IF EXISTS public.ix_journal_lines_dim_customer_id;
DROP INDEX IF EXISTS public.ix_journal_lines_dim_bank_account_id;
DROP INDEX IF EXISTS public.ix_journal_lines_account_code;
DROP INDEX IF EXISTS public.ix_journal_entries_source_type;
DROP INDEX IF EXISTS public.ix_journal_entries_source_id;
DROP INDEX IF EXISTS public.ix_journal_entries_event_type;
DROP INDEX IF EXISTS public.ix_journal_entries_entry_no;
DROP INDEX IF EXISTS public.ix_journal_entries_entry_date;
DROP INDEX IF EXISTS public.ix_inventory_transactions_product_id;
DROP INDEX IF EXISTS public.ix_inventory_transactions_branch_id;
DROP INDEX IF EXISTS public.ix_fuel_receipts_status;
DROP INDEX IF EXISTS public.ix_fuel_receipts_number;
DROP INDEX IF EXISTS public.ix_expenses_status;
DROP INDEX IF EXISTS public.ix_expenses_payment_method;
DROP INDEX IF EXISTS public.ix_expenses_number;
DROP INDEX IF EXISTS public.ix_expenses_expense_date;
DROP INDEX IF EXISTS public.ix_expenses_branch_id;
DROP INDEX IF EXISTS public.ix_expenses_bank_account_id;
DROP INDEX IF EXISTS public.ix_expenses_account_code;
DROP INDEX IF EXISTS public.ix_employees_is_active;
DROP INDEX IF EXISTS public.ix_employees_full_name;
DROP INDEX IF EXISTS public.ix_employees_branch_id;
DROP INDEX IF EXISTS public.ix_employee_advances_employee_id;
DROP INDEX IF EXISTS public.ix_employee_advances_advance_date;
DROP INDEX IF EXISTS public.ix_ebarimt_queue_status;
DROP INDEX IF EXISTS public.ix_ebarimt_queue_sale_id;
DROP INDEX IF EXISTS public.ix_customers_province;
DROP INDEX IF EXISTS public.ix_customers_phone;
DROP INDEX IF EXISTS public.ix_customers_name;
DROP INDEX IF EXISTS public.ix_customers_district;
DROP INDEX IF EXISTS public.ix_branches_is_active;
DROP INDEX IF EXISTS public.ix_branches_code;
DROP INDEX IF EXISTS public.ix_branch_prices_product_id;
DROP INDEX IF EXISTS public.ix_branch_prices_fuel_id;
DROP INDEX IF EXISTS public.ix_branch_prices_branch_id;
DROP INDEX IF EXISTS public.ix_branch_payment_methods_branch_id;
DROP INDEX IF EXISTS public.ix_bank_transactions_txn_date;
DROP INDEX IF EXISTS public.ix_bank_transactions_statement_id;
DROP INDEX IF EXISTS public.ix_bank_transactions_customer_id;
DROP INDEX IF EXISTS public.ix_bank_transactions_contract_id;
DROP INDEX IF EXISTS public.ix_bank_statements_date_from;
DROP INDEX IF EXISTS public.ix_bank_statements_bank_account_id;
DROP INDEX IF EXISTS public.ix_bank_statements_account_number;
DROP INDEX IF EXISTS public.ix_bank_accounts_branch_id;
DROP INDEX IF EXISTS public.ix_bank_accounts_account_number;
DROP INDEX IF EXISTS public.ix_audit_logs_entity_type;
DROP INDEX IF EXISTS public.ix_audit_logs_action;
DROP INDEX IF EXISTS public.ix_ar_payments_customer_id;
DROP INDEX IF EXISTS public.ix_ar_payments_bank_account_id;
DROP INDEX IF EXISTS public.ix_ar_invoices_status;
DROP INDEX IF EXISTS public.ix_ar_invoices_customer_id;
DROP INDEX IF EXISTS public.ix_ap_payments_ap_invoice_id;
DROP INDEX IF EXISTS public.ix_ap_invoices_supplier_id;
DROP INDEX IF EXISTS public.ix_ap_invoices_status;
DROP INDEX IF EXISTS public.ix_accounts_code;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_username_key;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_pkey;
ALTER TABLE IF EXISTS ONLY public.shift_tank_levels DROP CONSTRAINT IF EXISTS uq_shift_tank_phase;
ALTER TABLE IF EXISTS ONLY public.role_permissions DROP CONSTRAINT IF EXISTS uq_role_permission;
ALTER TABLE IF EXISTS ONLY public.pump_nozzles DROP CONSTRAINT IF EXISTS uq_pump_nozzle;
ALTER TABLE IF EXISTS ONLY public.pumps DROP CONSTRAINT IF EXISTS uq_pump_branch_number;
ALTER TABLE IF EXISTS ONLY public.product_branch_stocks DROP CONSTRAINT IF EXISTS uq_product_branch;
ALTER TABLE IF EXISTS ONLY public.payroll_periods DROP CONSTRAINT IF EXISTS uq_payroll_period;
ALTER TABLE IF EXISTS ONLY public.payroll_lines DROP CONSTRAINT IF EXISTS uq_payroll_line;
ALTER TABLE IF EXISTS ONLY public.journal_entries DROP CONSTRAINT IF EXISTS uq_journal_source_event;
ALTER TABLE IF EXISTS ONLY public.branch_prices DROP CONSTRAINT IF EXISTS uq_branch_product_price;
ALTER TABLE IF EXISTS ONLY public.branch_payment_methods DROP CONSTRAINT IF EXISTS uq_branch_payment_method;
ALTER TABLE IF EXISTS ONLY public.branch_prices DROP CONSTRAINT IF EXISTS uq_branch_fuel_price;
ALTER TABLE IF EXISTS ONLY public.bank_accounts DROP CONSTRAINT IF EXISTS uq_bank_account_number;
ALTER TABLE IF EXISTS ONLY public.ar_invoices DROP CONSTRAINT IF EXISTS uq_ar_contract_period;
ALTER TABLE IF EXISTS ONLY public.totalizer_readings DROP CONSTRAINT IF EXISTS totalizer_readings_pkey;
ALTER TABLE IF EXISTS ONLY public.tanks DROP CONSTRAINT IF EXISTS tanks_pkey;
ALTER TABLE IF EXISTS ONLY public.tank_movements DROP CONSTRAINT IF EXISTS tank_movements_pkey;
ALTER TABLE IF EXISTS ONLY public.sync_outbox DROP CONSTRAINT IF EXISTS sync_outbox_pkey;
ALTER TABLE IF EXISTS ONLY public.suppliers DROP CONSTRAINT IF EXISTS suppliers_pkey;
ALTER TABLE IF EXISTS ONLY public.shifts DROP CONSTRAINT IF EXISTS shifts_pkey;
ALTER TABLE IF EXISTS ONLY public.shift_tank_levels DROP CONSTRAINT IF EXISTS shift_tank_levels_pkey;
ALTER TABLE IF EXISTS ONLY public.shift_price_marks DROP CONSTRAINT IF EXISTS shift_price_marks_pkey;
ALTER TABLE IF EXISTS ONLY public.shift_closings DROP CONSTRAINT IF EXISTS shift_closings_shift_id_key;
ALTER TABLE IF EXISTS ONLY public.shift_closings DROP CONSTRAINT IF EXISTS shift_closings_pkey;
ALTER TABLE IF EXISTS ONLY public.shift_attachments DROP CONSTRAINT IF EXISTS shift_attachments_pkey;
ALTER TABLE IF EXISTS ONLY public.settings DROP CONSTRAINT IF EXISTS settings_pkey;
ALTER TABLE IF EXISTS ONLY public.sales DROP CONSTRAINT IF EXISTS sales_pkey;
ALTER TABLE IF EXISTS ONLY public.sale_items DROP CONSTRAINT IF EXISTS sale_items_pkey;
ALTER TABLE IF EXISTS ONLY public.roles DROP CONSTRAINT IF EXISTS roles_pkey;
ALTER TABLE IF EXISTS ONLY public.roles DROP CONSTRAINT IF EXISTS roles_code_key;
ALTER TABLE IF EXISTS ONLY public.role_permissions DROP CONSTRAINT IF EXISTS role_permissions_pkey;
ALTER TABLE IF EXISTS ONLY public.refunds DROP CONSTRAINT IF EXISTS refunds_pkey;
ALTER TABLE IF EXISTS ONLY public.refund_items DROP CONSTRAINT IF EXISTS refund_items_pkey;
ALTER TABLE IF EXISTS ONLY public.purchases DROP CONSTRAINT IF EXISTS purchases_pkey;
ALTER TABLE IF EXISTS ONLY public.purchase_items DROP CONSTRAINT IF EXISTS purchase_items_pkey;
ALTER TABLE IF EXISTS ONLY public.pumps DROP CONSTRAINT IF EXISTS pumps_pkey;
ALTER TABLE IF EXISTS ONLY public.pump_nozzles DROP CONSTRAINT IF EXISTS pump_nozzles_pkey;
ALTER TABLE IF EXISTS ONLY public.products DROP CONSTRAINT IF EXISTS products_sku_key;
ALTER TABLE IF EXISTS ONLY public.products DROP CONSTRAINT IF EXISTS products_pkey;
ALTER TABLE IF EXISTS ONLY public.product_categories DROP CONSTRAINT IF EXISTS product_categories_pkey;
ALTER TABLE IF EXISTS ONLY public.product_branch_stocks DROP CONSTRAINT IF EXISTS product_branch_stocks_pkey;
ALTER TABLE IF EXISTS ONLY public.price_changes DROP CONSTRAINT IF EXISTS price_changes_pkey;
ALTER TABLE IF EXISTS ONLY public.permissions DROP CONSTRAINT IF EXISTS permissions_pkey;
ALTER TABLE IF EXISTS ONLY public.permissions DROP CONSTRAINT IF EXISTS permissions_code_key;
ALTER TABLE IF EXISTS ONLY public.payroll_periods DROP CONSTRAINT IF EXISTS payroll_periods_pkey;
ALTER TABLE IF EXISTS ONLY public.payroll_lines DROP CONSTRAINT IF EXISTS payroll_lines_pkey;
ALTER TABLE IF EXISTS ONLY public.payments DROP CONSTRAINT IF EXISTS payments_pkey;
ALTER TABLE IF EXISTS ONLY public.journal_lines DROP CONSTRAINT IF EXISTS journal_lines_pkey;
ALTER TABLE IF EXISTS ONLY public.journal_entries DROP CONSTRAINT IF EXISTS journal_entries_pkey;
ALTER TABLE IF EXISTS ONLY public.inventory_transactions DROP CONSTRAINT IF EXISTS inventory_transactions_pkey;
ALTER TABLE IF EXISTS ONLY public.fuels DROP CONSTRAINT IF EXISTS fuels_pkey;
ALTER TABLE IF EXISTS ONLY public.fuels DROP CONSTRAINT IF EXISTS fuels_code_key;
ALTER TABLE IF EXISTS ONLY public.fuel_receipts DROP CONSTRAINT IF EXISTS fuel_receipts_pkey;
ALTER TABLE IF EXISTS ONLY public.expenses DROP CONSTRAINT IF EXISTS expenses_pkey;
ALTER TABLE IF EXISTS ONLY public.employees DROP CONSTRAINT IF EXISTS employees_pkey;
ALTER TABLE IF EXISTS ONLY public.employee_advances DROP CONSTRAINT IF EXISTS employee_advances_pkey;
ALTER TABLE IF EXISTS ONLY public.ebarimt_queue DROP CONSTRAINT IF EXISTS ebarimt_queue_pkey;
ALTER TABLE IF EXISTS ONLY public.customers DROP CONSTRAINT IF EXISTS customers_pkey;
ALTER TABLE IF EXISTS ONLY public.contracts DROP CONSTRAINT IF EXISTS contracts_pkey;
ALTER TABLE IF EXISTS ONLY public.contracts DROP CONSTRAINT IF EXISTS contracts_contract_no_key;
ALTER TABLE IF EXISTS ONLY public.branches DROP CONSTRAINT IF EXISTS branches_pkey;
ALTER TABLE IF EXISTS ONLY public.branch_prices DROP CONSTRAINT IF EXISTS branch_prices_pkey;
ALTER TABLE IF EXISTS ONLY public.branch_payment_methods DROP CONSTRAINT IF EXISTS branch_payment_methods_pkey;
ALTER TABLE IF EXISTS ONLY public.bank_transactions DROP CONSTRAINT IF EXISTS bank_transactions_pkey;
ALTER TABLE IF EXISTS ONLY public.bank_transactions DROP CONSTRAINT IF EXISTS bank_transactions_expense_id_key;
ALTER TABLE IF EXISTS ONLY public.bank_transactions DROP CONSTRAINT IF EXISTS bank_transactions_ar_payment_id_key;
ALTER TABLE IF EXISTS ONLY public.bank_statements DROP CONSTRAINT IF EXISTS bank_statements_pkey;
ALTER TABLE IF EXISTS ONLY public.bank_statements DROP CONSTRAINT IF EXISTS bank_statements_fee_expense_id_key;
ALTER TABLE IF EXISTS ONLY public.bank_statement_config DROP CONSTRAINT IF EXISTS bank_statement_config_pkey;
ALTER TABLE IF EXISTS ONLY public.bank_accounts DROP CONSTRAINT IF EXISTS bank_accounts_pkey;
ALTER TABLE IF EXISTS ONLY public.audit_logs DROP CONSTRAINT IF EXISTS audit_logs_pkey;
ALTER TABLE IF EXISTS ONLY public.ar_payments DROP CONSTRAINT IF EXISTS ar_payments_pkey;
ALTER TABLE IF EXISTS ONLY public.ar_invoices DROP CONSTRAINT IF EXISTS ar_invoices_pkey;
ALTER TABLE IF EXISTS ONLY public.ar_invoices DROP CONSTRAINT IF EXISTS ar_invoices_invoice_no_key;
ALTER TABLE IF EXISTS ONLY public.ap_payments DROP CONSTRAINT IF EXISTS ap_payments_pkey;
ALTER TABLE IF EXISTS ONLY public.ap_invoices DROP CONSTRAINT IF EXISTS ap_invoices_pkey;
ALTER TABLE IF EXISTS ONLY public.alembic_version DROP CONSTRAINT IF EXISTS alembic_version_pkc;
ALTER TABLE IF EXISTS ONLY public.accounts DROP CONSTRAINT IF EXISTS accounts_pkey;
DROP TABLE IF EXISTS public.users;
DROP TABLE IF EXISTS public.totalizer_readings;
DROP TABLE IF EXISTS public.tanks;
DROP TABLE IF EXISTS public.tank_movements;
DROP TABLE IF EXISTS public.sync_outbox;
DROP TABLE IF EXISTS public.suppliers;
DROP TABLE IF EXISTS public.shifts;
DROP TABLE IF EXISTS public.shift_tank_levels;
DROP TABLE IF EXISTS public.shift_price_marks;
DROP TABLE IF EXISTS public.shift_closings;
DROP TABLE IF EXISTS public.shift_attachments;
DROP TABLE IF EXISTS public.settings;
DROP TABLE IF EXISTS public.sales;
DROP SEQUENCE IF EXISTS public.sale_number_seq;
DROP TABLE IF EXISTS public.sale_items;
DROP TABLE IF EXISTS public.roles;
DROP TABLE IF EXISTS public.role_permissions;
DROP TABLE IF EXISTS public.refunds;
DROP TABLE IF EXISTS public.refund_items;
DROP TABLE IF EXISTS public.purchases;
DROP SEQUENCE IF EXISTS public.purchase_number_seq;
DROP TABLE IF EXISTS public.purchase_items;
DROP TABLE IF EXISTS public.pumps;
DROP TABLE IF EXISTS public.pump_nozzles;
DROP TABLE IF EXISTS public.products;
DROP TABLE IF EXISTS public.product_categories;
DROP TABLE IF EXISTS public.product_branch_stocks;
DROP TABLE IF EXISTS public.price_changes;
DROP TABLE IF EXISTS public.permissions;
DROP TABLE IF EXISTS public.payroll_periods;
DROP TABLE IF EXISTS public.payroll_lines;
DROP TABLE IF EXISTS public.payments;
DROP TABLE IF EXISTS public.journal_lines;
DROP TABLE IF EXISTS public.journal_entries;
DROP SEQUENCE IF EXISTS public.journal_entry_no_seq;
DROP TABLE IF EXISTS public.inventory_transactions;
DROP TABLE IF EXISTS public.fuels;
DROP TABLE IF EXISTS public.fuel_receipts;
DROP SEQUENCE IF EXISTS public.receipt_number_seq;
DROP TABLE IF EXISTS public.expenses;
DROP SEQUENCE IF EXISTS public.expense_number_seq;
DROP TABLE IF EXISTS public.employees;
DROP TABLE IF EXISTS public.employee_advances;
DROP TABLE IF EXISTS public.ebarimt_queue;
DROP TABLE IF EXISTS public.customers;
DROP TABLE IF EXISTS public.contracts;
DROP TABLE IF EXISTS public.branches;
DROP TABLE IF EXISTS public.branch_prices;
DROP TABLE IF EXISTS public.branch_payment_methods;
DROP TABLE IF EXISTS public.bank_transactions;
DROP TABLE IF EXISTS public.bank_statements;
DROP TABLE IF EXISTS public.bank_statement_config;
DROP TABLE IF EXISTS public.bank_accounts;
DROP TABLE IF EXISTS public.audit_logs;
DROP TABLE IF EXISTS public.ar_payments;
DROP TABLE IF EXISTS public.ar_invoices;
DROP TABLE IF EXISTS public.ap_payments;
DROP TABLE IF EXISTS public.ap_invoices;
DROP TABLE IF EXISTS public.alembic_version;
DROP TABLE IF EXISTS public.accounts;
DROP EXTENSION IF EXISTS pgcrypto;
--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: accounts; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.accounts (
    code character varying(16) NOT NULL,
    name_mn character varying(128) NOT NULL,
    account_type character varying(16) NOT NULL,
    is_postable boolean NOT NULL,
    parent_code character varying(16),
    sort_order integer NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.accounts OWNER TO kolonk;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO kolonk;

--
-- Name: ap_invoices; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.ap_invoices (
    supplier_id uuid NOT NULL,
    invoice_no character varying(64) NOT NULL,
    invoice_date date NOT NULL,
    due_date date,
    source_type character varying(32) NOT NULL,
    source_id uuid NOT NULL,
    amount_gross numeric(18,2) NOT NULL,
    amount_paid numeric(18,2) NOT NULL,
    status character varying(16) NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ap_invoices OWNER TO kolonk;

--
-- Name: ap_payments; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.ap_payments (
    ap_invoice_id uuid NOT NULL,
    supplier_id uuid NOT NULL,
    amount numeric(18,2) NOT NULL,
    paid_from character varying(16) NOT NULL,
    payment_date date NOT NULL,
    note text,
    created_by uuid,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ap_payments OWNER TO kolonk;

--
-- Name: ar_invoices; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.ar_invoices (
    customer_id uuid NOT NULL,
    contract_id uuid NOT NULL,
    invoice_no character varying(64) NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL,
    issued_at timestamp with time zone,
    amount numeric(18,2) NOT NULL,
    amount_paid numeric(18,2) NOT NULL,
    status character varying(16) NOT NULL,
    lines jsonb,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ar_invoices OWNER TO kolonk;

--
-- Name: ar_payments; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.ar_payments (
    ar_invoice_id uuid,
    customer_id uuid NOT NULL,
    contract_id uuid NOT NULL,
    amount numeric(18,2) NOT NULL,
    received_to character varying(16) NOT NULL,
    payment_date date NOT NULL,
    note text,
    created_by uuid,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    bank_account_id uuid
);


ALTER TABLE public.ar_payments OWNER TO kolonk;

--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.audit_logs (
    user_id uuid,
    action character varying(64) NOT NULL,
    entity_type character varying(64),
    entity_id uuid,
    before jsonb,
    after jsonb,
    ip character varying(64),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.audit_logs OWNER TO kolonk;

--
-- Name: bank_accounts; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.bank_accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    branch_id uuid,
    bank_name character varying(64) NOT NULL,
    account_number character varying(32) NOT NULL,
    holder_name character varying(128) DEFAULT ''::character varying NOT NULL,
    currency character varying(8) DEFAULT 'MNT'::character varying NOT NULL,
    opening_balance numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    is_fee_default boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    note text,
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.bank_accounts OWNER TO kolonk;

--
-- Name: bank_statement_config; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.bank_statement_config (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    settlement_customer_id uuid,
    settlement_contract_id uuid,
    settlement_description text DEFAULT 'ПОС орлого'::text NOT NULL,
    fee_account_code character varying(16),
    fee_description text DEFAULT 'Банкны шимтгэл'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.bank_statement_config OWNER TO kolonk;

--
-- Name: bank_statements; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.bank_statements (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    account_number character varying(32) DEFAULT ''::character varying NOT NULL,
    currency character varying(8) DEFAULT 'MNT'::character varying NOT NULL,
    date_from date,
    date_to date,
    filename character varying(255) DEFAULT ''::character varying NOT NULL,
    uploaded_by uuid,
    bank_account_id uuid,
    fee_expense_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.bank_statements OWNER TO kolonk;

--
-- Name: bank_transactions; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.bank_transactions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    statement_id uuid NOT NULL,
    txn_date timestamp with time zone,
    debit numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    credit numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    bank_description text DEFAULT ''::text NOT NULL,
    bank_counterpart character varying(64) DEFAULT ''::character varying NOT NULL,
    is_fee boolean DEFAULT false NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    customer_id uuid,
    contract_id uuid,
    expense_account_code character varying(16),
    ar_payment_id uuid,
    expense_id uuid,
    posted_at timestamp with time zone,
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.bank_transactions OWNER TO kolonk;

--
-- Name: branch_payment_methods; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.branch_payment_methods (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    branch_id uuid NOT NULL,
    method character varying(16) NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.branch_payment_methods OWNER TO kolonk;

--
-- Name: branch_prices; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.branch_prices (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    branch_id uuid NOT NULL,
    fuel_id uuid,
    product_id uuid,
    price numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.branch_prices OWNER TO kolonk;

--
-- Name: branches; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.branches (
    code character varying(16) NOT NULL,
    name character varying(128) NOT NULL,
    address text,
    phone character varying(32),
    manager_id uuid,
    is_active boolean NOT NULL,
    sort_order integer NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.branches OWNER TO kolonk;

--
-- Name: contracts; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.contracts (
    customer_id uuid NOT NULL,
    contract_no character varying(32) NOT NULL,
    credit_limit numeric(18,2) NOT NULL,
    balance numeric(18,2) NOT NULL,
    price_discount_per_l numeric(18,2) NOT NULL,
    billing_day integer NOT NULL,
    status character varying(16) NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.contracts OWNER TO kolonk;

--
-- Name: customers; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.customers (
    name character varying(128) NOT NULL,
    register_no character varying(32),
    phone character varying(32),
    email character varying(128),
    type character varying(16) NOT NULL,
    is_active boolean NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_name character varying(64),
    phone2 character varying(32),
    province character varying(64),
    district character varying(64),
    credit_limit numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    contract_file character varying(255)
);


ALTER TABLE public.customers OWNER TO kolonk;

--
-- Name: ebarimt_queue; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.ebarimt_queue (
    sale_id uuid NOT NULL,
    status character varying(16) NOT NULL,
    attempt_count integer NOT NULL,
    last_error text,
    receipt_id character varying(64),
    qr_data text,
    lottery_no character varying(32),
    sent_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ebarimt_queue OWNER TO kolonk;

--
-- Name: employee_advances; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.employee_advances (
    employee_id uuid NOT NULL,
    advance_date date NOT NULL,
    amount numeric(18,2) NOT NULL,
    paid_from character varying(16) NOT NULL,
    note text,
    created_by uuid,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.employee_advances OWNER TO kolonk;

--
-- Name: employees; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.employees (
    full_name character varying(128) NOT NULL,
    register_no character varying(32),
    social_no character varying(32),
    "position" character varying(128),
    phone character varying(32),
    bank_account character varying(64),
    base_salary numeric(18,2) NOT NULL,
    hire_date date,
    end_date date,
    is_active boolean NOT NULL,
    user_id uuid,
    note text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    branch_id uuid,
    si_enabled boolean DEFAULT true NOT NULL
);


ALTER TABLE public.employees OWNER TO kolonk;

--
-- Name: expense_number_seq; Type: SEQUENCE; Schema: public; Owner: kolonk
--

CREATE SEQUENCE public.expense_number_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.expense_number_seq OWNER TO kolonk;

--
-- Name: expenses; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.expenses (
    number integer DEFAULT nextval('public.expense_number_seq'::regclass) NOT NULL,
    expense_date date NOT NULL,
    account_code character varying(16) NOT NULL,
    payment_method character varying(16) NOT NULL,
    subtotal numeric(18,2) NOT NULL,
    vat_amount numeric(18,2) NOT NULL,
    total numeric(18,2) NOT NULL,
    supplier_id uuid,
    ap_invoice_id uuid,
    shift_id uuid,
    invoice_no character varying(64),
    description text,
    status character varying(16) NOT NULL,
    created_by uuid,
    posted_by uuid,
    posted_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    branch_id uuid,
    bank_account_id uuid
);


ALTER TABLE public.expenses OWNER TO kolonk;

--
-- Name: receipt_number_seq; Type: SEQUENCE; Schema: public; Owner: kolonk
--

CREATE SEQUENCE public.receipt_number_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.receipt_number_seq OWNER TO kolonk;

--
-- Name: fuel_receipts; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.fuel_receipts (
    number integer DEFAULT nextval('public.receipt_number_seq'::regclass) NOT NULL,
    supplier_id uuid NOT NULL,
    tank_id uuid NOT NULL,
    fuel_id uuid NOT NULL,
    receipt_date date NOT NULL,
    invoice_no character varying(64),
    liters numeric(12,3) NOT NULL,
    unit_cost numeric(18,6) NOT NULL,
    freight_cost numeric(18,2) NOT NULL,
    density numeric(6,4),
    temperature_c numeric(5,2),
    subtotal numeric(18,2) NOT NULL,
    vat_amount numeric(18,2) NOT NULL,
    total_gross numeric(18,2) NOT NULL,
    landed_unit_cost numeric(18,6) NOT NULL,
    status character varying(16) NOT NULL,
    posted_by uuid,
    posted_at timestamp with time zone,
    ap_invoice_id uuid,
    note text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.fuel_receipts OWNER TO kolonk;

--
-- Name: fuels; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.fuels (
    code character varying(16) NOT NULL,
    name_mn character varying(64) NOT NULL,
    price_per_liter numeric(18,2) NOT NULL,
    color_hex character varying(9) NOT NULL,
    sort_order integer NOT NULL,
    is_active boolean NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.fuels OWNER TO kolonk;

--
-- Name: inventory_transactions; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.inventory_transactions (
    product_id uuid NOT NULL,
    tx_type character varying(24) NOT NULL,
    qty numeric(12,3) NOT NULL,
    unit_cost numeric(18,6) NOT NULL,
    balance_after numeric(12,3) NOT NULL,
    ref_type character varying(32),
    ref_id uuid,
    note character varying(255),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    branch_id uuid
);


ALTER TABLE public.inventory_transactions OWNER TO kolonk;

--
-- Name: journal_entry_no_seq; Type: SEQUENCE; Schema: public; Owner: kolonk
--

CREATE SEQUENCE public.journal_entry_no_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.journal_entry_no_seq OWNER TO kolonk;

--
-- Name: journal_entries; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.journal_entries (
    entry_no integer DEFAULT nextval('public.journal_entry_no_seq'::regclass) NOT NULL,
    entry_date date NOT NULL,
    description character varying(255) NOT NULL,
    source_type character varying(32) NOT NULL,
    source_id uuid NOT NULL,
    event_type character varying(48) NOT NULL,
    posted_by uuid,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.journal_entries OWNER TO kolonk;

--
-- Name: journal_lines; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.journal_lines (
    entry_id uuid NOT NULL,
    line_no integer NOT NULL,
    account_code character varying(16) NOT NULL,
    debit numeric(18,2) NOT NULL,
    credit numeric(18,2) NOT NULL,
    memo character varying(255),
    dim_fuel_id uuid,
    dim_tank_id uuid,
    dim_customer_id uuid,
    dim_supplier_id uuid,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    dim_bank_account_id uuid,
    CONSTRAINT ck_journal_line_non_negative CHECK (((debit >= (0)::numeric) AND (credit >= (0)::numeric))),
    CONSTRAINT ck_journal_line_single_side CHECK (((debit = (0)::numeric) OR (credit = (0)::numeric)))
);


ALTER TABLE public.journal_lines OWNER TO kolonk;

--
-- Name: payments; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.payments (
    sale_id uuid NOT NULL,
    method character varying(16) NOT NULL,
    amount numeric(18,2) NOT NULL,
    contract_id uuid,
    received numeric(18,2),
    change_given numeric(18,2),
    ref_no character varying(64),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.payments OWNER TO kolonk;

--
-- Name: payroll_lines; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.payroll_lines (
    period_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    worked_days numeric(6,2) NOT NULL,
    month_days numeric(6,2) NOT NULL,
    base_salary numeric(18,2) NOT NULL,
    earned_salary numeric(18,2) NOT NULL,
    bonus numeric(18,2) NOT NULL,
    other_addition numeric(18,2) NOT NULL,
    gross numeric(18,2) NOT NULL,
    si_employee numeric(18,2) NOT NULL,
    si_employer numeric(18,2) NOT NULL,
    taxable numeric(18,2) NOT NULL,
    pit numeric(18,2) NOT NULL,
    advance numeric(18,2) NOT NULL,
    other_deduction numeric(18,2) NOT NULL,
    net numeric(18,2) NOT NULL,
    note text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    worked_from date,
    worked_to date,
    si_enabled boolean DEFAULT true NOT NULL
);


ALTER TABLE public.payroll_lines OWNER TO kolonk;

--
-- Name: payroll_periods; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.payroll_periods (
    year integer NOT NULL,
    month integer NOT NULL,
    status character varying(16) NOT NULL,
    si_employee_rate numeric(8,6) NOT NULL,
    si_employer_rate numeric(8,6) NOT NULL,
    pit_rate numeric(8,6) NOT NULL,
    pit_credit numeric(18,2) NOT NULL,
    gross_total numeric(18,2) NOT NULL,
    si_employee_total numeric(18,2) NOT NULL,
    si_employer_total numeric(18,2) NOT NULL,
    pit_total numeric(18,2) NOT NULL,
    net_total numeric(18,2) NOT NULL,
    paid_salary numeric(18,2) NOT NULL,
    paid_pit numeric(18,2) NOT NULL,
    paid_social numeric(18,2) NOT NULL,
    approved_by uuid,
    approved_at timestamp with time zone,
    note text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    auto_sync boolean DEFAULT true NOT NULL
);


ALTER TABLE public.payroll_periods OWNER TO kolonk;

--
-- Name: permissions; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.permissions (
    code character varying(64) NOT NULL,
    name_mn character varying(128) NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.permissions OWNER TO kolonk;

--
-- Name: price_changes; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.price_changes (
    target_type character varying(16) NOT NULL,
    fuel_id uuid,
    product_id uuid,
    old_price numeric(18,2) NOT NULL,
    new_price numeric(18,2) NOT NULL,
    reason text,
    status character varying(16) NOT NULL,
    requested_by uuid NOT NULL,
    decided_by uuid,
    decided_at timestamp with time zone,
    decision_note text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    branch_id uuid,
    effective_date date,
    applied_at timestamp with time zone
);


ALTER TABLE public.price_changes OWNER TO kolonk;

--
-- Name: product_branch_stocks; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.product_branch_stocks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    product_id uuid NOT NULL,
    branch_id uuid NOT NULL,
    qty numeric(12,3) DEFAULT '0'::numeric NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    avg_cost numeric(18,6) DEFAULT '0'::numeric NOT NULL
);


ALTER TABLE public.product_branch_stocks OWNER TO kolonk;

--
-- Name: product_categories; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.product_categories (
    name_mn character varying(64) NOT NULL,
    icon character varying(32),
    sort_order integer NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.product_categories OWNER TO kolonk;

--
-- Name: products; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.products (
    sku character varying(32) NOT NULL,
    barcode character varying(64),
    name_mn character varying(128) NOT NULL,
    category_id uuid NOT NULL,
    unit character varying(8) NOT NULL,
    price numeric(18,2) NOT NULL,
    avg_cost numeric(18,6) NOT NULL,
    stock_qty numeric(12,3) NOT NULL,
    min_stock numeric(12,3) NOT NULL,
    is_active boolean NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    sale_mode character varying(8) DEFAULT 'piece'::character varying NOT NULL,
    bulk_product_id uuid,
    bulk_factor numeric(12,3) DEFAULT '0'::numeric NOT NULL
);


ALTER TABLE public.products OWNER TO kolonk;

--
-- Name: pump_nozzles; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.pump_nozzles (
    pump_id uuid NOT NULL,
    nozzle_number integer NOT NULL,
    fuel_id uuid NOT NULL,
    tank_id uuid NOT NULL,
    totalizer numeric(14,3) NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.pump_nozzles OWNER TO kolonk;

--
-- Name: pumps; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.pumps (
    number integer NOT NULL,
    name character varying(64) NOT NULL,
    status character varying(24) NOT NULL,
    driver character varying(32) NOT NULL,
    is_active boolean NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    branch_id uuid,
    position_x integer DEFAULT 0 NOT NULL,
    position_y integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.pumps OWNER TO kolonk;

--
-- Name: purchase_items; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.purchase_items (
    purchase_id uuid NOT NULL,
    product_id uuid NOT NULL,
    qty numeric(12,3) NOT NULL,
    unit_cost numeric(18,6) NOT NULL,
    amount numeric(18,2) NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.purchase_items OWNER TO kolonk;

--
-- Name: purchase_number_seq; Type: SEQUENCE; Schema: public; Owner: kolonk
--

CREATE SEQUENCE public.purchase_number_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.purchase_number_seq OWNER TO kolonk;

--
-- Name: purchases; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.purchases (
    number integer DEFAULT nextval('public.purchase_number_seq'::regclass) NOT NULL,
    supplier_id uuid NOT NULL,
    purchase_date date NOT NULL,
    invoice_no character varying(64),
    subtotal numeric(18,2) NOT NULL,
    vat_amount numeric(18,2) NOT NULL,
    total_gross numeric(18,2) NOT NULL,
    status character varying(16) NOT NULL,
    posted_by uuid,
    posted_at timestamp with time zone,
    ap_invoice_id uuid,
    note text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    branch_id uuid
);


ALTER TABLE public.purchases OWNER TO kolonk;

--
-- Name: refund_items; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.refund_items (
    refund_id uuid NOT NULL,
    sale_item_id uuid NOT NULL,
    qty numeric(12,3) NOT NULL,
    amount numeric(18,2) NOT NULL,
    cogs_amount numeric(18,2) NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.refund_items OWNER TO kolonk;

--
-- Name: refunds; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.refunds (
    sale_id uuid NOT NULL,
    refund_type character varying(16) NOT NULL,
    amount numeric(18,2) NOT NULL,
    vat_amount numeric(18,2) NOT NULL,
    cogs_amount numeric(18,2) NOT NULL,
    reason text,
    restock boolean NOT NULL,
    refund_method character varying(16) NOT NULL,
    status character varying(16) NOT NULL,
    requested_by uuid NOT NULL,
    decided_by uuid,
    decided_at timestamp with time zone,
    decision_note text,
    shift_id uuid,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.refunds OWNER TO kolonk;

--
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.role_permissions (
    role_id uuid NOT NULL,
    permission_id uuid NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.role_permissions OWNER TO kolonk;

--
-- Name: roles; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.roles (
    code character varying(32) NOT NULL,
    name_mn character varying(64) NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.roles OWNER TO kolonk;

--
-- Name: sale_items; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.sale_items (
    sale_id uuid NOT NULL,
    line_no integer NOT NULL,
    item_type character varying(16) NOT NULL,
    fuel_id uuid,
    tank_id uuid,
    pump_id uuid,
    nozzle_id uuid,
    product_id uuid,
    name_snapshot character varying(128) NOT NULL,
    qty numeric(12,3) NOT NULL,
    unit_price numeric(18,2) NOT NULL,
    amount numeric(18,2) NOT NULL,
    unit_cost numeric(18,6) NOT NULL,
    cogs_amount numeric(18,2) NOT NULL,
    refunded_qty numeric(12,3) NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.sale_items OWNER TO kolonk;

--
-- Name: sale_number_seq; Type: SEQUENCE; Schema: public; Owner: kolonk
--

CREATE SEQUENCE public.sale_number_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sale_number_seq OWNER TO kolonk;

--
-- Name: sales; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.sales (
    number bigint DEFAULT nextval('public.sale_number_seq'::regclass) NOT NULL,
    shift_id uuid NOT NULL,
    cashier_id uuid NOT NULL,
    sale_type character varying(16) NOT NULL,
    status character varying(16) NOT NULL,
    subtotal numeric(18,2) NOT NULL,
    vat_amount numeric(18,2) NOT NULL,
    total numeric(18,2) NOT NULL,
    cogs_total numeric(18,2) NOT NULL,
    customer_id uuid,
    contract_id uuid,
    note text,
    completed_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    branch_id uuid
);


ALTER TABLE public.sales OWNER TO kolonk;

--
-- Name: settings; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.settings (
    key character varying(64) NOT NULL,
    value jsonb NOT NULL,
    description character varying(255),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.settings OWNER TO kolonk;

--
-- Name: shift_attachments; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.shift_attachments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    shift_id uuid NOT NULL,
    kind character varying(24) DEFAULT 'open'::character varying NOT NULL,
    ref_id uuid,
    file_name character varying(128) NOT NULL,
    original_name character varying(255) DEFAULT ''::character varying NOT NULL,
    content_type character varying(64) DEFAULT ''::character varying NOT NULL,
    size_bytes integer DEFAULT 0 NOT NULL,
    uploaded_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.shift_attachments OWNER TO kolonk;

--
-- Name: shift_closings; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.shift_closings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    shift_id uuid NOT NULL,
    settlement_vat numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    settlement_novat numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    fuel_total numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    credit_total numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    oil_total numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    fuel_sale_id uuid,
    oil_sale_id uuid,
    note text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    transfer_total numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    approved_by uuid,
    approved_at timestamp with time zone,
    approval_note text
);


ALTER TABLE public.shift_closings OWNER TO kolonk;

--
-- Name: shift_price_marks; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.shift_price_marks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    shift_id uuid NOT NULL,
    nozzle_id uuid NOT NULL,
    reading numeric(14,3) NOT NULL,
    old_price numeric(18,2) DEFAULT '0'::numeric NOT NULL,
    new_price numeric(18,2) NOT NULL,
    note character varying(255),
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.shift_price_marks OWNER TO kolonk;

--
-- Name: shift_tank_levels; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.shift_tank_levels (
    shift_id uuid NOT NULL,
    tank_id uuid NOT NULL,
    phase character varying(8) NOT NULL,
    dip_liters numeric(12,3) NOT NULL,
    book_liters numeric(12,3),
    variance_l numeric(12,3),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.shift_tank_levels OWNER TO kolonk;

--
-- Name: shifts; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.shifts (
    number integer NOT NULL,
    status character varying(16) NOT NULL,
    opened_by uuid NOT NULL,
    closed_by uuid,
    opened_at timestamp with time zone NOT NULL,
    closed_at timestamp with time zone,
    opening_cash numeric(18,2) NOT NULL,
    declared_cash numeric(18,2),
    expected_cash numeric(18,2),
    cash_over_short numeric(18,2),
    note text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    branch_id uuid
);


ALTER TABLE public.shifts OWNER TO kolonk;

--
-- Name: suppliers; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.suppliers (
    name character varying(128) NOT NULL,
    register_no character varying(32),
    phone character varying(32),
    bank_account character varying(64),
    address character varying(255),
    is_active boolean NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.suppliers OWNER TO kolonk;

--
-- Name: sync_outbox; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.sync_outbox (
    aggregate_type character varying(48) NOT NULL,
    aggregate_id uuid NOT NULL,
    event_type character varying(48) NOT NULL,
    payload jsonb NOT NULL,
    processed_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.sync_outbox OWNER TO kolonk;

--
-- Name: tank_movements; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.tank_movements (
    tank_id uuid NOT NULL,
    movement_type character varying(24) NOT NULL,
    liters numeric(12,3) NOT NULL,
    balance_after_l numeric(12,3) NOT NULL,
    unit_cost numeric(18,6) NOT NULL,
    ref_type character varying(32),
    ref_id uuid,
    note character varying(255),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.tank_movements OWNER TO kolonk;

--
-- Name: tanks; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.tanks (
    name character varying(64) NOT NULL,
    fuel_id uuid NOT NULL,
    capacity_l numeric(12,3) NOT NULL,
    current_l numeric(12,3) NOT NULL,
    avg_cost numeric(18,6) NOT NULL,
    min_level_l numeric(12,3) NOT NULL,
    is_active boolean NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    branch_id uuid
);


ALTER TABLE public.tanks OWNER TO kolonk;

--
-- Name: totalizer_readings; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.totalizer_readings (
    nozzle_id uuid NOT NULL,
    shift_id uuid,
    reading numeric(14,3) NOT NULL,
    reading_type character varying(24) NOT NULL,
    recorded_by uuid,
    recorded_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    price_per_liter numeric(18,2)
);


ALTER TABLE public.totalizer_readings OWNER TO kolonk;

--
-- Name: users; Type: TABLE; Schema: public; Owner: kolonk
--

CREATE TABLE public.users (
    username character varying(64) NOT NULL,
    full_name character varying(128) NOT NULL,
    pin_hash character varying(255) NOT NULL,
    role_id uuid NOT NULL,
    phone character varying(32),
    is_active boolean NOT NULL,
    last_login_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    branch_id uuid
);


ALTER TABLE public.users OWNER TO kolonk;

--
-- Data for Name: accounts; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.accounts (code, name_mn, account_type, is_postable, parent_code, sort_order, id, created_at, updated_at) FROM stdin;
1000	Хөрөнгө	asset	f	\N	1000	01a1e698-4aa1-450b-9ebc-9d99a0b1fd99	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
1101	Касс — бэлэн мөнгө	asset	t	1000	1101	fcba0f17-2018-4401-af1c-4ed90cded92d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
1102	Картын гүйлгээний тооцоо	asset	t	1000	1102	07404955-10a0-4d88-aa4a-4853cb1a438b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
1103	QR гүйлгээний тооцоо	asset	t	1000	1103	89be2d9f-ccf7-4b45-b8bd-8af93af46e11	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
1110	Харилцах данс	asset	t	1000	1110	4f29fdad-9929-4bcf-b1a0-9b13278013f7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
1201	Гэрээт худалдан авагчийн авлага	asset	t	1000	1201	68bb2009-974e-417a-95b9-9fc4ea6f5027	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
1205	Ажилтны урьдчилгаа	asset	t	1000	1205	d5cc0a93-4cc1-4571-b240-783b7aae6af1	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
1301	Түлшний бараа материал	asset	t	1000	1301	2307bbb0-53ca-4b6c-ba67-ad2406851886	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
1302	Дэлгүүрийн бараа материал	asset	t	1000	1302	28c7cae2-b69d-4b28-bdc6-408c86e3ebc6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
1402	Орох НӨАТ	asset	t	1000	1402	4cca024f-fd28-48df-bacb-916a75bc54b0	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2000	Өр төлбөр	liability	f	\N	2000	e6683c42-2da5-4afb-88e6-e78e55e1351e	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2101	Нийлүүлэгчийн өглөг	liability	t	2000	2101	ffb233d2-7c30-46bc-988e-1f3fa3c0f5de	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2201	Гарах НӨАТ	liability	t	2000	2201	77e1873c-d318-4e87-a481-a4ed9e4e8288	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2401	Цалингийн өглөг	liability	t	2000	2401	f75af7ce-18aa-4b73-8062-ca8016e1e8dc	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2402	ХХОАТ-ын өглөг	liability	t	2000	2402	7ce618c4-67fb-477d-a0eb-beabf570aca6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2403	НДШ-ийн өглөг	liability	t	2000	2403	23c6ee36-cb5b-4a8a-9dc7-79db3b39d8f9	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
3000	Эздийн өмч	equity	f	\N	3000	eaa9a188-2b76-4f28-bd7f-b47169efddf7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
3101	Эзний оруулсан хөрөнгө	equity	t	3000	3101	29d9edfb-4624-4d49-8b51-9506a963b368	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
3201	Хуримтлагдсан ашиг	equity	t	3000	3201	a9369bef-21fd-4f1d-ad07-40b4fcfe0813	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
4000	Орлого	revenue	f	\N	4000	a0453706-68ac-44dd-bfad-13bee3531865	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
4101	Түлшний борлуулалтын орлого	revenue	t	4000	4101	6fff4f0c-552c-4f48-b16f-5ed3a93def40	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
4102	Барааны борлуулалтын орлого	revenue	t	4000	4102	883c1b37-d2f6-497b-8a43-0f2121838a9f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
4901	Борлуулалтын буцаалт	revenue	t	4000	4901	43674dc2-c583-4fae-9e91-84171fcd5d55	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
4903	Бусад орлого	revenue	t	4000	4903	13119ae8-f178-4aef-b9a7-bdc28abb5000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5000	Зардал	expense	f	\N	5000	3c98fb73-48e4-46e9-86db-35d5e6e9ded0	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5101	Түлшний борлуулалтын өртөг	expense	t	5000	5101	c09562f8-b657-4507-8d31-5e964c8ce856	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5102	Барааны борлуулалтын өртөг	expense	t	5000	5102	836482c1-b0ad-490d-bb04-103d630ad7ea	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5201	Түлшний хорогдол, дутагдал	expense	t	5000	5201	2dd83a4c-532d-4557-9d6e-f64c0f6e0de3	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5301	Цалин хөлс	expense	t	5000	5301	23def7b3-01e2-4bd2-9a44-88f07e93a629	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5302	Нийгмийн даатгалын шимтгэл	expense	t	5000	5302	c897c5ad-c885-477e-8430-dc96c9da1cd3	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5311	Цахилгааны зардал	expense	t	5000	5311	8290e2b9-07ba-4294-9721-7689f9f4c8b6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5312	Ус, дулааны зардал	expense	t	5000	5312	53d110af-db09-4a58-821e-86e352d0cce5	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5313	Холбоо, интернэтийн зардал	expense	t	5000	5313	bed8a701-9f8c-44c1-be3a-287bbb632ad9	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5321	Түрээсийн зардал	expense	t	5000	5321	3ef1d61c-37ae-4a07-a223-7bff5cb948da	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5331	Засвар үйлчилгээний зардал	expense	t	5000	5331	1d9858c7-80d8-452d-8600-c5a82f3af2de	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5341	Тээвэр, шатахууны зардал	expense	t	5000	5341	9b41530e-2b79-49ee-8eb3-6ff91285eec3	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5351	Бичиг хэрэг, аж ахуйн зардал	expense	t	5000	5351	f1812bfd-5d3c-4051-8db6-78c69b566a03	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5361	Зар сурталчилгааны зардал	expense	t	5000	5361	0b782fc9-990d-48f6-8013-9dc5c2f04fe2	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5371	Банкны шимтгэл	expense	t	5000	5371	2e99f235-2f21-4233-bfce-d5b92f515068	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5381	Татвар, хураамж	expense	t	5000	5381	eb37eabd-c6d0-494b-9650-bdad1d3b7e95	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5391	Хамгаалалт, цэвэрлэгээ	expense	t	5000	5391	d3e0690a-9e62-413a-b60e-8cfdfc6d0216	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5401	Элэгдэл, хорогдол	expense	t	5000	5401	4cedac2c-f125-4f6a-871f-3c84d8949c29	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5901	Бусад зардал	expense	t	5000	5901	e35c7964-6a44-41b7-b48e-70d1355ddaf6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
5902	Кассын дутагдал	expense	t	5000	5902	242fcd5d-0313-4b01-900d-9ddb4866938c	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.alembic_version (version_num) FROM stdin;
a2f96e1c47d3
\.


--
-- Data for Name: ap_invoices; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.ap_invoices (supplier_id, invoice_no, invoice_date, due_date, source_type, source_id, amount_gross, amount_paid, status, id, created_at, updated_at) FROM stdin;
d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	NIC-1-0001	2026-08-14	2026-09-13	fuel_receipt	ee0cc1a9-149b-44a8-bc94-390ecde73348	38225000.00	0.00	open	21f54449-4ec3-4de1-ae48-0f82b7190ee3	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	NIC-2-0001	2026-08-14	2026-09-13	fuel_receipt	c7e0cf19-4db2-49f4-83dc-9ccead73b182	31372000.00	0.00	open	a38066d6-c780-40d6-a5a1-921b8a62956c	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	NIC-3-0001	2026-08-14	2026-09-13	fuel_receipt	d95e2d4a-7335-4c63-bd85-8a657f822f37	45628000.00	0.00	open	a10964ef-8f4f-4b38-a097-5cd74a6584cc	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
eebbf51f-69d4-4291-84aa-f23b4845b73e	OPEN-0001	2026-08-15	2026-09-14	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	16315860.00	0.00	open	e107dc4b-99bf-49a4-8219-78bfeb140be7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
\.


--
-- Data for Name: ap_payments; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.ap_payments (ap_invoice_id, supplier_id, amount, paid_from, payment_date, note, created_by, id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: ar_invoices; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.ar_invoices (customer_id, contract_id, invoice_no, period_start, period_end, issued_at, amount, amount_paid, status, lines, id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: ar_payments; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.ar_payments (ar_invoice_id, customer_id, contract_id, amount, received_to, payment_date, note, created_by, id, created_at, updated_at, bank_account_id) FROM stdin;
\N	22277089-5c93-4c72-815c-c19196658f37	636e4521-0375-4557-85c8-74d0187cbaa3	400000.00	bank	2026-08-17	Өдрийн хаалт — шилжүүлэг	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	093f9796-ba1d-43ff-89ff-34a3064664b0	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
\.


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.audit_logs (user_id, action, entity_type, entity_id, before, after, ip, id, created_at, updated_at) FROM stdin;
2703b8d8-048b-4340-bab3-9c882979afd2	fuel_receipt.post	fuel_receipt	ee0cc1a9-149b-44a8-bc94-390ecde73348	{"status": "draft"}	{"liters": "14000.000", "status": "posted", "subtotal": "34750000.00", "vat_amount": "3475000.00", "total_gross": "38225000.00", "ap_invoice_id": "21f54449-4ec3-4de1-ae48-0f82b7190ee3", "tank_avg_cost": "2482.142857", "tank_balance_l": "14000.000", "landed_unit_cost": "2482.142857"}	\N	460e150e-f60f-42de-b5ee-adce3dc32bf3	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2703b8d8-048b-4340-bab3-9c882979afd2	fuel_receipt.post	fuel_receipt	c7e0cf19-4db2-49f4-83dc-9ccead73b182	{"status": "draft"}	{"liters": "10500.000", "status": "posted", "subtotal": "28520000.00", "vat_amount": "2852000.00", "total_gross": "31372000.00", "ap_invoice_id": "a38066d6-c780-40d6-a5a1-921b8a62956c", "tank_avg_cost": "2716.190476", "tank_balance_l": "10500.000", "landed_unit_cost": "2716.190476"}	\N	d3d91aad-eb59-4469-bdfa-a1a3c08dd93f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2703b8d8-048b-4340-bab3-9c882979afd2	fuel_receipt.post	fuel_receipt	d95e2d4a-7335-4c63-bd85-8a657f822f37	{"status": "draft"}	{"liters": "16000.000", "status": "posted", "subtotal": "41480000.00", "vat_amount": "4148000.00", "total_gross": "45628000.00", "ap_invoice_id": "a10964ef-8f4f-4b38-a097-5cd74a6584cc", "tank_avg_cost": "2592.500000", "tank_balance_l": "16000.000", "landed_unit_cost": "2592.500000"}	\N	cae77312-34d7-4ef5-aac0-7b6e523cec87	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2703b8d8-048b-4340-bab3-9c882979afd2	purchase.post	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	{"status": "draft"}	{"status": "posted", "subtotal": "14832600.00", "item_count": 40, "vat_amount": "1483260.00", "total_gross": "16315860.00", "ap_invoice_id": "e107dc4b-99bf-49a4-8219-78bfeb140be7"}	\N	e972992a-b080-4482-a958-e8949bf382f7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2703b8d8-048b-4340-bab3-9c882979afd2	expense.create	expense	32571860-3fb6-4c7f-a60b-6442f6ae92d2	null	{"total": "480000.00", "number": 1, "account_code": "5311", "payment_method": "cash"}	\N	c946b142-93c9-48db-a87f-7498f2524d1a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2703b8d8-048b-4340-bab3-9c882979afd2	expense.create	expense	769c96a0-ad2b-4daf-94ac-cc2baf433f60	null	{"total": "180000.00", "number": 2, "account_code": "5312", "payment_method": "cash"}	\N	211418e3-f529-4cca-b05d-dd8c43e0ed9c	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2703b8d8-048b-4340-bab3-9c882979afd2	expense.create	expense	64806296-2238-4269-8391-e3f861277648	null	{"total": "1500000.00", "number": 3, "account_code": "5321", "payment_method": "bank"}	\N	2dc0c4bd-e09e-43af-b66c-685dda8c6560	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2703b8d8-048b-4340-bab3-9c882979afd2	expense.create	expense	fe0bf502-8ba4-4a8b-bd7d-20b32947eef6	null	{"total": "90000.00", "number": 4, "account_code": "5313", "payment_method": "cash"}	\N	097ea9dc-b23f-4c5b-86bb-93b53f022a33	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	34681e98-ff5e-4218-b015-a64718ad64b1	2026-08-17 04:05:40.067377+08	2026-08-17 04:05:40.067377+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.logout	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	null	172.18.0.1	13de67aa-495d-4475-a429-3cdbc9724c86	2026-08-17 04:06:11.298196+08	2026-08-17 04:06:11.298196+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	172.18.0.1	84b06b6a-07bd-4fd7-b5f5-86d95264633f	2026-08-17 04:07:50.811712+08	2026-08-17 04:07:50.811712+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.logout	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	null	172.18.0.1	00c28ffb-cbb1-442a-b6b9-8e354a3bbb91	2026-08-17 04:07:57.102654+08	2026-08-17 04:07:57.102654+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	172.18.0.1	f5a20352-cf93-47d8-9f22-f0b87204e1e7	2026-08-17 04:20:10.949689+08	2026-08-17 04:20:10.949689+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	172.18.0.1	835ac048-fab0-40c6-9927-14616c0bab61	2026-08-17 04:20:10.94952+08	2026-08-17 04:20:10.94952+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	172.18.0.1	31208bfe-69bf-420d-87f6-468b49a46c84	2026-08-17 10:06:27.150152+08	2026-08-17 10:06:27.150152+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	172.18.0.1	f1ac1462-5081-4d2b-82f6-bc06249f1b89	2026-08-17 10:08:49.162309+08	2026-08-17 10:08:49.162309+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.logout	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	null	172.18.0.1	8c7c35c1-c33b-4cfb-a16c-496923bb233c	2026-08-17 10:15:17.460518+08	2026-08-17 10:15:17.460518+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	172.18.0.1	d7ede37f-7ee2-4566-8482-df33be8fea4a	2026-08-17 10:15:21.278988+08	2026-08-17 10:15:21.278988+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.logout	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	null	172.18.0.1	c770e979-7122-45a9-b917-be2f6703b764	2026-08-17 10:27:16.372503+08	2026-08-17 10:27:16.372503+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	3a1123d7-dad5-418d-a5a5-4371334a88f7	2026-08-17 10:27:23.339867+08	2026-08-17 10:27:23.339867+08
2703b8d8-048b-4340-bab3-9c882979afd2	setting.update	setting	065f9286-1775-4de3-839a-e1a9fed6f9e5	{"key": "pos_sales_enabled", "value": true}	{"key": "pos_sales_enabled", "value": false}	172.18.0.1	9a6a1989-f5c6-4fa8-b8b3-a681f29b6061	2026-08-17 10:27:37.538985+08	2026-08-17 10:27:37.538985+08
2703b8d8-048b-4340-bab3-9c882979afd2	setting.update	setting	6f515ff9-fd04-4e92-877d-9ea59d1bcd6f	{"key": "shift_totalizer_enabled", "value": true}	{"key": "shift_totalizer_enabled", "value": false}	172.18.0.1	5c84e890-24ef-46f6-b733-c3cd875d99d5	2026-08-17 10:27:37.556968+08	2026-08-17 10:27:37.556968+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.logout	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	null	172.18.0.1	6222fb5e-62b2-46b3-892b-9878c4a8b48f	2026-08-17 10:27:41.390104+08	2026-08-17 10:27:41.390104+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	172.18.0.1	7f4a712d-65ac-488e-8d81-e0df7f7446bc	2026-08-17 10:27:44.43592+08	2026-08-17 10:27:44.43592+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	172.18.0.1	3036c0a4-dd9a-4dce-a252-9d5f0d673b03	2026-08-17 10:40:07.318299+08	2026-08-17 10:40:07.318299+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	172.18.0.1	6bc9a2ec-0527-4385-bf77-c91364fb9edd	2026-08-17 10:40:07.318426+08	2026-08-17 10:40:07.318426+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	shift.open	shift	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	null	{"tanks": 0, "number": 1, "nozzles": 7, "opening_cash": "500000.00"}	\N	e043a2d4-7394-4794-ba06-8dc3cd9d6045	2026-08-17 11:03:04.675143+08	2026-08-17 11:03:04.675143+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	shift.attachment	shift	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	null	{"file": "bed7b107f9944429b349610dc6ce5a11.jpg", "kind": "open", "size": 5332854}	\N	321f6fa0-2a24-45d4-8ed8-0d8d22aa5c15	2026-08-17 11:03:04.981582+08	2026-08-17 11:03:04.981582+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	sale.create	sale	9669e532-1cdd-4e15-9f5e-b9e12f9bd17d	null	{"items": 2, "total": "1534000.00", "number": 1, "methods": "contract", "cogs_total": "1299071.43", "vat_amount": "139454.55"}	\N	c6c21bc8-5fc0-4e39-849d-44e650247d8f	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	sale.create	sale	c1a85e9a-5a73-4a70-8691-1f0f90b7098d	null	{"items": 1, "total": "27930000.00", "number": 2, "methods": "card,cash", "cogs_total": "23580357.14", "vat_amount": "2539090.91"}	\N	0fa459c9-326f-4bf1-9482-a67bc34ec380	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	sale.create	sale	02734b52-a7ee-4fcb-9761-0fa713e24137	null	{"items": 1, "total": "42000.00", "number": 3, "methods": "cash", "cogs_total": "29000.00", "vat_amount": "3818.18"}	\N	423a3b45-9f6a-48f9-96f9-1cb257825dd2	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	contract.payment	contract	636e4521-0375-4557-85c8-74d0187cbaa3	{"balance": "1534000.00"}	{"amount": "400000.00", "balance": "1134000.00", "received_to": "bank", "ar_invoice_id": null}	\N	6a70adaa-e85f-45ca-8fef-9aac00297189	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	expense.create	expense	a59b18ae-a327-4e51-bd69-7aa243642096	null	{"total": "10000.00", "number": 5, "account_code": "5341", "payment_method": "cash"}	\N	289f0999-0909-4ea0-8947-6b7142c0e686	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	shift.close	shift	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	{"status": "open", "opening_cash": "500000.00"}	{"note": null, "status": "closed", "declared_cash": "20000.00", "expected_cash": "28372000.00", "cash_over_short": "-28352000.00"}	\N	f17715e1-a760-41a7-9340-d68658107169	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	shift.daily_close	shift	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	null	{"ar_total": "400000.00", "oil_total": "42000.00", "fuel_total": "27930000.00", "settlement": "90000.00", "credit_sales": 1, "credit_total": "1534000.00", "expense_total": "10000.00"}	\N	2a172332-02c6-48a7-a1ac-40bd549bc68e	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	shift.open	shift	2f1934fb-8b7e-4d0c-8de6-286fc9ed2fd0	null	{"tanks": 0, "number": 2, "nozzles": 7, "opening_cash": "0.00"}	\N	e552c563-172a-4118-9064-a92baae78be5	2026-08-17 12:27:33.895302+08	2026-08-17 12:27:33.895302+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.logout	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	null	172.18.0.1	4231c87a-bc2a-4d0b-b620-5c6d315f60e4	2026-08-17 12:40:34.601351+08	2026-08-17 12:40:34.601351+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	85494770-1218-4f43-819c-87de539722c2	2026-08-17 12:40:38.4164+08	2026-08-17 12:40:38.4164+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	75d34bcb-c285-48d9-a399-76848ee5cf26	2026-08-17 12:45:27.964698+08	2026-08-17 12:45:27.964698+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	1cf0dc69-53f2-4da1-a11d-ac042e77ae43	2026-08-17 13:05:07.226703+08	2026-08-17 13:05:07.226703+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	f3ff4657-9385-43ec-9e27-8f1b86034528	2026-08-17 13:05:17.342375+08	2026-08-17 13:05:17.342375+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	fdcb38b2-34ac-4c44-8fb9-686968a0ed63	2026-08-17 13:05:23.041282+08	2026-08-17 13:05:23.041282+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	f42ac437-c812-48ed-a60a-68055d6655db	2026-08-17 13:05:47.851899+08	2026-08-17 13:05:47.851899+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	241c6a4a-3570-48eb-bdb5-7b721051aad2	2026-08-17 13:08:09.11101+08	2026-08-17 13:08:09.11101+08
2703b8d8-048b-4340-bab3-9c882979afd2	shift.closing_approved	shift	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	null	{"note": "??????: ???????", "approved": true}	\N	5584524a-13a3-4574-8ba8-5ca9b8d2f20c	2026-08-17 13:08:09.333737+08	2026-08-17 13:08:09.333737+08
2703b8d8-048b-4340-bab3-9c882979afd2	shift.closing_unapproved	shift	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	null	{"note": null, "approved": false}	\N	cda510f0-615d-45c3-a2f7-b8dd0c8387d6	2026-08-17 13:08:09.506147+08	2026-08-17 13:08:09.506147+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	7051e2d0-2da7-4e53-87b5-d2b51849ff22	2026-08-17 13:08:27.404274+08	2026-08-17 13:08:27.404274+08
2703b8d8-048b-4340-bab3-9c882979afd2	shift.closing_corrected	shift	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	{"declared_cash": "20000.00", "cash_over_short": "-28352000.00"}	{"note": "???? - ???? ??????", "declared_cash": "20000.00", "cash_over_short": "-28352000.00"}	\N	57b98179-e3c7-43ac-bc1e-ec5f1314877f	2026-08-17 13:08:27.623374+08	2026-08-17 13:08:27.623374+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	65e6222e-77c9-4d49-8264-2f3a3eee1f57	2026-08-17 13:13:17.338233+08	2026-08-17 13:13:17.338233+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	e834e1b6-2c9c-4f7d-9a25-b45baedcb0b6	2026-08-17 13:13:17.337963+08	2026-08-17 13:13:17.337963+08
2703b8d8-048b-4340-bab3-9c882979afd2	shift.closing_approved	shift	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	null	{"note": null, "approved": true}	\N	5e377bd0-13b8-434f-bd5f-8bc1826da4d1	2026-08-17 13:14:14.574861+08	2026-08-17 13:14:14.574861+08
2703b8d8-048b-4340-bab3-9c882979afd2	shift.closing_unapproved	shift	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	null	{"note": null, "approved": false}	\N	75356526-1836-48e8-a96d-a6528b9caa49	2026-08-17 13:14:27.170136+08	2026-08-17 13:14:27.170136+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	26599abf-2530-43b2-a492-267059c4b912	2026-08-17 13:19:13.867748+08	2026-08-17 13:19:13.867748+08
2703b8d8-048b-4340-bab3-9c882979afd2	branch.create	branch	1f410c57-800a-4922-afc4-b9d5258cfff3	null	{"code": "02", "name": "Цагаан-Уул салбар"}	\N	f136977f-3b32-4888-b779-82db6a435c86	2026-08-17 16:52:23.043767+08	2026-08-17 16:52:23.043767+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	4a2e4c9b-37a0-46f8-a2c0-29aa23c3bb6f	2026-08-17 17:01:27.864595+08	2026-08-17 17:01:27.864595+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	ea16db5e-e2d2-47f6-b934-8fdb6a10156e	2026-08-17 17:03:52.882823+08	2026-08-17 17:03:52.882823+08
2703b8d8-048b-4340-bab3-9c882979afd2	tank.create	tank	b0c378c1-9d80-459e-8301-78a30c6df789	null	{"name": "40 тн", "fuel_id": "c1d6e693-3f8b-43a4-bc1b-46e9431db264", "avg_cost": "0", "current_l": "0", "is_active": true, "capacity_l": "5600.000", "min_level_l": "500.000"}	172.18.0.6	a9d1278b-0a30-49ef-ba7c-30b9f6b5f13d	2026-08-17 17:16:39.371577+08	2026-08-17 17:16:39.371577+08
2703b8d8-048b-4340-bab3-9c882979afd2	tank.update	tank	b0c378c1-9d80-459e-8301-78a30c6df789	{"name": "40 тн", "fuel_id": "c1d6e693-3f8b-43a4-bc1b-46e9431db264", "avg_cost": "0.000000", "current_l": "0.000", "is_active": true, "capacity_l": "5600.000", "min_level_l": "500.000"}	{"name": "40 тн", "fuel_id": "c1d6e693-3f8b-43a4-bc1b-46e9431db264", "avg_cost": "0.000000", "current_l": "0.000", "is_active": true, "capacity_l": "40000.000", "min_level_l": "500.000"}	172.18.0.6	ddbfb7d6-dec4-45f4-bff8-8a5d44e836f0	2026-08-17 17:17:29.818459+08	2026-08-17 17:17:29.818459+08
2703b8d8-048b-4340-bab3-9c882979afd2	tank.create	tank	c77bbf42-fd34-4f0e-8199-ec3cb27f3ceb	null	{"name": "30 тн", "fuel_id": "49fd9163-cbef-463e-89bf-a382f6769767", "avg_cost": "0", "current_l": "0", "is_active": true, "capacity_l": "30000.000", "min_level_l": "500.000"}	172.18.0.6	b6a3aa15-0025-4774-9e53-93b1e0a2d49f	2026-08-17 17:17:51.050351+08	2026-08-17 17:17:51.050351+08
2703b8d8-048b-4340-bab3-9c882979afd2	pump.create	pump	63364f53-5598-4ec4-814a-d0f97f89c28b	null	{"name": "А92", "driver": "simulated", "number": 1, "status": "idle", "position": "0,0", "branch_id": "1f410c57-800a-4922-afc4-b9d5258cfff3", "is_active": true}	172.18.0.6	534b09a0-70d7-4448-afed-06e21bd71580	2026-08-17 17:18:06.225735+08	2026-08-17 17:18:06.225735+08
2703b8d8-048b-4340-bab3-9c882979afd2	nozzle.create	pump_nozzle	5071301b-3e2d-498d-83b7-bf6fe0d8e350	null	{"fuel_id": "c1d6e693-3f8b-43a4-bc1b-46e9431db264", "pump_id": "63364f53-5598-4ec4-814a-d0f97f89c28b", "tank_id": "b0c378c1-9d80-459e-8301-78a30c6df789", "totalizer": "0.000", "nozzle_number": 1}	172.18.0.6	d0af9444-478d-4f4d-8f81-6fc25fa538f6	2026-08-17 17:18:15.280358+08	2026-08-17 17:18:15.280358+08
2703b8d8-048b-4340-bab3-9c882979afd2	pump.create	pump	29db29eb-0fbf-473a-b20f-1e572e27aa3f	null	{"name": "ТА", "driver": "simulated", "number": 2, "status": "idle", "position": "2,0", "branch_id": "1f410c57-800a-4922-afc4-b9d5258cfff3", "is_active": true}	172.18.0.6	120f03f6-ce05-4748-a2fc-f592f7dd3541	2026-08-17 17:19:19.614859+08	2026-08-17 17:19:19.614859+08
2703b8d8-048b-4340-bab3-9c882979afd2	nozzle.create	pump_nozzle	1a1b751b-833e-4627-9f55-a4da70db023a	null	{"fuel_id": "49fd9163-cbef-463e-89bf-a382f6769767", "pump_id": "29db29eb-0fbf-473a-b20f-1e572e27aa3f", "tank_id": "c77bbf42-fd34-4f0e-8199-ec3cb27f3ceb", "totalizer": "0.000", "nozzle_number": 1}	172.18.0.6	7fdc8094-8c6c-4d94-8277-93cc98c50fc1	2026-08-17 17:19:28.783345+08	2026-08-17 17:19:28.783345+08
2703b8d8-048b-4340-bab3-9c882979afd2	branch.payment_methods	branch	1f410c57-800a-4922-afc4-b9d5258cfff3	{"methods": "['cash', 'card', 'qr', 'transfer', 'contract', 'voucher', 'prepaid']"}	{"methods": "['cash', 'card', 'transfer', 'contract']"}	\N	e8d2ad54-2c83-4c97-bfcc-6a989ef3405c	2026-08-17 17:19:42.093581+08	2026-08-17 17:19:42.093581+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	48c10967-79a8-4816-8178-a4ccffff3a44	2026-08-17 19:39:03.209537+08	2026-08-17 19:39:03.209537+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	55a75088-3478-4fce-887d-a8ff01fd9711	2026-08-17 19:39:38.392029+08	2026-08-17 19:39:38.392029+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	44c33f34-65ab-42e6-ab0f-4327944d74ca	2026-08-17 19:48:10.924148+08	2026-08-17 19:48:10.924148+08
2703b8d8-048b-4340-bab3-9c882979afd2	setting.update	setting	065f9286-1775-4de3-839a-e1a9fed6f9e5	{"key": "pos_sales_enabled", "value": false}	{"key": "pos_sales_enabled", "value": true}	172.18.0.1	8296ddc0-4252-4a1f-bfb4-ee9853c79a9e	2026-08-17 20:08:31.78076+08	2026-08-17 20:08:31.78076+08
2703b8d8-048b-4340-bab3-9c882979afd2	setting.update	setting	065f9286-1775-4de3-839a-e1a9fed6f9e5	{"key": "pos_sales_enabled", "value": true}	{"key": "pos_sales_enabled", "value": false}	172.18.0.1	c79076fa-e82e-4842-a87e-3d3c1a68776c	2026-08-17 20:08:45.316297+08	2026-08-17 20:08:45.316297+08
2703b8d8-048b-4340-bab3-9c882979afd2	setting.update	setting	065f9286-1775-4de3-839a-e1a9fed6f9e5	{"key": "pos_sales_enabled", "value": false}	{"key": "pos_sales_enabled", "value": true}	172.18.0.1	2b4d9a12-4467-44a5-a4b6-986aa177c642	2026-08-17 23:34:53.009576+08	2026-08-17 23:34:53.009576+08
2703b8d8-048b-4340-bab3-9c882979afd2	setting.update	setting	065f9286-1775-4de3-839a-e1a9fed6f9e5	{"key": "pos_sales_enabled", "value": true}	{"key": "pos_sales_enabled", "value": false}	172.18.0.1	d4e7683f-e3f3-4864-a08f-050710fefa61	2026-08-17 23:35:13.543376+08	2026-08-17 23:35:13.543376+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	172.18.0.1	b8bcef08-3d25-4b9f-9b5d-59d0ea4673a9	2026-08-18 00:40:39.087408+08	2026-08-18 00:40:39.087408+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.logout	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	null	172.18.0.1	a78507fb-384f-4061-87f1-d4e755b90fed	2026-08-18 00:40:57.77584+08	2026-08-18 00:40:57.77584+08
51d10ad8-c589-4ade-8292-b0e48351819d	auth.login	user	51d10ad8-c589-4ade-8292-b0e48351819d	null	{"role": "cashier", "username": "tuya"}	172.18.0.1	44a7f8eb-196e-461e-a7d8-7f1163b60cfa	2026-08-18 00:41:01.40007+08	2026-08-18 00:41:01.40007+08
51d10ad8-c589-4ade-8292-b0e48351819d	auth.login	user	51d10ad8-c589-4ade-8292-b0e48351819d	null	{"role": "cashier", "username": "tuya"}	172.18.0.1	91a6a08f-68bd-4623-9d92-27109abf979a	2026-08-18 00:48:30.273669+08	2026-08-18 00:48:30.273669+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	172.18.0.1	2eca763b-9f7f-428f-bbfb-4bea2fcd0886	2026-08-18 00:50:38.379496+08	2026-08-18 00:50:38.379496+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	172.18.0.1	0da4d03c-4b2a-4fcd-a2a8-029ae34149ce	2026-08-18 00:56:31.377478+08	2026-08-18 00:56:31.377478+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.logout	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	null	172.18.0.1	555b290b-6a70-41b3-a3a9-8f970b1ad0c1	2026-08-18 00:56:32.826944+08	2026-08-18 00:56:32.826944+08
51d10ad8-c589-4ade-8292-b0e48351819d	auth.login	user	51d10ad8-c589-4ade-8292-b0e48351819d	null	{"role": "cashier", "username": "tuya"}	172.18.0.1	907fef73-97d2-4104-8253-d13dbc5ec76c	2026-08-18 00:56:34.932748+08	2026-08-18 00:56:34.932748+08
51d10ad8-c589-4ade-8292-b0e48351819d	auth.logout	user	51d10ad8-c589-4ade-8292-b0e48351819d	null	null	172.18.0.1	26914400-a030-4b6c-aa4a-50036d1ce5e5	2026-08-18 00:56:47.604528+08	2026-08-18 00:56:47.604528+08
51d10ad8-c589-4ade-8292-b0e48351819d	auth.login	user	51d10ad8-c589-4ade-8292-b0e48351819d	null	{"role": "cashier", "username": "tuya"}	172.18.0.1	98850199-ce52-4f6a-a189-ec10c6f11027	2026-08-18 00:56:52.150883+08	2026-08-18 00:56:52.150883+08
51d10ad8-c589-4ade-8292-b0e48351819d	auth.logout	user	51d10ad8-c589-4ade-8292-b0e48351819d	null	null	172.18.0.1	62d44fe4-f8dc-4a9d-821f-0d3b3d7d7a73	2026-08-18 00:56:59.04194+08	2026-08-18 00:56:59.04194+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	172.18.0.1	f9c0b00a-4461-4f37-90db-c85da3acb679	2026-08-18 01:09:20.767295+08	2026-08-18 01:09:20.767295+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	2405:5700:310:d895:1478:587d:4a72:1c02	3249c59c-bd85-4700-aa75-eef35d1908e0	2026-08-18 02:02:12.040133+08	2026-08-18 02:02:12.040133+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	2405:5700:310:d895:2565:cb9e:f274:1a3e	34623453-71d4-4f06-a74d-19428d5a90d8	2026-08-18 02:02:52.854187+08	2026-08-18 02:02:52.854187+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.logout	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	null	2405:5700:310:d895:1478:587d:4a72:1c02	bf01a713-b36f-43cc-8432-d6832a4dcb18	2026-08-18 02:05:56.265681+08	2026-08-18 02:05:56.265681+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	2405:5700:310:d895:347c:af3b:3e0b:c753	d90a76ee-56d1-4ff9-b6d9-738b6594ac27	2026-08-18 03:58:38.544879+08	2026-08-18 03:58:38.544879+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	2405:5700:310:d895:347c:af3b:3e0b:c753	c6d9d624-6185-49dd-8beb-575519c1cc1e	2026-08-18 04:53:48.04864+08	2026-08-18 04:53:48.04864+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.logout	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	null	2405:5700:310:d895:347c:af3b:3e0b:c753	fbf970df-8f09-4cb9-93ce-b5d0066e451b	2026-08-18 04:54:05.977465+08	2026-08-18 04:54:05.977465+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	2405:5700:310:d895:dfec:17b2:cae:a66	b30ab452-ea7c-41e4-bd6e-a90c48a283b3	2026-08-18 10:22:10.094442+08	2026-08-18 10:22:10.094442+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.logout	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	null	2405:5700:310:d895:dfec:17b2:cae:a66	1185b00e-a2d5-4bdc-a8ef-bf55cd15299b	2026-08-18 10:22:42.921174+08	2026-08-18 10:22:42.921174+08
51d10ad8-c589-4ade-8292-b0e48351819d	auth.login	user	51d10ad8-c589-4ade-8292-b0e48351819d	null	{"role": "cashier", "username": "tuya"}	2405:5700:310:d895:dfec:17b2:cae:a66	5638df0b-7422-4262-ba82-bb23b3c63670	2026-08-18 10:22:45.391752+08	2026-08-18 10:22:45.391752+08
51d10ad8-c589-4ade-8292-b0e48351819d	auth.logout	user	51d10ad8-c589-4ade-8292-b0e48351819d	null	null	2405:5700:310:d895:dfec:17b2:cae:a66	4d0694c2-b31f-4668-abe4-13988ed75711	2026-08-18 10:23:43.358051+08	2026-08-18 10:23:43.358051+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	2405:5700:310:d895:347c:af3b:3e0b:c753	5ee7f51c-91af-4f30-b0fe-be636f955af4	2026-08-18 10:28:43.920304+08	2026-08-18 10:28:43.920304+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	2405:5700:310:d895:347c:af3b:3e0b:c753	fc01787c-5135-4cf0-893f-33ffae7b2b50	2026-08-18 10:33:19.660206+08	2026-08-18 10:33:19.660206+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.login	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	{"role": "cashier", "username": "dorj"}	2405:5700:310:d895:347c:af3b:3e0b:c753	3348f851-c92c-4b3c-af16-3d0814ed3e99	2026-08-18 10:48:40.716962+08	2026-08-18 10:48:40.716962+08
daf81bad-2f51-4c92-9c7f-a43a9b882f5d	auth.logout	user	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	null	null	2405:5700:310:d895:347c:af3b:3e0b:c753	ce835194-1b70-4a17-84db-aac63f98d653	2026-08-18 10:49:07.860899+08	2026-08-18 10:49:07.860899+08
4fa3b753-2c30-43f4-96ab-9601dc29172c	auth.login	user	4fa3b753-2c30-43f4-96ab-9601dc29172c	null	{"role": "manager", "username": "saraa"}	2405:5700:310:d895:347c:af3b:3e0b:c753	361f9f6e-4dc0-426d-95b8-33cdf6e75993	2026-08-18 10:49:10.537258+08	2026-08-18 10:49:10.537258+08
4fa3b753-2c30-43f4-96ab-9601dc29172c	auth.logout	user	4fa3b753-2c30-43f4-96ab-9601dc29172c	null	null	2405:5700:310:d895:347c:af3b:3e0b:c753	ac699aa6-b313-409c-8ec2-2bdec2fdcfe8	2026-08-18 11:40:51.653547+08	2026-08-18 11:40:51.653547+08
2703b8d8-048b-4340-bab3-9c882979afd2	auth.login	user	2703b8d8-048b-4340-bab3-9c882979afd2	null	{"role": "owner", "username": "bold"}	2405:5700:310:d895:347c:af3b:3e0b:c753	d0665646-2da5-47c2-b19d-9ac98862dd13	2026-08-18 11:40:54.357656+08	2026-08-18 11:40:54.357656+08
\.


--
-- Data for Name: bank_accounts; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.bank_accounts (id, branch_id, bank_name, account_number, holder_name, currency, opening_balance, is_fee_default, is_active, note, sort_order, created_at, updated_at) FROM stdin;
44cb5db8-c88e-4dd1-9b70-196fc74e2f3b	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	Хаан банк	5301234567	Колонк ХХК	MNT	25000000.00	t	t	\N	0	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
fe5e438e-4559-44b4-85bb-5bc1b1263514	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	Голомт банк	1105001234	Колонк ХХК	MNT	8000000.00	f	t	\N	1	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
\.


--
-- Data for Name: bank_statement_config; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.bank_statement_config (id, settlement_customer_id, settlement_contract_id, settlement_description, fee_account_code, fee_description, created_at, updated_at) FROM stdin;
ecb5a2e6-14b7-4611-8d80-6c7528204934	\N	\N	ПОС орлого	\N	Банкны шимтгэл	2026-08-17 12:42:13.583247+08	2026-08-17 12:42:13.583247+08
\.


--
-- Data for Name: bank_statements; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.bank_statements (id, account_number, currency, date_from, date_to, filename, uploaded_by, bank_account_id, fee_expense_id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: bank_transactions; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.bank_transactions (id, statement_id, txn_date, debit, credit, bank_description, bank_counterpart, is_fee, description, customer_id, contract_id, expense_account_code, ar_payment_id, expense_id, posted_at, sort_order, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: branch_payment_methods; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.branch_payment_methods (id, branch_id, method, is_enabled, sort_order, created_at, updated_at) FROM stdin;
348f13be-e4ba-4b3f-b4a7-8b8ba32cab93	1f410c57-800a-4922-afc4-b9d5258cfff3	cash	t	0	2026-08-17 17:19:42.093581+08	2026-08-17 17:19:42.093581+08
b27bcaa8-4095-4f0b-8a38-fa07237f111e	1f410c57-800a-4922-afc4-b9d5258cfff3	card	t	1	2026-08-17 17:19:42.093581+08	2026-08-17 17:19:42.093581+08
ed335fa8-12d1-4d27-b1dd-2099eec31148	1f410c57-800a-4922-afc4-b9d5258cfff3	qr	f	2	2026-08-17 17:19:42.093581+08	2026-08-17 17:19:42.093581+08
9e53ed0d-301f-4ab0-9fd9-c4ed5f6eeeac	1f410c57-800a-4922-afc4-b9d5258cfff3	transfer	t	3	2026-08-17 17:19:42.093581+08	2026-08-17 17:19:42.093581+08
d4cfbc06-6af6-4a90-b0f3-94807db460f2	1f410c57-800a-4922-afc4-b9d5258cfff3	contract	t	4	2026-08-17 17:19:42.093581+08	2026-08-17 17:19:42.093581+08
075ff419-433e-43f0-a459-8b21f55ee226	1f410c57-800a-4922-afc4-b9d5258cfff3	voucher	f	5	2026-08-17 17:19:42.093581+08	2026-08-17 17:19:42.093581+08
3bc58e5a-b19c-44ab-9c1d-0604998564d6	1f410c57-800a-4922-afc4-b9d5258cfff3	prepaid	f	6	2026-08-17 17:19:42.093581+08	2026-08-17 17:19:42.093581+08
\.


--
-- Data for Name: branch_prices; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.branch_prices (id, branch_id, fuel_id, product_id, price, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: branches; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.branches (code, name, address, phone, manager_id, is_active, sort_order, id, created_at, updated_at) FROM stdin;
01	Төв салбар	\N	\N	\N	t	1	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
02	Цагаан-Уул салбар	\N	\N	\N	t	0	1f410c57-800a-4922-afc4-b9d5258cfff3	2026-08-17 16:52:23.043767+08	2026-08-17 16:52:23.043767+08
\.


--
-- Data for Name: contracts; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.contracts (customer_id, contract_no, credit_limit, balance, price_discount_per_l, billing_day, status, id, created_at, updated_at) FROM stdin;
4622797e-9004-480a-9007-d15a159f32b8	GR-002	25000000.00	0.00	40.00	1	active	15ee61c9-f627-4bcf-96aa-b9e35e4147a4	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
ec191b98-fc8e-4eaf-9032-a91ae894e6bf	GR-003	8000000.00	0.00	40.00	1	active	563bd6c7-ee92-44ec-be6f-7d06b95b2da1	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
22277089-5c93-4c72-815c-c19196658f37	GR-001	15000000.00	1134000.00	40.00	1	active	636e4521-0375-4557-85c8-74d0187cbaa3	2026-08-17 03:57:57.461784+08	2026-08-17 12:00:01.452484+08
\.


--
-- Data for Name: customers; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.customers (name, register_no, phone, email, type, is_active, id, created_at, updated_at, last_name, phone2, province, district, credit_limit, contract_file) FROM stdin;
Тээвэр Транс ХХК	2812345	9911-2233	\N	b2b	t	22277089-5c93-4c72-815c-c19196658f37	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N	\N	\N	\N	0.00	\N
Барилга Констракшн ХХК	2823456	9911-4455	\N	b2b	t	4622797e-9004-480a-9007-d15a159f32b8	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N	\N	\N	\N	0.00	\N
Такси Сервис ХХК	2834567	9911-6677	\N	b2b	t	ec191b98-fc8e-4eaf-9032-a91ae894e6bf	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N	\N	\N	\N	0.00	\N
\.


--
-- Data for Name: ebarimt_queue; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.ebarimt_queue (sale_id, status, attempt_count, last_error, receipt_id, qr_data, lottery_no, sent_at, id, created_at, updated_at) FROM stdin;
9669e532-1cdd-4e15-9f5e-b9e12f9bd17d	pending	0	\N	\N	\N	\N	\N	5509b9aa-04f5-45b5-ad3b-9187c3bdc46e	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
c1a85e9a-5a73-4a70-8691-1f0f90b7098d	pending	0	\N	\N	\N	\N	\N	c971314c-974c-47f5-a2e4-92aea354c850	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
02734b52-a7ee-4fcb-9761-0fa713e24137	pending	0	\N	\N	\N	\N	\N	9b65ef10-d2b4-4f1d-b800-69e2b0a5e74f	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
\.


--
-- Data for Name: employee_advances; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.employee_advances (employee_id, advance_date, amount, paid_from, note, created_by, id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: employees; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.employees (full_name, register_no, social_no, "position", phone, bank_account, base_salary, hire_date, end_date, is_active, user_id, note, id, created_at, updated_at, branch_id, si_enabled) FROM stdin;
Батбаяр	\N	\N	Ахлах түгээгч	\N	\N	1800000.00	\N	\N	t	\N	\N	cd0b3c16-7894-40ce-a83b-2d9d2ed91069	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	t
Оюунаа	\N	\N	Түгээгч	\N	\N	1500000.00	\N	\N	t	\N	\N	9f6acc09-76dc-43d0-aa74-58c24d979369	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	t
Ганбат	\N	\N	Түгээгч	\N	\N	1350000.00	\N	\N	t	\N	\N	41f2340d-a731-4dc4-b3fc-4a38fd8b99df	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	t
Цэцэгмаа	\N	\N	Нягтлан	\N	\N	2200000.00	\N	\N	t	\N	\N	752093b7-ea81-458b-945b-737f47f6a39a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	t
Дэлгэрмаа	\N	\N	Цэвэрлэгч	\N	\N	900000.00	\N	\N	t	\N	\N	b6bb3915-b92d-414b-bef9-9e49543da40e	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	t
\.


--
-- Data for Name: expenses; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.expenses (number, expense_date, account_code, payment_method, subtotal, vat_amount, total, supplier_id, ap_invoice_id, shift_id, invoice_no, description, status, created_by, posted_by, posted_at, id, created_at, updated_at, branch_id, bank_account_id) FROM stdin;
1	2026-08-17	5311	cash	436363.64	43636.36	480000.00	\N	\N	\N	\N	Цахилгааны төлбөр	posted	2703b8d8-048b-4340-bab3-9c882979afd2	2703b8d8-048b-4340-bab3-9c882979afd2	2026-08-17 03:57:58.859311+08	32571860-3fb6-4c7f-a60b-6442f6ae92d2	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	\N
2	2026-08-17	5312	cash	163636.36	16363.64	180000.00	\N	\N	\N	\N	Ус, дулаан	posted	2703b8d8-048b-4340-bab3-9c882979afd2	2703b8d8-048b-4340-bab3-9c882979afd2	2026-08-17 03:57:58.865045+08	769c96a0-ad2b-4daf-94ac-cc2baf433f60	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	\N
3	2026-08-17	5321	bank	1363636.36	136363.64	1500000.00	\N	\N	\N	\N	Талбайн түрээс	posted	2703b8d8-048b-4340-bab3-9c882979afd2	2703b8d8-048b-4340-bab3-9c882979afd2	2026-08-17 03:57:58.87016+08	64806296-2238-4269-8391-e3f861277648	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	\N
4	2026-08-17	5313	cash	81818.18	8181.82	90000.00	\N	\N	\N	\N	Интернэт, утас	posted	2703b8d8-048b-4340-bab3-9c882979afd2	2703b8d8-048b-4340-bab3-9c882979afd2	2026-08-17 03:57:58.876407+08	fe0bf502-8ba4-4a8b-bd7d-20b32947eef6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	\N
5	2026-08-17	5341	cash	10000.00	0.00	10000.00	\N	\N	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	\N	75888	posted	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:00:01.625852+08	a59b18ae-a327-4e51-bd69-7aa243642096	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N	\N
\.


--
-- Data for Name: fuel_receipts; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.fuel_receipts (number, supplier_id, tank_id, fuel_id, receipt_date, invoice_no, liters, unit_cost, freight_cost, density, temperature_c, subtotal, vat_amount, total_gross, landed_unit_cost, status, posted_by, posted_at, ap_invoice_id, note, id, created_at, updated_at) FROM stdin;
1	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	e77a6891-1f46-418f-9b0e-cc8192efc8d8	c1d6e693-3f8b-43a4-bc1b-46e9431db264	2026-08-14	NIC-1-0001	14000.000	2450.000000	450000.00	\N	\N	34750000.00	3475000.00	38225000.00	2482.142857	posted	2703b8d8-048b-4340-bab3-9c882979afd2	2026-08-17 03:57:58.610944+08	21f54449-4ec3-4de1-ae48-0f82b7190ee3	\N	ee0cc1a9-149b-44a8-bc94-390ecde73348	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	43a5b093-914f-4d5f-8869-1545cccd0c29	23a852ce-0998-4bac-b7f5-47f66cb855eb	2026-08-14	NIC-2-0001	10500.000	2680.000000	380000.00	\N	\N	28520000.00	2852000.00	31372000.00	2716.190476	posted	2703b8d8-048b-4340-bab3-9c882979afd2	2026-08-17 03:57:58.622144+08	a38066d6-c780-40d6-a5a1-921b8a62956c	\N	c7e0cf19-4db2-49f4-83dc-9ccead73b182	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
3	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	8f351557-542e-4c7f-86c4-e011cdde4516	49fd9163-cbef-463e-89bf-a382f6769767	2026-08-14	NIC-3-0001	16000.000	2560.000000	520000.00	\N	\N	41480000.00	4148000.00	45628000.00	2592.500000	posted	2703b8d8-048b-4340-bab3-9c882979afd2	2026-08-17 03:57:58.630288+08	a10964ef-8f4f-4b38-a097-5cd74a6584cc	\N	d95e2d4a-7335-4c63-bd85-8a657f822f37	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
\.


--
-- Data for Name: fuels; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.fuels (code, name_mn, price_per_liter, color_hex, sort_order, is_active, id, created_at, updated_at) FROM stdin;
AI92	АИ-92	2940.00	#10B981	1	t	c1d6e693-3f8b-43a4-bc1b-46e9431db264	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
AI95	АИ-95	3180.00	#2563EB	2	t	23a852ce-0998-4bac-b7f5-47f66cb855eb	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
DT	Дизель	3050.00	#F59E0B	3	t	49fd9163-cbef-463e-89bf-a382f6769767	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
\.


--
-- Data for Name: inventory_transactions; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.inventory_transactions (product_id, tx_type, qty, unit_cost, balance_after, ref_type, ref_id, note, id, created_at, updated_at, branch_id) FROM stdin;
4205ad35-3737-4eaf-9616-c576082f6b0a	purchase	24.000	58000.000000	24.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	482b2b1a-0c6d-4487-9081-06720a02f28a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
03d8206e-0ddd-4809-bedc-339b7cd5fcd3	purchase	30.000	53000.000000	30.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	103522d4-ada7-4c78-96d8-b899dee10031	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
601f3fd1-ecf1-40c9-a6ff-b92c26fd32e6	purchase	48.000	15500.000000	48.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	54fca8d7-1dbe-4e31-af46-899c6c8010d0	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
fd5fabc8-c097-4d63-aaf5-80750ac08591	purchase	20.000	18000.000000	20.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	1c0217c0-5f46-44d6-a665-ae589e589949	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
8d346bf0-da65-4362-a486-103422de94c2	purchase	18.000	13000.000000	18.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	4b03f398-c137-43c1-949a-58247be8cef5	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
6df82dc1-1c2f-4fb3-880a-2f7154f9d063	purchase	25.000	11000.000000	25.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	e33ff77b-fc4d-4743-ac43-40bd533dd97e	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
e0da3098-6a08-4dc5-95f4-46128fae6806	purchase	22.000	29000.000000	22.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	9c774adc-536d-4b80-9134-a5bd3558aa57	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
714e4437-a3ad-44ea-bb50-c904386d9c82	purchase	16.000	31000.000000	16.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	2403c732-94c1-4076-968c-6d786e3c1083	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
d9b0db4b-0c9a-43d8-88aa-fa4966a8d4d9	purchase	35.000	8500.000000	35.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	38863795-d6f1-4233-a651-21cd620b0a3f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
e421bb83-b6bc-4557-82f6-f2a5618129ce	purchase	40.000	10000.000000	40.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	3323b4b6-3796-4c3b-81cf-a968383914ff	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
252150ac-5039-4e84-b958-b2a9d32c04fc	purchase	6.000	225000.000000	6.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	0205bf95-681a-4e6a-b23f-78c3632246ea	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
3859b7ec-0e00-47cd-b5d7-855ce57a5b40	purchase	4.000	280000.000000	4.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	74688937-3234-4d6d-8686-5b4fecdeb521	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
e59acdf4-66d3-4d04-b22d-19bcaf57d447	purchase	30.000	7000.000000	30.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	e1bbb1af-297a-4f75-9512-c80be3096efe	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
5fd54064-dd7b-4480-8b16-4e870cb04a49	purchase	24.000	11000.000000	24.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	e3d0932e-951b-4b4d-a43c-956def5e200f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
c135c570-7a28-49a8-a528-f23b6eea64ac	purchase	120.000	900.000000	120.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	610bdb75-f87d-4f78-845f-2cd777d345c4	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
36842f30-734f-421b-b0f8-123ce58e6f8a	purchase	80.000	1600.000000	80.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	9eb3f400-c4ec-4cd8-819d-f83b5d7160a4	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
b5e0a9e1-5543-425b-bd00-7d62bb4ae1e8	purchase	96.000	2100.000000	96.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	202143d9-43c1-4d32-bf39-382d42733256	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
0e9d5f69-7d29-49c4-a11d-062ba7422c99	purchase	72.000	2100.000000	72.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	056b6151-7435-4e2f-9678-0eab9abc04f7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
a96c713f-6526-4297-9e17-af7bdc32744c	purchase	48.000	3800.000000	48.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	bf3b1920-fd88-4502-8fbc-568c37c06665	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
9c8fdd62-19a6-48bb-8359-3006f60d242c	purchase	60.000	2200.000000	60.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	a4fa8f91-fd62-49a9-b559-c45650158866	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
50d04e7e-8304-4a4e-8245-aaf3554d0629	purchase	36.000	4500.000000	36.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	2e3ab9fe-120b-424d-b07b-852f781b8daa	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
adb7e52f-6904-46cc-80bf-3521f787d2f6	purchase	60.000	3000.000000	60.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	d431bddc-e42e-463a-b240-179d042301c1	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
b5d63389-fbc4-4a30-bfbd-884a4493f80d	purchase	50.000	2300.000000	50.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	16bbbf37-5bbb-4088-b6d6-8dd338787278	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
39ae8b3c-09d1-4812-82b9-9cc529dc1cbf	purchase	45.000	3400.000000	45.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	bf7071b7-8eed-4d23-becf-21805a9489fe	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
3583bd45-3f4a-4b9c-973b-7769277755d1	purchase	30.000	5500.000000	30.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	7e6476ac-d945-4adb-9d28-507288bdd032	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
cbe4ec5f-4b93-432e-b0c9-81615c5dade1	purchase	80.000	1200.000000	80.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	cc763926-90e5-431e-ae47-626d2d1c6143	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
4fd12e88-8927-429d-ae1c-f0ff508feb1f	purchase	20.000	2000.000000	20.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	1165bb19-b98f-468b-9a90-30024110409d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
f6134a7c-af69-477f-8535-3d2a7ad98f35	purchase	50.000	8000.000000	50.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	45e09e84-19af-4d9f-a975-c6cae1ffe29f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
c1d58096-45a1-44e5-85f6-0040f634313d	purchase	40.000	7100.000000	40.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	d55aee1e-45f2-4042-bd3e-fea81731dd2a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
a68aad98-5af3-4ce7-b1c0-c49ba2c12a16	purchase	35.000	7500.000000	35.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	01551e15-c263-4758-82bf-bea5c0f5ad23	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
1aa68dba-e777-4d64-b4e2-9b1be2980f79	purchase	15.000	16000.000000	15.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	7158e530-4113-4972-93f9-132c2401c282	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
35fab42d-9792-412e-88e2-d30112757f12	purchase	5.000	98000.000000	5.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	a3d23794-83ef-428e-bc84-32e1a89a9716	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
cf458ed4-1a3f-42ba-af59-bece34408933	purchase	10.000	33000.000000	10.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	a24dbddc-b7ac-4113-b2fd-66f0c876378a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
cfc4d796-2177-4106-9cee-5ddfef157906	purchase	8.000	62000.000000	8.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	651bbaa3-fab7-4e29-a64c-da51b2259e54	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
d99fadd9-9f9b-4730-8fec-56df3776ddcd	purchase	12.000	14000.000000	12.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	90cb4992-9a15-4e54-a5a9-1b2c835a0b7d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
266fe348-d6f0-4083-83ae-dff3e8679bc5	purchase	40.000	3800.000000	40.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	bc2d78f3-cc8a-47ed-8cf7-8e54eefe05eb	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
21635e50-b235-489e-bc6c-f67cde6aeab8	purchase	60.000	2500.000000	60.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	303367da-5195-47a6-87a6-9a820dbf0dc5	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
47a733fd-b7dc-472c-b2ce-4e96edf207c4	purchase	20.000	12000.000000	20.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	ec252cd7-abf0-4373-8d8b-76ed9730a25b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
96996409-5f2a-4770-bac1-abdf2113211e	purchase	14.000	18500.000000	14.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	b9211c00-735b-4950-9c61-b5c18cc3c582	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
d8f3bc7f-4b11-4c43-8cfe-be16f6af95cc	purchase	18.000	9800.000000	18.000	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	\N	53012fe2-612f-4dfd-8306-ea6ec4de1914	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
e0da3098-6a08-4dc5-95f4-46128fae6806	sale	-2.000	29000.000000	20.000	sale	9669e532-1cdd-4e15-9f5e-b9e12f9bd17d	\N	ae5d378e-2da9-433c-bfce-2bee718dbb0d	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
e0da3098-6a08-4dc5-95f4-46128fae6806	sale	-1.000	29000.000000	19.000	sale	02734b52-a7ee-4fcb-9761-0fa713e24137	\N	04d935af-cf08-4acd-b860-42946b23be25	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
\.


--
-- Data for Name: journal_entries; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.journal_entries (entry_no, entry_date, description, source_type, source_id, event_type, posted_by, id, created_at, updated_at) FROM stdin;
1	2026-08-14	Шатахуун таталт №1 — НИК ХХК	fuel_receipt	ee0cc1a9-149b-44a8-bc94-390ecde73348	FUEL_RECEIPT_POSTED	2703b8d8-048b-4340-bab3-9c882979afd2	6e3871ab-442f-4745-b9d9-c592875e7758	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2	2026-08-14	Шатахуун таталт №2 — НИК ХХК	fuel_receipt	c7e0cf19-4db2-49f4-83dc-9ccead73b182	FUEL_RECEIPT_POSTED	2703b8d8-048b-4340-bab3-9c882979afd2	6eef20ba-8ac7-40f8-898b-167ed37a8b3c	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
3	2026-08-14	Шатахуун таталт №3 — НИК ХХК	fuel_receipt	d95e2d4a-7335-4c63-bd85-8a657f822f37	FUEL_RECEIPT_POSTED	2703b8d8-048b-4340-bab3-9c882979afd2	f8a06132-fac6-458b-afdf-89133fe07f24	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
4	2026-08-15	Худалдан авалт №1 — Ундаа Дистрибьютер ХХК	purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	PURCHASE_POSTED	2703b8d8-048b-4340-bab3-9c882979afd2	73fc5981-284c-4a35-9ef7-29df469e4f27	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
10	2026-08-17	Зардал №1 — Цахилгааны зардал	expense	32571860-3fb6-4c7f-a60b-6442f6ae92d2	EXPENSE_POSTED	2703b8d8-048b-4340-bab3-9c882979afd2	d0070e18-b10f-400f-bf55-8748d30fd47f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
11	2026-08-17	Зардал №2 — Ус, дулааны зардал	expense	769c96a0-ad2b-4daf-94ac-cc2baf433f60	EXPENSE_POSTED	2703b8d8-048b-4340-bab3-9c882979afd2	8178ace7-b540-4abe-b031-5ffcc5f95428	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
12	2026-08-17	Зардал №3 — Түрээсийн зардал	expense	64806296-2238-4269-8391-e3f861277648	EXPENSE_POSTED	2703b8d8-048b-4340-bab3-9c882979afd2	c336b706-4862-4bb0-b4ca-8ec6022311c8	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
13	2026-08-17	Зардал №4 — Холбоо, интернэтийн зардал	expense	fe0bf502-8ba4-4a8b-bd7d-20b32947eef6	EXPENSE_POSTED	2703b8d8-048b-4340-bab3-9c882979afd2	c1f69a84-b99e-4922-8d57-b888d54a0f14	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
14	2026-08-17	Борлуулалт №1	sale	9669e532-1cdd-4e15-9f5e-b9e12f9bd17d	SALE_POSTED	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	45314197-0169-4201-a1aa-b738fe488ba7	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
15	2026-08-17	Борлуулалт №2	sale	c1a85e9a-5a73-4a70-8691-1f0f90b7098d	SALE_POSTED	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	568fa39c-b226-46de-bf9d-89c679164083	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
16	2026-08-17	Борлуулалт №3	sale	02734b52-a7ee-4fcb-9761-0fa713e24137	SALE_POSTED	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	e1369f27-208b-47bf-aa61-890510dce5e1	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
17	2026-08-17	Гэрээт авлагын төлбөр — GR-001	ar_payment	093f9796-ba1d-43ff-89ff-34a3064664b0	AR_RECEIPT	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	ff9b0720-e150-4e98-9e0c-13ef7b61d7d7	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
18	2026-08-17	Зардал №5 — Тээвэр, шатахууны зардал	expense	a59b18ae-a327-4e51-bd69-7aa243642096	EXPENSE_POSTED	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	7b9781bc-4924-46c1-9549-63209f09fcc8	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
20	2026-08-17	Ээлж №1 — кассын дутагдал	shift	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	SHIFT_CASH_SHORT	2703b8d8-048b-4340-bab3-9c882979afd2	a1ab745f-8cd3-41a8-92bc-ee23d3c9d7e5	2026-08-17 13:08:27.623374+08	2026-08-17 13:08:27.623374+08
\.


--
-- Data for Name: journal_lines; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.journal_lines (entry_id, line_no, account_code, debit, credit, memo, dim_fuel_id, dim_tank_id, dim_customer_id, dim_supplier_id, id, created_at, updated_at, dim_bank_account_id) FROM stdin;
6e3871ab-442f-4745-b9d9-c592875e7758	1	1301	34750000.00	0.00	Шатахуун таталт №1	c1d6e693-3f8b-43a4-bc1b-46e9431db264	e77a6891-1f46-418f-9b0e-cc8192efc8d8	\N	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	eb917f1f-5df4-4cd6-84ba-e7c7d2a24ea6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
6e3871ab-442f-4745-b9d9-c592875e7758	2	1402	3475000.00	0.00	Орох НӨАТ	\N	\N	\N	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	a71a6d6f-fad8-41ed-9df2-738c0c9c11ac	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
6e3871ab-442f-4745-b9d9-c592875e7758	3	2101	0.00	38225000.00	Шатахуун таталт №1	\N	\N	\N	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	53f92925-9681-423b-8f01-e45ec3f67f9b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
6eef20ba-8ac7-40f8-898b-167ed37a8b3c	1	1301	28520000.00	0.00	Шатахуун таталт №2	23a852ce-0998-4bac-b7f5-47f66cb855eb	43a5b093-914f-4d5f-8869-1545cccd0c29	\N	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	8264eae9-7d0c-43c5-9974-3942fcb2613d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
6eef20ba-8ac7-40f8-898b-167ed37a8b3c	2	1402	2852000.00	0.00	Орох НӨАТ	\N	\N	\N	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	d2d03e9e-ed24-4bf8-959b-4be26c400db7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
6eef20ba-8ac7-40f8-898b-167ed37a8b3c	3	2101	0.00	31372000.00	Шатахуун таталт №2	\N	\N	\N	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	6488cbaf-ed97-4c8e-a0d3-8e5deea2473b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
f8a06132-fac6-458b-afdf-89133fe07f24	1	1301	41480000.00	0.00	Шатахуун таталт №3	49fd9163-cbef-463e-89bf-a382f6769767	8f351557-542e-4c7f-86c4-e011cdde4516	\N	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	86ec63ff-df35-45fa-88e6-e40a95ab9dd4	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
f8a06132-fac6-458b-afdf-89133fe07f24	2	1402	4148000.00	0.00	Орох НӨАТ	\N	\N	\N	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	7b7fe83d-b0b4-45db-bd01-29b6eb0e7c13	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
f8a06132-fac6-458b-afdf-89133fe07f24	3	2101	0.00	45628000.00	Шатахуун таталт №3	\N	\N	\N	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	a1b38a51-8991-44e7-9dd5-c3f3eb7c9c43	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
73fc5981-284c-4a35-9ef7-29df469e4f27	1	1302	14832600.00	0.00	Худалдан авалт №1	\N	\N	\N	eebbf51f-69d4-4291-84aa-f23b4845b73e	0b33ed53-48f6-4385-8355-399905aaa6fb	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
73fc5981-284c-4a35-9ef7-29df469e4f27	2	1402	1483260.00	0.00	Орох НӨАТ	\N	\N	\N	eebbf51f-69d4-4291-84aa-f23b4845b73e	8cc9b0b1-8f09-4cbb-b2f4-acc7a09e175b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
73fc5981-284c-4a35-9ef7-29df469e4f27	3	2101	0.00	16315860.00	Худалдан авалт №1	\N	\N	\N	eebbf51f-69d4-4291-84aa-f23b4845b73e	337e18f4-8cb3-4ad1-9c6b-369e03230f21	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
d0070e18-b10f-400f-bf55-8748d30fd47f	1	5311	436363.64	0.00	Зардал №1	\N	\N	\N	\N	022422b9-0989-40bd-b3d9-d6927dea1e25	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
d0070e18-b10f-400f-bf55-8748d30fd47f	2	1402	43636.36	0.00	Орох НӨАТ	\N	\N	\N	\N	f2a34fd7-8910-48ee-8e3a-279c70695a1b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
d0070e18-b10f-400f-bf55-8748d30fd47f	3	1101	0.00	480000.00	Зардал №1	\N	\N	\N	\N	8e9f5e37-5046-43aa-8acf-5649b1a3032b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
8178ace7-b540-4abe-b031-5ffcc5f95428	1	5312	163636.36	0.00	Зардал №2	\N	\N	\N	\N	05dc9792-bc50-4e36-8e68-e0e88555345a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
8178ace7-b540-4abe-b031-5ffcc5f95428	2	1402	16363.64	0.00	Орох НӨАТ	\N	\N	\N	\N	9bdaa412-7356-4ff7-a31c-519f104f641d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
8178ace7-b540-4abe-b031-5ffcc5f95428	3	1101	0.00	180000.00	Зардал №2	\N	\N	\N	\N	91f7c99d-320c-4dd7-b921-3d3437435568	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
c336b706-4862-4bb0-b4ca-8ec6022311c8	1	5321	1363636.36	0.00	Зардал №3	\N	\N	\N	\N	56dec37d-7a09-4d14-8e47-331b1fffa4fe	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
c336b706-4862-4bb0-b4ca-8ec6022311c8	2	1402	136363.64	0.00	Орох НӨАТ	\N	\N	\N	\N	026badc1-3409-414e-a5d0-77531224a01d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
c336b706-4862-4bb0-b4ca-8ec6022311c8	3	1110	0.00	1500000.00	Зардал №3	\N	\N	\N	\N	c4b67927-620e-415e-9bb0-501919fa758d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
c1f69a84-b99e-4922-8d57-b888d54a0f14	1	5313	81818.18	0.00	Зардал №4	\N	\N	\N	\N	cd1a2fa9-3cef-4b7a-9b2c-ce6f02f66b22	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
c1f69a84-b99e-4922-8d57-b888d54a0f14	2	1402	8181.82	0.00	Орох НӨАТ	\N	\N	\N	\N	b394e8fe-953f-4250-8ea1-c189246ba717	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
c1f69a84-b99e-4922-8d57-b888d54a0f14	3	1101	0.00	90000.00	Зардал №4	\N	\N	\N	\N	ea90a16a-fd74-478e-b1c6-7e2df2e74c3b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	\N
45314197-0169-4201-a1aa-b738fe488ba7	1	1201	1534000.00	0.00	Төлбөр — Гэрээ	\N	\N	22277089-5c93-4c72-815c-c19196658f37	\N	09333ee5-4c1b-49d9-85ef-20d2038059ec	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
45314197-0169-4201-a1aa-b738fe488ba7	2	4101	0.00	1318181.82	Түлшний борлуулалт	c1d6e693-3f8b-43a4-bc1b-46e9431db264	e77a6891-1f46-418f-9b0e-cc8192efc8d8	\N	\N	902ac644-4081-4e9e-891a-aea25b2e1881	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
45314197-0169-4201-a1aa-b738fe488ba7	3	4102	0.00	76363.63	Барааны борлуулалт	\N	\N	\N	\N	7cd64796-e0a9-4161-b88a-2d60c4dc0a89	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
45314197-0169-4201-a1aa-b738fe488ba7	4	2201	0.00	139454.55	Борлуулалтын НӨАТ	\N	\N	\N	\N	dd53476c-8408-424c-b68d-abcb8ea256b9	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
45314197-0169-4201-a1aa-b738fe488ba7	5	5101	1241071.43	0.00	Түлшний өртөг	c1d6e693-3f8b-43a4-bc1b-46e9431db264	e77a6891-1f46-418f-9b0e-cc8192efc8d8	\N	\N	885d7a03-56b4-4e1d-9182-187e08b08465	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
45314197-0169-4201-a1aa-b738fe488ba7	6	1301	0.00	1241071.43	Түлшний нөөц хасалт	c1d6e693-3f8b-43a4-bc1b-46e9431db264	e77a6891-1f46-418f-9b0e-cc8192efc8d8	\N	\N	75018f7d-2c4c-4ff7-8b74-a368413fce41	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
45314197-0169-4201-a1aa-b738fe488ba7	7	5102	58000.00	0.00	Барааны өртөг	\N	\N	\N	\N	a6f168f6-7c0e-463f-9caf-dc2c718df35b	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
45314197-0169-4201-a1aa-b738fe488ba7	8	1302	0.00	58000.00	Барааны нөөц хасалт	\N	\N	\N	\N	ce6f76cf-f611-4c6e-8ba2-a876493ef6be	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
568fa39c-b226-46de-bf9d-89c679164083	1	1102	90000.00	0.00	Төлбөр — Карт	\N	\N	\N	\N	33b3f60f-777c-4c3f-8e62-d66fd218b593	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
568fa39c-b226-46de-bf9d-89c679164083	2	1101	27840000.00	0.00	Төлбөр — Бэлэн	\N	\N	\N	\N	23da8878-9de3-461d-8ae5-1a8c9f41bed6	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
568fa39c-b226-46de-bf9d-89c679164083	3	4101	0.00	25390909.09	Түлшний борлуулалт	c1d6e693-3f8b-43a4-bc1b-46e9431db264	e77a6891-1f46-418f-9b0e-cc8192efc8d8	\N	\N	0a7e676f-550e-4a98-863a-b78d4c3078a3	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
568fa39c-b226-46de-bf9d-89c679164083	4	2201	0.00	2539090.91	Борлуулалтын НӨАТ	\N	\N	\N	\N	772748b5-c138-4d83-a2ce-0d12864673de	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
568fa39c-b226-46de-bf9d-89c679164083	5	5101	23580357.14	0.00	Түлшний өртөг	c1d6e693-3f8b-43a4-bc1b-46e9431db264	e77a6891-1f46-418f-9b0e-cc8192efc8d8	\N	\N	f4b3ebf3-b604-46ed-8328-301ef87c519d	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
568fa39c-b226-46de-bf9d-89c679164083	6	1301	0.00	23580357.14	Түлшний нөөц хасалт	c1d6e693-3f8b-43a4-bc1b-46e9431db264	e77a6891-1f46-418f-9b0e-cc8192efc8d8	\N	\N	9d0854be-aec3-4ac6-9aee-9038cc5e5786	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
e1369f27-208b-47bf-aa61-890510dce5e1	1	1101	42000.00	0.00	Төлбөр — Бэлэн	\N	\N	\N	\N	7dc14fa9-b25c-4f12-8333-aed6364a3ab2	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
e1369f27-208b-47bf-aa61-890510dce5e1	2	4102	0.00	38181.82	Барааны борлуулалт	\N	\N	\N	\N	1b3a19ea-f6a1-4cbc-918b-cfd89e9f2359	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
e1369f27-208b-47bf-aa61-890510dce5e1	3	2201	0.00	3818.18	Борлуулалтын НӨАТ	\N	\N	\N	\N	6df2a4e0-728b-4750-b29f-12a3d19c63af	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
e1369f27-208b-47bf-aa61-890510dce5e1	4	5102	29000.00	0.00	Барааны өртөг	\N	\N	\N	\N	eb00bd47-02a2-45d7-bbde-9ace4bb1f352	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
e1369f27-208b-47bf-aa61-890510dce5e1	5	1302	0.00	29000.00	Барааны нөөц хасалт	\N	\N	\N	\N	de5ebcbd-38a7-4976-92e7-9d688ab84bda	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
ff9b0720-e150-4e98-9e0c-13ef7b61d7d7	1	1110	400000.00	0.00	Гэрээт авлагын төлбөр	\N	\N	22277089-5c93-4c72-815c-c19196658f37	\N	078e268c-4c3e-4ec3-8e84-f99f9c636529	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
ff9b0720-e150-4e98-9e0c-13ef7b61d7d7	2	1201	0.00	400000.00	Гэрээт авлагын төлбөр	\N	\N	22277089-5c93-4c72-815c-c19196658f37	\N	6f6d4f77-a10b-4a91-b180-4e257beaed2a	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
7b9781bc-4924-46c1-9549-63209f09fcc8	1	5341	10000.00	0.00	Зардал №5	\N	\N	\N	\N	bd0abe96-1a9c-4ad2-8f00-1fb06289f913	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
7b9781bc-4924-46c1-9549-63209f09fcc8	2	1101	0.00	10000.00	Зардал №5	\N	\N	\N	\N	ff0baf88-ac4f-47d8-ae4b-d1ed22abbdc4	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
a1ab745f-8cd3-41a8-92bc-ee23d3c9d7e5	1	5902	28352000.00	0.00	Ээлж №1 — кассын дутагдал	\N	\N	\N	\N	e8d34d9c-4682-4987-b187-5544ae408734	2026-08-17 13:08:27.623374+08	2026-08-17 13:08:27.623374+08	\N
a1ab745f-8cd3-41a8-92bc-ee23d3c9d7e5	2	1101	0.00	28352000.00	Ээлж №1 — кассын дутагдал	\N	\N	\N	\N	28817292-673f-41ec-9cdc-a24ce54f694c	2026-08-17 13:08:27.623374+08	2026-08-17 13:08:27.623374+08	\N
\.


--
-- Data for Name: payments; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.payments (sale_id, method, amount, contract_id, received, change_given, ref_no, id, created_at, updated_at) FROM stdin;
9669e532-1cdd-4e15-9f5e-b9e12f9bd17d	contract	1534000.00	636e4521-0375-4557-85c8-74d0187cbaa3	\N	\N	\N	5b8dd2c9-2bcf-4615-ad74-05d4b05e3e6c	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
c1a85e9a-5a73-4a70-8691-1f0f90b7098d	card	90000.00	\N	\N	\N	SETTLEMENT	d7db6b52-7ee8-43f9-bbfb-d29ea67db674	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
c1a85e9a-5a73-4a70-8691-1f0f90b7098d	cash	27840000.00	\N	27840000.00	0.00	\N	52c5da05-8968-42bd-9fe3-d5b5cc8b14eb	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
02734b52-a7ee-4fcb-9761-0fa713e24137	cash	42000.00	\N	42000.00	0.00	\N	d2f450fb-011a-445a-9f76-73b894306568	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
\.


--
-- Data for Name: payroll_lines; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.payroll_lines (period_id, employee_id, worked_days, month_days, base_salary, earned_salary, bonus, other_addition, gross, si_employee, si_employer, taxable, pit, advance, other_deduction, net, note, id, created_at, updated_at, worked_from, worked_to, si_enabled) FROM stdin;
\.


--
-- Data for Name: payroll_periods; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.payroll_periods (year, month, status, si_employee_rate, si_employer_rate, pit_rate, pit_credit, gross_total, si_employee_total, si_employer_total, pit_total, net_total, paid_salary, paid_pit, paid_social, approved_by, approved_at, note, id, created_at, updated_at, auto_sync) FROM stdin;
\.


--
-- Data for Name: permissions; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.permissions (code, name_mn, id, created_at, updated_at) FROM stdin;
sales.create	Борлуулалт хийх	81d68127-8c79-47df-93a4-a6e6868564c4	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
sales.view	Борлуулалт харах	9f7e0948-4f95-4764-b079-d7189eca7e55	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
sales.view_all	Бүх борлуулалт харах	9328db06-c4f6-49ae-aacd-389edf3344cf	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
sales.refund.request	Буцаалт хүсэх	3b771d6c-95c6-4efc-9b98-4441fdb91a7b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
sales.refund.approve	Буцаалт батлах	761280ae-8053-471c-9370-623e83af02c0	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
shifts.open	Ээлж нээх	3366f7e4-f266-498c-aa6d-828f6b28a58d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
shifts.close	Ээлж хаах	3d3c99da-55f8-4f61-b3d4-70208ea2480b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
shifts.view_all	Бүх ээлж харах	42150907-0713-40ad-880d-ce31b676d7d7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
tanks.view	Сав харах	2ae3bf9c-fc2e-475b-862d-129928d3b74c	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
tanks.manage	Сав удирдах	13bfdf07-bce6-4bea-85a3-141d1a01dab7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
products.view	Бараа харах	fc0cadc1-35f6-4725-82a8-a1750c69f576	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
products.manage	Бараа удирдах	b8481eed-b9fb-4290-a5c3-71940453fdb7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
inventory.manage	Нөөц удирдах	3b33d0df-7bfe-480a-8ca2-6aa32a974eff	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
inventory.convert	Задлан хөрвүүлэх	7ec6b30c-a3fd-4faa-8b41-28f3758e1602	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
prices.request	Үнэ өөрчлөх хүсэх	d31337cb-42ab-4027-9463-b3582807d11f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
prices.approve	Үнэ өөрчлөх батлах	939ee1e0-fd63-4de5-bdbe-dc641d4276c5	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
receipts.create	Шатахуун таталт бүртгэх	2b798681-f1c1-4243-b504-1413e5859a1f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
purchases.manage	Худалдан авалт удирдах	86a80ae4-8c42-41ad-8b93-1b8d18ceb551	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
expenses.manage	Зардал бүртгэх	99b86ca9-aa78-4589-8520-f7bc76ab55b8	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
bank.manage	Харилцах данс, банкны хуулга	92204f20-1222-472e-be5b-2450e83f9a94	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
payroll.manage	Цалин тооцох	f6b1bac2-8ac9-431d-ae26-22f3d085b124	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
payroll.approve	Цалин батлах, олгох	bc629c27-aa0d-4f3c-95ce-df35233a9073	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
suppliers.manage	Нийлүүлэгч удирдах	940f1ca0-f9f5-4108-9e91-a89b75eb9f58	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
contracts.manage	Гэрээ удирдах	9d68fbfe-f1e4-44bf-853d-3582fbf4a452	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
instruments.manage	Ваучер/карт удирдах	6b1b69cd-0d9c-42ec-a6cb-98564324c6b0	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
accounting.view	НББ харах	6077caa3-5607-4fd4-9fb5-c4a8b365efcc	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
accounting.manage	НББ бичилт хийх	c670e0e3-f7e7-4d7d-a013-14bcceaa7169	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
reports.view	Тайлан харах	b8dab2a7-59a9-4a21-b972-81439dba5a01	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
dashboard.owner	Эзний хяналт	79b0681c-2917-4ad5-af43-716a2b843b03	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
users.manage	Хэрэглэгч удирдах	1b057e21-a8f9-4df0-b5d0-0e7f2904aa7a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
settings.manage	Тохиргоо удирдах	0754f750-df33-40a1-84f7-78cd0e9c1da6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
backup.manage	Нөөцлөлт удирдах	6efc4955-6651-4925-9941-d3782ea5e9d3	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
audit.view	Аудит лог харах	80496d5e-0010-4931-bb8b-9be25e8d9469	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
ebarimt.manage	И-баримт удирдах	c09004bf-0992-4594-8d60-70cf67f192c2	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
shifts.approve	Ээлжийн хаалт засаж батлах	2a00ee1a-397c-486f-a108-ba282fa51b03	2026-08-17 13:07:34.759648+08	2026-08-17 13:07:34.759648+08
pumps.view	Түгээгүүр харах	81984ba6-aeaf-4b27-a4b4-de7526a223c0	2026-08-17 03:57:57.461784+08	2026-08-17 17:29:01.246489+08
pumps.manage	Түгээгүүр удирдах	c8156488-2f96-4130-98f0-5e2003f04471	2026-08-17 03:57:57.461784+08	2026-08-17 17:29:01.246489+08
\.


--
-- Data for Name: price_changes; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.price_changes (target_type, fuel_id, product_id, old_price, new_price, reason, status, requested_by, decided_by, decided_at, decision_note, id, created_at, updated_at, branch_id, effective_date, applied_at) FROM stdin;
\.


--
-- Data for Name: product_branch_stocks; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.product_branch_stocks (id, product_id, branch_id, qty, created_at, updated_at, avg_cost) FROM stdin;
3df1c226-dc25-4a80-b017-e33aadf8f30f	4205ad35-3737-4eaf-9616-c576082f6b0a	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	24.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	58000.000000
681c54e7-c1e4-4dd9-8173-d63e859ea8be	03d8206e-0ddd-4809-bedc-339b7cd5fcd3	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	30.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	53000.000000
512dc070-c42a-4342-8e70-0bcc65bda942	601f3fd1-ecf1-40c9-a6ff-b92c26fd32e6	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	48.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	15500.000000
828debd3-25d8-4bac-bbd3-1a1b3624b91b	fd5fabc8-c097-4d63-aaf5-80750ac08591	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	20.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	18000.000000
27e336fa-2ddb-4626-bcd9-60afbed1c471	8d346bf0-da65-4362-a486-103422de94c2	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	18.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	13000.000000
c94d3e8f-cbb6-4f3b-85c0-b46e02d21118	6df82dc1-1c2f-4fb3-880a-2f7154f9d063	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	25.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	11000.000000
96d0d4d8-36b9-46ef-9944-38ad859ec14b	714e4437-a3ad-44ea-bb50-c904386d9c82	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	16.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	31000.000000
d856fc82-ac8e-4477-9127-2f1a21f85ef9	d9b0db4b-0c9a-43d8-88aa-fa4966a8d4d9	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	35.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	8500.000000
ecf69733-8566-417a-bffe-5199cfedab65	e421bb83-b6bc-4557-82f6-f2a5618129ce	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	40.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	10000.000000
4a76fe8b-7e29-4002-ba2a-4f0f32f72ff4	252150ac-5039-4e84-b958-b2a9d32c04fc	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	6.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	225000.000000
d3c7db18-1e0d-41d0-ab91-16239554f811	3859b7ec-0e00-47cd-b5d7-855ce57a5b40	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	4.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	280000.000000
12fb9d13-f10b-41e7-9473-aad64841c6b4	e59acdf4-66d3-4d04-b22d-19bcaf57d447	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	30.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	7000.000000
66893c80-6819-46be-b9f4-6af264981f37	5fd54064-dd7b-4480-8b16-4e870cb04a49	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	24.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	11000.000000
ed4da169-93de-46cc-915d-f9193b2a184e	c135c570-7a28-49a8-a528-f23b6eea64ac	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	120.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	900.000000
dd9d0359-f866-408b-899f-7feba496d5dc	36842f30-734f-421b-b0f8-123ce58e6f8a	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	80.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	1600.000000
5480aa71-8641-4d5d-b952-e73a0f4dd642	b5e0a9e1-5543-425b-bd00-7d62bb4ae1e8	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	96.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	2100.000000
6e6928cf-84b7-422c-ab06-391aae7a5452	0e9d5f69-7d29-49c4-a11d-062ba7422c99	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	72.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	2100.000000
091e72a9-4bc6-4099-b159-a9de7c0eda74	a96c713f-6526-4297-9e17-af7bdc32744c	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	48.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	3800.000000
26ca5f44-1945-4fda-948b-b6e3c4420a3e	9c8fdd62-19a6-48bb-8359-3006f60d242c	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	60.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	2200.000000
19fc9bc8-813c-4965-a7da-e06ed64a4cc3	50d04e7e-8304-4a4e-8245-aaf3554d0629	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	36.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	4500.000000
89bee37d-00f5-421f-bde3-c81b0d508fe1	adb7e52f-6904-46cc-80bf-3521f787d2f6	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	60.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	3000.000000
79e85736-43bd-451d-a411-ed1c20a10e11	b5d63389-fbc4-4a30-bfbd-884a4493f80d	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	50.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	2300.000000
aaf652b6-affe-41a7-9f10-f2cc27f35ac2	39ae8b3c-09d1-4812-82b9-9cc529dc1cbf	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	45.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	3400.000000
30ef57b5-9696-4ef2-bb71-73f5e768eef9	3583bd45-3f4a-4b9c-973b-7769277755d1	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	30.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	5500.000000
bab1100e-7a38-44aa-8082-2ed3d6e5e7c3	cbe4ec5f-4b93-432e-b0c9-81615c5dade1	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	80.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	1200.000000
93146a6e-1521-4bdb-ac8b-906e5d47d9bd	4fd12e88-8927-429d-ae1c-f0ff508feb1f	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	20.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	2000.000000
e8d67f95-ca37-401a-af5b-a2bdc02526e6	f6134a7c-af69-477f-8535-3d2a7ad98f35	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	50.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	8000.000000
83c6591a-7463-406e-809a-71043f076938	c1d58096-45a1-44e5-85f6-0040f634313d	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	40.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	7100.000000
71844826-427b-409e-9d03-6c07c416d22c	a68aad98-5af3-4ce7-b1c0-c49ba2c12a16	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	35.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	7500.000000
34e10684-faa6-4fbc-b61d-3c5d551a60c9	1aa68dba-e777-4d64-b4e2-9b1be2980f79	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	15.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	16000.000000
64a10f03-98fd-4f18-bd32-05c5715d9d6b	35fab42d-9792-412e-88e2-d30112757f12	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	5.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	98000.000000
ac806d4d-8526-4271-965c-82800b528590	cf458ed4-1a3f-42ba-af59-bece34408933	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	10.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	33000.000000
806dfe8f-d212-414a-9352-52ac8c12cb4d	cfc4d796-2177-4106-9cee-5ddfef157906	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	8.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	62000.000000
51ed9730-510e-463c-81e8-e2926e8104a7	d99fadd9-9f9b-4730-8fec-56df3776ddcd	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	12.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	14000.000000
4b5d9618-3546-4908-a8b6-d26fc7e8143a	266fe348-d6f0-4083-83ae-dff3e8679bc5	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	40.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	3800.000000
622c001f-0846-4cad-a4a3-1577dea783ea	21635e50-b235-489e-bc6c-f67cde6aeab8	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	60.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	2500.000000
8a59fac0-b65f-482e-8f20-0626a973dded	47a733fd-b7dc-472c-b2ce-4e96edf207c4	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	20.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	12000.000000
822705e8-307d-4f67-b6f6-231c1628dd78	96996409-5f2a-4770-bac1-abdf2113211e	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	14.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	18500.000000
faafe262-0396-4585-bb3c-c6ee53be0cfe	d8f3bc7f-4b11-4c43-8cfe-be16f6af95cc	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	18.000	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	9800.000000
3f8e8f01-c073-45aa-a61e-192929e2e6a0	e0da3098-6a08-4dc5-95f4-46128fae6806	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	19.000	2026-08-17 03:57:57.461784+08	2026-08-17 12:00:01.452484+08	29000.000000
\.


--
-- Data for Name: product_categories; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.product_categories (name_mn, icon, sort_order, id, created_at, updated_at) FROM stdin;
Тос, тосолгооны материал	droplet	1	f0cd472e-60ee-47e0-9ae2-b28ba3b87148	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
Антифриз, ХШУ	thermometer	2	c187ad34-4fc2-4420-a9b0-bc32947a1db8	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
Аккумулятор, цахилгаан	battery	3	a1cd32f7-b0c4-48eb-a65e-41e84c470fbc	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
Ундаа, ус	cup-soda	4	b681667b-ffac-454a-9bbf-f65643e55ed0	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
Хүнс, амттан	cookie	5	315a1526-303b-42f2-96ac-46565078ea01	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
Тамхи	cigarette	6	2de8ba94-bdb0-46b1-b7b6-d19367b2b0a1	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
Автын хэрэгсэл	wrench	7	3d0ad23e-0331-4271-b37b-ff0754bd3da2	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
Угаалга, арчилгаа	spray-can	8	86cd77e8-38a4-45da-ad7e-4f200adbf74b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
\.


--
-- Data for Name: products; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.products (sku, barcode, name_mn, category_id, unit, price, avg_cost, stock_qty, min_stock, is_active, id, created_at, updated_at, sale_mode, bulk_product_id, bulk_factor) FROM stdin;
BLK-001	\N	Мотор тос 5W-30 задлан	f0cd472e-60ee-47e0-9ae2-b28ba3b87148	л	21000.00	0.000000	0.000	2.000	t	5c063868-6183-443b-b3f1-fa93480ead66	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	bulk	\N	0.000
BLK-002	\N	Мотор тос 10W-40 задлан	f0cd472e-60ee-47e0-9ae2-b28ba3b87148	л	19500.00	0.000000	0.000	2.000	t	039412cc-c351-4425-abf9-39aa7f8666a6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	bulk	\N	0.000
BLK-003	\N	Антифриз ногоон задлан	c187ad34-4fc2-4420-a9b0-bc32947a1db8	л	11500.00	0.000000	0.000	2.000	t	01ec63c5-5521-4db8-8959-5a6a92df1b29	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	bulk	\N	0.000
OIL-001	\N	Мотор тос 5W-30 4л	f0cd472e-60ee-47e0-9ae2-b28ba3b87148	ш	78000.00	58000.000000	24.000	5.000	t	4205ad35-3737-4eaf-9616-c576082f6b0a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	5c063868-6183-443b-b3f1-fa93480ead66	4.000
OIL-002	\N	Мотор тос 10W-40 4л	f0cd472e-60ee-47e0-9ae2-b28ba3b87148	ш	72000.00	53000.000000	30.000	5.000	t	03d8206e-0ddd-4809-bedc-339b7cd5fcd3	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	039412cc-c351-4425-abf9-39aa7f8666a6	4.000
OIL-003	\N	Мотор тос 5W-40 1л	f0cd472e-60ee-47e0-9ae2-b28ba3b87148	ш	22000.00	15500.000000	48.000	5.000	t	601f3fd1-ecf1-40c9-a6ff-b92c26fd32e6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
OIL-004	\N	Хурдны хайрцгийн тос ATF 1л	f0cd472e-60ee-47e0-9ae2-b28ba3b87148	ш	26000.00	18000.000000	20.000	5.000	t	fd5fabc8-c097-4d63-aaf5-80750ac08591	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
OIL-005	\N	Гидравлик тос 1л	f0cd472e-60ee-47e0-9ae2-b28ba3b87148	ш	19000.00	13000.000000	18.000	5.000	t	8d346bf0-da65-4362-a486-103422de94c2	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
OIL-006	\N	Тормозны шингэн DOT-4	f0cd472e-60ee-47e0-9ae2-b28ba3b87148	ш	17000.00	11000.000000	25.000	5.000	t	6df82dc1-1c2f-4fb3-880a-2f7154f9d063	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
ANT-002	\N	Антифриз улаан 4л	c187ad34-4fc2-4420-a9b0-bc32947a1db8	ш	45000.00	31000.000000	16.000	5.000	t	714e4437-a3ad-44ea-bb50-c904386d9c82	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
ANT-003	\N	Хөргөлтийн шингэн 1л	c187ad34-4fc2-4420-a9b0-bc32947a1db8	ш	13000.00	8500.000000	35.000	5.000	t	d9b0db4b-0c9a-43d8-88aa-fa4966a8d4d9	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
ANT-004	\N	Шил угаагч -30°C 4л	c187ad34-4fc2-4420-a9b0-bc32947a1db8	ш	16000.00	10000.000000	40.000	5.000	t	e421bb83-b6bc-4557-82f6-f2a5618129ce	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
BAT-001	\N	Аккумулятор 60Ah	a1cd32f7-b0c4-48eb-a65e-41e84c470fbc	ш	295000.00	225000.000000	6.000	5.000	t	252150ac-5039-4e84-b958-b2a9d32c04fc	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
BAT-002	\N	Аккумулятор 75Ah	a1cd32f7-b0c4-48eb-a65e-41e84c470fbc	ш	365000.00	280000.000000	4.000	5.000	t	3859b7ec-0e00-47cd-b5d7-855ce57a5b40	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
BAT-003	\N	Гал хамгаалагчийн иж бүрдэл	a1cd32f7-b0c4-48eb-a65e-41e84c470fbc	ш	12000.00	7000.000000	30.000	5.000	t	e59acdf4-66d3-4d04-b22d-19bcaf57d447	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
BAT-004	\N	Гэрлийн чийдэн H4	a1cd32f7-b0c4-48eb-a65e-41e84c470fbc	ш	18000.00	11000.000000	24.000	5.000	t	5fd54064-dd7b-4480-8b16-4e870cb04a49	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
DRK-001	\N	Ус 0.5л	b681667b-ffac-454a-9bbf-f65643e55ed0	ш	1500.00	900.000000	120.000	5.000	t	c135c570-7a28-49a8-a528-f23b6eea64ac	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
DRK-002	\N	Ус 1.5л	b681667b-ffac-454a-9bbf-f65643e55ed0	ш	2500.00	1600.000000	80.000	5.000	t	36842f30-734f-421b-b0f8-123ce58e6f8a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
DRK-003	\N	Кока-Кола 0.5л	b681667b-ffac-454a-9bbf-f65643e55ed0	ш	3000.00	2100.000000	96.000	5.000	t	b5e0a9e1-5543-425b-bd00-7d62bb4ae1e8	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
DRK-004	\N	Спрайт 0.5л	b681667b-ffac-454a-9bbf-f65643e55ed0	ш	3000.00	2100.000000	72.000	5.000	t	0e9d5f69-7d29-49c4-a11d-062ba7422c99	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
DRK-005	\N	Эрчим хүчний ундаа	b681667b-ffac-454a-9bbf-f65643e55ed0	ш	5500.00	3800.000000	48.000	5.000	t	a96c713f-6526-4297-9e17-af7bdc32744c	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
DRK-006	\N	Хүйтэн цай 0.5л	b681667b-ffac-454a-9bbf-f65643e55ed0	ш	3200.00	2200.000000	60.000	5.000	t	9c8fdd62-19a6-48bb-8359-3006f60d242c	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
DRK-007	\N	Жүүс 1л	b681667b-ffac-454a-9bbf-f65643e55ed0	ш	6500.00	4500.000000	36.000	5.000	t	50d04e7e-8304-4a4e-8245-aaf3554d0629	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
FOD-001	\N	Шоколад	315a1526-303b-42f2-96ac-46565078ea01	ш	4500.00	3000.000000	60.000	5.000	t	adb7e52f-6904-46cc-80bf-3521f787d2f6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
FOD-002	\N	Жигнэмэг	315a1526-303b-42f2-96ac-46565078ea01	ш	3500.00	2300.000000	50.000	5.000	t	b5d63389-fbc4-4a30-bfbd-884a4493f80d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
FOD-003	\N	Чипс	315a1526-303b-42f2-96ac-46565078ea01	ш	5000.00	3400.000000	45.000	5.000	t	39ae8b3c-09d1-4812-82b9-9cc529dc1cbf	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
FOD-004	\N	Самар 100гр	315a1526-303b-42f2-96ac-46565078ea01	ш	8000.00	5500.000000	30.000	5.000	t	3583bd45-3f4a-4b9c-973b-7769277755d1	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
FOD-005	\N	Бохь	315a1526-303b-42f2-96ac-46565078ea01	ш	2000.00	1200.000000	80.000	5.000	t	cbe4ec5f-4b93-432e-b0c9-81615c5dade1	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
FOD-006	\N	Талх	315a1526-303b-42f2-96ac-46565078ea01	ш	3000.00	2000.000000	20.000	5.000	t	4fd12e88-8927-429d-ae1c-f0ff508feb1f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
CIG-001	\N	Мальборо	2de8ba94-bdb0-46b1-b7b6-d19367b2b0a1	ш	9500.00	8000.000000	50.000	5.000	t	f6134a7c-af69-477f-8535-3d2a7ad98f35	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
CIG-002	\N	Винстон	2de8ba94-bdb0-46b1-b7b6-d19367b2b0a1	ш	8500.00	7100.000000	40.000	5.000	t	c1d58096-45a1-44e5-85f6-0040f634313d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
CIG-003	\N	Кэмел	2de8ba94-bdb0-46b1-b7b6-d19367b2b0a1	ш	9000.00	7500.000000	35.000	5.000	t	a68aad98-5af3-4ce7-b1c0-c49ba2c12a16	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
TOL-001	\N	Шүүр (цас цэвэрлэгч)	3d0ad23e-0331-4271-b37b-ff0754bd3da2	ш	25000.00	16000.000000	15.000	5.000	t	1aa68dba-e777-4d64-b4e2-9b1be2980f79	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
TOL-002	\N	Домкрат 2т	3d0ad23e-0331-4271-b37b-ff0754bd3da2	ш	135000.00	98000.000000	5.000	5.000	t	35fab42d-9792-412e-88e2-d30112757f12	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
TOL-003	\N	Чирэх татлага 5т	3d0ad23e-0331-4271-b37b-ff0754bd3da2	ш	48000.00	33000.000000	10.000	5.000	t	cf458ed4-1a3f-42ba-af59-bece34408933	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
TOL-004	\N	Насос (компрессор)	3d0ad23e-0331-4271-b37b-ff0754bd3da2	ш	85000.00	62000.000000	8.000	5.000	t	cfc4d796-2177-4106-9cee-5ddfef157906	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
TOL-005	\N	Гар чийдэн	3d0ad23e-0331-4271-b37b-ff0754bd3da2	ш	22000.00	14000.000000	12.000	5.000	t	d99fadd9-9f9b-4730-8fec-56df3776ddcd	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
CLN-001	\N	Шил арчигч алчуур	86cd77e8-38a4-45da-ad7e-4f200adbf74b	ш	6000.00	3800.000000	40.000	5.000	t	266fe348-d6f0-4083-83ae-dff3e8679bc5	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
CLN-002	\N	Салфетка	86cd77e8-38a4-45da-ad7e-4f200adbf74b	ш	4000.00	2500.000000	60.000	5.000	t	21635e50-b235-489e-bc6c-f67cde6aeab8	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
CLN-003	\N	Автын шампунь 1л	86cd77e8-38a4-45da-ad7e-4f200adbf74b	ш	18000.00	12000.000000	20.000	5.000	t	47a733fd-b7dc-472c-b2ce-4e96edf207c4	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
CLN-004	\N	Гялалзуулагч полироль	86cd77e8-38a4-45da-ad7e-4f200adbf74b	ш	27000.00	18500.000000	14.000	5.000	t	96996409-5f2a-4770-bac1-abdf2113211e	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
CLN-005	\N	Дугуйны хөө арилгагч	86cd77e8-38a4-45da-ad7e-4f200adbf74b	ш	15000.00	9800.000000	18.000	5.000	t	d8f3bc7f-4b11-4c43-8cfe-be16f6af95cc	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	piece	\N	0.000
ANT-001	\N	Антифриз ногоон 4л	c187ad34-4fc2-4420-a9b0-bc32947a1db8	ш	42000.00	29000.000000	19.000	5.000	t	e0da3098-6a08-4dc5-95f4-46128fae6806	2026-08-17 03:57:57.461784+08	2026-08-17 12:00:01.452484+08	piece	01ec63c5-5521-4db8-8959-5a6a92df1b29	4.000
\.


--
-- Data for Name: pump_nozzles; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.pump_nozzles (pump_id, nozzle_number, fuel_id, tank_id, totalizer, id, created_at, updated_at) FROM stdin;
c8ac6abd-b7e9-4576-919a-8798a893bacd	1	23a852ce-0998-4bac-b7f5-47f66cb855eb	43a5b093-914f-4d5f-8869-1545cccd0c29	0.000	21a0e617-cadf-4b73-b0cb-c0cca44223d4	2026-08-17 03:57:57.461784+08	2026-08-17 11:03:04.675143+08
dcfa813d-1d03-40e6-98cc-ecab6543b3db	2	23a852ce-0998-4bac-b7f5-47f66cb855eb	43a5b093-914f-4d5f-8869-1545cccd0c29	0.000	6d24df68-0af6-4cbf-8f1b-e65b2507b57f	2026-08-17 03:57:57.461784+08	2026-08-17 11:03:04.675143+08
c8ac6abd-b7e9-4576-919a-8798a893bacd	2	49fd9163-cbef-463e-89bf-a382f6769767	8f351557-542e-4c7f-86c4-e011cdde4516	0.000	882a249d-276a-4e0f-bf5e-a727ac9275bd	2026-08-17 03:57:57.461784+08	2026-08-17 11:03:04.675143+08
7043bd3c-e278-4032-b6be-7967d940651b	1	c1d6e693-3f8b-43a4-bc1b-46e9431db264	e77a6891-1f46-418f-9b0e-cc8192efc8d8	0.000	c051e10d-4a06-4565-a3c2-99c0243b9cf7	2026-08-17 03:57:57.461784+08	2026-08-17 11:03:04.675143+08
54b151aa-82af-4a72-9fdc-826e50766251	1	c1d6e693-3f8b-43a4-bc1b-46e9431db264	e77a6891-1f46-418f-9b0e-cc8192efc8d8	0.000	d4f03de0-9946-41b2-b75b-d45fcd3a85f8	2026-08-17 03:57:57.461784+08	2026-08-17 11:03:04.675143+08
7043bd3c-e278-4032-b6be-7967d940651b	2	49fd9163-cbef-463e-89bf-a382f6769767	8f351557-542e-4c7f-86c4-e011cdde4516	0.000	d9e5c598-dc94-462e-9240-095bf84fa703	2026-08-17 03:57:57.461784+08	2026-08-17 11:03:04.675143+08
dcfa813d-1d03-40e6-98cc-ecab6543b3db	1	c1d6e693-3f8b-43a4-bc1b-46e9431db264	e77a6891-1f46-418f-9b0e-cc8192efc8d8	110000.000	0c934906-05eb-4e8b-bded-2f9377d8efcc	2026-08-17 03:57:57.461784+08	2026-08-17 12:00:01.452484+08
63364f53-5598-4ec4-814a-d0f97f89c28b	1	c1d6e693-3f8b-43a4-bc1b-46e9431db264	b0c378c1-9d80-459e-8301-78a30c6df789	0.000	5071301b-3e2d-498d-83b7-bf6fe0d8e350	2026-08-17 17:18:15.280358+08	2026-08-17 17:18:15.280358+08
29db29eb-0fbf-473a-b20f-1e572e27aa3f	1	49fd9163-cbef-463e-89bf-a382f6769767	c77bbf42-fd34-4f0e-8199-ec3cb27f3ceb	0.000	1a1b751b-833e-4627-9f55-a4da70db023a	2026-08-17 17:19:28.783345+08	2026-08-17 17:19:28.783345+08
\.


--
-- Data for Name: pumps; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.pumps (number, name, status, driver, is_active, id, created_at, updated_at, branch_id, position_x, position_y) FROM stdin;
1	А92	idle	simulated	t	63364f53-5598-4ec4-814a-d0f97f89c28b	2026-08-17 17:18:06.225735+08	2026-08-18 11:26:26.524378+08	1f410c57-800a-4922-afc4-b9d5258cfff3	0	0
2	ТА	idle	simulated	t	29db29eb-0fbf-473a-b20f-1e572e27aa3f	2026-08-17 17:19:19.614859+08	2026-08-18 11:26:26.524378+08	1f410c57-800a-4922-afc4-b9d5258cfff3	2	0
1	1-р түгээгүүр	idle	simulated	t	dcfa813d-1d03-40e6-98cc-ecab6543b3db	2026-08-17 03:57:57.461784+08	2026-08-18 11:26:26.524378+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	0	0
2	2-р түгээгүүр	idle	simulated	t	7043bd3c-e278-4032-b6be-7967d940651b	2026-08-17 03:57:57.461784+08	2026-08-18 11:26:26.524378+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	0	0
3	3-р түгээгүүр	idle	simulated	t	c8ac6abd-b7e9-4576-919a-8798a893bacd	2026-08-17 03:57:57.461784+08	2026-08-18 11:26:26.524378+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	0	0
4	4-р түгээгүүр	idle	simulated	t	54b151aa-82af-4a72-9fdc-826e50766251	2026-08-17 03:57:57.461784+08	2026-08-18 11:26:26.524378+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69	0	0
\.


--
-- Data for Name: purchase_items; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.purchase_items (purchase_id, product_id, qty, unit_cost, amount, id, created_at, updated_at) FROM stdin;
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	4205ad35-3737-4eaf-9616-c576082f6b0a	24.000	58000.000000	1392000.00	aa1310fb-6407-4777-b6b9-51a0973e952b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	03d8206e-0ddd-4809-bedc-339b7cd5fcd3	30.000	53000.000000	1590000.00	6402a4e6-620c-49d1-a5b9-6be4d62fb1bf	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	601f3fd1-ecf1-40c9-a6ff-b92c26fd32e6	48.000	15500.000000	744000.00	0bf5d90a-a3a0-4591-9611-1cd33a63f040	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	fd5fabc8-c097-4d63-aaf5-80750ac08591	20.000	18000.000000	360000.00	c9553b5e-057f-48cd-bc0a-204fd1721934	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	8d346bf0-da65-4362-a486-103422de94c2	18.000	13000.000000	234000.00	b305211e-8b13-4a11-9746-8e5aa1664363	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	6df82dc1-1c2f-4fb3-880a-2f7154f9d063	25.000	11000.000000	275000.00	fa9ac799-b14f-4e99-a1f1-2cb989c9a975	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	e0da3098-6a08-4dc5-95f4-46128fae6806	22.000	29000.000000	638000.00	646a5d0c-38ef-486a-a8ba-3d4f1565bdc8	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	714e4437-a3ad-44ea-bb50-c904386d9c82	16.000	31000.000000	496000.00	2d1ce5ab-d39c-482c-8b48-dc115338d4fb	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	d9b0db4b-0c9a-43d8-88aa-fa4966a8d4d9	35.000	8500.000000	297500.00	6fd789b2-71a5-43eb-8ffc-45562a209488	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	e421bb83-b6bc-4557-82f6-f2a5618129ce	40.000	10000.000000	400000.00	dbe8a520-c82b-4513-b4be-f84143052d30	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	252150ac-5039-4e84-b958-b2a9d32c04fc	6.000	225000.000000	1350000.00	6422e796-f8e4-4173-ad48-97d8a9543037	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	3859b7ec-0e00-47cd-b5d7-855ce57a5b40	4.000	280000.000000	1120000.00	0c4740ee-88e2-4b9f-a14e-254e89d58ed9	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	e59acdf4-66d3-4d04-b22d-19bcaf57d447	30.000	7000.000000	210000.00	960440e5-d1a1-4946-b5db-26eff66c802d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	5fd54064-dd7b-4480-8b16-4e870cb04a49	24.000	11000.000000	264000.00	5d7d3ff1-2d7f-4540-807c-3ecc74977ee4	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	c135c570-7a28-49a8-a528-f23b6eea64ac	120.000	900.000000	108000.00	b074e0f8-60a0-4d18-bedb-7df24883dbc9	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	36842f30-734f-421b-b0f8-123ce58e6f8a	80.000	1600.000000	128000.00	36f18c49-be8f-4796-93f1-75ecd0f9eb59	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	b5e0a9e1-5543-425b-bd00-7d62bb4ae1e8	96.000	2100.000000	201600.00	83096197-75b0-4e36-923c-dc9e24f2cfdf	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	0e9d5f69-7d29-49c4-a11d-062ba7422c99	72.000	2100.000000	151200.00	24ce764a-7dd0-49cf-84a9-738a59e95cc7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	a96c713f-6526-4297-9e17-af7bdc32744c	48.000	3800.000000	182400.00	59f8cde7-61f1-4979-912a-f558acaab023	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	9c8fdd62-19a6-48bb-8359-3006f60d242c	60.000	2200.000000	132000.00	10ad6f81-956e-408c-a98c-fc188179d357	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	50d04e7e-8304-4a4e-8245-aaf3554d0629	36.000	4500.000000	162000.00	d251bdef-58c8-4fb6-ac02-e2cb83a1794f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	adb7e52f-6904-46cc-80bf-3521f787d2f6	60.000	3000.000000	180000.00	49ba1b00-05d9-4c79-805a-386f966d7e8c	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	b5d63389-fbc4-4a30-bfbd-884a4493f80d	50.000	2300.000000	115000.00	8a1b25e0-7ef5-4d26-be77-81eaee8c922f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	39ae8b3c-09d1-4812-82b9-9cc529dc1cbf	45.000	3400.000000	153000.00	89d6df1d-a190-4d71-80f8-7a4391f4896f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	3583bd45-3f4a-4b9c-973b-7769277755d1	30.000	5500.000000	165000.00	aa92f8d8-b634-40a0-a45c-46c5c6d17180	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	cbe4ec5f-4b93-432e-b0c9-81615c5dade1	80.000	1200.000000	96000.00	3eb51db2-54fc-4b15-84f5-ebbfac239928	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	4fd12e88-8927-429d-ae1c-f0ff508feb1f	20.000	2000.000000	40000.00	6ff570e3-2faa-4e2d-b46c-d0fd35be3b4b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	f6134a7c-af69-477f-8535-3d2a7ad98f35	50.000	8000.000000	400000.00	7e790fb6-c2d7-4cc6-8908-d0833f1e01fc	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	c1d58096-45a1-44e5-85f6-0040f634313d	40.000	7100.000000	284000.00	471430c1-631e-47a3-9b48-3ad96fe9a7da	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	a68aad98-5af3-4ce7-b1c0-c49ba2c12a16	35.000	7500.000000	262500.00	2e2a1184-138a-4c2c-a89e-cb1b8506c088	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	1aa68dba-e777-4d64-b4e2-9b1be2980f79	15.000	16000.000000	240000.00	53717069-b02e-4746-b92e-9965bc65752c	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	35fab42d-9792-412e-88e2-d30112757f12	5.000	98000.000000	490000.00	5afe343f-2927-438c-92d7-69cb0a0957cd	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	cf458ed4-1a3f-42ba-af59-bece34408933	10.000	33000.000000	330000.00	0e2cccc3-79b4-499a-94f7-c63dacbd44eb	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	cfc4d796-2177-4106-9cee-5ddfef157906	8.000	62000.000000	496000.00	1503d315-068a-4a59-bef1-de2f15014942	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	d99fadd9-9f9b-4730-8fec-56df3776ddcd	12.000	14000.000000	168000.00	4da400bb-710b-47ea-b301-7e87e869e7fb	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	266fe348-d6f0-4083-83ae-dff3e8679bc5	40.000	3800.000000	152000.00	39508ca7-a94d-498d-adcf-7b2fee2ce5cb	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	21635e50-b235-489e-bc6c-f67cde6aeab8	60.000	2500.000000	150000.00	6daec96c-f646-4706-93d1-4cea48c6308f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	47a733fd-b7dc-472c-b2ce-4e96edf207c4	20.000	12000.000000	240000.00	f533f646-e9a0-450b-96ab-977beeaf9fac	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	96996409-5f2a-4770-bac1-abdf2113211e	14.000	18500.000000	259000.00	8e903a71-8556-49a8-a0f5-f554a4c8fdde	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
d9df4ad5-20ae-4343-a95a-f7efcecd02e0	d8f3bc7f-4b11-4c43-8cfe-be16f6af95cc	18.000	9800.000000	176400.00	46ec7455-68f8-47a1-9002-ebade734c739	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
\.


--
-- Data for Name: purchases; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.purchases (number, supplier_id, purchase_date, invoice_no, subtotal, vat_amount, total_gross, status, posted_by, posted_at, ap_invoice_id, note, id, created_at, updated_at, branch_id) FROM stdin;
1	eebbf51f-69d4-4291-84aa-f23b4845b73e	2026-08-15	OPEN-0001	14832600.00	1483260.00	16315860.00	posted	2703b8d8-048b-4340-bab3-9c882979afd2	2026-08-17 03:57:58.792529+08	e107dc4b-99bf-49a4-8219-78bfeb140be7	Эхний үлдэгдэл	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
\.


--
-- Data for Name: refund_items; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.refund_items (refund_id, sale_item_id, qty, amount, cogs_amount, id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: refunds; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.refunds (sale_id, refund_type, amount, vat_amount, cogs_amount, reason, restock, refund_method, status, requested_by, decided_by, decided_at, decision_note, shift_id, id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: role_permissions; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.role_permissions (role_id, permission_id, id, created_at, updated_at) FROM stdin;
0199301a-4fb1-4f50-88d2-5226c37ac559	81d68127-8c79-47df-93a4-a6e6868564c4	db26386d-0749-43f2-99ac-926aadaca39c	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
0199301a-4fb1-4f50-88d2-5226c37ac559	9f7e0948-4f95-4764-b079-d7189eca7e55	386c603c-40b2-4bae-b5c4-235e32db96ef	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
0199301a-4fb1-4f50-88d2-5226c37ac559	3b771d6c-95c6-4efc-9b98-4441fdb91a7b	03ae01be-11f2-47e0-aa58-10ed08072507	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
0199301a-4fb1-4f50-88d2-5226c37ac559	3366f7e4-f266-498c-aa6d-828f6b28a58d	a34af6ea-e1f0-4794-b106-9ac9e960c076	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
0199301a-4fb1-4f50-88d2-5226c37ac559	3d3c99da-55f8-4f61-b3d4-70208ea2480b	fadf18ed-cacb-4873-8af1-b34d637fb5b3	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
0199301a-4fb1-4f50-88d2-5226c37ac559	2ae3bf9c-fc2e-475b-862d-129928d3b74c	407c7331-cc24-49fc-a32e-dbf0cfcf58e5	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
0199301a-4fb1-4f50-88d2-5226c37ac559	81984ba6-aeaf-4b27-a4b4-de7526a223c0	e7014fdd-6805-4d58-81b3-960f5b859fc3	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
0199301a-4fb1-4f50-88d2-5226c37ac559	fc0cadc1-35f6-4725-82a8-a1750c69f576	928e752b-2cb8-4c9a-89d9-14c82bd5f31a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
0199301a-4fb1-4f50-88d2-5226c37ac559	7ec6b30c-a3fd-4faa-8b41-28f3758e1602	02e7b3b3-5c43-4fa8-8a29-9bbc4b10f0e0	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	81d68127-8c79-47df-93a4-a6e6868564c4	1008778a-1637-460d-806c-4b72b0f5d8fd	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	9f7e0948-4f95-4764-b079-d7189eca7e55	34d0a98c-efd6-4e56-93b3-d6e48cb36cd6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	3b771d6c-95c6-4efc-9b98-4441fdb91a7b	4d25679f-5d12-48f3-b991-c1d93b06c778	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	3366f7e4-f266-498c-aa6d-828f6b28a58d	c3662c3a-df59-4a6e-9905-eb60d94716ef	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	3d3c99da-55f8-4f61-b3d4-70208ea2480b	dd0003aa-08f7-4bcb-84a5-c7842c7d15f2	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	2ae3bf9c-fc2e-475b-862d-129928d3b74c	255f493e-0f1d-46ef-b81d-60eb2ebb2a71	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	81984ba6-aeaf-4b27-a4b4-de7526a223c0	3e1e56e3-9bb7-42b2-b39a-2ca1669fe182	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	fc0cadc1-35f6-4725-82a8-a1750c69f576	943d62d7-5d6b-40cc-accf-178d72238e77	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	7ec6b30c-a3fd-4faa-8b41-28f3758e1602	dee6d808-a6d9-4288-a1e5-aca08997d66b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	9328db06-c4f6-49ae-aacd-389edf3344cf	9a338329-7dd6-49a5-a480-7ebd8fa32ef7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	42150907-0713-40ad-880d-ce31b676d7d7	b173efdd-9585-49ab-b436-3b5a3804b5cd	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	13bfdf07-bce6-4bea-85a3-141d1a01dab7	bd1426f8-afde-4072-b950-a58a151e62ea	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	c8156488-2f96-4130-98f0-5e2003f04471	0073b8a9-959b-4f52-83ee-bc80a6952075	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	b8481eed-b9fb-4290-a5c3-71940453fdb7	1254d5fe-8603-4f97-8aae-a8ab0a29c629	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	3b33d0df-7bfe-480a-8ca2-6aa32a974eff	dee03083-4eff-4212-b4f8-492b915f8958	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	d31337cb-42ab-4027-9463-b3582807d11f	eb64857a-dff8-48d9-a751-86651d60cbfb	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	2b798681-f1c1-4243-b504-1413e5859a1f	a42fb2f5-9a1a-4e32-8736-14547a1782b9	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	86a80ae4-8c42-41ad-8b93-1b8d18ceb551	2f0c7b0d-2fde-438e-96ac-10900c675ceb	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	99b86ca9-aa78-4589-8520-f7bc76ab55b8	98368459-a9c2-4b51-a0eb-8fe997f27519	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	92204f20-1222-472e-be5b-2450e83f9a94	10fd1ba1-2635-4d22-bfeb-dc56192b548b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	f6b1bac2-8ac9-431d-ae26-22f3d085b124	9126d911-7bd8-4ceb-a175-e8d5a0f90e22	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	940f1ca0-f9f5-4108-9e91-a89b75eb9f58	585ec53e-43ee-47a9-99e8-f10cd52c7566	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	9d68fbfe-f1e4-44bf-853d-3582fbf4a452	2a952f7c-7417-4f01-888f-0cda90c74608	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	6b1b69cd-0d9c-42ec-a6cb-98564324c6b0	fab65263-f562-4c70-834a-1fe1d6253e9d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	6077caa3-5607-4fd4-9fb5-c4a8b365efcc	850becf7-a6cc-4a09-95ef-21355b68ff6a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	b8dab2a7-59a9-4a21-b972-81439dba5a01	d8256c29-94d6-4728-b527-a964f597354a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	c09004bf-0992-4594-8d60-70cf67f192c2	cf5a069b-c9c9-45e1-8333-2b7fd5c969fc	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	81d68127-8c79-47df-93a4-a6e6868564c4	d4c60dc1-ffa7-4b76-aacd-ecd3ad06b77e	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	9f7e0948-4f95-4764-b079-d7189eca7e55	f1bfd4bf-503e-44e7-b1d8-6572483bc6f3	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	9328db06-c4f6-49ae-aacd-389edf3344cf	067631c7-8f86-404e-ba5b-2285623916c4	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	3b771d6c-95c6-4efc-9b98-4441fdb91a7b	5763d6f8-5220-4faf-b649-1a89f76df32f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	761280ae-8053-471c-9370-623e83af02c0	f151ca1f-d231-473b-aaf4-ef0929028bd4	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	3366f7e4-f266-498c-aa6d-828f6b28a58d	cffafb74-b545-490d-a7b3-e5472f626dff	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	3d3c99da-55f8-4f61-b3d4-70208ea2480b	e36fa7e0-1ccf-48f0-9b07-6d50db24d35d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	42150907-0713-40ad-880d-ce31b676d7d7	55d5ea5d-fcdd-4bdf-ab6f-0528b1bc63f6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	2ae3bf9c-fc2e-475b-862d-129928d3b74c	91ffdb42-6488-4961-9b7b-fc3a8c527503	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	13bfdf07-bce6-4bea-85a3-141d1a01dab7	253a5b94-c1bd-4fd8-a6bd-a01e425a8924	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	81984ba6-aeaf-4b27-a4b4-de7526a223c0	42d8a1cc-600b-4d98-8c68-65a8013f24a7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	c8156488-2f96-4130-98f0-5e2003f04471	1a64e53d-3e1f-4854-a517-911ca2706208	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	fc0cadc1-35f6-4725-82a8-a1750c69f576	70954d00-9dba-4060-9726-34cafab249e1	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	b8481eed-b9fb-4290-a5c3-71940453fdb7	b18dba1e-bb0a-45a1-98be-9960d7431122	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	3b33d0df-7bfe-480a-8ca2-6aa32a974eff	69346bc2-37e6-490f-9a47-09b1c4036bf3	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	7ec6b30c-a3fd-4faa-8b41-28f3758e1602	d9b89444-1dd5-41b7-9a7e-df0f6e770f04	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	d31337cb-42ab-4027-9463-b3582807d11f	eb6d3b21-33fe-4785-9a40-1f8d6a1ee048	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	939ee1e0-fd63-4de5-bdbe-dc641d4276c5	68a1eaac-89c6-44ca-be3e-46899b27be76	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	2b798681-f1c1-4243-b504-1413e5859a1f	2020c14d-99c9-40aa-8bbc-8f89a9493339	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	86a80ae4-8c42-41ad-8b93-1b8d18ceb551	42cfcba3-96b2-4155-9c59-25b2b1ec0bc5	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	99b86ca9-aa78-4589-8520-f7bc76ab55b8	62141c8a-60c0-46f2-8795-617bde44815a	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	92204f20-1222-472e-be5b-2450e83f9a94	e5452da4-9cde-47ae-8408-ea346ef6969e	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	f6b1bac2-8ac9-431d-ae26-22f3d085b124	87a24493-2bde-4ac8-b076-8382cf2722d4	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	bc629c27-aa0d-4f3c-95ce-df35233a9073	85704d1b-9e5b-4dce-8775-2d4816501b51	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	940f1ca0-f9f5-4108-9e91-a89b75eb9f58	dcdd6c4f-6880-4243-b093-898d1aba2889	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	9d68fbfe-f1e4-44bf-853d-3582fbf4a452	c5189eec-4114-4d1e-8c27-402caed35b2c	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	6b1b69cd-0d9c-42ec-a6cb-98564324c6b0	e984aad2-fde8-4d2e-82e7-dfad95862059	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	6077caa3-5607-4fd4-9fb5-c4a8b365efcc	11ae5fde-c719-406a-b64c-b25538fe4960	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	c670e0e3-f7e7-4d7d-a013-14bcceaa7169	1e675c9a-0d2d-4262-9acd-976e5813df8b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	b8dab2a7-59a9-4a21-b972-81439dba5a01	fc5b2789-a36c-49c8-b190-67be29651ad1	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	79b0681c-2917-4ad5-af43-716a2b843b03	81d73ad1-1cc1-4c7d-a91c-bc8eb4d8bb8e	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	1b057e21-a8f9-4df0-b5d0-0e7f2904aa7a	b9c62975-b398-47d3-96f0-8365d0cb508b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	0754f750-df33-40a1-84f7-78cd0e9c1da6	57d7c9bc-8448-4cfe-8740-307a8b6793e6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	6efc4955-6651-4925-9941-d3782ea5e9d3	6ef6c070-efb3-4b22-85e9-bcecefbac791	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	80496d5e-0010-4931-bb8b-9be25e8d9469	d3118b94-392c-4fab-81e3-a74fbcbb33c0	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
2a3d5238-7201-446a-ac87-f82604010426	c09004bf-0992-4594-8d60-70cf67f192c2	e317ee8c-008e-40ac-9600-c10c9d96ecdb	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
569d8080-d875-4d7e-9fd7-6476bacb54da	2a00ee1a-397c-486f-a108-ba282fa51b03	21d7beda-cdd6-4934-8db8-ccdffa4208f1	2026-08-17 13:07:34.759648+08	2026-08-17 13:07:34.759648+08
2a3d5238-7201-446a-ac87-f82604010426	2a00ee1a-397c-486f-a108-ba282fa51b03	0e18e846-79f8-4797-8804-763773fd178f	2026-08-17 13:07:34.759648+08	2026-08-17 13:07:34.759648+08
\.


--
-- Data for Name: roles; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.roles (code, name_mn, id, created_at, updated_at) FROM stdin;
cashier	Түгээгч	0199301a-4fb1-4f50-88d2-5226c37ac559	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
owner	Admin	2a3d5238-7201-446a-ac87-f82604010426	2026-08-17 03:57:57.461784+08	2026-08-18 02:15:53.779802+08
manager	Нягтлан	569d8080-d875-4d7e-9fd7-6476bacb54da	2026-08-17 03:57:57.461784+08	2026-08-18 02:15:53.779802+08
\.


--
-- Data for Name: sale_items; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.sale_items (sale_id, line_no, item_type, fuel_id, tank_id, pump_id, nozzle_id, product_id, name_snapshot, qty, unit_price, amount, unit_cost, cogs_amount, refunded_qty, id, created_at, updated_at) FROM stdin;
9669e532-1cdd-4e15-9f5e-b9e12f9bd17d	1	fuel	c1d6e693-3f8b-43a4-bc1b-46e9431db264	e77a6891-1f46-418f-9b0e-cc8192efc8d8	\N	\N	\N	АИ-92	500.000	2900.00	1450000.00	2482.142857	1241071.43	0.000	18b2087b-e9a2-4651-9f0f-85de71703adf	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
9669e532-1cdd-4e15-9f5e-b9e12f9bd17d	2	product	\N	\N	\N	\N	e0da3098-6a08-4dc5-95f4-46128fae6806	Антифриз ногоон 4л	2.000	42000.00	84000.00	29000.000000	58000.00	0.000	7a3dbe4f-1792-4734-980f-464bed5bdab0	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
c1a85e9a-5a73-4a70-8691-1f0f90b7098d	1	fuel	c1d6e693-3f8b-43a4-bc1b-46e9431db264	e77a6891-1f46-418f-9b0e-cc8192efc8d8	\N	0c934906-05eb-4e8b-bded-2f9377d8efcc	\N	АИ-92	9500.000	2940.00	27930000.00	2482.142857	23580357.14	0.000	422e1540-1ee4-4edc-bcb3-d4e4c41b769b	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
02734b52-a7ee-4fcb-9761-0fa713e24137	1	product	\N	\N	\N	\N	e0da3098-6a08-4dc5-95f4-46128fae6806	Антифриз ногоон 4л	1.000	42000.00	42000.00	29000.000000	29000.00	0.000	9347ad86-641c-428c-9604-cb53ba33939d	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
\.


--
-- Data for Name: sales; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.sales (number, shift_id, cashier_id, sale_type, status, subtotal, vat_amount, total, cogs_total, customer_id, contract_id, note, completed_at, id, created_at, updated_at, branch_id) FROM stdin;
1	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	mixed	completed	1394545.45	139454.55	1534000.00	1299071.43	22277089-5c93-4c72-815c-c19196658f37	636e4521-0375-4557-85c8-74d0187cbaa3	\N	2026-08-17 12:00:01.500778+08	9669e532-1cdd-4e15-9f5e-b9e12f9bd17d	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
2	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	fuel	completed	25390909.09	2539090.91	27930000.00	23580357.14	\N	\N	\N	2026-08-17 12:00:01.567483+08	c1a85e9a-5a73-4a70-8691-1f0f90b7098d	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
3	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	store	completed	38181.82	3818.18	42000.00	29000.00	\N	\N	\N	2026-08-17 12:00:01.587475+08	02734b52-a7ee-4fcb-9761-0fa713e24137	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
\.


--
-- Data for Name: settings; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.settings (key, value, description, id, created_at, updated_at) FROM stdin;
station_name	{"value": "Колонк ШТС"}	ШТС-ийн нэр	34b8a644-d3f2-4b48-afc9-8bbeeff7d442	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
station_address	{"value": ""}	ШТС-ийн хаяг	a03b9ca0-3437-4b99-a6fd-e75763d7f636	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
station_phone	{"value": ""}	Холбоо барих утас	6558cae5-d67d-4e2e-b9a1-2eb2d84f5860	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
vat_payer_no	{"value": ""}	НӨАТ төлөгчийн дугаар	316f71fe-ccbd-47ca-ae04-cf88f0f8eb80	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
vat_rate	{"value": "0.10"}	НӨАТ-ын хувь (0.10 = 10%)	5fe95681-4ce6-4347-89d5-9de35c3d709e	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
receipt_footer	{"value": "Та бүхэнд баярлалаа. Дахин уулзая!"}	Баримтын хөлийн текст	a6e8da4c-cb85-4724-b634-d98cf78fe37f	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
printer_width_mm	{"value": 80}	Принтерийн цаасны өргөн (мм)	dfc8fee6-4fb8-4542-9dd5-60a6597f8fc2	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
ebarimt_enabled	{"value": true}	И-баримт илгээх эсэх	9aecc298-8e9b-4b28-a26b-bfbaa257dff7	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
ebarimt_pos_id	{"value": ""}	И-баримтын ПОС дугаар	7d3ade74-570f-4b70-abec-ab3606e7e3b2	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
auto_print_receipt	{"value": true}	Баримтыг автоматаар хэвлэх	21186048-edd0-402d-861f-3203a702055d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
currency_symbol	{"value": "₮"}	Мөнгөн тэмдэгт	0c749e26-a340-4447-9c13-87b4a87a5914	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
backup_dir	{"value": ""}	Нөөцлөлт хадгалах хавтас	a30cb6be-8b13-406f-ad4b-705ec1351927	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
payroll_si_employee_rate	{"value": "0.115"}	НДШ — ажилтны хувь (0.115 = 11.5%)	bdcdd4e9-169f-4386-ad47-eb351130df8e	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
payroll_si_employer_rate	{"value": "0.125"}	НДШ — ажил олгогчийн хувь (0.125 = 12.5%)	cb29ccc8-dbb5-48f9-b915-55428b87c1ed	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
payroll_pit_rate	{"value": "0.10"}	ХХОАТ-ын хувь (0.10 = 10%)	8be137d1-838f-41fa-9ba1-fa8dcdfc2af2	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
payroll_pit_credit	{"value": "20000"}	ХХОАТ-ын сарын хөнгөлөлт (₮)	9a0cd64a-1066-440c-b849-4bf629b4cb4e	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
payroll_si_base_cap	{"value": "0"}	НДШ бодох дээд хязгаар (0 = хязгааргүй)	c3d8a0e1-f2ae-4cdb-ad5c-361ce6154fe0	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
shift_totalizer_enabled	{"value": false}	Ээлжид тоолуурын заалт бүртгэх эсэх	6f515ff9-fd04-4e92-877d-9ea59d1bcd6f	2026-08-17 03:57:57.461784+08	2026-08-17 10:27:37.556968+08
pos_sales_enabled	{"value": false}	ПОС борлуулалт ашиглах эсэх (унтраавал түгээгчийн өдрийн горим)	065f9286-1775-4de3-839a-e1a9fed6f9e5	2026-08-17 03:57:57.461784+08	2026-08-17 23:35:13.543376+08
\.


--
-- Data for Name: shift_attachments; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.shift_attachments (id, shift_id, kind, ref_id, file_name, original_name, content_type, size_bytes, uploaded_by, created_at, updated_at) FROM stdin;
0bd5aa74-bf93-4d47-be1a-aade2e368e5d	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	open	\N	bed7b107f9944429b349610dc6ce5a11.jpg	17869357468905629259387934617931.jpg	image/jpeg	5332854	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 11:03:04.981582+08	2026-08-17 11:03:04.981582+08
\.


--
-- Data for Name: shift_closings; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.shift_closings (id, shift_id, settlement_vat, settlement_novat, fuel_total, credit_total, oil_total, fuel_sale_id, oil_sale_id, note, created_by, created_at, updated_at, transfer_total, approved_by, approved_at, approval_note) FROM stdin;
ccbd1bad-b2c1-4248-b046-c89647e1b6d3	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	50000.00	40000.00	29400000.00	1534000.00	42000.00	c1a85e9a-5a73-4a70-8691-1f0f90b7098d	02734b52-a7ee-4fcb-9761-0fa713e24137	???? - ???? ??????	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:00:01.452484+08	2026-08-17 13:14:27.170136+08	0.00	\N	\N	\N
\.


--
-- Data for Name: shift_price_marks; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.shift_price_marks (id, shift_id, nozzle_id, reading, old_price, new_price, note, created_by, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: shift_tank_levels; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.shift_tank_levels (shift_id, tank_id, phase, dip_liters, book_liters, variance_l, id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: shifts; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.shifts (number, status, opened_by, closed_by, opened_at, closed_at, opening_cash, declared_cash, expected_cash, cash_over_short, note, id, created_at, updated_at, branch_id) FROM stdin;
1	closed	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 11:03:04.690925+08	2026-08-17 12:00:01.640177+08	500000.00	20000.00	28372000.00	-28352000.00	\N	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	2026-08-17 11:03:04.675143+08	2026-08-17 12:00:01.452484+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
2	open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	\N	2026-08-17 12:27:33.912147+08	\N	0.00	\N	\N	\N	\N	2f1934fb-8b7e-4d0c-8de6-286fc9ed2fd0	2026-08-17 12:27:33.895302+08	2026-08-17 12:27:33.895302+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
\.


--
-- Data for Name: suppliers; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.suppliers (name, register_no, phone, bank_account, address, is_active, id, created_at, updated_at) FROM stdin;
НИК ХХК	2801234	7000-1234	5001234567	\N	t	d7ce8c7c-4a82-4401-a52f-43bb076e7aa5	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
Петровис ХХК	2805678	7000-5678	5005678901	\N	t	040a53db-e8ab-4663-b0fb-185947be8fba	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
Шунхлай ХХК	2809012	7000-9012	5009012345	\N	t	e1070fe4-2104-4b21-89b3-7558157bb0c4	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
Ундаа Дистрибьютер ХХК	2811111	9911-1111	5011111111	\N	t	eebbf51f-69d4-4291-84aa-f23b4845b73e	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
\.


--
-- Data for Name: sync_outbox; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.sync_outbox (aggregate_type, aggregate_id, event_type, payload, processed_at, id, created_at, updated_at) FROM stdin;
fuel_receipt	ee0cc1a9-149b-44a8-bc94-390ecde73348	FUEL_RECEIPT_POSTED	{"liters": "14000.000", "number": 1, "fuel_id": "c1d6e693-3f8b-43a4-bc1b-46e9431db264", "tank_id": "e77a6891-1f46-418f-9b0e-cc8192efc8d8", "subtotal": "34750000.00", "posted_at": "2026-08-16T19:57:58.610944+00:00", "unit_cost": "2450.000000", "vat_amount": "3475000.00", "supplier_id": "d7ce8c7c-4a82-4401-a52f-43bb076e7aa5", "total_gross": "38225000.00", "freight_cost": "450000.00", "receipt_date": "2026-08-14", "ap_invoice_id": "21f54449-4ec3-4de1-ae48-0f82b7190ee3", "fuel_receipt_id": "ee0cc1a9-149b-44a8-bc94-390ecde73348", "journal_entry_id": "6e3871ab-442f-4745-b9d9-c592875e7758", "landed_unit_cost": "2482.142857"}	\N	5c600fe6-ef06-4489-9a6a-eaec21bd8523	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
fuel_receipt	c7e0cf19-4db2-49f4-83dc-9ccead73b182	FUEL_RECEIPT_POSTED	{"liters": "10500.000", "number": 2, "fuel_id": "23a852ce-0998-4bac-b7f5-47f66cb855eb", "tank_id": "43a5b093-914f-4d5f-8869-1545cccd0c29", "subtotal": "28520000.00", "posted_at": "2026-08-16T19:57:58.622144+00:00", "unit_cost": "2680.000000", "vat_amount": "2852000.00", "supplier_id": "d7ce8c7c-4a82-4401-a52f-43bb076e7aa5", "total_gross": "31372000.00", "freight_cost": "380000.00", "receipt_date": "2026-08-14", "ap_invoice_id": "a38066d6-c780-40d6-a5a1-921b8a62956c", "fuel_receipt_id": "c7e0cf19-4db2-49f4-83dc-9ccead73b182", "journal_entry_id": "6eef20ba-8ac7-40f8-898b-167ed37a8b3c", "landed_unit_cost": "2716.190476"}	\N	ce45a59c-665a-4812-b738-577e87a8eed4	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
fuel_receipt	d95e2d4a-7335-4c63-bd85-8a657f822f37	FUEL_RECEIPT_POSTED	{"liters": "16000.000", "number": 3, "fuel_id": "49fd9163-cbef-463e-89bf-a382f6769767", "tank_id": "8f351557-542e-4c7f-86c4-e011cdde4516", "subtotal": "41480000.00", "posted_at": "2026-08-16T19:57:58.630288+00:00", "unit_cost": "2560.000000", "vat_amount": "4148000.00", "supplier_id": "d7ce8c7c-4a82-4401-a52f-43bb076e7aa5", "total_gross": "45628000.00", "freight_cost": "520000.00", "receipt_date": "2026-08-14", "ap_invoice_id": "a10964ef-8f4f-4b38-a097-5cd74a6584cc", "fuel_receipt_id": "d95e2d4a-7335-4c63-bd85-8a657f822f37", "journal_entry_id": "f8a06132-fac6-458b-afdf-89133fe07f24", "landed_unit_cost": "2592.500000"}	\N	b126edea-e033-4459-b8fa-13e19b2b0fad	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
purchase	d9df4ad5-20ae-4343-a95a-f7efcecd02e0	PURCHASE_POSTED	{"items": [{"qty": "24.000", "amount": "1392000.00", "unit_cost": "58000.000000", "product_id": "4205ad35-3737-4eaf-9616-c576082f6b0a"}, {"qty": "30.000", "amount": "1590000.00", "unit_cost": "53000.000000", "product_id": "03d8206e-0ddd-4809-bedc-339b7cd5fcd3"}, {"qty": "48.000", "amount": "744000.00", "unit_cost": "15500.000000", "product_id": "601f3fd1-ecf1-40c9-a6ff-b92c26fd32e6"}, {"qty": "20.000", "amount": "360000.00", "unit_cost": "18000.000000", "product_id": "fd5fabc8-c097-4d63-aaf5-80750ac08591"}, {"qty": "18.000", "amount": "234000.00", "unit_cost": "13000.000000", "product_id": "8d346bf0-da65-4362-a486-103422de94c2"}, {"qty": "25.000", "amount": "275000.00", "unit_cost": "11000.000000", "product_id": "6df82dc1-1c2f-4fb3-880a-2f7154f9d063"}, {"qty": "22.000", "amount": "638000.00", "unit_cost": "29000.000000", "product_id": "e0da3098-6a08-4dc5-95f4-46128fae6806"}, {"qty": "16.000", "amount": "496000.00", "unit_cost": "31000.000000", "product_id": "714e4437-a3ad-44ea-bb50-c904386d9c82"}, {"qty": "35.000", "amount": "297500.00", "unit_cost": "8500.000000", "product_id": "d9b0db4b-0c9a-43d8-88aa-fa4966a8d4d9"}, {"qty": "40.000", "amount": "400000.00", "unit_cost": "10000.000000", "product_id": "e421bb83-b6bc-4557-82f6-f2a5618129ce"}, {"qty": "6.000", "amount": "1350000.00", "unit_cost": "225000.000000", "product_id": "252150ac-5039-4e84-b958-b2a9d32c04fc"}, {"qty": "4.000", "amount": "1120000.00", "unit_cost": "280000.000000", "product_id": "3859b7ec-0e00-47cd-b5d7-855ce57a5b40"}, {"qty": "30.000", "amount": "210000.00", "unit_cost": "7000.000000", "product_id": "e59acdf4-66d3-4d04-b22d-19bcaf57d447"}, {"qty": "24.000", "amount": "264000.00", "unit_cost": "11000.000000", "product_id": "5fd54064-dd7b-4480-8b16-4e870cb04a49"}, {"qty": "120.000", "amount": "108000.00", "unit_cost": "900.000000", "product_id": "c135c570-7a28-49a8-a528-f23b6eea64ac"}, {"qty": "80.000", "amount": "128000.00", "unit_cost": "1600.000000", "product_id": "36842f30-734f-421b-b0f8-123ce58e6f8a"}, {"qty": "96.000", "amount": "201600.00", "unit_cost": "2100.000000", "product_id": "b5e0a9e1-5543-425b-bd00-7d62bb4ae1e8"}, {"qty": "72.000", "amount": "151200.00", "unit_cost": "2100.000000", "product_id": "0e9d5f69-7d29-49c4-a11d-062ba7422c99"}, {"qty": "48.000", "amount": "182400.00", "unit_cost": "3800.000000", "product_id": "a96c713f-6526-4297-9e17-af7bdc32744c"}, {"qty": "60.000", "amount": "132000.00", "unit_cost": "2200.000000", "product_id": "9c8fdd62-19a6-48bb-8359-3006f60d242c"}, {"qty": "36.000", "amount": "162000.00", "unit_cost": "4500.000000", "product_id": "50d04e7e-8304-4a4e-8245-aaf3554d0629"}, {"qty": "60.000", "amount": "180000.00", "unit_cost": "3000.000000", "product_id": "adb7e52f-6904-46cc-80bf-3521f787d2f6"}, {"qty": "50.000", "amount": "115000.00", "unit_cost": "2300.000000", "product_id": "b5d63389-fbc4-4a30-bfbd-884a4493f80d"}, {"qty": "45.000", "amount": "153000.00", "unit_cost": "3400.000000", "product_id": "39ae8b3c-09d1-4812-82b9-9cc529dc1cbf"}, {"qty": "30.000", "amount": "165000.00", "unit_cost": "5500.000000", "product_id": "3583bd45-3f4a-4b9c-973b-7769277755d1"}, {"qty": "80.000", "amount": "96000.00", "unit_cost": "1200.000000", "product_id": "cbe4ec5f-4b93-432e-b0c9-81615c5dade1"}, {"qty": "20.000", "amount": "40000.00", "unit_cost": "2000.000000", "product_id": "4fd12e88-8927-429d-ae1c-f0ff508feb1f"}, {"qty": "50.000", "amount": "400000.00", "unit_cost": "8000.000000", "product_id": "f6134a7c-af69-477f-8535-3d2a7ad98f35"}, {"qty": "40.000", "amount": "284000.00", "unit_cost": "7100.000000", "product_id": "c1d58096-45a1-44e5-85f6-0040f634313d"}, {"qty": "35.000", "amount": "262500.00", "unit_cost": "7500.000000", "product_id": "a68aad98-5af3-4ce7-b1c0-c49ba2c12a16"}, {"qty": "15.000", "amount": "240000.00", "unit_cost": "16000.000000", "product_id": "1aa68dba-e777-4d64-b4e2-9b1be2980f79"}, {"qty": "5.000", "amount": "490000.00", "unit_cost": "98000.000000", "product_id": "35fab42d-9792-412e-88e2-d30112757f12"}, {"qty": "10.000", "amount": "330000.00", "unit_cost": "33000.000000", "product_id": "cf458ed4-1a3f-42ba-af59-bece34408933"}, {"qty": "8.000", "amount": "496000.00", "unit_cost": "62000.000000", "product_id": "cfc4d796-2177-4106-9cee-5ddfef157906"}, {"qty": "12.000", "amount": "168000.00", "unit_cost": "14000.000000", "product_id": "d99fadd9-9f9b-4730-8fec-56df3776ddcd"}, {"qty": "40.000", "amount": "152000.00", "unit_cost": "3800.000000", "product_id": "266fe348-d6f0-4083-83ae-dff3e8679bc5"}, {"qty": "60.000", "amount": "150000.00", "unit_cost": "2500.000000", "product_id": "21635e50-b235-489e-bc6c-f67cde6aeab8"}, {"qty": "20.000", "amount": "240000.00", "unit_cost": "12000.000000", "product_id": "47a733fd-b7dc-472c-b2ce-4e96edf207c4"}, {"qty": "14.000", "amount": "259000.00", "unit_cost": "18500.000000", "product_id": "96996409-5f2a-4770-bac1-abdf2113211e"}, {"qty": "18.000", "amount": "176400.00", "unit_cost": "9800.000000", "product_id": "d8f3bc7f-4b11-4c43-8cfe-be16f6af95cc"}], "number": 1, "subtotal": "14832600.00", "posted_at": "2026-08-16T19:57:58.792529+00:00", "vat_amount": "1483260.00", "purchase_id": "d9df4ad5-20ae-4343-a95a-f7efcecd02e0", "supplier_id": "eebbf51f-69d4-4291-84aa-f23b4845b73e", "total_gross": "16315860.00", "ap_invoice_id": "e107dc4b-99bf-49a4-8219-78bfeb140be7", "purchase_date": "2026-08-15", "journal_entry_id": "73fc5981-284c-4a35-9ef7-29df469e4f27"}	\N	c986f40f-8e7d-4211-979e-2abc65fc2f87	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
expense	32571860-3fb6-4c7f-a60b-6442f6ae92d2	EXPENSE_POSTED	{"total": "480000.00", "number": 1, "expense_id": "32571860-3fb6-4c7f-a60b-6442f6ae92d2", "account_code": "5311", "expense_date": "2026-08-17", "payment_method": "cash"}	\N	106b6305-b24a-403b-9e4d-4f5d99bfd4db	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
expense	769c96a0-ad2b-4daf-94ac-cc2baf433f60	EXPENSE_POSTED	{"total": "180000.00", "number": 2, "expense_id": "769c96a0-ad2b-4daf-94ac-cc2baf433f60", "account_code": "5312", "expense_date": "2026-08-17", "payment_method": "cash"}	\N	cb69452d-fec8-4578-8b65-dce34488976b	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
expense	64806296-2238-4269-8391-e3f861277648	EXPENSE_POSTED	{"total": "1500000.00", "number": 3, "expense_id": "64806296-2238-4269-8391-e3f861277648", "account_code": "5321", "expense_date": "2026-08-17", "payment_method": "bank"}	\N	6afc8970-0ee0-4b41-8ffd-191e1759a544	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
expense	fe0bf502-8ba4-4a8b-bd7d-20b32947eef6	EXPENSE_POSTED	{"total": "90000.00", "number": 4, "expense_id": "fe0bf502-8ba4-4a8b-bd7d-20b32947eef6", "account_code": "5313", "expense_date": "2026-08-17", "payment_method": "cash"}	\N	122fc945-5eda-46c9-b95c-4417845e6eb6	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
shift	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	SHIFT_OPENED	{"number": 1, "shift_id": "88b5adf4-f2eb-47de-89e9-0d753c95aa0d", "opened_at": "2026-08-17T03:03:04.690925+00:00", "opened_by": "daf81bad-2f51-4c92-9c7f-a43a9b882f5d", "tank_dips": [], "opening_cash": "500000.00", "totalizer_readings": [{"reading": "100000.000", "nozzle_id": "0c934906-05eb-4e8b-bded-2f9377d8efcc"}, {"reading": "0.000", "nozzle_id": "6d24df68-0af6-4cbf-8f1b-e65b2507b57f"}, {"reading": "0.000", "nozzle_id": "c051e10d-4a06-4565-a3c2-99c0243b9cf7"}, {"reading": "0.000", "nozzle_id": "d9e5c598-dc94-462e-9240-095bf84fa703"}, {"reading": "0.000", "nozzle_id": "21a0e617-cadf-4b73-b0cb-c0cca44223d4"}, {"reading": "0.000", "nozzle_id": "882a249d-276a-4e0f-bf5e-a727ac9275bd"}, {"reading": "0.000", "nozzle_id": "d4f03de0-9946-41b2-b75b-d45fcd3a85f8"}]}	\N	0c1d25cd-a7c7-4553-8ef6-2316a5bfe95f	2026-08-17 11:03:04.675143+08	2026-08-17 11:03:04.675143+08
sale	9669e532-1cdd-4e15-9f5e-b9e12f9bd17d	SALE_COMPLETED	{"items": [{"qty": "500.000", "name": "АИ-92", "amount": "1450000.00", "line_no": 1, "item_type": "fuel", "unit_price": "2900.00"}, {"qty": "2.000", "name": "Антифриз ногоон 4л", "amount": "84000.00", "line_no": 2, "item_type": "product", "unit_price": "42000.00"}], "total": "1534000.00", "number": 1, "sale_id": "9669e532-1cdd-4e15-9f5e-b9e12f9bd17d", "payments": [{"amount": "1534000.00", "method": "contract"}], "shift_id": "88b5adf4-f2eb-47de-89e9-0d753c95aa0d", "subtotal": "1394545.45", "sale_type": "mixed", "cashier_id": "daf81bad-2f51-4c92-9c7f-a43a9b882f5d", "cogs_total": "1299071.43", "vat_amount": "139454.55", "contract_id": "636e4521-0375-4557-85c8-74d0187cbaa3", "customer_id": "22277089-5c93-4c72-815c-c19196658f37", "completed_at": "2026-08-17T04:00:01.500778+00:00"}	\N	14f60ba8-1117-4359-8752-ee229ae96b0c	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
sale	c1a85e9a-5a73-4a70-8691-1f0f90b7098d	SALE_COMPLETED	{"items": [{"qty": "9500.000", "name": "АИ-92", "amount": "27930000.00", "line_no": 1, "item_type": "fuel", "unit_price": "2940.00"}], "total": "27930000.00", "number": 2, "sale_id": "c1a85e9a-5a73-4a70-8691-1f0f90b7098d", "payments": [{"amount": "90000.00", "method": "card"}, {"amount": "27840000.00", "method": "cash"}], "shift_id": "88b5adf4-f2eb-47de-89e9-0d753c95aa0d", "subtotal": "25390909.09", "sale_type": "fuel", "cashier_id": "daf81bad-2f51-4c92-9c7f-a43a9b882f5d", "cogs_total": "23580357.14", "vat_amount": "2539090.91", "contract_id": null, "customer_id": null, "completed_at": "2026-08-17T04:00:01.567483+00:00"}	\N	49e09b5f-1ebb-44d9-a49d-317a0c71bfe1	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
sale	02734b52-a7ee-4fcb-9761-0fa713e24137	SALE_COMPLETED	{"items": [{"qty": "1.000", "name": "Антифриз ногоон 4л", "amount": "42000.00", "line_no": 1, "item_type": "product", "unit_price": "42000.00"}], "total": "42000.00", "number": 3, "sale_id": "02734b52-a7ee-4fcb-9761-0fa713e24137", "payments": [{"amount": "42000.00", "method": "cash"}], "shift_id": "88b5adf4-f2eb-47de-89e9-0d753c95aa0d", "subtotal": "38181.82", "sale_type": "store", "cashier_id": "daf81bad-2f51-4c92-9c7f-a43a9b882f5d", "cogs_total": "29000.00", "vat_amount": "3818.18", "contract_id": null, "customer_id": null, "completed_at": "2026-08-17T04:00:01.587475+00:00"}	\N	c40a8495-0cee-41b2-b228-c324d11b6fa5	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
ar_payment	093f9796-ba1d-43ff-89ff-34a3064664b0	AR_RECEIPT	{"amount": "400000.00", "contract_id": "636e4521-0375-4557-85c8-74d0187cbaa3", "customer_id": "22277089-5c93-4c72-815c-c19196658f37", "received_to": "bank", "payment_date": "2026-08-17", "ar_invoice_id": null, "ar_payment_id": "093f9796-ba1d-43ff-89ff-34a3064664b0"}	\N	6a60e248-caba-4dd6-9831-b45250011e5c	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
expense	a59b18ae-a327-4e51-bd69-7aa243642096	EXPENSE_POSTED	{"total": "10000.00", "number": 5, "expense_id": "a59b18ae-a327-4e51-bd69-7aa243642096", "account_code": "5341", "expense_date": "2026-08-17", "payment_method": "cash"}	\N	b4a1cff8-5e67-4172-b86f-9dc99159f7e2	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
shift	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	SHIFT_CLOSED	{"number": 1, "shift_id": "88b5adf4-f2eb-47de-89e9-0d753c95aa0d", "closed_at": "2026-08-17T04:00:01.640177+00:00", "closed_by": "daf81bad-2f51-4c92-9c7f-a43a9b882f5d", "cash_sales": "27882000.00", "cash_refunds": "0.00", "opening_cash": "500000.00", "declared_cash": "20000.00", "expected_cash": "28372000.00", "tank_variances": [], "cash_over_short": "-28352000.00"}	\N	efdd4ef6-8332-4009-bdc3-142c64b9e0cd	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
shift	2f1934fb-8b7e-4d0c-8de6-286fc9ed2fd0	SHIFT_OPENED	{"number": 2, "shift_id": "2f1934fb-8b7e-4d0c-8de6-286fc9ed2fd0", "opened_at": "2026-08-17T04:27:33.912147+00:00", "opened_by": "daf81bad-2f51-4c92-9c7f-a43a9b882f5d", "tank_dips": [], "opening_cash": "0.00", "totalizer_readings": [{"reading": "110000.000", "nozzle_id": "0c934906-05eb-4e8b-bded-2f9377d8efcc"}, {"reading": "0.000", "nozzle_id": "6d24df68-0af6-4cbf-8f1b-e65b2507b57f"}, {"reading": "0.000", "nozzle_id": "c051e10d-4a06-4565-a3c2-99c0243b9cf7"}, {"reading": "0.000", "nozzle_id": "d9e5c598-dc94-462e-9240-095bf84fa703"}, {"reading": "0.000", "nozzle_id": "21a0e617-cadf-4b73-b0cb-c0cca44223d4"}, {"reading": "0.000", "nozzle_id": "882a249d-276a-4e0f-bf5e-a727ac9275bd"}, {"reading": "0.000", "nozzle_id": "d4f03de0-9946-41b2-b75b-d45fcd3a85f8"}]}	\N	11230129-776d-47ec-9f8b-de17d91d1887	2026-08-17 12:27:33.895302+08	2026-08-17 12:27:33.895302+08
\.


--
-- Data for Name: tank_movements; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.tank_movements (tank_id, movement_type, liters, balance_after_l, unit_cost, ref_type, ref_id, note, id, created_at, updated_at) FROM stdin;
e77a6891-1f46-418f-9b0e-cc8192efc8d8	receipt	14000.000	14000.000	2482.142857	fuel_receipt	ee0cc1a9-149b-44a8-bc94-390ecde73348	\N	38965104-fce3-4618-b64c-9ea4308d59d2	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
43a5b093-914f-4d5f-8869-1545cccd0c29	receipt	10500.000	10500.000	2716.190476	fuel_receipt	c7e0cf19-4db2-49f4-83dc-9ccead73b182	\N	de4569bf-7ea5-4300-9bc3-1dee6f56429d	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
8f351557-542e-4c7f-86c4-e011cdde4516	receipt	16000.000	16000.000	2592.500000	fuel_receipt	d95e2d4a-7335-4c63-bd85-8a657f822f37	\N	f9393016-8a8a-4eb9-af71-b8b9ae80f9e1	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08
e77a6891-1f46-418f-9b0e-cc8192efc8d8	sale	-500.000	13500.000	2482.142857	sale	9669e532-1cdd-4e15-9f5e-b9e12f9bd17d	\N	d5b96534-7923-4d25-8613-7172719efab2	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
e77a6891-1f46-418f-9b0e-cc8192efc8d8	sale	-9500.000	4000.000	2482.142857	sale	c1a85e9a-5a73-4a70-8691-1f0f90b7098d	\N	fa2bca4b-2c42-4a8b-9562-39159aae342a	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08
\.


--
-- Data for Name: tanks; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.tanks (name, fuel_id, capacity_l, current_l, avg_cost, min_level_l, is_active, id, created_at, updated_at, branch_id) FROM stdin;
2-р сав (АИ-95)	23a852ce-0998-4bac-b7f5-47f66cb855eb	15000.000	10500.000	2716.190476	1500.000	t	43a5b093-914f-4d5f-8869-1545cccd0c29	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
3-р сав (Дизель)	49fd9163-cbef-463e-89bf-a382f6769767	20000.000	16000.000	2592.500000	2000.000	t	8f351557-542e-4c7f-86c4-e011cdde4516	2026-08-17 03:57:57.461784+08	2026-08-17 03:57:57.461784+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
1-р сав (АИ-92)	c1d6e693-3f8b-43a4-bc1b-46e9431db264	20000.000	4000.000	2482.142857	2000.000	t	e77a6891-1f46-418f-9b0e-cc8192efc8d8	2026-08-17 03:57:57.461784+08	2026-08-17 12:00:01.452484+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
40 тн	c1d6e693-3f8b-43a4-bc1b-46e9431db264	40000.000	0.000	0.000000	500.000	t	b0c378c1-9d80-459e-8301-78a30c6df789	2026-08-17 17:16:39.371577+08	2026-08-17 17:17:29.818459+08	1f410c57-800a-4922-afc4-b9d5258cfff3
30 тн	49fd9163-cbef-463e-89bf-a382f6769767	30000.000	0.000	0.000000	500.000	t	c77bbf42-fd34-4f0e-8199-ec3cb27f3ceb	2026-08-17 17:17:51.050351+08	2026-08-17 17:17:51.050351+08	1f410c57-800a-4922-afc4-b9d5258cfff3
\.


--
-- Data for Name: totalizer_readings; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.totalizer_readings (nozzle_id, shift_id, reading, reading_type, recorded_by, recorded_at, id, created_at, updated_at, price_per_liter) FROM stdin;
0c934906-05eb-4e8b-bded-2f9377d8efcc	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	100000.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 11:03:04.690925+08	abeebc4c-6111-483e-80c7-103b263eca04	2026-08-17 11:03:04.675143+08	2026-08-17 11:03:04.675143+08	2940.00
6d24df68-0af6-4cbf-8f1b-e65b2507b57f	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	0.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 11:03:04.690925+08	6da9a6e8-fc8f-4b62-a717-837c84fb3b03	2026-08-17 11:03:04.675143+08	2026-08-17 11:03:04.675143+08	3180.00
c051e10d-4a06-4565-a3c2-99c0243b9cf7	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	0.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 11:03:04.690925+08	ee72ecf2-1242-47b8-9ad6-60fcbd10ecca	2026-08-17 11:03:04.675143+08	2026-08-17 11:03:04.675143+08	2940.00
d9e5c598-dc94-462e-9240-095bf84fa703	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	0.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 11:03:04.690925+08	49385572-5669-44ca-9b33-3543b8dbf933	2026-08-17 11:03:04.675143+08	2026-08-17 11:03:04.675143+08	3050.00
21a0e617-cadf-4b73-b0cb-c0cca44223d4	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	0.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 11:03:04.690925+08	de35a0a7-e588-4e55-9b92-3146bde9128b	2026-08-17 11:03:04.675143+08	2026-08-17 11:03:04.675143+08	3180.00
882a249d-276a-4e0f-bf5e-a727ac9275bd	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	0.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 11:03:04.690925+08	80be2166-4141-4c7e-bd65-945eb337d037	2026-08-17 11:03:04.675143+08	2026-08-17 11:03:04.675143+08	3050.00
d4f03de0-9946-41b2-b75b-d45fcd3a85f8	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	0.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 11:03:04.690925+08	0f54a658-947b-4c75-a8d6-bf1bb611d580	2026-08-17 11:03:04.675143+08	2026-08-17 11:03:04.675143+08	2940.00
0c934906-05eb-4e8b-bded-2f9377d8efcc	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	110000.000	shift_close	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:00:01.640177+08	2011113f-fdd6-45c9-bb87-79883365b0e6	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
6d24df68-0af6-4cbf-8f1b-e65b2507b57f	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	0.000	shift_close	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:00:01.640177+08	889b70e3-1416-44f4-8931-436e768e8b6c	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
c051e10d-4a06-4565-a3c2-99c0243b9cf7	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	0.000	shift_close	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:00:01.640177+08	49eb395a-4800-436d-bd60-7840248ea37c	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
d9e5c598-dc94-462e-9240-095bf84fa703	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	0.000	shift_close	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:00:01.640177+08	a0b3d955-e727-4019-8b6a-805217d85c69	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
21a0e617-cadf-4b73-b0cb-c0cca44223d4	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	0.000	shift_close	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:00:01.640177+08	7192d9e0-3119-4bd1-b941-69e62c5d30c5	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
882a249d-276a-4e0f-bf5e-a727ac9275bd	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	0.000	shift_close	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:00:01.640177+08	f1a7ce76-6690-479c-8541-c2af590d79ba	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
d4f03de0-9946-41b2-b75b-d45fcd3a85f8	88b5adf4-f2eb-47de-89e9-0d753c95aa0d	0.000	shift_close	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:00:01.640177+08	d899c22d-7b93-485a-a5b3-0e08546c5518	2026-08-17 12:00:01.452484+08	2026-08-17 12:00:01.452484+08	\N
0c934906-05eb-4e8b-bded-2f9377d8efcc	2f1934fb-8b7e-4d0c-8de6-286fc9ed2fd0	110000.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:27:33.912147+08	0acb90ed-f2b2-49e3-9609-ec7b05d7d6d6	2026-08-17 12:27:33.895302+08	2026-08-17 12:27:33.895302+08	2940.00
6d24df68-0af6-4cbf-8f1b-e65b2507b57f	2f1934fb-8b7e-4d0c-8de6-286fc9ed2fd0	0.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:27:33.912147+08	73f97a2e-ebef-4d4f-9ee6-2d7edef816b8	2026-08-17 12:27:33.895302+08	2026-08-17 12:27:33.895302+08	3180.00
c051e10d-4a06-4565-a3c2-99c0243b9cf7	2f1934fb-8b7e-4d0c-8de6-286fc9ed2fd0	0.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:27:33.912147+08	ad2d1691-36fa-43bc-908f-469c22a8b123	2026-08-17 12:27:33.895302+08	2026-08-17 12:27:33.895302+08	2940.00
d9e5c598-dc94-462e-9240-095bf84fa703	2f1934fb-8b7e-4d0c-8de6-286fc9ed2fd0	0.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:27:33.912147+08	0846a2be-85ce-4db1-980c-05704d9b0adf	2026-08-17 12:27:33.895302+08	2026-08-17 12:27:33.895302+08	3050.00
21a0e617-cadf-4b73-b0cb-c0cca44223d4	2f1934fb-8b7e-4d0c-8de6-286fc9ed2fd0	0.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:27:33.912147+08	866b5c15-0899-45ed-a742-0a3489d8dde4	2026-08-17 12:27:33.895302+08	2026-08-17 12:27:33.895302+08	3180.00
882a249d-276a-4e0f-bf5e-a727ac9275bd	2f1934fb-8b7e-4d0c-8de6-286fc9ed2fd0	0.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:27:33.912147+08	36d9d7cb-1b85-4076-a967-f301ac8422ed	2026-08-17 12:27:33.895302+08	2026-08-17 12:27:33.895302+08	3050.00
d4f03de0-9946-41b2-b75b-d45fcd3a85f8	2f1934fb-8b7e-4d0c-8de6-286fc9ed2fd0	0.000	shift_open	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 12:27:33.912147+08	d45b43cd-a8c9-4320-aadb-e64510f34edf	2026-08-17 12:27:33.895302+08	2026-08-17 12:27:33.895302+08	2940.00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: kolonk
--

COPY public.users (username, full_name, pin_hash, role_id, phone, is_active, last_login_at, id, created_at, updated_at, branch_id) FROM stdin;
tuya	Туяа	$2b$12$Jr1FGRae31PbuE6uaTYgwuUVaLiijkXLBUBud9o9.1Xk6Aql7v34i	0199301a-4fb1-4f50-88d2-5226c37ac559	\N	t	2026-08-18 10:22:45.573341+08	51d10ad8-c589-4ade-8292-b0e48351819d	2026-08-17 03:57:57.461784+08	2026-08-18 10:22:45.391752+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
dorj	Дорж	$2b$12$lQ0z/APjWTGOJDyPAwZdVuCx8SDfEbV3z69qVWvPhcoFX6TDKwOle	0199301a-4fb1-4f50-88d2-5226c37ac559	\N	t	2026-08-18 10:48:40.918068+08	daf81bad-2f51-4c92-9c7f-a43a9b882f5d	2026-08-17 03:57:57.461784+08	2026-08-18 10:48:40.716962+08	b0751ae1-4804-4d0a-a4c9-d99daa5fec69
saraa	Сараа	$2b$12$QnTJDvB/XnR4O48WYDFRQegZAvkQy3e413Iw4eKQDhNPC2U3wPni.	569d8080-d875-4d7e-9fd7-6476bacb54da	\N	t	2026-08-18 10:49:10.736436+08	4fa3b753-2c30-43f4-96ab-9601dc29172c	2026-08-17 03:57:57.461784+08	2026-08-18 10:49:10.537258+08	\N
bold	Болд	$2b$12$tXRuy6aW4ooDXSuhB4jT/u.wk9pXilzmUN16d4WtUMYKZbbUaNpRG	2a3d5238-7201-446a-ac87-f82604010426	\N	t	2026-08-18 11:40:54.564011+08	2703b8d8-048b-4340-bab3-9c882979afd2	2026-08-17 03:57:57.461784+08	2026-08-18 11:40:54.357656+08	\N
\.


--
-- Name: expense_number_seq; Type: SEQUENCE SET; Schema: public; Owner: kolonk
--

SELECT pg_catalog.setval('public.expense_number_seq', 5, true);


--
-- Name: journal_entry_no_seq; Type: SEQUENCE SET; Schema: public; Owner: kolonk
--

SELECT pg_catalog.setval('public.journal_entry_no_seq', 23, true);


--
-- Name: purchase_number_seq; Type: SEQUENCE SET; Schema: public; Owner: kolonk
--

SELECT pg_catalog.setval('public.purchase_number_seq', 2, true);


--
-- Name: receipt_number_seq; Type: SEQUENCE SET; Schema: public; Owner: kolonk
--

SELECT pg_catalog.setval('public.receipt_number_seq', 4, true);


--
-- Name: sale_number_seq; Type: SEQUENCE SET; Schema: public; Owner: kolonk
--

SELECT pg_catalog.setval('public.sale_number_seq', 3, true);


--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: ap_invoices ap_invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ap_invoices
    ADD CONSTRAINT ap_invoices_pkey PRIMARY KEY (id);


--
-- Name: ap_payments ap_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ap_payments
    ADD CONSTRAINT ap_payments_pkey PRIMARY KEY (id);


--
-- Name: ar_invoices ar_invoices_invoice_no_key; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ar_invoices
    ADD CONSTRAINT ar_invoices_invoice_no_key UNIQUE (invoice_no);


--
-- Name: ar_invoices ar_invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ar_invoices
    ADD CONSTRAINT ar_invoices_pkey PRIMARY KEY (id);


--
-- Name: ar_payments ar_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ar_payments
    ADD CONSTRAINT ar_payments_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: bank_accounts bank_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_accounts
    ADD CONSTRAINT bank_accounts_pkey PRIMARY KEY (id);


--
-- Name: bank_statement_config bank_statement_config_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_statement_config
    ADD CONSTRAINT bank_statement_config_pkey PRIMARY KEY (id);


--
-- Name: bank_statements bank_statements_fee_expense_id_key; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_statements
    ADD CONSTRAINT bank_statements_fee_expense_id_key UNIQUE (fee_expense_id);


--
-- Name: bank_statements bank_statements_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_statements
    ADD CONSTRAINT bank_statements_pkey PRIMARY KEY (id);


--
-- Name: bank_transactions bank_transactions_ar_payment_id_key; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_transactions
    ADD CONSTRAINT bank_transactions_ar_payment_id_key UNIQUE (ar_payment_id);


--
-- Name: bank_transactions bank_transactions_expense_id_key; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_transactions
    ADD CONSTRAINT bank_transactions_expense_id_key UNIQUE (expense_id);


--
-- Name: bank_transactions bank_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_transactions
    ADD CONSTRAINT bank_transactions_pkey PRIMARY KEY (id);


--
-- Name: branch_payment_methods branch_payment_methods_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.branch_payment_methods
    ADD CONSTRAINT branch_payment_methods_pkey PRIMARY KEY (id);


--
-- Name: branch_prices branch_prices_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.branch_prices
    ADD CONSTRAINT branch_prices_pkey PRIMARY KEY (id);


--
-- Name: branches branches_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.branches
    ADD CONSTRAINT branches_pkey PRIMARY KEY (id);


--
-- Name: contracts contracts_contract_no_key; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_contract_no_key UNIQUE (contract_no);


--
-- Name: contracts contracts_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_pkey PRIMARY KEY (id);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- Name: ebarimt_queue ebarimt_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ebarimt_queue
    ADD CONSTRAINT ebarimt_queue_pkey PRIMARY KEY (id);


--
-- Name: employee_advances employee_advances_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.employee_advances
    ADD CONSTRAINT employee_advances_pkey PRIMARY KEY (id);


--
-- Name: employees employees_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_pkey PRIMARY KEY (id);


--
-- Name: expenses expenses_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_pkey PRIMARY KEY (id);


--
-- Name: fuel_receipts fuel_receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.fuel_receipts
    ADD CONSTRAINT fuel_receipts_pkey PRIMARY KEY (id);


--
-- Name: fuels fuels_code_key; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.fuels
    ADD CONSTRAINT fuels_code_key UNIQUE (code);


--
-- Name: fuels fuels_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.fuels
    ADD CONSTRAINT fuels_pkey PRIMARY KEY (id);


--
-- Name: inventory_transactions inventory_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.inventory_transactions
    ADD CONSTRAINT inventory_transactions_pkey PRIMARY KEY (id);


--
-- Name: journal_entries journal_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.journal_entries
    ADD CONSTRAINT journal_entries_pkey PRIMARY KEY (id);


--
-- Name: journal_lines journal_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.journal_lines
    ADD CONSTRAINT journal_lines_pkey PRIMARY KEY (id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (id);


--
-- Name: payroll_lines payroll_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.payroll_lines
    ADD CONSTRAINT payroll_lines_pkey PRIMARY KEY (id);


--
-- Name: payroll_periods payroll_periods_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.payroll_periods
    ADD CONSTRAINT payroll_periods_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_code_key; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_code_key UNIQUE (code);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: price_changes price_changes_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.price_changes
    ADD CONSTRAINT price_changes_pkey PRIMARY KEY (id);


--
-- Name: product_branch_stocks product_branch_stocks_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.product_branch_stocks
    ADD CONSTRAINT product_branch_stocks_pkey PRIMARY KEY (id);


--
-- Name: product_categories product_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.product_categories
    ADD CONSTRAINT product_categories_pkey PRIMARY KEY (id);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: products products_sku_key; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_sku_key UNIQUE (sku);


--
-- Name: pump_nozzles pump_nozzles_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.pump_nozzles
    ADD CONSTRAINT pump_nozzles_pkey PRIMARY KEY (id);


--
-- Name: pumps pumps_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.pumps
    ADD CONSTRAINT pumps_pkey PRIMARY KEY (id);


--
-- Name: purchase_items purchase_items_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.purchase_items
    ADD CONSTRAINT purchase_items_pkey PRIMARY KEY (id);


--
-- Name: purchases purchases_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.purchases
    ADD CONSTRAINT purchases_pkey PRIMARY KEY (id);


--
-- Name: refund_items refund_items_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.refund_items
    ADD CONSTRAINT refund_items_pkey PRIMARY KEY (id);


--
-- Name: refunds refunds_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.refunds
    ADD CONSTRAINT refunds_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (id);


--
-- Name: roles roles_code_key; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_code_key UNIQUE (code);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: sale_items sale_items_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sale_items
    ADD CONSTRAINT sale_items_pkey PRIMARY KEY (id);


--
-- Name: sales sales_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_pkey PRIMARY KEY (id);


--
-- Name: settings settings_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_pkey PRIMARY KEY (id);


--
-- Name: shift_attachments shift_attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_attachments
    ADD CONSTRAINT shift_attachments_pkey PRIMARY KEY (id);


--
-- Name: shift_closings shift_closings_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_closings
    ADD CONSTRAINT shift_closings_pkey PRIMARY KEY (id);


--
-- Name: shift_closings shift_closings_shift_id_key; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_closings
    ADD CONSTRAINT shift_closings_shift_id_key UNIQUE (shift_id);


--
-- Name: shift_price_marks shift_price_marks_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_price_marks
    ADD CONSTRAINT shift_price_marks_pkey PRIMARY KEY (id);


--
-- Name: shift_tank_levels shift_tank_levels_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_tank_levels
    ADD CONSTRAINT shift_tank_levels_pkey PRIMARY KEY (id);


--
-- Name: shifts shifts_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT shifts_pkey PRIMARY KEY (id);


--
-- Name: suppliers suppliers_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.suppliers
    ADD CONSTRAINT suppliers_pkey PRIMARY KEY (id);


--
-- Name: sync_outbox sync_outbox_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sync_outbox
    ADD CONSTRAINT sync_outbox_pkey PRIMARY KEY (id);


--
-- Name: tank_movements tank_movements_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.tank_movements
    ADD CONSTRAINT tank_movements_pkey PRIMARY KEY (id);


--
-- Name: tanks tanks_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.tanks
    ADD CONSTRAINT tanks_pkey PRIMARY KEY (id);


--
-- Name: totalizer_readings totalizer_readings_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.totalizer_readings
    ADD CONSTRAINT totalizer_readings_pkey PRIMARY KEY (id);


--
-- Name: ar_invoices uq_ar_contract_period; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ar_invoices
    ADD CONSTRAINT uq_ar_contract_period UNIQUE (contract_id, period_start);


--
-- Name: bank_accounts uq_bank_account_number; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_accounts
    ADD CONSTRAINT uq_bank_account_number UNIQUE (account_number);


--
-- Name: branch_prices uq_branch_fuel_price; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.branch_prices
    ADD CONSTRAINT uq_branch_fuel_price UNIQUE (branch_id, fuel_id);


--
-- Name: branch_payment_methods uq_branch_payment_method; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.branch_payment_methods
    ADD CONSTRAINT uq_branch_payment_method UNIQUE (branch_id, method);


--
-- Name: branch_prices uq_branch_product_price; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.branch_prices
    ADD CONSTRAINT uq_branch_product_price UNIQUE (branch_id, product_id);


--
-- Name: journal_entries uq_journal_source_event; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.journal_entries
    ADD CONSTRAINT uq_journal_source_event UNIQUE (source_type, source_id, event_type);


--
-- Name: payroll_lines uq_payroll_line; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.payroll_lines
    ADD CONSTRAINT uq_payroll_line UNIQUE (period_id, employee_id);


--
-- Name: payroll_periods uq_payroll_period; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.payroll_periods
    ADD CONSTRAINT uq_payroll_period UNIQUE (year, month);


--
-- Name: product_branch_stocks uq_product_branch; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.product_branch_stocks
    ADD CONSTRAINT uq_product_branch UNIQUE (product_id, branch_id);


--
-- Name: pumps uq_pump_branch_number; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.pumps
    ADD CONSTRAINT uq_pump_branch_number UNIQUE (branch_id, number);


--
-- Name: pump_nozzles uq_pump_nozzle; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.pump_nozzles
    ADD CONSTRAINT uq_pump_nozzle UNIQUE (pump_id, nozzle_number);


--
-- Name: role_permissions uq_role_permission; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT uq_role_permission UNIQUE (role_id, permission_id);


--
-- Name: shift_tank_levels uq_shift_tank_phase; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_tank_levels
    ADD CONSTRAINT uq_shift_tank_phase UNIQUE (shift_id, tank_id, phase);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: ix_accounts_code; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE UNIQUE INDEX ix_accounts_code ON public.accounts USING btree (code);


--
-- Name: ix_ap_invoices_status; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_ap_invoices_status ON public.ap_invoices USING btree (status);


--
-- Name: ix_ap_invoices_supplier_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_ap_invoices_supplier_id ON public.ap_invoices USING btree (supplier_id);


--
-- Name: ix_ap_payments_ap_invoice_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_ap_payments_ap_invoice_id ON public.ap_payments USING btree (ap_invoice_id);


--
-- Name: ix_ar_invoices_customer_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_ar_invoices_customer_id ON public.ar_invoices USING btree (customer_id);


--
-- Name: ix_ar_invoices_status; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_ar_invoices_status ON public.ar_invoices USING btree (status);


--
-- Name: ix_ar_payments_bank_account_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_ar_payments_bank_account_id ON public.ar_payments USING btree (bank_account_id);


--
-- Name: ix_ar_payments_customer_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_ar_payments_customer_id ON public.ar_payments USING btree (customer_id);


--
-- Name: ix_audit_logs_action; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_audit_logs_action ON public.audit_logs USING btree (action);


--
-- Name: ix_audit_logs_entity_type; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_audit_logs_entity_type ON public.audit_logs USING btree (entity_type);


--
-- Name: ix_bank_accounts_account_number; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_bank_accounts_account_number ON public.bank_accounts USING btree (account_number);


--
-- Name: ix_bank_accounts_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_bank_accounts_branch_id ON public.bank_accounts USING btree (branch_id);


--
-- Name: ix_bank_statements_account_number; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_bank_statements_account_number ON public.bank_statements USING btree (account_number);


--
-- Name: ix_bank_statements_bank_account_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_bank_statements_bank_account_id ON public.bank_statements USING btree (bank_account_id);


--
-- Name: ix_bank_statements_date_from; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_bank_statements_date_from ON public.bank_statements USING btree (date_from);


--
-- Name: ix_bank_transactions_contract_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_bank_transactions_contract_id ON public.bank_transactions USING btree (contract_id);


--
-- Name: ix_bank_transactions_customer_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_bank_transactions_customer_id ON public.bank_transactions USING btree (customer_id);


--
-- Name: ix_bank_transactions_statement_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_bank_transactions_statement_id ON public.bank_transactions USING btree (statement_id);


--
-- Name: ix_bank_transactions_txn_date; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_bank_transactions_txn_date ON public.bank_transactions USING btree (txn_date);


--
-- Name: ix_branch_payment_methods_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_branch_payment_methods_branch_id ON public.branch_payment_methods USING btree (branch_id);


--
-- Name: ix_branch_prices_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_branch_prices_branch_id ON public.branch_prices USING btree (branch_id);


--
-- Name: ix_branch_prices_fuel_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_branch_prices_fuel_id ON public.branch_prices USING btree (fuel_id);


--
-- Name: ix_branch_prices_product_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_branch_prices_product_id ON public.branch_prices USING btree (product_id);


--
-- Name: ix_branches_code; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE UNIQUE INDEX ix_branches_code ON public.branches USING btree (code);


--
-- Name: ix_branches_is_active; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_branches_is_active ON public.branches USING btree (is_active);


--
-- Name: ix_customers_district; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_customers_district ON public.customers USING btree (district);


--
-- Name: ix_customers_name; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_customers_name ON public.customers USING btree (name);


--
-- Name: ix_customers_phone; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_customers_phone ON public.customers USING btree (phone);


--
-- Name: ix_customers_province; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_customers_province ON public.customers USING btree (province);


--
-- Name: ix_ebarimt_queue_sale_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE UNIQUE INDEX ix_ebarimt_queue_sale_id ON public.ebarimt_queue USING btree (sale_id);


--
-- Name: ix_ebarimt_queue_status; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_ebarimt_queue_status ON public.ebarimt_queue USING btree (status);


--
-- Name: ix_employee_advances_advance_date; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_employee_advances_advance_date ON public.employee_advances USING btree (advance_date);


--
-- Name: ix_employee_advances_employee_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_employee_advances_employee_id ON public.employee_advances USING btree (employee_id);


--
-- Name: ix_employees_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_employees_branch_id ON public.employees USING btree (branch_id);


--
-- Name: ix_employees_full_name; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_employees_full_name ON public.employees USING btree (full_name);


--
-- Name: ix_employees_is_active; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_employees_is_active ON public.employees USING btree (is_active);


--
-- Name: ix_expenses_account_code; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_expenses_account_code ON public.expenses USING btree (account_code);


--
-- Name: ix_expenses_bank_account_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_expenses_bank_account_id ON public.expenses USING btree (bank_account_id);


--
-- Name: ix_expenses_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_expenses_branch_id ON public.expenses USING btree (branch_id);


--
-- Name: ix_expenses_expense_date; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_expenses_expense_date ON public.expenses USING btree (expense_date);


--
-- Name: ix_expenses_number; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_expenses_number ON public.expenses USING btree (number);


--
-- Name: ix_expenses_payment_method; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_expenses_payment_method ON public.expenses USING btree (payment_method);


--
-- Name: ix_expenses_status; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_expenses_status ON public.expenses USING btree (status);


--
-- Name: ix_fuel_receipts_number; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_fuel_receipts_number ON public.fuel_receipts USING btree (number);


--
-- Name: ix_fuel_receipts_status; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_fuel_receipts_status ON public.fuel_receipts USING btree (status);


--
-- Name: ix_inventory_transactions_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_inventory_transactions_branch_id ON public.inventory_transactions USING btree (branch_id);


--
-- Name: ix_inventory_transactions_product_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_inventory_transactions_product_id ON public.inventory_transactions USING btree (product_id);


--
-- Name: ix_journal_entries_entry_date; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_journal_entries_entry_date ON public.journal_entries USING btree (entry_date);


--
-- Name: ix_journal_entries_entry_no; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_journal_entries_entry_no ON public.journal_entries USING btree (entry_no);


--
-- Name: ix_journal_entries_event_type; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_journal_entries_event_type ON public.journal_entries USING btree (event_type);


--
-- Name: ix_journal_entries_source_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_journal_entries_source_id ON public.journal_entries USING btree (source_id);


--
-- Name: ix_journal_entries_source_type; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_journal_entries_source_type ON public.journal_entries USING btree (source_type);


--
-- Name: ix_journal_lines_account_code; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_journal_lines_account_code ON public.journal_lines USING btree (account_code);


--
-- Name: ix_journal_lines_dim_bank_account_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_journal_lines_dim_bank_account_id ON public.journal_lines USING btree (dim_bank_account_id);


--
-- Name: ix_journal_lines_dim_customer_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_journal_lines_dim_customer_id ON public.journal_lines USING btree (dim_customer_id);


--
-- Name: ix_journal_lines_dim_fuel_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_journal_lines_dim_fuel_id ON public.journal_lines USING btree (dim_fuel_id);


--
-- Name: ix_journal_lines_dim_supplier_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_journal_lines_dim_supplier_id ON public.journal_lines USING btree (dim_supplier_id);


--
-- Name: ix_journal_lines_entry_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_journal_lines_entry_id ON public.journal_lines USING btree (entry_id);


--
-- Name: ix_payments_method; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_payments_method ON public.payments USING btree (method);


--
-- Name: ix_payments_sale_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_payments_sale_id ON public.payments USING btree (sale_id);


--
-- Name: ix_payroll_periods_month; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_payroll_periods_month ON public.payroll_periods USING btree (month);


--
-- Name: ix_payroll_periods_status; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_payroll_periods_status ON public.payroll_periods USING btree (status);


--
-- Name: ix_payroll_periods_year; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_payroll_periods_year ON public.payroll_periods USING btree (year);


--
-- Name: ix_price_changes_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_price_changes_branch_id ON public.price_changes USING btree (branch_id);


--
-- Name: ix_price_changes_status; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_price_changes_status ON public.price_changes USING btree (status);


--
-- Name: ix_product_branch_stocks_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_product_branch_stocks_branch_id ON public.product_branch_stocks USING btree (branch_id);


--
-- Name: ix_product_branch_stocks_product_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_product_branch_stocks_product_id ON public.product_branch_stocks USING btree (product_id);


--
-- Name: ix_products_barcode; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_products_barcode ON public.products USING btree (barcode);


--
-- Name: ix_products_bulk_product_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_products_bulk_product_id ON public.products USING btree (bulk_product_id);


--
-- Name: ix_products_name_mn; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_products_name_mn ON public.products USING btree (name_mn);


--
-- Name: ix_pumps_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_pumps_branch_id ON public.pumps USING btree (branch_id);


--
-- Name: ix_purchase_items_purchase_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_purchase_items_purchase_id ON public.purchase_items USING btree (purchase_id);


--
-- Name: ix_purchases_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_purchases_branch_id ON public.purchases USING btree (branch_id);


--
-- Name: ix_purchases_number; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_purchases_number ON public.purchases USING btree (number);


--
-- Name: ix_purchases_status; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_purchases_status ON public.purchases USING btree (status);


--
-- Name: ix_refund_items_refund_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_refund_items_refund_id ON public.refund_items USING btree (refund_id);


--
-- Name: ix_refunds_sale_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_refunds_sale_id ON public.refunds USING btree (sale_id);


--
-- Name: ix_refunds_status; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_refunds_status ON public.refunds USING btree (status);


--
-- Name: ix_sale_items_sale_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_sale_items_sale_id ON public.sale_items USING btree (sale_id);


--
-- Name: ix_sales_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_sales_branch_id ON public.sales USING btree (branch_id);


--
-- Name: ix_sales_completed_at; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_sales_completed_at ON public.sales USING btree (completed_at);


--
-- Name: ix_sales_number; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_sales_number ON public.sales USING btree (number);


--
-- Name: ix_sales_shift_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_sales_shift_id ON public.sales USING btree (shift_id);


--
-- Name: ix_sales_status; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_sales_status ON public.sales USING btree (status);


--
-- Name: ix_settings_key; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE UNIQUE INDEX ix_settings_key ON public.settings USING btree (key);


--
-- Name: ix_shift_attachments_shift_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_shift_attachments_shift_id ON public.shift_attachments USING btree (shift_id);


--
-- Name: ix_shift_price_marks_nozzle_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_shift_price_marks_nozzle_id ON public.shift_price_marks USING btree (nozzle_id);


--
-- Name: ix_shift_price_marks_shift_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_shift_price_marks_shift_id ON public.shift_price_marks USING btree (shift_id);


--
-- Name: ix_shifts_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_shifts_branch_id ON public.shifts USING btree (branch_id);


--
-- Name: ix_shifts_number; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_shifts_number ON public.shifts USING btree (number);


--
-- Name: ix_shifts_status; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_shifts_status ON public.shifts USING btree (status);


--
-- Name: ix_sync_outbox_aggregate_type; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_sync_outbox_aggregate_type ON public.sync_outbox USING btree (aggregate_type);


--
-- Name: ix_sync_outbox_processed_at; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_sync_outbox_processed_at ON public.sync_outbox USING btree (processed_at);


--
-- Name: ix_tank_movements_tank_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_tank_movements_tank_id ON public.tank_movements USING btree (tank_id);


--
-- Name: ix_tanks_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_tanks_branch_id ON public.tanks USING btree (branch_id);


--
-- Name: ix_totalizer_readings_nozzle_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_totalizer_readings_nozzle_id ON public.totalizer_readings USING btree (nozzle_id);


--
-- Name: ix_totalizer_readings_shift_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_totalizer_readings_shift_id ON public.totalizer_readings USING btree (shift_id);


--
-- Name: ix_users_branch_id; Type: INDEX; Schema: public; Owner: kolonk
--

CREATE INDEX ix_users_branch_id ON public.users USING btree (branch_id);


--
-- Name: ap_invoices ap_invoices_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ap_invoices
    ADD CONSTRAINT ap_invoices_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- Name: ap_payments ap_payments_ap_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ap_payments
    ADD CONSTRAINT ap_payments_ap_invoice_id_fkey FOREIGN KEY (ap_invoice_id) REFERENCES public.ap_invoices(id);


--
-- Name: ap_payments ap_payments_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ap_payments
    ADD CONSTRAINT ap_payments_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: ap_payments ap_payments_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ap_payments
    ADD CONSTRAINT ap_payments_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- Name: ar_invoices ar_invoices_contract_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ar_invoices
    ADD CONSTRAINT ar_invoices_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES public.contracts(id);


--
-- Name: ar_invoices ar_invoices_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ar_invoices
    ADD CONSTRAINT ar_invoices_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- Name: ar_payments ar_payments_ar_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ar_payments
    ADD CONSTRAINT ar_payments_ar_invoice_id_fkey FOREIGN KEY (ar_invoice_id) REFERENCES public.ar_invoices(id);


--
-- Name: ar_payments ar_payments_contract_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ar_payments
    ADD CONSTRAINT ar_payments_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES public.contracts(id);


--
-- Name: ar_payments ar_payments_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ar_payments
    ADD CONSTRAINT ar_payments_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: ar_payments ar_payments_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ar_payments
    ADD CONSTRAINT ar_payments_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- Name: audit_logs audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: bank_accounts bank_accounts_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_accounts
    ADD CONSTRAINT bank_accounts_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: bank_statement_config bank_statement_config_fee_account_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_statement_config
    ADD CONSTRAINT bank_statement_config_fee_account_code_fkey FOREIGN KEY (fee_account_code) REFERENCES public.accounts(code);


--
-- Name: bank_statement_config bank_statement_config_settlement_contract_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_statement_config
    ADD CONSTRAINT bank_statement_config_settlement_contract_id_fkey FOREIGN KEY (settlement_contract_id) REFERENCES public.contracts(id);


--
-- Name: bank_statement_config bank_statement_config_settlement_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_statement_config
    ADD CONSTRAINT bank_statement_config_settlement_customer_id_fkey FOREIGN KEY (settlement_customer_id) REFERENCES public.customers(id);


--
-- Name: bank_statements bank_statements_bank_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_statements
    ADD CONSTRAINT bank_statements_bank_account_id_fkey FOREIGN KEY (bank_account_id) REFERENCES public.bank_accounts(id);


--
-- Name: bank_statements bank_statements_fee_expense_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_statements
    ADD CONSTRAINT bank_statements_fee_expense_id_fkey FOREIGN KEY (fee_expense_id) REFERENCES public.expenses(id);


--
-- Name: bank_statements bank_statements_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_statements
    ADD CONSTRAINT bank_statements_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.users(id);


--
-- Name: bank_transactions bank_transactions_ar_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_transactions
    ADD CONSTRAINT bank_transactions_ar_payment_id_fkey FOREIGN KEY (ar_payment_id) REFERENCES public.ar_payments(id);


--
-- Name: bank_transactions bank_transactions_contract_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_transactions
    ADD CONSTRAINT bank_transactions_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES public.contracts(id);


--
-- Name: bank_transactions bank_transactions_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_transactions
    ADD CONSTRAINT bank_transactions_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- Name: bank_transactions bank_transactions_expense_account_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_transactions
    ADD CONSTRAINT bank_transactions_expense_account_code_fkey FOREIGN KEY (expense_account_code) REFERENCES public.accounts(code);


--
-- Name: bank_transactions bank_transactions_expense_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_transactions
    ADD CONSTRAINT bank_transactions_expense_id_fkey FOREIGN KEY (expense_id) REFERENCES public.expenses(id);


--
-- Name: bank_transactions bank_transactions_statement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.bank_transactions
    ADD CONSTRAINT bank_transactions_statement_id_fkey FOREIGN KEY (statement_id) REFERENCES public.bank_statements(id) ON DELETE CASCADE;


--
-- Name: branch_payment_methods branch_payment_methods_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.branch_payment_methods
    ADD CONSTRAINT branch_payment_methods_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branches(id) ON DELETE CASCADE;


--
-- Name: branch_prices branch_prices_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.branch_prices
    ADD CONSTRAINT branch_prices_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: branch_prices branch_prices_fuel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.branch_prices
    ADD CONSTRAINT branch_prices_fuel_id_fkey FOREIGN KEY (fuel_id) REFERENCES public.fuels(id);


--
-- Name: branch_prices branch_prices_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.branch_prices
    ADD CONSTRAINT branch_prices_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: branches branches_manager_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.branches
    ADD CONSTRAINT branches_manager_id_fkey FOREIGN KEY (manager_id) REFERENCES public.users(id);


--
-- Name: contracts contracts_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT contracts_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- Name: ebarimt_queue ebarimt_queue_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ebarimt_queue
    ADD CONSTRAINT ebarimt_queue_sale_id_fkey FOREIGN KEY (sale_id) REFERENCES public.sales(id);


--
-- Name: employee_advances employee_advances_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.employee_advances
    ADD CONSTRAINT employee_advances_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: employee_advances employee_advances_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.employee_advances
    ADD CONSTRAINT employee_advances_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(id);


--
-- Name: employees employees_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: employees employees_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: expenses expenses_account_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_account_code_fkey FOREIGN KEY (account_code) REFERENCES public.accounts(code);


--
-- Name: expenses expenses_ap_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_ap_invoice_id_fkey FOREIGN KEY (ap_invoice_id) REFERENCES public.ap_invoices(id);


--
-- Name: expenses expenses_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: expenses expenses_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: expenses expenses_posted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_posted_by_fkey FOREIGN KEY (posted_by) REFERENCES public.users(id);


--
-- Name: expenses expenses_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.shifts(id);


--
-- Name: expenses expenses_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- Name: ar_payments fk_ar_payments_bank_account_id; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.ar_payments
    ADD CONSTRAINT fk_ar_payments_bank_account_id FOREIGN KEY (bank_account_id) REFERENCES public.bank_accounts(id);


--
-- Name: expenses fk_expenses_bank_account_id; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT fk_expenses_bank_account_id FOREIGN KEY (bank_account_id) REFERENCES public.bank_accounts(id);


--
-- Name: inventory_transactions fk_inventory_tx_branch; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.inventory_transactions
    ADD CONSTRAINT fk_inventory_tx_branch FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: price_changes fk_price_changes_branch; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.price_changes
    ADD CONSTRAINT fk_price_changes_branch FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: products fk_products_bulk_product_id; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT fk_products_bulk_product_id FOREIGN KEY (bulk_product_id) REFERENCES public.products(id);


--
-- Name: purchases fk_purchases_branch; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.purchases
    ADD CONSTRAINT fk_purchases_branch FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: fuel_receipts fuel_receipts_ap_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.fuel_receipts
    ADD CONSTRAINT fuel_receipts_ap_invoice_id_fkey FOREIGN KEY (ap_invoice_id) REFERENCES public.ap_invoices(id);


--
-- Name: fuel_receipts fuel_receipts_fuel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.fuel_receipts
    ADD CONSTRAINT fuel_receipts_fuel_id_fkey FOREIGN KEY (fuel_id) REFERENCES public.fuels(id);


--
-- Name: fuel_receipts fuel_receipts_posted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.fuel_receipts
    ADD CONSTRAINT fuel_receipts_posted_by_fkey FOREIGN KEY (posted_by) REFERENCES public.users(id);


--
-- Name: fuel_receipts fuel_receipts_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.fuel_receipts
    ADD CONSTRAINT fuel_receipts_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- Name: fuel_receipts fuel_receipts_tank_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.fuel_receipts
    ADD CONSTRAINT fuel_receipts_tank_id_fkey FOREIGN KEY (tank_id) REFERENCES public.tanks(id);


--
-- Name: inventory_transactions inventory_transactions_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.inventory_transactions
    ADD CONSTRAINT inventory_transactions_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: journal_entries journal_entries_posted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.journal_entries
    ADD CONSTRAINT journal_entries_posted_by_fkey FOREIGN KEY (posted_by) REFERENCES public.users(id);


--
-- Name: journal_lines journal_lines_account_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.journal_lines
    ADD CONSTRAINT journal_lines_account_code_fkey FOREIGN KEY (account_code) REFERENCES public.accounts(code);


--
-- Name: journal_lines journal_lines_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.journal_lines
    ADD CONSTRAINT journal_lines_entry_id_fkey FOREIGN KEY (entry_id) REFERENCES public.journal_entries(id) ON DELETE CASCADE;


--
-- Name: payments payments_contract_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES public.contracts(id);


--
-- Name: payments payments_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_sale_id_fkey FOREIGN KEY (sale_id) REFERENCES public.sales(id) ON DELETE CASCADE;


--
-- Name: payroll_lines payroll_lines_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.payroll_lines
    ADD CONSTRAINT payroll_lines_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(id);


--
-- Name: payroll_lines payroll_lines_period_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.payroll_lines
    ADD CONSTRAINT payroll_lines_period_id_fkey FOREIGN KEY (period_id) REFERENCES public.payroll_periods(id) ON DELETE CASCADE;


--
-- Name: payroll_periods payroll_periods_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.payroll_periods
    ADD CONSTRAINT payroll_periods_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: price_changes price_changes_decided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.price_changes
    ADD CONSTRAINT price_changes_decided_by_fkey FOREIGN KEY (decided_by) REFERENCES public.users(id);


--
-- Name: price_changes price_changes_fuel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.price_changes
    ADD CONSTRAINT price_changes_fuel_id_fkey FOREIGN KEY (fuel_id) REFERENCES public.fuels(id);


--
-- Name: price_changes price_changes_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.price_changes
    ADD CONSTRAINT price_changes_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: price_changes price_changes_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.price_changes
    ADD CONSTRAINT price_changes_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.users(id);


--
-- Name: product_branch_stocks product_branch_stocks_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.product_branch_stocks
    ADD CONSTRAINT product_branch_stocks_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: product_branch_stocks product_branch_stocks_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.product_branch_stocks
    ADD CONSTRAINT product_branch_stocks_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE CASCADE;


--
-- Name: products products_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.product_categories(id);


--
-- Name: pump_nozzles pump_nozzles_fuel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.pump_nozzles
    ADD CONSTRAINT pump_nozzles_fuel_id_fkey FOREIGN KEY (fuel_id) REFERENCES public.fuels(id);


--
-- Name: pump_nozzles pump_nozzles_pump_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.pump_nozzles
    ADD CONSTRAINT pump_nozzles_pump_id_fkey FOREIGN KEY (pump_id) REFERENCES public.pumps(id) ON DELETE CASCADE;


--
-- Name: pump_nozzles pump_nozzles_tank_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.pump_nozzles
    ADD CONSTRAINT pump_nozzles_tank_id_fkey FOREIGN KEY (tank_id) REFERENCES public.tanks(id);


--
-- Name: pumps pumps_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.pumps
    ADD CONSTRAINT pumps_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: purchase_items purchase_items_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.purchase_items
    ADD CONSTRAINT purchase_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: purchase_items purchase_items_purchase_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.purchase_items
    ADD CONSTRAINT purchase_items_purchase_id_fkey FOREIGN KEY (purchase_id) REFERENCES public.purchases(id) ON DELETE CASCADE;


--
-- Name: purchases purchases_ap_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.purchases
    ADD CONSTRAINT purchases_ap_invoice_id_fkey FOREIGN KEY (ap_invoice_id) REFERENCES public.ap_invoices(id);


--
-- Name: purchases purchases_posted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.purchases
    ADD CONSTRAINT purchases_posted_by_fkey FOREIGN KEY (posted_by) REFERENCES public.users(id);


--
-- Name: purchases purchases_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.purchases
    ADD CONSTRAINT purchases_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- Name: refund_items refund_items_refund_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.refund_items
    ADD CONSTRAINT refund_items_refund_id_fkey FOREIGN KEY (refund_id) REFERENCES public.refunds(id) ON DELETE CASCADE;


--
-- Name: refund_items refund_items_sale_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.refund_items
    ADD CONSTRAINT refund_items_sale_item_id_fkey FOREIGN KEY (sale_item_id) REFERENCES public.sale_items(id);


--
-- Name: refunds refunds_decided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.refunds
    ADD CONSTRAINT refunds_decided_by_fkey FOREIGN KEY (decided_by) REFERENCES public.users(id);


--
-- Name: refunds refunds_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.refunds
    ADD CONSTRAINT refunds_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.users(id);


--
-- Name: refunds refunds_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.refunds
    ADD CONSTRAINT refunds_sale_id_fkey FOREIGN KEY (sale_id) REFERENCES public.sales(id);


--
-- Name: refunds refunds_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.refunds
    ADD CONSTRAINT refunds_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.shifts(id);


--
-- Name: role_permissions role_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES public.permissions(id) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: sale_items sale_items_fuel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sale_items
    ADD CONSTRAINT sale_items_fuel_id_fkey FOREIGN KEY (fuel_id) REFERENCES public.fuels(id);


--
-- Name: sale_items sale_items_nozzle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sale_items
    ADD CONSTRAINT sale_items_nozzle_id_fkey FOREIGN KEY (nozzle_id) REFERENCES public.pump_nozzles(id);


--
-- Name: sale_items sale_items_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sale_items
    ADD CONSTRAINT sale_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: sale_items sale_items_pump_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sale_items
    ADD CONSTRAINT sale_items_pump_id_fkey FOREIGN KEY (pump_id) REFERENCES public.pumps(id);


--
-- Name: sale_items sale_items_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sale_items
    ADD CONSTRAINT sale_items_sale_id_fkey FOREIGN KEY (sale_id) REFERENCES public.sales(id) ON DELETE CASCADE;


--
-- Name: sale_items sale_items_tank_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sale_items
    ADD CONSTRAINT sale_items_tank_id_fkey FOREIGN KEY (tank_id) REFERENCES public.tanks(id);


--
-- Name: sales sales_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: sales sales_cashier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_cashier_id_fkey FOREIGN KEY (cashier_id) REFERENCES public.users(id);


--
-- Name: sales sales_contract_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES public.contracts(id);


--
-- Name: sales sales_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- Name: sales sales_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.shifts(id);


--
-- Name: shift_attachments shift_attachments_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_attachments
    ADD CONSTRAINT shift_attachments_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.shifts(id) ON DELETE CASCADE;


--
-- Name: shift_attachments shift_attachments_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_attachments
    ADD CONSTRAINT shift_attachments_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.users(id);


--
-- Name: shift_closings shift_closings_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_closings
    ADD CONSTRAINT shift_closings_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: shift_closings shift_closings_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_closings
    ADD CONSTRAINT shift_closings_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: shift_closings shift_closings_fuel_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_closings
    ADD CONSTRAINT shift_closings_fuel_sale_id_fkey FOREIGN KEY (fuel_sale_id) REFERENCES public.sales(id);


--
-- Name: shift_closings shift_closings_oil_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_closings
    ADD CONSTRAINT shift_closings_oil_sale_id_fkey FOREIGN KEY (oil_sale_id) REFERENCES public.sales(id);


--
-- Name: shift_closings shift_closings_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_closings
    ADD CONSTRAINT shift_closings_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.shifts(id) ON DELETE CASCADE;


--
-- Name: shift_price_marks shift_price_marks_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_price_marks
    ADD CONSTRAINT shift_price_marks_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: shift_price_marks shift_price_marks_nozzle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_price_marks
    ADD CONSTRAINT shift_price_marks_nozzle_id_fkey FOREIGN KEY (nozzle_id) REFERENCES public.pump_nozzles(id);


--
-- Name: shift_price_marks shift_price_marks_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_price_marks
    ADD CONSTRAINT shift_price_marks_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.shifts(id) ON DELETE CASCADE;


--
-- Name: shift_tank_levels shift_tank_levels_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_tank_levels
    ADD CONSTRAINT shift_tank_levels_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.shifts(id) ON DELETE CASCADE;


--
-- Name: shift_tank_levels shift_tank_levels_tank_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shift_tank_levels
    ADD CONSTRAINT shift_tank_levels_tank_id_fkey FOREIGN KEY (tank_id) REFERENCES public.tanks(id);


--
-- Name: shifts shifts_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT shifts_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: shifts shifts_closed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT shifts_closed_by_fkey FOREIGN KEY (closed_by) REFERENCES public.users(id);


--
-- Name: shifts shifts_opened_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT shifts_opened_by_fkey FOREIGN KEY (opened_by) REFERENCES public.users(id);


--
-- Name: tank_movements tank_movements_tank_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.tank_movements
    ADD CONSTRAINT tank_movements_tank_id_fkey FOREIGN KEY (tank_id) REFERENCES public.tanks(id);


--
-- Name: tanks tanks_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.tanks
    ADD CONSTRAINT tanks_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: tanks tanks_fuel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.tanks
    ADD CONSTRAINT tanks_fuel_id_fkey FOREIGN KEY (fuel_id) REFERENCES public.fuels(id);


--
-- Name: totalizer_readings totalizer_readings_nozzle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.totalizer_readings
    ADD CONSTRAINT totalizer_readings_nozzle_id_fkey FOREIGN KEY (nozzle_id) REFERENCES public.pump_nozzles(id);


--
-- Name: totalizer_readings totalizer_readings_recorded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.totalizer_readings
    ADD CONSTRAINT totalizer_readings_recorded_by_fkey FOREIGN KEY (recorded_by) REFERENCES public.users(id);


--
-- Name: totalizer_readings totalizer_readings_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.totalizer_readings
    ADD CONSTRAINT totalizer_readings_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.shifts(id);


--
-- Name: users users_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: users users_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kolonk
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id);


--
-- PostgreSQL database dump complete
--

\unrestrict 4JewKZhonZgsP85oG5RZX7jQpblwpDbzeZdlpipW0dpYupOYXShNs9zhV4X7XdP

