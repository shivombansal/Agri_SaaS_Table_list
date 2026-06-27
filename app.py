import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import time

st.set_page_config(
    page_title="SQL Export Tracker v2",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# NAMING CONVENTIONS (updated v2)
# ─────────────────────────────────────────────────────────────────────────────
# Tracker prefix  │ Actual DB table name (no prefix)
# ────────────────┼──────────────────────────────────────────────────────────
# sys_            │ Shared tables used by BOTH prod & CRM (employees, roles,
#                 │   departments, grades, geography geo-spine, expenses, etc.)
# mst_prod_       │ Production-only master / transaction tables
# mst_crm_        │ CRM-only master / transaction tables
#
# Each row: (wave, tracker_name, actual_db_table, type, deps, note, is_new)
#
# "actual_db_table" is the real table name in the MySQL database as found in
# the Sequelize model files (Detail_table_structure.txt).
# "—" means the names are identical (no rename / no prefix difference).
# ─────────────────────────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════════════════════
# SHARED SYSTEM MODULE  (sys_)
# Tables referenced by BOTH production and CRM code paths.
# Actual DB names have NO module prefix — they are truly shared.
# ══════════════════════════════════════════════════════════════════════════════
SYS_ROWS = [
    # ── Wave 1 — leaf roots ──────────────────────────────────────────────────
    # Tracker name                  Actual DB name              type       deps                                              note                                    new?
    (1,"sys_mst_departments",       "mst_departments",          "master",  "—",                                              "Dept master — parent of roles, sub-depts, workflows, policies", False),
    (1,"sys_mst_employee_grades",   "mst_employee_grades",      "master",  "—",                                              "Grade hierarchy — used by TADA approvers & expense caps",       False),
    (1,"sys_mst_employee_hq",       "mst_employee_hq",          "master",  "—",                                              "Employee HQ / location assignment master",                       False),
    (1,"sys_mst_designations",      "mst_designations",         "master",  "—",                                              "Designation / title master",                                    False),
    (1,"sys_mst_crop_types",        "mst_crop_types",           "master",  "—",                                              "Crop type grouping (used in employee record)",                  False),
    (1,"sys_mst_mode_of_travel",    "mst_mode_of_travel",       "master",  "—",                                              "Travel mode master (car, train…)",                              False),
    (1,"sys_mst_type_of_travel",    "mst_type_of_travel",       "master",  "—",                                              "Travel type master (local, outstation…)",                       False),
    (1,"sys_mst_dropdown_master",   "mst_dropdown_master",      "master",  "—",                                              "UI dropdown options — shared across modules",                   False),
    (1,"sys_tr_attachments",        "tr_attachments",           "transaction","—",                                           "File attachment store — shared by both expense flows",          False),
    (1,"sys_sec_sessions",          "tr_sessions",              "security","—",                                               "Login / session tokens",                                        False),
    (1,"sys_sec_otps",              "otps",                     "security","—",                                               "OTP verification records",                                      False),
    (1,"sys_tr_notifications",      "tr_notifications",         "transaction","—",                                           "Push notifications (shared app-wide)",                          False),
    (1,"sys_mst_zones",             "mst_zones",                "master",  "—",                                              "Top-level geography — used by prod, CRM, organizers, budgets",  False),
    (1,"sys_mst_crops",             "mst_crops",                "master",  "—",                                              "Crop master — referenced across prod plans, CRM activities",    False),
    (1,"sys_mst_product_skus",      "mst_product_skus",         "master",  "—",                                              "SKU master — used by varieties, CRM farmer purchase patterns",  False),
    (1,"sys_mst_female_codes",      "mst_female_codes",         "master",  "—",                                              "Variety female parent codes",                                   False),
    (1,"sys_mst_male_codes",        "mst_male_codes",           "master",  "—",                                              "Variety male parent codes",                                     False),
    (1,"sys_mst_years",             "mst_years",                "master",  "—",                                              "Production financial / season year master",                      False),
    (1,"sys_mst_crm_years",         "mst_crm_years",            "master",  "—",                                              "CRM year / period master",                                      False),
    (1,"sys_mst_c_states",          "mst_c_states",             "master",  "—",                                              "CRM state master — also linked to prod employees",              False),
    # ── Wave 2 ────────────────────────────────────────────────────────────────
    (2,"sys_mst_sub_departments",   "mst_sub_departments",      "master",  "sys_mst_departments",                            "Sub-department grouping",                                       False),
    (2,"sys_mst_regions",           "mst_regions",              "master",  "sys_mst_zones",                                  "Geo region — used by prod & CRM plans, budgets, growers",       False),
    (2,"sys_mst_varieties",         "mst_varieties",            "master",  "sys_mst_crops · sys_mst_product_skus · sys_mst_female_codes · sys_mst_male_codes", "Core variety master — central to all prod & CRM flows", False),
    (2,"sys_tr_travel_reimbursements","tr_travel_reimbursements","transaction","—",                                          "Reimbursement records — shared expense module",                 False),
    # ── Wave 3 ────────────────────────────────────────────────────────────────
    (3,"sys_mst_roles",             "mst_roles",                "master",  "sys_mst_departments · sys_mst_sub_departments",  "Role master — auth & approval hierarchy for both modules",      False),
    (3,"sys_mst_territories",       "mst_regions",              "master",  "sys_mst_regions",                                "Territory under region — used by CRM budgets & prod districts", False),
    (3,"sys_mst_mode_of_travel_mapping","mst_mode_of_travel_mapping","master","sys_mst_mode_of_travel · sys_mst_type_of_travel","Travel mode-type mapping",                                  False),
    # ── Wave 4 ────────────────────────────────────────────────────────────────
    (4,"sys_tr_employees",          "tr_employees",             "transaction","sys_mst_departments · sys_mst_sub_departments · sys_mst_roles · sys_mst_employee_grades · sys_mst_employee_hq · sys_mst_c_states · sys_mst_designations · sys_mst_crop_types", "Central user/employee table — backbone of all module auth and field operations", False),
    (4,"sys_tr_role_permissions",   "tr_role_permissions",      "security","sys_mst_roles",                                  "Permission matrix by role",                                     False),
    (4,"sys_tr_tada_workflows",     "tr_tada_workflows",        "transaction","sys_mst_departments",                         "TADA workflow rules by department",                             False),
    (4,"sys_tr_working_hours",      "tr_working_hours",         "transaction","sys_mst_departments",                         "Working-hour policy by department",                             False),
    (4,"sys_tr_travel_grade_rules", "tr_travel_grade_rules",    "transaction","sys_mst_departments",                         "Claim caps / eligibility by employee grade",                   False),
    (4,"sys_tr_policy",             "tr_policy",                "transaction","sys_mst_departments · sys_tr_attachments",    "Policy documents with dept mapping",                            False),
    # ── Wave 5 ────────────────────────────────────────────────────────────────
    (5,"sys_tr_tada_workflow_approvers","tr_tada_workflow_approvers","transaction","sys_tr_tada_workflows · sys_mst_employee_grades · sys_mst_roles","Approver matrix per workflow",         False),
    (5,"sys_tr_attendance",         "tr_attendance",            "transaction","sys_tr_employees",                            "Daily check-in/out attendance log",                             False),
    (5,"sys_tr_user_permissions",   "tr_user_permissions",      "security","sys_tr_employees",                               "User-level permission overrides",                               False),
    # ── Wave 6 ────────────────────────────────────────────────────────────────
    # Expense chain — shared by prod and CRM activity flows
    (6,"sys_tr_expenses",           "tr_expenses",              "transaction","sys_tr_employees · sys_tr_attachments",       "Expense claim header (both modules feed into this)",            False),
    # ── Wave 7 ────────────────────────────────────────────────────────────────
    (7,"sys_tr_expense_line_items", "tr_expense_line_items",    "transaction","sys_tr_expenses · sys_tr_attachments",        "Itemised expense lines",                                        False),
    (7,"sys_tr_approvals",          "tr_approvals",             "transaction","sys_tr_expenses · sys_tr_employees",          "Current approval chain",                                        False),
    (7,"sys_tr_expense_approval_history","tr_expense_approval_history","transaction","sys_tr_expenses · sys_tr_employees",  "Immutable approval action log",                                 False),
    # ── Wave 8 ────────────────────────────────────────────────────────────────
    (8,"sys_tr_expense_approval_changes","tr_expense_approval_changes","transaction","sys_tr_expenses · sys_tr_expense_approval_history","Fine-grained approval change log",                 False),
    (8,"sys_jn_policy_departments", "policy_departments",       "join",    "sys_tr_policy · sys_mst_departments",            "Policy ↔ Dept M:N",                                            False),
    # ── Join / M:N — employee geo assignments (used across both modules) ──────
    (5,"sys_jn_employee_zone",      "employeezone",             "join",    "sys_tr_employees · sys_mst_zones",               "Employee ↔ Zone M:N",                                          False),
    (5,"sys_jn_employee_region",    "employeeregion",           "join",    "sys_tr_employees · sys_mst_regions",             "Employee ↔ Region M:N",                                        False),
    (5,"sys_jn_employee_crop",      "employeecrop",             "join",    "sys_tr_employees · sys_mst_crops",               "Employee ↔ Crop M:N",                                          False),
    (5,"sys_jn_employee_variety",   "employeevariety",          "join",    "sys_tr_employees · sys_mst_varieties",           "Employee ↔ Variety M:N",                                       False),
    # ── Zone / Region geo spine join ──────────────────────────────────────────
    (2,"sys_jn_zone_region",        "zoneregion",               "join",    "sys_mst_zones · sys_mst_regions",                "Zone ↔ Region M:N",                                            False),
    (3,"sys_jn_region_territory",   "regionterritory",          "join",    "sys_mst_regions · sys_mst_territories",          "Region ↔ Territory M:N",                                       False),
]

# ══════════════════════════════════════════════════════════════════════════════
# PRODUCTION MODULE  (mst_prod_ / tr_prod_)
# Only production-specific tables — references to shared tables use sys_ keys.
# Column: (wave, tracker_name, actual_db_table, type, deps, note, is_new)
# ══════════════════════════════════════════════════════════════════════════════
PROD_ROWS = [
    # ── Wave 1 — leaf roots ──────────────────────────────────────────────────
    (1,"mst_prod_production_locations","mst_production_locations","master","—",                                              "Production location master (organizer field)",                  False),
    (1,"mst_prod_plants",           "mst_plants",               "master",  "—",                                              "Plant / processing site master",                                False),
    (1,"mst_prod_seed_types",       "mst_seed_types",           "master",  "—",                                              "Seed type master",                                              True),
    (1,"mst_prod_crop_categories",  "mst_crop_categories",      "master",  "—",                                              "Crop category master",                                          True),
    (1,"sync_prod_zone_dynamics",   "mst_zone_dynamics",        "sync",    "—",                                              "Dynamics zone staging",                                         False),
    (1,"sync_prod_crops_dynamics",  "mst_crops_dynamics",       "sync",    "—",                                              "Dynamics crop staging",                                         False),
    (1,"sync_prod_varieties_dynamics","mst_varieties_dynamics",  "sync",   "—",                                              "Dynamics variety staging",                                      False),
    # ── Wave 2 ────────────────────────────────────────────────────────────────
    (2,"mst_prod_seasons",          "mst_seasons",              "master",  "sys_mst_years",                                  "Season master (Kharif, Rabi, Zaid…)",                           True),
    (2,"mst_prod_terms",            "mst_terms",                "master",  "sys_mst_years · sys_mst_crops",                  "Crop terms per year",                                           False),
    (2,"sync_prod_region_dynamics", "mst_region_dynamics",      "sync",    "sync_prod_zone_dynamics",                        "Dynamics region staging",                                       False),
    # ── Wave 3 ────────────────────────────────────────────────────────────────
    (3,"mst_prod_blocks",           "mst_blocks",               "master",  "sys_mst_regions",                                "Production block master",                                       False),
    (3,"mst_prod_varieties_ext",    "mst_varieties",            "master",  "sys_mst_varieties · mst_prod_seed_types · mst_prod_crop_categories","Variety master with prod-specific seed/category extensions",False),
    (3,"sync_prod_territory_dynamics","mst_territory_dynamics", "sync",    "sync_prod_region_dynamics",                      "Dynamics territory staging",                                    False),
    # ── Wave 4 ────────────────────────────────────────────────────────────────
    (4,"mst_prod_districts",        "mst_districts",            "master",  "sys_mst_territories · sys_mst_c_states",         "Production district master (bridges CRM state)",                False),
    (4,"mst_prod_villages",         "mst_villages",             "master",  "mst_prod_blocks",                                "Production village master",                                     False),
    (4,"mst_prod_crop_analytics",   "mst_crop_analytics",       "master",  "sys_mst_crops · sys_mst_years · sys_mst_varieties · sys_mst_regions","Analytics baseline for prod targets",     False),
    (4,"tr_prod_plans",             "tr_production_plans",      "transaction","sys_mst_varieties · sys_mst_years",           "Base production plan (non-PS)",                                 False),
    (4,"jn_prod_block_villages",    "blockvillages",            "join",    "mst_prod_blocks · mst_prod_villages",            "Block ↔ Village M:N",                                          False),
    # ── Wave 5 ────────────────────────────────────────────────────────────────
    (5,"mst_prod_mdo_hqs",          "mst_mdo_hqs",              "master",  "mst_prod_districts",                             "MDO HQ locations",                                              False),
    (5,"mst_prod_organizers",       "mst_organizers",           "master",  "sys_mst_zones · sys_mst_regions · mst_prod_production_locations · sys_tr_employees","Organizer / field agent master",False),
    (5,"tr_prod_plan_ps",           "tr_production_plan_ps",    "transaction","sys_mst_varieties · sys_mst_years · mst_prod_crop_analytics","PS production plan",                            False),
    (5,"tr_prod_plan_hybrids",      "tr_prod_plan_hybrids",     "transaction","sys_mst_varieties · sys_mst_years · mst_prod_crop_analytics","Hybrid forecast / plan",                        False),
    (5,"tr_prod_location_allotments","tr_location_allotments",  "transaction","sys_mst_varieties · sys_mst_years",           "Location allotment header",                                     False),
    (5,"tr_prod_remark_histories",  "tr_remark_histories",      "transaction","sys_mst_varieties · sys_mst_years · sys_tr_employees","Planning remarks audit trail",                          False),
    (5,"tr_prod_sales_plan_histories","tr_sales_plan_histories", "transaction","sys_mst_varieties · sys_mst_years · sys_tr_employees","Sales plan change log",                                False),
    (5,"jn_prod_employee_block",    "employeeblock",            "join",    "sys_tr_employees · mst_prod_blocks",             "Employee ↔ Block M:N",                                         False),
    (5,"jn_prod_employee_district", "employeedistrict",         "join",    "sys_tr_employees · mst_prod_districts",          "Employee ↔ District M:N",                                      False),
    (5,"jn_prod_employee_village",  "employeevillage",          "join",    "sys_tr_employees · mst_prod_villages",           "Employee ↔ Village M:N",                                       False),
    (5,"jn_prod_employee_mdohq",    "employeemdohq",            "join",    "sys_tr_employees · mst_prod_mdo_hqs",            "Employee ↔ MDO HQ M:N",                                        False),
    # ── Wave 6 ────────────────────────────────────────────────────────────────
    (6,"mst_prod_growers",          "mst_growers",              "master",  "mst_prod_organizers · sys_tr_employees · sys_mst_zones · sys_mst_regions · mst_prod_blocks · mst_prod_villages · sys_mst_crops · sys_mst_varieties","Core grower registry",False),
    (6,"jn_prod_district_mdohq",    "districtmdohq",            "join",    "mst_prod_districts · mst_prod_mdo_hqs",          "District ↔ MDO HQ M:N",                                        False),
    (6,"jn_prod_mdohq_blocks",      "mdohqblocks",              "join",    "mst_prod_mdo_hqs · mst_prod_blocks",             "MDO HQ ↔ Block M:N",                                           False),
    (6,"jn_prod_org_block",         "org_block",                "join",    "mst_prod_organizers · mst_prod_blocks",          "Organizer ↔ Block M:N",                                        False),
    (6,"jn_prod_org_emp",           "org_emp",                  "join",    "mst_prod_organizers · sys_tr_employees",         "Organizer ↔ Employee M:N",                                     False),
    (6,"tr_prod_organizer_performances","tr_organizer_performances","transaction","mst_prod_organizers · sys_mst_varieties · sys_mst_years","Organizer performance scoring metrics",         False),
    (6,"tr_prod_region_allotments", "tr_region_allotments",     "transaction","tr_prod_location_allotments · mst_prod_crop_analytics · sys_mst_varieties · sys_mst_regions","Region allotment breakdown",False),
    # ── Wave 7 ────────────────────────────────────────────────────────────────
    (7,"tr_prod_organizer_selection","tr_organizer_selection",  "transaction","sys_mst_varieties · sys_mst_years · sys_mst_regions · mst_prod_organizers · tr_prod_organizer_performances","Organizer selection decisions",False),
    (7,"tr_prod_grower_preparations","tr_grower_preparations",  "transaction","sys_mst_varieties · sys_mst_years · sys_mst_regions · mst_prod_organizers · mst_prod_growers","Sowing readiness tracking",False),
    (7,"tr_prod_monitorings",       "tr_production_monitorings","transaction","sys_mst_varieties · sys_mst_years · sys_mst_regions · mst_prod_growers · sys_tr_employees","Crop lifecycle monitoring",False),
    (7,"tr_prod_crop_status",       "tr_monitoring_crop_status","transaction","sys_mst_varieties · sys_mst_years · sys_mst_regions · mst_prod_growers · sys_tr_employees","Crop status snapshot",False),
    (7,"tr_prod_crop_status_history","tr_monitoring_crop_status_history","transaction","sys_mst_varieties · sys_mst_years · sys_mst_regions · mst_prod_growers · sys_tr_employees","Crop status audit trail",False),
    (7,"tr_prod_purity_reports",    "tr_physical_purity_reports","transaction","sys_mst_varieties · sys_mst_years · sys_mst_regions · mst_prod_plants · mst_prod_organizers","Purity / quality reports",False),
    (7,"tr_prod_summary_reports",   "tr_prod_summary_reports",  "transaction","sys_mst_varieties · sys_mst_years · sys_mst_regions · mst_prod_organizers","Production summary header",       False),
    (7,"tr_prod_daily_visits",      "tr_daily_visits",          "transaction","sys_mst_varieties · sys_mst_years · sys_mst_regions · sys_tr_employees · mst_prod_growers","Daily field visit log",False),
    (7,"tr_prod_loc_altmt_histories","tr_loc_altmt_histories",  "transaction","tr_prod_location_allotments · sys_tr_employees","Location allotment change log",                              False),
    # ── Wave 8 ────────────────────────────────────────────────────────────────
    (8,"tr_prod_summary_weekly",    "tr_prod_summary_reports_weekly","transaction","tr_prod_summary_reports · sys_mst_varieties · sys_mst_years · sys_mst_regions · mst_prod_organizers","Weekly production breakdown",False),
    (8,"tr_prod_monitoring_sample_checks","tr_monitoring_sample_checks","transaction","tr_prod_monitorings",                 "Sample check child records for monitoring",                     False),
    # ── Wave 13 — Sync / Integration ─────────────────────────────────────────
    (13,"sync_prod_run_log",        "tr_dynamics_prod_sync_runs","sync",   "—",                                              "Production sync run monitor",                                   False),
    (13,"sync_prod_error_log",      "tr_dynamics_prod_sync_errors","sync", "—",                                              "Production sync error log",                                     False),
    (13,"sync_prod_planting_log",   "tr_dynamics_planting_logs","sync",    "—",                                              "Planting payload audit",                                        False),
    (13,"sync_prod_seed_dist_log",  "tr_dynamics_seed_distribution_logs","sync","—",                                         "Seed distribution payload audit",                               False),
    (13,"sync_prod_purity_log",     "tr_dynamics_purity_report_logs","sync","—",                                             "Purity report payload audit",                                   False),
]

# ══════════════════════════════════════════════════════════════════════════════
# CRM MODULE  (mst_crm_ / tr_crm_)
# Only CRM-specific tables.
# ══════════════════════════════════════════════════════════════════════════════
CRM_ROWS = [
    # ── Wave 1 — leaf roots ──────────────────────────────────────────────────
    (1,"mst_crm_activities",        "mst_activities",           "master",  "—",                                              "Activity type master for CRM execution",                        False),
    (1,"mst_crm_city_master",       "mst_city_master",          "master",  "—",                                              "Standalone city list",                                          False),
    (1,"mst_crm_banners",           "mst_banners",              "master",  "—",                                              "Scheme / banner master",                                        False),
    (1,"mst_crm_scheme_banner_attachments","mst_scheme_banner_attachments","master","—",                                     "Banner attachment assets",                                      False),
    (1,"mst_crm_geosetup",          "mst_geosetup",             "master",  "—",                                              "Geo setup staging (Dynamics sync)",                            False),
    (1,"sync_crm_zone_response",    "mst_zone_respone",         "sync",    "—",                                              "Sync zone response staging",                                    False),
    (1,"sync_crm_crop_response",    "mst_crop_response",        "sync",    "—",                                              "Sync crop response staging",                                    False),
    (1,"sync_crm_variety_sku_response","mst_varietiessku_response","sync", "—",                                              "Sync variety SKU response staging",                             False),
    (1,"sync_crm_distributors_response","mst_distributors_response","sync","—",                                              "Sync distributor response staging",                             False),
    # ── Wave 2 ────────────────────────────────────────────────────────────────
    (2,"mst_crm_c_districts",       "mst_c_districts",          "master",  "sys_mst_c_states",                               "CRM district master",                                           False),
    (2,"tr_crm_holiday",            "tr_holiday",               "transaction","sys_mst_c_states",                            "State holiday calendar",                                        False),
    # ── Wave 3 ────────────────────────────────────────────────────────────────
    (3,"mst_crm_c_blocks",          "mst_c_blocks",             "master",  "mst_crm_c_districts",                            "CRM block master",                                              False),
    (3,"mst_crm_varieties",         "mst_varieties",            "master",  "sys_mst_crops · sys_mst_product_skus",           "Variety master scoped to CRM flows",                            False),
    # ── Wave 4 ────────────────────────────────────────────────────────────────
    (4,"mst_crm_c_villages",        "mst_c_villages",           "master",  "mst_crm_c_blocks",                               "CRM village master",                                            False),
    (4,"mst_crm_city_category",     "mst_city_category",        "master",  "sys_mst_c_states · mst_crm_c_districts · mst_crm_c_blocks · mst_crm_c_villages","City category tagging",        False),
    (4,"mst_crm_focused_varieties", "mst_focused_varieties",    "master",  "sys_mst_varieties · sys_mst_regions · sys_mst_zones","Priority varieties for CRM planning",                      False),
    (4,"tr_crm_national_sales_budget","tr_national_sales_budget","transaction","sys_mst_varieties · sys_mst_crm_years",       "National sales budget header",                                  False),
    (4,"tr_crm_menu_permissions",   "tr_crm_menu_permissions",  "security","sys_mst_roles · sys_tr_employees",               "CRM menu access control",                                       False),
    (4,"tr_crm_sales_target_histories","tr_crm_sales_target_histories","transaction","sys_mst_varieties · sys_mst_years · sys_tr_employees","CRM sales target change log",                   False),
    (4,"jn_crm_dist_block",         "dist_crm_block",           "join",    "mst_prod_districts · mst_crm_c_blocks",          "Production district ↔ CRM block cross-map",                    False),
    (4,"jn_crm_employee_crop",      "employeecrop",             "join",    "sys_tr_employees · sys_mst_crops",               "Employee ↔ Crop M:N (CRM scope)",                              False),
    (4,"jn_crm_employee_variety",   "employeevariety",          "join",    "sys_tr_employees · sys_mst_varieties",           "Employee ↔ Variety M:N (CRM scope)",                           False),
    # ── Wave 5 ────────────────────────────────────────────────────────────────
    (5,"tr_crm_farmer",             "tr_farmer",                "transaction","sys_tr_employees · mst_prod_districts · mst_crm_c_blocks · mst_crm_c_villages","CRM farmer master",           False),
    (5,"tr_crm_distributors",       "tr_distributors",          "transaction","sys_tr_employees · mst_prod_districts · sys_mst_c_states · mst_crm_c_blocks","Distributor master",           False),
    (5,"tr_crm_retailers",          "tr_retailers",             "transaction","sys_tr_employees · mst_crm_c_districts · mst_crm_c_blocks","Retailer master",                                 False),
    # ── Wave 6 ────────────────────────────────────────────────────────────────
    (6,"tr_crm_distributor_visits", "tr_distributor_visits",    "transaction","tr_crm_distributors · mst_crm_c_blocks · sys_tr_employees · mst_crm_banners · mst_crm_scheme_banner_attachments","Distributor visit records",False),
    (6,"tr_crm_retailer_visits",    "tr_retailer_visits",       "transaction","tr_crm_retailers · mst_crm_c_blocks · sys_tr_employees · mst_crm_banners · mst_crm_scheme_banner_attachments","Retailer visit records",    False),
    (6,"tr_crm_seasons",            "tr_seasons",               "transaction","sys_tr_employees · tr_crm_retailers",          "Seasonal retailer tags",                                        False),
    (6,"tr_crm_seasons_distributor","tr_seasons_distributer",   "transaction","sys_tr_employees · tr_crm_distributors",       "Seasonal distributor tags",                                     False),
    (6,"tr_crm_farmer_purchase_pattern","tr_farmer_purchase_pattern","transaction","tr_crm_farmer · sys_mst_crm_years · sys_mst_crops · sys_mst_varieties · sys_mst_product_skus","Farmer purchase behavior",False),
    (6,"tr_crm_zone_sales_budget",  "tr_zone_sales_budget",     "transaction","sys_mst_varieties · sys_mst_crm_years · sys_mst_zones · tr_crm_national_sales_budget","Zone sales budget",   False),
    (6,"sync_crm_distributors_dynamics","tr_distributors_dynamics","sync",  "sys_tr_employees",                              "Dynamics distributor mirror",                                   False),
    (6,"sync_crm_distributors_dynamics_v2","tr_distributors_dynamics_new","sync","sys_tr_employees",                         "Dynamics distributor mirror v2",                                False),
    (6,"sync_crm_distributor_integration","tr_distributor_dynamic_integration","sync","sys_tr_employees",                    "Distributor integration log",                                   False),
    # ── Wave 7 ────────────────────────────────────────────────────────────────
    (7,"tr_crm_activity_planning",  "tr_activity_planning",     "transaction","sys_mst_crm_years · sys_mst_varieties · sys_tr_employees · mst_crm_focused_varieties","CRM FC activity plan",False),
    (7,"tr_crm_activity_planning_veg","tr_activity_planning_veg","transaction","sys_mst_crm_years · sys_mst_varieties · sys_tr_employees · mst_crm_focused_varieties","CRM Veg activity plan",False),
    (7,"tr_crm_region_sales_budget","tr_region_sales_budget",   "transaction","sys_mst_varieties · sys_mst_crm_years · sys_mst_regions · tr_crm_zone_sales_budget","Region sales budget",    False),
    # ── Wave 8 ────────────────────────────────────────────────────────────────
    (8,"tr_crm_field_visits",       "tr_field_visits",          "transaction","sys_tr_employees · tr_crm_farmer · sys_mst_varieties · mst_crm_activities · mst_crm_c_blocks · mst_crm_c_villages","Core CRM field visit (PDA/PSA start)",False),
    (8,"tr_crm_territory_sales_budget","tr_territory_sales_budget","transaction","sys_mst_varieties · sys_mst_crm_years · sys_mst_territories · tr_crm_region_sales_budget","Territory sales budget",False),
    (8,"tr_crm_territory_sales_budget_veg","tr_territory_sales_budget_veg","transaction","sys_mst_varieties · sys_mst_crm_years · sys_mst_territories","Territory Veg sales budget",         False),
    (8,"tr_crm_region_sales_budget_veg","tr_region_sales_budget_veg","transaction","sys_mst_varieties · sys_mst_crm_years · sys_mst_regions","Region Veg sales budget",                      False),
    (8,"tr_crm_activity_approval_history","tr_activity_approval_history","transaction","sys_mst_crm_years · sys_tr_employees","Activity approval log",                                       False),
    (8,"tr_crm_activity_plan_change_history","tr_activity_plan_change_history","transaction","sys_mst_crm_years · sys_tr_employees · mst_crm_focused_varieties","Activity plan change log",  False),
    # ── Wave 9 ────────────────────────────────────────────────────────────────
    (9,"tr_crm_fieldvisit_remarks", "tr_fieldvisit_remarks",    "transaction","tr_crm_field_visits · sys_tr_employees",      "Manager remarks on field visits",                               False),
    (9,"tr_crm_pda_psa_approval_history","tr_pda_psa_approval_history","transaction","tr_crm_field_visits · sys_tr_employees","PDA/PSA approval log",                                        False),
    (9,"tr_crm_dgactivity",         "tr_dgactivity",            "transaction","sys_tr_employees · tr_crm_field_visits · tr_crm_farmer · mst_crm_c_villages · mst_crm_activities · sys_mst_varieties · sys_mst_crops · mst_crm_c_blocks","DG activity execution (PDA)",False),
    (9,"tr_crm_psa_approval",       "tr_psa_approval",          "transaction","mst_crm_activities · sys_mst_varieties · mst_crm_c_villages · sys_tr_employees","PSA approval header",       False),
    # ── Wave 10 ───────────────────────────────────────────────────────────────
    (10,"tr_crm_dgactivity_remarks","tr_dgactivity_remarks",    "transaction","sys_tr_employees · tr_crm_dgactivity",        "DG activity review remarks",                                    False),
    (10,"tr_crm_psa_approval_history","tr_psa_approval_history","transaction","tr_crm_psa_approval · sys_tr_employees",     "PSA approval action log",                                       False),
    (10,"tr_crm_psa_dgactivity",    "tr_psa_dgactivity",        "transaction","tr_crm_psa_approval · sys_tr_employees · mst_crm_c_villages · mst_crm_activities · sys_mst_varieties · sys_mst_crops","Activity records under PSA",False),
    # ── Wave 11 ───────────────────────────────────────────────────────────────
    (11,"tr_crm_psa_dgactivity_remarks","tr_psa_dgactivity_remarks","transaction","sys_tr_employees · tr_crm_psa_dgactivity","PSA DG remark log",                                           False),
    # Note: CRM expenses now link to sys_tr_expenses (shared) + DG/PSA activity refs
    (11,"tr_crm_expenses_ext",      "tr_expenses",              "transaction","sys_tr_employees · sys_tr_attachments · tr_crm_dgactivity · tr_crm_psa_dgactivity","Expense header with CRM activity context (extends sys_tr_expenses)",False),
    # ── Wave 13 — Sync ────────────────────────────────────────────────────────
    (13,"sync_crm_geo_run_log",     "tr_dynamics_geo_sync_runs","sync",    "—",                                              "Geo sync run monitor",                                          False),
    (13,"sync_crm_geo_error_log",   "tr_dynamics_geo_sync_errors","sync",  "—",                                              "Geo sync error log",                                            False),
]

ALL_ROWS = SYS_ROWS + PROD_ROWS + CRM_ROWS

# ─── Colour palettes ──────────────────────────────────────────────────────────
TYPE_COLORS = {
    "master":      "#185FA5",
    "transaction": "#3B6D11",
    "join":        "#854F0B",
    "security":    "#534AB7",
    "sync":        "#5F5E5A",
}

MODULE_ACCENT = {
    "sys":  "#7C3AED",   # purple — shared system
    "prod": "#0369A1",   # blue  — production
    "crm":  "#065F46",   # green — CRM
}

WAVE_COLORS = [
    "#185FA5","#3B6D11","#854F0B","#72243E","#3C3489",
    "#085041","#993C1D","#444441","#791F1F","#412402",
    "#042C53","#173404","#501313",
]

# ─── Google Sheets helpers ────────────────────────────────────────────────────
@st.cache_resource(ttl=0)
def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["sheet_id"])
    return sh.sheet1

def load_done_from_sheet(ws) -> dict:
    records = ws.get_all_records()
    return {r["table_name"]: int(r.get("done", 0)) for r in records}

def save_done_to_sheet(ws, table_name: str, done_val: int):
    cell = ws.find(table_name, in_column=1)
    if cell:
        ws.update_cell(cell.row, 2, done_val)
    else:
        ws.append_row([table_name, done_val])

def bulk_init_sheet(ws, all_tables: list):
    existing = ws.col_values(1)
    if not existing or existing == ["table_name"]:
        data = [["table_name", "done"]] + [[t, 0] for t in all_tables]
        ws.clear()
        ws.update("A1", data)

# ─── Session state ────────────────────────────────────────────────────────────
def init_state():
    if "done_map" not in st.session_state:
        ws = get_sheet()
        all_tables = [r[1] for r in ALL_ROWS]
        bulk_init_sheet(ws, all_tables)
        st.session_state.done_map = load_done_from_sheet(ws)
        for t in all_tables:
            if t not in st.session_state.done_map:
                st.session_state.done_map[t] = 0

# ─── Badges & HTML helpers ────────────────────────────────────────────────────
def wave_badge(wave: int) -> str:
    color = WAVE_COLORS[(wave - 1) % len(WAVE_COLORS)]
    return (
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:22px;height:22px;border-radius:50%;background:{color}22;'
        f'color:{color};font-weight:600;font-size:11px;">{wave}</span>'
    )

def type_badge(t: str) -> str:
    c = TYPE_COLORS.get(t, "#888")
    return (
        f'<span style="display:inline-block;padding:1px 7px;border-radius:10px;'
        f'font-size:11px;font-weight:500;background:{c}22;color:{c};">{t}</span>'
    )

def db_name_html(tracker: str, actual: str) -> str:
    """Show tracker name + the real DB table name if different."""
    done = st.session_state.done_map.get(tracker, 0) == 1
    tick = "✅ " if done else ""
    if actual == "—" or actual == tracker:
        return f'{tick}<code style="font-size:10px;">{tracker}</code>'
    return (
        f'{tick}<code style="font-size:10px;">{tracker}</code>'
        f'<br><span style="font-size:9px;color:#666;">DB: </span>'
        f'<code style="font-size:9px;color:#7C3AED;">{actual}</code>'
    )

def dep_html(deps: str) -> str:
    if deps == "—":
        return '<span style="color:#aaa;font-size:11px;">—</span>'
    parts = [d.strip() for d in deps.split("·")]
    spans = " · ".join(
        f'<code style="font-size:10px;background:#f0f0f0;color:#1a1a1a;'
        f'padding:1px 4px;border-radius:3px;">{p}</code>'
        for p in parts
    )
    return spans

def render_table(subset: list):
    # subset rows: (wave, tracker_name, actual_db_table, type, deps, note, is_new)
    if not subset:
        st.markdown("_No tables in this group._")
        return

    done_map = st.session_state.done_map
    rows_html = ""
    for row in subset:
        wave, tracker, actual_db, ttype, deps, note, is_new = row
        done   = done_map.get(tracker, 0) == 1
        row_bg = "#e8f8f2" if done else ("#fffbea" if is_new else "#ffffff")
        new_tag = (
            ' <span style="font-size:9px;font-weight:700;background:#FEF3C7;'
            'color:#B45309;padding:1px 5px;border-radius:4px;">NEW</span>'
            if is_new else ""
        )
        rows_html += f"""
        <tr style="background:{row_bg};">
          <td style="padding:6px 10px;border-bottom:1px solid #eee;">{wave_badge(wave)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #eee;font-family:monospace;color:#1a1a1a;font-weight:500;">{db_name_html(tracker, actual_db)}{new_tag}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #eee;">{type_badge(ttype)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:11px;">{dep_html(deps)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:11px;color:#444;">{note}</td>
        </tr>"""

    st.markdown(f"""
    <div style="overflow-x:auto;border:1px solid #e0e0e0;border-radius:8px;margin-bottom:12px;">
    <table style="width:100%;border-collapse:collapse;font-size:12px;">
      <thead>
        <tr style="background:#f0f4f8;">
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#333;font-weight:700;border-bottom:2px solid #ddd;white-space:nowrap;">Wave</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#333;font-weight:700;border-bottom:2px solid #ddd;">Tracker Name <span style="font-weight:400;color:#7C3AED;">/ Actual DB Table</span></th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#333;font-weight:700;border-bottom:2px solid #ddd;">Type</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#333;font-weight:700;border-bottom:2px solid #ddd;">Depends On (FK Parents)</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#333;font-weight:700;border-bottom:2px solid #ddd;">Purpose / Note</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
    """, unsafe_allow_html=True)

# ─── Mark-done controls ───────────────────────────────────────────────────────
def done_controls(subset: list, key_prefix: str):
    table_names    = [r[1] for r in subset]
    done_map       = st.session_state.done_map
    currently_done = [t for t in table_names if done_map.get(t, 0) == 1]

    selected = st.multiselect(
        "✅ Mark as done (select / deselect):",
        options=table_names,
        default=currently_done,
        key=f"ms_{key_prefix}",
        label_visibility="visible",
    )

    if set(selected) != set(currently_done):
        ws = get_sheet()
        for t in table_names:
            new_val = 1 if t in selected else 0
            if done_map.get(t, 0) != new_val:
                done_map[t] = new_val
                save_done_to_sheet(ws, t, new_val)
        st.toast("Saved changes ✓", icon="✅")
        st.rerun()

# ─── Per-module wave renderer ─────────────────────────────────────────────────
def wave_match(wave: int, is_new: bool, wave_filter: str) -> bool:
    if wave_filter == "All waves":  return True
    if wave_filter == "W9–13":      return wave >= 9
    if wave_filter == "New only":   return is_new
    return wave == int(wave_filter[1:])

def render_module(rows: list, module_key: str, wave_filter: str):
    filtered = [r for r in rows if wave_match(r[0], r[6], wave_filter)]
    st.caption(f"Showing **{len(filtered)}** of **{len(rows)}** tables")

    if wave_filter == "All waves":
        for wave_num in range(1, 14):
            wave_rows = [r for r in filtered if r[0] == wave_num]
            if not wave_rows:
                continue
            wc = WAVE_COLORS[(wave_num - 1) % len(WAVE_COLORS)]
            done_count = sum(
                1 for r in wave_rows if st.session_state.done_map.get(r[1], 0) == 1
            )
            with st.expander(
                f"**Wave {wave_num}** — {len(wave_rows)} tables  ·  {done_count}/{len(wave_rows)} done",
                expanded=(wave_num <= 3),
            ):
                render_table(wave_rows)
                done_controls(wave_rows, f"{module_key}_w{wave_num}")
    else:
        render_table(filtered)
        done_controls(filtered, f"{module_key}_filtered_{wave_filter}")

# ─── App layout ───────────────────────────────────────────────────────────────
def main():
    init_state()

    st.title("🗄️ SQL Export Order Tracker  v2")
    st.caption(
        "Three-module layout: **🔷 Shared System** · **🌾 Production** · **🤝 CRM**  "
        "· Tracker names mapped to actual DB table names · progress saved to Google Sheets"
    )

    # Legend
    cols = st.columns(7)
    legends = [
        ("●", "Master",       "#185FA5"),
        ("●", "Transaction",  "#3B6D11"),
        ("●", "Join / M:N",   "#854F0B"),
        ("●", "Security",     "#534AB7"),
        ("●", "Sync/staging", "#5F5E5A"),
        ("●", "NEW",          "#B45309"),
        ("◆", "Actual DB name differs", "#7C3AED"),
    ]
    for col, (icon, label, color) in zip(cols, legends):
        col.markdown(
            f'<span style="font-size:12px;color:{color};">{icon} {label}</span>',
            unsafe_allow_html=True,
        )

    st.divider()

    # Overall progress
    done_map    = st.session_state.done_map
    total       = len(ALL_ROWS)
    done_count  = sum(1 for r in ALL_ROWS if done_map.get(r[1], 0) == 1)
    sys_total   = len(SYS_ROWS)
    prod_total  = len(PROD_ROWS)
    crm_total   = len(CRM_ROWS)
    sys_done    = sum(1 for r in SYS_ROWS  if done_map.get(r[1], 0) == 1)
    prod_done   = sum(1 for r in PROD_ROWS if done_map.get(r[1], 0) == 1)
    crm_done    = sum(1 for r in CRM_ROWS  if done_map.get(r[1], 0) == 1)

    st.progress(
        done_count / total if total else 0,
        text=(
            f"**Overall: {done_count} / {total}** exported "
            f"({done_count * 100 // total if total else 0}%)  ·  "
            f"🔷 Shared {sys_done}/{sys_total}  ·  "
            f"🌾 Prod {prod_done}/{prod_total}  ·  "
            f"🤝 CRM {crm_done}/{crm_total}"
        ),
    )

    st.divider()

    # Global controls
    col1, col2 = st.columns([3, 2])
    with col1:
        search = st.text_input(
            "🔍 Search tracker name or actual DB table name",
            placeholder="e.g. employees, tr_field_visits, organizer…",
        )
    with col2:
        wave_options = ["All waves", "W1", "W2", "W3", "W4", "W5", "W6",
                        "W7", "W8", "W9–13", "New only"]
        wave_filter = st.selectbox("Filter by wave", wave_options)

    # Search mode
    if search.strip():
        sv = search.strip().lower()

        def parse_deps(deps):
            if not deps or deps == "—":
                return []
            return [d.strip().lower() for d in deps.split("·")]

        for module_label, module_rows in [
            ("🔷 Shared System", SYS_ROWS),
            ("🌾 Production",    PROD_ROWS),
            ("🤝 CRM",           CRM_ROWS),
        ]:
            # match on tracker name OR actual DB name
            matched     = [r for r in module_rows if sv in r[1].lower() or sv in r[2].lower()]
            matched_set = {r[1].lower() for r in matched}

            parent_names = set()
            for r in matched:
                for p in parse_deps(r[4]):
                    if p not in matched_set:
                        parent_names.add(p)

            child_names = set()
            for r in module_rows:
                tl = r[1].lower()
                if tl in matched_set:
                    continue
                if any(m in parse_deps(r[4]) for m in matched_set):
                    child_names.add(tl)

            parent_rows = [r for r in module_rows if r[1].lower() in parent_names]
            child_rows  = [r for r in module_rows if r[1].lower() in child_names]

            if not matched and not parent_rows and not child_rows:
                continue

            st.subheader(module_label)
            if matched:
                st.markdown(f"**🎯 Matched ({len(matched)})**")
                render_table(matched)
                done_controls(matched, f"{module_label}_match")
            if parent_rows:
                st.markdown(f"**⬆️ FK Parents ({len(parent_rows)})**")
                render_table(parent_rows)
            if child_rows:
                st.markdown(f"**⬇️ Dependents ({len(child_rows)})**")
                render_table(child_rows)
    else:
        tab_sys, tab_prod, tab_crm = st.tabs([
            "🔷  Shared System (sys_)",
            "🌾  Production Module",
            "🤝  CRM Module",
        ])

        with tab_sys:
            st.markdown(
                "**Shared system tables** — used by BOTH production and CRM. "
                "These include employees, roles, departments, grades, geo spine "
                "(zones → regions → territories), varieties, crops, expense chain, "
                "and security tables. Export these **before** either module."
            )
            st.info(
                "💡 Tracker names use prefix `sys_` for clarity. "
                "The **Actual DB Name** column (purple) shows the real MySQL table name — "
                "most of these have NO module prefix in the database.",
                icon="ℹ️",
            )
            render_module(SYS_ROWS, "sys", wave_filter)

        with tab_prod:
            st.markdown(
                "**Production-only tables** — growers, organizers, monitoring, "
                "purity reports, planting logs, and production-specific sync tables. "
                "Depends on Shared System tables being exported first."
            )
            render_module(PROD_ROWS, "prod", wave_filter)

        with tab_crm:
            st.markdown(
                "**CRM-only tables** — farmers, distributors, retailers, "
                "field visits, PSA/PDA flows, DG activities, and CRM sales budgets. "
                "Depends on Shared System tables being exported first."
            )
            render_module(CRM_ROWS, "crm", wave_filter)

    # Danger zone
    st.divider()
    with st.expander("⚠️ Danger zone"):
        if st.button("Reset ALL progress to zero", type="secondary"):
            ws = get_sheet()
            all_tables = [r[1] for r in ALL_ROWS]
            for t in all_tables:
                st.session_state.done_map[t] = 0
            data = [["table_name", "done"]] + [[t, 0] for t in all_tables]
            ws.clear()
            ws.update("A1", data)
            st.success("All progress reset.")
            st.rerun()


if __name__ == "__main__":
    main()
