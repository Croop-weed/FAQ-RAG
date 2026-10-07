import React, { useState } from 'react';
import { processDraftQuery } from './api/client';
import { INITIAL_TICKETS } from './api/mock';
import type { Ticket } from './api/types';
import { AgentWorkspace } from './components/agent/AgentWorkspace';
import { CustomerPortal } from './components/customer/CustomerPortal';
import { Navbar } from './components/Navbar';

export const App: React.FC = () => {
  const [activeRole, setActiveRole] = useState<'customer' | 'agent'>('customer');
  const [tickets, setTickets] = useState<Ticket[]>(INITIAL_TICKETS);
  const [activeCustomerTicket, setActiveCustomerTicket] = useState<Ticket | null>(null);

  const pendingCount = tickets.filter((t) => t.status === 'pending').length;

  const handleCustomerSubmitQuestion = async (question: string): Promise<Ticket> => {
    const evaluatedDraft = await processDraftQuery(question);

    const newTicket: Ticket = {
      id: `tkt-${Math.floor(Math.random() * 9000 + 1000)}`,
      customer_name: 'You (Customer)',
      customer_email: 'customer@example.com',
      question,
      created_at: 'Just now',
      status: 'pending',
      evaluated_draft: evaluatedDraft,
    };

    setTickets((prev) => [newTicket, ...prev]);
    setActiveCustomerTicket(newTicket);
    return newTicket;
  };

  const handleAgentSendResponse = (ticketId: string, finalAnswer: string) => {
    setTickets((prev) =>
      prev.map((t) => {
        if (t.id === ticketId) {
          return {
            ...t,
            status: 'sent',
            evaluated_draft: t.evaluated_draft
              ? {
                  ...t.evaluated_draft,
                  answer: finalAnswer,
                }
              : undefined,
          };
        }
        return t;
      })
    );
  };

  const handleAgentRejectDraft = (ticketId: string) => {
    setTickets((prev) =>
      prev.map((t) => {
        if (t.id === ticketId) {
          return {
            ...t,
            evaluated_draft: t.evaluated_draft
              ? {
                  ...t.evaluated_draft,
                  decision: 'abstain',
                  answer: null,
                  reason: 'Draft rejected by human support agent.',
                }
              : undefined,
          };
        }
        return t;
      })
    );
  };

  const handleAgentRegenerateDraft = async (ticketId: string) => {
    const target = tickets.find((t) => t.id === ticketId);
    if (!target) return;

    const freshDraft = await processDraftQuery(target.question);
    setTickets((prev) =>
      prev.map((t) => {
        if (t.id === ticketId) {
          return {
            ...t,
            evaluated_draft: freshDraft,
          };
        }
        return t;
      })
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar
        activeRole={activeRole}
        onRoleChange={setActiveRole}
        pendingCount={pendingCount}
      />

      <main className="flex-1">
        {activeRole === 'customer' ? (
          <CustomerPortal
            onSubmitQuestion={handleCustomerSubmitQuestion}
            activeTicket={activeCustomerTicket}
          />
        ) : (
          <AgentWorkspace
            tickets={tickets}
            onSendResponse={handleAgentSendResponse}
            onRejectDraft={handleAgentRejectDraft}
            onRegenerateDraft={handleAgentRegenerateDraft}
          />
        )}
      </main>
    </div>
  );
};

export default App;
