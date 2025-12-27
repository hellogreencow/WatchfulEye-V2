import React, { useState } from 'react';
import { HelpCircle, X, Lightbulb, Info, AlertCircle } from 'lucide-react';
import { Card } from './ui/card';
import { Button } from './ui/button';

interface HelpTip {
  id: string;
  title: string;
  content: string;
  type: 'info' | 'tip' | 'warning';
}

interface OnboardingHelperProps {
  section: string;
}

const OnboardingHelper: React.FC<OnboardingHelperProps> = ({ section }) => {
  const [showHelp, setShowHelp] = useState(false);
  const [expandedTip, setExpandedTip] = useState<string | null>(null);

  const helpContent: Record<string, HelpTip[]> = {
    pulse: [
      {
        id: 'pulse-1',
        title: 'Understanding Impact Scores',
        content: 'Impact scores (0-1) indicate how significant an event is across multiple dimensions. Higher scores mean greater potential disruption or opportunity.',
        type: 'info'
      },
      {
        id: 'pulse-2',
        title: 'Urgency Levels Explained',
        content: 'Level 1-2: Low urgency, monitor\nLevel 3: Medium, review within 24h\nLevel 4-5: High urgency, immediate attention needed',
        type: 'tip'
      },
      {
        id: 'pulse-3',
        title: 'Click for Deep Analysis',
        content: 'Click "Analyze" on any event to get multi-perspective insights including market, geopolitical, and strategic implications.',
        type: 'tip'
      }
    ],
    analysis: [
      {
        id: 'analysis-1',
        title: 'Three Perspectives',
        content: 'Each analysis provides three distinct viewpoints: Market (financial), Geopolitical (international), and Decision-Maker (strategic).',
        type: 'info'
      },
      {
        id: 'analysis-2',
        title: 'Confidence Scores',
        content: 'Confidence scores indicate the reliability of the analysis. Scores above 0.7 are considered high confidence.',
        type: 'info'
      },
      {
        id: 'analysis-3',
        title: 'Entity Mentions',
        content: 'Key entities (companies, people, organizations) are automatically extracted and highlighted for quick reference.',
        type: 'tip'
      }
    ],
    'war-room': [
      {
        id: 'war-1',
        title: 'Creating Scenarios',
        content: 'Create "what-if" scenarios to explore potential futures. Example: "What if oil prices double?" or "What if a major tech company fails?"',
        type: 'tip'
      },
      {
        id: 'war-2',
        title: 'Probability vs Impact',
        content: 'Probability: How likely is this scenario?\nImpact: If it happens, how significant would the effects be?',
        type: 'info'
      },
      {
        id: 'war-3',
        title: 'Cascading Effects',
        content: 'The system models first-order (immediate), second-order (medium-term), and third-order (long-term) effects of your scenario.',
        type: 'info'
      }
    ],
    query: [
      {
        id: 'query-1',
        title: 'Ask Anything',
        content: 'Ask questions in natural language about markets, geopolitics, or strategic decisions. The AI will synthesize relevant intelligence.',
        type: 'tip'
      },
      {
        id: 'query-2',
        title: 'Query Types',
        content: 'Select the appropriate query type for better results:\n• Market: Financial and economic questions\n• Geopolitical: International relations\n• Scenario: Hypothetical situations',
        type: 'info'
      },
      {
        id: 'query-3',
        title: 'Pro Tip',
        content: 'Be specific in your queries. Instead of "market trends", try "impact of inflation on tech stocks in Q4 2024".',
        type: 'tip'
      }
    ]
  };

  const tips = helpContent[section] || [];

  const getIcon = (type: string) => {
    switch (type) {
      case 'tip':
        return <Lightbulb className="w-4 h-4 text-yellow-500" />;
      case 'warning':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Info className="w-4 h-4 text-blue-500" />;
    }
  };

  return (
    <div className="relative">
      {/* Help Button */}
      <Button
        onClick={() => setShowHelp(!showHelp)}
        variant="ghost"
        size="sm"
        className="fixed bottom-20 right-4 z-30 bg-white shadow-lg hover:shadow-xl transition-all duration-300"
      >
        <HelpCircle className="w-5 h-5 mr-2" />
        Help
      </Button>

      {/* Help Panel */}
      {showHelp && (
        <Card className="fixed bottom-32 right-4 w-80 z-40 bg-white shadow-2xl animate-slide-up">
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-lg">Quick Help</h3>
              <button
                onClick={() => setShowHelp(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3">
              {tips.map((tip) => (
                <div
                  key={tip.id}
                  className="border rounded-lg p-3 hover:bg-gray-50 transition-colors cursor-pointer"
                  onClick={() => setExpandedTip(expandedTip === tip.id ? null : tip.id)}
                >
                  <div className="flex items-start space-x-2">
                    {getIcon(tip.type)}
                    <div className="flex-1">
                      <h4 className="font-medium text-sm">{tip.title}</h4>
                      {expandedTip === tip.id && (
                        <p className="text-sm text-gray-600 mt-2 whitespace-pre-line">
                          {tip.content}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {tips.length === 0 && (
              <p className="text-gray-500 text-sm">
                No help available for this section.
              </p>
            )}
          </div>
        </Card>
      )}

      <style>{`
        @keyframes slide-up {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .animate-slide-up {
          animation: slide-up 0.3s ease-out;
        }
      `}</style>
    </div>
  );
};

export default OnboardingHelper; 