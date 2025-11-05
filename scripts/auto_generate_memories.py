"""
Auto-generate bot memories from persona profiles.

This script analyzes existing bots and creates default memories based on their
persona_profile, persona_hint, and emotion_profile.

Usage:
    python scripts/auto_generate_memories.py [--dry-run]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from database import get_db, Bot, BotMemory

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def parse_persona_to_memories(bot: Bot) -> List[Dict[str, Any]]:
    """
    Parse bot's persona_profile, persona_hint, and emotion_profile to generate memories.

    Returns list of memory dicts with keys: memory_type, content, relevance_score
    """
    memories = []

    # Parse persona_profile
    persona = bot.persona_profile or {}

    # 1. RISK PROFILE → Preference
    risk = persona.get('risk_profile', '')
    if risk and isinstance(risk, str):
        risk_map = {
            'conservative': 'Yatırımlarımda çok temkinliyim, güvenli limanları tercih ederim.',
            'moderate': 'Dengeli bir yatırımcıyım, risk ve getiri arasında denge kurarım.',
            'aggressive': 'Yüksek risk alırım, büyük kazançlar için cesur kararlar veririm.'
        }
        content = risk_map.get(risk, f'{risk.capitalize()} risk profiline sahibim.')
        memories.append({
            'memory_type': 'preference',
            'content': content,
            'relevance_score': 0.9
        })

    # 2. WATCHLIST → Personal Fact
    watchlist = persona.get('watchlist', [])
    if watchlist and len(watchlist) > 0:
        symbols = ', '.join(watchlist[:3])  # İlk 3 sembol
        memories.append({
            'memory_type': 'personal_fact',
            'content': f'Sürekli takip ettiğim piyasalar: {symbols}',
            'relevance_score': 0.85
        })

    # 3. TONE → Personal Fact
    tone = persona.get('tone', '')
    if tone and isinstance(tone, str):
        tone_map = {
            'optimistic': 'Genel olarak iyimser biriyim, piyasalarda fırsatlar görürüm.',
            'pessimistic': 'Temkinli ve gerçekçi biriyim, riskleri önceden görmeye çalışırım.',
            'neutral': 'Tarafsız ve objektif yaklaşırım, duygularımı kontrol ederim.',
            'analytical': 'Analitik düşünürüm, her kararımı verilere dayanarak alırım.'
        }
        content = tone_map.get(tone, f'{tone.capitalize()} bir kişiliğim var.')
        memories.append({
            'memory_type': 'personal_fact',
            'content': content,
            'relevance_score': 0.8
        })

    # 4. STYLE → Routine
    style = persona.get('style', '')
    if style and isinstance(style, str):
        style_map = {
            'concise': 'Kısa ve öz yazmayı severim, fazla detaya girmem.',
            'detailed': 'Detaylı analizler yaparım, her açıdan değerlendiririm.',
            'casual': 'Rahat ve samimi bir üslubum var, günlük dille konuşurum.',
            'formal': 'Profesyonel ve resmi bir dil kullanırım.'
        }
        content = style_map.get(style, f'{style.capitalize()} bir yazım stilim var.')
        memories.append({
            'memory_type': 'routine',
            'content': content,
            'relevance_score': 0.7
        })

    # 5. PERSONA HINT → Parse if meaningful
    hint = (bot.persona_hint or '').strip()
    if hint and len(hint) > 10:
        # Basit parse: İlk 150 karakter
        content = hint[:150]
        memories.append({
            'memory_type': 'personal_fact',
            'content': content,
            'relevance_score': 0.85
        })

    # 6. EMOTION PROFILE → Personal Fact
    emotion = bot.emotion_profile or {}

    # Signature phrases → Relationship (how I communicate)
    phrases = emotion.get('signature_phrases', [])
    if phrases and len(phrases) > 0:
        phrase = phrases[0] if isinstance(phrases, list) else phrases
        memories.append({
            'memory_type': 'routine',
            'content': f'Konuşmalarımda sık kullandığım ifade: "{phrase}"',
            'relevance_score': 0.75
        })

    # Anecdotes → Past Event
    anecdotes = emotion.get('anecdotes', [])
    if anecdotes and len(anecdotes) > 0:
        anecdote = anecdotes[0] if isinstance(anecdotes, list) else anecdotes
        if len(anecdote) > 20:
            memories.append({
                'memory_type': 'past_event',
                'content': anecdote[:200],  # İlk 200 karakter
                'relevance_score': 0.8
            })

    # Energy level → Personal Fact
    energy = emotion.get('energy', '')
    if energy and isinstance(energy, str):
        energy_map = {
            'high': 'Enerjik ve hareketli biriyim, hızlı karar alırım.',
            'medium': 'Dengeli bir enerjim var, aceleci değilim.',
            'low': 'Sakin ve düşünceliyim, acele etmem.'
        }
        content = energy_map.get(energy, f'{energy.capitalize()} enerjiye sahibim.')
        memories.append({
            'memory_type': 'personal_fact',
            'content': content,
            'relevance_score': 0.7
        })

    # 7. DEFAULT MEMORIES (if none created)
    if len(memories) == 0:
        memories.append({
            'memory_type': 'personal_fact',
            'content': 'Türk piyasalarında aktif bir yatırımcıyım.',
            'relevance_score': 0.8
        })
        memories.append({
            'memory_type': 'preference',
            'content': 'Günlük piyasa gelişmelerini takip etmeyi severim.',
            'relevance_score': 0.75
        })

    return memories


def generate_memories_for_bot(db: Session, bot: Bot, dry_run: bool = False) -> int:
    """
    Generate and save memories for a single bot.

    Returns number of memories created.
    """
    # Check if bot already has memories
    existing_count = db.query(BotMemory).filter(BotMemory.bot_id == bot.id).count()

    if existing_count > 0:
        logger.info(f"Bot {bot.id} ({bot.name}) already has {existing_count} memories, skipping")
        return 0

    # Generate memories
    memories_data = parse_persona_to_memories(bot)

    if dry_run:
        logger.info(f"[DRY RUN] Would create {len(memories_data)} memories for bot {bot.id} ({bot.name}):")
        for i, mem in enumerate(memories_data, 1):
            logger.info(f"  {i}. [{mem['memory_type']}] {mem['content'][:80]}...")
        return len(memories_data)

    # Save memories
    created = 0
    now = datetime.now(timezone.utc)

    for mem_data in memories_data:
        memory = BotMemory(
            bot_id=bot.id,
            memory_type=mem_data['memory_type'],
            content=mem_data['content'],
            relevance_score=mem_data['relevance_score'],
            created_at=now,
            last_used_at=now,
            usage_count=0
        )
        db.add(memory)
        created += 1

    db.commit()
    logger.info(f"✅ Created {created} memories for bot {bot.id} ({bot.name})")

    return created


def main():
    parser = argparse.ArgumentParser(description='Auto-generate bot memories from personas')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
    parser.add_argument('--bot-id', type=int, help='Only process specific bot ID')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("AUTO-GENERATE BOT MEMORIES")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be saved")

    db = next(get_db())

    try:
        # Get bots
        query = db.query(Bot)
        if args.bot_id:
            query = query.filter(Bot.id == args.bot_id)

        bots = query.all()

        if not bots:
            logger.warning("No bots found")
            return

        logger.info(f"Found {len(bots)} bot(s) to process\n")

        total_created = 0

        for bot in bots:
            count = generate_memories_for_bot(db, bot, dry_run=args.dry_run)
            total_created += count

        logger.info("\n" + "=" * 60)
        if args.dry_run:
            logger.info(f"[DRY RUN] Would create {total_created} memories total")
        else:
            logger.info(f"✅ Created {total_created} memories total")
        logger.info("=" * 60)

    except Exception as e:
        logger.exception(f"Error during memory generation: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    main()
