/**
 * ReviewExplanationCard — mobile/components/cv/ReviewExplanationCard.tsx
 *
 * Responsibility: Render a structured fake-review authenticity explanation.
 * Reuses the ExplanationAccordion lazy-tap pattern from Feature 1.
 *
 * Architecture rules (from spec):
 *   - NEVER show for reviews where is_flagged_fake is false.
 *   - Fetch is lazy — only on first user tap of "Why was this flagged?" trigger.
 *   - Always shows "AI generated" label.
 *   - Verdict badge is colour-coded: red (Likely fake), amber (Possibly fake),
 *     grey (Inconclusive).
 *
 * Props:
 *   reviewId      — UUID of the flagged review.
 *   isFlaggedFake — boolean guard; renders nothing if false.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
  LayoutAnimation,
  Platform,
  UIManager,
  ScrollView,
} from 'react-native';
import { useReviewExplanation } from '../../hooks/useReviewExplanation';

// Enable LayoutAnimation on Android
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

interface ReviewExplanationCardProps {
  /** UUID of the review */
  reviewId: string;
  /** Whether the review is flagged as fake (defaults to true if flagged, false if clean) */
  isFlaggedFake?: boolean;
}

// ---------------------------------------------------------------------------
// Verdict badge colours
// ---------------------------------------------------------------------------

const VERDICT_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  'Verified authentic': { bg: 'rgba(16,185,129,0.12)', text: '#10B981', border: '#10B98140' },
  'Likely authentic':   { bg: 'rgba(16,185,129,0.12)', text: '#10B981', border: '#10B98140' },
  'Likely fake':        { bg: 'rgba(239,68,68,0.12)',  text: '#EF4444', border: '#EF444440' },
  'Possibly fake':      { bg: 'rgba(245,158,11,0.12)', text: '#F59E0B', border: '#F59E0B40' },
  'Inconclusive':       { bg: 'rgba(107,114,128,0.12)',text: '#9CA3AF', border: '#9CA3AF40' },
};

function VerdictBadge({ verdict }: { verdict: string }) {
  const style = VERDICT_STYLES[verdict] ?? VERDICT_STYLES['Inconclusive'];
  return (
    <View
      style={[
        styles.verdictBadge,
        { backgroundColor: style.bg, borderColor: style.border },
      ]}
    >
      <Text style={[styles.verdictText, { color: style.text }]}>
        {verdict}
      </Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Phrase chip
// ---------------------------------------------------------------------------

function PhraseChip({ text, isFlagged = true }: { text: string; isFlagged?: boolean }) {
  const chipBg = isFlagged ? 'rgba(239,68,68,0.08)' : 'rgba(16,185,129,0.08)';
  const chipBorder = isFlagged ? 'rgba(239,68,68,0.25)' : 'rgba(16,185,129,0.25)';
  const chipText = isFlagged ? '#EF4444' : '#10B981';

  return (
    <View style={[styles.phraseChip, { backgroundColor: chipBg, borderColor: chipBorder }]}>
      <Text style={[styles.phraseChipText, { color: chipText }]}>"{text}"</Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ReviewExplanationCard({
  reviewId,
  isFlaggedFake = false,
}: ReviewExplanationCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [hasTapped, setHasTapped] = useState(false);

  const { explanation, loading, error, retry } = useReviewExplanation({
    reviewId,
    enabled: hasTapped,
  });

  const handlePress = () => {
    if (!hasTapped) setHasTapped(true);
    if (error) retry();
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded((prev) => !prev);
  };

  const isFlagged = isFlaggedFake;
  const triggerColor = isFlagged ? '#EF4444' : '#10B981';
  const triggerIcon = isFlagged ? '⚠️' : '🛡️';
  const triggerTitle = isFlagged ? 'Why was this flagged?' : 'Why is this listing verified?';

  return (
    <View style={styles.container}>
      {/* Divider */}
      <View style={styles.divider} />

      {/* Trigger row */}
      <TouchableOpacity
        style={styles.trigger}
        onPress={handlePress}
        activeOpacity={0.75}
        accessibilityRole="button"
        accessibilityLabel={triggerTitle}
        accessibilityState={{ expanded }}
      >
        <View style={styles.triggerLeft}>
          <Text style={styles.warningIcon}>{triggerIcon}</Text>
          <Text style={[styles.triggerText, { color: triggerColor }]}>{triggerTitle}</Text>
        </View>
        <Text style={[styles.chevron, { color: triggerColor }]}>{expanded ? '▴' : '▾'}</Text>
      </TouchableOpacity>

      {/* Expanded content */}
      {expanded && (
        <View style={styles.content}>
          {/* Loading state */}
          {loading && (
            <View style={styles.loadingRow}>
              <ActivityIndicator size="small" color={triggerColor} />
              <Text style={styles.loadingText}>Analysing review patterns…</Text>
            </View>
          )}

          {/* Error state */}
          {!loading && error && (
            <TouchableOpacity onPress={retry} activeOpacity={0.7}>
              <Text style={styles.errorText}>Could not load analysis. Tap to retry.</Text>
            </TouchableOpacity>
          )}

          {/* Loaded state */}
          {!loading && !error && explanation && (
            <View style={styles.explanationBody}>
              {/* Verdict */}
              <View style={styles.verdictRow}>
                <Text style={styles.sectionLabel}>Verdict</Text>
                <VerdictBadge verdict={explanation.overall_verdict} />
              </View>

              {/* Image mismatch / match summary */}
              {explanation.image_mismatch_summary ? (
                <View style={styles.section}>
                  <Text style={styles.mismatchText}>
                    {explanation.image_mismatch_summary}
                  </Text>
                </View>
              ) : null}

              {/* Phrases found */}
              {Array.isArray(explanation.suspicious_phrases) && explanation.suspicious_phrases.length > 0 && (
                <View style={styles.section}>
                  <Text style={styles.sectionLabel}>
                    {isFlagged ? 'Suspicious phrases found' : 'Authenticity phrases analyzed'}
                  </Text>
                  <View style={styles.chipsRow}>
                    {explanation.suspicious_phrases.map((phrase, idx) => (
                      <PhraseChip key={idx} text={phrase} isFlagged={isFlagged} />
                    ))}
                  </View>
                </View>
              )}

              {/* Pattern matches */}
              {Array.isArray(explanation.pattern_matches) && explanation.pattern_matches.length > 0 && (
                <View style={styles.section}>
                  <Text style={styles.sectionLabel}>
                    {isFlagged
                      ? `Matches ${explanation.pattern_matches.length} known fake review pattern${explanation.pattern_matches.length !== 1 ? 's' : ''}.`
                      : `Matches ${explanation.pattern_matches.length} positive trust indicator${explanation.pattern_matches.length !== 1 ? 's' : ''}.`}
                  </Text>
                  {explanation.pattern_matches.map((match, idx) => (
                    <View key={idx} style={styles.bulletRow}>
                      <Text style={styles.bullet}>·</Text>
                      <Text style={styles.bulletText}>{match}</Text>
                    </View>
                  ))}
                </View>
              )}

              {/* Recommendation */}
              {explanation.recommendation ? (
                <View style={styles.recommendationBox}>
                  <Text style={styles.recommendationIcon}>{isFlagged ? '💡' : '✨'}</Text>
                  <Text style={styles.recommendationText}>
                    {explanation.recommendation}
                  </Text>
                </View>
              ) : null}

              {/* AI generated label */}
              <View style={styles.aiLabelRow}>
                <View style={styles.aiDot} />
                <Text style={styles.aiLabel}>AI generated</Text>
              </View>
            </View>
          )}
        </View>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles — dark theme matching ExplanationAccordion
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {},

  divider: {
    height: 1,
    backgroundColor: '#24242E',
  },

  trigger: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#16161C',
  },
  triggerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  warningIcon: {
    fontSize: 14,
  },
  triggerText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#EF4444',
    letterSpacing: 0.2,
  },
  chevron: {
    fontSize: 11,
    color: '#EF4444',
    fontWeight: '700',
  },

  content: {
    paddingHorizontal: 16,
    paddingBottom: 16,
    paddingTop: 8,
    backgroundColor: '#13131A',
  },

  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 6,
  },
  loadingText: {
    fontSize: 12,
    color: '#70707A',
    fontStyle: 'italic',
  },

  errorText: {
    fontSize: 12,
    color: '#EF444480',
    fontStyle: 'italic',
    paddingVertical: 6,
  },

  explanationBody: {
    gap: 14,
  },

  // Verdict
  verdictRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  verdictBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    borderWidth: 1,
  },
  verdictText: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.3,
  },

  // Section
  section: {
    gap: 6,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#70707A',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },

  // Mismatch
  mismatchText: {
    fontSize: 13,
    color: '#C8C8D4',
    lineHeight: 19,
  },

  // Chips
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 2,
  },
  phraseChip: {
    backgroundColor: 'rgba(239,68,68,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.25)',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  phraseChipText: {
    fontSize: 11,
    color: '#EF4444',
    fontWeight: '500',
  },

  // Bullet points
  bulletRow: {
    flexDirection: 'row',
    gap: 6,
    alignItems: 'flex-start',
  },
  bullet: {
    color: '#70707A',
    fontSize: 14,
    lineHeight: 19,
  },
  bulletText: {
    flex: 1,
    fontSize: 12,
    color: '#A0A0A5',
    lineHeight: 18,
  },

  // Recommendation
  recommendationBox: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'flex-start',
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 10,
    padding: 10,
    borderWidth: 1,
    borderColor: '#24242E',
  },
  recommendationIcon: {
    fontSize: 14,
  },
  recommendationText: {
    flex: 1,
    fontSize: 12,
    color: '#C8C8D4',
    lineHeight: 18,
  },

  // AI label
  aiLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: 2,
  },
  aiDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: '#4C4CF0',
  },
  aiLabel: {
    fontSize: 10,
    color: '#4C4CF0',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
});
