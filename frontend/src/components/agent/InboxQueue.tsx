import React from 'react';
import { AlertTriangle, CheckCircle2, Clock, Inbox, Filter } from 'lucide-react';
import type { Ticket } from '../../api/types';

interface InboxQueueProps {
  tickets: Ticket[];
  selectedTicketId: string | null;
  onSelectTicket: (ticket: Ticket) => void;
  filter: 'all' | 'review' | 'gap' | 'resolved';
  onFilterChange: (filter: 'all' | 'review' | 'gap' | 'resolved') => void;
}

export const InboxQueue: React.FC<InboxQueueProps> = ({
  tickets,
  selectedTicketId,
  onSelectTicket,
  filter,
  onFilterChange,
}) => {
  const filteredTickets = tickets.filter((t) => {
    if (filter === 'review') return t.evaluated_draft?.decision === 'review' && t.status !== 'sent';
    if (filter === 'gap') return t.evaluated_draft?.decision === 'abstain' && t.status !== 'sent';
    if (filter === 'resolved') return t.status === 'sent';
    return true;
  });

  return (
    <div className="flex flex-col h-full bg-slate-900/60 border-r border-slate-800">
      {/* Queue Header & Filters */}
      <div className="p-3.5 border-b border-slate-800 space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Inbox className="w-4 h-4 text-indigo-400" />
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
              Support Inbox ({tickets.length})
            </h3>
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-none">
          <button
            onClick={() => onFilterChange('all')}
            className={`px-2.5 py-1 text-[11px] font-medium rounded-lg transition-all flex items-center gap-1 ${
              filter === 'all'
                ? 'bg-slate-800 text-white border border-slate-700'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Filter className="w-3 h-3" />
            All
          </button>
          <button
            onClick={() => onFilterChange('review')}
            className={`px-2.5 py-1 text-[11px] font-medium rounded-lg transition-all flex items-center gap-1 ${
              filter === 'review'
                ? 'bg-amber-950 text-amber-300 border border-amber-800/60'
                : 'text-slate-400 hover:text-amber-300'
            }`}
          >
            <Clock className="w-3 h-3" />
            Review
          </button>
          <button
            onClick={() => onFilterChange('gap')}
            className={`px-2.5 py-1 text-[11px] font-medium rounded-lg transition-all flex items-center gap-1 ${
              filter === 'gap'
                ? 'bg-red-950 text-red-300 border border-red-800/60'
                : 'text-slate-400 hover:text-red-300'
            }`}
          >
            <AlertTriangle className="w-3 h-3" />
            Gap
          </button>
          <button
            onClick={() => onFilterChange('resolved')}
            className={`px-2.5 py-1 text-[11px] font-medium rounded-lg transition-all flex items-center gap-1 ${
              filter === 'resolved'
                ? 'bg-emerald-950 text-emerald-300 border border-emerald-800/60'
                : 'text-slate-400 hover:text-emerald-300'
            }`}
          >
            <CheckCircle2 className="w-3 h-3" />
            Resolved
          </button>
        </div>
      </div>

      {/* Ticket List Items */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60">
        {filteredTickets.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-500">
            No tickets match the selected filter.
          </div>
        ) : (
          filteredTickets.map((t) => {
            const isSelected = t.id === selectedTicketId;
            const decision = t.evaluated_draft?.decision;

            return (
              <div
                key={t.id}
                onClick={() => onSelectTicket(t)}
                className={`p-3.5 cursor-pointer transition-all ${
                  isSelected
                    ? 'bg-slate-800/80 border-l-4 border-indigo-500'
                    : 'hover:bg-slate-900/80'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs font-semibold text-slate-200 truncate">
                    {t.customer_name}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">{t.created_at}</span>
                </div>

                <p className="text-xs text-slate-400 line-clamp-2 mb-2">{t.question}</p>

                {/* Status Badges */}
                <div className="flex items-center justify-between">
                  {decision === 'accept' && (
                    <span className="px-2 py-0.5 text-[10px] font-semibold bg-emerald-950 text-emerald-300 rounded border border-emerald-800/50 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      Strong Support
                    </span>
                  )}
                  {decision === 'review' && (
                    <span className="px-2 py-0.5 text-[10px] font-semibold bg-amber-950 text-amber-300 rounded border border-amber-800/50 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      Review Needed
                    </span>
                  )}
                  {decision === 'abstain' && (
                    <span className="px-2 py-0.5 text-[10px] font-semibold bg-red-950 text-red-300 rounded border border-red-800/50 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      Knowledge Gap
                    </span>
                  )}

                  {t.status === 'sent' && (
                    <span className="px-2 py-0.5 text-[10px] font-bold text-emerald-400">
                      Sent
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
