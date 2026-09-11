# delivered

The shopping agent over delivered's live guest catalog: the multi-market product search
(Bunjang, Weverse Shop, Poca Market, YES24, Aladin, Ktown4u, Makestar, Smart Store) and the
Naver Smart Store listing with its detail route. Prices are in won; every product ships
abroad through delivered (a seller's export flag is ignored); the cart is per-session state
in this process and `checkout` hands off to delivered's own checkout. There is no
merchant portal, and orders, policies, and fulfillment are switched off in the config.

## Run

```bash
python scripts/run_demo.py delivered            # API :8004 + storefront :3004
```

Or start the pieces yourself, after `npm ci` in `examples/`:

```bash
uvicorn delivered.api.main:app --app-dir examples --reload --port 8004
(cd examples/delivered/storefront-web && npm run dev)     # :3004
```

Chat needs `ANTHROPIC_API_KEY` in the repo-root `.env` or the environment; browsing the
catalog does not. `DELIVERED_API_URL` points the backend at another gateway (the
production guest API is the default). The home page lists the first Smart Store pages,
fetched at boot; a boot without network shows an empty listing and logs why.

## Try

Storefront (`scripts/smoke_chat.py --vertical delivered` runs the same three turns):

1. 줄넘기 하나 사려고 하는데 3만원 이하로 괜찮은 거 찾아줘.
2. 위에 두 개 비교해줘. 가격이랑 배송비 위주로.
3. 첫 번째 걸로 장바구니에 담아줘.

Single prompts, each in a fresh session:

| Prompt | A good answer |
|---|---|
| 뉴진스 굿즈 뭐 있어? | One search for "뉴진스" or "NewJeans"; cards from several markets, each naming its market and whether it is used. |
| BTS 앨범 중고로 싼 거 있어? | Searches "BTS" with `condition: 중고`, shows Bunjang listings first, and states the domestic shipping fee where the record carries one. |
| 이 텀블러 재고 있어? 해외 배송 돼? | Reads the Smart Store detail for the stock count, and says delivered ships it abroad with the fee quoted at checkout. |
| 나이키 운동화 찾아줘 | The multi-market search answers "unsupported market" and the Smart Store listing finds nothing; the answer says so instead of inventing a product. |

## What is specific to this example

- `api/delivered_backend.py`: the mapping from delivered records to `Product` and
  `ProductDetails` (ids are `market:id`, prices the discounted won figure, market and
  condition as attributes), `DeliveredClient` over the three routes, and
  `DeliveredStorefront`, the `StorefrontBackend` with a per-process cache of every record
  a call returned so ids resolve on markets without a detail route.
- `api/agent_config.py`: `domain_search_notes` describing the Korean catalog and its
  markets; orders, policies, and fulfillment off.
- `data/users.json`: one guest profile; `data/memory-seed.json` is empty.
- `storefront-web/`: the retail storefront with delivered's name, port 3004, and no
  returns or free-shipping copy (those terms are delivered's checkout's to state).
- `api/tests/fixtures/`: recorded responses of the three routes; the tests run over them
  with `httpx.MockTransport` and never reach the network.

## Quirks of the guest API the backend absorbs

- The multi-market search accepts one keyword its markets know (뉴진스, 텀블러, BTS) and
  answers the same keyword with extra words (뉴진스 굿즈) with HTTP 400
  (`NOT_SUPPORT_MARKETS`), and a page size under 20 with HTTP 404 (`SP-001`). A rejected
  query is retried one word at a time (`query_variants`); a miss on every word counts as no
  results from that source, and the Smart Store listing still answers.
- The gateway lists one market's results first, so the merged page is interleaved across
  markets (`interleave_by_market`) before the limit is applied.
- Bunjang image URLs carry a literal `{cnt}` slot; the backend substitutes the first image.
- Only Smart Store has a detail route; other markets' records come from the search cache.
