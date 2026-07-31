"""
tool_rankings.py — AI Tool Ranking Table
==========================================
Static ranking data for recommending the best AI tools based on user task.

Each entry contains:
  - task:    The canonical user-task label.
  - aliases: Alternative names/phrases that map to this task.
  - rank_1, rank_2, rank_3: Top 3 recommended tools in order.
"""

from __future__ import annotations

from typing import TypedDict


class ToolRankingEntry(TypedDict):
    task: str
    aliases: list[str]
    rank_1: str
    rank_2: str
    rank_3: str


TOOL_RANKINGS: list[ToolRankingEntry] = [
    # ── General / Chat ────────────────────────────────────────────────
    {
        "task": "General Chat",
        "aliases": ["chat", "conversation", "general", "talk", "ask question", "general purpose"],
        "rank_1": "ChatGPT",
        "rank_2": "Claude",
        "rank_3": "Gemini",
    },
    {
        "task": "Deep Research",
        "aliases": ["research", "deep dive", "in-depth research", "investigative research", "thorough research"],
        "rank_1": "ChatGPT Deep Research",
        "rank_2": "Perplexity",
        "rank_3": "Gemini",
    },
    {
        "task": "Academic Research",
        "aliases": ["academic", "scholarly research", "scientific research", "paper research", "literature review"],
        "rank_1": "Consensus",
        "rank_2": "Elicit",
        "rank_3": "ChatGPT",
    },

    # ── Coding & Development ──────────────────────────────────────────
    {
        "task": "Coding",
        "aliases": ["programming", "code", "software development", "write code", "develop software", "developer", "coder", "coding assistant"],
        "rank_1": "Claude",
        "rank_2": "ChatGPT",
        "rank_3": "Gemini",
    },
    {
        "task": "Debugging Code",
        "aliases": ["debug", "fix bug", "troubleshoot code", "error fixing", "code error"],
        "rank_1": "Claude",
        "rank_2": "ChatGPT",
        "rank_3": "DeepSeek",
    },
    {
        "task": "React/Web Development",
        "aliases": [
            "react", "web development", "frontend", "frontend developer", "frontend dev",
            "web dev", "web app", "website development", "html css javascript", "nextjs",
            "vue", "angular", "landing page", "web page", "website design"
        ],
        "rank_1": "Claude",
        "rank_2": "ChatGPT",
        "rank_3": "Cursor",
    },
    {
        "task": "Mobile App Development",
        "aliases": ["mobile app", "ios development", "android development", "flutter", "react native", "mobile development"],
        "rank_1": "Claude",
        "rank_2": "ChatGPT",
        "rank_3": "Gemini",
    },

    # ── Design ────────────────────────────────────────────────────────
    {
        "task": "UI/UX Design Ideas",
        "aliases": ["ui design", "ux design", "user interface", "user experience", "design ideas", "wireframe", "mockup"],
        "rank_1": "ChatGPT",
        "rank_2": "Claude",
        "rank_3": "Gemini",
    },
    {
        "task": "Website Generation",
        "aliases": ["generate website", "build website", "website builder", "no-code website", "create site"],
        "rank_1": "Lovable",
        "rank_2": "Bolt",
        "rank_3": "Replit",
    },

    # ── Business & Professional ───────────────────────────────────────
    {
        "task": "Business Plan",
        "aliases": ["business strategy", "startup plan", "business model", "business proposal"],
        "rank_1": "ChatGPT",
        "rank_2": "Claude",
        "rank_3": "Gemini",
    },
    {
        "task": "Resume Writing",
        "aliases": ["resume", "cv", "curriculum vitae", "resume builder"],
        "rank_1": "ChatGPT",
        "rank_2": "Claude",
        "rank_3": "Gemini",
    },
    {
        "task": "Cover Letter",
        "aliases": ["cover letter writing", "job application letter", "application letter"],
        "rank_1": "ChatGPT",
        "rank_2": "Claude",
        "rank_3": "Gemini",
    },
    {
        "task": "Email Writing",
        "aliases": ["write email", "email draft", "professional email", "compose email"],
        "rank_1": "ChatGPT",
        "rank_2": "Claude",
        "rank_3": "Gemini",
    },
    {
        "task": "Legal Document Drafting",
        "aliases": ["legal writing", "contract drafting", "legal document", "terms of service", "privacy policy"],
        "rank_1": "Claude",
        "rank_2": "ChatGPT",
        "rank_3": "Gemini",
    },

    # ── Marketing & Content ───────────────────────────────────────────
    {
        "task": "Marketing Copy",
        "aliases": ["marketing", "ad copy", "advertising copy", "sales copy", "copywriting"],
        "rank_1": "Claude",
        "rank_2": "ChatGPT",
        "rank_3": "Jasper",
    },
    {
        "task": "SEO Content",
        "aliases": ["seo", "search engine optimization", "seo writing", "seo article", "keyword optimization"],
        "rank_1": "Claude",
        "rank_2": "ChatGPT",
        "rank_3": "Gemini",
    },
    {
        "task": "Blog Writing",
        "aliases": ["blog", "blog post", "article writing", "write article", "blogging"],
        "rank_1": "Claude",
        "rank_2": "ChatGPT",
        "rank_3": "Gemini",
    },
    {
        "task": "Social Media Posts",
        "aliases": ["social media", "twitter post", "instagram caption", "linkedin post", "social content", "tweet"],
        "rank_1": "ChatGPT",
        "rank_2": "Claude",
        "rank_3": "Jasper",
    },

    # ── Creative Writing ──────────────────────────────────────────────
    {
        "task": "Story Writing",
        "aliases": ["story", "fiction writing", "creative writing", "short story", "narrative writing"],
        "rank_1": "Claude",
        "rank_2": "ChatGPT",
        "rank_3": "Gemini",
    },
    {
        "task": "Book Writing",
        "aliases": ["book", "novel writing", "write a book", "manuscript", "long-form writing"],
        "rank_1": "Claude",
        "rank_2": "ChatGPT",
        "rank_3": "Sudowrite",
    },

    # ── Image Generation ──────────────────────────────────────────────
    {
        "task": "Image Generation",
        "aliases": ["generate image", "create image", "ai image", "image creation", "picture generation"],
        "rank_1": "Midjourney",
        "rank_2": "GPT Image",
        "rank_3": "Flux",
    },
    {
        "task": "Photorealistic Images",
        "aliases": ["photorealistic", "realistic photo", "photo generation", "realistic image"],
        "rank_1": "Midjourney",
        "rank_2": "Flux",
        "rank_3": "GPT Image",
    },
    {
        "task": "AI Art",
        "aliases": ["ai artwork", "digital art", "art generation", "artistic image", "concept art"],
        "rank_1": "Midjourney",
        "rank_2": "Flux",
        "rank_3": "Leonardo",
    },
    {
        "task": "Logo Design",
        "aliases": ["logo", "brand logo", "logo creation", "design logo", "company logo"],
        "rank_1": "GPT Image",
        "rank_2": "Ideogram",
        "rank_3": "Midjourney",
    },
    {
        "task": "Posters/Flyers",
        "aliases": ["poster", "flyer", "poster design", "flyer design", "promotional material"],
        "rank_1": "Ideogram",
        "rank_2": "GPT Image",
        "rank_3": "Midjourney",
    },
    {
        "task": "Text Inside Images",
        "aliases": ["text in image", "image with text", "typography image", "text overlay"],
        "rank_1": "Ideogram",
        "rank_2": "GPT Image",
        "rank_3": "Flux",
    },
    {
        "task": "YouTube Thumbnail",
        "aliases": ["thumbnail", "youtube thumbnail", "video thumbnail", "yt thumbnail"],
        "rank_1": "Midjourney",
        "rank_2": "GPT Image",
        "rank_3": "Flux",
    },
    {
        "task": "Product Photography",
        "aliases": ["product photo", "product shot", "product image", "ecommerce photography"],
        "rank_1": "Flux",
        "rank_2": "Midjourney",
        "rank_3": "GPT Image",
    },

    # ── Video Generation ──────────────────────────────────────────────
    {
        "task": "Video Generation",
        "aliases": ["generate video", "create video", "ai video", "video creation"],
        "rank_1": "Veo",
        "rank_2": "Kling",
        "rank_3": "Runway",
    },
    {
        "task": "Cinematic Video",
        "aliases": ["cinematic", "movie quality video", "film production", "cinematic footage"],
        "rank_1": "Veo",
        "rank_2": "Kling",
        "rank_3": "Runway",
    },
    {
        "task": "Shorts/Reels",
        "aliases": ["shorts", "reels", "tiktok", "short video", "vertical video", "short form video"],
        "rank_1": "Kling",
        "rank_2": "Veo",
        "rank_3": "Runway",
    },
    {
        "task": "Animation",
        "aliases": ["animate", "motion graphics", "animated video", "cartoon animation"],
        "rank_1": "Runway",
        "rank_2": "Kling",
        "rank_3": "Veo",
    },
    {
        "task": "AI Avatar Video",
        "aliases": ["avatar video", "talking head", "virtual presenter", "ai spokesperson"],
        "rank_1": "HeyGen",
        "rank_2": "Synthesia",
        "rank_3": "Veo",
    },

    # ── Audio & Music ─────────────────────────────────────────────────
    {
        "task": "Voice Cloning",
        "aliases": ["clone voice", "voice replication", "voice synthesis", "voice copy"],
        "rank_1": "ElevenLabs",
        "rank_2": "PlayHT",
        "rank_3": "Cartesia",
    },
    {
        "task": "Text-to-Speech",
        "aliases": ["tts", "text to speech", "speech synthesis", "read aloud", "voiceover"],
        "rank_1": "ElevenLabs",
        "rank_2": "PlayHT",
        "rank_3": "OpenAI Voice",
    },
    {
        "task": "Music Generation",
        "aliases": ["generate music", "create music", "ai music", "compose music", "music creation"],
        "rank_1": "Suno",
        "rank_2": "Udio",
        "rank_3": "AIVA",
    },
    {
        "task": "Background Music",
        "aliases": ["background score", "ambient music", "soundtrack", "bgm", "royalty free music"],
        "rank_1": "Udio",
        "rank_2": "Suno",
        "rank_3": "AIVA",
    },

    # ── Productivity & Presentations ──────────────────────────────────
    {
        "task": "Presentation Creation",
        "aliases": ["presentation", "slides", "powerpoint", "pitch deck", "slide deck", "create presentation"],
        "rank_1": "Gamma",
        "rank_2": "Canva",
        "rank_3": "Beautiful.ai",
    },
    {
        "task": "Spreadsheet Analysis",
        "aliases": ["spreadsheet", "excel analysis", "google sheets", "csv analysis", "tabular data"],
        "rank_1": "ChatGPT",
        "rank_2": "Claude",
        "rank_3": "Gemini",
    },
    {
        "task": "Data Analysis",
        "aliases": ["analyze data", "data science", "data insights", "statistical analysis", "data visualization"],
        "rank_1": "ChatGPT",
        "rank_2": "Claude",
        "rank_3": "Gemini",
    },

    # ── Education & Science ───────────────────────────────────────────
    {
        "task": "Math Problems",
        "aliases": ["math", "mathematics", "solve equation", "calculus", "algebra", "math homework"],
        "rank_1": "Gemini",
        "rank_2": "ChatGPT",
        "rank_3": "Claude",
    },
    {
        "task": "Physics/Chemistry",
        "aliases": ["physics", "chemistry", "science problems", "science homework", "physics equations"],
        "rank_1": "Gemini",
        "rank_2": "ChatGPT",
        "rank_3": "Claude",
    },
    {
        "task": "Medical Information",
        "aliases": ["medical", "health information", "symptoms", "medical advice", "healthcare"],
        "rank_1": "ChatGPT",
        "rank_2": "Gemini",
        "rank_3": "Claude",
    },

    # ── Lifestyle & Planning ──────────────────────────────────────────
    {
        "task": "Travel Planning",
        "aliases": ["travel", "trip planning", "itinerary", "vacation planning", "travel guide"],
        "rank_1": "ChatGPT",
        "rank_2": "Gemini",
        "rank_3": "Perplexity",
    },
    {
        "task": "Shopping Advice",
        "aliases": ["shopping", "buy recommendation", "what to buy", "purchase advice"],
        "rank_1": "ChatGPT",
        "rank_2": "Perplexity",
        "rank_3": "Gemini",
    },
    {
        "task": "Product Comparison",
        "aliases": ["compare products", "product review", "which is better", "product vs product"],
        "rank_1": "Perplexity",
        "rank_2": "ChatGPT",
        "rank_3": "Gemini",
    },

    # ── Learning ──────────────────────────────────────────────────────
    {
        "task": "Learning New Skills",
        "aliases": ["learn", "tutorial", "how to", "skill building", "online learning", "teach me"],
        "rank_1": "ChatGPT",
        "rank_2": "Gemini",
        "rank_3": "Claude",
    },
    {
        "task": "Language Learning",
        "aliases": ["learn language", "language practice", "language tutor", "foreign language"],
        "rank_1": "ChatGPT",
        "rank_2": "Gemini",
        "rank_3": "Claude",
    },
    {
        "task": "Translation",
        "aliases": ["translate", "language translation", "translate text", "multilingual"],
        "rank_1": "Gemini",
        "rank_2": "ChatGPT",
        "rank_3": "DeepL",
    },

    # ── Workspace & Automation ────────────────────────────────────────
    {
        "task": "Meeting Notes",
        "aliases": ["meeting summary", "meeting minutes", "transcribe meeting", "meeting recap"],
        "rank_1": "Notion AI",
        "rank_2": "ChatGPT",
        "rank_3": "Claude",
    },
    {
        "task": "Productivity Assistant",
        "aliases": ["productivity", "task management", "organize work", "personal assistant"],
        "rank_1": "ChatGPT",
        "rank_2": "Notion AI",
        "rank_3": "Claude",
    },
    {
        "task": "Workflow Automation",
        "aliases": ["automation", "automate workflow", "process automation", "integrate apps", "no-code automation"],
        "rank_1": "Zapier AI",
        "rank_2": "Make",
        "rank_3": "n8n",
    },

    # ── AI Agents & Support ───────────────────────────────────────────
    {
        "task": "Customer Support Bot",
        "aliases": ["customer support", "chatbot", "support bot", "help desk bot", "customer service"],
        "rank_1": "Claude",
        "rank_2": "ChatGPT",
        "rank_3": "Gemini",
    },
    {
        "task": "AI Agents",
        "aliases": ["agent", "autonomous agent", "ai assistant", "multi-step agent", "agentic ai"],
        "rank_1": "Claude",
        "rank_2": "ChatGPT",
        "rank_3": "Gemini",
    },
    {
        "task": "Open Source Local Model",
        "aliases": ["open source", "local model", "self-hosted", "on-premise ai", "offline ai", "local llm"],
        "rank_1": "Qwen",
        "rank_2": "DeepSeek",
        "rank_3": "Kim",
    },
]


# ── Fallback / Default ────────────────────────────────────────────────
DEFAULT_RECOMMENDATION: ToolRankingEntry = {
    "task": "General Chat",
    "aliases": [],
    "rank_1": "ChatGPT",
    "rank_2": "Claude",
    "rank_3": "Gemini",
}
