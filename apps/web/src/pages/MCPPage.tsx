import { useState } from "react";
import { Link } from "react-router-dom";

import { tw } from "@/shared/ui/tw";

const eyebrow = `text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`;
const codeBlock =
  "rounded-[max(var(--radius-inner),1rem)] border border-outline/35 bg-ink/[0.035] px-5 py-4 pr-20 sm:px-6 sm:py-5 sm:pr-24 overflow-x-auto font-mono text-[0.78rem] leading-relaxed text-ink/90 whitespace-pre tracking-body";
const inlineCode =
  "rounded-md bg-ink/[0.06] px-1.5 py-0.5 font-mono text-[0.78em] text-ink";

function CopyIcon({ copied }: { copied: boolean }) {
  if (copied) {
    return (
      <svg
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <polyline points="20 6 9 17 4 12" />
      </svg>
    );
  }
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function CopyableCode({ code, className }: { code: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard may be unavailable (insecure context, denied permission); silently no-op
    }
  };

  return (
    <div className={`relative ${className ?? ""}`}>
      <pre className={codeBlock}>
        <code>{code}</code>
      </pre>
      <button
        type="button"
        onClick={handleCopy}
        aria-label={copied ? "Copied to clipboard" : "Copy code to clipboard"}
        aria-live="polite"
        className="absolute right-3 top-3 inline-flex cursor-pointer items-center gap-1.5 rounded-pill border border-outline/45 bg-surface-strong/85 px-2.5 py-1 text-[0.62rem] font-semibold uppercase tracking-[0.14em] text-ink shadow-[0_4px_12px_rgba(34,28,23,0.06)] backdrop-blur-[6px] transition-[transform,background-color,border-color,opacity] duration-150 hover:-translate-y-px hover:border-ink/40 hover:bg-surface-strong focus-visible:-translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        <CopyIcon copied={copied} />
        <span>{copied ? "Copied" : "Copy"}</span>
      </button>
    </div>
  );
}

function PageHero() {
  return (
    <header className="max-w-3xl">
      <p className={`mb-2 ${eyebrow}`}>MCP Integration</p>
      <h1 className={`${tw.storyTitle} max-w-[28ch]`}>
        Drop HyperPersona into any storefront
      </h1>
      <p className={`mt-5 max-w-2xl text-pretty text-sm leading-relaxed ${tw.muted}`}>
        You bring the catalog and the shoppers. We bring the recommendations,
        chain-of-verification, and DPDP/GDPR-ready privacy plumbing. About three
        hours from the first <span className={inlineCode}>curl</span> to a personalized
        rail in production. No ML team, no AWS account, no model selection required.
      </p>
      <dl className="mt-8 grid grid-cols-2 gap-y-4 gap-x-8 sm:grid-cols-4 sm:gap-x-12">
        {[
          ["Time to ship", "~3 hours"],
          ["Surface", "REST + JWT"],
          ["Hosting", "Managed AWS"],
          ["Lock-in", "None"],
        ].map(([k, v]) => (
          <div key={k} className="flex flex-col gap-1">
            <dt className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>
              {k}
            </dt>
            <dd className="text-sm font-medium tracking-body text-ink">{v}</dd>
          </div>
        ))}
      </dl>
    </header>
  );
}

function ArchitectureSection() {
  const stackBox =
    "rounded-[max(var(--radius-inner),1rem)] border border-outline/40 bg-surface-strong/55 px-5 py-4 backdrop-blur-[6px]";
  return (
    <section className="space-y-6">
      <div className="max-w-2xl">
        <p className={eyebrow}>Where it fits</p>
        <h2 className={`${tw.displayH2} mt-2 text-[clamp(1.6rem,2.6vw,2.25rem)]`}>
          One thin client layer in your backend.
        </h2>
        <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
          You write nothing above the dashed line that you don't already have.
          The HyperPersona Client is the only new thing, about eighty lines of
          glue between your routes and our HTTPS API.
        </p>
      </div>

      <div className={`${tw.labPanel} ${tw.labPanelPad}`}>
        <p className={`${eyebrow} mb-4`}>Your ecommerce stack</p>
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:items-stretch">
          <div className={stackBox}>
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-accent-strong">
              Storefront
            </p>
            <p className="mt-2 text-sm leading-relaxed text-ink">
              React, Vue, Svelte, whatever you already ship. Clicks, views,
              and purchases bubble up to your backend.
            </p>
          </div>
          <div className="hidden items-center justify-center text-xs uppercase tracking-[0.18em] text-muted sm:flex">
            events ↓
          </div>
          <div className={stackBox}>
            <p className="text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-accent-strong">
              Your backend
            </p>
            <p className="mt-2 text-sm leading-relaxed text-ink">
              Node, Python, Go, Ruby, PHP, Java. Identity, catalog, checkout
              already there, plus a thin{" "}
              <span className={inlineCode}>HyperPersonaClient</span> module.
            </p>
          </div>
        </div>

        <div
          aria-hidden
          className="my-6 border-t border-dashed border-outline/60"
        />

        <p className={`${eyebrow} mb-4`}>HyperPersona, managed</p>
        <div
          className={`${stackBox} flex flex-wrap items-center justify-between gap-3`}
        >
          <p className="text-sm leading-relaxed text-ink">
            Bedrock · AgentCore · OpenSearch Serverless · DynamoDB · SQS ·
            Comprehend · S3
          </p>
          <span className={tw.chipInfo}>HTTPS + JWT</span>
        </div>
      </div>
    </section>
  );
}

type Step = {
  n: string;
  title: string;
  estimate: string;
  body: string;
  code?: { language: string; content: string };
};

const STEPS: Step[] = [
  {
    n: "01",
    title: "Sign up & get tenant credentials",
    estimate: "2 min",
    body: "One POST to provision a tenant and an API key. Store it in your secret manager. It never leaves your backend.",
    code: {
      language: "bash",
      content: `curl -X POST https://api.hyperpersona.dev/admin/tenants \\
  -H "Content-Type: application/json" \\
  -d '{
    "company": "Acme Outdoor",
    "domain": "acme-outdoor.com",
    "contact_email": "you@acme-outdoor.com"
  }'

# → { "tenant_id": "acme-outdoor",
#     "api_key": "sk_hp_live_xxxxxxxxxxxxxxxx",
#     "base_url": "https://api.hyperpersona.dev" }`,
    },
  },
  {
    n: "02",
    title: "Mint per-shopper JWTs",
    estimate: "15 min",
    body: "Your auth (Auth0, Cognito, NextAuth, Devise…) already knows who's logged in. Exchange the user's id for a scoped, short-lived token.",
    code: {
      language: "javascript",
      content: `import { HyperPersona } from '@hyperpersona/client';

const hp = new HyperPersona({ apiKey: process.env.HYPERPERSONA_API_KEY });

const { token } = await hp.issueToken({
  shopperId: user.id,
  email: user.email,
  scopes: ['personalization', 'analytics'],
  expiresIn: 3600,
});`,
    },
  },
  {
    n: "03",
    title: "Show consent UI, record consent",
    estimate: "30 min",
    body: "DPDP, GDPR, and CPRA require explicit opt-in. Without consent, /events returns 403, by design. Record it once, change it whenever.",
    code: {
      language: "javascript",
      content: `await fetch('https://api.hyperpersona.dev/consent', {
  method: 'POST',
  headers: {
    Authorization: \`Bearer \${token}\`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    scopes: ['personalization', 'analytics'],
    data_retention_days: 90,
  }),
});`,
    },
  },
  {
    n: "04",
    title: "Stream behavior events",
    estimate: "1 hour",
    body: "Every meaningful interaction becomes a POST /events. Six event types cover the full shopping funnel. Use the batch endpoint on high-traffic surfaces.",
  },
  {
    n: "05",
    title: "Render personalized recommendations",
    estimate: "1–2 hours",
    body: "Cache miss runs the agentic path in 16–18s; warm cache returns in under 200ms. Cold-start shoppers auto-route to trending, no extra code.",
    code: {
      language: "javascript",
      content: `const rec = await fetch(
  \`https://api.hyperpersona.dev/recommend?context=\${ctx}&limit=5\`,
  { headers: { Authorization: \`Bearer \${token}\` } }
).then(r => r.json());

// rec.products[]    rec.personalization_reason
// rec.facts_used[]  rec.verifier_status`,
    },
  },
  {
    n: "06",
    title: "Right-to-erasure",
    estimate: "15 min",
    body: "One DELETE wipes the customer atomically across DynamoDB, three OpenSearch indexes, and Redis. Returns audit counts under 500ms.",
    code: {
      language: "javascript",
      content: `await fetch('https://api.hyperpersona.dev/customer', {
  method: 'DELETE',
  headers: { Authorization: \`Bearer \${token}\` },
});
// → { events_deleted: 1247, consent_deleted: true,
//     redis_keys_deleted: 3, vector_collections_cleared: 3 }`,
    },
  },
];

function StepCard({ step }: { step: Step }) {
  return (
    <article className={`${tw.labPanel} ${tw.labPanelPad}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="flex items-baseline gap-4">
          <span
            className={`${tw.displayWordmarkNav} text-2xl text-accent-strong`}
            aria-hidden
          >
            {step.n}
          </span>
          <h3 className={`${tw.displayH2} text-[1.35rem] sm:text-[1.5rem]`}>
            {step.title}
          </h3>
        </div>
        <span className={tw.chipInfo}>{step.estimate}</span>
      </div>
      <p className={`mt-3 max-w-2xl text-sm leading-relaxed ${tw.muted}`}>
        {step.body}
      </p>
      {step.code ? (
        <CopyableCode code={step.code.content} className="mt-5" />
      ) : null}
    </article>
  );
}

const EVENT_TYPES = [
  ["page_view", "shopper visits a product page"],
  ["add_to_cart", "shopper adds an item"],
  ["purchase", "order completes"],
  ["search", "shopper searches"],
  ["wishlist_add", "shopper hearts an item"],
  ["category_view", "shopper opens a department"],
];

function StepsSection() {
  return (
    <section className="space-y-6">
      <div className="max-w-2xl">
        <p className={eyebrow}>The integration</p>
        <h2 className={`${tw.displayH2} mt-2 text-[clamp(1.6rem,2.6vw,2.25rem)]`}>
          Six steps to first recommendation.
        </h2>
        <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
          Steps one through three are mandatory. The rest fall into place
          naturally once your shopper sessions are flowing through us.
        </p>
      </div>

      <div className="grid gap-5">
        {STEPS.map((step) => (
          <StepCard key={step.n} step={step} />
        ))}
      </div>

      <div className={`${tw.labPanel} ${tw.labPanelPad}`}>
        <p className={`${eyebrow} mb-4`}>Step 04 · Event vocabulary</p>
        <ul role="list" className="m-0 grid gap-x-8 gap-y-4 p-0 sm:grid-cols-2">
          {EVENT_TYPES.map(([type, when]) => (
            <li
              key={type}
              className="flex items-start justify-between gap-4 border-b border-outline/20 pb-3 last:border-0"
            >
              <span className={inlineCode}>{type}</span>
              <span className={`text-right text-sm ${tw.muted}`}>{when}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

const FULL_CLIENT_CODE = `// hp.js: drop-in HyperPersona client for an ecommerce backend
import { v4 as uuid } from 'uuid';

const HP_BASE = process.env.HYPERPERSONA_BASE_URL || 'https://api.hyperpersona.dev';
const HP_API_KEY = process.env.HYPERPERSONA_API_KEY;

async function hpRequest(method, path, body, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = \`Bearer \${token}\`;
  else if (HP_API_KEY) headers.Authorization = \`Bearer \${HP_API_KEY}\`;
  const resp = await fetch(\`\${HP_BASE}\${path}\`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) throw new Error(\`hp \${path}: \${resp.status} \${await resp.text()}\`);
  return resp.json();
}

export async function issueShopperToken(shopper) {
  return hpRequest('POST', '/admin/tokens', {
    shopper_id: shopper.id,
    email: shopper.email,
    scopes: shopper.consentScopes,
    expires_in: 3600,
  });
}

export async function trackEvent(token, eventType, payload) {
  return hpRequest('POST', '/events', {
    client_event_id: uuid(),
    event_type: eventType,
    payload,
  }, token);
}

export async function getRecommendation(token, context, limit = 5) {
  return hpRequest(
    'GET',
    \`/recommend?context=\${encodeURIComponent(context)}&limit=\${limit}\`,
    null,
    token,
  );
}

export async function deleteShopper(token) {
  return hpRequest('DELETE', '/customer', null, token);
}`;

function CompleteClientSection() {
  return (
    <section className="space-y-5">
      <div className="max-w-2xl">
        <p className={eyebrow}>The complete client</p>
        <h2 className={`${tw.displayH2} mt-2 text-[clamp(1.6rem,2.6vw,2.25rem)]`}>
          Eighty lines of Node.js.
        </h2>
        <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
          Drop this in <span className={inlineCode}>lib/hp.js</span>, import the
          functions you need from your routes. Same shape works in Python, Go,
          PHP. The wire format is the same.
        </p>
      </div>
      <CopyableCode code={FULL_CLIENT_CODE} />
    </section>
  );
}

const MCP_DESKTOP_CONFIG = `{
  "mcpServers": {
    "hyperpersona": {
      "command": "hyperpersona-mcp",
      "env": {
        "HYPERPERSONA_BASE_URL": "https://api.hyperpersona.dev",
        "HYPERPERSONA_JWT": "<the-shopper's-jwt>"
      }
    }
  }
}`;

function McpServerSection() {
  return (
    <section className="space-y-5">
      <div className="max-w-2xl">
        <p className={eyebrow}>Optional · Step 07</p>
        <h2 className={`${tw.displayH2} mt-2 text-[clamp(1.6rem,2.6vw,2.25rem)]`}>
          MCP server for LLM-powered surfaces.
        </h2>
        <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
          If Claude is already in your shopping assistant, admin dashboard, or
          support flow, give it five tools and answers like “show me Priya's
          recommendation history and explain why we recommended Wildcraft.”
        </p>
      </div>
      <div className={`${tw.labPanel} ${tw.labPanelPad} space-y-4`}>
        <div className="flex flex-wrap items-center gap-3">
          <span className={`${eyebrow} text-ink`}>Install</span>
          <code className={inlineCode}>pip install hyperpersona-mcp</code>
        </div>
        <div>
          <p className={`${eyebrow} mb-2 text-ink`}>Claude Desktop</p>
          <CopyableCode code={MCP_DESKTOP_CONFIG} />
        </div>
      </div>
    </section>
  );
}

const PRICING_TIERS: Array<{
  name: string;
  price: string;
  details: string;
  audience: string;
  emphasis?: boolean;
}> = [
  {
    name: "Free Pilot",
    price: "$0",
    details: "25K events + 5K recs / month. One environment.",
    audience: "Validation, dev, demos",
  },
  {
    name: "Growth",
    price: "$5K + $0.20/rec over 25K",
    details: "Up to 250K recs / month. Production SLAs.",
    audience: "Mid-market retailers ($10–100M)",
    emphasis: true,
  },
  {
    name: "Scale",
    price: "$50K + $0.15/rec over 250K",
    details: "Unlimited events. 99.9% uptime.",
    audience: "$100M–$1B retailers",
  },
  {
    name: "Enterprise",
    price: "$500K+ flat",
    details: "Dedicated VPC, custom SLA, on-prem option.",
    audience: "$1B+, banks, healthcare",
  },
];

function PricingSection() {
  return (
    <section className="space-y-5">
      <div className="max-w-2xl">
        <p className={eyebrow}>Pricing</p>
        <h2 className={`${tw.displayH2} mt-2 text-[clamp(1.6rem,2.6vw,2.25rem)]`}>
          Four tiers. No data lock-in.
        </h2>
        <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
          Optional white-glove integration package: $25K, two-week ship, with
          Cognizant-led pairing instead of two-month internal effort.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {PRICING_TIERS.map((tier) => (
          <article
            key={tier.name}
            className={`${tw.labPanel} ${tw.labPanelPad} flex flex-col gap-3 ${
              tier.emphasis
                ? "ring-1 ring-accent/40 bg-accent/[0.04]"
                : ""
            }`}
          >
            <div className="flex items-baseline justify-between gap-3">
              <h3
                className={`${tw.displayH2} text-[1.35rem]`}
              >
                {tier.name}
              </h3>
              {tier.emphasis ? (
                <span className={tw.chipSuccess}>Most common</span>
              ) : null}
            </div>
            <p className="font-mono text-[0.85rem] tabular-nums text-ink">
              {tier.price}
            </p>
            <p className={`text-sm leading-relaxed ${tw.muted}`}>
              {tier.details}
            </p>
            <p
              className={`mt-auto pt-2 text-[0.7rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}
            >
              {tier.audience}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}

const REQUIRED = [
  ["Authenticated shopper sessions", "We use your IDs. We don't auth your users."],
  ["Consent capture UI", "DPDP/GDPR/CCPA. ~30 min if you don't have one."],
  ["Event instrumentation", "Where to fire POST /events from. ~2–4 hours."],
  ["Recommendation rendering", "A 'for you' component. ~1–2 hours."],
  ["One env var", "HYPERPERSONA_API_KEY in your secret manager."],
];

const NOT_REQUIRED = [
  ["Your customer database", "Events stream in. We build customer memory ourselves."],
  ["Your product catalog", "Optional. Improves recs but isn't required."],
  ["ML expertise", "None. We pick and tune the models."],
  ["Your AWS account", "We host. (Or your AWS, on Enterprise.)"],
  ["Anthropic / OpenAI keys", "We manage all LLM auth via Bedrock."],
];

function RequirementsSection() {
  return (
    <section className="space-y-5">
      <div className="max-w-2xl">
        <p className={eyebrow}>The contract</p>
        <h2 className={`${tw.displayH2} mt-2 text-[clamp(1.6rem,2.6vw,2.25rem)]`}>
          What you bring, what you don't.
        </h2>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <div className={`${tw.labPanel} ${tw.labPanelPad}`}>
          <p className={`${eyebrow} text-success`}>You bring</p>
          <ul role="list" className="m-0 mt-4 space-y-3 p-0">
            {REQUIRED.map(([title, body]) => (
              <li
                key={title}
                className="border-b border-outline/20 pb-3 last:border-0"
              >
                <p className="text-sm font-medium tracking-body text-ink">
                  {title}
                </p>
                <p className={`mt-1 text-sm leading-relaxed ${tw.muted}`}>
                  {body}
                </p>
              </li>
            ))}
          </ul>
        </div>
        <div className={`${tw.labPanel} ${tw.labPanelPad}`}>
          <p className={`${eyebrow} text-accent-strong`}>You skip</p>
          <ul role="list" className="m-0 mt-4 space-y-3 p-0">
            {NOT_REQUIRED.map(([title, body]) => (
              <li
                key={title}
                className="border-b border-outline/20 pb-3 last:border-0"
              >
                <p className="text-sm font-medium tracking-body text-ink line-through decoration-ink/20">
                  {title}
                </p>
                <p className={`mt-1 text-sm leading-relaxed ${tw.muted}`}>
                  {body}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

const FAQS: Array<[string, string]> = [
  [
    "How long until first recommendation works?",
    "About three hours of integration time. Time-to-meaningful-personalization is roughly 50 to 100 events per shopper, usually within their first session.",
  ],
  [
    "What if I don't have an LLM-powered surface?",
    "Skip the MCP path entirely. The REST API is the whole product; MCP is a thin wrapper for in-app Claude.",
  ],
  [
    "Can I run it in my own AWS account?",
    "Enterprise tier. We ship a CDK construct + Terraform module that deploys the full stack into your account. You keep the data; we operate the agents.",
  ],
  [
    "What models am I paying for under the hood?",
    "Sonnet 4.5 for orchestration and fact extraction. Opus 4.5 for offer generation and verification. Titan Embed v2 for vectors. All via Bedrock. You don't pick.",
  ],
  [
    "How do I migrate off?",
    "GET /export/customer/{id} returns the customer's facts, behaviors, and recommendations as JSONL. We don't lock you in. Build moats through quality, not data hostage-taking.",
  ],
  [
    "What's the SLA?",
    "Free: best-effort. Growth: 99.5% uptime, 30s p95 recommend latency. Scale and Enterprise: 99.9% uptime, dedicated support.",
  ],
  [
    "What if Bedrock has an outage?",
    "BEDROCK_MODE=mock is the graceful-degradation fallback. Recommendations switch to deterministic offers. Better than 500ing your shoppers.",
  ],
  [
    "How do you keep PII out of model providers?",
    "AWS Comprehend redacts PII before anything reaches Bedrock. The pipeline is architecturally incapable of sending raw PII to a model.",
  ],
  [
    "What about data residency?",
    "Default us-east-1. ap-south-1 (Mumbai), eu-central-1 (Frankfurt), or any other region for $1K/month per added region. Data never leaves the region you pick.",
  ],
];

function FaqSection() {
  return (
    <section className="space-y-5">
      <div className="max-w-2xl">
        <p className={eyebrow}>FAQ</p>
        <h2 className={`${tw.displayH2} mt-2 text-[clamp(1.6rem,2.6vw,2.25rem)]`}>
          Common questions, short answers.
        </h2>
      </div>
      <ul role="list" className="m-0 grid list-none gap-3 p-0">
        {FAQS.map(([q, a]) => (
          <li key={q}>
            <details
              className={`${tw.labPanel} group px-6 py-5 sm:px-8 [&_summary::-webkit-details-marker]:hidden`}
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-medium tracking-body text-ink">
                <span>{q}</span>
                <span
                  aria-hidden
                  className="shrink-0 text-lg leading-none text-muted transition-transform duration-200 group-open:rotate-45"
                >
                  +
                </span>
              </summary>
              <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>{a}</p>
            </details>
          </li>
        ))}
      </ul>
    </section>
  );
}

const DEMO_CURL = `# 1. Register a tenant (stand-in for /admin/tokens during pilot):
curl -X POST http://localhost:8000/register \\
  -H "Content-Type: application/json" \\
  -d '{"email":"prospect@acme.com","password":"demo-password-123"}'
# → { "token": "...", "customer_id": "..." }

# 2. Track a purchase:
TOKEN="<paste from step 1>"
curl -X POST http://localhost:8000/events \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"client_event_id":"e1","event_type":"purchase","payload":{"product":"wildcraft trail shoes","price":4999}}'

# 3. Set consent so /recommend will work:
curl -X POST http://localhost:8000/consent \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"scopes":["personalization","analytics"]}'

# 4. Wait ~10s for the worker, then ask for a rec:
sleep 10
curl "http://localhost:8000/recommend?context=hiking%20gear" \\
  -H "Authorization: Bearer $TOKEN"
# → JSON with offer, products, facts_used, verifier_status, path`;

function DemoSection() {
  return (
    <section className="space-y-5">
      <div className="max-w-2xl">
        <p className={eyebrow}>60-second demo</p>
        <h2 className={`${tw.displayH2} mt-2 text-[clamp(1.6rem,2.6vw,2.25rem)]`}>
          Four curl commands, end-to-end.
        </h2>
        <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
          Pasteable from any terminal pointed at the running pilot. Anything
          else (MCP, batch ingest, deletion) is a one-line addition on top.
        </p>
      </div>
      <CopyableCode code={DEMO_CURL} />
    </section>
  );
}

function ClosingCTA() {
  return (
    <section
      className={`${tw.labPanel} ${tw.labPanelPad} flex flex-col items-start gap-5 sm:flex-row sm:items-center sm:justify-between`}
    >
      <div className="max-w-2xl">
        <p className={eyebrow}>Ready when you are</p>
        <h2 className={`${tw.displayH2} mt-2 text-[clamp(1.5rem,2.4vw,2rem)]`}>
          Try the demo storefront, or wire up the live API.
        </h2>
      </div>
      <div className="flex flex-wrap gap-3">
        <Link to="/demo" className={tw.buttonEditorialBag}>
          Open demo lab
        </Link>
        <Link to="/catalog" className={tw.buttonEditorialBag}>
          Browse catalog
        </Link>
      </div>
    </section>
  );
}

export function MCPPage() {
  return (
    <div
      className={`${tw.stackLg} min-h-[min(76vh,880px)] gap-12 pt-8 pb-12 sm:gap-14 sm:pt-10 sm:pb-14 lg:gap-16 lg:pt-12 lg:pb-16`}
    >
      <PageHero />
      <ArchitectureSection />
      <StepsSection />
      <CompleteClientSection />
      <McpServerSection />
      <PricingSection />
      <RequirementsSection />
      <FaqSection />
      <DemoSection />
      <ClosingCTA />
    </div>
  );
}
