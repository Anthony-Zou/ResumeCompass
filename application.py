import requests  # Added missing import for requests
import base64
from PIL import Image
import PIL
from typing import List, Dict, Any, Optional, Type, Callable
import plotly.graph_objects as go
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import uuid
from dotenv import load_dotenv
import json
import time
from langchain.schema.agent import AgentFinish
from langchain.tools import BaseTool, StructuredTool, Tool
from langchain.agents import AgentExecutor, create_structured_chat_agent
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.text_splitter import CharacterTextSplitter, RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader, UnstructuredPDFLoader
from langchain.prompts import PromptTemplate
from langchain.chains.summarize import load_summarize_chain
from langchain.document_loaders import Docx2txtLoader
import tempfile
import os
import streamlit as st

# Set page configuration at the very beginning
st.set_page_config(
    page_title="CareerCompass Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Try to load environment variables from .env file (for local development)
load_dotenv()


def get_api_key():

    # Then, check environment variables (for local development)
    if 'GOOGLE_API_KEY' in os.environ:
        return os.environ['GOOGLE_API_KEY']
        # First, check for API key in Streamlit secrets (for deployment)
    elif hasattr(st, 'secrets') and 'GOOGLE_API_KEY' in st.secrets:
        return st.secrets['GOOGLE_API_KEY']
    # If no key is found, return None
    else:
        return None

# Function to load and encode images for background


def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()


def set_background(png_file):
    try:
        bin_str = get_base64_of_bin_file(png_file)
        page_bg_img = '''
        <style>
        .stApp {
            background-image: url("data:image/png;base64,%s");
            background-size: cover;
            background-position: center;
        }
        </style>
        ''' % bin_str
        st.markdown(page_bg_img, unsafe_allow_html=True)
    except:
        pass  # Skip if background file not available

# Enhanced LLM setup with caching


@st.cache_resource
def initialize_llm():
    api_key = get_api_key()

    if not api_key:
        return None

    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.2,
        top_p=0.95,
        top_k=40,
        max_output_tokens=2048,
        google_api_key=api_key)


# Initialize LLM with API key and advanced parameters
llm = initialize_llm()

# Initialize conversation memory for contextual responses
# Changed from "chat_history" to "history"
memory = ConversationBufferMemory(memory_key="history")

# Create a conversation chain for follow-up questions
conversation = ConversationChain(
    llm=llm,
    memory=memory,
    verbose=True
)

# Advanced text splitter for better document processing
advanced_text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""],
    keep_separator=True,
)

# Enhanced tools for the agent


class ResumeAnalysisTool(BaseTool):
    name: str = "resume_analyzer"  # Add type annotation
    # Add type annotation
    description: str = "Analyzes a resume for strengths, weaknesses, and improvement areas"

    def _run(self, resume_text: str) -> str:
        prompt = PromptTemplate.from_template(
            "You are an expert resume analyst. Analyze the following resume: {resume_text}"
        )
        return llm.invoke(prompt.format(resume_text=resume_text)).content

    def _arun(self, resume_text: str):
        raise NotImplementedError("This tool does not support async")


class JobMatchTool(BaseTool):
    name: str = "job_matcher"  # Add type annotation
    # Add type annotation
    description: str = "Evaluates how well a resume matches a job description"

    def _run(self, resume_text: str, job_description: str) -> str:
        prompt = PromptTemplate.from_template(
            "You are an expert job matcher. Evaluate how well this resume: {resume_text} " +
            "matches this job description: {job_description}. Provide a percentage match and detailed analysis."
        )
        return llm.invoke(prompt.format(
            resume_text=resume_text,
            job_description=job_description
        )).content

    def _arun(self, resume_text: str, job_description: str):
        raise NotImplementedError("This tool does not support async")

# Add a helper function for consistent navigation sidebar


def add_navigation_sidebar():
    if not st.session_state['user_authenticated']:
        return

    st.sidebar.success(f"Logged in as: {st.session_state['user_email']}")
    if st.session_state['subscription_end_date']:
        days_left = (
            st.session_state['subscription_end_date'] - datetime.now()).days
        st.sidebar.info(f"Subscription active: {days_left} days remaining")

    st.sidebar.markdown("## Navigation")

    # Dashboard button
    if st.sidebar.button("Dashboard", key="nav_dashboard"):
        st.session_state['current_page'] = "dashboard"
        st.rerun()

    # Resume Analysis button
    if st.sidebar.button("Resume Analysis", key="nav_resume_analysis"):
        st.session_state['current_page'] = "resume_analysis"
        st.rerun()

    # Resume Generator button
    if st.sidebar.button("Resume Generator", key="nav_resume_generator"):
        st.session_state['current_page'] = "resume_generator"
        st.rerun()

    # Cover Letter Generator button
    if st.sidebar.button("Cover Letter Generator", key="nav_cover_letter"):
        st.session_state['current_page'] = "cover_letter_generator"
        st.rerun()

    st.sidebar.markdown("---")

    if st.sidebar.button("Log Out", key="nav_logout"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()


# Initialize session state for user authentication and subscription
if 'user_authenticated' not in st.session_state:
    st.session_state['user_authenticated'] = False
if 'subscription_active' not in st.session_state:
    st.session_state['subscription_active'] = False
if 'subscription_end_date' not in st.session_state:
    st.session_state['subscription_end_date'] = None
if 'user_email' not in st.session_state:
    st.session_state['user_email'] = None
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
if 'current_page' not in st.session_state:
    st.session_state['current_page'] = "login"


def process_docx(docx_file):
    # We need to modify this too to handle Streamlit uploads
    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_file:
        tmp_file.write(docx_file.getvalue())
        tmp_path = tmp_file.name

    loader = Docx2txtLoader(tmp_path)
    text = loader.load_and_split()

    # Clean up the temporary file
    os.unlink(tmp_path)
    return text


def process_pdf(pdf_file):
    text = ""
    # Create a temporary file to save the uploaded PDF
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        tmp_file.write(pdf_file.getvalue())
        tmp_path = tmp_file.name

    # Try UnstructuredPDFLoader first for better parsing of complex PDFs
    try:
        loader = UnstructuredPDFLoader(tmp_path)
        pages = loader.load()

        # If the UnstructuredPDFLoader fails to parse content properly, fall back to PyPDFLoader
        if not any(page.page_content for page in pages):
            raise ValueError("UnstructuredPDFLoader returned empty content")

        for page in pages:
            text += page.page_content

    except Exception as e:
        # Fallback to PyPDFLoader
        loader = PyPDFLoader(tmp_path)
        pages = loader.load()

        for page in pages:
            text += page.page_content

    text = text.replace('\t', ' ')

    # Use advanced text splitter for better chunk quality
    texts = advanced_text_splitter.create_documents([text])

    # Clean up the temporary file
    os.unlink(tmp_path)

    return texts

# New function for resume improvement with job-specific optimization


def generate_improved_resume(resume_text, target_job=None, style="modern"):
    prompt_template = """
    You are a professional resume writer with expertise in creating impactful, ATS-friendly resumes.
    
    Based on the following resume content:
    {resume_text}
    
    Create an improved, professionally formatted resume in the {style} style that:
    1. Emphasizes key achievements and quantifiable results
    2. Uses strong action verbs and industry-specific keywords
    3. Optimizes for ATS systems with appropriate keyword placement
    4. Follows modern resume best practices
    5. Maintains all original information but presents it more effectively
    6. Improves layout and organization for better readability
    7. Ensures proper formatting with clear section headers
    
    {job_target_info}
    
    Format the resume sections with proper markdown and ensure it's ready for professional use.
    Include a Skills section that highlights technical, soft, and transferable skills relevant to their career.
    
    Your response MUST be in markdown format suitable for professional presentation.
    """

    job_target_text = ""
    if target_job:
        job_target_text = f"""Target the resume specifically for this job description or industry: {target_job}
        Analyze the job description to identify key requirements and ensure relevant skills and experiences are 
        highlighted prominently. Include industry-specific keywords from the job description."""

    prompt = PromptTemplate.from_template(prompt_template).format(
        resume_text=resume_text,
        job_target_info=job_target_text,
        style=style
    )

    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        st.error(f"Error generating resume: {str(e)}")
        return "Error generating resume. Please try again."

# Enhanced cover letter generation with tone and style options


def generate_cover_letter(resume_text, job_description, company_info, tone="professional"):
    prompt_template = """
    You are a professional cover letter writer with expertise in creating compelling, personalized cover letters.
    
    Based on:
    
    RESUME:
    {resume_text}
    
    JOB DESCRIPTION:
    {job_description}
    
    COMPANY INFORMATION:
    {company_info}
    
    TONE REQUESTED: 
    {tone}
    
    Create a compelling cover letter that:
    1. Is personalized to the specific job and company
    2. Highlights relevant experience from the resume that matches the job description
    3. Demonstrates understanding of the company's values and goals
    4. Uses a {tone} tone throughout
    5. Includes a strong attention-grabbing opening
    6. Provides specific examples of achievements relevant to the role
    7. Includes a confident closing with a clear call to action
    8. Is between 250-350 words
    
    Format the cover letter professionally with proper salutation, paragraphs, and signature.
    Your response MUST be in markdown format suitable for professional presentation.
    """

    prompt = PromptTemplate.from_template(prompt_template).format(
        resume_text=resume_text,
        job_description=job_description,
        company_info=company_info,
        tone=tone
    )

    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        st.error(f"Error generating cover letter: {str(e)}")
        return "Error generating cover letter. Please try again."

# Resume visualization function


def generate_skills_chart(analysis_text):
    # Extract skills from the analysis
    try:
        skills_section = ""
        sections = analysis_text.split("##")
        for section in sections:
            if "Skills" in section or "Key Skills" in section:
                skills_section = section
                break

        if not skills_section:
            # If no explicit skills section, use the whole text
            skills_section = analysis_text

        # Extract skills as bullet points
        skills = []
        lines = skills_section.split('\n')
        for line in lines:
            if line.strip().startswith('- ') or line.strip().startswith('* '):
                skill = line.strip()[2:].strip()
                # Avoid long text that's probably not a skill
                if skill and len(skill) < 50:
                    skills.append(skill)

        if len(skills) < 3:
            # Fallback: ask LLM to extract skills
            prompt = f"Extract a list of professional skills from this text. Respond with only the skills as a JSON array: {skills_section}"
            response = llm.invoke(prompt).content
            try:
                # Try to extract JSON array from the response
                start_idx = response.find('[')
                end_idx = response.rfind(']') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response[start_idx:end_idx]
                    skills = json.loads(json_str)
                    skills = skills[:10]  # Limit to top 10 skills
            except:
                # If JSON parsing fails, use default skills
                skills = ["Communication", "Leadership", "Problem Solving"]

        # Generate random scores for visualization (in a real app, these would be derived from analysis)
        import random
        scores = [random.randint(60, 95) for _ in range(len(skills))]

        # Create DataFrame for visualization
        df = pd.DataFrame({
            'Skill': skills[:8],  # Limit to 8 skills for better visualization
            'Score': scores[:8]
        })

        # Create radar chart using plotly
        fig = go.Figure()

        fig.add_trace(go.Scatterpolar(
            r=df['Score'],
            theta=df['Skill'],
            fill='toself',
            fillcolor='rgba(79, 139, 249, 0.3)',
            line=dict(color='#4F8BF9', width=2),
            name='Skills Assessment'
        ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            height=400,
        )

        return fig
    except Exception as e:
        print(f"Error generating skills chart: {str(e)}")
        return None

# Add animation helper for UI elements


def load_lottie_animation(url):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

# UI components - Custom cards


def create_metric_card(title, value, delta=None):
    st.markdown(
        f"""
        <div style="background-color:white; border-radius:10px; padding:15px; margin-bottom:20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h4 style="color:#333; margin:0;">{title}</h4>
            <h2 style="color:#4F8BF9; margin:5px 0;">{value}</h2>
            {f'<p style="color:{"green" if delta > 0 else "red"}; margin:0;">{delta}%</p>' if delta is not None else ''}
        </div>
        """,
        unsafe_allow_html=True
    )

# Enhanced login interface


def show_login_page():
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(
            '<div class="title-container"><h1>CareerCompass Pro</h1><p>Login to access premium career tools</p></div>', unsafe_allow_html=True)

        with st.form("login_form"):
            st.markdown("""
            <style>
            div[data-testid="stForm"] {
                background-color: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }
            div[data-testid="stFormSubmitButton"] > button {
                background-color: #4F8BF9;
                width: 100%;
                margin-top: 20px;
            }
            </style>
            """, unsafe_allow_html=True)

            st.image(
                "https://img.icons8.com/fluent/80/000000/user-male-circle.png", width=80)
            email = st.text_input("Email", key="login_email")
            password = st.text_input(
                "Password", type="password", key="login_password")

            col1, col2 = st.columns([1, 1])
            with col1:
                st.checkbox("Remember me")
            with col2:
                st.markdown(
                    '<p style="text-align:right;"><a href="#">Forgot password?</a></p>', unsafe_allow_html=True)

            submit = st.form_submit_button("Login")

            if submit:
                with st.spinner("Authenticating..."):
                    time.sleep(1)  # Simulate authentication delay
                    if email in MOCK_USERS and MOCK_USERS[email]["password"] == password:
                        st.session_state['user_authenticated'] = True
                        st.session_state['user_email'] = email
                        st.session_state['user_id'] = MOCK_USERS[email]["id"]
                        st.session_state['current_page'] = "dashboard"
                        st.rerun()
                    else:
                        st.error("Invalid email or password")

        st.markdown("---")
        st.markdown(
            '<div style="text-align:center;">Don\'t have an account?</div>', unsafe_allow_html=True)

        if st.button("Create an account", use_container_width=True):
            st.session_state['current_page'] = "signup"
            st.rerun()

# Signup page


def show_signup_page():
    st.markdown('<div class="title-container"><h1>CareerCompass Pro</h1><p>Create your account</p></div>',
                unsafe_allow_html=True)

    with st.form("signup_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submit = st.form_submit_button("Sign Up")

        if submit:
            if password != confirm_password:
                st.error("Passwords do not match")
            elif email in MOCK_USERS:
                st.error("Email already registered")
            else:
                # In a real app, securely hash the password before storing
                MOCK_USERS[email] = {
                    "password": password, "id": str(uuid.uuid4())}
                st.success("Account created! You can now log in.")
                st.session_state['current_page'] = "login"
                st.rerun()

    st.markdown("---")
    if st.button("Already have an account? Login"):
        st.session_state['current_page'] = "login"
        st.rerun()

# Subscription page


def show_subscription_page():
    st.markdown('<div class="title-container"><h1>Choose Your Plan</h1><p>Select a subscription that fits your job search timeline</p></div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div style="border:1px solid #ddd; padding: 20px; border-radius: 10px; height: 360px;">
            <h3>2-Week Access</h3>
            <h2>$14.99</h2>
            <p>Perfect for quick job applications</p>
            <ul>
                <li>Resume Analysis & Optimization</li>
                <li>Cover Letter Generation</li>
                <li>Interview Preparation</li>
                <li>2-Week Access</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Select 2-Week Plan"):
            success, end_date = validate_subscription(
                st.session_state['user_id'], "2-week")
            if success:
                st.session_state['subscription_active'] = True
                st.session_state['subscription_end_date'] = end_date
                st.session_state['current_page'] = "dashboard"
                st.rerun()

    with col2:
        st.markdown("""
        <div style="border:1px solid #4f8bf9; padding: 20px; border-radius: 10px; background-color: #f8f9fe; height: 360px;">
            <h3>Monthly Access</h3>
            <h2>$29.99</h2>
            <p><strong>Most Popular</strong></p>
            <ul>
                <li>Resume Analysis & Optimization</li>
                <li>Cover Letter Generation</li>
                <li>Interview Preparation</li>
                <li>30-Day Access</li>
                <li>Priority Support</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Select Monthly Plan"):
            success, end_date = validate_subscription(
                st.session_state['user_id'], "monthly")
            if success:
                st.session_state['subscription_active'] = True
                st.session_state['subscription_end_date'] = end_date
                st.session_state['current_page'] = "dashboard"
                st.rerun()

    with col3:
        st.markdown("""
        <div style="border:1px solid #ddd; padding: 20px; border-radius: 10px; height: 360px;">
            <h3>Annual Access</h3>
            <h2>$199.99</h2>
            <p>Best Value</p>
            <ul>
                <li>Resume Analysis & Optimization</li>
                <li>Cover Letter Generation</li>
                <li>Interview Preparation</li>
                <li>365-Day Access</li>
                <li>Priority Support</li>
                <li>Job Search Tracking</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Select Annual Plan"):
            success, end_date = validate_subscription(
                st.session_state['user_id'], "annual")
            if success:
                st.session_state['subscription_active'] = True
                st.session_state['subscription_end_date'] = end_date
                st.session_state['current_page'] = "dashboard"
                st.rerun()


# Mock user database (replace with actual database in production)
MOCK_USERS = {
    "user@example.com": {"password": "password123", "id": "user123"}
}

# Mock subscription validation (replace with actual payment processor integration)


def validate_subscription(user_id, plan_type):
    # In a real app, call payment processor API to validate payment
    # For demo, always return success
    today = datetime.now()

    if plan_type == "2-week":
        end_date = today + timedelta(days=14)
    elif plan_type == "monthly":
        end_date = today + timedelta(days=30)
    elif plan_type == "annual":
        end_date = today + timedelta(days=365)
    else:
        return False, None

    return True, end_date

# Custom Dashboard Metrics


def calculate_resume_metrics(user_id):
    # In a real app, these would come from a database
    metrics = {
        "resume_score": 78,
        "industry_avg": 65,
        "improvement": 12,
        "keyword_match": 82,
        "format_score": 90,
        "areas_to_improve": 3
    }
    return metrics

# Enhanced Dashboard with analytics


def show_dashboard():
    add_navigation_sidebar()

    st.markdown('<div class="title-container"><h1>Welcome to CareerCompass Pro</h1><p>Your all-in-one career toolkit</p></div>', unsafe_allow_html=True)

    # Resume metrics (in a real app, these would come from actual analysis)
    metrics = calculate_resume_metrics(st.session_state['user_id'])

    # Display metrics in a modern dashboard layout
    st.markdown("## Resume Analytics")
    col1, col2, col3 = st.columns(3)

    with col1:
        create_metric_card(
            "Resume Score", f"{metrics['resume_score']}%")
    with col2:
        create_metric_card("Industry Average", f"{metrics['industry_avg']}%")
    with col3:
        create_metric_card("ATS Match Score", f"{metrics['keyword_match']}%")

    # Add charts
    st.markdown("## Your Skills Analysis")
    st.info("Upload your resume in Resume Analysis to generate your personalized skills visualization")

    # Main tools section
    st.markdown("## Career Tools")
    col1, col2, col3 = st.columns(3)

    with col1:
        # Make the cards clickable with enhanced styling
        st.markdown("""
        <div style="border:1px solid #4F8BF9; padding:20px; border-radius:10px; text-align:center; 
                   cursor:pointer; background-color:white; height:220px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <img src="" style="width:48px; margin-bottom:10px;">
            <h3 style="color:#4F8BF9;">Resume Analysis</h3>
            <p>Get comprehensive feedback and insights on your current resume</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Go to Resume Analysis", key="goto_resume_analysis", use_container_width=True):
            st.session_state['current_page'] = "resume_analysis"
            st.rerun()

    with col2:
        st.markdown("""
        <div style="border:1px solid #4F8BF9; padding:20px; border-radius:10px; text-align:center; 
                   cursor:pointer; background-color:white; height:220px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <img src="" style="width:48px; margin-bottom:10px;">
            <h3 style="color:#4F8BF9;">Resume Generator</h3>
            <p>Create an optimized, ATS-friendly version of your resume</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Go to Resume Generator", key="goto_resume_generator", use_container_width=True):
            st.session_state['current_page'] = "resume_generator"
            st.rerun()

    with col3:
        st.markdown("""
        <div style="border:1px solid #4F8BF9; padding:20px; border-radius:10px; text-align:center; 
                   cursor:pointer; background-color:white; height:220px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <img src="" style="width:48px; margin-bottom:10px;">
            <h3 style="color:#4F8BF9;">Cover Letter Generator</h3>
            <p>Generate targeted cover letters for specific job applications</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Go to Cover Letter Generator", key="goto_cover_letter", use_container_width=True):
            st.session_state['current_page'] = "cover_letter_generator"
            st.rerun()

    # Recent activity section (would be populated from database in real app)
    st.markdown("## Recent Activity")
    activity_data = [
        {"date": "May 15, 2023", "activity": "Generated 3 cover letters",
            "status": "Complete"},
        {"date": "May 12, 2023", "activity": "Resume analyzed", "status": "Complete"},
        {"date": "May 10, 2023",
            "activity": "Resume optimized for Software Engineer role", "status": "Complete"}
    ]

    st.table(pd.DataFrame(activity_data))

# Enhanced Resume Generator page with style selection


def show_resume_generator():
    add_navigation_sidebar()

    st.markdown('<div class="title-container"><h1>Resume Generator</h1><p>Create an optimized version of your resume</p></div>', unsafe_allow_html=True)

    # Add a back button to return to dashboard
    col_back, col_spacer = st.columns([1, 5])
    with col_back:
        if st.button("← Back to Dashboard", key="back_to_dashboard_from_generator"):
            st.session_state['current_page'] = "dashboard"
            st.rerun()

    # Use tabs for different resume generator options
    tab1, tab2 = st.tabs(["Basic Generator", "Advanced Generator"])

    with tab1:
        uploaded_file = st.file_uploader(
            "Upload your current resume", type=["pdf", "docx"], key="resume_gen_uploader")
        target_job = st.text_area(
            "Enter the job title or description you're targeting (optional)", height=100)

        if uploaded_file and st.button("Generate Improved Resume", use_container_width=True):
            with st.spinner("Analyzing and improving your resume..."):
                if uploaded_file.name.endswith('.docx'):
                    text = process_docx(uploaded_file)
                    resume_text = "\n".join([doc.page_content for doc in text])
                else:
                    text = process_pdf(uploaded_file)
                    resume_text = "\n".join([doc.page_content for doc in text])

                improved_resume = generate_improved_resume(
                    resume_text, target_job, "modern")

                st.success("Resume successfully improved!")
                with st.expander("View Improved Resume", expanded=True):
                    st.markdown(improved_resume)

                # Download options
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="Download as Markdown",
                        data=improved_resume,
                        file_name="improved_resume.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
                with col2:
                    # In a full implementation, we would convert to PDF and offer download
                    st.button("Download as PDF (Premium)",
                              disabled=True, use_container_width=True)

    with tab2:
        st.markdown("### Advanced Resume Generator")
        uploaded_file = st.file_uploader(
            "Upload your current resume", type=["pdf", "docx"], key="adv_resume_gen_uploader")

        col1, col2 = st.columns(2)
        with col1:
            target_job = st.text_area(
                "Job Description (for targeting)", height=150)
        with col2:
            style = st.selectbox("Resume Style",
                                 ["Modern", "Traditional", "Creative",
                                     "Executive", "Technical"],
                                 index=0)

        st.markdown("### Resume Sections")
        col1, col2, col3 = st.columns(3)
        with col1:
            include_summary = st.checkbox("Professional Summary", value=True)
        with col2:
            include_skills = st.checkbox("Skills Section", value=True)
        with col3:
            include_achievements = st.checkbox("Key Achievements", value=True)

        if uploaded_file and st.button("Generate Advanced Resume", use_container_width=True):
            with st.spinner("Creating your optimized resume..."):
                if uploaded_file.name.endswith('.docx'):
                    text = process_docx(uploaded_file)
                    resume_text = "\n".join([doc.page_content for doc in text])
                else:
                    text = process_pdf(uploaded_file)
                    resume_text = "\n".join([doc.page_content for doc in text])

                improved_resume = generate_improved_resume(
                    resume_text, target_job, style.lower())

                st.success("Premium resume successfully generated!")

                tab1, tab2 = st.tabs(["Preview", "ATS Analysis"])

                with tab1:
                    st.markdown(improved_resume)

                with tab2:
                    st.info("ATS Compatibility Analysis")

                    # In a real implementation, this would be actual ATS analysis
                    ats_score = 92
                    st.progress(ats_score/100)
                    st.markdown(f"**ATS Compatibility Score:** {ats_score}%")

                    st.markdown("**Keyword Matches:**")
                    st.json({
                        "project management": "Found",
                        "team leadership": "Found",
                        "agile": "Found",
                        "data analysis": "Not Found - Consider Adding",
                        "strategic planning": "Found"
                    })

                # Download options
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="Download as Markdown",
                        data=improved_resume,
                        file_name="premium_resume.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
                with col2:
                    st.button("Download as PDF (Premium)",
                              disabled=True, use_container_width=True)

# Enhanced Cover Letter Generator with tone selection


def show_cover_letter_generator():
    add_navigation_sidebar()

    st.markdown('<div class="title-container"><h1>Cover Letter Generator</h1><p>Create targeted cover letters for specific job applications</p></div>', unsafe_allow_html=True)

    # Add a back button to return to dashboard
    col_back, col_spacer = st.columns([1, 5])
    with col_back:
        if st.button("← Back to Dashboard", key="back_to_dashboard_from_cover_letter"):
            st.session_state['current_page'] = "dashboard"
            st.rerun()

    # Enhanced UI with sections
    st.markdown("### Upload Your Information")

    col1, col2 = st.columns(2)
    with col1:
        uploaded_file = st.file_uploader(
            "Upload your resume", type=["pdf", "docx"])
    with col2:
        tone = st.selectbox("Cover Letter Tone",
                            ["Professional", "Enthusiastic",
                                "Confident", "Formal", "Conversational"],
                            index=0)

    st.markdown("### Job Information")
    job_description = st.text_area("Paste the job description", height=150)

    st.markdown("### Company Research")
    company_info = st.text_area(
        "Enter information about the company (culture, values, mission, etc.)", height=100)

    col1, col2, col3 = st.columns(3)
    with col1:
        include_salary = st.checkbox(
            "Include salary expectations", value=False)
    with col2:
        include_availability = st.checkbox(
            "Include availability date", value=False)
    with col3:
        include_references = st.checkbox("Mention references", value=False)

    if uploaded_file and job_description and st.button("Generate Cover Letter", use_container_width=True):
        with st.spinner("Creating your personalized cover letter..."):
            if uploaded_file.name.endswith('.docx'):
                text = process_docx(uploaded_file)
                resume_text = "\n".join([doc.page_content for doc in text])
            else:
                text = process_pdf(uploaded_file)
                resume_text = "\n".join([doc.page_content for doc in text])

            cover_letter = generate_cover_letter(
                resume_text, job_description, company_info, tone.lower())

            st.success("Cover letter successfully generated!")

            # Use tabs for different views
            tab1, tab2 = st.tabs(["Preview", "Format Options"])

            with tab1:
                st.markdown(cover_letter)

            with tab2:
                st.markdown("### Formatting Options")
                st.radio("Font Style", [
                         "Modern", "Traditional", "Professional"])
                st.radio("Salutation", [
                         "Dear Hiring Manager", "Dear Recruiter", "To Whom It May Concern"])

            # Download options with columns for better layout
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Download as Markdown",
                    data=cover_letter,
                    file_name="cover_letter.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            with col2:
                st.button("Download as PDF (Premium)",
                          disabled=True, use_container_width=True)

# Enhanced Resume Analysis with visualizations


def show_resume_analysis():
    add_navigation_sidebar()

    st.markdown('<div class="title-container"><h1>Resume Analysis</h1><p>Get detailed feedback on your current resume</p></div>', unsafe_allow_html=True)

    # Add a back button to return to dashboard
    col_back, col_spacer = st.columns([1, 5])
    with col_back:
        if st.button("← Back to Dashboard", key="back_to_dashboard_from_analysis"):
            st.session_state['current_page'] = "dashboard"
            st.rerun()

    # Main content area with two columns
    col1, col2 = st.columns([1, 2])

    with col1:
       # st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        st.markdown("### Upload Your Resume")

        # Add option for example resume
        # use_example = st.checkbox("Use example resume")
        use_example = False
        if use_example:
            # This would be a path to an actual example file
            uploaded_file = "example_resume.pdf"
            st.info("Using example resume")
        else:
            uploaded_file = st.file_uploader(
                "", type=["pdf", "docx"], key="resume_uploader")

        if uploaded_file and not use_example:
            st.success(f"Uploaded: {uploaded_file.name}")
            file_details = {
                "Filename": uploaded_file.name,
                "File size": f"{uploaded_file.size / 1024:.2f} KB",
                "File type": uploaded_file.type
            }
            for key, value in file_details.items():
                st.text(f"{key}: {value}")

        # Optional target job field
        # target_job = st.text_input("Target job position (optional)")
        target_job = ""
        st.markdown('</div>', unsafe_allow_html=True)

    # Main column for results
    with col2:
        if uploaded_file is not None and not use_example:
            with st.spinner("Analyzing your resume..."):
                progress_bar = st.progress(0)

                # Process the file based on extension
                file_extension = uploaded_file.name.split(".")[-1]

                progress_bar.progress(25)
                time.sleep(0.5)  # Simulate processing time

                if file_extension == "docx":
                    text = process_docx(uploaded_file)
                elif file_extension == "pdf":
                    text = process_pdf(uploaded_file)
                else:
                    st.error(
                        "Unsupported file type. Please upload a PDF or DOCX file.")
                    st.markdown('</div>', unsafe_allow_html=True)
                    return

                progress_bar.progress(50)
                time.sleep(0.5)  # Simulate processing time

                # Setup enhanced prompts with more detailed instructions - FIX HERE
                prompt_template_str = """
                You are a professional CV analyzer with expertise in resume evaluation and career coaching.
                Write a detailed analysis of the following resume content:
                {text}
                """

                # Create a proper PromptTemplate object with only the text variable
                prompt = PromptTemplate(
                    template=prompt_template_str,
                    input_variables=["text"]
                )

                # Handle target job separately after chain execution if needed
                resume_content = "\n".join([doc.page_content for doc in text])

                refine_template = (
                    # ...existing template...
                    "Your job is to produce a final outcome\n"
                    "We have provided an existing detail: {existing_answer}\n"
                    "We want a refined version of the existing detail based on initial details below\n"
                    "--------\n"
                    "Given the new context, refine the original summary in the following manner using proper markdown formatting:\n"
                    # ...rest of the template...
                )

                # Create a proper PromptTemplate object for the refine template
                refine_prompt = PromptTemplate(
                    template=refine_template,
                    input_variables=["existing_answer", "text"]
                )

                chain = load_summarize_chain(
                    llm=llm,
                    chain_type="refine",
                    question_prompt=prompt,
                    refine_prompt=refine_prompt,
                    return_intermediate_steps=True,
                    input_key="input_documents",
                    output_key="output_text",
                )

                # Now we pass only the required input_documents to the chain
                result = chain({"input_documents": text},
                               return_only_outputs=True)

                # If target job is specified, we can add this information to the output
                if target_job:
                    job_prompt = f"\n\n## Target Job Analysis\nAdditional analysis for target job: {target_job}"
                    result['output_text'] += job_prompt

                progress_bar.progress(75)
                time.sleep(0.5)  # Simulate processing time

                result = chain({"input_documents": text},
                               return_only_outputs=True)

                progress_bar.progress(100)
                time.sleep(0.5)  # Simulate completion

                # Hide the progress elements
                progress_bar.empty()

                # Parse the result into sections
                output_text = result['output_text']
                sections = output_text.split('##')

                # Create tabs for different views of the analysis
                tab1, tab2, tab3 = st.tabs(
                    ["Analysis", "Insights", "Visualization"])

                with tab1:
                    # Display a success message
                    st.success(
                        "Analysis complete! Review your personalized career guidance below.")

                    # Process each section with better styling
                    for section in sections:
                        if section.strip():  # Skip empty sections
                            lines = section.strip().split('\n', 1)
                            if len(lines) > 0:
                                section_title = lines[0].strip()
                                section_content = lines[1].strip() if len(
                                    lines) > 1 else ""

                                # Special handling for Name and Email sections
                                if section_title.lower() == "name" or section_title.lower() == "email":
                                    st.markdown(
                                        f"<h3 class='section-header'>{section_title}</h3>", unsafe_allow_html=True)
                                    st.markdown(
                                        f"<p>{section_content}</p>", unsafe_allow_html=True)
                                    if section_title.lower() == "email":
                                        st.markdown(
                                            "<hr>", unsafe_allow_html=True)
                                else:
                                    # Create an expander for other sections
                                    with st.expander(f"{section_title}", expanded=False):
                                        st.markdown(section_content)

                with tab2:
                    # Create a summary of key insights
                    st.subheader("Key Insights")

                    # Extract insights from the analysis
                    try:
                        # In a real implementation, we would use more sophisticated extraction
                        strengths = []
                        improvements = []

                        for section in sections:
                            if "Career Assessment" in section:
                                lines = section.split("\n")
                                for line in lines:
                                    if line.strip().startswith("- ") and "strength" in line.lower():
                                        strengths.append(line.strip()[2:])
                            elif "Resume Gaps" in section:
                                lines = section.split("\n")
                                for line in lines:
                                    if line.strip().startswith("- "):
                                        improvements.append(line.strip()[2:])

                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("### Strengths")
                            for strength in strengths[:3]:  # Show top 3
                                st.success(strength)

                        with col2:
                            st.markdown("### Areas for Improvement")
                            for improvement in improvements[:3]:  # Show top 3
                                st.warning(improvement)

                        # Resume Scores
                        st.markdown("### Resume Score")

                        # In a real implementation, these would be derived from actual analysis
                        scores = {
                            "Overall": 78,
                            "Format": 85,
                            "Content": 76,
                            "ATS Compatibility": 82,
                            "Industry Relevance": 75
                        }

                        # Display scores as horizontal bars
                        for category, score in scores.items():
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.progress(score/100)
                            with col2:
                                st.write(f"{score}%")
                            st.caption(category)

                    except Exception as e:
                        st.error(f"Error generating insights: {str(e)}")
                        st.write(
                            "Could not generate insights from the analysis. Please try again.")

                with tab3:
                    # Generate skill visualization
                    st.subheader("Skills Visualization")

                    skills_chart = generate_skills_chart(output_text)
                    if skills_chart:
                        st.plotly_chart(skills_chart, use_container_width=True)
                    else:
                        st.info(
                            "Skills visualization could not be generated. Please check the analysis for skills information.")

                # Add download options
                st.download_button(
                    label="Download Analysis as Text",
                    data=result['output_text'],
                    file_name=f"career_analysis_{uploaded_file.name.split('.')[0] if not use_example else 'example'}.txt",
                    mime="text/plain"
                )

                # Add option for follow-up questions
                st.markdown("### Have questions about your analysis?")
                follow_up = st.text_input(
                    "Ask a follow-up question about your resume or the analysis")

                if follow_up:
                    with st.spinner("Generating response..."):
                        # Use the conversation chain for context-aware responses
                        conversation.memory.save_context(
                            # First 1000 chars for context
                            {"input": f"Resume analysis: {output_text[:1000]}..."},
                            {"output": "I've analyzed this resume."}
                        )

                        response = conversation.predict(input=follow_up)
                        st.write(response)


def main():
    # Try to set a background image for enhanced visual appeal
    # set_background("/path/to/background.png")  # Uncomment and provide path if available

    # Add custom CSS with enhanced styling
    st.markdown("""
    <style>
    /* Base styles */
    .main {
        padding: 2rem;
        background-color: #f8f9fa;
    }
    
    /* Header container */
    .title-container {
        background: linear-gradient(90deg, #4f8bf9, #4361ee);
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    /* Card containers */
    .upload-container, .results-container {
        background-color: white;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        margin-bottom: 2rem;
        border-left: 5px solid #4f8bf9;
    }
    
    /* Section headers */
    .section-header {
        color: #4f8bf9;
        font-weight: bold;
        margin-top: 1rem;
        border-bottom: 2px solid #f0f0f0;
        padding-bottom: 8px;
    }
    
    /* Expander styling */
    .expander-header {
        font-weight: bold !important;
        color: #2c3e50 !important;
    }
    
    /* Enhanced expanders */
    div.stExpander > div:first-child {
        font-weight: bold;
        font-size: 1.1em;
        background: linear-gradient(90deg, #f1f7fe, white);
        border-radius: 5px;
        padding: 0.7rem;
        border-left: 3px solid #4f8bf9;
    }
    
    div.stExpander > div:nth-child(2) {
        max-height: 300px;
        overflow-y: auto;
        padding: 1.2rem;
        border-left: 3px solid #4CAF50;
        background-color: #fcfcfc;
        margin-left: 10px;
    }
    
    /* Progress bar */
    .stProgress .st-c6 {
        background-color: #4f8bf9 !important;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #4f8bf9;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    
    .stButton > button:hover {
        background-color: #3a7bd5;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }
    
    /* File uploader */
    .stFileUploader {
        padding: 1rem;
        border: 2px dashed #c2c2c2;
        border-radius: 5px;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    /* Tables */
    .dataframe {
        border-collapse: collapse;
        width: 100%;
        border-radius: 5px;
        overflow: hidden;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
    }
    
    .dataframe thead th {
        background-color: #4f8bf9;
        color: white;
        padding: 12px;
        text-align: left;
    }
    
    .dataframe tbody tr:nth-child(even) {
        background-color: #f8f9fa;
    }
    
    .dataframe tbody td {
        padding: 10px;
        border-bottom: 1px solid #ddd;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding: 10px 16px;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #4f8bf9;
        color: white;
    }
    
    /* Inputs and text areas */
    input, textarea {
        border-radius: 5px;
        border: 1px solid #ddd;
        padding: 10px;
    }
    
    /* Sidebar */
    .sidebar .sidebar-content {
        background-color: #2c3e50;
    }
    </style>
    """, unsafe_allow_html=True)

    # Check if API key is available
    api_key = get_api_key()
    if not api_key:
        st.error(
            "Google API Key not found. Please set up your API key in Streamlit secrets or environment variables.")
        st.info("For local development: Add GOOGLE_API_KEY to your .env file\nFor Streamlit deployment: Add GOOGLE_API_KEY to your app secrets")
        return

    # Route to the appropriate page based on auth status and current page
    if not st.session_state['user_authenticated']:
        if st.session_state['current_page'] == "signup":
            show_signup_page()
        else:
            show_login_page()
    else:
        if not st.session_state['subscription_active']:
            show_subscription_page()
        else:
            if st.session_state['current_page'] == "dashboard":
                show_dashboard()
            elif st.session_state['current_page'] == "resume_analysis":
                show_resume_analysis()
            elif st.session_state['current_page'] == "resume_generator":
                show_resume_generator()
            elif st.session_state['current_page'] == "cover_letter_generator":
                show_cover_letter_generator()


if __name__ == "__main__":
    main()
