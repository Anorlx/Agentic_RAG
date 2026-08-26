import { describe, expect, it } from 'vitest';
import { shouldShowRetrievalDetails } from './routePresentation';

describe('route presentation', () => {
  it('shows retrieval details only for knowledge-base routes', () => {
    expect(shouldShowRetrievalDetails('direct')).toBe(false);
    expect(shouldShowRetrievalDetails('web_search')).toBe(false);
    expect(shouldShowRetrievalDetails('knowledge_base')).toBe(true);
    expect(shouldShowRetrievalDetails('knowledge_base_and_web_search')).toBe(true);
  });
});
