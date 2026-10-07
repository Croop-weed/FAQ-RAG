import type { EvaluatedGroundedDraft, FAQRead, Ticket } from './types';

export const SAMPLE_FAQS: FAQRead[] = [
  {
    id: 'faq-101',
    question: 'How do I reset my password?',
    answer: 'You can reset your password by going to Account Settings -> Security -> Reset Password. A password reset link will be sent to your registered email address.',
    category: 'account',
    product: 'Orbit Desk',
    version: 'v2.4',
    tags: ['password', 'security', 'account'],
    source: 'Customer Help Center',
    status: 'active',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'faq-102',
    question: 'How do I update my billing information?',
    answer: 'To update your billing details, navigate to Billing & Invoices in the admin console. Click Edit Payment Method to update credit card or invoice details.',
    category: 'billing',
    product: 'Orbit Desk',
    version: 'v2.4',
    tags: ['billing', 'payment', 'invoices'],
    source: 'Billing Knowledge Base',
    status: 'active',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'faq-103',
    question: 'Where can I download my monthly invoices?',
    answer: 'Monthly invoices can be downloaded directly under Billing -> Invoices. You can download PDF statements for any billing cycle.',
    category: 'billing',
    product: 'Orbit Desk',
    version: 'v2.4',
    tags: ['invoices', 'pdf', 'billing'],
    source: 'Billing Knowledge Base',
    status: 'active',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'faq-104',
    question: 'What is the refund policy for annual subscriptions?',
    answer: 'Annual subscriptions are eligible for a full refund within 14 days of purchase. After 14 days, prorated refunds are not supported.',
    category: 'billing',
    product: 'Orbit Desk',
    version: 'v2.4',
    tags: ['refund', 'cancellation', 'billing'],
    source: 'Terms of Service',
    status: 'active',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const INITIAL_TICKETS: Ticket[] = [
  {
    id: 'tkt-801',
    customer_name: 'Alex Johnson',
    customer_email: 'alex.j@example.com',
    question: 'How do I reset my password if I no longer have access to my registered email address?',
    created_at: '10 minutes ago',
    status: 'pending',
    evaluated_draft: {
      decision: 'review',
      confidence: 0.62,
      answer: 'To reset your password, navigate to Account Settings -> Security -> Reset Password. If you cannot access your registered email, a support specialist must verify your identity manually.',
      reason: 'Review required: Relevant evidence exists but support for lost email recovery requires verification.',
      citations: [
        {
          faq_id: 'faq-101',
          question: 'How do I reset my password?',
          source: 'Customer Help Center',
        },
      ],
      confidence_assessment: {
        decision: 'review',
        confidence_score: 0.62,
        supporting_evidence_ids: ['faq-101'],
        weak_evidence_indicators: [
          'Narrow score margin between top retrieval candidates.',
          'Draft contains claims regarding lost email recovery requiring agent verification.',
        ],
        reason: 'Review required: Evidence is relevant but support is uncertain.',
        metadata: {
          top_reranker_score: 0.68,
          score_margin: 0.08,
          support_signal: 0.70,
          citation_signal: 1.0,
        },
      },
      grounded_draft: {
        answer: 'To reset your password, navigate to Account Settings -> Security -> Reset Password. If you cannot access your registered email, a support specialist must verify your identity manually.',
        citations: [
          {
            faq_id: 'faq-101',
            question: 'How do I reset my password?',
            source: 'Customer Help Center',
          },
        ],
        evidence_ids: ['faq-101'],
        provided_evidence: [
          {
            faq_id: 'faq-101',
            question: 'How do I reset my password?',
            answer: 'You can reset your password by going to Account Settings -> Security -> Reset Password. A password reset link will be sent to your registered email address.',
            source: 'Customer Help Center',
            category: 'account',
            product: 'Orbit Desk',
            version: 'v2.4',
            tags: ['password', 'security'],
            retrieval_rank: 1,
            retrieval_score: 0.68,
            retrieval_stage: 'reranker',
          },
        ],
        metadata: {
          provider: 'ollama',
          model: 'llama3',
          latency_ms: 320,
          evidence_count: 1,
          prompt_version: 'grounded-support-v1',
        },
      },
    },
  },
  {
    id: 'tkt-802',
    customer_name: 'Sarah Miller',
    customer_email: 'sarah.m@company.org',
    question: 'Where can I find and download my monthly PDF invoices?',
    created_at: '25 minutes ago',
    status: 'pending',
    evaluated_draft: {
      decision: 'accept',
      confidence: 0.88,
      answer: 'You can download your monthly PDF invoices directly by navigating to Billing -> Invoices in your admin console. PDF statements are available for any billing cycle.',
      reason: 'Draft accepted: Strong reranked evidence (score 0.86), valid citations, and verified support.',
      citations: [
        {
          faq_id: 'faq-103',
          question: 'Where can I download my monthly invoices?',
          source: 'Billing Knowledge Base',
        },
      ],
      confidence_assessment: {
        decision: 'accept',
        confidence_score: 0.88,
        supporting_evidence_ids: ['faq-103', 'faq-102'],
        weak_evidence_indicators: [],
        reason: 'Draft accepted: Strong evidence support and valid citations.',
        metadata: {
          top_reranker_score: 0.86,
          score_margin: 0.24,
          support_signal: 0.95,
          citation_signal: 1.0,
        },
      },
      grounded_draft: {
        answer: 'You can download your monthly PDF invoices directly by navigating to Billing -> Invoices in your admin console. PDF statements are available for any billing cycle.',
        citations: [
          {
            faq_id: 'faq-103',
            question: 'Where can I download my monthly invoices?',
            source: 'Billing Knowledge Base',
          },
        ],
        evidence_ids: ['faq-103', 'faq-102'],
        provided_evidence: [
          {
            faq_id: 'faq-103',
            question: 'Where can I download my monthly invoices?',
            answer: 'Monthly invoices can be downloaded directly under Billing -> Invoices. You can download PDF statements for any billing cycle.',
            source: 'Billing Knowledge Base',
            category: 'billing',
            product: 'Orbit Desk',
            version: 'v2.4',
            tags: ['invoices', 'pdf'],
            retrieval_rank: 1,
            retrieval_score: 0.86,
            retrieval_stage: 'reranker',
          },
          {
            faq_id: 'faq-102',
            question: 'How do I update my billing information?',
            answer: 'To update your billing details, navigate to Billing & Invoices in the admin console.',
            source: 'Billing Knowledge Base',
            category: 'billing',
            product: 'Orbit Desk',
            version: 'v2.4',
            tags: ['billing'],
            retrieval_rank: 2,
            retrieval_score: 0.62,
            retrieval_stage: 'reranker',
          },
        ],
        metadata: {
          provider: 'ollama',
          model: 'llama3',
          latency_ms: 240,
          evidence_count: 2,
          prompt_version: 'grounded-support-v1',
        },
      },
    },
  },
  {
    id: 'tkt-803',
    customer_name: 'John Doe',
    customer_email: 'john.doe@techcorp.io',
    question: 'How do I set up webhooks for real-time API event streaming in quantum cluster mode?',
    created_at: '1 hour ago',
    status: 'pending',
    evaluated_draft: {
      decision: 'abstain',
      confidence: 0.15,
      answer: null,
      reason: 'Abstained: Knowledge gap detected - Top reranked evidence score (0.18) is below knowledge-gap threshold (0.25).',
      citations: [],
      confidence_assessment: {
        decision: 'abstain',
        confidence_score: 0.15,
        supporting_evidence_ids: [],
        weak_evidence_indicators: [
          'Top reranked evidence score (0.18) is below threshold.',
          'Retrieved evidence does not share key terms with customer query.',
        ],
        reason: 'Abstained: Knowledge gap detected.',
        metadata: {
          gap_type: 'low_reranker_score',
          top_reranker_score: 0.18,
        },
      },
      grounded_draft: null,
    },
  },
];

export function getMockDraftResult(query: string): EvaluatedGroundedDraft {
  const clean = query.toLowerCase().trim();
  if (clean.includes('password') || clean.includes('reset') || clean.includes('login')) {
    return INITIAL_TICKETS[0].evaluated_draft!;
  }
  if (clean.includes('invoice') || clean.includes('billing') || clean.includes('payment')) {
    return INITIAL_TICKETS[1].evaluated_draft!;
  }
  if (clean.includes('webhook') || clean.includes('quantum') || clean.includes('api')) {
    return INITIAL_TICKETS[2].evaluated_draft!;
  }

  // Generic supported answer fallback
  return {
    decision: 'accept',
    confidence: 0.78,
    answer: 'Based on support documentation: You can manage account settings and subscription options directly from the Orbit Desk administrative console.',
    reason: 'Draft accepted: Relevant FAQ evidence supports the customer inquiry.',
    citations: [
      {
        faq_id: 'faq-101',
        question: 'How do I reset my password?',
        source: 'Customer Help Center',
      },
    ],
    confidence_assessment: {
      decision: 'accept',
      confidence_score: 0.78,
      supporting_evidence_ids: ['faq-101'],
      weak_evidence_indicators: [],
      reason: 'Draft accepted: Strong evidence support.',
      metadata: {
        top_reranker_score: 0.76,
        score_margin: 0.15,
        support_signal: 0.85,
        citation_signal: 1.0,
      },
    },
    grounded_draft: {
      answer: 'Based on support documentation: You can manage account settings and subscription options directly from the Orbit Desk administrative console.',
      citations: [
        {
          faq_id: 'faq-101',
          question: 'How do I reset my password?',
          source: 'Customer Help Center',
        },
      ],
      evidence_ids: ['faq-101'],
      provided_evidence: [
        {
          faq_id: 'faq-101',
          question: 'How do I reset my password?',
          answer: 'You can reset your password by going to Account Settings -> Security -> Reset Password.',
          source: 'Customer Help Center',
          category: 'account',
          product: 'Orbit Desk',
          version: 'v2.4',
          tags: ['account', 'security'],
          retrieval_rank: 1,
          retrieval_score: 0.76,
          retrieval_stage: 'reranker',
        },
      ],
      metadata: {
        provider: 'demo-grounded-v1',
        model: 'demo-model',
        latency_ms: 15,
        evidence_count: 1,
        prompt_version: 'grounded-support-v1',
      },
    },
  };
}
