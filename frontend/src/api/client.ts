import { getMockDraftResult, SAMPLE_FAQS } from './mock';
import type { EvaluatedGroundedDraft, FAQRead } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function generateRequestId(): string {
  return 'req_' + Math.random().toString(36).substring(2, 11);
}

export async function processDraftQuery(query: string): Promise<EvaluatedGroundedDraft> {
  const requestId = generateRequestId();
  try {
    const response = await fetch(`${API_BASE_URL}/drafts/process`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': requestId,
      },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      console.warn(`Backend returned status ${response.status}. Using demo mode fallback.`);
      return getMockDraftResult(query);
    }

    const data: EvaluatedGroundedDraft = await response.json();
    return data;
  } catch (error) {
    console.warn('Backend server connection un-reachable. Falling back to demo mode.', error);
    return getMockDraftResult(query);
  }
}

export async function fetchKnowledgeBaseFAQs(): Promise<FAQRead[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/knowledge-base/faqs?limit=100`, {
      headers: {
        'X-Request-ID': generateRequestId(),
      },
    });
    if (!response.ok) {
      return SAMPLE_FAQS;
    }
    const data = await response.json();
    return data.items || SAMPLE_FAQS;
  } catch (error) {
    console.warn('Backend server un-reachable for FAQs. Returning demo FAQs.', error);
    return SAMPLE_FAQS;
  }
}
