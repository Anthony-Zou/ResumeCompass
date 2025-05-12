# ResumeCompass Pro

ResumeCompass Pro is an AI-powered career toolkit that helps users optimize their resumes, generate targeted cover letters, and receive detailed career guidance. Built with Streamlit and powered by Google's Gemini AI, it provides a modern, user-friendly interface for career development.

## Features

- **Resume Analysis**: Get detailed feedback on your resume's strengths and areas for improvement
- **Resume Generator**: Create optimized, ATS-friendly versions of your resume
- **Cover Letter Generator**: Generate targeted cover letters for specific job applications
- **Skills Visualization**: Interactive visualization of your professional skills
- **Career Dashboard**: Track your career progress and get personalized insights

## Prerequisites

- Python 3.9 or higher
- Google API Key for Gemini AI
- pip (Python package installer)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/ResumeCompass.git
cd ResumeCompass
```

2. Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install the required packages:

```bash
pip install -r requirements.txt
```

4. Set up your environment variables:
   - Create a `.env` file in the project root
   - Add your Google API key:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```

## Usage

1. Start the application:

```bash
streamlit run application.py
```

2. Open your web browser and navigate to the URL shown in the terminal (typically http://localhost:8501)

3. Log in with your credentials or create a new account

4. Choose from the available tools:
   - Resume Analysis
   - Resume Generator
   - Cover Letter Generator
   - Career Dashboard

## Features in Detail

### Resume Analysis

- Upload your resume in PDF or DOCX format
- Receive detailed feedback on content, formatting, and ATS compatibility
- Get suggestions for improvement
- View skills visualization

### Resume Generator

- Create optimized versions of your resume
- Target specific job descriptions
- Choose from multiple resume styles
- Download in various formats

### Cover Letter Generator

- Generate targeted cover letters
- Customize tone and style
- Include company-specific information
- Download in multiple formats

### Career Dashboard

- Track your career progress
- View resume scores and improvements
- Monitor application status
- Access personalized career insights

## Dependencies

- streamlit: Web application framework
- langchain: Framework for LLM applications
- langchain-google-genai: Google Gemini AI integration
- langchain-community: Community-maintained LangChain components
- python-dotenv: Environment variable management
- PyPDF2: PDF processing
- docx2txt: DOCX file processing
- plotly: Data visualization
- pandas: Data manipulation
- requests: HTTP requests
- unstructured: Document processing
- python-magic: File type detection

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Google Gemini AI for powering the AI features
- Streamlit for the web framework
- All contributors and users of the project

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.

## Roadmap

- [ ] Add more resume templates
- [ ] Implement job search integration
- [ ] Add interview preparation tools
- [ ] Enhance ATS compatibility checking
- [ ] Add multi-language support
