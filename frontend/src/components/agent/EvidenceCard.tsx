import React, { useState } from 'react';
import { BookOpen, CheckCircle2, ChevronDown, ChevronUp, Database, ExternalLink, ShieldAlert, Tag } from 'lucide-react';
import type { EvidenceItem } from '../../api/types';

interface EvidenceCardProps {
  item: EvidenceItem;
  isCited?: boolean;
}

export const EvidenceCard: React.FC<EvidenceCardProps> = ({ item, isCited = false }) => {
  const [showMetadata, setShowMetadata] = useState(false);

  // Normalize score into percentage display
  const scorePercent = Math.round(item.retrieval_score * 100);
  const isStrong = item.retrieval_score >= 0.5;

  return (
    <div
      className={`p-4 rounded-xl border transition-all ${
        isCited
          ? 'bg-slate-900/90 border-indigo-500/50 shadow-md shadow-indigo-500/10'
          : 'bg-slate-950/80 border-slate-800'
      }`}
    >
      {/* Card Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 text-[11px] font-mono font-semibold bg-slate-800 text-indigo-300 rounded border border-slate-700">
            {item.faq_id}
          </span>
          {isCited && (
            <span className="px-2 py-0.5 text-[10px] font-bold bg-indigo-950 text-indigo-300 rounded-full border border-indigo-800 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-indigo-400" />
              Cited in Draft
            </span>
          )}
        </div>
        <span
          className={`px-2 py-0.5 text-[11px] font-medium rounded-full flex items-center gap-1 ${
            isStrong
              ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/60'
              : 'bg-amber-950/80 text-amber-300 border border-amber-800/60'
          }`}
        >
          {isStrong ? <CheckCircle2 className="w-3 h-3" /> : <ShieldAlert className="w-3 h-3" />}
          {isStrong ? 'Strong Support' : 'Weak Support'}
        </span>
      </div>

      {/* FAQ Question & Answer */}
      <div className="space-y-2 mb-3">
        <h4 className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
          <BookOpen className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
          {item.question}
        </h4>
        <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
          {item.answer}
        </p>
      </div>

      {/* Metadata Badges */}
      <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400 mb-2">
        {item.source && (
          <span className="px-2 py-0.5 bg-slate-800/60 rounded text-slate-300 flex items-center gap-1">
            <ExternalLink className="w-3 h-3 text-slate-400" />
            {item.source}
          </span>
        )}
        {item.product && (
          <span className="px-2 py-0.5 bg-slate-800/60 rounded text-slate-300">
            {item.product}
          </span>
        )}
        {item.version && (
          <span className="px-2 py-0.5 bg-slate-800/60 rounded text-slate-400 font-mono text-[10px]">
            {item.version}
          </span>
        )}
        {item.tags && item.tags.length > 0 && (
          <span className="px-2 py-0.5 bg-slate-800/60 rounded text-slate-400 flex items-center gap-1">
            <Tag className="w-3 h-3" />
            {item.tags.slice(0, 2).join(', ')}
          </span>
        )}
      </div>

      {/* Expandable Technical Retrieval Trace */}
      <button
        onClick={() => setShowMetadata(!showMetadata)}
        className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1 transition-colors font-mono pt-1 border-t border-slate-800/60 w-full justify-between"
      >
        <span className="flex items-center gap-1">
          <Database className="w-3 h-3 text-slate-500" />
          Retrieval Details
        </span>
        {showMetadata ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>

      {showMetadata && (
        <div className="mt-2 p-2.5 bg-slate-950 rounded-lg border border-slate-800 font-mono text-[10px] space-y-1 text-slate-400">
          <div className="flex justify-between">
            <span>Retrieval Stage:</span>
            <span className="text-slate-200">{item.retrieval_stage}</span>
          </div>
          <div className="flex justify-between">
            <span>Stage Rank:</span>
            <span className="text-slate-200">#{item.retrieval_rank}</span>
          </div>
          <div className="flex justify-between">
            <span>Stage Score:</span>
            <span className="text-slate-200">{item.retrieval_score.toFixed(4)} ({scorePercent}%)</span>
          </div>
        </div>
      )}
    </div>
  );
};
