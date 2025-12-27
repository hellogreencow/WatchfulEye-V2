import React from 'react';
import WatchfulEyeLogo from './components/WatchfulEyeLogo';
import { Button } from './components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card';
import { Input } from './components/ui/input';
import { Badge } from './components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { ExpandedArticleCard } from './components/ArticleCard';
import FormattedMessage from './components/FormattedMessage';
import { cn } from './lib/utils';
import { Moon, Sun, Search, Sparkles, ShieldCheck, TrendingUp } from 'lucide-react';

type PreviewArticle = {
  id: number;
  title: string;
  source: string;
  url?: string;
  description?: string;
  sentiment_score?: number;
  sentiment_confidence?: number;
  category?: string;
  created_at?: string;
};

const SAMPLE_ARTICLES: PreviewArticle[] = [
  {
    id: 1,
    title: 'GPU efficiency breakthroughs reshape edge inference economics',
    source: 'The Verge',
    url: 'https://example.com/article-1',
    description:
      'A wave of compiler-level optimizations and model sparsity techniques is pushing useful inference to smaller devices without the usual quality collapse.',
    sentiment_score: 0.42,
    sentiment_confidence: 0.78,
    category: 'AI Infrastructure',
    created_at: new Date(Date.now() - 1000 * 60 * 42).toISOString(),
  },
  {
    id: 2,
    title: 'Regulators converge on disclosure rules for synthetic media',
    source: 'Financial Times',
    url: 'https://example.com/article-2',
    description:
      'New proposals standardize watermarking, provenance metadata, and platform responsibility, with material impact to newsrooms and creators.',
    sentiment_score: -0.18,
    sentiment_confidence: 0.63,
    category: 'Policy',
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(),
  },
  {
    id: 3,
    title: 'Enterprise search shifts from keyword to “answer engines”',
    source: 'Wired',
    url: 'https://example.com/article-3',
    description:
      'RAG-first UX patterns are hardening: evidence chips, query rewrites, and trust layers become table-stakes for internal knowledge tools.',
    sentiment_score: 0.12,
    sentiment_confidence: 0.71,
    category: 'Product',
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 28).toISOString(),
  },
];

const SAMPLE_ASSISTANT_TEXT =
  "Key Insights:\n" +
  "- The market is rewarding *distribution + trust*, not just model quality.\n" +
  "- Evidence UI (citations [1,2]) is becoming a competitive moat.\n" +
  "- Near-term risk: synthetic media disclosure rules will force costly provenance pipelines.\n\n" +
  "Actionable Next Steps:\n" +
  "1. Tighten the citation UX into compact chips + hover previews.\n" +
  "2. Add a lightweight provenance score per article.\n" +
  "3. Ship a “Figma-ready” design token set for rapid iteration.";

export default function FigmaPreview() {
  const [tab, setTab] = React.useState<'news' | 'saved' | 'insights'>('news');
  const [dark, setDark] = React.useState<boolean>(() =>
    typeof document !== 'undefined' ? document.documentElement.classList.contains('dark') : false
  );
  const [query, setQuery] = React.useState('edge inference economics');

  React.useEffect(() => {
    const root = document.documentElement;
    if (dark) root.classList.add('dark');
    else root.classList.remove('dark');
  }, [dark]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      <div className="w-full px-4 sm:px-6 lg:px-10 py-8">
        <div className="flex items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <WatchfulEyeLogo size={26} textClassName="text-2xl text-slate-900 dark:text-slate-100" />
            <Badge className="bg-indigo-600 text-white hover:bg-indigo-600">Figma Preview</Badge>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setDark(false)} className={cn(!dark && 'bg-white')}>
              <Sun className="w-4 h-4 mr-2" />
              Light
            </Button>
            <Button variant="outline" onClick={() => setDark(true)} className={cn(dark && 'bg-white/10')}>
              <Moon className="w-4 h-4 mr-2" />
              Dark
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: primary content */}
          <div className="lg:col-span-8 space-y-6">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-xl">Market Feed</CardTitle>
                    <CardDescription>Static preview data for design work in Figma.</CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      Trust layer
                    </Badge>
                    <Badge variant="secondary" className="gap-1">
                      <TrendingUp className="w-3.5 h-3.5" />
                      Sentiment
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex flex-col sm:flex-row gap-2">
                  <div className="relative flex-1">
                    <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <Input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      className="pl-9"
                      placeholder="Search articles, companies, topics…"
                    />
                  </div>
                  <Button className="sm:w-auto">
                    <Sparkles className="w-4 h-4 mr-2" />
                    Refine
                  </Button>
                </div>

                <div className="mt-4">
                  <Tabs value={tab} onValueChange={(v) => setTab(v as any)}>
                    <TabsList>
                      <TabsTrigger value="news">News</TabsTrigger>
                      <TabsTrigger value="saved">Saved</TabsTrigger>
                      <TabsTrigger value="insights">Insights</TabsTrigger>
                    </TabsList>

                    <TabsContent value="news" className="mt-4">
                      <div className="space-y-3">
                        {SAMPLE_ARTICLES.map((a) => (
                          <ExpandedArticleCard
                            key={a.id}
                            source={a}
                            onAnalyze={() => {}}
                            onSave={() => {}}
                            isSaved={a.id === 2}
                          />
                        ))}
                      </div>
                    </TabsContent>

                    <TabsContent value="saved" className="mt-4">
                      <div className="space-y-3">
                        <ExpandedArticleCard source={SAMPLE_ARTICLES[1]} onAnalyze={() => {}} onSave={() => {}} isSaved />
                      </div>
                    </TabsContent>

                    <TabsContent value="insights" className="mt-4">
                      <Card className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20">
                        <CardHeader>
                          <CardTitle className="text-lg">Weekly Signal</CardTitle>
                          <CardDescription>Example analysis output formatting.</CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed">
                            <FormattedMessage text={SAMPLE_ASSISTANT_TEXT} />
                          </div>
                        </CardContent>
                      </Card>
                    </TabsContent>
                  </Tabs>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right: sidebar */}
          <div className="lg:col-span-4 space-y-6">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Snapshot</CardTitle>
                <CardDescription>High-level KPIs (mock).</CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-3 bg-white/50 dark:bg-slate-900/40">
                  <div className="text-xs text-slate-500 dark:text-slate-400">Articles</div>
                  <div className="text-2xl font-semibold text-slate-900 dark:text-slate-100">1,248</div>
                </div>
                <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-3 bg-white/50 dark:bg-slate-900/40">
                  <div className="text-xs text-slate-500 dark:text-slate-400">Analyses</div>
                  <div className="text-2xl font-semibold text-slate-900 dark:text-slate-100">312</div>
                </div>
                <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-3 bg-white/50 dark:bg-slate-900/40">
                  <div className="text-xs text-slate-500 dark:text-slate-400">Positive</div>
                  <div className="text-2xl font-semibold text-green-600">54%</div>
                </div>
                <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-3 bg-white/50 dark:bg-slate-900/40">
                  <div className="text-xs text-slate-500 dark:text-slate-400">Negative</div>
                  <div className="text-2xl font-semibold text-red-600">18%</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Design Notes</CardTitle>
                <CardDescription>What to copy into Figma.</CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed space-y-2">
                <div>
                  <span className="font-semibold">Typography:</span> system stack + tight tracking (see `index.css`).
                </div>
                <div>
                  <span className="font-semibold">Color tokens:</span> CSS variables (HSL) for light/dark theme.
                </div>
                <div>
                  <span className="font-semibold">Components:</span> cards, badges, tabs, article cards, evidence chips.
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}


