#!/usr/bin/env python3
"""
Quick test to show the improved message formatting
"""

# Sample formatted message with the new [LINK] format
sample_message = """┏━━ *GLOBAL BRIEF* ━━┓
*#GEOPOLITICS*
— 2025-06-05
┗━━━━━━━━━━━━━━━━┛

⚡1 *BREAKING TIER-1* — +++ 18:02 Putin Tells Trump He Will Respond to Ukraine Attack, Escalation Feared +++
Russian President Vladimir Putin informed US President Donald Trump that he feels obligated to respond to Ukraine's recent drone attack, as reported by Politicalwire.com. This development raises concerns of a potential escalation in the ongoing conflict between Russia and Ukraine. [LINK](https://nypost.com/2025/06/04/lifestyle/plane-feud-erupts-over-air-vent-and-cup-of-hot-water/)
*KEY INSIGHT:* The communication between Putin and Trump suggests a heightened risk of military escalation, which could impact global markets through increased volatility and risk aversion.
*ACTIONABLE ADVICE:* HEDGE against geopolitical risk by increasing positions in safe-haven assets such as gold (ticker: GLD) and U.S. Treasuries.

⚡2 *BREAKING TIER-2* — +++ 18:02 Zelenskyy Urges Western Allies to Accelerate Air Defense Deliveries +++
Ukrainian President Volodymyr Zelenskyy has requested Western allies to expedite the delivery of air defense systems to counteract Russian missile strikes, as per PBS reporting. [LINK](https://www.irishtimes.com/business/2025/06/04/ryanairs-michael-oleary-sells-shares-worth-21m/)
*KEY INSIGHT:* Zelenskyy's plea for air defense support could lead to increased defense spending and bolster the defense sector.
*ACTIONABLE ADVICE:* BUY shares in defense contractors, such as Lockheed Martin (ticker: LMT).

📊 *KEY NUMBERS*
• *Nvidia's Massive Chip Write-off* [LINK](https://slashdot.org/firehose.pl) — $4.5 billion
  The Times of India reports Nvidia's $4.5 billion write-off due to US export restrictions, significantly impacting the semiconductor industry.
• *Private Sector Job Growth Decline* [LINK](https://biztoc.com/x/8e7221689dec3fed) — 37,000 jobs
  According to pymnts.com, the private sector added only 37,000 jobs in May, marking the lowest level in two years.

📈 *MARKET PULSE*
• *Defense Stocks ↑* — Increased geopolitical tensions [LINK](https://example.com)
  Why it matters: Defense contractors may benefit from increased military spending amid escalating conflicts.

₿ *CRYPTO BAROMETER*
• *BITCOIN ↓* — Risk-off sentiment due to geopolitical uncertainty [LINK](https://example.com)
  Bitcoin may decline as investors seek safer assets during heightened tensions.

💡 *IDEA DESK*
• *BUY LMT* — Defense sector poised to benefit from increased military spending [LINK](https://example.com)
• *HEDGE GLD* — Safe-haven assets attractive during geopolitical uncertainty [LINK](https://example.com)

🎯 *FINAL INTEL*
The most critical development is Putin's communication to Trump about responding to Ukraine's drone attacks, signaling potential escalation. Defense stocks may benefit while risk assets face pressure.
*Investment Horizon:* Short-term volatility, medium-term defense sector growth
*Key Risks:* Military escalation, economic sanctions, market volatility

━━━━━━━━━━━━━━━━━
📰 *100 sources analyzed*
🌐 *Full analysis:* https://watchfuleye.us
⚱ *Processing:* 54.2s
*🤖 Powered by DiatomsAI*
━━━━━━━━━━━━━━━━━"""

print("🎯 NEW IMPROVED FORMAT:")
print("=" * 60)
print(sample_message)
print("\n" + "=" * 60)
print(f"📊 MESSAGE STATS:")
print(f"• Characters: {len(sample_message)}")
print(f"• Lines: {len(sample_message.split(chr(10)))}")
print(f"• [LINK] references: {sample_message.count('[LINK]')}")
print(f"• Telegram ready: {'✅' if len(sample_message) <= 4096 else '❌ (will auto-truncate)'}") 