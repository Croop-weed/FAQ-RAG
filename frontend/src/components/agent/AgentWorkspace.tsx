import React, { useState } from 'react';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronUp,
  Clock,
  Edit3,
  Info,
  RefreshCw,
  Send,
  ShieldAlert,
  Sparkles,
  User,
  XCircle,
} from 'lucide-react';
import type { Ticket } from '../../api/types';
import { EvidenceCard } from './EvidenceCard';
import { InboxQueue } from './InboxQueue';

interface AgentWorkspaceProps {
  tickets: Ticket[];
  onSendResponse: (ticketId: string, finalAnswer: string) => void;
  onRejectDraft: (ticketId: string) => void;
  onRegenerateDraft: (ticketId: string) => Promise<void>;
}

export const AgentWorkspace: React.FC<AgentWorkspaceProps> = ({
  tickets,
  onSendResponse,
  onRejectDraft,
  onRegenerateDraft,
}) => {
  const [selectedTicketId, setSelectedTicketId] = useState<string>(tickets[0]?.id || '');
  const [filter, setFilter] = useState<'all' | 'review' | 'gap' | 'resolved'>('all');
  // Per-ticket edits: maps ticket id → agent-edited text
  const [editedAnswers, setEditedAnswers] = useState<Record<string, string>>({});
  const [showConfidenceDetails, setShowConfidenceDetails] = useState<boolean>(false);
  const [isRegenerating, setIsRegenerating] = useState<boolean>(false);

  const ticket = tickets.find((t) => t.id === selectedTicketId) || tickets[0];
  const evalDraft = ticket?.evaluated_draft;
  const decision = evalDraft?.decision ?? 'review';
  const confidencePercent = evalDraft?.confidence ? Math.round(evalDraft.confidence * 100) : 0;
  const evidenceList = evalDraft?.grounded_draft?.provided_evidence ?? [];
  const citations = evalDraft?.citations ?? [];
  const citedIds = citations.map((c) => c.faq_id);

  // Current text in the editor: prefer agent-edited override, then AI draft
  const currentAnswer = ticket
    ? (editedAnswers[ticket.id] ?? evalDraft?.answer ?? '')
    : '';

  const isEditedByAgent =
    ticket !== undefined &&
    editedAnswers[ticket.id] !== undefined &&
    editedAnswers[ticket.id] !== (evalDraft?.answer ?? '');

  const handleAnswerChange = (value: string) => {
    if (!ticket) return;
    setEditedAnswers((prev) => ({ ...prev, [ticket.id]: value }));
  };

  const handleSend = () => {
    if (!ticket) return;
    onSendResponse(ticket.id, currentAnswer);
  };

  const handleRegenerate = async () => {
    if (!ticket || isRegenerating) return;
    setIsRegenerating(true);
    // Clear agent edit so regenerated draft shows cleanly
    setEditedAnswers((prev) => {
      const next = { ...prev };
      delete next[ticket.id];
      return next;
    });
    try {
      await onRegenerateDraft(ticket.id);
    } finally {
      setIsRegenerating(false);
    }
  };

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col md:flex-row bg-slate-950 overflow-hidden">
      {/* LEFT COLUMN: Queue / Inbox (~320px) */}
      <div className="w-full md:w-80 lg:w-96 flex-shrink-0 h-64 md:h-full">
        <InboxQueue
          tickets={tickets}
          selectedTicketId={selectedTicketId}
          onSelectTicket={(t) => {
            setSelectedTicketId(t.id);
            setShowConfidenceDetails(false);
          }}
          filter={filter}
          onFilterChange={setFilter}
        />
      </div>

      {/* CENTER COLUMN: Customer Question & AI Draft */}
      {ticket ? (
        <div className="flex-1 flex flex-col h-full border-r border-slate-800 bg-slate-900/30 overflow-y-auto">
          {/* Customer Query Header */}
          <div className="p-4 bg-slate-900 border-b border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full bg-slate-800 flex items-center justify-center text-slate-300">
                  <User className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-slate-200">{ticket.customer_name}</h3>
                  <p className="text-[11px] text-slate-400">{ticket.customer_email}</p>
                </div>
              </div>
              <span className="text-[11px] text-slate-500 font-mono">ID: {ticket.id}</span>
            </div>

            {/* Customer Question Banner */}
            <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                Customer Question
              </span>
              <p className="text-xs sm:text-sm font-medium text-slate-100 leading-relaxed">
                &ldquo;{ticket.question}&rdquo;
              </p>
            </div>
          </div>

          {/* AI Draft & Decision Workspace */}
          <div className="p-4 space-y-4 flex-1">
            {/* Decision Status Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-900 rounded-xl border border-slate-800">
              {/* Decision Badge */}
              <div className="flex items-center gap-2">
                {decision === 'accept' && (
                  <span className="px-3 py-1 text-xs font-bold bg-emerald-950 text-emerald-300 rounded-lg border border-emerald-800/80 flex items-center gap-1.5 shadow-sm">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ✓ Strongly Supported
                  </span>
                )}
                {decision === 'review' && (
                  <span className="px-3 py-1 text-xs font-bold bg-amber-950 text-amber-300 rounded-lg border border-amber-800/80 flex items-center gap-1.5 shadow-sm">
                    <Clock className="w-4 h-4 text-amber-400" />
                    ! Review Recommended
                  </span>
                )}
                {decision === 'abstain' && (
                  <span className="px-3 py-1 text-xs font-bold bg-red-950 text-red-300 rounded-lg border border-red-800/80 flex items-center gap-1.5 shadow-sm">
                    <AlertTriangle className="w-4 h-4 text-red-400" />
                    ⚠ Insufficient Knowledge
                  </span>
                )}
              </div>

              {/* Confidence Indicator */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Support Confidence:</span>
                <span className="text-xs font-bold text-slate-200 bg-slate-950 px-2.5 py-1 rounded-md border border-slate-800">
                  {decision === 'abstain' ? 'Low' : `${confidencePercent}%`}
                </span>
                <button
                  onClick={() => setShowConfidenceDetails(!showConfidenceDetails)}
                  className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 underline underline-offset-2"
                >
                  <Info className="w-3.5 h-3.5" />
                  Why?
                </button>
              </div>
            </div>

            {/* Expandable Confidence Signal Breakdown */}
            {showConfidenceDetails && evalDraft && (
              <div className="p-3.5 bg-slate-950 rounded-xl border border-slate-800 space-y-2 text-xs">
                <div className="flex justify-between items-center border-b border-slate-800 pb-2">
                  <span className="font-bold text-slate-200 flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-indigo-400" />
                    Confidence Evaluation Signal Breakdown
                  </span>
                  <button
                    onClick={() => setShowConfidenceDetails(false)}
                    className="text-slate-500 hover:text-slate-300"
                  >
                    <ChevronUp className="w-4 h-4" />
                  </button>
                </div>
                <div className="space-y-1.5 font-mono text-[11px] text-slate-300">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>
                      Reranker Evidence Score:{' '}
                      {String(evalDraft.confidence_assessment?.metadata?.top_reranker_score ?? 'N/A')}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>
                      Citation Validity: 100% ({citations.length} cited FAQ
                      {citations.length !== 1 ? 's' : ''})
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {evalDraft.confidence_assessment?.weak_evidence_indicators?.length === 0 ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                    )}
                    <span>
                      {evalDraft.confidence_assessment?.weak_evidence_indicators?.length === 0
                        ? 'No unsupported claims detected in answer text'
                        : `${evalDraft.confidence_assessment.weak_evidence_indicators.length} risk indicator(s) flagged`}
                    </span>
                  </div>
                  {evalDraft.reason && (
                    <p className="mt-2 text-[11px] text-slate-400 font-sans italic border-t border-slate-800/80 pt-1.5">
                      &ldquo;{evalDraft.reason}&rdquo;
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Evidence Risk Indicators Warning */}
            {evalDraft?.confidence_assessment?.weak_evidence_indicators &&
              evalDraft.confidence_assessment.weak_evidence_indicators.length > 0 && (
                <div className="p-3 bg-amber-950/40 border border-amber-800/50 rounded-xl text-amber-200 text-xs space-y-1">
                  <div className="flex items-center gap-1.5 font-semibold text-amber-300">
                    <ShieldAlert className="w-4 h-4 text-amber-400" />
                    <span>Evidence Risk Indicators Flagged by AI</span>
                  </div>
                  <ul className="list-disc list-inside space-y-0.5 text-slate-300 text-[11px]">
                    {evalDraft.confidence_assessment.weak_evidence_indicators.map((ind, idx) => (
                      <li key={idx}>{ind}</li>
                    ))}
                  </ul>
                </div>
              )}

            {/* Knowledge Gap Abstention Banner */}
            {decision === 'abstain' && (
              <div className="p-4 bg-red-950/40 border border-red-800/60 rounded-xl text-red-200 text-xs space-y-2">
                <div className="flex items-center gap-2 font-bold text-red-300 text-sm">
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                  <span>Knowledge Gap Detected</span>
                </div>
                <p className="text-slate-300 leading-relaxed">
                  The knowledge base does not contain enough verified information to confidently
                  answer this customer inquiry.
                </p>
                <p className="text-[11px] text-slate-400 font-mono">
                  Reason: {evalDraft?.reason || 'Low reranker score / no matching FAQ found.'}
                </p>
              </div>
            )}

            {/* Draft Answer Editor */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Edit3 className="w-3.5 h-3.5 text-indigo-400" />
                  AI Suggested Response Draft
                </label>
                {isEditedByAgent && (
                  <span className="px-2 py-0.5 text-[10px] font-bold bg-indigo-950 text-indigo-300 rounded border border-indigo-800">
                    Edited by Agent
                  </span>
                )}
              </div>

              <textarea
                value={currentAnswer}
                onChange={(e) => handleAnswerChange(e.target.value)}
                placeholder={
                  decision === 'abstain'
                    ? 'Write a custom response manually based on agent verification...'
                    : 'Edit AI draft before sending to customer...'
                }
                rows={6}
                className="w-full bg-slate-950 text-slate-100 text-xs sm:text-sm rounded-xl p-3.5 border border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 resize-y leading-relaxed font-sans"
              />
            </div>

            {/* Action Buttons Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex items-center gap-2">
                <button
                  onClick={handleRegenerate}
                  disabled={isRegenerating || ticket.status === 'sent'}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 text-xs font-medium rounded-lg border border-slate-700 transition-all flex items-center gap-1.5"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isRegenerating ? 'animate-spin' : ''}`} />
                  {isRegenerating ? 'Regenerating...' : 'Regenerate'}
                </button>
                <button
                  onClick={() => onRejectDraft(ticket.id)}
                  disabled={ticket.status === 'sent'}
                  className="px-3 py-2 bg-slate-900 hover:bg-red-950/60 disabled:opacity-50 text-slate-400 hover:text-red-300 text-xs font-medium rounded-lg border border-slate-800 transition-all flex items-center gap-1.5"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  Reject Draft
                </button>
              </div>

              <button
                onClick={handleSend}
                disabled={!currentAnswer.trim() || ticket.status === 'sent'}
                className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600 text-white font-bold text-xs rounded-xl transition-all shadow-md shadow-emerald-600/30 flex items-center gap-2"
              >
                <Send className="w-4 h-4" />
                {ticket.status === 'sent' ? 'Response Sent ✓' : 'Approve & Send to Customer'}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 p-8 text-center text-slate-500 text-xs flex items-center justify-center">
          Select a customer ticket from the inbox to review AI draft &amp; evidence.
        </div>
      )}

      {/* RIGHT COLUMN: Knowledge Base Evidence Panel */}
      <div className="w-full md:w-80 lg:w-96 bg-slate-950 p-4 border-t md:border-t-0 md:border-l border-slate-800 flex flex-col h-64 md:h-full overflow-y-auto space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-indigo-400" />
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
              Retrieved Evidence ({evidenceList.length})
            </h3>
          </div>
        </div>

        {evidenceList.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-500 bg-slate-900/40 rounded-xl border border-slate-800">
            No FAQ evidence was retrieved for this inquiry.
          </div>
        ) : (
          evidenceList.map((item) => (
            <EvidenceCard
              key={item.faq_id}
              item={item}
              isCited={citedIds.includes(item.faq_id)}
            />
          ))
        )}
      </div>
    </div>
  );
};
