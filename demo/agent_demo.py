#!/usr/bin/env python3
"""
Modelo Gateway — Multimedia Pipeline Demo

Usage:
    python demo/agent_demo.py --url "https://news.ycombinator.com"
    python demo/agent_demo.py --url "https://example.com" --gateway-url "http://localhost:8000"

Required env vars (or .env file):
    ADMIN_TOKEN   — admin token for wallet/key creation
    GATEWAY_URL   — gateway base URL (default: Railway production)

Pipeline:
    Wallet setup → Firecrawl → Claude → Stability AI → AssemblyAI
    Saves image to demo/output/image.png and audio to demo/output/audio.mp3
"""

import argparse
import asyncio
import base64
import os
import sys
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_GATEWAY_URL = "https://web-production-b51ff.up.railway.app"
SAMPLE_AUDIO_URL = "https://assembly.ai/sports_injuries.mp3"
OUTPUT_DIR = Path(__file__).parent / "output"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

async def admin_post(client: httpx.AsyncClient, gateway: str, path: str, body: dict, admin_token: str) -> dict:
    resp = await client.post(
        f"{gateway}{path}",
        json=body,
        headers={"X-Admin-Token": admin_token},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


async def tool_call(
    client: httpx.AsyncClient, gateway: str, api_key: str, tool: str, params: dict
) -> tuple:
    resp = await client.post(
        f"{gateway}/mcp/call",
        json={"tool": tool, "params": params},
        headers={"X-API-Key": api_key},
        timeout=180.0,
    )
    resp.raise_for_status()
    data = resp.json()
    balance_remaining = resp.headers.get("X-Balance-Remaining", "?")
    return data, balance_remaining


# ---------------------------------------------------------------------------
# Wallet setup
# ---------------------------------------------------------------------------

async def setup_wallet(client: httpx.AsyncClient, gateway: str, admin_token: str):
    agent_id = f"demo-{uuid.uuid4().hex[:8]}"

    print(f"\n🏦  Creating wallet for agent: {agent_id}")
    wallet = await admin_post(client, gateway, "/wallets", {"agent_id": agent_id}, admin_token)
    wallet_id = wallet["id"]
    print(f"    ✅  Wallet ID: {wallet_id}")

    print("💳  Creating API key...")
    key_resp = await admin_post(client, gateway, "/keys", {"wallet_id": wallet_id, "label": "demo"}, admin_token)
    api_key = key_resp["key"]
    print(f"    ✅  API key: {api_key[:22]}...")

    print("💰  Topping up $10.00 USDT...")
    topup = await admin_post(client, gateway, f"/wallets/{wallet_id}/topup", {"amount": 10.0}, admin_token)
    balance = topup["balance_usdt"]
    print(f"    ✅  Balance: ${balance} USDT")

    return wallet_id, api_key, str(balance)


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

async def step_firecrawl(client: httpx.AsyncClient, gateway: str, api_key: str, url: str) -> str:
    print(f"\n🕷️   Step 1/4 — Firecrawl: scraping {url}")
    data, remaining = await tool_call(client, gateway, api_key, "firecrawl", {
        "url": url,
        "formats": ["markdown"],
    })
    markdown = data["result"].get("markdown", "")
    cost = data["total_usdt"]
    print(f"    ✅  Scraped {len(markdown):,} chars  |  cost: ${cost} USDT  |  balance: ${remaining}")
    return markdown[:3000]


async def step_claude(client: httpx.AsyncClient, gateway: str, api_key: str, content: str) -> str:
    print("\n🤖  Step 2/4 — Claude (Anthropic haiku): summarizing content...")
    data, remaining = await tool_call(client, gateway, api_key, "anthropic", {
        "messages": [
            {
                "role": "user",
                "content": (
                    "Summarize this web page content in 3 concise sentences. "
                    "Focus on the main topic and key points.\n\n"
                    f"{content}"
                ),
            }
        ],
        "max_tokens": 256,
        "system": "You are a concise summarizer. Return only the summary, no preamble.",
    })
    content_blocks = data["result"].get("content", [])
    summary = content_blocks[0]["text"] if content_blocks else ""
    cost = data["total_usdt"]
    print(f"    ✅  Summary ready  |  cost: ${cost} USDT  |  balance: ${remaining}")
    preview = summary[:120] + "..." if len(summary) > 120 else summary
    print(f"    📝  \"{preview}\"")
    return summary


async def step_stability(client: httpx.AsyncClient, gateway: str, api_key: str, summary: str) -> Path:
    print("\n🎨  Step 3/4 — Stability AI (sdxl): generating image...")
    prompt = f"Digital illustration: {summary[:200]}"
    data, remaining = await tool_call(client, gateway, api_key, "stability", {
        "prompt": prompt,
        "model": "sdxl",
    })
    image_b64 = data["result"]["image_b64"]
    output_path = OUTPUT_DIR / "image.png"
    output_path.write_bytes(base64.b64decode(image_b64))
    cost = data["total_usdt"]
    print(f"    ✅  Image saved → {output_path}  |  cost: ${cost} USDT  |  balance: ${remaining}")
    return output_path


async def step_assemblyai(client: httpx.AsyncClient, gateway: str, api_key: str) -> Path:
    print(f"\n🎙️   Step 4/4 — AssemblyAI: transcribing audio sample...")

    print(f"    ⬇️   Downloading audio from {SAMPLE_AUDIO_URL}")
    async with httpx.AsyncClient(timeout=30.0) as dl:
        audio_resp = await dl.get(SAMPLE_AUDIO_URL)
        audio_resp.raise_for_status()
    audio_path = OUTPUT_DIR / "audio.mp3"
    audio_path.write_bytes(audio_resp.content)
    size_kb = len(audio_resp.content) // 1024
    print(f"    💾  Audio saved → {audio_path} ({size_kb} KB)")

    data, remaining = await tool_call(client, gateway, api_key, "assemblyai", {
        "audio_url": SAMPLE_AUDIO_URL,
        "language_code": "en",
    })
    result = data["result"]
    transcript = result.get("text", "")
    duration = result.get("audio_duration_seconds", 0)
    cost = data["total_usdt"]
    print(f"    ✅  Transcribed {duration:.1f}s of audio  |  cost: ${cost} USDT  |  balance: ${remaining}")
    preview = transcript[:100] + "..." if len(transcript) > 100 else transcript
    print(f"    📝  \"{preview}\"")

    transcript_path = OUTPUT_DIR / "transcript.txt"
    transcript_path.write_text(transcript, encoding="utf-8")
    return audio_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(url: str, gateway: str, admin_token: str) -> None:
    print("=" * 62)
    print("🚀  Modelo Gateway — Multimedia Pipeline Demo")
    print("=" * 62)
    print(f"🌐  Gateway : {gateway}")
    print(f"🔗  Target  : {url}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    async with httpx.AsyncClient(timeout=60.0) as client:
        wallet_id, api_key, initial_balance = await setup_wallet(client, gateway, admin_token)

        print(f"\n💵  Balance before pipeline: ${initial_balance} USDT")
        print("-" * 62)

        markdown = await step_firecrawl(client, gateway, api_key, url)
        summary = await step_claude(client, gateway, api_key, markdown)
        await step_stability(client, gateway, api_key, summary)
        await step_assemblyai(client, gateway, api_key)

        wallet_resp = await client.get(f"{gateway}/wallets/{wallet_id}", timeout=10.0)
        wallet_resp.raise_for_status()
        final_balance = wallet_resp.json()["balance_usdt"]
        spent = float(initial_balance) - float(final_balance)

        print("\n" + "=" * 62)
        print("✅  Pipeline complete!")
        print(f"💵  Balance after pipeline : ${final_balance} USDT")
        print(f"💸  Total spent            : ${spent:.6f} USDT")
        print(f"\n📁  Outputs saved to {OUTPUT_DIR}/")
        print(f"    🖼️   image.png       — Stability AI generated image")
        print(f"    🎵  audio.mp3       — AssemblyAI sample audio")
        print(f"    📄  transcript.txt  — AssemblyAI transcript")
        print("=" * 62)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Modelo Gateway multimedia pipeline demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python demo/agent_demo.py --url \"https://news.ycombinator.com\"",
    )
    parser.add_argument("--url", required=True, help="URL to scrape with Firecrawl")
    parser.add_argument(
        "--gateway-url",
        default=os.getenv("GATEWAY_URL", DEFAULT_GATEWAY_URL),
        help="Gateway base URL (overrides GATEWAY_URL env var)",
    )
    args = parser.parse_args()

    admin_token = os.getenv("ADMIN_TOKEN", "")
    if not admin_token:
        print("❌  ADMIN_TOKEN not set. Add it to your .env file or environment.")
        print("    Example: ADMIN_TOKEN=your-admin-token")
        sys.exit(1)

    asyncio.run(run(args.url, args.gateway_url, admin_token))


if __name__ == "__main__":
    main()
