<script setup lang="ts">
import { computed, ref } from "vue";
import { useDashboard } from "~/composables/useDashboard";
const store = useDashboard();

const localCals = ref(store.caloriesForToday ?? 0);
function save() {
  store.setCalories(Number(localCals.value));
}
</script>

<template>
  <article class="card">
    <header>
      <h3>Calorie Tracker</h3>
      <small>Today</small>
    </header>

    <section class="content">
      <div class="table-row">
        <label>Calories (kcal)</label>
        <input type="number" v-model.number="localCals" />
      </div>
      <div class="actions">
        <button @click="save">Save</button>
        <div class="meta">
          Goal: <strong>{{ store.calorieGoal ?? "—" }}</strong>
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
  background: #ef4444;
  color: white;
  border: none;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
}
.meta {
  color: #6b7280;
}
</style>
