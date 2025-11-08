#!/usr/bin/env python
"""Test worker - tek mesaj üretimi"""
import asyncio
from dotenv import load_dotenv
load_dotenv()  # .env dosyasını yükle

from behavior_engine import BehaviorEngine

async def test_one_message():
    engine = BehaviorEngine()
    print('[OK] Behavior engine olusturuldu')
    print('[->] Bir mesaj uretmeye calisiliyor...')

    # Bir kere tick et
    result = await engine.tick_once()

    if result:
        print(f'[OK] MESAJ URETILDI! Message ID: {result}')
        return True
    else:
        print('[WARN] Mesaj uretilemedi (bot secilmemis olabilir - retry yapabilir)')
        return False

if __name__ == '__main__':
    success = asyncio.run(test_one_message())
    exit(0 if success else 1)
