<script setup lang="ts">
// Page shows dashboard when user is signed in via Clerk
// Components are auto-imported by Nuxt

async function syncProfile() {
  // Try to find Clerk user on the client; fallback will prompt for minimal info
  // This is best-effort: for production wire a Clerk webhook to call /api/users/sync
  // or use Clerk SDK to get the current user server-side.
  // Attempt common globals
  // @ts-ignore
  const user =
    (window as any)?.Clerk?.user ?? (window as any)?.__clerk__?.user ?? null;

  let payload = { user };
  if (!user) {
    const email = prompt(
      "Clerk user object not found. Enter your email to sync a minimal record (optional):"
    );
    if (!email) return;
    payload = { user: { id: email, email } };
  }

  try {
    const res = await fetch("/api/users/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    alert("Profile synced");
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error("sync error", err);
    alert("Sync failed: " + String(err));
  }
}
</script>

<template>
  <main class="page-wrap">
    <SignedOut>
      <section class="signed-out">
        <h2>Welcome to Healthly</h2>
        <p>Please sign in to view your dashboard.</p>
        <SignInButton />
      </section>
    </SignedOut>

    <SignedIn>
      <section class="dashboard">
        <h1>Your Daily Dashboard</h1>
        <div
          style="
            display: flex;
            gap: 0.5rem;
            align-items: center;
            margin-bottom: 0.75rem;
          "
        >
          <button @click="syncProfile" class="sync-btn">
            Sync profile to DB
          </button>
          <small class="muted"
            >(or configure Clerk webhook to POST to /api/users/sync)</small
          >
        </div>
        <div class="cards-grid">
          <WeightCard />
          <CalorieCard />
          <MacrosCard />
        </div>
      </section>
    </SignedIn>
  </main>
</template>

<style scoped>
.page-wrap {
  padding: 1.25rem;
  max-width: 1200px;
  margin: 0 auto;
}
.signed-out {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 3rem 1rem;
  text-align: center;
}
.dashboard h1 {
  margin-bottom: 1rem;
}
.cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

@media (max-width: 900px) {
  .cards-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 540px) {
  .cards-grid {
    grid-template-columns: 1fr;
  }
}
.sync-btn {
  background: #0ea5a4;
  color: white;
  border: none;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
}
.muted {
  color: #6b7280;
}
</style>
