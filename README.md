
# 🧠 LinkedIn Apply Bot with Offline AI Integration (Ollama)

## Project Overview

This project automates the job application process on LinkedIn Easy Apply and extends support to external platforms such as Greenhouse, Ashby, and more. It features AI-powered resume tailoring and intelligent question answering via offline LLMs (Ollama or any LLM provider through LiteLLM), delivering a personalized, end-to-end automation experience for job seekers.

---

## 🚦 Project Status

### ✅ Stable Features

- Automated login and job application for LinkedIn Easy Apply
- AI-driven question answering for application forms (text, numeric, multiple-choice)
- Resume tailoring and skill replacement to optimize ATS scores
- Support for both PDF and DOCX resumes
- Offline AI integration (Ollama + phi4-mini) for data privacy and speed
- Flexible backend—integrate any LLM via LiteLLM
- Modular codebase designed for extensibility and additional platforms

### 🧪 Experimental Features

- Support for external applications including Greenhouse and Ashby
- Resume tailoring and regeneration (DOCX to PDF)

### 🚧 In Development / On the Way

- Improved resume tailoring using RAG with semantic chunking and vector retrieval
- Lightweight LLM-powered rewriting of resume sections based on job descriptions
- Resume context compression for small models to reduce hallucination
- Confidence scoring and APPLY/SKIP justification for job fit evaluation
- Pluggable model backend (phi4-mini, Mistral, TinyLlama, etc.)
- Logging outcomes for feedback loop and model fine-tuning


## 🧩 Technologies Used

- Python (Selenium, PDF, DOCX)
- Ollama for offline LLM chat
- `phi4-mini` model
- PyAutoGUI (to prevent system sleep)
- Regex, JSON, CSV, and automation utilities


## 📦 Getting Started

1. Clone the repository
2. Configure `config.yaml` with your details (LinkedIn credentials, resume path, etc.)
3. Run the bot using your preferred driver (e.g., Chrome WebDriver)
4. Ensure Ollama and the `phi4-mini` model are running locally
5. Ensure you have Groq API Key in .env file.

## ⚙️ AI Capabilities

- Uses LLM to:
  - Extract job-specific skills
  - Replace outdated resume skills
  - Tailor and regenerate resume (DOCX to PDF) *(experimental)*
  - Answer custom LinkedIn application questions
  - Evaluate job fit (optional, in development)

## 🔮 Future Work

- Expand support for more external job platforms
- Add a user-friendly GUI for configuration and monitoring
- Enhance error handling and reporting
- Community-driven plugin system for new features


## 📁 Repository Status

> This project is a **modified version** of a popular LinkedIn Easy Apply Bot with enhanced AI capabilities via offline models.
> 
> Original credit: https://github.com/NathanDuma/LinkedIn-Easy-Apply-Bot

## 📜 License

This project is for educational and personal use only. Do not use it to spam applications or violate LinkedIn's terms.

---

🔐 **Important:** Keep your `config.yaml` and credentials private. Do not upload them to any public repo.
