<script setup lang="ts">
import { useDashboard } from "~/composables/useDashboard";
import { computed } from "vue";
const store = useDashboard();

const local = computed(() => store.weightForToday);
function save() {
  store.setWeight(local.value);
}
</script>

<template>
  <article class="card">
    <header>
      <h3>Weight Tracker</h3>
      <small>Today</small>
    </header>

    <section class="content">
      <div class="table-row">
        <label>Weight (kg)</label>
        <input type="number" v-model.number="local.value" step="0.1" />
      </div>
      <div class="actions">
        <button @click="save">Save</button>
        <div class="meta">
          Last: <strong>{{ store.lastWeight ?? "—" }}</strong>
        </div>
      </div>
    </section>
  </article>
</template>

<style scoped>
.card {
  background: #fff;
  border-radius: 12px;
  padding: 1rem;
  box-shadow: 0 8px 22px rgba(16, 24, 40, 0.08);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.card header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card .content {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.table-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}
.table-row input {
  width: 120px;
  padding: 0.5rem;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}
.actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.5rem;
}
.actions button {
  background: #0ea5a4;
  color: white;
  border: none;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
}
.meta {
  color: #6b7280;
}
</style>
