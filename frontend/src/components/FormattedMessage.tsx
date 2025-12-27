import React from 'react';

type FormattedMessageProps = {
  text: string;
};

// Helper to render inline citations like [1], [2,3]
function renderInlineCitations(line: string): React.ReactNode[] {
  const parts = line.split(/(\[[0-9,\s]+\])/g);
  return parts.map((part, idx) => {
    if (/^\[[0-9,\s]+\]$/.test(part)) {
      return (
        <span key={idx} className="font-semibold text-blue-600 dark:text-blue-400">
          {part}
        </span>
      );
    }
    return <React.Fragment key={idx}>{renderInlineBold(part)}</React.Fragment>;
  });
}

// Enhanced bold parsing for **bold** and *bold* tokens
function renderInlineBold(line: string): React.ReactNode[] {
  const parts = line.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts.map((part, idx) => {
    // Handle **bold** format
    const boldMatch = part.match(/^\*\*([^*]+)\*\*$/);
    if (boldMatch) {
      return (
        <strong key={idx} className="font-bold">
          {boldMatch[1]}
        </strong>
      );
    }
    
    // Handle *bold* format
    const italicBoldMatch = part.match(/^\*([^*]+)\*$/);
    if (italicBoldMatch) {
      return (
        <strong key={idx} className="font-bold">
          {italicBoldMatch[1]}
        </strong>
      );
    }
    
    return <React.Fragment key={idx}>{part}</React.Fragment>;
  });
}

export default function FormattedMessage({ text }: FormattedMessageProps) {
  // Handle undefined or null text
  if (!text || text === '') {
    return null;
  }
  
  // Normalize line endings and trim
  const lines = text.replace(/\r\n/g, '\n').split('\n');

  const blocks: Array<
    | { type: 'heading'; content: string }
    | { type: 'ul'; items: string[] }
    | { type: 'ol'; items: string[] }
    | { type: 'para'; content: string }
  > = [];

  let currentUL: string[] | null = null;
  let currentOL: string[] | null = null;

  const flushLists = () => {
    if (currentUL && currentUL.length) {
      blocks.push({ type: 'ul', items: currentUL });
    }
    if (currentOL && currentOL.length) {
      blocks.push({ type: 'ol', items: currentOL });
    }
    currentUL = null;
    currentOL = null;
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      flushLists();
      continue;
    }

    // Headings like "Key Insights:" or any sentence ending with ':'
    if (/^[A-Z][A-Za-z\s\-/&]+:\s*$/.test(line)) {
      flushLists();
      blocks.push({ type: 'heading', content: line.replace(/:\s*$/, '') });
      continue;
    }

    // Unordered list marker
    if (/^[-•]\s+/.test(line)) {
      if (!currentUL) {
        flushLists();
        currentUL = [];
      }
      currentUL.push(line.replace(/^[-•]\s+/, ''));
      continue;
    }

    // Ordered list marker (1. 2) etc.)
    if (/^\d+[\.)]\s+/.test(line)) {
      if (!currentOL) {
        flushLists();
        currentOL = [];
      }
      currentOL.push(line.replace(/^\d+[\.)]\s+/, ''));
      continue;
    }

    // Continuation of previous list item starting with en dash style hyphen
    if (/^—\s+/.test(line)) {
      if (currentUL && currentUL.length > 0) {
        currentUL[currentUL.length - 1] += ' ' + line.replace(/^—\s+/, '');
        continue;
      }
      if (currentOL && currentOL.length > 0) {
        currentOL[currentOL.length - 1] += ' ' + line.replace(/^—\s+/, '');
        continue;
      }
    }

    flushLists();
    blocks.push({ type: 'para', content: line });
  }
  flushLists();

  return (
    <div className="space-y-2">
      {blocks.map((b, i) => {
        if (b.type === 'heading') {
          return (
            <div key={i} className="mt-1 mb-1 font-bold text-slate-900 dark:text-slate-100">
              {renderInlineCitations(b.content)}
            </div>
          );
        }
        if (b.type === 'ul') {
          return (
            <ul key={i} className="list-disc pl-5 space-y-1">
              {b.items.map((it, j) => (
                <li key={j} className="marker:text-slate-400">
                  {renderInlineCitations(it)}
                </li>
              ))}
            </ul>
          );
        }
        if (b.type === 'ol') {
          return (
            <ol key={i} className="list-decimal pl-5 space-y-1">
              {b.items.map((it, j) => (
                <li key={j} className="marker:text-slate-400">
                  {renderInlineCitations(it)}
                </li>
              ))}
            </ol>
          );
        }
        return (
          <p key={i} className="leading-relaxed">
            {renderInlineCitations(b.content)}
          </p>
        );
      })}
    </div>
  );
}
