import React from 'react';

interface BisLogoProps {
  size?: number;
  className?: string;
  style?: React.CSSProperties;
  animated?: boolean;
}

export const BisLogo: React.FC<BisLogoProps> = ({
  size = 24,
  className = '',
  style = {},
  animated = false,
}) => {
  return (
    <img
      src="/bis_logo.png"
      alt="Bureau of Indian Standards (BIS) Official Logo"
      width={size}
      height={size}
      className={`${className} ${animated ? 'bis-logo-pulse' : ''}`}
      style={{
        objectFit: 'contain',
        display: 'inline-block',
        verticalAlign: 'middle',
        flexShrink: 0,
        borderRadius: '4px',
        ...style,
      }}
    />
  );
};
