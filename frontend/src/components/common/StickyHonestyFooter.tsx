import React from 'react';

export const StickyHonestyFooter: React.FC = () => {
  return (
    <footer
      id="honesty-footer"
      style={{
        position: 'sticky',
        bottom: 0,
        left: 0,
        right: 0,
        width: '100%',
        padding: '9px 24px',
        background: 'rgba(5, 14, 28, 0.95)',
        borderTop: '1px solid rgba(0, 212, 255, 0.25)',
        color: 'var(--text-secondary, #a8d5e5)',
        fontSize: '11px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        zIndex: 40,
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        boxShadow: '0 -2px 10px rgba(0, 0, 0, 0.4)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span
          style={{
            color: 'var(--amber, #ffb800)',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          HONESTY DOCTRINE:
        </span>
        <strong style={{ color: '#ffffff', fontWeight: 600 }}>
          Investigation Priority ≠ Guilt.
        </strong>
        <span>
          Outputs are evidence-backed candidates requiring independent human verification and physical inspection.
        </span>
      </div>
      <div
        style={{
          fontFamily: "'IBM Plex Mono', 'JetBrains Mono', monospace",
          fontSize: '10px',
          color: 'var(--text-muted, #7da0b4)',
        }}
      >
        OCCURIS PS 26143 · MARPOL ANNEX I FORENSICS
      </div>
    </footer>
  );
};

export default StickyHonestyFooter;
