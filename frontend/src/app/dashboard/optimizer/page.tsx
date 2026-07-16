'use client';

import React, { useState } from 'react';
import { ComparisonBlock } from '@/features/optimizer';
import ScoreSection from '@/features/optimizer/components/ScoreSection';

export default function OptimizerPage() {
  const [isAnalyzing,  setIsAnalyzing]  = useState(false);
  const [isAnalyzed,   setIsAnalyzed]   = useState(false);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [isOptimized,  setIsOptimized]  = useState(false);

  const handleAnalyze = () => {
    setIsAnalyzing(true);
    setIsAnalyzed(false);
    setIsOptimized(false);
    setTimeout(() => { setIsAnalyzing(false); setIsAnalyzed(true); }, 2200);
  };

  const handleOptimize = () => {
    setIsOptimizing(true);
    setTimeout(() => { setIsOptimizing(false); setIsOptimized(true); }, 2800);
  };

  return (
    <div className="workspace-container">
      <ComparisonBlock
        isAnalyzing={isAnalyzing}
        isAnalyzed={isAnalyzed}
        isOptimizing={isOptimizing}
        isOptimized={isOptimized}
        onAnalyze={handleAnalyze}
        onOptimize={handleOptimize}
      />
      {isOptimized && <ScoreSection isAnalyzed={isAnalyzed} isOptimized={isOptimized} />}
    </div>
  );
}
