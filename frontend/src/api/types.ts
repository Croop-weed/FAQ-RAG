export type ConfidenceDecision = 'accept' | 'review' | 'abstain';

export type FAQStatus = 'active' | 'inactive' | 'draft';

export interface EvidenceItem {
  faq_id: string;
  question: string;
  answer: string;
  source?: string | null;
  category?: string | null;
  product?: string | null;
  version?: string | null;
  tags?: string[];
  retrieval_rank: number;
  retrieval_score: number;
  retrieval_stage: string;
  retrieval_metadata?: Record<string, unknown>;
}

export interface DraftCitation {
  faq_id: string;
  source?: string | null;
  question: string;
}

export interface GenerationMetadata {
  provider: string;
  model: string;
  latency_ms: number;
  input_tokens?: number | null;
  output_tokens?: number | null;
  evidence_count: number;
  prompt_version: string;
}

export interface GroundedDraft {
  answer: string;
  citations: DraftCitation[];
  evidence_ids: string[];
  provided_evidence: EvidenceItem[];
  metadata: GenerationMetadata;
}

export interface EvidenceSupportResult {
  supported: boolean;
  support_score: number;
  supporting_evidence_ids: string[];
  unsupported_claims: string[];
  citation_validity: number;
  evidence_relevance_scores: Record<string, number>;
  explanation: string;
}

export interface KnowledgeGapAssessment {
  is_gap: boolean;
  reason: string;
  gap_type: string;
  confidence_cap?: number | null;
}

export interface ConfidenceAssessment {
  decision: ConfidenceDecision;
  confidence_score: number;
  supporting_evidence_ids: string[];
  weak_evidence_indicators: string[];
  reason: string;
  metadata?: Record<string, unknown>;
}

export interface EvaluatedGroundedDraft {
  decision: ConfidenceDecision;
  confidence: number;
  answer?: string | null;
  reason: string;
  citations: DraftCitation[];
  confidence_assessment: ConfidenceAssessment;
  grounded_draft?: GroundedDraft | null;
}

export interface FAQRead {
  id: string;
  question: string;
  answer: string;
  category?: string | null;
  product?: string | null;
  version?: string | null;
  region?: string | null;
  tags: string[];
  source?: string | null;
  status: FAQStatus;
  created_at: string;
  updated_at: string;
}

export interface Ticket {
  id: string;
  customer_name: string;
  customer_email: string;
  question: string;
  created_at: string;
  status: 'pending' | 'reviewed' | 'sent' | 'rejected';
  evaluated_draft?: EvaluatedGroundedDraft;
}
