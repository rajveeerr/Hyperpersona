/**
 * Composed Tailwind class strings aligned with semantic @theme tokens in `app.css` (see FE_PLAN.md, UI_REFERENCE.md).
 * Display type uses `font-display` + `tracking-display*` + tight leading — keep feature components on these helpers.
 */

export const tw = {
  /** Horizontal gutters — matches `Header` inner padding. */
  layoutGutterX: "px-4 sm:px-6 lg:px-8",

  /**
   * Centered max width + gutters — `Header`, `Footer`, and any `editorialBreakout` inner wrapper
   * (hero / lab / story). Uses `100vw` in `max-width` so nested breakouts align with the nav rail.
   */
  layoutFrame:
    "mx-auto w-full max-w-[min(90rem,calc(100vw-2rem))] px-4 sm:px-6 lg:px-8",

  page: "flex flex-col gap-8",
  stackSm: "flex flex-col gap-2",
  stackMd: "flex flex-col gap-4",
  stackLg: "flex flex-col gap-8",

  surface:
    "rounded-card border border-outline bg-surface shadow-card backdrop-blur-[12px]",
  surfacePad: "p-8",
  surfacePadMd: "p-5",

  eyebrow: `text-[0.8rem] font-normal uppercase tracking-ui-wide text-accent-strong`,

  muted: "text-muted",

  /** Page-level serif H1 — tight leading, editorial weight */
  displayH1:
    "font-display font-normal tracking-display text-balance text-ink antialiased leading-[1.02] text-[clamp(2.1rem,4vw,4.25rem)]",

  /** Section serif H2 — pair with `text-2xl` / `text-3xl` in feature UIs */
  displayH2:
    "font-display font-normal tracking-display text-balance text-ink antialiased leading-[1.06]",

  /** Home category story titles — slightly tighter block */
  storyTitle:
    "font-display font-medium tracking-display text-balance text-ink antialiased leading-[0.98] text-[clamp(1.85rem,3.8vw,3.45rem)]",

  /** PDP-style product name (hero, cards) */
  displayProductTitle:
    "font-display font-large tracking-display text-balance text-ink antialiased leading-[1.02]",

  /** Nav wordmark — lowercase, tightest tracking */
  displayWordmarkNav:
    "font-display font-medium lowercase tracking-display-tight text-ink antialiased",

  /** Footer mega wordmark */
  displayWordmarkFooter:
    "font-display font-medium lowercase tracking-display-tight text-ink/92 antialiased leading-[0.92]",

  /** Newsletter / trust serif headline (sentence case) */
  displayNewsletterHeading:
    "font-display font-normal tracking-display text-balance text-ink antialiased leading-snug",

  /** Home editorial story band — multi-line display block */
  editorialStoryHeadline:
    "font-display font-normal tracking-display-tight text-balance text-ink antialiased leading-[1.02] text-[clamp(1.85rem,4.2vw,3.35rem)]",

  button:
    "inline-flex min-h-12 cursor-pointer touch-manipulation items-center justify-center gap-2 rounded-pill border-0 bg-ink px-[1.2rem] text-white transition-transform duration-150 ease-out hover:-translate-y-px focus-visible:-translate-y-px",

  /**
   * Hero + PDP — pill quantity on cream canvases (`surface-strong` + soft lift).
   * Pair shell with `qtyStepperBtn` / `qtyStepperValue`.
   */
  qtyStepper:
    "inline-flex h-12 min-w-0 items-stretch overflow-hidden rounded-pill border border-outline/50 bg-surface-strong/95 text-[0.8125rem] font-semibold tracking-body text-ink shadow-[0_8px_22px_rgba(62,40,27,0.08)] backdrop-blur-[6px]",
  qtyStepperBtn:
    "touch-manipulation px-4 transition-colors duration-150 hover:bg-ink/[0.045] active:bg-ink/[0.08]",
  qtyStepperValue:
    "flex min-w-[2.75rem] items-center justify-center border-x border-outline/35 px-2 tabular-nums",

  /** Extra presence on solid ink CTAs in commerce rows (use with `tw.button`). */
  buttonCommerce:
    "px-6 text-[0.8125rem] font-semibold tracking-wider shadow-[0_12px_32px_rgba(34,28,23,0.18)] hover:shadow-[0_14px_36px_rgba(34,28,23,0.22)]",

  /** PDP / editorial — underlined caps row (reference “shop / checkout” strip). */
  linkCommerceUnderline:
    "inline-flex cursor-pointer items-center border-0 bg-transparent pb-0.5 text-left text-[0.6875rem] font-semibold uppercase tracking-[0.14em] text-ink underline decoration-ink/30 underline-offset-[0.38rem] transition-opacity duration-150 hover:opacity-65 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
  buttonGhost:
    "inline-flex min-h-12 cursor-pointer touch-manipulation items-center justify-center gap-2 rounded-pill border border-outline bg-transparent px-[1.2rem] text-ink transition-transform duration-150 ease-out hover:-translate-y-px focus-visible:-translate-y-px",

  /**
   * Primary commerce CTA on cream radial canvases — glass pill, not solid ink (`tw.button`).
   * Used by `EditorialHero` and PDP “Add to bag” beside `qtyStepper`.
   */
  buttonEditorialBag:
    "inline-flex min-h-12 cursor-pointer touch-manipulation items-center justify-center gap-2 rounded-pill border border-ink/30 bg-surface-strong/40 px-6 text-[0.8125rem] font-semibold tracking-wider text-ink shadow-[0_8px_22px_rgba(62,40,27,0.06)] backdrop-blur-[6px] transition-transform duration-150 ease-out hover:-translate-y-px hover:border-ink/45 hover:bg-surface-strong/70 focus-visible:-translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",

  /** Same glass vocabulary as `buttonEditorialBag`, compact height — consent toast, tight stacks. */
  buttonEditorialBagSm:
    "inline-flex min-h-10 cursor-pointer touch-manipulation items-center justify-center gap-2 rounded-pill border border-ink/30 bg-surface-strong/40 px-4 text-sm font-semibold tracking-wider text-ink shadow-[0_6px_18px_rgba(62,40,27,0.06)] backdrop-blur-[6px] transition-transform duration-150 ease-out hover:-translate-y-px hover:border-ink/45 hover:bg-surface-strong/70 focus-visible:-translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:pointer-events-none disabled:opacity-55",

  buttonSecondary:
    "inline-flex min-h-12 cursor-pointer touch-manipulation items-center justify-center gap-2 rounded-pill border-0 bg-success px-[1.2rem] text-white transition-transform duration-150 ease-out hover:-translate-y-px focus-visible:-translate-y-px",
  buttonSmall: "min-h-10 px-4 text-sm",

  chip: "inline-flex min-h-9 items-center rounded-pill bg-accent/10 px-[0.85rem] text-accent-strong",
  chipList: "m-0 flex list-none flex-wrap gap-2 p-0",
  chipInfo: "inline-flex min-h-8 items-center rounded-pill border border-info/30 bg-info/10 px-3 text-xs text-info",
  chipSuccess:
    "inline-flex min-h-8 items-center rounded-pill border border-success/30 bg-success/10 px-3 text-xs text-success",
  chipWarning:
    "inline-flex min-h-8 items-center rounded-pill border border-warning/30 bg-warning/10 px-3 text-xs text-warning",
  chipError: "inline-flex min-h-8 items-center rounded-pill border border-error/30 bg-error/10 px-3 text-xs text-error",

  sectionHeader: "flex flex-col justify-between gap-4 sm:flex-row sm:items-center",
  flexBetween: "flex items-center justify-between gap-4",

  fieldInput: "field-input",

  /** Flat editorial shell (nav + hero) — no glass card */
  heroCanvas: "bg-hero-canvas text-ink",

  /** Post-hero story band — cooler ground than `heroCanvas` */
  storyCanvas: "bg-story-canvas text-ink",

  /**
   * Break out of `PageShell` + padded `main` so editorial bands span the **viewport** rail
   * (same horizontal envelope as the fixed `Header`). Uses full-bleed margins, not `left: 50%`
   * on a padded ancestor, which visually narrows the band vs the nav.
   */
  editorialBreakout:
    "relative -mt-px ml-[calc(50%-50vw)] mr-[calc(50%-50vw)] w-screen max-w-none shrink-0",

  /** Navbar search submit — explicit affordance (pill, not plain text) */
  navSearchSubmit:
    "inline-flex shrink-0 cursor-pointer items-center justify-center rounded-pill border border-outline bg-surface-strong px-3 py-1.5 text-[0.7rem] font-semibold uppercase tracking-[0.1em] text-ink transition-colors duration-150 hover:border-ink hover:bg-ink hover:text-white",

  /**
   * Quiet editorial mat on body canvas — profile, consent, explainability (`UI_REFERENCE.md`).
   * Pair with `labPanelPad`.
   */
  labPanel:
    "rounded-[max(var(--radius-inner),1rem)] border border-outline/35 bg-surface-strong/75 shadow-[0_1px_0_rgba(34,28,23,0.06)] ring-1 ring-inset ring-white/55 backdrop-blur-[10px]",
  labPanelPad: "px-6 py-7 sm:px-8 sm:py-8",
} as const;
