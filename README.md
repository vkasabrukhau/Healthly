# Nuxt Minimal Starter

Look at the [Nuxt documentation](https://nuxt.com/docs/getting-started/introduction) to learn more.

## Setup

Make sure to install dependencies:

```bash
# npm
npm install

# pnpm
pnpm install

# yarn
yarn install

# bun
bun install
```

## Development Server

Start the development server on `http://localhost:3000`:

```bash
# npm
npm run dev

# pnpm
pnpm dev

# yarn
yarn dev

# bun
bun run dev
```

## Production

Build the application for production:

```bash
# npm
npm run build

# pnpm
pnpm build

# yarn
yarn build

# bun
bun run build
```

Locally preview production build:

```bash
# npm
npm run preview

# pnpm
pnpm preview

# yarn
yarn preview

# bun
bun run preview
```

Check out the [deployment documentation](https://nuxt.com/docs/getting-started/deployment) for more information.

## Additional: Clerk -> MongoDB user sync

This project includes a small server endpoint that upserts Clerk user information into your MongoDB cluster when called.

- Endpoint: POST /api/users/sync
- Body: { user: { id, email, first_name, last_name, created_at, ... } }

Two ways to use it:

1. Configure a Clerk webhook to POST the user payload to your deployed `/api/users/sync` URL when users are created/signed in (recommended for automatic sync).
2. From the client, use the "Sync profile to DB" button in the dashboard to send your profile manually (useful in dev).

Make sure to set your Mongo connection string in the environment variable `MONGO_URI` (do NOT commit secrets). See `.env.example`.

Dependencies: the server uses the official `mongodb` Node driver; install dependencies with `npm install`.

## Clerk integration

The project supports two server-side features to integrate Clerk with MongoDB:

1. Webhook handling (recommended):

   - Configure a Clerk webhook to POST user events to your deployed `/api/users/sync` URL.
   - In your environment, set `CLERK_WEBHOOK_SECRET` to the secret you configure in Clerk. The server will verify the webhook signature (HMAC-SHA256) using that secret and reject invalid requests.

2. Server-side verification/fetching (optional):
   - If you set `CLERK_API_KEY` in your environment, the `/api/users/sync` handler will also fetch the authoritative user record from Clerk Admin API before upserting into MongoDB. This ensures stored profile fields are accurate.
   - A helper endpoint `/api/users/verify` is provided which accepts POST { userId } and returns the Clerk Admin API user when `CLERK_API_KEY` is present.

Environment variables to set (examples):

```
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.18nn6sj.mongodb.net/?appName=Cluster0
CLERK_WEBHOOK_SECRET=your_clerk_webhook_secret   # optional but recommended for security
CLERK_API_KEY=sk_live_xxx                         # optional, used to call Clerk Admin API
```

Clerk webhook notes (assumptions):

- This implementation assumes Clerk signs webhook payloads by computing an HMAC-SHA256 of the raw JSON payload and placing the signature as a hex string in the `x-clerk-signature` header. If your Clerk plan provides a different signing format, set `CLERK_WEBHOOK_SECRET` and adapt the verification logic accordingly.

If you'd like, I can update the webhook verification to use Clerk's official verification helper from `@clerk/clerk-sdk-node` once you provide the exact webhook signing method or webhook secret example — or I can add full signature verification using Clerk's SDK (requires `CLERK_API_KEY`/SDK usage). Let me know which you prefer.
