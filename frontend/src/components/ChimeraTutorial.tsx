import React, { useState, useEffect } from 'react';
import { X, ChevronRight, ChevronLeft, Rocket, Brain, Target, Shield, Lightbulb, TrendingUp } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';

interface TutorialStep {
  id: number;
  title: string;
  content: string;
  icon: React.ReactNode;
  highlight?: string;
  action?: string;
}

const ChimeraTutorial: React.FC = () => {
  const [showTutorial, setShowTutorial] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [hasSeenTutorial, setHasSeenTutorial] = useState(false);

  const tutorialSteps: TutorialStep[] = [
    {
      id: 0,
      title: "Welcome to Chimera Intelligence Platform! 🚀",
      content: "Transform raw data into actionable intelligence with our advanced AI-driven analysis system. This tutorial will guide you through all the powerful features.",
      icon: <Rocket className="w-8 h-8 text-blue-500" />,
      action: "Let's get started!"
    },
    {
      id: 1,
      title: "Pulse Feed - Real-Time Intelligence",
      content: "The Pulse Feed shows breaking news and events with impact scores and urgency levels. Each event is analyzed for its market, geopolitical, and strategic implications.",
      icon: <TrendingUp className="w-8 h-8 text-green-500" />,
      highlight: "pulse",
      action: "Click on any event to see detailed analysis"
    },
    {
      id: 2,
      title: "Multi-Perspective Analysis",
      content: "Every event is analyzed from three perspectives:\n• Market: Financial implications\n• Geopolitical: International relations\n• Decision-Maker: Strategic insights",
      icon: <Brain className="w-8 h-8 text-purple-500" />,
      highlight: "analysis",
      action: "View comprehensive insights for informed decisions"
    },
    {
      id: 3,
      title: "War Room - Scenario Modeling",
      content: "Create 'what-if' scenarios to explore potential futures. Model first, second, and third-order effects of hypothetical events.",
      icon: <Target className="w-8 h-8 text-red-500" />,
      highlight: "war-room",
      action: "Try creating a scenario like 'What if Bugatti ran on hydrogen?'"
    },
    {
      id: 4,
      title: "Adversarial Analysis",
      content: "Challenge assumptions and explore alternative perspectives. Our AI actively questions consensus views and provides counter-arguments.",
      icon: <Shield className="w-8 h-8 text-orange-500" />,
      highlight: "adversarial",
      action: "Get a balanced view with critical analysis"
    },
    {
      id: 5,
      title: "Query Engine",
      content: "Ask any question about current events, market trends, or geopolitical developments. Get personalized, synthesized intelligence tailored to your needs.",
      icon: <Lightbulb className="w-8 h-8 text-yellow-500" />,
      highlight: "query",
      action: "Ask anything - the AI will provide strategic insights"
    },
    {
      id: 6,
      title: "Your Intelligence Advantage",
      content: "Chimera doesn't just report what happened - it tells you why it matters, to whom, and what happens next. Start exploring your intelligence advantage!",
      icon: <Rocket className="w-8 h-8 text-indigo-500" />,
      action: "Start Exploring"
    }
  ];

  useEffect(() => {
    // Check if user has seen tutorial
    const tutorialSeen = localStorage.getItem('chimera_tutorial_seen');
    if (!tutorialSeen) {
      setTimeout(() => setShowTutorial(true), 1000);
    } else {
      setHasSeenTutorial(true);
    }
  }, []);

  const handleNext = () => {
    if (currentStep < tutorialSteps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleClose();
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleClose = () => {
    setShowTutorial(false);
    localStorage.setItem('chimera_tutorial_seen', 'true');
    setHasSeenTutorial(true);
  };

  const handleSkip = () => {
    handleClose();
  };

  const handleRestart = () => {
    setCurrentStep(0);
    setShowTutorial(true);
  };

  if (!showTutorial) {
    return (
      <>
        {hasSeenTutorial && (
          <Button
            onClick={handleRestart}
            className="fixed bottom-4 right-4 z-50 bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-lg hover:shadow-xl transition-all duration-300"
            size="sm"
          >
            <Lightbulb className="w-4 h-4 mr-2" />
            Tutorial
          </Button>
        )}
      </>
    );
  }

  const step = tutorialSteps[currentStep];

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black bg-opacity-50 z-40 transition-opacity duration-300" />
      
      {/* Tutorial Modal */}
      <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
        <Card className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full animate-fade-in-up">
          <div className="relative p-8">
            {/* Close button */}
            <button
              onClick={handleClose}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-6 h-6" />
            </button>

            {/* Progress indicator */}
            <div className="flex justify-center mb-6">
              <div className="flex space-x-2">
                {tutorialSteps.map((_, index) => (
                  <div
                    key={index}
                    className={`h-2 w-2 rounded-full transition-all duration-300 ${
                      index === currentStep
                        ? 'bg-blue-500 w-8'
                        : index < currentStep
                        ? 'bg-blue-300'
                        : 'bg-gray-300'
                    }`}
                  />
                ))}
              </div>
            </div>

            {/* Content */}
            <div className="text-center mb-8">
              <div className="flex justify-center mb-4">
                {step.icon}
              </div>
              <h2 className="text-2xl font-bold mb-4 text-gray-900">
                {step.title}
              </h2>
              <p className="text-gray-600 whitespace-pre-line leading-relaxed">
                {step.content}
              </p>
              {step.action && (
                <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                  <p className="text-blue-700 font-medium">
                    💡 {step.action}
                  </p>
                </div>
              )}
            </div>

            {/* Navigation */}
            <div className="flex justify-between items-center">
              <button
                onClick={handleSkip}
                className="text-gray-500 hover:text-gray-700 transition-colors"
              >
                Skip Tutorial
              </button>

              <div className="flex space-x-3">
                {currentStep > 0 && (
                  <Button
                    onClick={handlePrevious}
                    variant="outline"
                    size="sm"
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    Previous
                  </Button>
                )}
                <Button
                  onClick={handleNext}
                  className="bg-gradient-to-r from-blue-500 to-purple-600 text-white"
                  size="sm"
                >
                  {currentStep === tutorialSteps.length - 1 ? (
                    <>
                      Get Started
                      <Rocket className="w-4 h-4 ml-1" />
                    </>
                  ) : (
                    <>
                      Next
                      <ChevronRight className="w-4 h-4 ml-1" />
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Highlight overlay */}
      {step.highlight && (
        <div className="fixed inset-0 pointer-events-none z-35">
          <div className={`highlight-${step.highlight} animate-pulse`} />
        </div>
      )}

      <style>{`
        @keyframes fade-in-up {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .animate-fade-in-up {
          animation: fade-in-up 0.3s ease-out;
        }

        .highlight-pulse {
          border: 3px solid #3B82F6;
          border-radius: 12px;
          box-shadow: 0 0 20px rgba(59, 130, 246, 0.5);
        }

        .highlight-analysis {
          position: absolute;
          top: 200px;
          left: 50%;
          transform: translateX(-50%);
          width: 80%;
          height: 400px;
        }

        .highlight-war-room {
          position: absolute;
          top: 100px;
          right: 20px;
          width: 200px;
          height: 50px;
        }
      `}</style>
    </>
  );
};

export default ChimeraTutorial; 