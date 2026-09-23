# AI Resume Matcher

An AI-powered tool that analyzes how well a resume matches a job description, providing a match score, key strengths, gaps, and actionable improvement suggestions — powered by Google's Gemini API.

**🔗 Live Demo:** _(add your deployed link here once live)_

## Features

- Paste in a resume and a job description
- Get an instant AI-generated match score (0–100%)
- See your strengths relative to the role
- Identify gaps between your experience and the job requirements
- Receive specific, actionable suggestions to improve alignment

## Tech Stack

- **Frontend:** HTML, CSS, vanilla JavaScript
- **Backend:** Node.js, Express
- **AI:** Google Gemini API (`@google/generative-ai`)

## How It Works

1. The user submits their resume text and a target job description via a simple web form.
2. The Express backend constructs a structured prompt and sends it to the Gemini API.
3. Gemini analyzes both texts and returns a structured JSON response (match score, strengths, gaps, suggestions).
4. The frontend renders this response as a clean, readable report.

## Running Locally

```bash
git clone https://github.com/YOUR_USERNAME/ai-resume-matcher.git
cd ai-resume-matcher
npm install
```

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

Then run:

```bash
node server.js
```

Visit `http://localhost:3500` in your browser.

## Project Structure

```
ai-resume-matcher/
├── server.js          # Express backend + Gemini API integration
├── public/
│   └── index.html      # Frontend UI
├── .env                # API key (not committed to Git)
├── .gitignore
└── package.json
```

## Why I Built This

This project combines full-stack development (React-style frontend patterns, Express backend, REST API design) with practical LLM integration — going beyond a basic chatbot wrapper to build something genuinely useful: helping job seekers quickly understand how well their resume aligns with a specific role.
