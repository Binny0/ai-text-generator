from flask import Flask, render_template, request, jsonify
from transformers import pipeline
import requests
from datetime import datetime
import warnings
import re
import os

warnings.filterwarnings('ignore')

app = Flask(__name__)

# API KEYS - Get them from:
# OpenAI: https://platform.openai.com/api-keys
# Tavily: https://tavily.com (1000 free searches/month)

# SET YOUR API KEYS HERE:
OPENAI_API_KEY = 'Set your API KEY Here'
TAVILY_API_KEY = 'Set your API KEY Here'

print("🤖 Loading AI models...")

# Sentiment Analysis (for real-time detection)
sentiment_analyzer = pipeline(
    "sentiment-analysis",
    model="cardiffnlp/twitter-roberta-base-sentiment-latest"
)

print("✓ Models ready!")


def universal_sentiment_detection(text):
    """Universal sentiment detection for ANY topic"""
    
    text_lower = text.lower()
    
    # Positive indicators
    positive_indicators = [
        'benefit', 'advantage', 'opportunity', 'solution', 'improve', 'innovation',
        'success', 'growth', 'development', 'advancement', 'progress', 'potential',
        'effective', 'efficient', 'promising', 'breakthrough', 'achievement'
    ]
    
    # Negative indicators
    negative_indicators = [
        'problem', 'issue', 'challenge', 'concern', 'risk', 'threat', 'crisis',
        'failure', 'decline', 'loss', 'damage', 'harm', 'danger', 'difficulty',
        'obstacle', 'barrier', 'limitation', 'weakness', 'drawback'
    ]
    
    # Check for negations
    negation_words = ['no', 'not', 'never', 'without', 'hardly', 'barely', "n't"]
    
    for neg in negation_words:
        for pos in positive_indicators:
            if re.search(f'{neg}\\s+{pos}', text_lower):
                return 'negative', 0.88
        
        for negs in negative_indicators:
            if re.search(f'{neg}\\s+{negs}', text_lower):
                return 'positive', 0.88
    
    # Count indicators
    pos_count = sum(1 for word in positive_indicators if word in text_lower)
    neg_count = sum(1 for word in negative_indicators if word in text_lower)
    
    if pos_count > neg_count:
        return 'positive', 0.85
    elif neg_count > pos_count:
        return 'negative', 0.85
    
    # Use AI model
    try:
        result = sentiment_analyzer(text[:512])[0]
        label = result['label'].lower()
        score = result['score']
        
        if 'pos' in label:
            return 'positive', score
        elif 'neg' in label:
            return 'negative', score
        else:
            return 'neutral', score
    except:
        return 'neutral', 0.70


def search_with_tavily(topic):
    """Search web using Tavily API - Best for AI applications"""
    print(f"🔍 Searching with Tavily API: {topic}")
    
    if not TAVILY_API_KEY or TAVILY_API_KEY.startswith('your-'):
        print("⚠️  Tavily API key not configured, using Wikipedia fallback")
        return get_wikipedia_fallback(topic)
    
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            headers={
                "Content-Type": "application/json"
            },
            json={
                "api_key": TAVILY_API_KEY,
                "query": f"{topic} latest information news 2024 2025",
                "search_depth": "advanced",  # 'basic' or 'advanced'
                "include_answer": True,  # Get AI-generated summary
                "include_raw_content": False,  # Don't need full HTML
                "max_results": 5  # Number of search results
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Combine AI answer + search results
            combined_info = ""
            
            # Add Tavily's AI-generated answer (summary of all results)
            if data.get('answer'):
                combined_info += f"Overview: {data['answer']}\n\n"
            
            # Add individual search results
            results = data.get('results', [])
            sources = []
            
            for item in results:
                combined_info += f"\n{item.get('content', '')}\n"
                
                # Extract clean source domain
                url = item.get('url', '')
                domain = url.split('/')[2] if '/' in url else 'Web Source'
                domain = domain.replace('www.', '')
                
                sources.append({
                    'title': item.get('title', 'Web Article'),
                    'url': url,
                    'source': domain
                })
            
            if combined_info.strip():
                print(f"✓ Tavily returned {len(combined_info)} characters from {len(sources)} sources")
                return combined_info.strip(), sources
        
        print(f"⚠️  Tavily returned status {response.status_code}")
        
    except Exception as e:
        print(f"❌ Tavily error: {e}")
    
    # Fallback to Wikipedia
    return get_wikipedia_fallback(topic)


def get_wikipedia_fallback(topic):
    """Fallback to Wikipedia API"""
    print(f"📚 Using Wikipedia fallback for: {topic}")
    
    try:
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic.replace(' ', '_')}"
        response = requests.get(wiki_url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            extract = data.get('extract', '')
            
            if extract:
                sources = [{
                    'title': data.get('title', topic),
                    'url': data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                    'source': 'Wikipedia'
                }]
                print(f"✓ Got Wikipedia content: {len(extract)} characters")
                return extract, sources
    
    except Exception as e:
        print(f"Wikipedia error: {e}")
    
    # Last resort - minimal fallback
    return (
        f"Information about {topic}. This topic is currently being researched and discussed across various fields.",
        [{
            'title': f'Search results for {topic}',
            'url': f"https://www.google.com/search?q={topic.replace(' ', '+')}",
            'source': 'Web Search'
        }]
    )


def generate_with_openai(topic, sentiment, web_content, word_count_target):
    """Use OpenAI GPT to generate high-quality, sentiment-aligned content"""
    print(f"✍️  Generating with OpenAI GPT-4o-mini...")
    
    if not OPENAI_API_KEY or OPENAI_API_KEY.startswith('your-'):
        print("⚠️  OpenAI API key not configured!")
        return create_fallback_content(topic, sentiment, web_content)
    
    try:
        # Sentiment-specific instructions
        if sentiment == 'positive':
            tone_instruction = """Write in an OPTIMISTIC and ENCOURAGING tone:
- Highlight benefits, opportunities, and positive developments
- Emphasize success stories and achievements
- Focus on potential and promising future prospects
- Use positive language and forward-looking statements"""
        
        elif sentiment == 'negative':
            tone_instruction = """Write in a CRITICAL and CAUTIONARY tone:
- Emphasize challenges, risks, and concerns
- Highlight problems and limitations
- Focus on obstacles and potential failures
- Use skeptical language and warning statements"""
        
        else:
            tone_instruction = """Write in a BALANCED and OBJECTIVE tone:
- Present both opportunities and challenges equally
- Include multiple perspectives
- Acknowledge complexity and nuance
- Use neutral, analytical language"""
        
        system_prompt = f"""You are an expert content writer specializing in research-based essays.

TASK: Write a comprehensive, well-structured essay about the given topic.

REQUIREMENTS:
- Length: Approximately {word_count_target} words
- Structure: Introduction, 3-4 body paragraphs, strong conclusion
- Style: Professional, engaging, flowing prose (NO bullet points or lists)
- Content: Use the provided research as your factual foundation
- Date context: Include current date references (December 2024)
- Tone: {tone_instruction}

IMPORTANT: 
- Base your essay on the provided research
- Include specific facts, statistics, and examples from the research
- Make it informative and authoritative
- Write in complete, flowing paragraphs"""

        user_prompt = f"""Topic: {topic}

Research Material:
{web_content[:4000]}

Write a comprehensive essay about this topic following the specified tone and requirements."""

        # Call OpenAI API
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",  # Fast and affordable ($0.150/$0.600 per 1M tokens)
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,  # Balance between creativity and consistency
                "max_tokens": 2000,  # Allow longer responses
                "top_p": 1.0
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            generated_text = data['choices'][0]['message']['content'].strip()
            
            # Add metadata footer
            current_date = datetime.now().strftime("%B %Y")
            generated_text += f"\n\n---\n*AI-generated content based on current web research as of {current_date}*"
            
            word_count = len(generated_text.split())
            print(f"✓ OpenAI generated {word_count} words")
            return generated_text
        
        else:
            print(f"❌ OpenAI API error: {response.status_code}")
            error_detail = response.json() if response.content else {}
            print(f"Error details: {error_detail}")
            return create_fallback_content(topic, sentiment, web_content)
            
    except Exception as e:
        print(f"❌ OpenAI generation error: {e}")
        import traceback
        traceback.print_exc()
        return create_fallback_content(topic, sentiment, web_content)


def create_fallback_content(topic, sentiment, web_content):
    """Fallback content generator if OpenAI fails"""
    print("⚠️  Using fallback content generator")
    
    current_date = datetime.now().strftime("%B %Y")
    
    # Extract sentences from web content
    sentences = re.split(r'[.!?]+', web_content)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 40][:8]
    
    # Build content with sentiment
    paragraphs = []
    
    # Introduction
    if sentiment == 'positive':
        intro = f"Examining {topic} as of {current_date} reveals significant progress and promising developments. "
    elif sentiment == 'negative':
        intro = f"Analyzing {topic} as of {current_date} uncovers substantial challenges and concerns. "
    else:
        intro = f"Understanding {topic} as of {current_date} requires examining multiple perspectives. "
    
    if sentences:
        intro += sentences[0] + "."
    paragraphs.append(intro)
    
    # Body paragraphs
    for i in range(1, min(4, len(sentences))):
        para = sentences[i] + ". "
        
        if sentiment == 'positive':
            para += "This development demonstrates meaningful progress with practical implications."
        elif sentiment == 'negative':
            para += "This situation raises important questions about viability and potential risks."
        else:
            para += "The outcomes depend significantly on implementation context and specific conditions."
        
        paragraphs.append(para)
    
    # Conclusion
    if sentiment == 'positive':
        conclusion = f"The trajectory for {topic} indicates continued growth and expanding opportunities. Current evidence supports optimism about future developments."
    elif sentiment == 'negative':
        conclusion = f"The challenges facing {topic} require immediate attention and careful consideration. Current indicators suggest caution moving forward."
    else:
        conclusion = f"The future of {topic} depends on balancing opportunities with challenges. Success requires realistic expectations and strategic implementation."
    
    paragraphs.append(conclusion)
    
    content = "\n\n".join(paragraphs)
    content += f"\n\n---\n*Content based on available research as of {current_date}*"
    
    return content


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/analyze-realtime', methods=['POST'])
def analyze_realtime():
    """Real-time sentiment detection"""
    try:
        data = request.json
        text = data.get('text', '').strip()
        
        if not text or len(text) < 3:
            return jsonify({
                'sentiment': 'neutral',
                'confidence': 0,
                'message': 'Type something...'
            })
        
        sentiment, confidence = universal_sentiment_detection(text)
        
        return jsonify({
            'sentiment': sentiment,
            'confidence': round(confidence * 100, 2),
            'message': f'{sentiment.upper()} detected'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/generate', methods=['POST'])
def generate():
    """Main generation endpoint"""
    try:
        data = request.json
        topic = data.get('prompt', '').strip()
        force_sentiment = data.get('sentiment', 'auto')
        min_length = int(data.get('min_length', 300))
        max_length = int(data.get('max_length', 600))
        
        if not topic or len(topic) < 3:
            return jsonify({'error': 'Please provide a topic (minimum 3 characters)'}), 400
        
        print(f"\n{'='*70}")
        print(f"📝 Topic: {topic}")
        print(f"📅 Date: {datetime.now().strftime('%B %d, %Y %H:%M:%S')}")
        
        # Step 1: Detect sentiment
        if force_sentiment == 'auto':
            sentiment, confidence = universal_sentiment_detection(topic)
            print(f"📊 Sentiment: {sentiment.upper()} (confidence: {confidence:.0%})")
        else:
            sentiment = force_sentiment
            confidence = 1.0
            print(f"👤 Sentiment: {sentiment.upper()} (user selected)")
        
        # Step 2: Search web with Tavily
        web_content, sources = search_with_tavily(topic)
        print(f"🌐 Sources: {len(sources)} found")
        
        # Step 3: Generate with OpenAI
        word_target = (min_length + max_length) // 2
        content = generate_with_openai(topic, sentiment, web_content, word_target)
        
        word_count = len(content.split())
        char_count = len(content)
        
        print(f"✅ Generated: {word_count} words, {char_count} characters")
        print(f"{'='*70}\n")
        
        return jsonify({
            'success': True,
            'topic': topic,
            'sentiment': sentiment,
            'confidence': round(confidence * 100, 2),
            'content': content,
            'sources': sources,
            'word_count': word_count,
            'char_count': char_count
        })
        
    except Exception as e:
        print(f"❌ Generation error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Generation failed: {str(e)}'}), 500


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'openai_configured': bool(OPENAI_API_KEY and not OPENAI_API_KEY.startswith('your-')),
        'tavily_configured': bool(TAVILY_API_KEY and not TAVILY_API_KEY.startswith('your-')),
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    print("\n" + "="*70)
    print("🎓 AI Text Generator - Tavily + OpenAI Edition")
    print("="*70)
    print("Features:")
    print("  ✓ Tavily API for real-time web search")
    print("  ✓ OpenAI GPT-4o-mini for text generation")
    print("  ✓ Sentiment-aware content generation")
    print("  ✓ Wikipedia fallback for reliability")
    print(f"  ✓ Current as of {datetime.now().strftime('%B %Y')}")
    print("="*70)
    
    # Check API keys
    apis_configured = []
    apis_missing = []
    
    if OPENAI_API_KEY != 'your-openai-key-here':
        print("✅ OpenAI API key: Configured")
        apis_configured.append('OpenAI')
    else:
        print("⚠️  OpenAI API key: NOT SET")
        print("   Get it from: https://platform.openai.com/api-keys")
        apis_missing.append('OpenAI')
    
    if TAVILY_API_KEY != 'your-tavily-key-here':
        print("✅ Tavily API key: Configured")
        apis_configured.append('Tavily')
    else:
        print("⚠️  Tavily API key: NOT SET")
        print("   Get it from: https://tavily.com (1000 free/month)")
        apis_missing.append('Tavily')
    
    print("="*70)
    
    if apis_missing:
        print("\n📝 To set API keys:")
        print("   export OPENAI_API_KEY='sk-...'")
        print("   export TAVILY_API_KEY='tvly-...'")
        print("\n   Or edit lines 16-17 in app.py directly\n")
    
    print("="*70)
    print("🌐 Starting server: http://localhost:8080")
    print("="*70 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=8080)
