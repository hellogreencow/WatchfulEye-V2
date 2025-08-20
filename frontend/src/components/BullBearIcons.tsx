import * as React from "react";

type Variant = "solid" | "outline";

export type IconProps = Omit<React.SVGProps<SVGSVGElement>, "color"> & {
  size?: number | string;       // 16 | "1em"
  title?: string;               // a11y label (omit if decorative)
  variant?: Variant;            // "solid" | "outline"
  strokeWidth?: number;         // for outline
  color?: string;               // defaults to currentColor
  className?: string;           // for Tailwind classes
};

const clampSize = (v: number | string) =>
  typeof v === "number" ? Math.max(12, Math.round(v)) : v;

const BaseIcon = React.forwardRef<SVGSVGElement, IconProps>(function BaseIcon(
  {
    size = 16,
    title,
    color = "currentColor",
    variant = "solid",
    strokeWidth = 1.25,
    className,
    children,
    ...rest
  },
  ref
) {
  const titleId = React.useId();
  const ariaHidden = title ? undefined : true;

  const common = {
    ref,
    width: clampSize(size),
    height: clampSize(size),
    // add padding to avoid stroke clipping at edges
    viewBox: "0 0 16 16",
    role: "img",
    "aria-labelledby": title ? titleId : undefined,
    "aria-hidden": ariaHidden,
    xmlns: "http://www.w3.org/2000/svg",
    shapeRendering: "geometricPrecision" as const,
    vectorEffect: "non-scaling-stroke" as const,
    preserveAspectRatio: "xMidYMid meet" as const,
    overflow: "visible" as const,
    ...rest,
  };

  return (
    <svg
      {...common}
      className={className}
      style={{ display: 'block' }}
      fill={variant === "solid" ? color : "none"}
      stroke={variant === "outline" ? color : "none"}
      strokeWidth={variant === "outline" ? strokeWidth : 0}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {title ? <title id={titleId}>{title}</title> : null}
      {children}
    </svg>
  );
});

/* ========================= Bull Icon ========================= */

export const BullHeadIcon = React.memo(
  React.forwardRef<SVGSVGElement, IconProps>(function BullHeadIcon(
    { variant = "outline", color, className, ...props },
    ref
  ) {
    return (
      <BaseIcon ref={ref} variant="outline" color={color} strokeWidth={1.5} className={className} {...props}>
        {/* Bull horns and head from the provided SVG */}
        <path d="M11.7 3.6C8.6 4.2 11.4 7.9 13.7 4.5" />
        <path d="M9.2 5.7C8.5 6.4 7.9 6.3 7.1 6.3C6.4 6.4 5.5 5.8 5.0 5.9C4.9 5.9 4.6 6.4 4.4 6.5C2.5 7.5 3.4 6.4 3.5 9.2C3.5 9.9 3.5 10.7 3.4 11.4C3.4 11.5 3.2 12.4 3.3 12.4C3.4 12.4 3.5 12.1 3.6 12.1C3.9 11.5 4.7 9.9 5.7 9.6C7.2 9.0 9.2 12.2 9.3 12.2C9.6 12.2 9.4 11.6 9.4 11.4C9.4 10.8 9.6 10.0 10.0 9.6C10.5 8.9 11.1 8.3 12.4 7.9C12.8 7.8 13.5 7.8 13.8 7.9C13.8 7.9 14.0 8.2 14.1 8.1C14.3 8.0 14.1 7.0 14.1 6.7" />
        <path d="M3.2 7.0C2.3 6.6 2.4 5.8 2.4 5.7" />
      </BaseIcon>
    );
  })
);

/* ========================= Bear Icon ========================= */

export const BearHeadIcon = React.memo(
  React.forwardRef<SVGSVGElement, IconProps>(function BearHeadIcon(
    { variant = "solid", color, className, ...props },
    ref
  ) {
    return (
      <BaseIcon ref={ref} variant="solid" color={color} className={className} {...props}>
        {/* Bear paw from the provided SVG */}
        <path d="M7.8 8.8C7.8 9.5 7.7 11.7 6.0 11.7C5.0 11.7 4.8 9.5 3.8 9.5C3.0 9.5 2.5 8.6 2.0 8.6C1.4 8.6 1.0 7.5 1.0 6.0C1.0 4.5 2.4 5.3 3.8 4.6C5.2 3.9 4.8 5.9 5.8 5.9C6.8 5.9 7.8 8.1 7.8 8.8Z" />
        <path d="M1.5 4.7C1.5 3.8 1.0 3.0 0.7 3.0C0.3 3.0 0.0 3.2 0.0 4.1C0.0 5.7 0.3 6.7 0.8 6.7C1.2 6.7 1.4 5.6 1.5 4.7Z" />
        <path d="M5.1 4.1C5.1 3.2 5.6 1.6 5.3 1.6C5.0 1.6 4.9 2.8 4.9 3.4C4.9 4.0 4.9 5.0 5.1 5.0C5.3 5.0 5.1 4.1 5.1 4.1Z" />
        <path d="M6.8 5.6C6.8 4.7 7.3 3.5 7.0 3.5C6.7 3.5 6.6 4.7 6.6 5.3C6.6 5.9 6.6 6.9 6.8 6.9C7.0 6.9 6.8 5.6 6.8 5.6Z" />
        <path d="M8.9 5.1C8.9 4.2 9.4 2.6 9.1 2.6C8.8 2.6 8.7 3.8 8.7 4.4C8.7 5.0 8.7 6.0 8.9 6.0C9.1 6.0 8.9 5.1 8.9 5.1Z" />
        <path d="M2.7 3.2C2.8 3.3 2.9 3.4 2.9 3.2C2.9 2.9 3.0 2.4 2.8 2.4C2.7 2.4 2.5 2.9 2.4 3.1C2.3 3.4 2.6 3.2 2.7 3.2Z" />
        <path d="M3.5 0.9C3.7 1.0 3.8 1.1 3.8 0.9C3.8 0.6 3.9 0.1 3.7 0.1C3.6 0.1 3.4 0.6 3.3 0.8C3.2 1.1 3.5 0.9 3.5 0.9Z" />
        <path d="M6.1 1.1C6.2 1.2 6.3 1.3 6.3 1.1C6.3 0.8 6.4 0.3 6.2 0.3C6.1 0.3 5.9 0.8 5.8 1.0C5.7 1.3 6.0 1.1 6.1 1.1Z" />
        <path d="M8.3 2.4C8.4 2.5 8.5 2.6 8.5 2.4C8.5 2.1 8.6 1.6 8.4 1.6C8.3 1.6 8.1 2.1 8.0 2.3C7.9 2.6 8.2 2.4 8.3 2.4Z" />
        <path d="M9.9 3.8C9.8 3.8 9.7 3.5 9.9 3.5C10.1 3.5 10.2 3.8 10.2 4.0C10.2 4.2 10.1 4.7 9.9 4.7C9.7 4.7 9.6 4.2 9.6 4.0C9.6 3.8 9.8 3.8 9.9 3.8Z" />
      </BaseIcon>
    );
  })
);

export default { BullHeadIcon, BearHeadIcon };