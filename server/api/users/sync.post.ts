import { MongoClient } from 'mongodb'
import crypto from 'crypto'

// Simple cached client to avoid reconnecting repeatedly
let cachedClient: MongoClient | null = null
async function getClient(uri: string){
  if(cachedClient) return cachedClient
  const client = new MongoClient(uri)
  await client.connect()
  cachedClient = client
  return client
}

function computeHmac(secret: string, payload: string){
  return crypto.createHmac('sha256', secret).update(payload).digest('hex')
}

export default defineEventHandler(async (event) => {
  // parsed body
  const body = await readBody(event)

  const config = useRuntimeConfig()
  const uri = config?.PUBLIC_MONGO_URI || process.env.MONGO_URI
  if(!uri) return sendError(event, createError({ statusCode: 500, statusMessage: 'MONGO_URI not configured' }))

  // Optional: verify webhook signature when CLERK_WEBHOOK_SECRET is set
  const webhookSecret = config?.CLERK_WEBHOOK_SECRET || process.env.CLERK_WEBHOOK_SECRET
  if(webhookSecret){
    const sigHeader = getRequestHeader(event, 'x-clerk-signature') || getRequestHeader(event, 'X-Clerk-Signature')
    if(!sigHeader) return sendError(event, createError({ statusCode: 400, statusMessage: 'Missing signature header' }))

    const payloadStr = JSON.stringify(body)
    const expected = computeHmac(webhookSecret, payloadStr)

    // signature must be hex string and same length
    if(typeof sigHeader !== 'string' || sigHeader.length !== expected.length){
      return sendError(event, createError({ statusCode: 401, statusMessage: 'Invalid webhook signature' }))
    }

    const sigBuf = Buffer.from(sigHeader, 'hex')
    const expBuf = Buffer.from(expected, 'hex')
    if(sigBuf.length !== expBuf.length || !crypto.timingSafeEqual(sigBuf, expBuf)){
      return sendError(event, createError({ statusCode: 401, statusMessage: 'Invalid webhook signature' }))
    }
  }

  const user = body?.user
  if(!user || !user.id) return sendError(event, createError({ statusCode: 400, statusMessage: 'Invalid payload: missing user' }))

  try{
    const client = await getClient(uri)
    const db = client.db('healthly')
    const users = db.collection('users')

    let docUser = user

    // If CLERK_API_KEY is set, fetch authoritative profile from Clerk Admin API
    const clerkApiKey = config?.CLERK_API_KEY || process.env.CLERK_API_KEY
    if(clerkApiKey){
      try{
        const clerkRes = await $fetch(`https://api.clerk.com/v1/users/${encodeURIComponent(user.id)}`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${clerkApiKey}` }
        })
        docUser = clerkRes as any
      }catch(err){
        console.error('Failed to fetch user from Clerk Admin API', err)
        // continue with provided payload
      }
    }

    const doc = {
      _id: docUser.id,
      email: docUser.email_addresses?.[0]?.email_address ?? docUser.email ?? null,
      firstName: docUser.first_name ?? docUser.firstName ?? null,
      lastName: docUser.last_name ?? docUser.lastName ?? null,
      createdAt: docUser.created_at ? new Date(docUser.created_at) : new Date(),
      raw: docUser
    }

    await users.updateOne({ _id: doc._id }, { $set: doc }, { upsert: true })
    return { ok: true }
  }catch(err){
    console.error('sync user error', err)
    return sendError(event, createError({ statusCode: 500, statusMessage: 'DB error' }))
  }
})
import crypto from 'crypto'

import { MongoClient } from "mongodb";

// Simple cached client to avoid reconnecting on every lambda invocation
let cachedClient: MongoClient | null = null;

async function getClient(uri: string) {
  if (cachedClient) return cachedClient;
  const client = new MongoClient(uri);
  await client.connect();
  cachedClient = client;
  return client;
}

export default defineEventHandler(async (event) => {
  const body = await readBody(event);
  // Expecting Clerk user payload (id, email, firstName, lastName)
  const user = body?.user;
  if (!user || !user.id) {
    return sendError(
      event,
      createError({
        statusCode: 400,
        statusMessage: "Invalid payload: missing user",
      })
    );
  }

  const config = useRuntimeConfig();
  const uri = config?.PUBLIC_MONGO_URI || process.env.MONGO_URI;
  if (!uri) {
    return sendError(
      event,
      createError({
        statusCode: 500,
        statusMessage: "MONGO_URI not configured",
      })
    );
  }

  try {
    const client = await getClient(uri);
    const db = client.db("healthly");
    const users = db.collection("users");

    // Upsert by Clerk user id
    const doc = {
      _id: user.id,
      email: user.email_addresses?.[0]?.email_address ?? user.email ?? null,
      firstName: user.first_name ?? user.firstName ?? null,
      lastName: user.last_name ?? user.lastName ?? null,
      createdAt: user.created_at ? new Date(user.created_at) : new Date(),
    };

    await users.updateOne({ _id: doc._id }, { $set: doc }, { upsert: true });
    return { ok: true };
  } catch (err) {
    console.error("sync user error", err);
    return sendError(
      event,
      createError({ statusCode: 500, statusMessage: "DB error" })
    );
  }
  
  /**
   * Helper: compute HMAC-SHA256 of the given payload string with secret
   */
  function computeHmac(secret: string, payload: string) {
    return crypto.createHmac('sha256', secret).update(payload).digest('hex');
  }
  
  // Optional webhook signature verification
  const webhookSecret = config?.CLERK_WEBHOOK_SECRET || process.env.CLERK_WEBHOOK_SECRET;
  if (webhookSecret) {
    // We assume Clerk includes a header 'x-clerk-signature' with hex HMAC-SHA256 of JSON payload
    const sigHeader = getRequestHeader(event, 'x-clerk-signature') || getRequestHeader(event, 'X-Clerk-Signature');
    if (!sigHeader) {
      return sendError(event, createError({ statusCode: 400, statusMessage: 'Missing signature header' }));
    }
    
    // compute HMAC of the stringified body. NOTE: this assumes Clerk signs the raw JSON string.
    const payloadStr = JSON.stringify(body);
    const expected = computeHmac(webhookSecret, payloadStr);
    if (!crypto.timingSafeEqual(Buffer.from(expected, 'hex'), Buffer.from(sigHeader, 'hex'))) {
      return sendError(event, createError({ statusCode: 401, statusMessage: 'Invalid webhook signature' }));
    }
  }
  
  let docUser = user;
  
  // If we have a Clerk API key, fetch the authoritative user profile from Clerk Admin API
  const clerkApiKey = config?.CLERK_API_KEY || process.env.CLERK_API_KEY;
  if (clerkApiKey) {
    try {
      const clerkRes = await $fetch(`https://api.clerk.com/v1/users/${encodeURIComponent(user.id)}`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${clerkApiKey}` },
      });
      docUser = clerkRes as any;
    } catch (err) {
      // log but continue with provided payload
      console.error('Failed to fetch user from Clerk Admin API', err);
    }
  }
  
  const doc = {
    _id: docUser.id,
    email: docUser.email_addresses?.[0]?.email_address ?? docUser.email ?? null,
    firstName: docUser.first_name ?? docUser.firstName ?? null,
    lastName: docUser.last_name ?? docUser.lastName ?? null,
    createdAt: docUser.created_at ? new Date(docUser.created_at) : new Date(),
    raw: docUser
  };
  
  await users.updateOne({ _id: doc._id }, { $set: doc }, { upsert: true });
  return { ok: true };
});
});
