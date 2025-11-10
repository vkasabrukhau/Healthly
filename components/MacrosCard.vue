<script setup lang="ts">
import { reactive } from "vue";
import { useDashboard } from "~/composables/useDashboard";
const store = useDashboard();

const local = reactive({
  protein: store.macrosForToday?.protein ?? 0,
  carbs: store.macrosForToday?.carbs ?? 0,
  fat: store.macrosForToday?.fat ?? 0,
});
function save() {
  store.setMacros({
    protein: Number(local.protein),
    carbs: Number(local.carbs),
    fat: Number(local.fat),
  });
}
</script>

<template>
  <article class="card">
    <header>
      <h3>Macros</h3>
      <small>Grams</small>
    </header>

    <section class="content">
      <div class="table-row">
        <label>Protein</label
        ><input type="number" v-model.number="local.protein" />
      </div>
      <div class="table-row">
        <label>Carbs</label><input type="number" v-model.number="local.carbs" />
      </div>
      <div class="table-row">
        <label>Fat</label><input type="number" v-model.number="local.fat" />
      </div>

      <div class="actions">
        <button @click="save">Save</button>
        <div class="meta">
          Total:
          <strong>{{
            Number(local.protein) + Number(local.carbs) + Number(local.fat)
          }}</strong>
          g
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
  background: #6366f1;
  color: white;
  border: none;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
}
.meta {
  color: #6b7280;
}
</style>
