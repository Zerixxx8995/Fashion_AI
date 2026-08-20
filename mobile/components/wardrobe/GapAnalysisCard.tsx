/**
 * GapAnalysisCard — mobile/components/wardrobe/GapAnalysisCard.tsx
 *
 * Responsibility: Display capsule wardrobe coverage score gauge,
 * missing category gaps, priority levels, and suggested budget allocation.
 */

import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
} from 'react-native';

export interface GapItem {
  category: string;
  priority: 'high' | 'medium' | 'low' | string;
  reason: string;
  suggested_budget_inr?: number | null;
}

export interface GapAnalysisData {
  coverage_score: number; // 0..1
  owned_categories?: string[];
  missing_categories?: GapItem[];
  analysis_note?: string;
  total_items?: number;
}

interface GapAnalysisCardProps {
  data: GapAnalysisData | null;
  loading: boolean;
  onRunAnalysis: () => void;
}

export default function GapAnalysisCard({
  data,
  loading,
  onRunAnalysis,
}: GapAnalysisCardProps) {
  const coveragePercent = data
    ? Math.round((data.coverage_score || 0) * 100)
    : 70;

  const getPriorityColor = (p: string) => {
    switch (p.toLowerCase()) {
      case 'high':
        return { text: '#EF4444', bg: 'rgba(239,68,68,0.12)', border: '#EF4444' };
      case 'medium':
        return { text: '#F59E0B', bg: 'rgba(245,158,11,0.12)', border: '#F59E0B' };
      default:
        return { text: '#10B981', bg: 'rgba(16,185,129,0.12)', border: '#10B981' };
    }
  };

  return (
    <View style={styles.card}>
      {/* Top Header */}
      <View style={styles.headerRow}>
        <View style={styles.headerTitleWrap}>
          <Text style={styles.title}>✦ AI Wardrobe Gap Analysis</Text>
          <Text style={styles.sub}>Capsule completion & missing essential categories</Text>
        </View>

        <TouchableOpacity
          style={styles.recalcBtn}
          onPress={onRunAnalysis}
          disabled={loading}
          activeOpacity={0.8}
        >
          {loading ? (
            <ActivityIndicator size="small" color="#FF3F6C" />
          ) : (
            <Text style={styles.recalcText}>↺ Analyze</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Coverage Score Metric */}
      <View style={styles.metricCard}>
        <View style={styles.gaugeWrap}>
          <Text style={styles.scoreNumber}>{coveragePercent}%</Text>
          <Text style={styles.scoreLabel}>Capsule Coverage</Text>
        </View>
        <View style={styles.noteWrap}>
          <Text style={styles.noteText}>
            {data?.analysis_note ||
              'Good foundation — focus on high-priority gaps to maximize outfit combinations.'}
          </Text>
        </View>
      </View>

      {/* Missing Categories Gaps List */}
      <View style={styles.gapsSection}>
        <Text style={styles.gapsHeading}>RECOMMENDED ESSENTIAL GAPS</Text>

        {loading ? (
          <ActivityIndicator color="#FF3F6C" style={{ marginVertical: 12 }} />
        ) : !data || !data.missing_categories || data.missing_categories.length === 0 ? (
          <View style={styles.completeWrap}>
            <Text style={styles.completeText}>🎉 Complete Capsule! No critical gaps detected.</Text>
          </View>
        ) : (
          <View style={styles.gapsList}>
            {data.missing_categories.slice(0, 4).map((gap, idx) => {
              const colors = getPriorityColor(gap.priority);
              return (
                <View key={idx} style={styles.gapRow}>
                  <View style={styles.gapLeft}>
                    <View style={styles.gapNameRow}>
                      <Text style={styles.gapCategory}>{gap.category}</Text>
                      <View style={[styles.priorityTag, { backgroundColor: colors.bg, borderColor: colors.border }]}>
                        <Text style={[styles.priorityText, { color: colors.text }]}>
                          {gap.priority.toUpperCase()}
                        </Text>
                      </View>
                    </View>
                    <Text style={styles.gapReason} numberOfLines={2}>
                      {gap.reason}
                    </Text>
                  </View>

                  {gap.suggested_budget_inr ? (
                    <View style={styles.budgetWrap}>
                      <Text style={styles.budgetLabel}>Budget</Text>
                      <Text style={styles.budgetValue}>₹{gap.suggested_budget_inr}</Text>
                    </View>
                  ) : null}
                </View>
              );
            })}
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#16161C',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#24242E',
    padding: 16,
    gap: 14,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  headerTitleWrap: { flex: 1, gap: 2 },
  title: { fontSize: 16, fontWeight: '900', color: '#FF3F6C' },
  sub: { fontSize: 11, color: '#70707A' },
  recalcBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 10,
    backgroundColor: '#0B0B0E',
    borderWidth: 1,
    borderColor: '#24242E',
  },
  recalcText: { color: '#FF3F6C', fontSize: 12, fontWeight: '800' },

  metricCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0B0B0E',
    padding: 12,
    borderRadius: 14,
    gap: 14,
  },
  gaugeWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRightWidth: 1,
    borderRightColor: '#24242E',
    paddingRight: 14,
  },
  scoreNumber: { fontSize: 26, fontWeight: '900', color: '#10B981' },
  scoreLabel: { fontSize: 9, fontWeight: '700', color: '#70707A', textTransform: 'uppercase' },
  noteWrap: { flex: 1 },
  noteText: { fontSize: 12, color: '#E8E8F0', lineHeight: 16 },

  gapsSection: { gap: 8 },
  gapsHeading: { fontSize: 10, fontWeight: '800', color: '#60606A', letterSpacing: 0.8 },
  completeWrap: { padding: 12, alignItems: 'center' },
  completeText: { color: '#10B981', fontSize: 12, fontWeight: '700' },

  gapsList: { gap: 8 },
  gapRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#0B0B0E',
    padding: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#24242E',
  },
  gapLeft: { flex: 1, gap: 2, paddingRight: 8 },
  gapNameRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  gapCategory: { fontSize: 13, fontWeight: '700', color: '#E8E8F0' },
  priorityTag: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    borderWidth: 1,
  },
  priorityText: { fontSize: 8, fontWeight: '900' },
  gapReason: { fontSize: 11, color: '#90909A' },

  budgetWrap: { alignItems: 'flex-end', justifyContent: 'center' },
  budgetLabel: { fontSize: 9, color: '#70707A', textTransform: 'uppercase' },
  budgetValue: { fontSize: 13, fontWeight: '900', color: '#FF3F6C' },
});
