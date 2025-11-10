export default defineEventHandler(async (event) => {
  const body = await readBody(event);
  const userId = body?.userId;
  if (!userId)
    return sendError(
      event,
      createError({ statusCode: 400, statusMessage: "Missing userId" })
    );

  const config = useRuntimeConfig();
  const clerkApiKey = config?.CLERK_API_KEY || process.env.CLERK_API_KEY;
  if (!clerkApiKey)
    return sendError(
      event,
      createError({
        statusCode: 501,
        statusMessage: "CLERK_API_KEY not configured",
      })
    );

  try {
    const clerkRes = await $fetch(
      `https://api.clerk.com/v1/users/${encodeURIComponent(userId)}`,
      {
        method: "GET",
        headers: { Authorization: `Bearer ${clerkApiKey}` },
      }
    );
    return { ok: true, user: clerkRes };
  } catch (err) {
    console.error("verify user error", err);
    return sendError(
      event,
      createError({ statusCode: 500, statusMessage: "Clerk API error" })
    );
  }
});
