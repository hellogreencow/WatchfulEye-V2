import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, CreditCard, Lock, Check, ArrowRight, Shield } from 'lucide-react';

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  tier: 'war-room' | 'ep-package';
  amount: number;
  packageDetails?: {
    title: string;
    description: string;
    features: string[];
  };
}

export function PaymentModal({ isOpen, onClose, onSuccess, tier, amount, packageDetails }: PaymentModalProps) {
  const [step, setStep] = useState<'payment' | 'processing' | 'success'>('payment');
  const [cardNumber, setCardNumber] = useState('');
  const [expiry, setExpiry] = useState('');
  const [cvc, setCvc] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsProcessing(true);
    setStep('processing');
    
    // Simulate payment processing
    setTimeout(() => {
      setStep('success');
      setTimeout(() => {
        onSuccess();
        onClose();
        // Reset state
        setTimeout(() => {
          setStep('payment');
          setCardNumber('');
          setExpiry('');
          setCvc('');
          setIsProcessing(false);
        }, 500);
      }, 2000);
    }, 2000);
  };

  const formatCardNumber = (value: string) => {
    const cleaned = value.replace(/\s/g, '');
    const chunks = cleaned.match(/.{1,4}/g) || [];
    return chunks.join(' ').substring(0, 19);
  };

  const formatExpiry = (value: string) => {
    const cleaned = value.replace(/\D/g, '');
    if (cleaned.length >= 2) {
      return cleaned.substring(0, 2) + '/' + cleaned.substring(2, 4);
    }
    return cleaned;
  };

  if (!isOpen) return null;

  const defaultPackage = {
    title: tier === 'war-room' ? 'War Room Access' : 'EyePoints Package',
    description: tier === 'war-room' 
      ? 'Full access to Chimera, unlimited EyePoints, and advanced analytics'
      : 'Boost your EyePoints balance',
    features: tier === 'war-room' 
      ? [
          'Chimera AI Autopilot',
          'Unlimited EyePoints',
          'Real-time market alerts',
          'Advanced analytics dashboard',
          '10-year historical data',
          'Priority support'
        ]
      : [
          'Instant EyePoints delivery',
          'No expiration',
          'Use for intel, analysis, and more',
        ]
  };

  const pkg = packageDetails || defaultPackage;

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="relative w-full max-w-2xl bg-background border-2 border-primary/30 shadow-2xl max-h-[90vh] overflow-y-auto"
          >
            {/* Close button */}
            {step === 'payment' && (
              <button
                onClick={onClose}
                className="absolute top-4 right-4 p-2 hover:bg-white/10 transition-colors z-10"
              >
                <X className="w-5 h-5" />
              </button>
            )}

            {step === 'payment' && (
              <div className="p-8">
                {/* Header */}
                <div className="mb-8">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-12 h-12 bg-primary/20 border border-primary rounded-lg flex items-center justify-center">
                      <Shield className="w-6 h-6 text-primary" />
                    </div>
                    <div>
                      <h2 className="text-2xl font-black uppercase">{pkg.title}</h2>
                      <p className="text-sm text-muted-foreground">{pkg.description}</p>
                    </div>
                  </div>

                  {/* Features */}
                  <div className="bg-gradient-to-br from-primary/5 to-primary/10 border border-primary/20 rounded-lg p-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {pkg.features.map((feature, i) => (
                        <div key={i} className="flex items-center gap-2">
                          <Check className="w-4 h-4 text-primary shrink-0" />
                          <span className="text-sm">{feature}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Payment Form */}
                <form onSubmit={handleSubmit} className="space-y-6">
                  {/* Amount */}
                  <div className="bg-card border border-border p-6 rounded-lg">
                    <div className="flex items-baseline justify-between mb-2">
                      <span className="text-sm text-muted-foreground uppercase tracking-wider">Total Amount</span>
                      <div className="flex items-baseline gap-1">
                        <span className="text-4xl font-black text-primary">${amount}</span>
                        {tier === 'war-room' && <span className="text-sm text-muted-foreground">/month</span>}
                      </div>
                    </div>
                    {tier === 'war-room' && (
                      <p className="text-xs text-muted-foreground">Cancel anytime. No hidden fees.</p>
                    )}
                  </div>

                  {/* Card Number */}
                  <div>
                    <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
                      Card Number
                    </label>
                    <div className="relative">
                      <input
                        type="text"
                        value={cardNumber}
                        onChange={(e) => setCardNumber(formatCardNumber(e.target.value))}
                        placeholder="1234 5678 9012 3456"
                        maxLength={19}
                        required
                        className="w-full px-4 py-3 bg-card border border-border rounded-lg focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary font-mono"
                      />
                      <CreditCard className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    </div>
                  </div>

                  {/* Expiry & CVC */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
                        Expiry
                      </label>
                      <input
                        type="text"
                        value={expiry}
                        onChange={(e) => setExpiry(formatExpiry(e.target.value))}
                        placeholder="MM/YY"
                        maxLength={5}
                        required
                        className="w-full px-4 py-3 bg-card border border-border rounded-lg focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
                        CVC
                      </label>
                      <div className="relative">
                        <input
                          type="text"
                          value={cvc}
                          onChange={(e) => setCvc(e.target.value.replace(/\D/g, '').substring(0, 3))}
                          placeholder="123"
                          maxLength={3}
                          required
                          className="w-full px-4 py-3 bg-card border border-border rounded-lg focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary font-mono"
                        />
                        <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      </div>
                    </div>
                  </div>

                  {/* Security Notice */}
                  <div className="flex items-center gap-2 p-3 bg-primary/10 border border-primary/30 rounded-lg">
                    <Lock className="w-4 h-4 text-primary shrink-0" />
                    <p className="text-xs text-muted-foreground">
                      Secured by 256-bit SSL encryption. Your payment information is never stored.
                    </p>
                  </div>

                  {/* Submit */}
                  <button
                    type="submit"
                    disabled={isProcessing}
                    className="w-full py-4 bg-primary hover:bg-primary/90 text-black font-bold uppercase text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isProcessing ? (
                      'Processing...'
                    ) : (
                      <>
                        Complete Purchase
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>

                  <p className="text-xs text-center text-muted-foreground">
                    By confirming, you agree to our Terms of Service and Privacy Policy
                  </p>
                </form>
              </div>
            )}

            {step === 'processing' && (
              <div className="p-12 text-center">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  className="w-16 h-16 border-4 border-primary/30 border-t-primary rounded-full mx-auto mb-6"
                />
                <h3 className="text-xl font-black mb-2">Processing Payment...</h3>
                <p className="text-sm text-muted-foreground">This will only take a moment</p>
              </div>
            )}

            {step === 'success' && (
              <div className="p-12 text-center">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 200, damping: 15 }}
                  className="w-20 h-20 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-6"
                >
                  <Check className="w-10 h-10 text-white" />
                </motion.div>
                <h3 className="text-2xl font-black mb-2">Payment Successful!</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {tier === 'war-room' 
                    ? 'Welcome to the War Room. Redirecting...' 
                    : 'EyePoints added to your account'}
                </p>
                {tier === 'war-room' && (
                  <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary/20 border border-primary/50 rounded-full text-sm font-mono text-primary">
                    <Shield className="w-4 h-4" />
                    WAR ROOM ACCESS GRANTED
                  </div>
                )}
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}