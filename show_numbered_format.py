#!/usr/bin/env python3
"""
Show the improved format with numbered references
"""

sample_message = """┏━━ *GLOBAL BRIEF* ━━┓
*#GEOPOLITICS*
— 2025-06-05
┗━━━━━━━━━━━━━━━━┛

⚡1 *BREAKING TIER-1* — +++ 18:09 Putin Tells Trump He Will Respond to Ukraine Attack, Escalation Feared +++
Russian President Vladimir Putin informed President Donald Trump during a phone call that he felt obligated to respond to a recent drone attack by Ukraine, as reported by Politicalwire.com. This development raises concerns of a potential escalation in the ongoing conflict between Russia and Ukraine. [1]
*KEY INSIGHT:* This communication between Putin and Trump signals a high likelihood of increased military action by Russia, which could destabilize the region further and impact global markets.
*ACTIONABLE ADVICE:* Consider hedging against market volatility with defensive assets such as gold (ticker: GLD) and government bonds.

⚡2 *BREAKING TIER-2* — +++ 18:09 Ray Dalio Warns of US Economic Peril Due to Rising Debt +++
Ray Dalio, founder of Bridgewater Associates, has issued a warning about the United States' financial situation, highlighting the emerging problem of rising debt and interest costs. [2]
*KEY INSIGHT:* Dalio's warning could lead to increased investor caution, potentially affecting bond yields and equity markets.
*ACTIONABLE ADVICE:* Consider shorting U.S. equities sensitive to interest rate hikes and increasing exposure to TIP.

📊 *KEY NUMBERS*
• *US Deficit Reduction from Trump's Tariffs* [3] — $2.8 trillion
  President Trump's tariff plan is projected to cut deficits by $2.8 trillion over 10 years, which could impact trade relations.
• *Nvidia's Massive Chip Write-Off* [4] — $4.5 billion
  Nvidia has written off $4.5 billion in chips due to US export restrictions, affecting the semiconductor market.

📈 *MARKET PULSE*
• *Defense Stocks ↑* — Increased geopolitical tensions [5]
  Why it matters: Defense contractors may benefit from increased military spending amid escalating conflicts.

₿ *CRYPTO BAROMETER*
• *BITCOIN ↓* — Risk-off sentiment due to geopolitical uncertainty [6]
  Bitcoin may decline as investors seek safer assets during heightened tensions.

💡 *IDEA DESK*
• *BUY LMT* — Defense sector poised to benefit from increased military spending [7]
• *HEDGE GLD* — Safe-haven assets attractive during geopolitical uncertainty [8]

🎯 *FINAL INTEL*
The most critical development is Putin's communication to Trump about responding to Ukraine's drone attacks, signaling potential escalation. Defense stocks may benefit while risk assets face pressure.
*Investment Horizon:* Short-term volatility, medium-term defense sector growth
*Key Risks:* Military escalation, economic sanctions, market volatility

━━━━━━━━━━━━━━━━━
📰 *100 sources analyzed*
🌐 *Full analysis:* https://diatombot.xyz
⚱ *Processing:* 54.1s
*🤖 Powered by DiatomsAI*

━━━━━━━━━━━━━━━━━
*📎 SOURCES:*
[1] nypost.com/...
[2] irishtimes.com/...
[3] slashdot.org/...
[4] biztoc.com/...
[5] example.com/...
[6] businessinsider.com/...
[7] cbssports.com/...
[8] news.sky.com/...
... +7 more sources
━━━━━━━━━━━━━━━━━"""

print("🎯 IMPROVED FORMAT WITH NUMBERED REFERENCES:")
print("=" * 60)
print(sample_message)
print("\n" + "=" * 60)
print(f"📊 MESSAGE STATS:")
print(f"• Characters: {len(sample_message)}")
print(f"• Lines: {len(sample_message.split(chr(10)))}")
print(f"• Reference numbers: {sample_message.count('[') - 1}")  # -1 for the SOURCES header
print(f"• Telegram ready: {'✅' if len(sample_message) <= 4096 else '❌ (will auto-truncate)'}")
print("\n✨ KEY IMPROVEMENTS:")
print("• Numbered references [1], [2], etc. instead of broken [LINK]")
print("• Source URLs listed at bottom with domain names")
print("• Clean, professional appearance")
print("• No markdown parsing issues") 