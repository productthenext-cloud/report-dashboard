# ==================== RENDER CONFIGURATION ====================
import os
import sys
import tempfile
from pathlib import Path

# Configure for Render's read-only filesystem
if os.environ.get('RENDER', False):
    TEMP_DIR = Path(tempfile.gettempdir()) / 'telecaller_dashboard'
    TEMP_DIR.mkdir(exist_ok=True, parents=True)
    os.environ['DATA_DIR'] = str(TEMP_DIR)
    os.environ['TZ'] = 'Asia/Kathmandu'
    sys.path.insert(0, str(Path.cwd()))
# ==================== END RENDER CONFIG ====================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import hashlib
import json

# Import local modules
from data_processor import DataProcessor
from auth_manager import AuthManager

# Page configuration
st.set_page_config(
    page_title="Telecaller Daily Report Dashboard",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
def init_session_state():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.user_role = None
        st.session_state.user_name = None
        st.session_state.telecaller_name = None
        st.session_state.user_permissions = {}
        st.session_state.edit_mode = False
        st.session_state.editing_report = None
        st.session_state.editing_report_date = None
        st.session_state.managing_user = None
        st.session_state.selected_range = "today"

init_session_state()

# Initialize data processor and auth manager
@st.cache_resource
def init_processor():
    return DataProcessor()

@st.cache_resource
def init_auth_manager(_processor):
    return AuthManager(_processor)

processor = init_processor()
auth_manager = init_auth_manager(processor)

# Helper function to get day name from date
def get_day_from_date(date_value):
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[date_value.weekday()]

# Permission check functions
def can_edit_report(report_telecaller):
    if st.session_state.user_role == 'admin':
        return True
    elif st.session_state.user_permissions.get('can_edit_all', False):
        return True
    elif st.session_state.user_permissions.get('can_edit_own', False):
        return report_telecaller == st.session_state.telecaller_name
    return False

def can_delete_report(report_telecaller):
    if st.session_state.user_role == 'admin':
        return True
    return st.session_state.user_permissions.get('can_delete_all', False)

def can_view_all_reports():
    if st.session_state.user_role == 'admin':
        return True
    return st.session_state.user_permissions.get('can_view_all', False)

def can_manage_users():
    if st.session_state.user_role == 'admin':
        return True
    return st.session_state.user_permissions.get('can_manage_users', False)

def can_export_data():
    if st.session_state.user_role == 'admin':
        return True
    return st.session_state.user_permissions.get('can_export_data', False)

# Logout function
def logout():
    for key in ['authenticated', 'user', 'user_role', 'user_name', 'telecaller_name', 
                'user_permissions', 'edit_mode', 'editing_report', 'editing_report_date']:
        st.session_state[key] = None if key != 'authenticated' else False
    st.rerun()

# Custom CSS
def load_css():
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            color: #1976D2;
            font-weight: bold;
            margin-bottom: 1rem;
        }
        
        .stat-card {
            background-color: white;
            padding: 1.5rem;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
            border-left: 5px solid #1976D2;
        }
        
        .stat-number {
            font-size: 2rem;
            font-weight: bold;
            color: #1976D2;
        }
        
        .stat-label {
            font-size: 0.9rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .video-day {
            border-left-color: #F44336 !important;
        }
        
        .video-day .stat-number {
            color: #F44336;
        }
        
        .success-card {
            border-left-color: #4CAF50 !important;
        }
        
        .success-card .stat-number {
            color: #4CAF50;
        }
        
        .warning-card {
            border-left-color: #FF9800 !important;
        }
        
        .warning-card .stat-number {
            color: #FF9800;
        }
        
        .badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 600;
        }
        
        .badge-primary {
            background-color: #e3f2fd;
            color: #1976D2;
        }
        
        .badge-success {
            background-color: #e8f5e9;
            color: #4CAF50;
        }
        
        .badge-warning {
            background-color: #fff3cd;
            color: #856404;
        }
        
        .badge-danger {
            background-color: #f8d7da;
            color: #721c24;
        }
        
        .badge-admin {
            background-color: #9c27b0;
            color: white;
        }
        
        .badge-telecaller {
            background-color: #2196f3;
            color: white;
        }
        
        .day-display {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 0.375rem;
            padding: 0.5rem 0.75rem;
            color: #495057;
            font-weight: 500;
        }
        
        .role-badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-left: 0.5rem;
        }
        
        .user-card {
            background-color: white;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            border-left: 4px solid #1976D2;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .stButton button {
            width: 100%;
        }
        
        div[data-testid="stDataFrame"] {
            width: 100%;
        }
    </style>
    """, unsafe_allow_html=True)

# Login page
def login_page():
    st.markdown('<h1 class="main-header">📞 Telecaller Dashboard Login</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🔐 Login")
        
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Login", use_container_width=True, type="primary"):
                success, user_data = auth_manager.authenticate(username, password)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.user = username
                    st.session_state.user_role = user_data['role']
                    st.session_state.user_name = user_data['name']
                    st.session_state.telecaller_name = user_data.get('telecaller_name')
                    st.session_state.user_permissions = user_data.get('permissions', {})
                    st.success(f"Welcome, {user_data['name']}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        
        with col2:
            if st.button("Clear", use_container_width=True):
                st.rerun()
        
        st.markdown("---")
        with st.expander("🔐 Demo Credentials (Click to expand)"):
            st.markdown("""
            **Available Demo Accounts:**
            | Role | Username | Password |
            |------|----------|----------|
            | Admin | `admin` | `admin123` |
            | Prakriti | `prakriti` | `prakriti123` |
            | Raphiya | `raphiya` | `raphiya123` |
            | Sudikshya | `sudikshya` | `sudikshya123` |
            | Shiru | `shiru` | `shiru123` |
            """)

# Dashboard page
def dashboard_page():
    st.markdown('<h1 class="main-header">📊 Telecaller Performance Dashboard</h1>', unsafe_allow_html=True)
    
    # Date Range Selector
    col1, col2, col3, col4, col5 = st.columns(5)
    date_ranges = {
        "Today": "today",
        "Yesterday": "yesterday",
        "This Week": "week",
        "This Month": "month",
        "All Time": "all"
    }
    
    for i, (label, value) in enumerate(date_ranges.items()):
        button_type = "primary" if st.session_state.selected_range == value else "secondary"
        if i == 0 and col1.button(label, key=f"range_{value}", type=button_type):
            st.session_state.selected_range = value
            st.rerun()
        elif i == 1 and col2.button(label, key=f"range_{value}", type=button_type):
            st.session_state.selected_range = value
            st.rerun()
        elif i == 2 and col3.button(label, key=f"range_{value}", type=button_type):
            st.session_state.selected_range = value
            st.rerun()
        elif i == 3 and col4.button(label, key=f"range_{value}", type=button_type):
            st.session_state.selected_range = value
            st.rerun()
        elif i == 4 and col5.button(label, key=f"range_{value}", type=button_type):
            st.session_state.selected_range = value
            st.rerun()
    
    # Get dashboard stats
    if st.session_state.user_role == 'admin' or can_view_all_reports():
        stats = processor.get_dashboard_stats(st.session_state.selected_range)
    else:
        stats = processor.get_dashboard_stats(st.session_state.selected_range, 
                                             telecaller=st.session_state.telecaller_name)
    
    # Stats Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{stats.get('total_calls', 0):,}</div>
            <div class="stat-label">Total Calls</div>
            <div style="font-size: 0.8rem; color: #666;">Avg: {stats.get('avg_calls_per_day', 0)}/day</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-card success-card">
            <div class="stat-number">{stats.get('new_data', 0):,}</div>
            <div class="stat-label">New Data</div>
            <div style="font-size: 0.8rem; color: #666;">Avg: {stats.get('avg_new_data_per_day', 0)}/day</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card warning-card">
            <div class="stat-number">{stats.get('crm_data', 0):,}</div>
            <div class="stat-label">CRM Updates</div>
            <div style="font-size: 0.8rem; color: #666;">{stats.get('crm_completion_rate', 0)}% of calls</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="stat-card video-day">
            <div class="stat-number">{stats.get('video_activities', 0)}</div>
            <div class="stat-label">Video Activities</div>
            <div style="font-size: 0.8rem; color: #666;">{stats.get('video_activities', 0)} days</div>
        </div>
        """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        country_count = stats.get('country_data_count', 0)
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{country_count}</div>
            <div class="stat-label">Country Data</div>
            <div style="font-size: 0.8rem; color: #666;">International leads</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{stats.get('fair_data', 0):,}</div>
            <div class="stat-label">Fair Leads</div>
            <div style="font-size: 0.8rem; color: #666;">Event leads</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{stats.get('visited_students', 0):,}</div>
            <div class="stat-label">Visited Students</div>
            <div style="font-size: 0.8rem; color: #666;">Student visits</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        conversion_rate = stats.get('conversion_rate', 0)
        st.markdown(f"""
        <div class="stat-card success-card">
            <div class="stat-number">{conversion_rate:.1f}%</div>
            <div class="stat-label">Conversion Rate</div>
            <div style="font-size: 0.8rem; color: #666;">New Data / Total Calls</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Charts
    st.markdown("---")
    st.markdown("### 📈 Performance Charts")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.session_state.user_role == 'admin' or can_view_all_reports():
            weekly_data = processor.get_weekly_summary()
        else:
            weekly_data = processor.get_weekly_summary(telecaller=st.session_state.telecaller_name)
        
        if weekly_data and len(weekly_data) > 0:
            df_weekly = pd.DataFrame(weekly_data)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_weekly['date'],
                y=df_weekly['total_calls'],
                name='Total Calls',
                marker_color='#1976D2'
            ))
            fig.add_trace(go.Bar(
                x=df_weekly['date'],
                y=df_weekly['new_data'],
                name='New Data',
                marker_color='#4CAF50'
            ))
            fig.update_layout(
                title='Last 7 Days Performance',
                barmode='group',
                height=400,
                showlegend=True,
                xaxis_title='Date',
                yaxis_title='Count'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No weekly data available. Add reports to see charts.")
    
    with col2:
        if st.session_state.user_role == 'admin' or can_view_all_reports():
            trend_data = processor.get_performance_trend(30)
        else:
            trend_data = processor.get_performance_trend(30, telecaller=st.session_state.telecaller_name)
        
        if trend_data and len(trend_data) > 0:
            df_trend = pd.DataFrame(trend_data)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_trend['date'],
                y=df_trend['total_calls'],
                name='Total Calls',
                line=dict(color='#1976D2', width=3),
                mode='lines+markers'
            ))
            fig.add_trace(go.Scatter(
                x=df_trend['date'],
                y=df_trend['new_data'],
                name='New Data',
                line=dict(color='#4CAF50', width=3),
                mode='lines+markers'
            ))
            fig.update_layout(
                title='30-Day Performance Trend',
                height=400,
                showlegend=True,
                xaxis_title='Date',
                yaxis_title='Count'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data available. Add reports to see charts.")
    
    # Telecaller Performance
    if st.session_state.user_role == 'admin' or can_view_all_reports():
        st.markdown("---")
        st.markdown("### 👥 All Telecallers Performance")
        
        try:
            telecaller_stats = processor.get_telecaller_performance()
            if telecaller_stats is not None and not telecaller_stats.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    fig = px.bar(telecaller_stats,
                                x='Telecaller',
                                y='Total Calls',
                                title='Total Calls by Telecaller',
                                color='Total Calls',
                                color_continuous_scale='Viridis')
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = px.bar(telecaller_stats,
                                x='Telecaller',
                                y='New Data',
                                title='New Data Collected by Telecaller',
                                color='New Data',
                                color_continuous_scale='Greens')
                    st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("#### Performance Summary")
                st.dataframe(telecaller_stats, use_container_width=True, hide_index=True)
            else:
                st.info("No telecaller data available. Add reports to see statistics.")
        except Exception as e:
            st.info("Telecaller performance data will be available after adding reports.")

# Daily Reports page
def daily_reports_page():
    st.markdown(f'<h1 class="main-header">📋 Daily Reports</h1>', unsafe_allow_html=True)
    
    # Search and Filters
    with st.expander("🔍 Search & Filters", expanded=True):
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            start_date = st.date_input("Start Date", 
                                      value=datetime.now() - timedelta(days=30),
                                      key="reports_start_date")
        
        with col2:
            end_date = st.date_input("End Date", 
                                    value=datetime.now(),
                                    key="reports_end_date")
        
        with col3:
            if st.session_state.user_role == 'admin' or can_view_all_reports():
                all_reports = processor.get_all_reports()
                if not all_reports.empty and 'Telecaller' in all_reports.columns:
                    telecallers = ['All'] + sorted(all_reports['Telecaller'].unique().tolist())
                else:
                    telecallers = ['All']
                telecaller_filter = st.selectbox("Telecaller", telecallers, index=0, key="telecaller_filter")
            else:
                telecaller_filter = st.session_state.telecaller_name
                st.text_input("Telecaller", value=telecaller_filter, disabled=True)
        
        with col4:
            video_filter = st.selectbox("Video", ["All", "Yes", "No"], index=0, key="video_filter")
        
        with col5:
            search_term = st.text_input("Search", placeholder="Search...", key="search_filter")
    
    # Apply filters
    filters = {}
    if start_date:
        filters['start_date'] = start_date
    if end_date:
        filters['end_date'] = end_date
    if video_filter != "All":
        filters['video'] = video_filter
    if search_term:
        filters['search'] = search_term
    
    if st.session_state.user_role == 'admin' or can_view_all_reports():
        if telecaller_filter != "All":
            filters['telecaller'] = telecaller_filter
    else:
        filters['telecaller'] = st.session_state.telecaller_name
    
    # Get reports
    reports = processor.get_all_reports(filters)
    
    st.markdown(f"**Found {len(reports)} reports**")
    
    # Export button
    if can_export_data() and not reports.empty:
        csv = reports.to_csv(index=False)
        st.download_button(
            label="📥 Export to CSV",
            data=csv,
            file_name=f"telecaller_reports_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    # Display reports
    if not reports.empty:
        reports_display = reports.copy()
        reports_display['Date'] = pd.to_datetime(reports_display['Date']).dt.strftime('%Y-%m-%d')
        
        # Reorder columns for better display
        column_order = ['Date', 'Telecaller', 'Day', 'Total Calls', 'New Data', 'CRM Data', 
                       'Country Data', 'Fair Data', 'Visited Students', 'Video', 'Video Details']
        available_columns = [col for col in column_order if col in reports_display.columns]
        
        st.dataframe(
            reports_display[available_columns],
            use_container_width=True,
            hide_index=True
        )
        
        # Report Actions
        st.markdown("### ✏️ Report Actions")
        
        # Determine editable reports
        if st.session_state.user_role == 'admin':
            editable_reports = reports_display
        else:
            editable_reports = reports_display[reports_display['Telecaller'] == st.session_state.telecaller_name]
        
        if not editable_reports.empty:
            # Create a list of options for the selectbox
            report_options = []
            report_indices = []
            
            for idx in editable_reports.index:
                date_val = editable_reports.loc[idx, 'Date']
                telecaller_val = editable_reports.loc[idx, 'Telecaller']
                calls_val = editable_reports.loc[idx, 'Total Calls']
                report_options.append(f"{date_val} - {telecaller_val} - {calls_val} calls")
                report_indices.append(idx)
            
            selected_idx = st.selectbox(
                "Select a report to edit/delete",
                options=range(len(report_options)),
                format_func=lambda x: report_options[x],
                key="report_select"
            )
            
            selected_report_index = report_indices[selected_idx]
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✏️ Edit Selected Report", use_container_width=True):
                    if can_edit_report(reports.loc[selected_report_index, 'Telecaller']):
                        st.session_state.editing_report = selected_report_index
                        st.session_state.edit_mode = True
                        st.session_state.editing_report_date = reports.loc[selected_report_index, 'Date']
                        st.rerun()
                    else:
                        st.error("You don't have permission to edit this report!")
            
            with col2:
                if st.button("🗑️ Delete Selected Report", use_container_width=True):
                    if can_delete_report(reports.loc[selected_report_index, 'Telecaller']):
                        # Log deletion
                        edit_log = {
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'user': st.session_state.user_name,
                            'username': st.session_state.user,
                            'role': st.session_state.user_role,
                            'action': 'DELETE',
                            'report_date': str(reports.loc[selected_report_index, 'Date']),
                            'telecaller': reports.loc[selected_report_index, 'Telecaller'],
                            'original_data': json.dumps(reports.loc[selected_report_index].to_dict(), default=str),
                            'new_data': ''
                        }
                        processor.log_edit_action(edit_log)
                        
                        # Delete report
                        success = processor.delete_report(selected_report_index)
                        if success:
                            st.success("Report deleted successfully!")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.error("You don't have permission to delete this report!")
        else:
            st.info("No reports available to edit.")
    else:
        st.info("No reports found. Add your first report from the 'Add Report' page.")

# My Reports page
def my_reports_page():
    st.markdown(f'<h1 class="main-header">📋 My Reports</h1>', unsafe_allow_html=True)
    
    filters = {'telecaller': st.session_state.telecaller_name}
    reports = processor.get_all_reports(filters)
    
    st.markdown(f"**Found {len(reports)} reports**")
    
    if not reports.empty:
        reports_display = reports.copy()
        reports_display['Date'] = pd.to_datetime(reports_display['Date']).dt.strftime('%Y-%m-%d')
        
        column_order = ['Date', 'Day', 'Total Calls', 'New Data', 'CRM Data', 
                       'Country Data', 'Fair Data', 'Visited Students', 'Video', 'Video Details']
        available_columns = [col for col in column_order if col in reports_display.columns]
        
        st.dataframe(
            reports_display[available_columns],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No reports found. Add your first report from the 'Add Report' page.")

# Add Report page
def add_report_page():
    st.markdown('<h1 class="main-header">➕ Add Daily Report</h1>', unsafe_allow_html=True)
    
    editing = st.session_state.get('edit_mode', False)
    
    if editing:
        st.info("✏️ You are editing an existing report")
        reports = processor.get_all_reports()
        
        # Find the report by date if index is not available
        if st.session_state.editing_report is not None:
            try:
                if isinstance(st.session_state.editing_report, int):
                    report_idx = st.session_state.editing_report
                    if report_idx < len(reports):
                        original_data = reports.iloc[report_idx]
                    else:
                        st.error("Report not found. Please select again.")
                        st.session_state.edit_mode = False
                        st.session_state.editing_report = None
                        st.rerun()
                else:
                    # Try to find by date
                    date_str = st.session_state.editing_report_date
                    matching_reports = reports[reports['Date'].dt.strftime('%Y-%m-%d') == date_str]
                    if not matching_reports.empty:
                        report_idx = matching_reports.index[0]
                        original_data = reports.loc[report_idx]
                        st.session_state.editing_report = report_idx
                    else:
                        st.error("Report not found. Please select again.")
                        st.session_state.edit_mode = False
                        st.session_state.editing_report = None
                        st.rerun()
            except Exception as e:
                st.error(f"Error loading report: {str(e)}")
                st.session_state.edit_mode = False
                st.session_state.editing_report = None
                st.rerun()
        else:
            st.error("No report selected for editing.")
            st.session_state.edit_mode = False
            st.rerun()
        
        # Set default values
        default_date = pd.to_datetime(original_data['Date']) if pd.notna(original_data['Date']) else datetime.now()
        default_telecaller = original_data.get('Telecaller', 'Select Telecaller')
        default_total_calls = int(original_data.get('Total Calls', 0))
        default_new_data = int(original_data.get('New Data', 0))
        default_crm_data = int(original_data.get('CRM Data', 0))
        default_country = original_data.get('Country Data', '')
        default_fair_data = int(original_data.get('Fair Data', 0))
        default_visited = int(original_data.get('Visited Students', 0))
        default_video = original_data.get('Video', 'No')
        default_video_details = original_data.get('Video Details', '')
        default_other_work = original_data.get('Other Work Description', '')
        default_remarks = original_data.get('Remarks', '')
    else:
        default_date = datetime.now()
        default_telecaller = st.session_state.telecaller_name if st.session_state.telecaller_name else 'Select Telecaller'
        default_total_calls = 0
        default_new_data = 0
        default_crm_data = 0
        default_country = ''
        default_fair_data = 0
        default_visited = 0
        default_video = 'No'
        default_video_details = ''
        default_other_work = ''
        default_remarks = ''
    
    # Create form
    with st.form("add_report_form"):
        st.markdown("### 📅 Basic Information")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            report_date = st.date_input("Date *", value=default_date, key="report_date")
        
        with col2:
            if editing and st.session_state.user_role != 'admin':
                telecaller = st.text_input("Telecaller *", value=default_telecaller, disabled=True)
            else:
                telecaller_options = ["Select Telecaller", "Prakriti", "Raphiya", "Sudikshya", "Shiru", "Other"]
                default_index = 0
                if default_telecaller != 'Select Telecaller' and default_telecaller in telecaller_options:
                    default_index = telecaller_options.index(default_telecaller)
                telecaller = st.selectbox("Telecaller *", telecaller_options, index=default_index)
        
        with col3:
            day_name = get_day_from_date(report_date)
            st.markdown("**Day**")
            st.markdown(f'<div class="day-display">{day_name}</div>', unsafe_allow_html=True)
            st.caption("Auto-calculated")
        
        st.markdown("### 📊 Call Statistics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_calls = st.number_input("Total Calls *", min_value=0, value=default_total_calls, step=1)
        
        with col2:
            new_data = st.number_input("New Data *", min_value=0, value=default_new_data, step=1)
        
        with col3:
            crm_data = st.number_input("CRM Data *", min_value=0, value=default_crm_data, step=1)
        
        st.markdown("### 📝 Additional Information")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            country_options = ["", "UK", "Australia", "Canada", "USA", "New Zealand", "Other"]
            default_country_index = 0
            if default_country in country_options:
                default_country_index = country_options.index(default_country)
            country_data = st.selectbox("Country Data", country_options, index=default_country_index)
        
        with col2:
            fair_data = st.number_input("Fair Data", min_value=0, value=default_fair_data, step=1)
        
        with col3:
            visited_students = st.number_input("Visited Students", min_value=0, value=default_visited, step=1)
        
        st.markdown("### 🎥 Video Activity")
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            video = st.selectbox("Video Activity *", ["No", "Yes"], 
                               index=0 if default_video == 'No' else 1)
        
        with col2:
            if video == "Yes":
                video_details = st.text_input("Video Details *", value=default_video_details,
                                            placeholder="e.g., TikTok video, training video...")
            else:
                video_details = ""
                st.text_input("Video Details", value="No video activity", disabled=True)
        
        st.markdown("### 📋 Other Information")
        
        other_work = st.text_area("Other Work Description", value=default_other_work,
                                placeholder="e.g., Trained volunteers, helped Asmita mam...",
                                height=100)
        
        remarks = st.text_area("Remarks / Notes", value=default_remarks,
                             placeholder="Any additional notes...",
                             height=100)
        
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            if editing:
                submitted = st.form_submit_button("✏️ Update Report", use_container_width=True, type="primary")
            else:
                submitted = st.form_submit_button("💾 Save Report", use_container_width=True, type="primary")
        
        if submitted:
            errors = []
            
            if telecaller == "Select Telecaller":
                errors.append("❌ Please select a telecaller!")
            if total_calls == 0:
                errors.append("❌ Total Calls cannot be zero!")
            if new_data == 0:
                errors.append("❌ New Data cannot be zero!")
            if crm_data == 0:
                errors.append("❌ CRM Data cannot be zero!")
            if video == "Yes" and not video_details.strip():
                errors.append("❌ Video Details is required when Video Activity is 'Yes'!")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                report_data = {
                    'date': report_date.strftime('%d/%m/%Y 00:00:01'),
                    'telecaller': telecaller,
                    'day': day_name,
                    'total_calls': total_calls,
                    'new_data': new_data,
                    'crm_data': crm_data,
                    'country_data': country_data,
                    'fair_data': fair_data,
                    'video': video,
                    'video_details': video_details if video == "Yes" else "",
                    'other_work': other_work,
                    'visited_students': visited_students,
                    'remarks': remarks
                }
                
                with st.spinner("Saving report..."):
                    try:
                        if editing:
                            # Log edit action
                            edit_log = {
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'user': st.session_state.user_name,
                                'username': st.session_state.user,
                                'role': st.session_state.user_role,
                                'action': 'EDIT',
                                'report_date': report_date.strftime('%Y-%m-%d'),
                                'telecaller': telecaller,
                                'original_data': json.dumps(st.session_state.get('original_report_data', {}), default=str),
                                'new_data': json.dumps(report_data, default=str)
                            }
                            processor.log_edit_action(edit_log)
                            
                            # Update report
                            success = processor.update_report(report_idx, report_data)
                            if success:
                                st.success("✅ Report updated successfully!")
                                st.session_state.edit_mode = False
                                st.session_state.editing_report = None
                                st.session_state.editing_report_date = None
                                st.session_state.original_report_data = None
                                time.sleep(1)
                                st.rerun()
                        else:
                            # Add new report
                            success = processor.add_report(report_data)
                            if success:
                                st.success("✅ Report added successfully!")
                                st.balloons()
                                time.sleep(1)
                                st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error saving report: {str(e)}")
    
    if editing:
        if st.button("❌ Cancel Editing"):
            st.session_state.edit_mode = False
            st.session_state.editing_report = None
            st.session_state.editing_report_date = None
            st.session_state.original_report_data = None
            st.rerun()

# Analysis page
def analysis_page():
    st.markdown('<h1 class="main-header">📈 Performance Analysis</h1>', unsafe_allow_html=True)
    
    # Analysis Period Selector
    col1, col2, col3 = st.columns(3)
    
    with col1:
        period = st.selectbox("Analysis Period", 
                             ["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"],
                             key="analysis_period")
    
    with col2:
        metric = st.selectbox("Primary Metric",
                             ["Total Calls", "New Data", "Conversion Rate", "Video Activities"],
                             key="analysis_metric")
    
    with col3:
        grouping = st.selectbox("Group By",
                               ["Daily", "Weekly", "Monthly"],
                               key="analysis_grouping")
    
    # Analysis Tabs
    if st.session_state.user_role == 'admin' or can_view_all_reports():
        tabs = ["Trend Analysis", "Telecaller Comparison", "Video Activities", "Country Distribution"]
    else:
        tabs = ["My Performance", "Video Activities", "Country Distribution"]
    
    tab_list = st.tabs(tabs)
    
    # Tab 1: Trend Analysis
    with tab_list[0]:
        if st.session_state.user_role == 'admin' or can_view_all_reports():
            st.markdown("### 📊 Overall Trend Analysis")
            days_map = {"Last 7 Days": 7, "Last 30 Days": 30, "Last 90 Days": 90, "All Time": 365}
            trend_data = processor.get_performance_trend(days_map.get(period, 30))
            title_prefix = "Overall"
        else:
            st.markdown(f"### 📊 {st.session_state.user_name}'s Performance")
            days_map = {"Last 7 Days": 7, "Last 30 Days": 30, "Last 90 Days": 90, "All Time": 365}
            trend_data = processor.get_performance_trend(days_map.get(period, 30), 
                                                        telecaller=st.session_state.telecaller_name)
            title_prefix = st.session_state.user_name
        
        if trend_data and len(trend_data) > 0:
            df_trend = pd.DataFrame(trend_data)
            
            # Ensure columns exist
            if 'total_calls' not in df_trend.columns:
                df_trend['total_calls'] = 0
            if 'new_data' not in df_trend.columns:
                df_trend['new_data'] = 0
            
            # Create chart
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig.add_trace(
                go.Scatter(x=df_trend['date'], y=df_trend['total_calls'], 
                          name="Total Calls", line=dict(color='#1976D2', width=3),
                          mode='lines+markers'),
                secondary_y=False,
            )
            
            fig.add_trace(
                go.Scatter(x=df_trend['date'], y=df_trend['new_data'], 
                          name="New Data", line=dict(color='#4CAF50', width=3),
                          mode='lines+markers'),
                secondary_y=True,
            )
            
            fig.update_layout(
                title=f"{title_prefix} Performance Trend - {period}",
                height=500,
                hovermode='x unified',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            fig.update_xaxes(title_text="Date")
            fig.update_yaxes(title_text="Total Calls", secondary_y=False)
            fig.update_yaxes(title_text="New Data", secondary_y=True)
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Summary statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Calls", f"{df_trend['total_calls'].sum():,}")
            with col2:
                st.metric("Total New Data", f"{df_trend['new_data'].sum():,}")
            with col3:
                conversion = (df_trend['new_data'].sum() / df_trend['total_calls'].sum() * 100) if df_trend['total_calls'].sum() > 0 else 0
                st.metric("Overall Conversion", f"{conversion:.1f}%")
            with col4:
                st.metric("Days with Data", len(df_trend))
        else:
            st.info("No trend data available. Add reports to see analysis.")
    
    # Tab 2: Telecaller Comparison
    if len(tabs) > 1 and (st.session_state.user_role == 'admin' or can_view_all_reports()):
        with tab_list[1]:
            st.markdown("### 👥 Telecaller Comparison")
            
            try:
                telecaller_stats = processor.get_telecaller_performance()
                if telecaller_stats is not None and not telecaller_stats.empty:
                    
                    comparison_metric = st.radio(
                        "Select Metric to Compare",
                        ["Total Calls", "New Data", "Conversion Rate", "Video Activities"],
                        horizontal=True,
                        key="comparison_metric"
                    )
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        if comparison_metric == "Conversion Rate":
                            if 'Conversion Rate' not in telecaller_stats.columns:
                                telecaller_stats['Conversion Rate'] = (
                                    telecaller_stats['New Data'] / telecaller_stats['Total Calls'] * 100
                                ).round(1)
                            fig = px.bar(telecaller_stats, 
                                       x='Telecaller', 
                                       y='Conversion Rate',
                                       title='Conversion Rate by Telecaller',
                                       color='Conversion Rate',
                                       color_continuous_scale='RdYlGn',
                                       text='Conversion Rate')
                            fig.update_traces(texttemplate='%{text}%', textposition='outside')
                        else:
                            fig = px.bar(telecaller_stats, 
                                       x='Telecaller', 
                                       y=comparison_metric,
                                       title=f'{comparison_metric} by Telecaller',
                                       color=comparison_metric,
                                       color_continuous_scale='Viridis')
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        st.markdown("### Summary")
                        for _, row in telecaller_stats.iterrows():
                            conversion = (row['New Data'] / row['Total Calls'] * 100) if row['Total Calls'] > 0 else 0
                            st.markdown(f"""
                            <div class="user-card">
                                <strong>{row['Telecaller']}</strong><br>
                                📞 Calls: {row['Total Calls']:,}<br>
                                📊 New Data: {row['New Data']:,}<br>
                                📈 Conversion: {conversion:.1f}%<br>
                                🎥 Videos: {row.get('Video Activities', 0)}
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.info("No telecaller data available. Add reports to see comparison.")
            except Exception as e:
                st.info("Telecaller comparison data will be available after adding reports.")
    
    # Tab 3/2: Video Activities
    video_tab_index = 2 if (st.session_state.user_role == 'admin' or can_view_all_reports()) else 1
    with tab_list[video_tab_index]:
        st.markdown("### 🎥 Video Activities")
        
        video_days = st.slider("Show last N days", min_value=7, max_value=90, value=30, key="video_days")
        
        if st.session_state.user_role == 'admin' or can_view_all_reports():
            video_activities = processor.get_video_activities(video_days)
        else:
            video_activities = processor.get_video_activities(video_days, telecaller=st.session_state.telecaller_name)
        
        if video_activities and len(video_activities) > 0:
            df_video = pd.DataFrame(video_activities)
            
            fig = px.bar(df_video, x='date', y='total_calls',
                        title=f"Video Activities - Last {video_days} Days",
                        color='new_data',
                        color_continuous_scale='Reds',
                        hover_data=['video_details', 'telecaller'],
                        labels={'date': 'Date', 'total_calls': 'Total Calls', 'new_data': 'New Data'})
            
            fig.update_layout(height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("#### Recent Video Activities")
            for i, activity in enumerate(video_activities[:10]):
                with st.expander(f"{activity['date']} - {activity.get('telecaller', 'Unknown')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**📹 Video Details:** {activity['video_details']}")
                        st.markdown(f"**📞 Total Calls:** {activity['total_calls']}")
                    with col2:
                        st.markdown(f"**📊 New Data:** {activity['new_data']}")
                        conversion = (activity['new_data'] / activity['total_calls'] * 100) if activity['total_calls'] > 0 else 0
                        st.markdown(f"**📈 Conversion:** {conversion:.1f}%")
        else:
            st.info("No video activities recorded in the selected period.")
    
    # Tab 4/3: Country Distribution
    country_tab_index = 3 if (st.session_state.user_role == 'admin' or can_view_all_reports()) else 2
    with tab_list[country_tab_index]:
        st.markdown("### 🌍 Country Distribution")
        
        if st.session_state.user_role == 'admin' or can_view_all_reports():
            country_dist = processor.get_country_distribution()
        else:
            country_dist = processor.get_country_distribution(telecaller=st.session_state.telecaller_name)
        
        if country_dist:
            # Filter out empty countries
            country_dist = {k: v for k, v in country_dist.items() if k and str(k).strip() and v > 0}
            
            if country_dist:
                df_country = pd.DataFrame(list(country_dist.items()), columns=['Country', 'Count'])
                df_country = df_country.sort_values('Count', ascending=False)
                
                col1, col2 = st.columns([3, 2])
                
                with col1:
                    fig = px.pie(df_country, 
                               values='Count', 
                               names='Country', 
                               hole=0.3,
                               title='International Leads Distribution')
                    fig.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.markdown("#### Country Summary")
                    total = df_country['Count'].sum()
                    for _, row in df_country.iterrows():
                        percentage = (row['Count'] / total * 100)
                        st.markdown(f"""
                        **{row['Country']}**: {row['Count']} ({percentage:.1f}%)
                        <div style="background-color: #f0f2f6; border-radius: 5px; margin-bottom: 10px;">
                            <div style="background-color: #1976D2; width: {percentage}%; height: 5px; border-radius: 5px;"></div>
                        </div>
                        """, unsafe_allow_html=True)
                
                st.markdown("#### Detailed Country Data")
                st.dataframe(df_country, use_container_width=True, hide_index=True)
            else:
                st.info("No country data available.")
        else:
            st.info("No country data available.")

# Edit History page
def edit_history_page():
    st.markdown('<h1 class="main-header">📝 Edit History</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        history_days = st.number_input("Show last N days", min_value=1, max_value=365, value=30, key="history_days")
    
    with col2:
        action_filter = st.selectbox("Action Type", ["All", "EDIT", "DELETE", "ADD"], key="action_filter")
    
    with col3:
        user_filter = st.text_input("Filter by User", placeholder="Enter username", key="user_filter")
    
    edit_logs = processor.get_edit_logs()
    
    if edit_logs is not None and not edit_logs.empty:
        filtered_logs = edit_logs.copy()
        
        if 'timestamp' in filtered_logs.columns:
            filtered_logs['timestamp'] = pd.to_datetime(filtered_logs['timestamp'], errors='coerce')
            cutoff_date = datetime.now() - timedelta(days=history_days)
            filtered_logs = filtered_logs[filtered_logs['timestamp'] >= cutoff_date]
        
        if action_filter != "All" and 'action' in filtered_logs.columns:
            filtered_logs = filtered_logs[filtered_logs['action'] == action_filter]
        
        if user_filter and 'user' in filtered_logs.columns:
            filtered_logs = filtered_logs[filtered_logs['user'].str.contains(user_filter, case=False, na=False)]
        
        st.markdown(f"**Total Edit Actions: {len(filtered_logs)}**")
        
        if not filtered_logs.empty:
            display_cols = ['timestamp', 'user', 'action', 'report_date', 'telecaller']
            display_cols = [col for col in display_cols if col in filtered_logs.columns]
            
            st.dataframe(filtered_logs[display_cols], use_container_width=True, hide_index=True)
            
            if can_export_data():
                csv = filtered_logs.to_csv(index=False)
                st.download_button(
                    label="📥 Export Edit History",
                    data=csv,
                    file_name=f"edit_history_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No edit history matches your filters.")
    else:
        st.info("No edit history available.")

# User Management page
def user_management_page():
    st.markdown('<h1 class="main-header">👥 User Management</h1>', unsafe_allow_html=True)
    
    user_tabs = st.tabs(["View Users", "Add User", "Manage Permissions"])
    
    with user_tabs[0]:
        users = auth_manager.get_all_users()
        st.markdown("### Current Users")
        
        for username, user_info in users.items():
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                
                with col1:
                    st.markdown(f"**{user_info['name']}**")
                    st.caption(f"@{username}")
                
                with col2:
                    role_color = "badge-admin" if user_info['role'] == 'admin' else "badge-telecaller"
                    st.markdown(f'<span class="role-badge {role_color}">{user_info["role"].upper()}</span>', 
                               unsafe_allow_html=True)
                    st.caption(f"Telecaller: {user_info.get('telecaller_name', 'N/A')}")
                
                with col3:
                    status = "✅ Active" if user_info.get('is_active', True) else "❌ Inactive"
                    st.markdown(status)
                    st.caption(f"Created: {user_info.get('created_at', 'N/A')[:10]}")
                
                with col4:
                    if username != 'admin':
                        if st.button("🗑️", key=f"delete_{username}", help="Delete User"):
                            success, message = auth_manager.delete_user(username)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                
                st.markdown("---")
    
    with user_tabs[1]:
        st.markdown("### Add New User")
        
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_username = st.text_input("Username *", placeholder="Enter username")
                new_name = st.text_input("Full Name *", placeholder="Enter full name")
                new_password = st.text_input("Password *", type="password", placeholder="Enter password")
            
            with col2:
                new_role = st.selectbox("Role *", ["telecaller", "admin"])
                new_telecaller = st.text_input("Telecaller Name", 
                                              placeholder="Enter telecaller name (if telecaller)")
                confirm_password = st.text_input("Confirm Password *", type="password", 
                                                placeholder="Confirm password")
            
            submitted = st.form_submit_button("➕ Add User", type="primary", use_container_width=True)
            
            if submitted:
                errors = []
                if not new_username:
                    errors.append("Username is required")
                if not new_name:
                    errors.append("Full name is required")
                if not new_password:
                    errors.append("Password is required")
                if new_password != confirm_password:
                    errors.append("Passwords do not match")
                if new_role == "telecaller" and not new_telecaller:
                    errors.append("Telecaller name is required for telecaller role")
                
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    user_data = {
                        'name': new_name,
                        'role': new_role,
                        'telecaller_name': new_telecaller if new_role == "telecaller" else None,
                        'password': new_password
                    }
                    
                    success, message = auth_manager.add_user(new_username, user_data)
                    if success:
                        st.success(message)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(message)
    
    with user_tabs[2]:
        st.markdown("### Manage User Permissions")
        
        users = auth_manager.get_all_users()
        usernames = [u for u in users.keys() if u != 'admin']
        
        if usernames:
            selected_user = st.selectbox("Select User", usernames, key="perm_user")
            
            if selected_user:
                user_data = users[selected_user]
                current_permissions = user_data.get('permissions', {})
                
                st.markdown(f"#### Managing permissions for: {user_data['name']}")
                
                with st.form("permission_form"):
                    st.markdown("##### Report Permissions")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        can_add_reports = st.checkbox("Add Reports", 
                                                     value=current_permissions.get('can_add_reports', True))
                        can_edit_own = st.checkbox("Edit Own Reports", 
                                                  value=current_permissions.get('can_edit_own', True))
                        can_edit_all = st.checkbox("Edit All Reports", 
                                                  value=current_permissions.get('can_edit_all', False))
                    
                    with col2:
                        can_delete_all = st.checkbox("Delete Reports", 
                                                    value=current_permissions.get('can_delete_all', False))
                        can_view_all = st.checkbox("View All Reports", 
                                                  value=current_permissions.get('can_view_all', False))
                        can_export_data_perm = st.checkbox("Export Data", 
                                                          value=current_permissions.get('can_export_data', False))
                    
                    st.markdown("##### System Permissions")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        can_manage_users_perm = st.checkbox("Manage Users", 
                                                           value=current_permissions.get('can_manage_users', False))
                    
                    with col2:
                        can_view_analytics = st.checkbox("View Analytics", 
                                                        value=current_permissions.get('can_view_analytics', True))
                    
                    submitted = st.form_submit_button("💾 Save Permissions", type="primary", use_container_width=True)
                    
                    if submitted:
                        permissions = {
                            'can_add_reports': can_add_reports,
                            'can_edit_own': can_edit_own,
                            'can_edit_all': can_edit_all,
                            'can_delete_all': can_delete_all,
                            'can_view_all': can_view_all,
                            'can_export_data': can_export_data_perm,
                            'can_manage_users': can_manage_users_perm,
                            'can_view_analytics': can_view_analytics
                        }
                        
                        success, message = auth_manager.update_permissions(selected_user, permissions)
                        if success:
                            st.success(message)
                            if selected_user == st.session_state.user:
                                st.session_state.user_permissions = permissions
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(message)
        else:
            st.info("No non-admin users available for permission management.")

# System Status page
def system_status_page():
    st.markdown('<h1 class="main-header">⚙️ System Status</h1>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Connection Status")
        try:
            status = processor.check_connection()
            if status.get('google_sheets', False):
                st.success("✅ Connected to Google Sheets")
                for sheet in status.get('worksheets', []):
                    st.markdown(f"- {sheet}")
            else:
                st.warning("⚠️ Using Local Storage Mode")
                st.info("Data is stored in local JSON files")
            
            reports = processor.get_all_reports()
            st.metric("Total Reports", len(reports))
            
            if st.session_state.user_role == 'admin' or can_view_all_reports():
                if not reports.empty and 'Telecaller' in reports.columns:
                    st.metric("Active Telecallers", reports['Telecaller'].nunique())
            
            users = auth_manager.get_all_users()
            st.metric("Registered Users", len(users))
        except Exception as e:
            st.error(f"❌ Connection Error: {str(e)}")
    
    with col2:
        st.markdown("### Data Health")
        reports = processor.get_all_reports()
        
        if not reports.empty:
            total_records = len(reports)
            
            if st.session_state.user_role == 'admin' or can_view_all_reports():
                complete_records = reports.notna().all(axis=1).sum()
                video_records = reports[reports['Video'] == 'Yes'].shape[0] if 'Video' in reports.columns else 0
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Records", total_records)
                col2.metric("Complete Records", complete_records)
                col3.metric("Completion Rate", f"{(complete_records/total_records*100):.1f}%")
                
                col1, col2 = st.columns(2)
                col1.metric("Video Activities", video_records)
                if total_records > 0:
                    col2.metric("Video Rate", f"{(video_records/total_records*100):.1f}%")
                
                edit_logs = processor.get_edit_logs()
                if edit_logs is not None and not edit_logs.empty:
                    st.metric("Edit History Entries", len(edit_logs))
            else:
                my_reports = reports[reports['Telecaller'] == st.session_state.telecaller_name]
                st.metric("My Reports", len(my_reports))
        else:
            st.info("No data available")
    
    st.markdown("---")
    st.markdown("### System Actions")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 Refresh All Data", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("All caches cleared!")
            time.sleep(1)
            st.rerun()
    with col2:
        if st.button("📊 Rebuild Charts", use_container_width=True):
            st.rerun()
    with col3:
        if st.button("🧹 Clear Cache", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("Cache cleared!")
            time.sleep(1)
            st.rerun()

# Main app logic
def main():
    load_css()
    
    if not st.session_state.authenticated:
        login_page()
        st.stop()
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"""
        ## 📞 Telecaller Dashboard
        **Welcome, {st.session_state.user_name}!**
        <span class="role-badge {'badge-admin' if st.session_state.user_role == 'admin' else 'badge-telecaller'}">
            {st.session_state.user_role.upper()}
        </span>
        """, unsafe_allow_html=True)
        st.markdown("---")
        
        # Navigation
        nav_options = ["Dashboard", "Daily Reports", "Add Report", "Analysis"]
        
        if st.session_state.user_role == 'admin' or can_view_all_reports():
            nav_options.append("Edit History")
        
        if st.session_state.user_role == 'admin' or can_manage_users():
            nav_options.append("User Management")
        
        nav_options.append("System Status")
        
        if st.session_state.user_role == 'telecaller' and 'My Reports' not in nav_options:
            nav_options.insert(1, "My Reports")
            if "Daily Reports" in nav_options:
                nav_options.remove("Daily Reports")
        
        page = st.radio("Navigation", nav_options, label_visibility="collapsed")
        
        st.markdown("---")
        st.markdown("### Quick Actions")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()
        
        if st.button("🚪 Logout"):
            logout()
        
        st.markdown("---")
        st.markdown("### System Info")
        st.markdown(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        st.markdown(f"**Timezone:** {time.tzname[0]}")
    
    # Page routing
    if page == "Dashboard":
        dashboard_page()
    elif page == "Daily Reports":
        daily_reports_page()
    elif page == "My Reports":
        my_reports_page()
    elif page == "Add Report":
        add_report_page()
    elif page == "Analysis":
        analysis_page()
    elif page == "Edit History" and (st.session_state.user_role == 'admin' or can_view_all_reports()):
        edit_history_page()
    elif page == "User Management" and (st.session_state.user_role == 'admin' or can_manage_users()):
        user_management_page()
    elif page == "System Status":
        system_status_page()
    
    # Footer
    st.markdown("---")
    footer_col1, footer_col2, footer_col3 = st.columns(3)
    
    with footer_col1:
        st.markdown("**📞 Telecaller Performance Dashboard**")
        st.caption("© 2026 All Rights Reserved")
    
    with footer_col2:
        st.markdown("**Quick Actions**")
        if st.button("🔄 Refresh", key="footer_refresh"):
            st.rerun()
        if st.button("🚪 Logout", key="footer_logout"):
            logout()
    
    with footer_col3:
        st.markdown("**System Info**")
        st.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        st.caption(f"Timezone: {time.tzname[0]}")

if __name__ == "__main__":
    main()