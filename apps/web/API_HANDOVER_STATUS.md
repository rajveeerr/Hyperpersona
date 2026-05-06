# API Handover Status (Reality Check)

Last updated: 2026-05-05

This file reconciles three things:
- current **real backend** code under `server/src/routes`
- current **frontend client expectations** in `src/shared/api/client.ts`
- the **contract target** in `API_REQUIREMENTS.md`

## 1) Real backend APIs already implemented

These exist in `server/src/routes` and should be considered available now:

- `GET /health`
- `POST /events` (consent-gated, creates job, queues worker processing)
- `GET /recommend` (cache + async job wait pattern)
- `POST /consent`
- `GET /consent/{customer_id}`
- `GET /jobs/{job_id}`
- `GET /traces/{job_id}`
- `DELETE /customer/{customer_id}`

## 2) Frontend APIs currently implemented only in mock/MSW

These power the web app today but are not yet exposed by the real server routes:

- Catalog/listing:
  - `GET /catalog/categories`
  - `GET /catalog/facets`
  - `GET /catalog/products`
  - `GET /catalog/popular`
  - `GET /catalog/products/{slug}`
- Reviews/UGC:
  - `GET /catalog/products/{slug}/reviews`
  - `POST /catalog/products/{slug}/reviews`
  - `PUT /catalog/products/{slug}/reviews/{reviewId}/helpful`
- Search:
  - `GET /search`
- Recommendations (surface rails):
  - `GET /recommendations/home`
  - `GET /recommendations/pdp`
  - `GET /recommendations/cart`
  - `GET /recommendations/profile`
- Consent/profile/debug convenience:
  - `GET /consent`
  - `PUT /consent`
  - `GET /me/profile`
  - `PATCH /me/preferences`
  - `GET /me/explanations`
  - `GET /debug/events`
- Checkout/orders/addresses:
  - `POST /checkout`
  - `GET /me/orders`
  - `PATCH /me/orders/{orderId}/delivery-address`
  - `GET /me/addresses`
  - `PATCH /me/addresses/{id}`

## 3) Integration decision

- Keep current frontend mock flows for the endpoints in section 2.
- Start wiring frontend to real server first for section 1 (`/events`, `/recommend`, `/jobs`, `/traces`, consent read/write shape alignment).
- Keep `API_REQUIREMENTS.md` as the target contract and use this file as execution status.

## 4) What can be marked done in backend handover

Done now:
- event ingestion + async job queue handoff
- recommendation generation endpoint shape (single endpoint flow)
- consent CRUD (currently `POST` + `GET /consent/{customer_id}`)
- job status endpoint
- trace lookup endpoint
- right-to-delete endpoint

Still pending for full frontend parity:
- all catalog/search/review/order/address endpoints listed in section 2
- plural recommendation history endpoints (`GET /recommendations`, `GET /recommendations/{id}`)
- contract normalization differences (`GET /consent` + `PUT /consent` in web client)
