import React, { useState } from 'react';
import { Clock, HelpCircle, Loader2, MessageSquare, Send, ShieldAlert, Sparkles, UserCheck } from 'lucide-react';
import type { Ticket } from '../../api/types';

interface CustomerPortalProps {
  onSubmitQuestion: (question: string) => Promise<Ticket>;
  activeTicket: Ticket | null;
}

export const CustomerPortal: React.FC<CustomerPortalProps> = ({
  onSubmitQuestion,
  activeTicket,
}) => {
  const [inputQuery, setInputQuery] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentTicket, setCurrentTicket] = useState<Ticket | null>(activeTicket);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const suggestedQuestions = [
    'How do I reset my password?',
    'Where can I find my monthly invoices?',
    'How do I update my billing information?',
    'What is the refund policy for annual subscriptions?',
  ];

  const handleSubmit = async (queryToSubmit: string) => {
    const q = queryToSubmit.trim();
    if (!q || isSubmitting) return;

    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const ticket = await onSubmitQuestion(q);
      setCurrentTicket(ticket);
      setInputQuery('');
    } catch (err) {
      console.error(err);
      setErrorMessage("We couldn't process your request right now. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
      {/* Header section */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-950/80 border border-indigo-800/50 text-indigo-300 text-xs font-medium">
          <HelpCircle className="w-3.5 h-3.5 text-indigo-400" />
          <span>Orbit Desk Help & Support</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-100 tracking-tight">
          How can we help you today?
        </h1>
        <p className="text-slate-400 text-sm max-w-lg mx-auto">
          Ask a question about your account, billing, or product features. Our support team will review and assist you promptly.
        </p>
      </div>

      {/* Suggested Questions Chips */}
      {!currentTicket && (
        <div className="space-y-3">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider text-center">
            Suggested Questions
          </p>
          <div className="flex flex-wrap gap-2 justify-center">
            {suggestedQuestions.map((sq, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setInputQuery(sq);
                  handleSubmit(sq);
                }}
                disabled={isSubmitting}
                className="px-3.5 py-2 text-xs font-medium bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white rounded-xl border border-slate-800 hover:border-slate-700 transition-all flex items-center gap-1.5 shadow-sm"
              >
                <Sparkles className="w-3 h-3 text-indigo-400" />
                {sq}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Question Input Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit(inputQuery);
        }}
        className="bg-slate-900 p-3 rounded-2xl border border-slate-800 shadow-xl space-y-3"
      >
        <div className="relative">
          <textarea
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            placeholder="Type your question here..."
            rows={3}
            disabled={isSubmitting}
            className="w-full bg-slate-950 text-slate-100 placeholder-slate-500 text-sm rounded-xl p-3.5 border border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 resize-none"
          />
        </div>
        <div className="flex justify-between items-center px-1">
          <span className="text-xs text-slate-500">
            All AI suggestions are verified by a support specialist before sending.
          </span>
          <button
            type="submit"
            disabled={!inputQuery.trim() || isSubmitting}
            className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white font-medium text-xs rounded-xl transition-all shadow-md shadow-indigo-600/30 flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Submitting...
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                Send Question
              </>
            )}
          </button>
        </div>
      </form>

      {/* Error state alert */}
      {errorMessage && (
        <div className="p-4 bg-red-950/60 border border-red-800/50 rounded-xl text-red-200 text-xs flex items-start gap-3">
          <ShieldAlert className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-red-300">Submission Error</p>
            <p>{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Active Conversation View */}
      {currentTicket && (
        <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-6 space-y-6 shadow-2xl">
          <div className="flex justify-between items-center border-b border-slate-800 pb-4">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-indigo-400" />
              <span className="text-sm font-semibold text-slate-200">Ticket #{currentTicket.id}</span>
            </div>
            <span className="text-xs text-slate-500">{currentTicket.created_at}</span>
          </div>

          <div className="space-y-4">
            {/* Customer Bubble (Right Aligned) */}
            <div className="flex justify-end">
              <div className="max-w-md bg-indigo-600 text-white p-4 rounded-2xl rounded-tr-none text-sm shadow-md">
                <p className="text-xs font-semibold text-indigo-200 mb-1">You asked:</p>
                <p>{currentTicket.question}</p>
              </div>
            </div>

            {/* Support Response States (Left Aligned) */}
            <div className="flex justify-start">
              <div className="max-w-xl w-full">
                {currentTicket.status === 'sent' && (
                  <div className="bg-slate-950 border border-emerald-800/50 text-slate-200 p-5 rounded-2xl rounded-tl-none space-y-2 shadow-lg">
                    <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400 border-b border-slate-800 pb-2">
                      <UserCheck className="w-4 h-4" />
                      <span>Support Specialist Verified Answer</span>
                    </div>
                    <p className="text-sm leading-relaxed text-slate-200">
                      {currentTicket.evaluated_draft?.answer || 'Here is the verified response from our support specialist.'}
                    </p>
                  </div>
                )}

                {currentTicket.status === 'pending' && (
                  <div className="bg-slate-950 border border-amber-800/40 text-slate-300 p-5 rounded-2xl rounded-tl-none space-y-3 shadow-lg">
                    <div className="flex items-center gap-2 text-xs font-semibold text-amber-400">
                      <Clock className="w-4 h-4 animate-pulse" />
                      <span>Under Support Specialist Review</span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Your question has been received. A support specialist is currently reviewing your request to provide an accurate answer.
                    </p>
                    <div className="text-[11px] text-slate-500 bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                      ℹ Our team ensures all responses adhere strictly to Orbit Desk verified documentation.
                    </div>
                  </div>
                )}

                {currentTicket.status === 'reviewed' && (
                  <div className="bg-slate-950 border border-indigo-800/50 text-slate-200 p-5 rounded-2xl rounded-tl-none space-y-2 shadow-lg">
                    <div className="flex items-center gap-2 text-xs font-semibold text-indigo-400 border-b border-slate-800 pb-2">
                      <UserCheck className="w-4 h-4" />
                      <span>Approved Support Response</span>
                    </div>
                    <p className="text-sm leading-relaxed text-slate-200">
                      {currentTicket.evaluated_draft?.answer}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
