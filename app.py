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

# ─── Data ────────────────────────────────────────────────────────────────────

ROWS = [
    (1,"mst_zones","master","—","Top-level geo. Export first.",False),
    (1,"mst_c_states","master","—","CRM state master",False),
    (1,"mst_crops","master","—","Crop master — used everywhere",False),
    (1,"mst_years","master","—","Season/financial year",False),
    (1,"mst_crm_years","master","—","CRM year / period",False),
    (1,"mst_departments","master","—","HR dept master",False),
    (1,"mst_employee_grades","master","—","Grade hierarchy",False),
    (1,"mst_employee_hq","master","—","Employee HQ locations",False),
    (1,"mst_designations","master","—","Employee titles",False),
    (1,"mst_activities","master","—","CRM activity type master",False),
    (1,"mst_product_skus","master","—","SKU master",False),
    (1,"mst_female_codes","master","—","Variety female codes",False),
    (1,"mst_male_codes","master","—","Variety male codes",False),
    (1,"mst_production_locations","master","—","Prod location master",False),
    (1,"mst_plants","master","—","Plant/processing sites",False),
    (1,"mst_crop_types","master","—","Crop type grouping",False),
    (1,"mst_dropdown_master","master","—","UI dropdown options",False),
    (1,"mst_city_master","master","—","Standalone city list",False),
    (1,"mst_mode_of_travel","master","—","Travel mode (car, train…)",False),
    (1,"mst_type_of_travel","master","—","Travel type (local, outstation…)",False),
    (1,"tr_attachments","master","—","File attachment store",False),
    (1,"tr_sessions","security","—","Login / session tokens",False),
    (1,"otps","security","—","OTP auth records",False),
    (1,"tr_notifications","security","—","Push notifications",False),
    (1,"tr_travel_reimbursements","transaction","—","Standalone reimbursement",False),
    (1,"mst_zone_dynamics","sync","—","Dynamics geo staging",False),
    (1,"mst_crops_dynamics","sync","—","Dynamics crop staging",False),
    (1,"mst_crop_response","sync","—","Sync response staging",False),
    (1,"mst_distributors_response","sync","—","Sync response staging",False),
    (1,"mst_zone_respone","sync","—","Sync response staging",False),
    (1,"mst_varietiessku_response","sync","—","Sync response staging",False),
    (1,"mst_seed_types","master","—","Seed type master",True),
    (1,"mst_seed_categories","master","—","Seed category master",True),
    (2,"mst_regions","master","mst_zones","Geo region under zone",False),
    (2,"mst_c_districts","master","mst_c_states","CRM district",False),
    (2,"mst_sub_departments","master","mst_departments","Sub-dept grouping",False),
    (2,"mst_terms","master","mst_years · mst_crops","Crop terms per year",False),
    (2,"tr_tada_workflows","transaction","mst_departments","TADA workflow rules",False),
    (2,"tr_working_hours","transaction","mst_departments","Working-hour policy",False),
    (2,"tr_travel_grade_rules","transaction","mst_departments","Claim caps by grade",False),
    (2,"tr_holiday","transaction","mst_c_states","State holiday calendar",False),
    (2,"tr_policy","transaction","mst_departments · tr_attachments","Policy document store",False),
    (2,"mst_seasons","master","mst_years","Season master (Kharif, Rabi, Zaid…)",True),
    (3,"mst_territories","master","mst_regions","Territory under region",False),
    (3,"mst_blocks","master","mst_regions","Production block",False),
    (3,"mst_c_blocks","master","mst_c_districts","CRM block",False),
    (3,"mst_roles","master","mst_departments · mst_sub_departments","Role / permissions master",False),
    (3,"mst_varieties","master","mst_crops · mst_female_codes · mst_male_codes · mst_product_skus · mst_seed_types · mst_seed_categories","Core variety master",False),
    (3,"mst_region_dynamics","sync","mst_zone_dynamics","Dynamics region staging",False),
    (3,"mst_mode_of_travel_mapping","master","mst_mode_of_travel · mst_type_of_travel","Travel mode mapping",False),
    (3,"zoneregion","join","mst_zones · mst_regions","Zone ↔ Region M:N",False),
    (4,"mst_districts","master","mst_territories · mst_c_states","Production district",False),
    (4,"mst_villages","master","mst_blocks","Production village",False),
    (4,"mst_c_villages","master","mst_c_blocks","CRM village",False),
    (4,"mst_banners","master","mst_regions · mst_territories","Scheme / banner master",False),
    (4,"mst_crop_analytics","master","mst_crops · mst_years · mst_varieties · mst_regions","Analytics baseline for targets",False),
    (4,"mst_focused_varieties","master","mst_regions · mst_zones · mst_varieties","Priority varieties for CRM",False),
    (4,"mst_territory_dynamics","sync","mst_region_dynamics","Dynamics territory staging",False),
    (4,"tr_employees","transaction","mst_departments · mst_sub_departments · mst_roles · mst_employee_grades · mst_employee_hq · mst_c_states · mst_designations · mst_crop_types","Central user/employee record",False),
    (4,"tr_role_permissions","security","mst_roles","Role permission matrix",False),
    (4,"tr_production_plans","transaction","mst_varieties · mst_years","Base production plan (non-PS)",False),
    (4,"tr_national_sales_budget","transaction","mst_varieties · mst_crm_years","National sales budget header",False),
    (4,"regionterritory","join","mst_regions · mst_territories","Region ↔ Territory M:N",False),
    (4,"blockvillages","join","mst_blocks · mst_villages","Block ↔ Village M:N",False),
    (5,"mst_mdo_hqs","master","mst_districts","MDO HQ locations",False),
    (5,"mst_city_category","master","mst_c_states · mst_c_districts · mst_c_blocks · mst_c_villages","City category tagging",False),
    (5,"mst_organizers","master","mst_zones · mst_regions · mst_production_locations · tr_employees","Organizer / field agents",False),
    (5,"tr_farmer","transaction","tr_employees · mst_districts · mst_c_blocks · mst_c_villages","CRM farmer master",False),
    (5,"tr_distributors","transaction","tr_employees · mst_districts · mst_c_states · mst_c_blocks · mst_c_districts","Distributor master",False),
    (5,"tr_retailers","transaction","tr_employees · mst_c_districts · mst_c_blocks","Retailer master",False),
    (5,"tr_tada_workflow_approvers","transaction","tr_tada_workflows · mst_employee_grades · mst_roles","Approver matrix per workflow",False),
    (5,"tr_attendance","transaction","tr_employees","Daily attendance",False),
    (5,"tr_user_permissions","security","tr_employees","User-level permission overrides",False),
    (5,"tr_crm_menu_permissions","security","mst_roles · tr_employees","CRM menu access control",False),
    (5,"tr_production_plan_ps","transaction","mst_varieties · mst_years · mst_crop_analytics","PS production plan",False),
    (5,"tr_prod_plan_hybrids","transaction","mst_varieties · mst_years · mst_crop_analytics","Hybrid forecast plan",False),
    (5,"tr_location_allotments","transaction","mst_varieties · mst_years","Location allotment header",False),
    (5,"tr_crm_sales_target_histories","transaction","mst_varieties · mst_years · tr_employees","CRM target change log",False),
    (5,"tr_remark_histories","transaction","mst_varieties · mst_years · tr_employees","Planning remarks audit",False),
    (5,"tr_sales_plan_histories","transaction","mst_varieties · mst_years · tr_employees","Sales plan change log",False),
    (5,"dist_crm_block","join","mst_districts · mst_c_blocks","Prod district ↔ CRM block",False),
    (5,"employeeblock","join","tr_employees · mst_blocks","Emp ↔ Block M:N",False),
    (5,"employeecrop","join","tr_employees · mst_crops","Emp ↔ Crop M:N",False),
    (5,"employeedistrict","join","tr_employees · mst_districts","Emp ↔ District M:N",False),
    (5,"employeeregion","join","tr_employees · mst_regions","Emp ↔ Region M:N",False),
    (5,"employeevariety","join","tr_employees · mst_varieties","Emp ↔ Variety M:N",False),
    (5,"employeevillage","join","tr_employees · mst_villages","Emp ↔ Village M:N",False),
    (5,"employeezone","join","tr_employees · mst_zones","Emp ↔ Zone M:N",False),
    (6,"mst_growers","master","mst_organizers · tr_employees · mst_zones · mst_regions · mst_blocks · mst_villages · mst_crops · mst_varieties","Grower registry — core production record",False),
    (6,"districtmdohq","join","mst_districts · mst_mdo_hqs","District ↔ MDO HQ M:N",False),
    (6,"mdohqblocks","join","mst_mdo_hqs · mst_blocks","MDO HQ ↔ Block M:N",False),
    (6,"employeemdohq","join","tr_employees · mst_mdo_hqs","Emp ↔ MDO HQ M:N",False),
    (6,"org_block","join","mst_organizers · mst_blocks","Organizer ↔ Block M:N",False),
    (6,"org_emp","join","mst_organizers · tr_employees","Organizer ↔ Employee M:N",False),
    (6,"tr_distributor_visits","transaction","tr_distributors · mst_c_blocks · tr_employees · mst_banners","Distributor visit records",False),
    (6,"tr_retailer_visits","transaction","tr_retailers · mst_c_blocks · tr_employees · mst_banners","Retailer visit records",False),
    (6,"tr_seasons","transaction","tr_employees · tr_retailers · mst_seasons","Seasonal retailer tags",False),
    (6,"tr_seasons_distributer","transaction","tr_employees · tr_distributors · mst_seasons","Seasonal distributor tags",False),
    (6,"tr_farmer_purchase_pattern","transaction","tr_farmer · mst_crm_years · mst_crops · mst_varieties · mst_product_skus","Farmer purchase behavior",False),
    (6,"tr_zone_sales_budget","transaction","mst_varieties · mst_crm_years · mst_zones · tr_national_sales_budget","Zone sales budget",False),
    (6,"tr_organizer_performances","transaction","mst_organizers · mst_varieties · mst_years · mst_seasons","Organizer scoring",False),
    (6,"tr_region_allotments","transaction","tr_location_allotments · mst_crop_analytics · mst_varieties · mst_regions","Region allotment breakdown",False),
    (6,"tr_distributors_dynamics","sync","tr_employees · mst_districts","Dynamics distributor mirror",False),
    (6,"tr_distributors_dynamics_new","sync","tr_employees · mst_districts","Dynamics distributor mirror v2",False),
    (6,"tr_distributor_dynamic_integration","sync","tr_employees · mst_districts","Distributor integration log",False),
    (7,"tr_organizer_selection","transaction","mst_varieties · mst_years · mst_seasons · mst_regions · mst_organizers · tr_organizer_performances","Organizer selection decisions",False),
    (7,"tr_grower_preparations","transaction","mst_varieties · mst_years · mst_seasons · mst_regions · mst_organizers · mst_growers","Sowing readiness tracking",False),
    (7,"tr_production_monitorings","transaction","mst_varieties · mst_years · mst_seasons · mst_regions · mst_growers · tr_employees","Crop lifecycle monitoring",False),
    (7,"tr_monitoring_crop_status","transaction","mst_varieties · mst_years · mst_seasons · mst_regions · mst_growers · tr_employees","Crop status snapshot",False),
    (7,"tr_monitoring_crop_status_history","transaction","mst_varieties · mst_years · mst_seasons · mst_regions · mst_growers · tr_employees","Crop status audit trail",False),
    (7,"tr_physical_purity_reports","transaction","mst_varieties · mst_years · mst_seasons · mst_regions · mst_plants · mst_organizers","Quality/purity reports",False),
    (7,"tr_prod_summary_reports","transaction","mst_varieties · mst_years · mst_seasons · mst_regions · mst_organizers","Production summary header",False),
    (7,"tr_daily_visits","transaction","mst_varieties · mst_years · mst_seasons · mst_regions · tr_employees · mst_growers","Daily field visit log",False),
    (7,"tr_region_sales_budget","transaction","mst_varieties · mst_crm_years · mst_regions · tr_zone_sales_budget","Region sales budget",False),
    (7,"tr_activity_planning","transaction","mst_crm_years · mst_zones · mst_regions · mst_territories · tr_employees · mst_focused_varieties","CRM FC activity plan",False),
    (7,"tr_activity_planning_veg","transaction","mst_crm_years · mst_zones · mst_regions · mst_territories · tr_employees · mst_focused_varieties","CRM Veg activity plan",False),
    (7,"tr_loc_altmt_histories","transaction","tr_location_allotments · tr_employees","Allotment change log",False),
    (8,"tr_prod_summary_reports_weekly","transaction","tr_prod_summary_reports · mst_varieties · mst_years · mst_seasons · mst_regions · mst_organizers","Weekly production breakdown",False),
    (8,"tr_monitoring_sample_checks","transaction","tr_production_monitorings","Sample check child records",False),
    (8,"tr_territory_sales_budget","transaction","mst_varieties · mst_crm_years · mst_territories · tr_region_sales_budget","Territory sales budget",False),
    (8,"tr_territory_sales_budget_veg","transaction","mst_varieties · mst_crm_years · mst_territories","Territory Veg sales budget",False),
    (8,"tr_region_sales_budget_veg","transaction","mst_varieties · mst_crm_years · mst_regions","Region Veg sales budget",False),
    (8,"tr_activity_approval_history","transaction","mst_crm_years · mst_zones · mst_regions · mst_territories · tr_employees","Activity approval log",False),
    (8,"tr_activity_plan_change_history","transaction","mst_crm_years · mst_zones · mst_regions · mst_territories · tr_employees · mst_focused_varieties","Activity plan change log",False),
    (8,"tr_field_visits","transaction","tr_employees · tr_farmer · mst_varieties · mst_activities · mst_districts · mst_c_blocks · mst_c_villages","Core CRM field visit — PDA/PSA starts here",False),
    (9,"tr_fieldvisit_remarks","transaction","tr_field_visits · tr_employees","Manager remarks on visits",False),
    (9,"tr_pda_psa_approval_history","transaction","tr_field_visits · tr_employees","PDA/PSA approval log",False),
    (9,"tr_dgactivity","transaction","tr_employees · tr_field_visits · tr_farmer · mst_c_villages · mst_activities · mst_varieties · mst_crops · mst_c_blocks","DG activity execution (PDA)",False),
    (9,"tr_psa_approval","transaction","mst_activities · mst_varieties · mst_c_villages · tr_employees","PSA approval header",False),
    (10,"tr_dgactivity_remarks","transaction","tr_employees · tr_dgactivity","DG activity review remarks",False),
    (10,"tr_psa_approval_history","transaction","tr_psa_approval · tr_employees","PSA approval action log",False),
    (10,"tr_psa_dgactivity","transaction","tr_psa_approval · tr_employees · mst_c_villages · mst_activities · mst_varieties · mst_crops","Activity records under PSA",False),
    (11,"tr_psa_dgactivity_remarks","transaction","tr_employees · tr_psa_dgactivity","PSA DG remark log",False),
    (11,"tr_expenses","transaction","tr_employees · tr_attachments · tr_dgactivity · tr_psa_dgactivity","Expense claim header",False),
    (12,"tr_expense_line_items","transaction","tr_expenses · tr_attachments","Itemised expense lines",False),
    (12,"tr_approvals","transaction","tr_expenses · tr_employees","Current approval chain",False),
    (12,"tr_expense_approval_history","transaction","tr_expenses · tr_employees","Immutable approval log",False),
    (13,"tr_expense_approval_changes","transaction","tr_expenses · tr_expense_approval_history","Fine-grained change log for approvals",False),
    (13,"tr_dynamics_geo_sync_runs","sync","—","Geo sync run monitor",False),
    (13,"tr_dynamics_geo_sync_errors","sync","—","Geo sync error log",False),
    (13,"tr_dynamics_prod_sync_runs","sync","—","Prod sync run monitor",False),
    (13,"tr_dynamics_prod_sync_errors","sync","—","Prod sync error log",False),
    (13,"tr_dynamics_planting_logs","sync","—","Planting payload audit",False),
    (13,"tr_dynamics_seed_distribution_logs","sync","—","Seed dist payload audit",False),
    (13,"tr_dynamics_purity_report_logs","sync","—","Purity report payload audit",False),
    (13,"policy_departments","join","tr_policy · mst_departments","Policy ↔ Dept M:N",False),
]

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


def load_done_from_sheet(ws) -> dict[str, int]:
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


def bulk_init_sheet(ws, all_tables: list[str]):
    """Writes all table names with done=0 if sheet is empty."""
    existing = ws.col_values(1)
    if not existing or existing == ["table_name"]:
        # Fresh sheet: write header + all rows
        data = [["table_name", "done"]] + [[t, 0] for t in all_tables]
        ws.clear()
        ws.update("A1", data)

# ─── Session state bootstrap ──────────────────────────────────────────────────

def init_state():
    if "done_map" not in st.session_state:
        ws = get_sheet()
        all_tables = [r[1] for r in ROWS]
        bulk_init_sheet(ws, all_tables)
        st.session_state.done_map = load_done_from_sheet(ws)
        # fill any missing
        for t in all_tables:
            if t not in st.session_state.done_map:
                st.session_state.done_map[t] = 0


# ─── Styling helpers ──────────────────────────────────────────────────────────

def wave_badge(wave: int) -> str:
    color = WAVE_COLORS[(wave - 1) % len(WAVE_COLORS)]
    return f'<span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:{color}22;color:{color};font-weight:600;font-size:11px;">{wave}</span>'


def type_badge(t: str) -> str:
    c = TYPE_COLORS.get(t, "#888")
    return f'<span style="display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:500;background:{c}22;color:{c};">{t}</span>'


def dep_html(deps: str) -> str:
    if deps == "—":
        return '<span style="color:#aaa;font-size:11px;">—</span>'
    parts = [d.strip() for d in deps.split("·")]
    spans = " · ".join(
        f'<code style="font-size:10px;background:#f0f0f0;padding:1px 4px;border-radius:3px;">{p}</code>'
        for p in parts
    )
    return spans


def render_table(subset: list, section_color: str = None):
    """Renders an HTML table for a list of rows."""
    if not subset:
        st.markdown("_No tables in this group._")
        return

    done_map = st.session_state.done_map

    header_bg = "#f8f9fa"
    rows_html = ""
    for (wave, table, ttype, deps, note, is_new) in subset:
        done = done_map.get(table, 0) == 1
        row_bg = "#e8f8f2" if done else ("#fffbea" if is_new else "white")
        new_tag = ' <span style="font-size:9px;font-weight:700;background:#FEF3C7;color:#B45309;padding:1px 5px;border-radius:4px;">NEW</span>' if is_new else ""
        rows_html += f"""
        <tr style="background:{row_bg};">
          <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:12px;font-family:monospace;">{wave_badge(wave)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:12px;font-family:monospace;">{"✅ " if done else ""}{table}{new_tag}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #eee;">{type_badge(ttype)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:11px;">{dep_html(deps)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:11px;color:#555;">{note}</td>
        </tr>"""

    st.markdown(f"""
    <div style="overflow-x:auto;border:1px solid #e0e0e0;border-radius:8px;margin-bottom:12px;">
    <table style="width:100%;border-collapse:collapse;font-size:12px;">
      <thead>
        <tr style="background:{header_bg};">
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#666;font-weight:600;border-bottom:1px solid #ddd;white-space:nowrap;">Wave</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#666;font-weight:600;border-bottom:1px solid #ddd;">Table Name</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#666;font-weight:600;border-bottom:1px solid #ddd;">Type</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#666;font-weight:600;border-bottom:1px solid #ddd;">Depends On (FK Parents)</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#666;font-weight:600;border-bottom:1px solid #ddd;">Purpose / Note</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
    """, unsafe_allow_html=True)


# ─── Mark-done controls ───────────────────────────────────────────────────────

def done_controls(subset: list, key_prefix: str):
    """Renders a multi-select to mark tables done/undone in bulk."""
    table_names = [r[1] for r in subset]
    done_map = st.session_state.done_map
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
        changed = []
        for t in table_names:
            new_val = 1 if t in selected else 0
            if done_map.get(t, 0) != new_val:
                done_map[t] = new_val
                save_done_to_sheet(ws, t, new_val)
                changed.append(t)
        if changed:
            st.toast(f"Saved {len(changed)} change(s) to Google Sheets ✓", icon="✅")
            st.rerun()


# ─── App layout ───────────────────────────────────────────────────────────────

def main():
    init_state()

    st.title("🗄️ SQL Export Order Tracker")
    st.caption("13-wave dependency-ordered export plan · progress saved to Google Sheets")

    # ── Legend
    cols = st.columns(6)
    legends = [
        ("🔵","Master","#185FA5"),("🟢","Transaction","#3B6D11"),
        ("🟠","Join / M:N","#854F0B"),("🟣","Security","#534AB7"),
        ("⚫","Sync / staging","#5F5E5A"),("🟡","NEW","#B45309"),
    ]
    for col, (icon, label, color) in zip(cols, legends):
        col.markdown(f'<span style="font-size:12px;color:{color};">● {label}</span>', unsafe_allow_html=True)

    st.divider()

    # ── Progress bar
    done_map = st.session_state.done_map
    total = len(ROWS)
    done_count = sum(1 for r in ROWS if done_map.get(r[1], 0) == 1)
    st.progress(done_count / total, text=f"**{done_count} / {total}** tables exported ({done_count*100//total}%)")

    st.divider()

    # ── Controls
    col1, col2 = st.columns([3, 2])
    with col1:
        search = st.text_input(
            "🔍 Search table name",
            placeholder="e.g. tr_employees — shows match + parents + dependents",
        )
    with col2:
        wave_options = ["All waves", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9–13", "New only"]
        wave_filter = st.selectbox("Filter by wave", wave_options)

    # ── Filter logic
    def wave_match(wave, is_new):
        if wave_filter == "All waves":       return True
        if wave_filter == "W9–13":           return wave >= 9
        if wave_filter == "New only":        return is_new
        return wave == int(wave_filter[1:])

    if search.strip():
        sv = search.strip().lower()
        matched     = [r for r in ROWS if sv in r[1].lower()]
        matched_set = {r[1].lower() for r in matched}

        def parse_deps(deps):
            if not deps or deps == "—": return []
            return [d.strip().lower() for d in deps.split("·")]

        parent_names = set()
        for r in matched:
            for p in parse_deps(r[3]):
                if p not in matched_set:
                    parent_names.add(p)

        child_names = set()
        for r in ROWS:
            tl = r[1].lower()
            if tl in matched_set: continue
            if any(m in parse_deps(r[3]) for m in matched_set):
                child_names.add(tl)

        parent_rows = [r for r in ROWS if r[1].lower() in parent_names]
        child_rows  = [r for r in ROWS if r[1].lower() in child_names]

        st.subheader(f"🎯 Matched tables ({len(matched)})")
        render_table(matched)
        done_controls(matched, "match")

        st.subheader(f"⬆️ FK Parents — this table depends on ({len(parent_rows)})")
        render_table(parent_rows)

        st.subheader(f"⬇️ Dependents — tables that depend on this ({len(child_rows)})")
        render_table(child_rows)

    else:
        filtered = [r for r in ROWS if wave_match(r[0], r[5])]
        st.caption(f"Showing **{len(filtered)}** of **{total}** tables")

        if wave_filter == "All waves":
            for wave_num in range(1, 14):
                wave_rows = [r for r in filtered if r[0] == wave_num]
                if not wave_rows: continue
                wc = WAVE_COLORS[(wave_num - 1) % len(WAVE_COLORS)]
                wave_done = sum(1 for r in wave_rows if done_map.get(r[1], 0) == 1)
                with st.expander(
                    f"**Wave {wave_num}** — {len(wave_rows)} tables  ·  {wave_done}/{len(wave_rows)} done",
                    expanded=(wave_num <= 3),
                ):
                    render_table(wave_rows)
                    done_controls(wave_rows, f"w{wave_num}")
        else:
            render_table(filtered)
            done_controls(filtered, f"filtered_{wave_filter}")

    # ── Reset button
    st.divider()
    with st.expander("⚠️ Danger zone"):
        if st.button("Reset ALL progress to zero", type="secondary"):
            ws = get_sheet()
            all_tables = [r[1] for r in ROWS]
            for t in all_tables:
                st.session_state.done_map[t] = 0
            # Bulk update sheet
            data = [["table_name", "done"]] + [[t, 0] for t in all_tables]
            ws.clear()
            ws.update("A1", data)
            st.success("All progress reset.")
            st.rerun()


if __name__ == "__main__":
    main()
