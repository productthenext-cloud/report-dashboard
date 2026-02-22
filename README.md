# Telecaller Daily Report Dashboard

A Streamlit-based dashboard for tracking telecaller daily performance metrics with Google Sheets as a database.

## Features

- 🔐 User authentication (Admin/Telecaller roles)
- 📊 Daily report submission and tracking
- 📈 Performance analytics and visualization
- 👥 User management (Admin only)
- 📝 Edit history tracking
- 🎥 Video activity monitoring
- 🌍 Country distribution analysis
- 📱 Responsive design

## Technology Stack

- **Frontend**: Streamlit
- **Database**: Google Sheets (with local JSON fallback)
- **Authentication**: SHA-256 password hashing
- **Charts**: Plotly
- **Hosting**: Render

## Prerequisites

- Python 3.9+
- Google Cloud Platform account
- Google Sheets API enabled
- Render account (for deployment)

## Local Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/telecaller-dashboard.git
cd telecaller-dashboard