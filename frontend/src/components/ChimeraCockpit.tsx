import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Badge } from './ui/badge';
import ChimeraTutorial from './ChimeraTutorial';
import OnboardingHelper from './OnboardingHelper';
import { AlertCircle, TrendingUp, Brain, Target, MessageSquare, Sparkles, RefreshCw } from 'lucide-react';
import { motion } from 'framer-motion';

interface PulseEvent {
  id: number;
  title: string;
  description: string;
  source: string;
  category: string;
  created_at: string;
  impact_score: number;
  urgency_level: number;
  synthesis_summary: string;
  confidence_score: number;
}

interface PrismAnalysis {
  market_perspective: string;
  geopolitical_perspective: string;
  decision_maker_perspective: string;
  neutral_facts: string;
  synthesis_summary: string;
  impact_assessment: string;
  confidence_score: number;
  citations: string[];
  entity_mentions: string[];
  temporal_context: string;
}

interface Scenario {
  id: number;
  scenario_name: string;
  trigger_event: string;
  first_order_effects: string;
  second_order_effects: string;
  third_order_effects: string;
  probability_score: number;
  impact_score: number;
  created_at: string;
}

interface UserInterest {
  id: number;
  interest_type: string;
  interest_value: string;
  priority_level: number;
}

const ChimeraCockpit: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('pulse');
  const [pulseEvents, setPulseEvents] = useState<PulseEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<PulseEvent | null>(null);
  const [analysis, setAnalysis] = useState<PrismAnalysis | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [userInterests, setUserInterests] = useState<UserInterest[]>([]);
  const [queryText, setQueryText] = useState('');
  const [queryType, setQueryType] = useState('general');
  const [queryResult, setQueryResult] = useState<any>(null);
  const [userId] = useState(1); // Default user ID
  
  // New state for scenario creation
  const [scenarioName, setScenarioName] = useState('');
  const [triggerEvent, setTriggerEvent] = useState('');
  const [probabilityScore, setProbabilityScore] = useState<number>(50);
  const [impactScore, setImpactScore] = useState<number>(50);
  const [firstOrderEffects, setFirstOrderEffects] = useState<string[]>([]);
  const [secondOrderEffects, setSecondOrderEffects] = useState<string[]>([]);
  const [thirdOrderEffects, setThirdOrderEffects] = useState<string[]>([]);
  const [newEffectText, setNewEffectText] = useState<string>('');
  const [newEffectTier, setNewEffectTier] = useState<'first'|'second'|'third'>('first');

  // Get API base URL from environment or use relative path (works with CRA proxy and prod nginx)
  const API_BASE_URL = (() => {
    const fallback = '/api';
    const raw = (process.env.REACT_APP_API_URL || '').trim();
    if (!raw) return fallback;

    const pageHost = window.location.hostname;
    const isLocalPage = pageHost === 'localhost' || pageHost === '127.0.0.1';

    try {
      if (/^https?:\/\//i.test(raw)) {
        const u = new URL(raw);
        const isLocalTarget = u.hostname === 'localhost' || u.hostname === '127.0.0.1';
        if (isLocalTarget && !isLocalPage) return fallback;
        if (!u.pathname || u.pathname === '/') u.pathname = '/api';
        return u.toString().replace(/\/$/, '');
      }
    } catch {
      // ignore
    }
    const cleaned = raw.replace(/\/$/, '');
    if (!cleaned.startsWith('/') && !cleaned.startsWith('http')) return `/${cleaned}`;
    return cleaned;
  })();

  // Get user ID from localStorage or session
  useEffect(() => {
    const user = localStorage.getItem('user');
    if (user) {
      const userData = JSON.parse(user);
      // setUserId(userData.id); // This line was removed from the new_code, so it's removed here.
    }
  }, []);

  // Load Pulse Feed
  const loadPulseFeed = useCallback(async () => {
    if (!userId) return;
    
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/chimera/pulse?user_id=${userId}&limit=20`);
      const data = await response.json();
      
      if (data.success) {
        setPulseEvents(data.pulse_events);
      }
    } catch (error) {
      console.error('Error loading pulse feed:', error);
    } finally {
      setLoading(false);
    }
  }, [userId, API_BASE_URL]);

  // Load user scenarios
  const loadScenarios = useCallback(async () => {
    if (!userId) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/chimera/war-room/scenarios?user_id=${userId}`);
      const data = await response.json();
      
      if (data.success) {
        setScenarios(data.scenarios);
      }
    } catch (error) {
      console.error('Error loading scenarios:', error);
    }
  }, [userId, API_BASE_URL]);

  // Load user interests
  const loadUserInterests = useCallback(async () => {
    if (!userId) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/chimera/interests/${userId}`);
      const data = await response.json();
      
      if (data.success) {
        setUserInterests(data.interests);
      }
    } catch (error) {
      console.error('Error loading user interests:', error);
    }
  }, [userId, API_BASE_URL]);

  // Analyze selected event
  const analyzeEvent = useCallback(async (event: PulseEvent) => {
    if (!userId) return;
    
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/chimera/analyze/${event.id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });
      
      const data = await response.json();
      
      if (data.success) {
        setAnalysis(data.analysis);
        setSelectedEvent(event);
        setActiveTab('analysis');
      }
    } catch (error) {
      console.error('Error analyzing event:', error);
    } finally {
      setLoading(false);
    }
  }, [userId, API_BASE_URL]);

  // Submit query
  const submitQuery = useCallback(async () => {
    if (!userId || !queryText.trim()) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/chimera/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query_text: queryText,
          query_type: queryType,
          user_id: userId,
        }),
      });
      
      const data = await response.json();
      
      if (data.success) {
        setQueryResult(data.result);
      } else {
        setQueryResult({ error: 'Failed to submit query' });
      }
    } catch (error) {
      console.error('Error submitting query:', error);
      setQueryResult({ error: 'Error submitting query. Please check your connection.' });
    } finally {
      setLoading(false);
    }
  }, [userId, queryText, queryType, API_BASE_URL]);

  // Create scenario function
  const createScenario = useCallback(async () => {
    if (!scenarioName.trim() || !triggerEvent.trim()) {
      alert('Please enter both scenario name and trigger event');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/chimera/war-room/scenario`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          scenario_name: scenarioName,
          trigger_event: triggerEvent,
          probability_score: probabilityScore / 100,
          impact_score: impactScore / 100,
          first_order_effects: JSON.stringify(firstOrderEffects),
          second_order_effects: JSON.stringify(secondOrderEffects),
          third_order_effects: JSON.stringify(thirdOrderEffects),
        }),
      });

      if (response.ok) {
        const data = await response.json();
        console.log('Scenario created:', data);
        // Clear inputs
        setScenarioName('');
        setTriggerEvent('');
        setProbabilityScore(50);
        setImpactScore(50);
        setFirstOrderEffects([]);
        setSecondOrderEffects([]);
        setThirdOrderEffects([]);
        // Reload scenarios
        loadScenarios();
        alert('Scenario created successfully!');
      } else {
        console.error('Failed to create scenario');
        alert('Failed to create scenario. Please try again.');
      }
    } catch (error) {
      console.error('Error creating scenario:', error);
      alert('Error creating scenario. Please check your connection.');
    } finally {
      setLoading(false);
    }
  }, [scenarioName, triggerEvent, userId, API_BASE_URL, loadScenarios]);

  // Load data on component mount
  useEffect(() => {
    if (userId) {
      loadPulseFeed();
      loadScenarios();
      loadUserInterests();
    }
  }, [userId, loadPulseFeed, loadScenarios, loadUserInterests]);

  // Auto-refresh pulse feed every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      if (activeTab === 'pulse') {
        loadPulseFeed();
      }
    }, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, [activeTab, loadPulseFeed]);

  const getUrgencyColor = (level: number) => {
    switch (level) {
      case 5: return 'bg-red-500';
      case 4: return 'bg-orange-500';
      case 3: return 'bg-yellow-500';
      case 2: return 'bg-blue-500';
      default: return 'bg-gray-500';
    }
  };

  const getImpactColor = (score: number) => {
    if (score > 0.8) return 'text-red-600';
    if (score > 0.6) return 'text-orange-600';
    if (score > 0.4) return 'text-yellow-600';
    return 'text-gray-600';
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 p-3 sm:p-4 md:p-6">
      {/* Tutorial Component */}
      <ChimeraTutorial />
      
      <div className="max-w-7xl mx-auto space-y-4 sm:space-y-6">
        {/* Enhanced Header */}
        <motion.div 
          className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm p-4 sm:p-6 sticky top-0 z-10 backdrop-blur bg-opacity-90"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl sm:text-2xl md:text-3xl font-bold text-slate-900 dark:text-slate-100 mb-2">
                WatchfulEye Intelligence Cockpit
              </h1>
              <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 flex items-center">
                <Sparkles className="w-4 h-4 mr-2 text-yellow-500" />
                Advanced intelligence synthesis and analysis platform
              </p>
            </div>
            <div className="flex items-center space-x-4">
              <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                Live
              </Badge>
              <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                {userId ? `User ID: ${userId}` : 'Guest'}
              </Badge>
            </div>
          </div>
        </motion.div>

        {/* Blurred Out Chimera Intelligence Section */}
        <div className="relative">
          <div className="absolute inset-0 bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm rounded-xl z-10 flex items-center justify-center">
            <div className="text-center p-8">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <Brain className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-2">
                Chimera Intelligence
              </h2>
              <p className="text-slate-600 dark:text-slate-400 mb-4">
                Advanced multi-perspective intelligence analysis
              </p>
              <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300">
                Coming Soon
              </Badge>
            </div>
          </div>
          
          {/* Original content (blurred) */}
          <div className="blur-sm pointer-events-none opacity-50">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4 sm:space-y-6">
              <TabsList className="grid w-full grid-cols-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm">
                <TabsTrigger value="pulse" className="flex items-center space-x-2">
                  <TrendingUp className="w-4 h-4" />
                  <span>Pulse Feed</span>
                </TabsTrigger>
                <TabsTrigger value="analysis" className="flex items-center space-x-2">
                  <Brain className="w-4 h-4" />
                  <span>Analysis</span>
                </TabsTrigger>
                <TabsTrigger value="war-room" className="flex items-center space-x-2">
                  <Target className="w-4 h-4" />
                  <span>War Room</span>
                </TabsTrigger>
                <TabsTrigger value="query" className="flex items-center space-x-2">
                  <MessageSquare className="w-4 h-4" />
                  <span>Query Engine</span>
                </TabsTrigger>
              </TabsList>

              {/* Pulse Feed Tab */}
              <TabsContent value="pulse" className="space-y-4">
                <OnboardingHelper section="pulse" />
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
                <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 shadow-lg">
                  <CardHeader className="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-slate-800 dark:to-slate-800/80">
                    <CardTitle className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <TrendingUp className="w-5 h-5 text-blue-600" />
                        <span>Real-Time Intelligence Pulse</span>
                      </div>
                      <Button 
                        onClick={loadPulseFeed} 
                        disabled={loading}
                        variant="outline"
                        size="sm"
                        className="flex items-center space-x-2"
                      >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        <span>{loading ? 'Refreshing...' : 'Refresh'}</span>
                      </Button>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {pulseEvents.length === 0 ? (
                        <div className="text-center py-8 text-slate-500">
                          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                          <p>No pulse events available</p>
                          <p className="text-sm mt-2">Check back later for real-time intelligence updates</p>
                        </div>
                      ) : (
                        pulseEvents.map((event) => (
                          <motion.div key={event.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
                          <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 cursor-pointer hover:shadow-md transition-shadow">
                            <CardContent className="p-4">
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <div className="flex items-center gap-2 mb-2">
                                    <h3 className="font-semibold text-lg">{event.title}</h3>
                                    <Badge className={getUrgencyColor(event.urgency_level)}>
                                      Level {event.urgency_level}
                                    </Badge>
                                  </div>
                                  <p className="text-slate-600 dark:text-slate-300 mb-2">{event.description}</p>
                                  <div className="flex items-center gap-4 text-sm text-slate-500 dark:text-slate-400">
                                    <span>{event.source}</span>
                                    <span>{new Date(event.created_at).toLocaleString()}</span>
                                    <span className={getImpactColor(event.impact_score)}>
                                      Impact: {(event.impact_score * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                  {event.synthesis_summary && (
                                    <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                                      <p className="text-sm text-blue-800 dark:text-blue-200">{event.synthesis_summary}</p>
                                    </div>
                                  )}
                                </div>
                                <Button
                                  onClick={() => analyzeEvent(event)}
                                  disabled={loading}
                                  size="sm"
                                  className="ml-4"
                                >
                                  Analyze
                                </Button>
                              </div>
                            </CardContent>
                          </Card>
                          </motion.div>
                        ))
                      )}
                    </div>
                  </CardContent>
                </Card>
                </motion.div>
              </TabsContent>

              {/* Analysis Tab */}
              <TabsContent value="analysis" className="space-y-4">
                <OnboardingHelper section="analysis" />
                {selectedEvent && analysis ? (
                  <motion.div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                    {/* Event Header */}
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 lg:col-span-3">
                      <CardHeader>
                        <CardTitle>{selectedEvent.title}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-slate-600 dark:text-slate-300">{selectedEvent.description}</p>
                        <div className="flex items-center gap-4 mt-4">
                          <Badge className={getUrgencyColor(selectedEvent.urgency_level)}>
                            Urgency Level {selectedEvent.urgency_level}
                          </Badge>
                          <span className={getImpactColor(selectedEvent.impact_score)}>
                            Impact: {(selectedEvent.impact_score * 100).toFixed(0)}%
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setScenarioName(selectedEvent.title);
                              setTriggerEvent(selectedEvent.description);
                              createScenario();
                            }}
                          >
                            Promote to Scenario
                          </Button>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Market Perspective */}
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                      <CardHeader>
                        <CardTitle>Market Perspective</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm leading-relaxed">{analysis.market_perspective}</p>
                      </CardContent>
                    </Card>

                    {/* Geopolitical Perspective */}
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                      <CardHeader>
                        <CardTitle>Geopolitical Perspective</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm leading-relaxed">{analysis.geopolitical_perspective}</p>
                      </CardContent>
                    </Card>

                    {/* Decision-Maker Perspective */}
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                      <CardHeader>
                        <CardTitle>Decision-Maker Perspective</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm leading-relaxed">{analysis.decision_maker_perspective}</p>
                      </CardContent>
                    </Card>

                    {/* Synthesis Summary */}
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 lg:col-span-3">
                      <CardHeader>
                        <CardTitle>Synthesis Summary</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm leading-relaxed">{analysis.synthesis_summary}</p>
                        <div className="mt-4 flex items-center gap-4">
                          <Badge variant="outline">
                            Confidence: {(analysis.confidence_score * 100).toFixed(0)}%
                          </Badge>
                          {analysis.entity_mentions.length > 0 && (
                            <div className="flex gap-2">
                              <span className="text-sm text-gray-600">Entities:</span>
                              {analysis.entity_mentions.slice(0, 3).map((entity, index) => (
                                <Badge key={index} variant="secondary">{entity}</Badge>
                              ))}
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>

                    {/* Neutral Facts */}
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 lg:col-span-2">
                      <CardHeader>
                        <CardTitle>Neutral Facts</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm leading-relaxed">{analysis.neutral_facts}</p>
                      </CardContent>
                    </Card>

                    {/* Impact Assessment */}
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                      <CardHeader>
                        <CardTitle>Impact Assessment</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm leading-relaxed">{analysis.impact_assessment}</p>
                      </CardContent>
                    </Card>
                  </motion.div>
                ) : (
                  <Card>
                    <CardContent className="p-8 text-center">
                      <Brain className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                      <p className="text-gray-600">Select an event from the Pulse Feed to view analysis</p>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              {/* War Room Tab */}
              <TabsContent value="war-room" className="space-y-4">
                <OnboardingHelper section="war-room" />
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Create Scenario */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Create New Scenario</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm font-medium mb-1">Scenario Name</label>
                          <Input 
                            placeholder="e.g., Bugatti Hydrogen Revolution" 
                            value={scenarioName}
                            onChange={(e) => setScenarioName(e.target.value)}
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-1">Trigger Event</label>
                          <Input 
                            placeholder="e.g., Bugatti announces transition to hydrogen fuel" 
                            value={triggerEvent}
                            onChange={(e) => setTriggerEvent(e.target.value)}
                          />
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <label className="block text-sm font-medium mb-1">Probability ({probabilityScore}%)</label>
                            <input type="range" min={0} max={100} value={probabilityScore} onChange={(e) => setProbabilityScore(Number(e.target.value))} className="w-full" />
                          </div>
                          <div>
                            <label className="block text-sm font-medium mb-1">Impact ({impactScore}%)</label>
                            <input type="range" min={0} max={100} value={impactScore} onChange={(e) => setImpactScore(Number(e.target.value))} className="w-full" />
                          </div>
                        </div>

                        <div className="space-y-2">
                          <label className="block text-sm font-medium">Causal Effects</label>
                          <div className="flex gap-2 items-center">
                            <select className="border rounded px-2 py-1 text-sm" value={newEffectTier} onChange={(e) => setNewEffectTier(e.target.value as any)}>
                              <option value="first">1st order</option>
                              <option value="second">2nd order</option>
                              <option value="third">3rd order</option>
                            </select>
                            <Input placeholder="Add effect..." value={newEffectText} onChange={(e) => setNewEffectText(e.target.value)} />
                            <Button
                              onClick={() => {
                                const text = newEffectText.trim();
                                if (!text) return;
                                if (newEffectTier === 'first') setFirstOrderEffects(prev => [...prev, text]);
                                else if (newEffectTier === 'second') setSecondOrderEffects(prev => [...prev, text]);
                                else setThirdOrderEffects(prev => [...prev, text]);
                                setNewEffectText('');
                              }}
                            >Add</Button>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <div className="p-2 rounded border">
                              <div className="text-xs font-semibold mb-1">1st Order</div>
                              <div className="space-y-1">
                                {firstOrderEffects.map((e, i) => (
                                  <div key={`f-${i}`} className="flex items-center justify-between bg-slate-50 dark:bg-slate-700/50 p-1 rounded text-sm">
                                    <span className="truncate">{e}</span>
                                    <Button variant="ghost" size="icon" onClick={() => setFirstOrderEffects(prev => prev.filter((_, idx) => idx !== i))}>×</Button>
                                  </div>
                                ))}
                              </div>
                            </div>
                            <div className="p-2 rounded border">
                              <div className="text-xs font-semibold mb-1">2nd Order</div>
                              <div className="space-y-1">
                                {secondOrderEffects.map((e, i) => (
                                  <div key={`s-${i}`} className="flex items-center justify-between bg-slate-50 dark:bg-slate-700/50 p-1 rounded text-sm">
                                    <span className="truncate">{e}</span>
                                    <Button variant="ghost" size="icon" onClick={() => setSecondOrderEffects(prev => prev.filter((_, idx) => idx !== i))}>×</Button>
                                  </div>
                                ))}
                              </div>
                            </div>
                            <div className="p-2 rounded border">
                              <div className="text-xs font-semibold mb-1">3rd Order</div>
                              <div className="space-y-1">
                                {thirdOrderEffects.map((e, i) => (
                                  <div key={`t-${i}`} className="flex items-center justify-between bg-slate-50 dark:bg-slate-700/50 p-1 rounded text-sm">
                                    <span className="truncate">{e}</span>
                                    <Button variant="ghost" size="icon" onClick={() => setThirdOrderEffects(prev => prev.filter((_, idx) => idx !== i))}>×</Button>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                          {/* Compact causal chain visualization */}
                          {(firstOrderEffects.length + secondOrderEffects.length + thirdOrderEffects.length) > 0 && (
                            <div className="mt-2 p-3 bg-slate-50 dark:bg-slate-800 rounded">
                              <div className="text-xs mb-2 text-slate-600 dark:text-slate-400">Causal Chain</div>
                              <div className="flex items-start gap-2 text-xs overflow-x-auto">
                                <div className="min-w-[180px]">
                                  {firstOrderEffects.map((e, i) => (
                                    <div key={`vf-${i}`} className="px-2 py-1 mb-1 bg-white dark:bg-slate-700 rounded border">{e}</div>
                                  ))}
                                </div>
                                <div className="self-center">➡️</div>
                                <div className="min-w-[180px]">
                                  {secondOrderEffects.map((e, i) => (
                                    <div key={`vs-${i}`} className="px-2 py-1 mb-1 bg-white dark:bg-slate-700 rounded border">{e}</div>
                                  ))}
                                </div>
                                <div className="self-center">➡️</div>
                                <div className="min-w-[180px]">
                                  {thirdOrderEffects.map((e, i) => (
                                    <div key={`vt-${i}`} className="px-2 py-1 mb-1 bg-white dark:bg-slate-700 rounded border">{e}</div>
                                  ))}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                        <Button 
                          onClick={createScenario} 
                          disabled={loading || !scenarioName.trim() || !triggerEvent.trim()}
                          className="w-full"
                        >
                          {loading ? 'Creating...' : 'Create Scenario'}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  {/* User Interests */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Your Interests</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {userInterests.length === 0 ? (
                          <p className="text-gray-500 text-sm">No interests configured</p>
                        ) : (
                          userInterests.map((interest) => (
                            <div key={interest.id} className="flex items-center justify-between">
                              <span className="text-sm">{interest.interest_value}</span>
                              <Badge variant={interest.priority_level > 3 ? 'default' : 'secondary'}>
                                Priority {interest.priority_level}
                              </Badge>
                            </div>
                          ))
                        )}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Existing Scenarios */}
                  <Card className="lg:col-span-2">
                    <CardHeader>
                      <CardTitle>Existing Scenarios</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        {scenarios.length === 0 ? (
                          <p className="text-gray-500 text-sm">No scenarios created yet</p>
                        ) : (
                          scenarios.map((scenario) => (
                            <Card key={scenario.id} className="p-4">
                              <h4 className="font-semibold mb-2">{scenario.scenario_name}</h4>
                              <p className="text-sm text-gray-600 mb-3">{scenario.trigger_event}</p>
                              <div className="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                  <span className="text-gray-500">Probability:</span>
                                  <Badge className="ml-2">{(scenario.probability_score * 100).toFixed(0)}%</Badge>
                                </div>
                                <div>
                                  <span className="text-gray-500">Impact:</span>
                                  <Badge className="ml-2">{(scenario.impact_score * 100).toFixed(0)}%</Badge>
                                </div>
                              </div>
                              {scenario.first_order_effects && (
                                <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                                  <p className="text-xs font-semibold text-gray-700 mb-1">First Order Effects:</p>
                                  <p className="text-xs text-gray-600">{scenario.first_order_effects}</p>
                                </div>
                              )}
                            </Card>
                          ))
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              {/* Query Engine Tab */}
              <TabsContent value="query" className="space-y-4">
                <OnboardingHelper section="query" />
                <Card>
                  <CardHeader>
                    <CardTitle>Intelligence Query Engine</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium mb-1">Your Question</label>
                        <Input
                          placeholder="Ask anything about markets, geopolitics, or strategic decisions..."
                          value={queryText}
                          onChange={(e) => setQueryText(e.target.value)}
                          onKeyPress={(e) => e.key === 'Enter' && submitQuery()}
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">Query Type</label>
                        <select
                          className="w-full p-2 border rounded-md"
                          value={queryType}
                          onChange={(e) => setQueryType(e.target.value)}
                        >
                          <option value="general">General</option>
                          <option value="market">Market Analysis</option>
                          <option value="geopolitical">Geopolitical</option>
                          <option value="scenario">Scenario Analysis</option>
                        </select>
                      </div>
                      <Button 
                        onClick={submitQuery} 
                        disabled={loading || !queryText.trim()}
                        className="w-full"
                      >
                        {loading ? 'Analyzing...' : 'Submit Query'}
                      </Button>
                    </div>

                    {queryResult && (
                      <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                        <h4 className="font-semibold mb-3">Analysis Result</h4>
                        <div className="space-y-4">
                          {queryResult.synthesis && (
                            <div>
                              <h5 className="text-sm font-medium text-gray-700 mb-1">Synthesis</h5>
                              <p className="text-sm text-gray-600">{queryResult.synthesis}</p>
                            </div>
                          )}
                          {queryResult.recommendations && (
                            <div>
                              <h5 className="text-sm font-medium text-gray-700 mb-1">Recommendations</h5>
                              <ul className="list-disc list-inside text-sm text-gray-600">
                                {queryResult.recommendations.map((rec: string, index: number) => (
                                  <li key={index}>{rec}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChimeraCockpit; 