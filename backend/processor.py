"""
processor.py
------------
All heavy-lifting logic: YouTube transcript fetching and AI analysis (Gemini + Groq fallback).
Kept separate so main.py stays a thin routing layer.
"""

import re
import time
from typing import Tuple, Optional

# ── YouTube helpers ──────────────────────────────────────────────────────────

def get_video_id(url: str) -> Optional[str]:
    """Extract the 11-char video ID from any standard YouTube URL."""
    pattern = r"(?:v=|youtu\.be\/|\/embed\/|\/shorts\/)([0-9A-Za-z_-]{11})"
    match = re.search(pattern, url)
    return match.group(1) if match else None


def fetch_transcript(video_id: str, language: str = "en") -> Tuple[Optional[str], Optional[str]]:
    """
    Return (transcript_text, error_message).
    Supports both the legacy and the new youtube_transcript_api APIs.
    Language parameter: 'en' (English)
    Uses proxy to bypass YouTube IP restrictions on cloud platforms.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.proxies import GenericProxyConfig
        import os
        
        # Configure proxy to bypass YouTube IP blocks on cloud platforms
        proxy_host = os.getenv('PROXY_HOST')
        proxy_port = os.getenv('PROXY_PORT')
        proxy_user = os.getenv('PROXY_USER')
        proxy_pass = os.getenv('PROXY_PASS')
        
        if proxy_host and proxy_port:
            print(f"🔧 Configuring proxy: {proxy_host}:{proxy_port}")
            # Build proxy URL: http://user:pass@host:port
            proxy_url = f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}" if proxy_user else f"http://{proxy_host}:{proxy_port}"
            
            # Create proxy config
            proxy_config = GenericProxyConfig(proxy_url=proxy_url)
            api = YouTubeTranscriptApi(proxy_config=proxy_config)
            print("✅ Proxy configured successfully")
        else:
            print("⚠️  No proxy configured, using direct connection")
            api = YouTubeTranscriptApi()

        # ── new API (>=0.6): instantiate, then call .list() ──────────────────
        if not hasattr(YouTubeTranscriptApi, "get_transcript"):
            transcript_list = api.list(video_id)
            
            # Try to get the requested language, fall back to available options
            try:
                chosen = transcript_list.find_transcript([language])
            except Exception:
                # If requested language not available, try English
                if language != "en":
                    try:
                        chosen = transcript_list.find_transcript(["en"])
                    except Exception:
                        # Fall back to first available
                        chosen = next(iter(transcript_list))
                else:
                    chosen = next(iter(transcript_list))
            snippets = chosen.fetch()
        else:
            # ── legacy API (< 0.6): class-level static method ────────────────
            try:
                snippets = YouTubeTranscriptApi.get_transcript(video_id, languages=[language])
            except Exception:
                if language != "en":
                    snippets = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
                else:
                    raise

        # Normalise: both dict-style and object-style snippets
        def snippet_text(s):
            if isinstance(s, dict):
                return s.get("text", "")
            return getattr(s, "text", "")

        full_text = " ".join(snippet_text(s) for s in snippets).strip()
        if not full_text:
            return None, "Transcript is empty for this video."

        return full_text, None

    except Exception as exc:
        return None, f"Could not fetch transcript: {exc}"


def get_available_languages(video_id: str) -> list:
    """
    Get list of available languages for a video.
    Returns list of language codes (e.g., ['en', 'hi', 'te'])
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        if not hasattr(YouTubeTranscriptApi, "get_transcript"):
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)
            languages = []
            for transcript in transcript_list:
                lang_code = getattr(transcript, 'language_code', None)
                if lang_code:
                    languages.append(lang_code)
            return languages
        else:
            # Legacy API
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            languages = []
            for transcript in transcript_list:
                languages.append(transcript.language_code)
            return languages
    except Exception:
        return ["en"]  # Default to English if can't fetch


# ── Gemini helpers ───────────────────────────────────────────────────────────

def _pick_model(client) -> str:
    """Return the name of the first model that supports generateContent."""
    # Prioritize models that tend to be more available
    preferred_models = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]
    
    try:
        all_models = list(client.models.list())
        
        # First try preferred models in order
        for preferred in preferred_models:
            for m in all_models:
                if preferred in m.name:
                    actions = getattr(m, "supported_actions", None) or []
                    if "generateContent" in actions:
                        print(f"Using model: {m.name}")
                        return m.name
        
        # Fallback to any available model
        for m in all_models:
            actions = getattr(m, "supported_actions", None) or []
            if "generateContent" in actions:
                print(f"Using fallback model: {m.name}")
                return m.name
        
        raise RuntimeError("No generateContent-compatible Gemini model found.")
    except Exception as e:
        print(f"Error picking model: {e}")
        # Default to a commonly available model
        return "gemini-2.0-flash"


# Base prompt template - will be customized based on transcript length
BASE_PROMPT_TEMPLATE = """
You are an expert educational assistant and translator.

🚨🚨🚨 LANGUAGE INSTRUCTION - READ CAREFULLY 🚨🚨🚨
The transcript below is in English.
You MUST analyze the content and then TRANSLATE your entire response to {language_name}.

YOUR COMPLETE RESPONSE MUST BE WRITTEN IN {language_name} LANGUAGE.
- Summary: Write in {language_name}
- Quiz questions: Write in {language_name}
- Key terms: Write in {language_name}
- Timestamps: Write in {language_name}
- Keywords: Write in {language_name}

DO NOT write in English. Translate everything to {language_name}.
🚨🚨🚨 END OF LANGUAGE INSTRUCTION 🚨🚨🚨

⚠️ CRITICAL REQUIREMENTS - YOU MUST FOLLOW THESE EXACTLY:
- You MUST provide EXACTLY {num_summary_points} summary bullet points (count them!)
- You MUST create EXACTLY {num_quiz_questions} quiz questions (count them!)
- You MUST list EXACTLY {num_key_terms} key terms (count them!)
- You MUST extract EXACTLY {num_timestamps} timestamps (count them!)
- DO NOT provide fewer items than requested. This is critical!

## Summary
{summary_instructions}

## Quiz
{quiz_instructions}

## Key Terms
{key_terms_instructions}

## Timestamps
{timestamp_instructions}

## Keywords
{keywords_instructions}

---
TRANSCRIPT (in English - analyze it but respond in {language_name}):
{transcript}
""".strip()


def _generate_dynamic_prompt(original_transcript_length: int, optimized_transcript: str, language_name: str) -> str:
    """
    Generate a prompt that scales based on ORIGINAL transcript length.
    Longer transcripts get more comprehensive analysis.
    """
    # Estimate video duration from ORIGINAL transcript length (not the optimized one)
    # Average speaking rate: ~150 words per minute
    # We estimate original word count from the length ratio
    estimated_original_words = original_transcript_length / 5  # Approx chars per word
    estimated_minutes = estimated_original_words / 150
    
    # Determine content scale based on estimated duration
    # OPTIMIZED FOR EXAM PREPARATION - Quality over quantity
    if estimated_minutes <= 10:  # Short video (< 10 min)
        num_summary_points = 5
        num_quiz_questions = 5
        num_key_terms = 5
        num_timestamps = 5
        num_keywords = 8
    elif estimated_minutes <= 30:  # Medium video (10-30 min)
        num_summary_points = 7
        num_quiz_questions = 7
        num_key_terms = 7
        num_timestamps = 7
        num_keywords = 12
    elif estimated_minutes <= 60:  # Long video (30-60 min)
        num_summary_points = 7
        num_quiz_questions = 8
        num_key_terms = 8
        num_timestamps = 8
        num_keywords = 15
    elif estimated_minutes <= 180:  # Very long video (1-3 hours)
        num_summary_points = 7
        num_quiz_questions = 10
        num_key_terms = 10
        num_timestamps = 10
        num_keywords = 20
    else:  # Extremely long video (3+ hours)
        num_summary_points = 7
        num_quiz_questions = 12
        num_key_terms = 12
        num_timestamps = 12
        num_keywords = 25
    
    # Generate summary instructions - EXAM-FOCUSED comprehensive notes
    summary_instructions = f"""CRITICAL: Provide EXACTLY {num_summary_points} comprehensive bullet points in {language_name} that serve as complete exam notes.

Each bullet point must be detailed (3-4 sentences) and cover:
- Key concepts and definitions
- Important technical details
- Practical applications and examples
- Critical relationships between concepts

These notes should be comprehensive enough that a student could use them to prepare for an exam without watching the full video.

Write exactly {num_summary_points} detailed bullet points in {language_name} covering the MOST IMPORTANT topics from the ENTIRE transcript:
• Point 1: [Major concept with details in {language_name}]
• Point 2: [Major concept with details in {language_name}]
• Point 3: [Major concept with details in {language_name}]
• Point 4: [Major concept with details in {language_name}]
• Point 5: [Major concept with details in {language_name}]"""
    
    # Add more examples for 7 points
    if num_summary_points >= 7:
        summary_instructions += """
• Point 6: [Major concept with details]
• Point 7: [Major concept with details]"""
    
    summary_instructions += f"""

CRITICAL REQUIREMENTS:
- Each point must be 3-4 sentences long with specific details
- Cover the MOST CRUCIAL concepts that would appear on an exam
- Include technical terms, definitions, and practical examples
- Make each point comprehensive and self-contained
- A student should be able to study from these notes alone
- You MUST write exactly {num_summary_points} points - no more, no less"""
    
    # Generate quiz instructions
    quiz_questions_text = "\n\n".join([
        f"""Q{i}. [Question in {language_name}]
A) [Option]
B) [Option]
C) [Option]
D) [Option]
**Answer:** [Correct letter and text]"""
        for i in range(1, num_quiz_questions + 1)
    ])
    quiz_instructions = f"Create exactly {num_quiz_questions} multiple-choice questions. Format:\n\n{quiz_questions_text}"
    
    # Generate key terms instructions
    key_terms_instructions = f"List exactly {num_key_terms} important terms with one-sentence definitions:"
    key_terms_examples = "\n".join([f"- **Term {i}**: Definition" for i in range(1, num_key_terms + 1)])
    key_terms_instructions = f"{key_terms_instructions}\n{key_terms_examples}"
    
    # Generate timestamp instructions
    timestamp_instructions = f"Extract {num_timestamps} key moments spread across the ENTIRE video. Format:"
    timestamp_examples = "\n".join([
        f"00:00 - [Topic in {language_name}]",
        f"01:15 - [Topic in {language_name}]",
        f"02:45 - [Topic in {language_name}]"
    ])
    if estimated_minutes > 60:
        timestamp_examples += "\n...\n"
        hours = int(estimated_minutes // 60)
        mins = int(estimated_minutes % 60)
        timestamp_examples += f"{hours:02d}:{mins:02d} - [Topic in {language_name}]"
    timestamp_instructions = f"{timestamp_instructions}\n{timestamp_examples}"
    
    # Generate keywords instructions
    keywords_instructions = f"List {num_keywords}-{num_keywords+2} keywords as comma-separated values:"
    keywords_example = ", ".join([f"keyword{i}" for i in range(1, min(num_keywords + 1, 10))])
    if num_keywords > 9:
        keywords_example += ", ..."
    keywords_instructions = f"{keywords_instructions}\n{keywords_example}"
    
    # Build the complete prompt
    prompt = BASE_PROMPT_TEMPLATE.format(
        language_name=language_name,
        num_summary_points=num_summary_points,
        num_quiz_questions=num_quiz_questions,
        num_key_terms=num_key_terms,
        num_timestamps=num_timestamps,
        summary_instructions=summary_instructions,
        quiz_instructions=quiz_instructions,
        key_terms_instructions=key_terms_instructions,
        timestamp_instructions=timestamp_instructions,
        keywords_instructions=keywords_instructions,
        transcript=optimized_transcript
    )
    
    print(f"\n📊 Transcript Analysis:")
    print(f"   Original length: {original_transcript_length:,} chars")
    print(f"   Optimized length: {len(optimized_transcript):,} chars")
    print(f"   Estimated duration: {estimated_minutes:.0f} minutes ({estimated_minutes/60:.1f} hours)")
    print(f"   Summary points: {num_summary_points}")
    print(f"   Quiz questions: {num_quiz_questions}")
    print(f"   Key terms: {num_key_terms}")
    print(f"   Timestamps: {num_timestamps}")
    print(f"   Keywords: {num_keywords}-{num_keywords+2}")
    
    return prompt


def _optimize_transcript(transcript: str, max_chars: int = 3000) -> str:
    """
    Optimize transcript to reduce token usage while keeping key information.
    Uses intelligent sampling to get the most important parts.
    """
    # If transcript is already short, use it as-is
    if len(transcript) <= max_chars:
        return transcript
    
    # Split into sentences
    import re
    sentences = re.split(r'(?<=[.!?])\s+', transcript)
    
    # Strategy 1: Take first 20% and last 20% (intro + conclusion are most important)
    third = len(sentences) // 3
    selected = sentences[:third] + sentences[-third:]
    
    # Strategy 2: Sample from middle if we still have room
    if len(' '.join(selected)) < max_chars:
        middle_start = third
        middle_end = len(sentences) - third
        middle_sample = sentences[middle_start:middle_end:max(1, (middle_end - middle_start) // 10)]
        selected = sentences[:third] + middle_sample + sentences[-third:]
    
    # Join and truncate if still too long
    result = ' '.join(selected)
    if len(result) > max_chars:
        result = result[:max_chars]
        # Cut at last complete sentence
        last_period = result.rfind('.')
        if last_period > max_chars * 0.7:
            result = result[:last_period + 1]
    
    return result


def analyze_with_gemini(transcript: str, api_keys: list, groq_api_keys: list = [], language: str = "en") -> Tuple[Optional[dict], Optional[str]]:
    """
    Call the Gemini API and return (result_dict, error_message).
    Falls back to Groq API if Gemini is unavailable.
    Supports multiple API keys for automatic failover.
    result_dict keys: analysis, model_used, word_count
    """
    if not api_keys and not groq_api_keys:
        return None, "No API keys configured. Please add GEMINI_API_KEY or GROQ_API_KEY to your .env file."

    # Map language code to language name for the prompt
    language_names = {
        "en": "English"
    }
    language_name = language_names.get(language, "English")
    
    # Store original transcript length for dynamic scaling
    original_transcript_length = len(transcript)
    
    # DYNAMIC OPTIMIZATION: Scale transcript limit based on original length
    # Reduced to fit within Groq's 12,000 TPM limit
    if original_transcript_length > 200000:  # Very long (>200K chars, e.g., 12+ hours)
        max_chars = 10000  # Use 10K for very long videos
    elif original_transcript_length > 100000:  # Long (100K-200K)
        max_chars = 8000   # Use 8K for long videos
    elif original_transcript_length > 50000:  # Medium-long (50K-100K)
        max_chars = 7000   # Use 7K for medium-long
    elif original_transcript_length > 20000:  # Short-medium (20K-50K)
        max_chars = 6000   # Use 6K for short-medium
    else:
        max_chars = 4000   # Default 4K for shorter videos
    
    optimized_transcript = _optimize_transcript(transcript, max_chars=max_chars)
    print(f"Transcript optimized: {len(transcript)} -> {len(optimized_transcript)} chars ({len(optimized_transcript)/len(transcript)*100:.1f}%)")
    
    # Generate dynamic prompt based on ORIGINAL transcript length
    localized_prompt = _generate_dynamic_prompt(original_transcript_length, optimized_transcript, language_name)
    
    # Extract expected summary points from prompt for validation
    import re
    expected_match = re.search(r'EXACTLY (\d+) summary bullet points', localized_prompt)
    expected_summary_points = int(expected_match.group(1)) if expected_match else 5

    # Try Groq FIRST (more reliable, better quotas)
    if groq_api_keys:
        print(f"\n🔄 Trying {len(groq_api_keys)} Groq API key(s)...")
        for key_index, groq_key in enumerate(groq_api_keys, 1):
            print(f"\n[Groq Key {key_index}/{len(groq_api_keys)}] Attempting...")
            result, error = _try_groq_analysis(optimized_transcript, groq_key, localized_prompt, key_index, expected_summary_points)
            if result:
                print(f"✅ Success with Groq key #{key_index}!")
                return result, None
            print(f"❌ Groq key #{key_index} failed: {error}")
    
    # Fallback to Gemini API keys
    if api_keys:
        print(f"\n🔄 Trying {len(api_keys)} Gemini API key(s)...")
        for key_index, api_key in enumerate(api_keys, 1):
            print(f"\n[Gemini Key {key_index}/{len(api_keys)}] Attempting...")
            result, error = _try_gemini_analysis(optimized_transcript, api_key, localized_prompt, key_index)
            if result:
                print(f"✅ Success with Gemini key #{key_index}!")
                return result, None
            print(f"❌ Gemini key #{key_index} failed: {error}")
    
    # Last resort: demo mode
    print("\n⚠️ WARNING: All AI services exhausted, providing demo data")
    demo_result = _generate_demo_data(transcript)
    return demo_result, None


def _try_gemini_analysis(transcript: str, api_key: str, prompt: str, key_index: int = 1) -> Tuple[Optional[dict], Optional[str]]:
    """Try to analyze with Gemini API."""
    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=api_key)
        
        # Try multiple models in case one is down
        models_to_try = [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.5-flash"
        ]

        last_error = None
        
        for model_name in models_to_try:
            print(f"  Trying Gemini key #{key_index}, model: {model_name}")
            
            try:
                response = client.models.generate_content(model=model_name, contents=prompt)
                analysis_text = response.text.strip()

                print(f"  ✓ Successfully used Gemini key #{key_index}, model: {model_name}")
                return {
                    "status": "success",
                    "model_used": f"Gemini key #{key_index}: {model_name}",
                    "word_count": len(transcript.split()),
                    "analysis": analysis_text,
                    "sections": _parse_sections(analysis_text),
                }, None
                
            except Exception as exc:
                last_error = exc
                error_str = str(exc).lower()
                
                # Check for quota errors (429) - fail fast to try next key
                if "429" in error_str or "resource_exhausted" in error_str or "quota" in error_str:
                    print(f"    ✗ Quota exceeded for key #{key_index}. Moving to next key...")
                    return None, f"Gemini key #{key_index} quota exceeded: {exc}"
                
                # Check for 503 errors
                if "503" in error_str or "unavailable" in error_str:
                    print(f"    ✗ {model_name} unavailable. Trying next model...")
                else:
                    print(f"    ✗ {model_name} error: {exc}")
        
        return None, f"Gemini key #{key_index} unavailable: {last_error}"

    except Exception as exc:
        return None, f"Gemini key #{key_index} error: {exc}"


def _try_groq_analysis(transcript: str, api_key: str, prompt: str, key_index: int = 1, expected_summary_points: int = 5) -> Tuple[Optional[dict], Optional[str]]:
    """Try to analyze with Groq API (fallback when Gemini is down)."""
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        
        # Groq models that are fast and reliable (updated 2024)
        # Prioritize models that follow instructions better
        models_to_try = [
            "llama-3.3-70b-versatile",  # Primary model - active
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant"
        ]

        last_error = None
        
        for model_name in models_to_try:
            print(f"  Trying Groq key #{key_index}, model: {model_name}")
            
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are an expert educational assistant. Follow ALL instructions carefully and provide EXACTLY the requested number of items."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=6000  # Increased from 4000 to allow comprehensive responses
                )
                
                analysis_text = response.choices[0].message.content.strip()

                print(f"  ✓ Successfully used Groq key #{key_index}, model: {model_name}")
                
                # Parse and validate sections
                sections = _parse_sections(analysis_text)
                summary_lines = [l for l in sections.get('summary', '').split('\n') if l.strip().startswith('•')]
                
                if len(summary_lines) >= expected_summary_points:
                    print(f"  ✅ AI generated {len(summary_lines)} comprehensive summary points")
                else:
                    print(f"  ⚠️ AI generated {len(summary_lines)} points (expected {expected_summary_points})")
                
                return {
                    "status": "success",
                    "model_used": f"Groq key #{key_index}: {model_name}",
                    "word_count": len(transcript.split()),
                    "analysis": analysis_text,
                    "sections": sections,
                }, None
                
            except Exception as exc:
                last_error = exc
                error_str = str(exc).lower()
                
                # Check for rate limit errors - fail fast to try next key
                if "rate_limit" in error_str or "429" in error_str:
                    print(f"    ✗ Rate limited on key #{key_index}. Moving to next key...")
                    return None, f"Groq key #{key_index} rate limited: {exc}"
                
                # For other errors, try next model
                print(f"    ✗ Model {model_name} error: {exc}")
        
        return None, f"Groq key #{key_index} unavailable: {last_error}"

    except ImportError:
        return None, "Groq library not installed. Run: pip install groq"
    except Exception as exc:
        return None, f"Groq key #{key_index} error: {exc}"


def _generate_demo_data(transcript: str) -> dict:
    """
    Generate demo/sample data when API is unavailable.
    This allows the app to remain functional for testing.
    Scales based on transcript length.
    """
    word_count = len(transcript.split())
    estimated_minutes = word_count / 150
    
    # Determine scale based on estimated duration
    if estimated_minutes <= 10:
        num_summary = 5
        num_quiz = 5
        num_terms = 5
        num_timestamps = 5
        num_keywords = 8
    elif estimated_minutes <= 30:
        num_summary = 8
        num_quiz = 7
        num_terms = 8
        num_timestamps = 8
        num_keywords = 12
    elif estimated_minutes <= 60:
        num_summary = 10
        num_quiz = 8
        num_terms = 10
        num_timestamps = 10
        num_keywords = 15
    elif estimated_minutes <= 180:
        num_summary = 12
        num_quiz = 10
        num_terms = 12
        num_timestamps = 15
        num_keywords = 20
    else:
        num_summary = 15
        num_quiz = 12
        num_terms = 15
        num_timestamps = 20
        num_keywords = 25
    
    # Extract keywords from the transcript
    words = transcript.lower().split()
    common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'but', 'this', 'that', 'it', 'with', 'as', 'by', 'from', 'be', 'have', 'has', 'had', 'not', 'you', 'your', 'we', 'our', 'they', 'their', 'can', 'will', 'would', 'should', 'may', 'might', 'must', 'shall'}
    unique_words = list(set([w for w in words if w not in common_words and len(w) > 4]))
    keywords = unique_words[:num_keywords] if len(unique_words) >= num_keywords else unique_words
    
    # Generate summary points
    summary_points = [
        "This lecture covers fundamental concepts and advanced techniques in the subject matter, providing students with a comprehensive understanding of key principles.",
        "The instructor discusses important theoretical frameworks and their practical applications in real-world scenarios and modern contexts.",
        "Several case studies and examples are presented to illustrate complex ideas and help students grasp difficult concepts more easily.",
        "Key methodologies and approaches are compared and contrasted, highlighting their respective strengths, weaknesses, and appropriate use cases.",
        "The session includes interactive discussions about current trends, emerging technologies, and future directions in the field.",
        "Important takeaways and best practices are summarized to help students apply what they've learned in their own work and projects.",
        "The lecture emphasizes critical thinking and problem-solving skills through practical exercises and real-world applications.",
        "Students are encouraged to engage with the material through questions, discussions, and collaborative learning activities.",
        "Advanced topics build upon foundational knowledge to create a comprehensive learning experience.",
        "The instructor provides valuable insights into industry standards and professional best practices.",
        "Historical context is provided to help students understand the evolution of current methodologies.",
        "Practical demonstrations illustrate how theoretical concepts are applied in professional settings.",
        "The lecture addresses common misconceptions and provides clarification on complex topics.",
        "Resources and references are recommended for further study and deeper exploration of key concepts.",
        "The session concludes with a comprehensive review of main points and their practical implications."
    ]
    
    summary_text = "\n".join([f"• {point}" for point in summary_points[:num_summary]])
    
    # Generate quiz questions
    quiz_questions = [
        ("What is the primary focus of this lecture?", "B) Theoretical frameworks and practical applications"),
        ("Which method is used to illustrate complex concepts?", "B) Case studies and real-world examples"),
        ("What is emphasized for student learning?", "B) Application of concepts to real projects"),
        ("What approach is used to compare different methodologies?", "B) Highlighting strengths and weaknesses"),
        ("What type of discussions are included in the session?", "B) Current trends and emerging technologies"),
        ("What is provided to help students with their own projects?", "B) Important takeaways and best practices"),
        ("How are difficult concepts made easier to understand?", "B) Through examples and case studies"),
        ("What is the ultimate goal of this lecture?", "B) To help students apply learning in practical work"),
        ("What skills does the lecture emphasize?", "B) Critical thinking and problem-solving"),
        ("How does the instructor engage students?", "B) Through questions and collaborative activities"),
        ("What context is provided for the material?", "B) Historical evolution of methodologies"),
        ("How are concepts demonstrated?", "B) Through practical demonstrations")
    ]
    
    quiz_text = ""
    for i in range(min(num_quiz, len(quiz_questions))):
        question, answer = quiz_questions[i]
        # Extract the letter from answer (e.g., "B) To help students..." -> "B")
        answer_letter = answer.split(")")[0].strip()
        # Extract the text after the letter (e.g., "B) To help..." -> "To help...")
        answer_text = ")".join(answer.split(")")[1:]).strip()
        
        quiz_text += f"""Q{i+1}. {question}
A) Incorrect option
B) {answer_text}
C) Incorrect option
D) Incorrect option
**Answer:** {answer_letter})

"""
    
    # Generate key terms
    key_terms_list = [
        ("Framework", "A structured approach or methodology used to organize concepts and guide implementation."),
        ("Methodology", "A system of methods and principles used in a particular discipline."),
        ("Case Study", "A detailed analysis of a specific example used to illustrate theoretical concepts."),
        ("Application", "The practical implementation of theoretical knowledge to solve real-world problems."),
        ("Best Practice", "A proven method that has consistently shown superior results."),
        ("Concept", "An abstract idea or general notion that forms the basis of understanding."),
        ("Theory", "A system of ideas intended to explain something based on general principles."),
        ("Analysis", "Detailed examination of the elements or structure of something."),
        ("Implementation", "The process of putting a decision or plan into effect."),
        ("Evaluation", "The making of a judgment about the amount or value of something."),
        ("Integration", "The process of combining things to work together as a whole."),
        ("Optimization", "The action of making the best or most effective use of a situation."),
        ("Strategy", "A plan of action designed to achieve a long-term aim."),
        ("Assessment", "The evaluation or estimation of the nature or ability of something."),
        ("Synthesis", "The combination of ideas to form a theory or system.")
    ]
    
    key_terms_text = "\n".join([f"- **{term}**: {definition}" for term, definition in key_terms_list[:num_terms]])
    
    # Generate timestamps
    timestamps_text = ""
    for i in range(num_timestamps):
        if estimated_minutes <= 60:
            # For shorter videos, spread across minutes
            minute = int((estimated_minutes * i) / num_timestamps)
            timestamp = f"{minute:02d}:00"
        else:
            # For longer videos, spread across hours and minutes
            total_minutes = int((estimated_minutes * i) / num_timestamps)
            hours = total_minutes // 60
            mins = total_minutes % 60
            timestamp = f"{hours:02d}:{mins:02d}"
        
        timestamps_text += f"{timestamp} - [Topic {i+1} covered in the lecture]\n"
    
    # Generate keywords
    keywords_text = ", ".join(keywords) if keywords else "concept, framework, application, methodology, analysis"
    
    demo_analysis = f"""## Summary
{summary_text}

## Quiz
{quiz_text.strip()}

## Key Terms
{key_terms_text}

## Timestamps
{timestamps_text.strip()}

## Keywords
{keywords_text}
"""
    
    return {
        "status": "success",
        "model_used": "demo-mode (AI API unavailable)",
        "word_count": word_count,
        "analysis": demo_analysis,
        "sections": _parse_sections(demo_analysis),
    }


def _parse_sections(text: str) -> dict:
    """
    Split the markdown response into {summary, quiz, key_terms, timestamps, keywords} for easy
    front-end consumption.
    """
    sections = {"summary": "", "quiz": "", "key_terms": "", "timestamps": "", "keywords": ""}
    current = None
    buffer = []

    for line in text.splitlines():
        stripped = line.strip()
        # English headings
        if stripped.startswith("## Summary"):
            if current:
                sections[current] = "\n".join(buffer).strip()
            current = "summary"
            buffer = []
        elif stripped.startswith("## Quiz"):
            if current:
                sections[current] = "\n".join(buffer).strip()
            current = "quiz"
            buffer = []
        elif stripped.startswith("## Key Terms"):
            if current:
                sections[current] = "\n".join(buffer).strip()
            current = "key_terms"
            buffer = []
        elif stripped.startswith("## Timestamps"):
            if current:
                sections[current] = "\n".join(buffer).strip()
            current = "timestamps"
            buffer = []
        elif stripped.startswith("## Keywords"):
            if current:
                sections[current] = "\n".join(buffer).strip()
            current = "keywords"
            buffer = []
        elif current:
            buffer.append(line)

    if current and buffer:
        sections[current] = "\n".join(buffer).strip()

    return sections
