"""
MapleStory Idle Calculator - Streamlit Web App
Main entry point with login/registration flow.
"""
import os
import streamlit as st
from utils.auth import authenticate, create_user, user_exists
from utils.data_manager import load_user_data, save_user_data, UserData

# =============================================================================
# LOCAL DEV BYPASS - Set to True to skip login during development
# =============================================================================
# Option 1: Set this directly to True for local testing
# Option 2: Set environment variable MAPLE_DEV_MODE=true
DEV_MODE = True  # <-- Toggle this for local dev
# DEV_MODE = os.environ.get("MAPLE_DEV_MODE", "false").lower() == "true"
DEV_USERNAME = "dev_user"

# Page config
st.set_page_config(
    page_title="MapleStory Idle Calculator",
    page_icon="🍁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme
st.markdown("""
<style>
    .stApp {
        background-color: #1a1a2e;
    }
    .main-title {
        color: #00d4ff;
        font-size: 2.5em;
        font-weight: bold;
        text-align: center;
        margin-bottom: 20px;
    }
    .sub-title {
        color: #888;
        text-align: center;
        margin-bottom: 30px;
    }
    .login-container {
        max-width: 400px;
        margin: auto;
        padding: 30px;
        background-color: #2a2a4e;
        border-radius: 10px;
    }
    .stButton > button {
        width: 100%;
        background-color: #4a4a8a;
        color: white;
        border: none;
        padding: 10px;
        border-radius: 5px;
    }
    .stButton > button:hover {
        background-color: #5a5a9a;
    }
    .success-msg {
        color: #00ff88;
        text-align: center;
    }
    .error-msg {
        color: #ff4444;
        text-align: center;
    }
    .user-info {
        color: #ffd700;
        font-size: 1.1em;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'user_data' not in st.session_state:
        st.session_state.user_data = None


def login_page():
    """Display login/register page."""
    st.markdown('<div class="main-title">🍁 MapleStory Idle Calculator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Track your stats, optimize your build</div>', unsafe_allow_html=True)

    # Create centered container
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            st.subheader("Welcome Back!")
            login_username = st.text_input("Username", key="login_user", placeholder="Enter username")
            login_password = st.text_input("Password", key="login_pass", type="password", placeholder="Enter password")

            if st.button("Login", key="login_btn"):
                if login_username and login_password:
                    success, result = authenticate(login_username, login_password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.username = result
                        st.session_state.user_data = load_user_data(result)
                        st.success(f"Welcome back, {result}!")
                        st.rerun()
                    else:
                        st.error(result)
                else:
                    st.warning("Please enter username and password")

        with tab2:
            st.subheader("Create Account")
            reg_code = st.text_input("Registration Code", key="reg_code", type="password", placeholder="Required to create account")
            reg_username = st.text_input("Choose Username", key="reg_user", placeholder="2-20 characters")
            reg_password = st.text_input("Choose Password", key="reg_pass", type="password", placeholder="At least 4 characters")
            reg_password2 = st.text_input("Confirm Password", key="reg_pass2", type="password", placeholder="Repeat password")

            if st.button("Create Account", key="reg_btn"):
                if reg_password != reg_password2:
                    st.error("Passwords don't match!")
                elif reg_username and reg_password and reg_code:
                    success, msg = create_user(reg_username, reg_password, reg_code)
                    if success:
                        st.success(msg + " You can now login.")
                    else:
                        st.error(msg)
                else:
                    st.warning("Please fill in all fields")


def main_app():
    """Display main application after login."""
    # Sidebar with user info and navigation
    with st.sidebar:
        st.markdown(f'<div class="user-info">👤 Logged in as: {st.session_state.username}</div>', unsafe_allow_html=True)
        st.divider()

        if st.button("💾 Save Data"):
            if save_user_data(st.session_state.username, st.session_state.user_data):
                st.success("Data saved!")
            else:
                st.error("Failed to save")

        if st.button("🚪 Logout"):
            # Save before logout
            save_user_data(st.session_state.username, st.session_state.user_data)
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.user_data = None
            st.rerun()

        st.divider()
        st.markdown("### Navigation")
        st.markdown("Use the pages in the sidebar to navigate between different sections of the calculator.")

    # Main content
    st.markdown('<div class="main-title">🍁 MapleStory Idle Calculator</div>', unsafe_allow_html=True)

    # Quick stats overview
    data = st.session_state.user_data

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Character Level", data.character_level)
    with col2:
        st.metric("All Skills", f"+{data.all_skills}")
    with col3:
        st.metric("Combat Mode", data.combat_mode.title())
    with col4:
        st.metric("Chapter", data.chapter.replace("Chapter ", "Ch. "))

    st.divider()

    # Welcome message and instructions
    st.markdown("### Welcome!")
    st.markdown("""
    Use the **sidebar navigation** to access different sections:

    - **Character Settings** - Set your level, skills, and combat mode
    - **Equipment** - Track your equipment items, starforce, and potentials
    - **Hero Power** - Configure your hero power lines and passives
    - **Artifacts** - Manage your artifacts and their effects
    - **Weapons** - Track weapon ATK% bonuses
    - **Companions** - Set up your companion team
    - **Maple Rank** - Track your Maple Rank progression
    - **Damage Calculator** - Calculate your DPS and see stat priorities
    - **Character Stats** - View aggregated stats from all sources
    - **Upgrade Optimizer** - Get recommendations for upgrades
    - **Cube Tools** - Cube simulator and cost calculator
    - **Starforce Calc** - Calculate starforce costs
    - **Stat Guide** - Reference information

    Your data is **automatically saved** when you log out or click the Save button.
    """)


def dev_auto_login():
    """Auto-login for development mode."""
    if not st.session_state.logged_in:
        st.session_state.logged_in = True
        st.session_state.username = DEV_USERNAME
        # Load or create dev user data
        try:
            st.session_state.user_data = load_user_data(DEV_USERNAME)
        except Exception:
            st.session_state.user_data = UserData()


def main():
    """Main entry point."""
    init_session_state()

    # Dev mode bypass
    if DEV_MODE:
        dev_auto_login()
        st.sidebar.warning("🔧 DEV MODE - Auth bypassed")

    if st.session_state.logged_in:
        main_app()
    else:
        login_page()


if __name__ == "__main__":
    main()
