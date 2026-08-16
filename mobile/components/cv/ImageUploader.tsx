/**
 * ImageUploader — mobile/components/cv/ImageUploader.tsx
 *
 * Responsibility: Renders the image selection area for the CV Scan screen.
 * Shows either the picked image preview or the "pick / take photo" CTA.
 *
 * Props:
 *   imageUri   — URI of picked image (null = nothing picked yet)
 *   phase      — current scan phase (controls disabled state)
 *   onGallery  — callback: open gallery picker
 *   onCamera   — callback: open camera
 *   onReset    — callback: clear picked image and start over
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
import type { CVScanPhase } from '../../hooks/useCVScore';

interface ImageUploaderProps {
  imageUri: string | null;
  phase: CVScanPhase;
  onGallery: () => void;
  onCamera: () => void;
  onReset: () => void;
}

export default function ImageUploader({
  imageUri,
  phase,
  onGallery,
  onCamera,
  onReset,
}: ImageUploaderProps) {
  const isBusy = phase !== 'idle' && phase !== 'error' && phase !== 'complete' && phase !== 'picking';

  if (imageUri) {
    return (
      <View style={styles.previewContainer}>
        <Image source={{ uri: imageUri }} style={styles.preview} resizeMode="cover" />
        <View style={styles.previewOverlay}>
          {isBusy ? (
            <View style={styles.busyBadge}>
              <ActivityIndicator color="#FF3F6C" size="small" />
              <Text style={styles.busyText}>Analysing…</Text>
            </View>
          ) : (
            <TouchableOpacity style={styles.changeBtn} onPress={onReset} activeOpacity={0.8}>
              <Text style={styles.changeBtnText}>↺  Change Image</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.placeholder}>
      <Text style={styles.placeholderIcon}>📷</Text>
      <Text style={styles.placeholderTitle}>Upload a Product Photo</Text>
      <Text style={styles.placeholderSub}>
        We'll compare it against the stock photo and give you a confidence score
      </Text>

      <View style={styles.buttonRow}>
        <TouchableOpacity
          style={[styles.actionBtn, styles.galleryBtn]}
          onPress={onGallery}
          activeOpacity={0.8}
          disabled={isBusy}
        >
          <Text style={styles.galleryIcon}>🖼</Text>
          <Text style={styles.actionBtnText}>Gallery</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionBtn, styles.cameraBtn]}
          onPress={onCamera}
          activeOpacity={0.8}
          disabled={isBusy}
        >
          <Text style={styles.cameraIcon}>📸</Text>
          <Text style={styles.actionBtnText}>Camera</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  // ── Preview ──────────────────────────────────────────────────────────────
  previewContainer: {
    width: '100%',
    height: 280,
    borderRadius: 20,
    overflow: 'hidden',
    backgroundColor: '#16161C',
  },
  preview: {
    width: '100%',
    height: '100%',
  },
  previewOverlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: 'rgba(11,11,14,0.7)',
    alignItems: 'center',
  },
  busyBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  busyText: {
    color: '#FF3F6C',
    fontSize: 13,
    fontWeight: '600',
  },
  changeBtn: {
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: 'rgba(255,63,108,0.15)',
    borderWidth: 1,
    borderColor: '#FF3F6C',
  },
  changeBtnText: {
    color: '#FF3F6C',
    fontSize: 13,
    fontWeight: '600',
  },

  // ── Placeholder ───────────────────────────────────────────────────────────
  placeholder: {
    width: '100%',
    minHeight: 280,
    borderRadius: 20,
    borderWidth: 1.5,
    borderColor: '#24242E',
    borderStyle: 'dashed',
    backgroundColor: '#16161C',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  placeholderIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  placeholderTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#E8E8F0',
    textAlign: 'center',
    marginBottom: 8,
  },
  placeholderSub: {
    fontSize: 13,
    color: '#60606A',
    textAlign: 'center',
    lineHeight: 18,
    marginBottom: 28,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 12,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 14,
    borderWidth: 1,
  },
  galleryBtn: {
    backgroundColor: 'rgba(255,63,108,0.08)',
    borderColor: '#FF3F6C',
  },
  cameraBtn: {
    backgroundColor: 'rgba(99,102,241,0.08)',
    borderColor: '#6366F1',
  },
  galleryIcon: {
    fontSize: 18,
  },
  cameraIcon: {
    fontSize: 18,
  },
  actionBtnText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#E8E8F0',
  },
});
