import React from 'react';

interface BisLogoProps {
  size?: number;
  width?: number | string;
  height?: number | string;
  className?: string;
  style?: React.CSSProperties;
  animated?: boolean;
}

export const BisLogo: React.FC<BisLogoProps> = ({
  size = 24,
  width,
  height,
  className = '',
  style = {},
  animated = false,
}) => {
  const finalHeight = height ?? size;
  const finalWidth = width ?? 'auto';

  return (
    <img
      src="/bis_logo.png"
      alt="Bureau of Indian Standards (BIS) Official Logo"
      className={`bis-logo ${animated ? 'animate-pulse' : ''} ${className}`.trim()}
      style={{
        height: finalHeight,
        width: finalWidth,
        maxHeight: '100%',
        objectFit: 'contain',
        display: 'inline-block',
        verticalAlign: 'middle',
        flexShrink: 0,
        filter: 'drop-shadow(0 1px 2px rgba(0, 0, 0, 0.35))',
        transition: 'transform 0.2s ease, filter 0.2s ease',
        ...style,
      }}
    />
  );
};

