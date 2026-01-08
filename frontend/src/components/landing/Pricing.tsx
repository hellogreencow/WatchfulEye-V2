import { useState } from 'react';
import { motion } from 'motion/react';
import { 
  Shield, 
  Brain, 
  Zap, 
  TrendingUp, 
  Eye, 
  Check, 
  X,
  Crown,
  Sparkles,
  BarChart3,
  Bell,
  Database,
  Infinity,
  Lock
} from 'lucide-react';
import { EP_PACKAGES, upgradeToWarRoom, getSubscription } from '../../lib/subscription';
import { PaymentModal } from '../ui/chimera/PaymentModal';

export function Pricing() {
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('monthly');
  const [paymentModal, setPaymentModal] = useState<{
    isOpen: boolean;
    tier: 'war-room' | 'ep-package';
    amount: number;
    packageDetails?: any;
  }>({
    isOpen: false,
    tier: 'war-room',
    amount: 29,
  });
  const subscription = getSubscription();

  const handleUpgrade = () => {
    const amount = billingCycle === 'monthly' ? 29 : 199;
    setPaymentModal({
      isOpen: true,
      tier: 'war-room',
      amount,
      packageDetails: {
        title: `War Room ${billingCycle === 'monthly' ? 'Monthly' : 'Annual'}`,
        description: billingCycle === 'monthly' 
          ? 'Full access to Privatized Intelligence Suite, Unlimited Tasking, and Smart Money Filter'
          : 'Full access to Privatized Intelligence Suite - Save 40%!',
        features: [
          'Unlimited Intelligence Dossiers',
          'Social Sentiment Analysis',
          'Smart Money "Copy-Trade" Filter',
          'Deep Intel Sources (Dark Pools)',
          '10-year Historical Causality',
          'Priority Tasking Queue'
        ]
      }
    });
  };

  const handlePaymentSuccess = () => {
    upgradeToWarRoom();
    window.location.reload(); // Reload to show new features
  };

  const handlePurchaseEP = (pkg: typeof EP_PACKAGES[0]) => {
    setPaymentModal({
      isOpen: true,
      tier: 'ep-package',
      amount: pkg.price,
      packageDetails: {
        title: `${(pkg.amount + pkg.bonus).toLocaleString()} EyePoints`,
        description: pkg.bonus > 0 
          ? `${pkg.amount.toLocaleString()} EP + ${pkg.bonus.toLocaleString()} Bonus EP`
          : 'Boost your EyePoints balance',
        features: [
          'Instant delivery',
          'No expiration',
          'Use for Deep Intel Analysis',
          'Unlock historical reports',
          'Play extra Daily 5 rounds',
          'AI ticker analysis'
        ]
      }
    });
  };

  return (
    <div className="min-h-screen bg-black text-white py-20 px-6 overflow-y-auto">
      <div className="max-w-7xl mx-auto">
        
        {/* Header */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 border border-primary/30 rounded-full mb-6">
            <Sparkles className="w-4 h-4 text-primary" />
            <span className="text-xs font-bold text-primary uppercase tracking-widest">Premium Access</span>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-black mb-6 tracking-tighter">
            Choose Your <span className="text-primary">Arsenal</span>
          </h1>
          
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-8">
            Start free. Upgrade when you're ready to dominate the markets with AI-powered intelligence.
          </p>

          {/* Billing Toggle */}
          <div className="inline-flex items-center gap-4 bg-white/5 border border-white/10 rounded-full p-1">
            <button
              onClick={() => setBillingCycle('monthly')}
              className={`px-6 py-2 rounded-full font-bold text-sm transition-all ${
                billingCycle === 'monthly' 
                  ? 'bg-primary text-black' 
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingCycle('annual')}
              className={`px-6 py-2 rounded-full font-bold text-sm transition-all relative ${
                billingCycle === 'annual' 
                  ? 'bg-primary text-black' 
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Annual
              <span className="absolute -top-2 -right-2 text-[8px] bg-green-500 text-black px-2 py-0.5 rounded-full font-bold">
                SAVE 40%
              </span>
            </button>
          </div>
        </motion.div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-2 gap-8 max-w-5xl mx-auto mb-20">
          
          {/* FREE TIER */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-white/5 border border-white/10 p-8 rounded-lg relative overflow-hidden"
          >
            <div className="relative z-10">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-muted/20 border border-muted/30 rounded-lg flex items-center justify-center">
                  <TrendingUp className="w-6 h-6 text-muted-foreground" />
                </div>
                <div>
                  <h3 className="text-2xl font-black uppercase tracking-tight">Recruit</h3>
                  <p className="text-xs text-muted-foreground font-mono">FREE FOREVER</p>
                </div>
              </div>

              <div className="mb-8">
                <div className="flex items-baseline gap-2">
                  <span className="text-5xl font-black">$0</span>
                  <span className="text-muted-foreground">/month</span>
                </div>
                <p className="text-sm text-muted-foreground mt-2">Perfect for Field Agents</p>
              </div>

              <button 
                disabled={subscription.tier === 'free'}
                className="w-full py-4 bg-white/10 border border-white/20 hover:bg-white/20 transition-all font-bold uppercase tracking-widest text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {subscription.tier === 'free' ? 'Current Plan' : 'Downgrade'}
              </button>

              <div className="mt-8 space-y-4">
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">Prediction Market Access</p>
                    <p className="text-xs text-muted-foreground">Vote on headlines & track results</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">Basic Intelligence Dossiers</p>
                    <p className="text-xs text-muted-foreground">Standard news & price history</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">Personal Precision Score</p>
                    <p className="text-xs text-muted-foreground">Track your own accuracy rating</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">Public Sentiment Feed</p>
                    <p className="text-xs text-muted-foreground">See global community votes</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 opacity-30">
                  <Lock className="w-5 h-5 text-gray-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">Tasking Authority</p>
                    <p className="text-xs text-muted-foreground">War Room exclusive</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 opacity-30">
                  <Lock className="w-5 h-5 text-gray-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">Smart Money Filter</p>
                    <p className="text-xs text-muted-foreground">War Room exclusive</p>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* WAR ROOM TIER */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-gradient-to-br from-primary/20 via-primary/5 to-primary/20 border-2 border-primary p-8 rounded-lg relative overflow-hidden"
          >
            {/* Animated background */}
            <div className="absolute inset-0 opacity-20">
              <motion.div
                className="absolute inset-0"
                animate={{
                  background: [
                    'radial-gradient(circle at 0% 0%, rgba(59, 130, 246, 0.3) 0%, transparent 50%)',
                    'radial-gradient(circle at 100% 100%, rgba(59, 130, 246, 0.3) 0%, transparent 50%)',
                    'radial-gradient(circle at 0% 0%, rgba(59, 130, 246, 0.3) 0%, transparent 50%)',
                  ],
                }}
                transition={{ duration: 8, repeat: Infinity as any }}
              />
            </div>

            <div className="relative z-10">
              {/* Popular Badge */}
              <div className="absolute -top-4 -right-4 bg-primary text-black px-4 py-1 rounded-full text-xs font-black uppercase tracking-widest rotate-12 shadow-lg">
                Most Popular
              </div>

              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-primary/20 border border-primary rounded-lg flex items-center justify-center">
                  <Crown className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h3 className="text-2xl font-black uppercase tracking-tight">War Room</h3>
                  <p className="text-xs text-primary font-mono">ELITE ACCESS</p>
                </div>
              </div>

              <div className="mb-8">
                <div className="flex items-baseline gap-2">
                  {billingCycle === 'monthly' ? (
                    <>
                      <span className="text-5xl font-black">${29}</span>
                      <span className="text-gray-400">/month</span>
                    </>
                  ) : (
                    <>
                      <span className="text-5xl font-black">${17}</span>
                      <span className="text-gray-400">/month</span>
                      <div className="ml-2 text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-full font-bold">
                        Billed ${199}/year
                      </div>
                    </>
                  )}
                </div>
                <p className="text-sm text-foreground mt-2">For Station Chiefs</p>
              </div>

              <button 
                onClick={handleUpgrade}
                disabled={subscription.tier === 'war-room'}
                className="w-full py-4 bg-primary hover:bg-primary/90 text-black transition-all font-bold uppercase tracking-widest text-sm shadow-lg shadow-primary/50 disabled:opacity-50 disabled:cursor-not-allowed relative overflow-hidden group"
              >
                <span className="relative z-10">
                  {subscription.tier === 'war-room' ? 'Current Plan' : 'Upgrade to War Room'}
                </span>
                <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform" />
              </button>

              <div className="mt-8 space-y-4">
                <div className="flex items-start gap-3">
                  <Zap className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">Everything in Free +</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm text-primary">Unlimited Tasking Authority</p>
                    <p className="text-xs text-muted-foreground">"Chimera, analyze [X]" - unlimited requests</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">Smart Money Filter</p>
                    <p className="text-xs text-muted-foreground">See what the Top 1% of predictors are betting</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">Deep Intel Sources</p>
                    <p className="text-xs text-muted-foreground">Dark pools, insider chatter, satellite data</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">Social Sentiment Analysis</p>
                    <p className="text-xs text-muted-foreground">Twitter/X narrative velocity tracking</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">Causality Models</p>
                    <p className="text-xs text-muted-foreground">10yr historical correlation engine</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">Priority Report Generation</p>
                    <p className="text-xs text-muted-foreground">Instant dossier compilation</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-sm">The Divergence Engine</p>
                    <p className="text-xs text-muted-foreground">Auto-alerts when Crowd vs. Data diverges</p>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>

        {/* EyePoints Packages */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="max-w-5xl mx-auto"
        >
          <div className="text-center mb-12">
            <h2 className="text-3xl font-black mb-4">Need More <span className="text-primary">EyePoints</span>?</h2>
            <p className="text-muted-foreground mb-6">Use EyePoints to unlock premium intelligence and analysis</p>
            
            {/* What EyePoints Unlock */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-w-3xl mx-auto mb-8 text-left">
              <div className="bg-white/5 border border-white/10 p-3 rounded">
                <div className="text-primary font-bold text-sm mb-1">100 EP</div>
                <div className="text-xs text-muted-foreground">Deep Intel Analysis</div>
              </div>
              <div className="bg-white/5 border border-white/10 p-3 rounded">
                <div className="text-primary font-bold text-sm mb-1">250 EP</div>
                <div className="text-xs text-muted-foreground">Extra Daily 5 Play</div>
              </div>
              <div className="bg-white/5 border border-white/10 p-3 rounded">
                <div className="text-primary font-bold text-sm mb-1">200 EP</div>
                <div className="text-xs text-muted-foreground">Historical Reports</div>
              </div>
              <div className="bg-white/5 border border-white/10 p-3 rounded">
                <div className="text-primary font-bold text-sm mb-1">150 EP</div>
                <div className="text-xs text-muted-foreground">AI Ticker Analysis</div>
              </div>
              <div className="bg-white/5 border border-white/10 p-3 rounded">
                <div className="text-primary font-bold text-sm mb-1">50 EP</div>
                <div className="text-xs text-muted-foreground">Custom Alerts</div>
              </div>
              <div className="bg-white/5 border border-white/10 p-3 rounded">
                <div className="text-primary font-bold text-sm mb-1">300 EP</div>
                <div className="text-xs text-muted-foreground">Scenario Replay</div>
              </div>
            </div>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {/* Starter Pack */}
            <div className="bg-white/5 border border-white/10 p-6 rounded-lg hover:border-primary/50 transition-all">
              <div className="text-center mb-6">
                <div className="text-4xl font-black mb-2">5,000 EP</div>
                <div className="text-2xl font-bold text-primary mb-1">$9.99</div>
                <p className="text-xs text-gray-500">Perfect for casual players</p>
              </div>
              <button className="w-full py-3 bg-white/10 border border-white/20 hover:bg-white/20 transition-all font-bold uppercase text-sm" onClick={() => handlePurchaseEP(EP_PACKAGES[0])}>
                Purchase
              </button>
            </div>

            {/* Pro Pack */}
            <div className="bg-gradient-to-br from-primary/10 to-primary/5 border-2 border-primary p-6 rounded-lg relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-black px-3 py-1 rounded-full text-[10px] font-black uppercase">
                Best Value
              </div>
              <div className="text-center mb-6">
                <div className="text-4xl font-black mb-2">18,000 EP</div>
                <div className="text-xs text-gray-400 line-through mb-1">15,000 EP + 3,000 BONUS</div>
                <div className="text-2xl font-bold text-primary mb-1">$24.99</div>
                <p className="text-xs text-gray-500">Most popular choice</p>
              </div>
              <button className="w-full py-3 bg-primary hover:bg-primary/90 text-black transition-all font-bold uppercase text-sm" onClick={() => handlePurchaseEP(EP_PACKAGES[1])}>
                Purchase
              </button>
            </div>

            {/* Elite Pack */}
            <div className="bg-white/5 border border-white/10 p-6 rounded-lg hover:border-primary/50 transition-all">
              <div className="text-center mb-6">
                <div className="text-4xl font-black mb-2">65,000 EP</div>
                <div className="text-xs text-gray-400 line-through mb-1">50,000 EP + 15,000 BONUS</div>
                <div className="text-2xl font-bold text-primary mb-1">$74.99</div>
                <p className="text-xs text-gray-500">Maximum value</p>
              </div>
              <button className="w-full py-3 bg-white/10 border border-white/20 hover:bg-white/20 transition-all font-bold uppercase text-sm" onClick={() => handlePurchaseEP(EP_PACKAGES[2])}>
                Purchase
              </button>
            </div>
          </div>

          <p className="text-center text-xs text-gray-500 mt-6">
            💡 Pro tip: War Room subscribers get unlimited EyePoints included
          </p>
        </motion.div>

        {/* Feature Comparison Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="max-w-5xl mx-auto mt-20 bg-white/5 border border-white/10 rounded-lg overflow-hidden"
        >
          <div className="p-6 border-b border-white/10">
            <h2 className="text-2xl font-black">Full Feature Comparison</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-white/10">
                <tr>
                  <th className="text-left p-4 font-bold">Feature</th>
                  <th className="text-center p-4 font-bold">Recruit</th>
                  <th className="text-center p-4 font-bold text-primary">War Room</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                <tr>
                  <td className="p-4">Prediction Market Access</td>
                  <td className="p-4 text-center"><Check className="w-5 h-5 text-green-500 mx-auto" /></td>
                  <td className="p-4 text-center"><Check className="w-5 h-5 text-primary mx-auto" /></td>
                </tr>
                <tr>
                  <td className="p-4">Daily Tasking Credits</td>
                  <td className="p-4 text-center text-gray-400">10 / day</td>
                  <td className="p-4 text-center text-primary font-bold">Unlimited</td>
                </tr>
                <tr>
                  <td className="p-4">Intelligence Sources</td>
                  <td className="p-4 text-center text-gray-400">Public News</td>
                  <td className="p-4 text-center text-primary font-bold">Deep Intel + Dark Pools</td>
                </tr>
                <tr>
                  <td className="p-4">Smart Money Filter</td>
                  <td className="p-4 text-center"><Lock className="w-5 h-5 text-gray-500 mx-auto" /></td>
                  <td className="p-4 text-center"><Check className="w-5 h-5 text-primary mx-auto" /></td>
                </tr>
                <tr>
                  <td className="p-4">The Divergence Engine</td>
                  <td className="p-4 text-center"><Lock className="w-5 h-5 text-gray-500 mx-auto" /></td>
                  <td className="p-4 text-center"><Check className="w-5 h-5 text-primary mx-auto" /></td>
                </tr>
                <tr>
                  <td className="p-4">Causality Models</td>
                  <td className="p-4 text-center"><Lock className="w-5 h-5 text-gray-500 mx-auto" /></td>
                  <td className="p-4 text-center"><Check className="w-5 h-5 text-primary mx-auto" /></td>
                </tr>
                <tr>
                  <td className="p-4">Social Sentiment Analysis</td>
                  <td className="p-4 text-center"><Lock className="w-5 h-5 text-gray-500 mx-auto" /></td>
                  <td className="p-4 text-center"><Check className="w-5 h-5 text-primary mx-auto" /></td>
                </tr>
                <tr>
                  <td className="p-4">Analyst API Access</td>
                  <td className="p-4 text-center"><Lock className="w-5 h-5 text-gray-500 mx-auto" /></td>
                  <td className="p-4 text-center"><Check className="w-5 h-5 text-primary mx-auto" /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </motion.div>
      </div>

      {/* Payment Modal */}
      <PaymentModal
        isOpen={paymentModal.isOpen}
        onClose={() => setPaymentModal({ ...paymentModal, isOpen: false })}
        onSuccess={handlePaymentSuccess}
        tier={paymentModal.tier}
        amount={paymentModal.amount}
        packageDetails={paymentModal.packageDetails}
      />
    </div>
  );
}