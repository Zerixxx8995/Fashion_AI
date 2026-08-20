/**
 * CompareUploader — mobile/components/cv/CompareUploader.tsx
 *
 * Responsibility: Renders a dual-image picker interface for direct 2-image comparison.
 * Lets the user pick Image A (Received / Photo 1) and Image B (Advertised / Photo 2)
 * and compare their CLIP similarity directly.
 */

import React from 'react';
import {
  View,
  Text,
  Image,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';

interface CompareUploaderProps {
  imageUriA: string | null;
  imageUriB: string | null;
  isBusy: boolean;
  onPickImageA: (source: 'gallery' | 'camera') => void;
  onPickImageB: (source: 'gallery' | 'camera') => void;
  onCompare: () => void;
  onReset: () => void;
}

export default function CompareUploader({
  imageUriA,
  imageUriB,
  isBusy,
  onPickImageA,
  onPickImageB,
  onCompare,
  onReset,
}: CompareUploaderProps) {
  const canCompare = Boolean(imageUriA && imageUriB) && !isBusy;

  return (
    <View style={styles.container}>
      <View style={styles.headerBox}>
        <Text style={styles.title}>Direct 2-Image Comparison</Text>
        <Text style={styles.subtitle}>
          Upload two photos to test how accurately CLIP detects similarity between them
        </Text>
      </View>

      <View style={styles.cardsRow}>
        {/* Image A Slot */}
        <View style={styles.slotCard}>
          <Text style={styles.slotTag}>PHOTO 1 (RECEIVED ITEM)</Text>
          {imageUriA ? (
            <View style={styles.previewBox}>
              <Image source={{ uri: imageUriA }} style={styles.image} resizeMode="cover" />
              {!isBusy && (
                <TouchableOpacity
                  style={styles.changeOverlayBtn}
                  onPress={() => onPickImageA('gallery')}
                  activeOpacity={0.8}
                >
                  <Text style={styles.changeOverlayText}>Change</Text>
                </TouchableOpacity>
              )}
            </View>
          ) : (
            <View style={styles.emptySlot}>
              <Text style={styles.emptyIcon}>📦</Text>
              <Text style={styles.emptyLabel}>Select Photo 1</Text>
              <View style={styles.slotBtnRow}>
                <TouchableOpacity
                  style={styles.miniBtn}
                  onPress={() => onPickImageA('gallery')}
                  disabled={isBusy}
                >
                  <Text style={styles.miniBtnText}>🖼 Gallery</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.miniBtn}
                  onPress={() => onPickImageA('camera')}
                  disabled={isBusy}
                >
                  <Text style={styles.miniBtnText}>📸 Camera</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>

        {/* Image B Slot */}
        <View style={styles.slotCard}>
          <Text style={styles.slotTag}>PHOTO 2 (AD / REFERENCE)</Text>
          {imageUriB ? (
            <View style={styles.previewBox}>
              <Image source={{ uri: imageUriB }} style={styles.image} resizeMode="cover" />
              {!isBusy && (
                <TouchableOpacity
                  style={styles.changeOverlayBtn}
                  onPress={() => onPickImageB('gallery')}
                  activeOpacity={0.8}
                >
                  <Text style={styles.changeOverlayText}>Change</Text>
                </TouchableOpacity>
              )}
            </View>
          ) : (
            <View style={styles.emptySlot}>
              <Text style={styles.emptyIcon}>🏷️</Text>
              <Text style={styles.emptyLabel}>Select Photo 2</Text>
              <View style={styles.slotBtnRow}>
                <TouchableOpacity
                  style={styles.miniBtn}
                  onPress={() => onPickImageB('gallery')}
                  disabled={isBusy}
                >
                  <Text style={styles.miniBtnText}>🖼 Gallery</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.miniBtn}
                  onPress={() => onPickImageB('camera')}
                  disabled={isBusy}
                >
                  <Text style={styles.miniBtnText}>📸 Camera</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>
      </View>

      {/* Compare CTA Action */}
      <View style={styles.actionRow}>
        <TouchableOpacity
          style={[styles.compareBtn, !canCompare && styles.compareBtnDisabled]}
          onPress={onCompare}
          disabled={!canCompare}
          activeOpacity={0.85}
        >
          {isBusy ? (
            <ActivityIndicator color="#FFFFFF" size="small" />
          ) : (
            <>
              <Text style={styles.compareBtnIcon}>⚡</Text>
              <Text style={styles.compareBtnText}>Calculate Match Score</Text>
            </>
          )}
        </TouchableOpacity>

        {(imageUriA || imageUriB) && !isBusy && (
          <TouchableOpacity style={styles.resetBtn} onPress={onReset} activeOpacity={0.8}>
            <Text style={styles.resetBtnText}>Clear All</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    backgroundColor: '#16161C',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#24242E',
    padding: 16,
    gap: 14,
  },
  headerBox: {
    gap: 4,
  },
  title: {
    fontSize: 16,
    fontWeight: '800',
    color: '#E8E8F0',
  },
  subtitle: {
    fontSize: 12,
    color: '#70707A',
    lineHeight: 16,
  },
  cardsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  slotCard: {
    flex: 1,
    backgroundColor: '#0B0B0E',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#24242E',
    padding: 10,
    gap: 8,
  },
  slotTag: {
    fontSize: 10,
    fontWeight: '800',
    color: '#FF3F6C',
    letterSpacing: 0.5,
  },
  previewBox: {
    width: '100%',
    height: 140,
    borderRadius: 10,
    overflow: 'hidden',
    position: 'relative',
  },
  image: {
    width: '100%',
    height: '100%',
  },
  changeOverlayBtn: {
    position: 'absolute',
    bottom: 6,
    right: 6,
    backgroundColor: 'rgba(0,0,0,0.7)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  changeOverlayText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '700',
  },
  emptySlot: {
    height: 140,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 6,
  },
  emptyIcon: {
    fontSize: 28,
  },
  emptyLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#A0A0A5',
  },
  slotBtnRow: {
    flexDirection: 'row',
    gap: 6,
    marginTop: 4,
  },
  miniBtn: {
    paddingHorizontal: 8,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: 'rgba(255,63,108,0.1)',
    borderWidth: 1,
    borderColor: 'rgba(255,63,108,0.3)',
  },
  miniBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#FF3F6C',
  },
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  compareBtn: {
    flex: 1,
    height: 46,
    borderRadius: 12,
    backgroundColor: '#FF3F6C',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  compareBtnDisabled: {
    backgroundColor: '#30303A',
    opacity: 0.6,
  },
  compareBtnIcon: {
    fontSize: 16,
  },
  compareBtnText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '800',
  },
  resetBtn: {
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.05)',
  },
  resetBtnText: {
    color: '#A0A0A5',
    fontSize: 12,
    fontWeight: '600',
  },
});
