// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

/** Products are records from examples/retail/data/catalog.json. */

import type {
  CartPayload,
  CheckoutPayload,
  ComparisonPayload,
  GuidePayload,
  OrderStatusPayload,
  PlanPayload,
  Product,
  ProductsPayload,
} from "./types";

const BLOCK_SET: Product = {
  product_id: "AR-1401",
  title: "ACME Playroom Stacking Wooden Block Set (54 pc)",
  brand: "ACME Playroom",
  price: 34.0,
  rating: 4.8,
  review_count: 2940,
  image_url: "/products/AR-1401.webp",
  category: "toys-games",
  labels: ["bestseller"],
  attributes: {
    pieces: "54 blocks + 12 idea cards",
    age_range: "4-10 years",
    material: "beechwood, water-based paint",
    storage: "cotton carry sack",
  },
  in_stock: true,
};

const PUZZLE: Product = {
  product_id: "AR-2104",
  title: "ACME Makers 300-Piece Meadow Puzzle",
  brand: "ACME Makers",
  price: 27.0,
  rating: 4.4,
  review_count: 1530,
  image_url: "/products/AR-2104.webp",
  category: "kids-room",
  attributes: {
    pieces: "300",
    finished_size: "18 x 24 in",
    art: "original meadow illustration",
    age_range: "8+",
  },
  in_stock: true,
};

const POSTER_SET: Product = {
  product_id: "AR-2108",
  title: "ACME Playroom Solar System Poster Set (4 pc)",
  brand: "ACME Playroom",
  price: 18.0,
  rating: 4.6,
  review_count: 980,
  image_url: "/products/AR-2108.webp",
  category: "kids-room",
  attributes: {
    count: "4 posters",
    size: "16 x 20 in",
    finish: "matte, glare-free",
    theme: "space",
  },
  in_stock: true,
};

const WALL_DECALS: Product = {
  product_id: "AR-2102",
  title: "ACME Kids Peel-and-Stick Ocean Wall Decals (36 pc)",
  brand: "ACME Kids",
  price: 24.0,
  rating: 4.6,
  review_count: 2440,
  category: "kids-room",
  attributes: {
    count: "36 decals",
    removable: "yes",
    largest: "24 in whale",
    theme: "ocean",
    // Same count as merchant_inventory.json shows in the portal.
    low_stock: "3",
  },
  in_stock: true,
};

const STORYBOOK_BEAR: Product = {
  product_id: "AR-2105",
  title: "ACME Playroom Storybook Bear (14 in)",
  brand: "ACME Playroom",
  price: 32.0,
  rating: 4.8,
  review_count: 2110,
  category: "kids-room",
  labels: ["bestseller"],
  attributes: { size: "14 in", material: "plush, embroidered eyes", washable: "machine wash, gentle", age_range: "3+" },
  in_stock: true,
};

const STORAGE_BINS: Product = {
  product_id: "AR-2106",
  title: "ACME Kids Toy Storage Bins (Set of 3)",
  brand: "ACME Kids",
  price: 29.0,
  rating: 4.5,
  review_count: 720,
  category: "kids-room",
  attributes: {
    count: "3 bins",
    collapsible: "yes",
    labels: "beachcombing icons",
    theme: "ocean",
  },
  in_stock: true,
};

const products: ProductsPayload = {
  title: "Gifts for a 9-Year-Old Builder (~$45)",
  layout: "carousel",
  items: [
    {
      product: BLOCK_SET,
      reason: "Bestseller with idea cards that turn a pile into bridges and towns.",
    },
    {
      product: PUZZLE,
      reason: "An afternoon at the table with a frame-worthy finish.",
    },
    {
      product: POSTER_SET,
      reason: "Reference-wall decor that answers her questions.",
    },
    {
      product: STORYBOOK_BEAR,
      reason: "The soft option — the bear that ends up in every photo.",
    },
  ],
};

const comparison: ComparisonPayload = {
  title: "Block Set vs. Puzzle for a 9-Year-Old",
  entries: [
    {
      product_id: "AR-1401",
      product: BLOCK_SET,
      best_for: "Active, hands-on building and a kid who rebuilds bigger every time",
      pros: [
        "Solid beechwood — no small parts to snap, survives being stepped on",
        "Water-based paint holds up through a year of rough play (per reviews)",
        "Idea cards add structure without turning play into homework",
      ],
      cons: ["54 pieces to keep track of", "Carry sack fills fast during cleanup races"],
    },
    {
      product_id: "AR-2104",
      product: PUZZLE,
      best_for: "Quiet-table focus and a kid who loves finishing things",
      pros: [
        "300 pieces sits right at the 8+ sweet spot",
        "Original meadow art — frame-worthy once finished",
        "The calm-afternoon gift parents thank you for",
      ],
      cons: [
        "Cardboard — less durable than solid wood if bent",
        "Mostly a one-builder activity at the table",
      ],
    },
  ],
  dimensions: ["Sturdiness", "Age appropriateness (9)", "Play engagement", "Price"],
  recommended_product_id: "AR-1401",
};

const plan: PlanPayload = {
  title: "Kids' Room Refresh",
  intro: "Three coordinated steps that turn the spare wall into the fun wall.",
  steps: [
    { label: "The centerpiece", detail: "One hero piece the room hangs off", products: [WALL_DECALS] },
    { label: "The soft layer", detail: "Something to hug during story time", products: [STORYBOOK_BEAR] },
    { label: "The cleanup game", detail: "Bins that make sorting part of play", products: [STORAGE_BINS] },
    {
      label: "Already covered: the reading nook",
      detail: "Your beanbag fits the corner as-is — nothing to buy.",
      products: [],
    },
  ],
};

const guide: GuidePayload = {
  title: "Keeping plush toys clean",
  sections: [
    {
      heading: "Machine washing",
      body: "Plush with embroidered eyes and sewn seams can go through a gentle cold cycle in a pillowcase. Air-dry fully before it goes back to bed duty.",
    },
    {
      heading: "Between washes",
      body: "A lint roller and ten minutes in the sun handle most weeks. Spot-clean spills right away so they don't set into the pile.",
    },
  ],
  related_products: [STORYBOOK_BEAR],
};

const order_status: OrderStatusPayload = {
  order_id: "AR-77903",
  summary:
    "The ACME Paws Orthopedic Dog Bed was placed June 10 and is marked delayed — the delivery estimate was revised to June 27 after the original June 21 date was missed.",
  next_step: "Track the package for the latest carrier update, or ask me about your options.",
  order: {
    order_id: "AR-77903",
    status: "delayed",
    placed_at: "2026-06-10",
    items: [
      {
        product_id: "AR-1501",
        title: "ACME Paws Orthopedic Memory Foam Dog Bed, Large",
        quantity: 1,
        price: 79.0,
      },
    ],
    total: 79.0,
    currency: "USD",
    // Same shape as the orders fixture: current estimate first, missed original in the note.
    estimated_delivery:
      "2026-06-27 (updated after a carrier delay; the original 2026-06-21 estimate was missed)",
    tracking_url: "https://track.example.com/AR-77903",
  },
};

/** A delivered cart as `examples/delivered/api/delivered_cart.py` shapes it: two markets, a fee line, an option line, an expired line. */
export const SHOWCASE_CART: CartPayload = {
  items: [
    {
      product_id: "smart_store:11314403854#137751",
      title: "요넥스 배드민턴 라켓 세트",
      price: 30000,
      quantity: 2,
      line_total: 60000,
    },
    { product_id: "smart_store:10791906854", title: "줄넘기 스피드 로프", price: 5000, quantity: 1, line_total: 5000 },
    { product_id: "bunjang:429925416", title: "중고 기계식 키보드", price: 45000, quantity: 1, line_total: 45000 },
  ],
  item_count: 4,
  subtotal: 110000,
  currency: "KRW",
  delivered_cart: {
    groups: [
      {
        market_sub_type: "SMART_STORE",
        market_name: "스마트스토어",
        is_bundled: false,
        items: [
          {
            buy_request_id: 1010074,
            product_id: "smart_store:11314403854#137751",
            product_url: "https://smartstore.naver.com/main/products/11314403854",
            fees: [
              { fee_type: "UNIT_PRICE", cost_krw: 30000, cost_usd: 22.1 },
              { fee_type: "DOMESTIC_SHIPPING_PRICE", cost_krw: 3000, cost_usd: 2.2 },
            ],
            line_total: 63000,
            options: [{ name: "색상", value: "White" }],
            is_expired: false,
            is_selling: true,
          },
          {
            buy_request_id: 1010075,
            product_id: "smart_store:10791906854",
            product_url: "https://smartstore.naver.com/main/products/10791906854",
            fees: [{ fee_type: "UNIT_PRICE", cost_krw: 5000, cost_usd: 3.7 }],
            line_total: 5000,
            options: [],
            is_expired: false,
            is_selling: true,
          },
        ],
      },
      {
        market_sub_type: "BUNJANG",
        market_name: "번개장터",
        is_bundled: true,
        items: [
          {
            buy_request_id: 1010076,
            product_id: "bunjang:429925416",
            product_url: "https://m.bunjang.co.kr/products/429925416",
            fees: [{ fee_type: "UNIT_PRICE", cost_krw: 45000, cost_usd: 33.0 }],
            line_total: 45000,
            options: [],
            is_expired: true,
            is_selling: false,
          },
        ],
      },
    ],
  },
};

const checkout: CheckoutPayload = {
  note: "Two markets, three items still on sale — delivered settles fees and shipping.",
  fulfillment_method: "shipping",
  cart: SHOWCASE_CART,
  handoffs: [{ url: "https://www.delivered.co.kr/cart", label: "Continue on delivered" }],
};

export const SHOWCASE = { products, comparison, plan, guide, order_status, checkout };
