# delivered

The shopping agent over delivered's live guest catalog: the multi-market product search
(16 markets — Smart Store, Musinsa, Olive Young, Daiso, DK Shop, Bunjang, Weverse Shop,
Poca Market, YES24, Aladin, Ktown4u, Makestar, Fans, Witchform, Be On D, Giftifan Shop) and
the Naver Smart Store listing with its detail route. Prices are in won; every product ships
abroad through delivered (a seller's export flag is ignored); the cart is the customer's real delivered cart
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
catalog does not. `DELIVERED_API_URL` points the catalog at another gateway (the
production guest API is the default); `DELIVERED_AUTH_URL` and
`DELIVERED_CUSTOMER_API_URL` point sign-in and the customer API elsewhere (production,
`https://gw.delivered.co.kr`, is the default for all three, so a delivered account is
needed to sign in; point all three at staging together to work there). The home page lists the first Smart Store pages, fetched at boot; a boot without
network shows an empty listing and logs why.

## Sign-in

A session starts as a guest: search and product details work, the cart and checkout
need a delivered account. The host holds the token beside the session; the browser keeps
only `X-Session-Id`, and no response carries a token.

| Route | Does |
|---|---|
| `POST /api/session/login` `{email, password, remember_me?}` | Signs in through the delivered auth gateway and reads the profile. With `X-Session-Id` the credential attaches to that session (the conversation continues); without it a new session starts. 401 `invalid_credentials`, 502 `auth_unavailable`. |
| `POST /api/session/logout` | Drops the token; the same session continues as a guest. |
| `GET /api/session/me` | `{session_id, user_id, signed_in, name, tier, country}` for the header. |

A guest asking to add to the cart gets sign-in guidance from the agent; a customer API
answer of `Expired Token` drops the credential and the agent asks for a fresh sign-in.

### Signing in from the storefront

The storefront (port 3004) shows an account strip under the app bar. A guest sees
"Browsing as a guest" and a **Sign in** button; the button opens a sheet that takes a
delivered email and password (the API signs in against production by default) and turns
the same session into a member session, so the conversation continues. When the
assistant answers that sign-in is needed, a **Sign in to continue** chip appears under
the conversation, and a guest tapping Add on a product card opens the same sheet.
The browser keeps only the session id, in `sessionStorage`, so a reload continues
the session while the tab stays open; **Sign out** returns the same session to a
guest and empties the cart panel.

## Cart

A signed-in session's cart is delivered's own cart, the one the delivered website shows.
delivered keeps a cart in two steps, and the backend follows them: adding a product first
creates a **buy request** on the route for the product's market (`POST /v1/buy-request/rpa-store`
for the RPA markets — Smart Store, Daiso, Musinsa, Olive Young, Weverse, YES24, Ktown4u,
Poca Market, Makestar, Aladin, Witchform, Be On D, Fans; `POST /v2/buy-request/bunjang` for
Bunjang; `POST /v2/buy-request/shop` for the DK shop), then attaches its id with
`POST /v2/cart/add-carts`. `GET /v3/cart` is read after every write and before every turn;
`DELETE /v2/cart` removes a line; a quantity change deletes and recreates the buy request,
since delivered has no quantity route. A line's buy-request id is the listing item's
`cart_id`; lines added on the website are named through `GET /v2/cart/{id}` once and cached.

The framework's `Cart` carries product id, title, unit price (delivered's `UNIT_PRICE` in
won), quantity, and image; delivered's fee lines, market groups, and expiry ride on the cart
payload under `delivered_cart` for the page. delivered's refusals (`CART-005` cart full,
a sold-out product, an unknown market) reach the agent as Korean sentences it relays;
`CART-004` (already in the cart) and `CART-001` (already gone) are absorbed.

The catalog and the customer API must point at the same delivered environment: a buy
request names a product the customer API has to know. All three defaults point at production; to work against staging, set
`DELIVERED_API_URL`, `DELIVERED_AUTH_URL`, and `DELIVERED_CUSTOMER_API_URL` together.

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
| 나이키 운동화 찾아줘 | One search for "나이키" or "운동화"; cards from Musinsa, Olive Young, and Smart Store, each naming its market. |
| (guest) 이거 장바구니에 담아줘 | No cart write; the agent says a delivered sign-in is needed first. |
| (signed in) 첫 번째 상품 담아줘 | A buy request on the product's market route, attached to the delivered cart; the panel shows the re-read cart. |
| (signed in) 내 등급이 뭐야? | Reads the account context: member tier and country from the delivered profile. |

## What is specific to this example

- `api/delivered_backend.py`: the mapping from delivered records to `Product` and
  `ProductDetails` (ids are `market:id`, prices the discounted won figure, market and
  condition as attributes), `DeliveredClient` over the three routes, and
  `DeliveredStorefront`, the `StorefrontBackend` with a per-process cache of every record
  a call returned so ids resolve on markets without a detail route.
- `api/delivered_auth.py`: `DeliveredAuthClient` (sign-in on the auth gateway, Bearer
  calls on the customer API, `Expired Token` detection), `CredentialStore` (token and
  profile per session id, outside the session's state document), and the sign-in
  exceptions. `api/session_routes.py` adds the three session routes;
  `api/delivered_executor.py` turns `SignInRequired`/`TokenExpired` into guidance for the
  customer instead of a "temporarily unavailable" line.
- `api/agent_config.py`: `domain_search_notes` describing the Korean catalog, its markets,
  and the sign-in rule; orders, policies, and fulfillment off.
- `data/users.json`: one guest profile; `data/memory-seed.json` is empty.
- `storefront-web/`: the retail storefront with delivered's name, port 3004, and no
  returns or free-shipping copy (those terms are delivered's checkout's to state).
- `api/tests/fixtures/`: recorded responses of the three catalog routes; the tests run
  over them with `httpx.MockTransport` and never reach the network. `test_delivered_auth.py`
  and `test_session_routes.py` play the auth gateway the same way.

## Quirks of the guest API the backend absorbs

- The multi-market search picks markets from the keyword unless the request lists them,
  and answers a keyword it cannot place (나이키, 화장품, 뉴진스 굿즈) with HTTP 400
  (`NOT_SUPPORT_MARKETS`); it also refuses a `shop_types` list naming `OTHER`, and a page
  size under 20 with HTTP 404 (`SP-001`). The backend names every supported market
  (`SUPPORTED_SHOP_TYPES`, 16 types) on each call, which makes any keyword searchable; a
  rejection that still comes back is retried one word at a time (`query_variants`), and a
  miss on every word counts as no results from that source while the Smart Store listing
  still answers. The page fills its first twenty slots from the shop markets and appends
  Bunjang after them, so the backend asks for forty (`SEARCH_PAGE_SIZE`).
- The gateway lists one market's results first, so the merged page is interleaved across
  markets (`interleave_by_market`) before the limit is applied.
- Bunjang image URLs carry a literal `{cnt}` slot; the backend substitutes the first image.
- Only Smart Store has a detail route; other markets' records come from the search cache.
