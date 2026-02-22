import os
import json
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import tempfile
from pathlib import Path

# Google Sheets imports
try:
    import gspread
    from google.oauth2.service_account import Credentials
    from google.auth.exceptions import GoogleAuthError
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False
    print("⚠️ Google Sheets libraries not installed. Using local storage only.")

class GoogleSheetsService:
    def __init__(self):
        self.is_render = os.environ.get('RENDER', False)
        self.use_google_sheets = False
        self.gc = None
        self.sheet = None
        self.worksheets = {}
        
        # Setup local storage fallback
        self._setup_local_storage()
        
        # Try to initialize Google Sheets if credentials exist
        self._init_google_sheets()
    
    def _setup_local_storage(self):
        """Setup local storage directory"""
        if self.is_render:
            self.data_dir = Path(tempfile.gettempdir()) / 'telecaller_dashboard'
        else:
            self.data_dir = Path('data')
        
        self.data_dir.mkdir(exist_ok=True, parents=True)
        
        # Initialize data files
        self.reports_file = self.data_dir / 'reports.json'
        self.edit_logs_file = self.data_dir / 'edit_logs.json'
        
        if not self.reports_file.exists():
            self._save_json(self.reports_file, [])
        
        if not self.edit_logs_file.exists():
            self._save_json(self.edit_logs_file, [])
    
    def _init_google_sheets(self):
        """Initialize Google Sheets connection"""
        if not GOOGLE_SHEETS_AVAILABLE:
            print("⚠️ Google Sheets libraries not available")
            return
        
        try:
            # Get credentials from environment or secrets
            creds_json = None
            sheet_url = None
            
            if self.is_render:
                # On Render, get from environment variables
                creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
                sheet_url = os.environ.get('GOOGLE_SHEET_URL')
            else:
                # Local development - try streamlit secrets
                try:
                    if 'gcp_service_account' in st.secrets:
                        creds_json = st.secrets["gcp_service_account"]
                    if 'private_gsheets_url' in st.secrets:
                        sheet_url = st.secrets["private_gsheets_url"]
                except:
                    pass
            
            if creds_json and sheet_url:
                # Parse credentials
                if isinstance(creds_json, str):
                    creds_info = json.loads(creds_json)
                else:
                    creds_info = dict(creds_json)
                
                # Define required scopes
                scopes = [
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
                
                # Create credentials
                credentials = Credentials.from_service_account_info(
                    creds_info, scopes=scopes
                )
                
                # Authorize with gspread
                self.gc = gspread.authorize(credentials)
                
                # Open the spreadsheet by URL
                self.sheet = self.gc.open_by_url(sheet_url)
                
                # Get all worksheets
                for worksheet in self.sheet.worksheets():
                    self.worksheets[worksheet.title] = worksheet
                
                self.use_google_sheets = True
                print("✅ Connected to Google Sheets")
                
                # Initialize worksheets if they don't exist
                self._ensure_worksheets()
            else:
                print("⚠️ Google Sheets credentials not found, using local storage")
                
        except Exception as e:
            print(f"❌ Error initializing Google Sheets: {str(e)}")
            print("⚠️ Falling back to local storage")
    
    def _ensure_worksheets(self):
        """Ensure required worksheets exist"""
        required_worksheets = ['Reports', 'Users', 'EditLogs']
        
        for ws_name in required_worksheets:
            if ws_name not in self.worksheets:
                try:
                    self.worksheets[ws_name] = self.sheet.add_worksheet(
                        title=ws_name, rows=1000, cols=20
                    )
                    # Add headers
                    if ws_name == 'Reports':
                        headers = ['Date', 'Telecaller', 'Day', 'Total Calls', 'New Data', 
                                 'CRM Data', 'Country Data', 'Fair Data', 'Video', 
                                 'Video Details', 'Other Work Description', 'Visited Students', 
                                 'Remarks', 'Timestamp']
                        self.worksheets[ws_name].append_row(headers)
                    elif ws_name == 'Users':
                        headers = ['Username', 'Password', 'Role', 'Name', 'TelecallerName',
                                 'Permissions', 'CreatedAt', 'UpdatedAt', 'IsActive']
                        self.worksheets[ws_name].append_row(headers)
                    elif ws_name == 'EditLogs':
                        headers = ['Timestamp', 'User', 'Username', 'Role', 'Action',
                                 'ReportDate', 'Telecaller', 'OriginalData', 'NewData']
                        self.worksheets[ws_name].append_row(headers)
                except Exception as e:
                    print(f"Error creating worksheet {ws_name}: {str(e)}")
    
    def _load_json(self, file_path):
        """Load JSON data from file"""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def _save_json(self, file_path, data):
        """Save JSON data to file"""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def get_users(self):
        """Get users from Google Sheets or local storage"""
        if self.use_google_sheets and 'Users' in self.worksheets:
            try:
                worksheet = self.worksheets['Users']
                records = worksheet.get_all_records()
                
                # Convert to dictionary format
                users = {}
                for record in records:
                    username = record.get('Username')
                    if username:
                        users[username] = {
                            'password': record.get('Password'),
                            'role': record.get('Role'),
                            'name': record.get('Name'),
                            'telecaller_name': record.get('TelecallerName'),
                            'permissions': json.loads(record.get('Permissions', '{}')),
                            'created_at': record.get('CreatedAt'),
                            'updated_at': record.get('UpdatedAt'),
                            'is_active': record.get('IsActive', 'True') == 'True'
                        }
                return users
            except Exception as e:
                print(f"Error reading users from Google Sheets: {str(e)}")
                return self._get_local_users()
        else:
            return self._get_local_users()
    
    def _get_local_users(self):
        """Get users from local JSON"""
        users_file = self.data_dir / 'users.json'
        if users_file.exists():
            try:
                with open(users_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_users(self, users):
        """Save users to Google Sheets or local storage"""
        if self.use_google_sheets and 'Users' in self.worksheets:
            try:
                worksheet = self.worksheets['Users']
                
                # Clear existing data (keep headers)
                worksheet.clear()
                worksheet.append_row(['Username', 'Password', 'Role', 'Name', 'TelecallerName',
                                    'Permissions', 'CreatedAt', 'UpdatedAt', 'IsActive'])
                
                # Add users
                for username, user_data in users.items():
                    row = [
                        username,
                        user_data.get('password', ''),
                        user_data.get('role', ''),
                        user_data.get('name', ''),
                        user_data.get('telecaller_name', ''),
                        json.dumps(user_data.get('permissions', {})),
                        user_data.get('created_at', ''),
                        user_data.get('updated_at', ''),
                        str(user_data.get('is_active', True))
                    ]
                    worksheet.append_row(row)
                return True
            except Exception as e:
                print(f"Error saving users to Google Sheets: {str(e)}")
                return self._save_local_users(users)
        else:
            return self._save_local_users(users)
    
    def _save_local_users(self, users):
        """Save users to local JSON"""
        users_file = self.data_dir / 'users.json'
        try:
            with open(users_file, 'w') as f:
                json.dump(users, f, indent=2, default=str)
            return True
        except:
            return False
    
    def add_report(self, report_data):
        """Add a new report"""
        if self.use_google_sheets and 'Reports' in self.worksheets:
            try:
                worksheet = self.worksheets['Reports']
                report_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Convert report_data to list in correct order
                row = [
                    report_data.get('date', ''),
                    report_data.get('telecaller', ''),
                    report_data.get('day', ''),
                    report_data.get('total_calls', 0),
                    report_data.get('new_data', 0),
                    report_data.get('crm_data', 0),
                    report_data.get('country_data', ''),
                    report_data.get('fair_data', 0),
                    report_data.get('video', 'No'),
                    report_data.get('video_details', ''),
                    report_data.get('other_work', ''),
                    report_data.get('visited_students', 0),
                    report_data.get('remarks', ''),
                    report_data.get('timestamp', '')
                ]
                worksheet.append_row(row)
                return True
            except Exception as e:
                print(f"Error adding report to Google Sheets: {str(e)}")
                return self._add_local_report(report_data)
        else:
            return self._add_local_report(report_data)
    
    def _add_local_report(self, report_data):
        """Add report to local JSON"""
        try:
            reports = self._load_json(self.reports_file)
            report_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            reports.append(report_data)
            self._save_json(self.reports_file, reports)
            return True
        except Exception as e:
            print(f"Error adding local report: {str(e)}")
            return False
    
    def get_all_reports(self):
        """Get all reports from Google Sheets or local JSON"""
        if self.use_google_sheets and 'Reports' in self.worksheets:
            try:
                worksheet = self.worksheets['Reports']
                data = worksheet.get_all_records()
                return pd.DataFrame(data)
            except Exception as e:
                print(f"Error reading from Google Sheets: {str(e)}")
                return self._get_local_reports()
        else:
            return self._get_local_reports()
    
    def _get_local_reports(self):
        """Get reports from local JSON"""
        try:
            reports = self._load_json(self.reports_file)
            if reports:
                return pd.DataFrame(reports)
            return pd.DataFrame()
        except:
            return pd.DataFrame()
    
    def update_report(self, index, report_data):
        """Update an existing report"""
        if self.use_google_sheets and 'Reports' in self.worksheets:
            # Note: This is simplified. In production, you'd need to handle row updates properly
            print("Update via Google Sheets requires row identification")
            return self._update_local_report(index, report_data)
        else:
            return self._update_local_report(index, report_data)
    
    def _update_local_report(self, index, report_data):
        """Update report in local JSON"""
        try:
            reports = self._load_json(self.reports_file)
            if 0 <= index < len(reports):
                report_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                reports[index] = report_data
                self._save_json(self.reports_file, reports)
                return True
            return False
        except:
            return False
    
    def delete_report(self, index):
        """Delete a report"""
        if self.use_google_sheets and 'Reports' in self.worksheets:
            # Note: This is simplified
            return self._delete_local_report(index)
        else:
            return self._delete_local_report(index)
    
    def _delete_local_report(self, index):
        """Delete report from local JSON"""
        try:
            reports = self._load_json(self.reports_file)
            if 0 <= index < len(reports):
                reports.pop(index)
                self._save_json(self.reports_file, reports)
                return True
            return False
        except:
            return False
    
    def log_edit_action(self, edit_log):
        """Log edit actions"""
        if self.use_google_sheets and 'EditLogs' in self.worksheets:
            try:
                worksheet = self.worksheets['EditLogs']
                row = [
                    edit_log.get('timestamp', ''),
                    edit_log.get('user', ''),
                    edit_log.get('username', ''),
                    edit_log.get('role', ''),
                    edit_log.get('action', ''),
                    edit_log.get('report_date', ''),
                    edit_log.get('telecaller', ''),
                    edit_log.get('original_data', ''),
                    edit_log.get('new_data', '')
                ]
                worksheet.append_row(row)
                return True
            except Exception as e:
                print(f"Error logging to Google Sheets: {str(e)}")
                return self._add_local_edit_log(edit_log)
        else:
            return self._add_local_edit_log(edit_log)
    
    def _add_local_edit_log(self, edit_log):
        """Add edit log to local JSON"""
        try:
            logs = self._load_json(self.edit_logs_file)
            logs.append(edit_log)
            self._save_json(self.edit_logs_file, logs)
            return True
        except:
            return False
    
    def get_edit_logs(self):
        """Get edit logs"""
        if self.use_google_sheets and 'EditLogs' in self.worksheets:
            try:
                worksheet = self.worksheets['EditLogs']
                data = worksheet.get_all_records()
                return pd.DataFrame(data)
            except Exception as e:
                print(f"Error reading edit logs from Google Sheets: {str(e)}")
                return self._get_local_edit_logs()
        else:
            return self._get_local_edit_logs()
    
    def _get_local_edit_logs(self):
        """Get edit logs from local JSON"""
        try:
            logs = self._load_json(self.edit_logs_file)
            if logs:
                return pd.DataFrame(logs)
            return pd.DataFrame()
        except:
            return pd.DataFrame()
    
    def check_connection(self):
        """Check connection status"""
        if self.use_google_sheets:
            return {
                'google_sheets': True,
                'worksheets': list(self.worksheets.keys()),
                'local_mode': False
            }
        else:
            return {
                'google_sheets': False,
                'worksheets': ['Local JSON Storage'],
                'local_mode': True
            }


class DataProcessor:
    def __init__(self):
        """Initialize the DataProcessor with Google Sheets integration"""
        self.gs_service = GoogleSheetsService()
    
    def add_report(self, report_data):
        """Add a new report"""
        try:
            return self.gs_service.add_report(report_data)
        except Exception as e:
            st.error(f"Error adding report: {str(e)}")
            return False
    
    def get_all_reports(self, filters=None):
        """Get all reports with optional filters"""
        try:
            df = self.gs_service.get_all_reports()
            
            if df.empty:
                return df
            
            # Standardize column names
            column_mapping = {
                'Date': 'Date',
                'Telecaller': 'Telecaller',
                'Day': 'Day',
                'Total Calls': 'Total Calls',
                'New Data': 'New Data',
                'CRM Data': 'CRM Data',
                'Country Data': 'Country Data',
                'Fair Data': 'Fair Data',
                'Video': 'Video',
                'Video Details': 'Video Details',
                'Other Work Description': 'Other Work Description',
                'Visited Students': 'Visited Students',
                'Remarks': 'Remarks'
            }
            
            # Rename columns to match expected names
            df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
            
            # Convert Date column to datetime
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.dropna(subset=['Date'])
            
            # Convert numeric columns
            numeric_cols = ['Total Calls', 'New Data', 'CRM Data', 'Fair Data', 'Visited Students']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            
            # Apply filters
            if filters:
                if 'start_date' in filters and filters['start_date'] and 'Date' in df.columns:
                    df = df[df['Date'].dt.date >= filters['start_date']]
                if 'end_date' in filters and filters['end_date'] and 'Date' in df.columns:
                    df = df[df['Date'].dt.date <= filters['end_date']]
                if 'telecaller' in filters and filters['telecaller'] and filters['telecaller'] != 'All':
                    df = df[df['Telecaller'] == filters['telecaller']]
                if 'video' in filters and filters['video'] != 'All' and 'Video' in df.columns:
                    df = df[df['Video'] == filters['video']]
                if 'search' in filters and filters['search']:
                    search_term = filters['search'].lower()
                    mask = df.astype(str).apply(lambda x: x.str.lower().str.contains(search_term, na=False)).any(axis=1)
                    df = df[mask]
            
            return df.sort_values('Date', ascending=False) if not df.empty and 'Date' in df.columns else df
        except Exception as e:
            st.error(f"Error fetching reports: {str(e)}")
            return pd.DataFrame()
    
    def update_report(self, index, report_data):
        """Update an existing report"""
        try:
            return self.gs_service.update_report(index, report_data)
        except Exception as e:
            st.error(f"Error updating report: {str(e)}")
            return False
    
    def delete_report(self, index):
        """Delete a report"""
        try:
            return self.gs_service.delete_report(index)
        except Exception as e:
            st.error(f"Error deleting report: {str(e)}")
            return False
    
    def get_dashboard_stats(self, time_range='today', telecaller=None):
        """Get dashboard statistics"""
        df = self.get_all_reports()
        
        if df.empty:
            return {
                'total_calls': 0, 'new_data': 0, 'crm_data': 0, 'video_activities': 0,
                'country_data': 0, 'country_data_count': 0, 'fair_data': 0, 'visited_students': 0,
                'avg_calls_per_day': 0, 'avg_new_data_per_day': 0,
                'crm_completion_rate': 0, 'conversion_rate': 0
            }
        
        if telecaller and 'Telecaller' in df.columns:
            df = df[df['Telecaller'] == telecaller]
        
        today = datetime.now().date()
        
        if 'Date' in df.columns:
            if time_range == 'today':
                df = df[df['Date'].dt.date == today]
            elif time_range == 'yesterday':
                yesterday = today - timedelta(days=1)
                df = df[df['Date'].dt.date == yesterday]
            elif time_range == 'week':
                week_ago = today - timedelta(days=7)
                df = df[df['Date'].dt.date >= week_ago]
            elif time_range == 'month':
                month_ago = today - timedelta(days=30)
                df = df[df['Date'].dt.date >= month_ago]
        
        total_calls = df['Total Calls'].sum() if not df.empty and 'Total Calls' in df.columns else 0
        new_data = df['New Data'].sum() if not df.empty and 'New Data' in df.columns else 0
        crm_data = df['CRM Data'].sum() if not df.empty and 'CRM Data' in df.columns else 0
        video_activities = df[df['Video'] == 'Yes'].shape[0] if not df.empty and 'Video' in df.columns else 0
        
        # Country data - count of non-empty country entries
        country_data_count = 0
        if not df.empty and 'Country Data' in df.columns:
            country_data_count = df['Country Data'].notna() & (df['Country Data'] != '')
            country_data_count = country_data_count.sum() if not isinstance(country_data_count, int) else 0
        
        fair_data = df['Fair Data'].sum() if not df.empty and 'Fair Data' in df.columns else 0
        visited_students = df['Visited Students'].sum() if not df.empty and 'Visited Students' in df.columns else 0
        
        num_days = len(df['Date'].dt.date.unique()) if not df.empty and 'Date' in df.columns else 1
        avg_calls_per_day = total_calls / num_days if num_days > 0 else 0
        avg_new_data_per_day = new_data / num_days if num_days > 0 else 0
        
        crm_completion_rate = (crm_data / total_calls * 100) if total_calls > 0 else 0
        conversion_rate = (new_data / total_calls * 100) if total_calls > 0 else 0
        
        return {
            'total_calls': total_calls,
            'new_data': new_data,
            'crm_data': crm_data,
            'video_activities': video_activities,
            'country_data': country_data_count,
            'country_data_count': country_data_count,
            'fair_data': fair_data,
            'visited_students': visited_students,
            'avg_calls_per_day': round(avg_calls_per_day, 1),
            'avg_new_data_per_day': round(avg_new_data_per_day, 1),
            'crm_completion_rate': round(crm_completion_rate, 1),
            'conversion_rate': round(conversion_rate, 1)
        }
    
    def get_weekly_summary(self, telecaller=None):
        """Get weekly performance summary"""
        df = self.get_all_reports()
        
        if df.empty:
            return []
        
        if telecaller and 'Telecaller' in df.columns:
            df = df[df['Telecaller'] == telecaller]
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        if 'Date' in df.columns:
            df_week = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
        else:
            return []
        
        if df_week.empty:
            return []
        
        daily_stats = df_week.groupby(df_week['Date'].dt.date).agg({
            'Total Calls': 'sum',
            'New Data': 'sum'
        }).reset_index()
        
        daily_stats['date'] = pd.to_datetime(daily_stats['Date']).dt.strftime('%Y-%m-%d')
        daily_stats = daily_stats.sort_values('Date')
        
        return daily_stats.to_dict('records')
    
    def get_performance_trend(self, days=30, telecaller=None):
        """Get performance trend for specified number of days"""
        df = self.get_all_reports()
        
        if df.empty:
            return []
        
        if telecaller and 'Telecaller' in df.columns:
            df = df[df['Telecaller'] == telecaller]
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        if 'Date' in df.columns:
            df_trend = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
        else:
            return []
        
        if df_trend.empty:
            return []
        
        trend_data = df_trend.groupby(df_trend['Date'].dt.date).agg({
            'Total Calls': 'sum',
            'New Data': 'sum'
        }).reset_index()
        
        trend_data['date'] = pd.to_datetime(trend_data['Date']).dt.strftime('%Y-%m-%d')
        trend_data = trend_data.sort_values('Date')
        
        return trend_data.to_dict('records')
    
    def get_telecaller_performance(self):
        """Get performance summary for all telecallers"""
        df = self.get_all_reports()
        
        if df.empty or 'Telecaller' not in df.columns:
            return pd.DataFrame()
        
        performance = df.groupby('Telecaller').agg({
            'Total Calls': 'sum',
            'New Data': 'sum',
            'CRM Data': 'sum',
            'Video': lambda x: (x == 'Yes').sum()
        }).reset_index()
        
        performance.columns = ['Telecaller', 'Total Calls', 'New Data', 'CRM Data', 'Video Activities']
        performance['Conversion Rate'] = (performance['New Data'] / performance['Total Calls'] * 100).round(1)
        
        return performance
    
    def get_video_activities(self, days=30, telecaller=None):
        """Get video activities"""
        df = self.get_all_reports()
        
        if df.empty:
            return []
        
        if telecaller and 'Telecaller' in df.columns:
            df = df[df['Telecaller'] == telecaller]
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        if 'Date' in df.columns and 'Video' in df.columns:
            video_df = df[(df['Video'] == 'Yes') & (df['Date'] >= start_date) & (df['Date'] <= end_date)].copy()
        else:
            return []
        
        if video_df.empty:
            return []
        
        video_df = video_df.sort_values('Date', ascending=False)
        video_df['date'] = video_df['Date'].dt.strftime('%Y-%m-%d')
        
        return video_df.to_dict('records')
    
    def get_country_distribution(self, telecaller=None):
        """Get country distribution of leads"""
        df = self.get_all_reports()
        
        if df.empty:
            return {}
        
        if telecaller and 'Telecaller' in df.columns:
            df = df[df['Telecaller'] == telecaller]
        
        if 'Country Data' in df.columns:
            country_data = df[df['Country Data'].notna() & (df['Country Data'] != '')]
        else:
            return {}
        
        if country_data.empty:
            return {}
        
        return country_data['Country Data'].value_counts().to_dict()
    
    def log_edit_action(self, edit_log):
        """Log edit actions for history tracking"""
        try:
            return self.gs_service.log_edit_action(edit_log)
        except Exception as e:
            st.error(f"Error logging edit action: {str(e)}")
            return False
    
    def get_edit_logs(self):
        """Get edit history logs"""
        try:
            return self.gs_service.get_edit_logs()
        except Exception as e:
            st.error(f"Error fetching edit logs: {str(e)}")
            return pd.DataFrame()
    
    def check_connection(self):
        """Check connection status"""
        try:
            return self.gs_service.check_connection()
        except:
            return {'google_sheets': False, 'worksheets': [], 'local_mode': True}