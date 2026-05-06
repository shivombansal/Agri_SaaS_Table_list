import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import time

st.set_page_config(
    page_title="SQL Export Tracker",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Production Module Tables ─────────────────────────────────────────────────
# Naming convention: {type_prefix}_{prod}_{tablename}
# type prefixes: mst_ = master, tr_ = transaction, jn_ = join/M:N, sync_ = sync/staging, sec_ = security
PROD_ROWS = [
    # ── Wave 1 — leaf roots (no dependencies) ────────────────────────────────
    (1,"mst_prod_crops","master","—","Crop master for production module",False),
    (1,"mst_prod_years","master","—","Season / financial year",False),
    (1,"mst_prod_zones","master","—","Top-level production geography",False),
    (1,"mst_prod_states","master","—","State master for prod employee linking",False),
    (1,"mst_prod_departments","master","—","HR department master",False),
    (1,"mst_prod_employee_grades","master","—","Grade hierarchy for approvals",False),
    (1,"mst_prod_employee_hq","master","—","Employee HQ / location master",False),
    (1,"mst_prod_designations","master","—","Employee designation / title",False),
    (1,"mst_prod_crop_types","master","—","Crop type grouping",False),
    (1,"mst_prod_dropdown_master","master","—","UI dropdown options",False),
    (1,"mst_prod_mode_of_travel","master","—","Travel mode (car, train…)",False),
    (1,"mst_prod_type_of_travel","master","—","Travel type (local, outstation…)",False),
    (1,"mst_prod_production_locations","master","—","Production location master",False),
    (1,"mst_prod_plants","master","—","Plant / processing sites",False),
    (1,"mst_prod_product_skus","master","—","SKU master",False),
    (1,"mst_prod_female_codes","master","—","Variety female parent codes",False),
    (1,"mst_prod_male_codes","master","—","Variety male parent codes",False),
    (1,"tr_prod_attachments","transaction","—","File attachment store",False),
    (1,"sec_prod_sessions","security","—","Login / session tokens",False),
    (1,"sec_prod_otps","security","—","OTP auth records",False),
    (1,"tr_prod_notifications","security","—","Push notifications",False),
    (1,"tr_prod_travel_reimbursements","transaction","—","Standalone reimbursement records",False),
    (1,"sync_prod_zone_dynamics","sync","—","Dynamics zone staging",False),
    (1,"sync_prod_crops_dynamics","sync","—","Dynamics crop staging",False),
    (1,"sync_prod_varieties_dynamics","sync","—","Dynamics variety staging",False),
    (1,"mst_prod_seed_types","master","—","Seed type master",True),
    (1,"mst_prod_seed_categories","master","—","Seed category master",True),
    # ── Wave 2 ────────────────────────────────────────────────────────────────
    (2,"mst_prod_regions","master","mst_prod_zones","Geo region under zone",False),
    (2,"mst_prod_sub_departments","master","mst_prod_departments","Sub-department grouping",False),
    (2,"tr_prod_tada_workflows","transaction","mst_prod_departments","TADA workflow rules by dept",False),
    (2,"tr_prod_working_hours","transaction","mst_prod_departments","Working-hour policy by dept",False),
    (2,"tr_prod_travel_grade_rules","transaction","mst_prod_departments","Claim caps by employee grade",False),
    (2,"tr_prod_policy","transaction","mst_prod_departments · tr_prod_attachments","Policy document store",False),
    (2,"mst_prod_seasons","master","mst_prod_years","Season master (Kharif, Rabi, Zaid…)",True),
    # ── Wave 3 ────────────────────────────────────────────────────────────────
    (3,"mst_prod_territories","master","mst_prod_regions","Territory under region",False),
    (3,"mst_prod_blocks","master","mst_prod_regions","Production block master",False),
    (3,"mst_prod_roles","master","mst_prod_departments · mst_prod_sub_departments","Role / permissions master",False),
    (3,"mst_prod_varieties","master","mst_prod_crops · mst_prod_product_skus · mst_prod_female_codes · mst_prod_male_codes · mst_prod_seed_types · mst_prod_seed_categories","Core variety master",False),
    (3,"sync_prod_region_dynamics","sync","sync_prod_zone_dynamics","Dynamics region staging",False),
    (3,"mst_prod_mode_of_travel_mapping","master","mst_prod_mode_of_travel · mst_prod_type_of_travel","Travel mode-type mapping",False),
    (3,"jn_prod_zone_region","join","mst_prod_zones · mst_prod_regions","Zone ↔ Region M:N",False),
    (3,"mst_prod_terms","master","mst_prod_years · mst_prod_crops","Crop terms per year",False),
    # ── Wave 4 ────────────────────────────────────────────────────────────────
    (4,"mst_prod_districts","master","mst_prod_territories","Production district master",False),
    (4,"mst_prod_villages","master","mst_prod_blocks","Production village master",False),
    (4,"mst_prod_crop_analytics","master","mst_prod_crops · mst_prod_years · mst_prod_varieties · mst_prod_regions","Analytics baseline for targets",False),
    (4,"sync_prod_territory_dynamics","sync","sync_prod_region_dynamics","Dynamics territory staging",False),
    (4,"tr_prod_employees","transaction","mst_prod_departments · mst_prod_sub_departments · mst_prod_roles · mst_prod_employee_grades · mst_prod_employee_hq · mst_prod_states · mst_prod_designations · mst_prod_crop_types","Central user / employee record",False),
    (4,"tr_prod_role_permissions","security","mst_prod_roles","Role permission matrix",False),
    (4,"tr_prod_plans","transaction","mst_prod_varieties · mst_prod_years","Base production plan (non-PS)",False),
    (4,"jn_prod_region_territory","join","mst_prod_regions · mst_prod_territories","Region ↔ Territory M:N",False),
    (4,"jn_prod_block_villages","join","mst_prod_blocks · mst_prod_villages","Block ↔ Village M:N",False),
    # ── Wave 5 ────────────────────────────────────────────────────────────────
    (5,"mst_prod_mdo_hqs","master","mst_prod_districts","MDO HQ locations",False),
    (5,"mst_prod_organizers","master","mst_prod_zones · mst_prod_regions · mst_prod_production_locations · tr_prod_employees","Organizer / field agent master",False),
    (5,"tr_prod_tada_workflow_approvers","transaction","tr_prod_tada_workflows · mst_prod_employee_grades · mst_prod_roles","Approver matrix per workflow",False),
    (5,"tr_prod_attendance","transaction","tr_prod_employees","Daily attendance log",False),
    (5,"tr_prod_user_permissions","security","tr_prod_employees","User-level permission overrides",False),
    (5,"tr_prod_plan_ps","transaction","mst_prod_varieties · mst_prod_years · mst_prod_crop_analytics","PS production plan",False),
    (5,"tr_prod_plan_hybrids","transaction","mst_prod_varieties · mst_prod_years · mst_prod_crop_analytics","Hybrid forecast / plan",False),
    (5,"tr_prod_location_allotments","transaction","mst_prod_varieties · mst_prod_years","Location allotment header",False),
    (5,"tr_prod_remark_histories","transaction","mst_prod_varieties · mst_prod_years · tr_prod_employees","Planning remarks audit trail",False),
    (5,"tr_prod_sales_plan_histories","transaction","mst_prod_varieties · mst_prod_years · tr_prod_employees","Sales plan change log",False),
    (5,"jn_prod_employee_block","join","tr_prod_employees · mst_prod_blocks","Emp ↔ Block M:N",False),
    (5,"jn_prod_employee_crop","join","tr_prod_employees · mst_prod_crops","Emp ↔ Crop M:N",False),
    (5,"jn_prod_employee_district","join","tr_prod_employees · mst_prod_districts","Emp ↔ District M:N",False),
    (5,"jn_prod_employee_region","join","tr_prod_employees · mst_prod_regions","Emp ↔ Region M:N",False),
    (5,"jn_prod_employee_variety","join","tr_prod_employees · mst_prod_varieties","Emp ↔ Variety M:N",False),
    (5,"jn_prod_employee_village","join","tr_prod_employees · mst_prod_villages","Emp ↔ Village M:N",False),
    (5,"jn_prod_employee_zone","join","tr_prod_employees · mst_prod_zones","Emp ↔ Zone M:N",False),
    # ── Wave 6 ────────────────────────────────────────────────────────────────
    (6,"mst_prod_growers","master","mst_prod_organizers · tr_prod_employees · mst_prod_zones · mst_prod_regions · mst_prod_blocks · mst_prod_villages · mst_prod_crops · mst_prod_varieties","Grower registry — core production record",False),
    (6,"jn_prod_district_mdohq","join","mst_prod_districts · mst_prod_mdo_hqs","District ↔ MDO HQ M:N",False),
    (6,"jn_prod_mdohq_blocks","join","mst_prod_mdo_hqs · mst_prod_blocks","MDO HQ ↔ Block M:N",False),
    (6,"jn_prod_employee_mdohq","join","tr_prod_employees · mst_prod_mdo_hqs","Emp ↔ MDO HQ M:N",False),
    (6,"jn_prod_org_block","join","mst_prod_organizers · mst_prod_blocks","Organizer ↔ Block M:N",False),
    (6,"jn_prod_org_emp","join","mst_prod_organizers · tr_prod_employees","Organizer ↔ Employee M:N",False),
    (6,"tr_prod_organizer_performances","transaction","mst_prod_organizers · mst_prod_varieties · mst_prod_years · mst_prod_seasons","Organizer scoring metrics",False),
    (6,"tr_prod_region_allotments","transaction","tr_prod_location_allotments · mst_prod_crop_analytics · mst_prod_varieties · mst_prod_regions","Region allotment breakdown",False),
    # ── Wave 7 ────────────────────────────────────────────────────────────────
    (7,"tr_prod_organizer_selection","transaction","mst_prod_varieties · mst_prod_years · mst_prod_seasons · mst_prod_regions · mst_prod_organizers · tr_prod_organizer_performances","Organizer selection decisions",False),
    (7,"tr_prod_grower_preparations","transaction","mst_prod_varieties · mst_prod_years · mst_prod_seasons · mst_prod_regions · mst_prod_organizers · mst_prod_growers","Sowing readiness tracking",False),
    (7,"tr_prod_monitorings","transaction","mst_prod_varieties · mst_prod_years · mst_prod_seasons · mst_prod_regions · mst_prod_growers · tr_prod_employees","Crop lifecycle monitoring",False),
    (7,"tr_prod_crop_status","transaction","mst_prod_varieties · mst_prod_years · mst_prod_seasons · mst_prod_regions · mst_prod_growers · tr_prod_employees","Crop status snapshot",False),
    (7,"tr_prod_crop_status_history","transaction","mst_prod_varieties · mst_prod_years · mst_prod_seasons · mst_prod_regions · mst_prod_growers · tr_prod_employees","Crop status audit trail",False),
    (7,"tr_prod_purity_reports","transaction","mst_prod_varieties · mst_prod_years · mst_prod_regions · mst_prod_plants · mst_prod_organizers","Quality / purity reports",False),
    (7,"tr_prod_summary_reports","transaction","mst_prod_varieties · mst_prod_years · mst_prod_regions · mst_prod_organizers","Production summary header",False),
    (7,"tr_prod_daily_visits","transaction","mst_prod_varieties · mst_prod_years · mst_prod_regions · tr_prod_employees · mst_prod_growers","Daily field visit log",False),
    (7,"tr_prod_loc_altmt_histories","transaction","tr_prod_location_allotments · tr_prod_employees","Location allotment change log",False),
    # ── Wave 8 ────────────────────────────────────────────────────────────────
    (8,"tr_prod_summary_weekly","transaction","tr_prod_summary_reports · mst_prod_varieties · mst_prod_years · mst_prod_regions · mst_prod_organizers","Weekly production breakdown",False),
    (8,"tr_prod_monitoring_sample_checks","transaction","tr_prod_monitorings","Sample check child records",False),
    # ── Wave 9 ────────────────────────────────────────────────────────────────
    (9,"tr_prod_expenses","transaction","tr_prod_employees · tr_prod_attachments","Expense claim header",False),
    # ── Wave 10 ───────────────────────────────────────────────────────────────
    (10,"tr_prod_expense_line_items","transaction","tr_prod_expenses · tr_prod_attachments","Itemised expense lines",False),
    (10,"tr_prod_approvals","transaction","tr_prod_expenses · tr_prod_employees","Current approval chain",False),
    (10,"tr_prod_expense_approval_history","transaction","tr_prod_expenses · tr_prod_employees","Immutable approval log",False),
    # ── Wave 11 ───────────────────────────────────────────────────────────────
    (11,"tr_prod_expense_approval_changes","transaction","tr_prod_expenses · tr_prod_expense_approval_history","Fine-grained approval change log",False),
    (11,"jn_prod_policy_departments","join","tr_prod_policy · mst_prod_departments","Policy ↔ Dept M:N",False),
    # ── Wave 13 — Sync / Integration ─────────────────────────────────────────
    (13,"sync_prod_run_log","sync","—","Production sync run monitor",False),
    (13,"sync_prod_error_log","sync","—","Production sync error log",False),
    (13,"sync_prod_planting_log","sync","—","Planting payload audit",False),
    (13,"sync_prod_seed_dist_log","sync","—","Seed distribution payload audit",False),
    (13,"sync_prod_purity_log","sync","—","Purity report payload audit",False),
]

# ─── CRM Module Tables ────────────────────────────────────────────────────────
# Naming convention: {type_prefix}_{crm}_{tablename}
CRM_ROWS = [
    # ── Wave 1 — leaf roots ───────────────────────────────────────────────────
    (1,"mst_crm_crops","master","—","Crop master for CRM module",False),
    (1,"mst_crm_states","master","—","CRM state master",False),
    (1,"mst_crm_years","master","—","CRM year / period master",False),
    (1,"mst_crm_departments","master","—","HR department master",False),
    (1,"mst_crm_employee_grades","master","—","Grade hierarchy for approvals",False),
    (1,"mst_crm_employee_hq","master","—","Employee HQ / location master",False),
    (1,"mst_crm_designations","master","—","Employee designation / title",False),
    (1,"mst_crm_crop_types","master","—","Crop type grouping",False),
    (1,"mst_crm_activities","master","—","CRM activity type master",False),
    (1,"mst_crm_dropdown_master","master","—","UI dropdown options",False),
    (1,"mst_crm_mode_of_travel","master","—","Travel mode (car, train…)",False),
    (1,"mst_crm_type_of_travel","master","—","Travel type (local, outstation…)",False),
    (1,"mst_crm_city_master","master","—","Standalone city list",False),
    (1,"mst_crm_product_skus","master","—","SKU master",False),
    (1,"tr_crm_attachments","transaction","—","File attachment store",False),
    (1,"sec_crm_sessions","security","—","Login / session tokens",False),
    (1,"sec_crm_otps","security","—","OTP auth records",False),
    (1,"tr_crm_notifications","security","—","Push notifications",False),
    (1,"tr_crm_travel_reimbursements","transaction","—","Standalone reimbursement records",False),
    (1,"sync_crm_zone_response","sync","—","Sync zone response staging",False),
    (1,"sync_crm_crop_response","sync","—","Sync crop response staging",False),
    (1,"sync_crm_variety_sku_response","sync","—","Sync variety SKU response staging",False),
    (1,"sync_crm_distributors_response","sync","—","Sync distributor response staging",False),
    # ── Wave 2 ────────────────────────────────────────────────────────────────
    (2,"mst_crm_districts","master","mst_crm_states","CRM district master",False),
    (2,"mst_crm_sub_departments","master","mst_crm_departments","Sub-department grouping",False),
    (2,"tr_crm_tada_workflows","transaction","mst_crm_departments","TADA workflow rules by dept",False),
    (2,"tr_crm_working_hours","transaction","mst_crm_departments","Working-hour policy by dept",False),
    (2,"tr_crm_travel_grade_rules","transaction","mst_crm_departments","Claim caps by employee grade",False),
    (2,"tr_crm_holiday","transaction","mst_crm_states","State holiday calendar",False),
    (2,"tr_crm_policy","transaction","mst_crm_departments · tr_crm_attachments","Policy document store",False),
    # ── Wave 3 ────────────────────────────────────────────────────────────────
    (3,"mst_crm_blocks","master","mst_crm_districts","CRM block master",False),
    (3,"mst_crm_roles","master","mst_crm_departments · mst_crm_sub_departments","Role / permissions master",False),
    (3,"mst_crm_varieties","master","mst_crm_crops · mst_crm_product_skus","Core variety master for CRM",False),
    (3,"mst_crm_mode_of_travel_mapping","master","mst_crm_mode_of_travel · mst_crm_type_of_travel","Travel mode-type mapping",False),
    # ── Wave 4 ────────────────────────────────────────────────────────────────
    (4,"mst_crm_villages","master","mst_crm_blocks","CRM village master",False),
    (4,"mst_crm_banners","master","—","Scheme / banner master",False),
    (4,"mst_crm_focused_varieties","master","mst_crm_varieties","Priority varieties for CRM planning",False),
    (4,"mst_crm_city_category","master","mst_crm_states · mst_crm_districts · mst_crm_blocks · mst_crm_villages","City category tagging",False),
    (4,"tr_crm_employees","transaction","mst_crm_departments · mst_crm_sub_departments · mst_crm_roles · mst_crm_employee_grades · mst_crm_employee_hq · mst_crm_states · mst_crm_designations · mst_crm_crop_types","Central user / employee record",False),
    (4,"tr_crm_role_permissions","security","mst_crm_roles","Role permission matrix",False),
    (4,"tr_crm_national_sales_budget","transaction","mst_crm_varieties · mst_crm_years","National sales budget header",False),
    # ── Wave 5 ────────────────────────────────────────────────────────────────
    (5,"tr_crm_tada_workflow_approvers","transaction","tr_crm_tada_workflows · mst_crm_employee_grades · mst_crm_roles","Approver matrix per workflow",False),
    (5,"tr_crm_farmer","transaction","tr_crm_employees · mst_crm_districts · mst_crm_blocks · mst_crm_villages","CRM farmer master",False),
    (5,"tr_crm_distributors","transaction","tr_crm_employees · mst_crm_districts · mst_crm_states · mst_crm_blocks","Distributor master",False),
    (5,"tr_crm_retailers","transaction","tr_crm_employees · mst_crm_districts · mst_crm_blocks","Retailer master",False),
    (5,"tr_crm_attendance","transaction","tr_crm_employees","Daily attendance log",False),
    (5,"tr_crm_user_permissions","security","tr_crm_employees","User-level permission overrides",False),
    (5,"tr_crm_menu_permissions","security","mst_crm_roles · tr_crm_employees","CRM menu access control",False),
    (5,"tr_crm_sales_target_histories","transaction","mst_crm_varieties · mst_crm_years · tr_crm_employees","CRM target change log",False),
    (5,"jn_crm_employee_crop","join","tr_crm_employees · mst_crm_crops","Emp ↔ Crop M:N",False),
    (5,"jn_crm_employee_variety","join","tr_crm_employees · mst_crm_varieties","Emp ↔ Variety M:N",False),
    (5,"jn_crm_dist_block","join","mst_crm_districts · mst_crm_blocks","Production district ↔ CRM block map",False),
    # ── Wave 6 ────────────────────────────────────────────────────────────────
    (6,"tr_crm_distributor_visits","transaction","tr_crm_distributors · mst_crm_blocks · tr_crm_employees · mst_crm_banners","Distributor visit records",False),
    (6,"tr_crm_retailer_visits","transaction","tr_crm_retailers · mst_crm_blocks · tr_crm_employees · mst_crm_banners","Retailer visit records",False),
    (6,"tr_crm_seasons","transaction","tr_crm_employees · tr_crm_retailers","Seasonal retailer tags",False),
    (6,"tr_crm_seasons_distributor","transaction","tr_crm_employees · tr_crm_distributors","Seasonal distributor tags",False),
    (6,"tr_crm_farmer_purchase_pattern","transaction","tr_crm_farmer · mst_crm_years · mst_crm_crops · mst_crm_varieties · mst_crm_product_skus","Farmer purchase behavior",False),
    (6,"tr_crm_zone_sales_budget","transaction","mst_crm_varieties · mst_crm_years · tr_crm_national_sales_budget","Zone sales budget",False),
    (6,"sync_crm_distributors_dynamics","sync","tr_crm_employees","Dynamics distributor mirror",False),
    (6,"sync_crm_distributors_dynamics_v2","sync","tr_crm_employees","Dynamics distributor mirror v2",False),
    (6,"sync_crm_distributor_integration","sync","tr_crm_employees","Distributor integration log",False),
    # ── Wave 7 ────────────────────────────────────────────────────────────────
    (7,"tr_crm_activity_planning","transaction","mst_crm_years · mst_crm_varieties · tr_crm_employees · mst_crm_focused_varieties","CRM FC activity plan",False),
    (7,"tr_crm_activity_planning_veg","transaction","mst_crm_years · mst_crm_varieties · tr_crm_employees · mst_crm_focused_varieties","CRM Veg activity plan",False),
    (7,"tr_crm_region_sales_budget","transaction","mst_crm_varieties · mst_crm_years · tr_crm_zone_sales_budget","Region sales budget",False),
    # ── Wave 8 ────────────────────────────────────────────────────────────────
    (8,"tr_crm_field_visits","transaction","tr_crm_employees · tr_crm_farmer · mst_crm_varieties · mst_crm_activities · mst_crm_blocks · mst_crm_villages","Core CRM field visit — PDA/PSA starts here",False),
    (8,"tr_crm_territory_sales_budget","transaction","mst_crm_varieties · mst_crm_years · tr_crm_region_sales_budget","Territory sales budget",False),
    (8,"tr_crm_territory_sales_budget_veg","transaction","mst_crm_varieties · mst_crm_years","Territory Veg sales budget",False),
    (8,"tr_crm_region_sales_budget_veg","transaction","mst_crm_varieties · mst_crm_years","Region Veg sales budget",False),
    (8,"tr_crm_activity_approval_history","transaction","mst_crm_years · tr_crm_employees","Activity approval log",False),
    (8,"tr_crm_activity_plan_change_history","transaction","mst_crm_years · tr_crm_employees · mst_crm_focused_varieties","Activity plan change log",False),
    # ── Wave 9 ────────────────────────────────────────────────────────────────
    (9,"tr_crm_fieldvisit_remarks","transaction","tr_crm_field_visits · tr_crm_employees","Manager remarks on field visits",False),
    (9,"tr_crm_pda_psa_approval_history","transaction","tr_crm_field_visits · tr_crm_employees","PDA/PSA approval log",False),
    (9,"tr_crm_dgactivity","transaction","tr_crm_employees · tr_crm_field_visits · tr_crm_farmer · mst_crm_villages · mst_crm_activities · mst_crm_varieties · mst_crm_crops · mst_crm_blocks","DG activity execution (PDA)",False),
    (9,"tr_crm_psa_approval","transaction","mst_crm_activities · mst_crm_varieties · mst_crm_villages · tr_crm_employees","PSA approval header",False),
    # ── Wave 10 ───────────────────────────────────────────────────────────────
    (10,"tr_crm_dgactivity_remarks","transaction","tr_crm_employees · tr_crm_dgactivity","DG activity review remarks",False),
    (10,"tr_crm_psa_approval_history","transaction","tr_crm_psa_approval · tr_crm_employees","PSA approval action log",False),
    (10,"tr_crm_psa_dgactivity","transaction","tr_crm_psa_approval · tr_crm_employees · mst_crm_villages · mst_crm_activities · mst_crm_varieties · mst_crm_crops","Activity records under PSA",False),
    # ── Wave 11 ───────────────────────────────────────────────────────────────
    (11,"tr_crm_psa_dgactivity_remarks","transaction","tr_crm_employees · tr_crm_psa_dgactivity","PSA DG remark log",False),
    (11,"tr_crm_expenses","transaction","tr_crm_employees · tr_crm_attachments · tr_crm_dgactivity · tr_crm_psa_dgactivity","Expense claim header",False),
    # ── Wave 12 ───────────────────────────────────────────────────────────────
    (12,"tr_crm_expense_line_items","transaction","tr_crm_expenses · tr_crm_attachments","Itemised expense lines",False),
    (12,"tr_crm_approvals","transaction","tr_crm_expenses · tr_crm_employees","Current approval chain",False),
    (12,"tr_crm_expense_approval_history","transaction","tr_crm_expenses · tr_crm_employees","Immutable approval log",False),
    # ── Wave 13 ───────────────────────────────────────────────────────────────
    (13,"tr_crm_expense_approval_changes","transaction","tr_crm_expenses · tr_crm_expense_approval_history","Fine-grained approval change log",False),
    (13,"jn_crm_policy_departments","join","tr_crm_policy · mst_crm_departments","Policy ↔ Dept M:N",False),
    (13,"sync_crm_geo_run_log","sync","—","Geo sync run monitor",False),
    (13,"sync_crm_geo_error_log","sync","—","Geo sync error log",False),
]

# Combined list used for progress tracking and Google Sheets init
ALL_ROWS = PROD_ROWS + CRM_ROWS

# ─── Colour palettes ──────────────────────────────────────────────────────────

TYPE_COLORS = {
    "master":      "#185FA5",
    "transaction": "#3B6D11",
    "join":        "#854F0B",
    "security":    "#534AB7",
    "sync":        "#5F5E5A",
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
    """Returns {table_name: 0|1}"""
    records = ws.get_all_records()
    return {r["table_name"]: int(r.get("done", 0)) for r in records}


def save_done_to_sheet(ws, table_name: str, done_val: int):
    """Finds or creates the row for table_name and sets done."""
    cell = ws.find(table_name, in_column=1)
    if cell:
        ws.update_cell(cell.row, 2, done_val)
    else:
        ws.append_row([table_name, done_val])


def bulk_init_sheet(ws, all_tables: list):
    """Writes all table names with done=0 if sheet is empty."""
    existing = ws.col_values(1)
    if not existing or existing == ["table_name"]:
        data = [["table_name", "done"]] + [[t, 0] for t in all_tables]
        ws.clear()
        ws.update("A1", data)


# ─── Session state bootstrap ──────────────────────────────────────────────────

def init_state():
    if "done_map" not in st.session_state:
        ws = get_sheet()
        all_tables = [r[1] for r in ALL_ROWS]
        bulk_init_sheet(ws, all_tables)
        st.session_state.done_map = load_done_from_sheet(ws)
        for t in all_tables:
            if t not in st.session_state.done_map:
                st.session_state.done_map[t] = 0


# ─── Styling helpers ──────────────────────────────────────────────────────────

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
    """Renders an HTML table for a list of rows with black text on table names."""
    if not subset:
        st.markdown("_No tables in this group._")
        return

    done_map = st.session_state.done_map
    rows_html = ""
    for (wave, table, ttype, deps, note, is_new) in subset:
        done   = done_map.get(table, 0) == 1
        row_bg = "#e8f8f2" if done else ("#fffbea" if is_new else "#ffffff")
        new_tag = (
            ' <span style="font-size:9px;font-weight:700;background:#FEF3C7;'
            'color:#B45309;padding:1px 5px;border-radius:4px;">NEW</span>'
            if is_new else ""
        )
        rows_html += f"""
        <tr style="background:{row_bg};">
          <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:12px;color:#1a1a1a;">{wave_badge(wave)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:12px;font-family:monospace;color:#1a1a1a;font-weight:500;">{"✅ " if done else ""}{table}{new_tag}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #eee;color:#1a1a1a;">{type_badge(ttype)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:11px;color:#1a1a1a;">{dep_html(deps)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:11px;color:#444;">{note}</td>
        </tr>"""

    st.markdown(f"""
    <div style="overflow-x:auto;border:1px solid #e0e0e0;border-radius:8px;margin-bottom:12px;">
    <table style="width:100%;border-collapse:collapse;font-size:12px;">
      <thead>
        <tr style="background:#f0f4f8;">
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#333;font-weight:700;border-bottom:2px solid #ddd;white-space:nowrap;">Wave</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#333;font-weight:700;border-bottom:2px solid #ddd;">Table Name</th>
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
    """Renders a multi-select to bulk mark tables done/undone."""
    table_names   = [r[1] for r in subset]
    done_map      = st.session_state.done_map
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
        st.toast(f"Saved changes ✓", icon="✅")
        st.rerun()


# ─── Per-module wave renderer ─────────────────────────────────────────────────

def render_module(rows: list, module_key: str, wave_filter: str):
    """Renders all waves for a given module (prod or crm)."""
    filtered = [r for r in rows if wave_match(r[0], r[5], wave_filter)]
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


def wave_match(wave: int, is_new: bool, wave_filter: str) -> bool:
    if wave_filter == "All waves":  return True
    if wave_filter == "W9–13":      return wave >= 9
    if wave_filter == "New only":   return is_new
    return wave == int(wave_filter[1:])


# ─── App layout ───────────────────────────────────────────────────────────────

def main():
    init_state()

    st.title("🗄️ SQL Export Order Tracker")
    st.caption("Dual-module (Production & CRM) dependency-ordered export plan · progress saved to Google Sheets")

    # ── Legend
    cols = st.columns(6)
    legends = [
        ("●", "Master",      "#185FA5"),
        ("●", "Transaction", "#3B6D11"),
        ("●", "Join / M:N",  "#854F0B"),
        ("●", "Security",    "#534AB7"),
        ("●", "Sync/staging","#5F5E5A"),
        ("●", "NEW",         "#B45309"),
    ]
    for col, (icon, label, color) in zip(cols, legends):
        col.markdown(
            f'<span style="font-size:12px;color:{color};">{icon} {label}</span>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Overall progress bar (across both modules)
    done_map    = st.session_state.done_map
    total       = len(ALL_ROWS)
    done_count  = sum(1 for r in ALL_ROWS if done_map.get(r[1], 0) == 1)
    prod_total  = len(PROD_ROWS)
    crm_total   = len(CRM_ROWS)
    prod_done   = sum(1 for r in PROD_ROWS if done_map.get(r[1], 0) == 1)
    crm_done    = sum(1 for r in CRM_ROWS  if done_map.get(r[1], 0) == 1)

    st.progress(
        done_count / total if total else 0,
        text=f"**Overall: {done_count} / {total}** exported ({done_count * 100 // total if total else 0}%)  ·  "
             f"🌾 Prod {prod_done}/{prod_total}  ·  🤝 CRM {crm_done}/{crm_total}",
    )

    st.divider()

    # ── Global controls (search + wave filter)
    col1, col2 = st.columns([3, 2])
    with col1:
        search = st.text_input(
            "🔍 Search table name",
            placeholder="e.g. employees — shows match + parents + dependents",
        )
    with col2:
        wave_options = ["All waves", "W1", "W2", "W3", "W4", "W5", "W6",
                        "W7", "W8", "W9–13", "New only"]
        wave_filter = st.selectbox("Filter by wave", wave_options)

    # ── Search mode: show across both modules with clear headings
    if search.strip():
        sv = search.strip().lower()

        def parse_deps(deps):
            if not deps or deps == "—":
                return []
            return [d.strip().lower() for d in deps.split("·")]

        for module_label, module_rows in [("🌾 Production", PROD_ROWS), ("🤝 CRM", CRM_ROWS)]:
            matched     = [r for r in module_rows if sv in r[1].lower()]
            matched_set = {r[1].lower() for r in matched}

            parent_names = set()
            for r in matched:
                for p in parse_deps(r[3]):
                    if p not in matched_set:
                        parent_names.add(p)

            child_names = set()
            for r in module_rows:
                tl = r[1].lower()
                if tl in matched_set:
                    continue
                if any(m in parse_deps(r[3]) for m in matched_set):
                    child_names.add(tl)

            parent_rows = [r for r in module_rows if r[1].lower() in parent_names]
            child_rows  = [r for r in module_rows if r[1].lower() in child_names]

            if not matched and not parent_rows and not child_rows:
                continue

            st.subheader(f"{module_label}")
            if matched:
                st.markdown(f"**🎯 Matched ({len(matched)})**")
                render_table(matched)
                done_controls(matched, f"{module_label}_match")
            if parent_rows:
                st.markdown(f"**⬆️ FK Parents — depends on ({len(parent_rows)})**")
                render_table(parent_rows)
            if child_rows:
                st.markdown(f"**⬇️ Dependents — tables that depend on this ({len(child_rows)})**")
                render_table(child_rows)

    else:
        # ── Tab view for Production vs CRM
        tab_prod, tab_crm = st.tabs(["🌾  Production Module", "🤝  CRM Module"])

        with tab_prod:
            st.markdown(
                "Tables prefixed **`_prod_`** — production geography, growers, "
                "organizers, monitoring, and related HR/expense records."
            )
            render_module(PROD_ROWS, "prod", wave_filter)

        with tab_crm:
            st.markdown(
                "Tables prefixed **`_crm_`** — CRM geography, farmers, distributors, "
                "field visits, PSA/PDA flows, sales budgets, and related HR/expense records."
            )
            render_module(CRM_ROWS, "crm", wave_filter)

    # ── Reset / danger zone
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
