import { Ref } from "vue";
import { useState } from "#imports";

type Macros = { protein: number; carbs: number; fat: number };

export function useDashboard() {
  // Nuxt useState persists state between server/client and across pages
  const weightForToday = useState<number | null>("weightForToday", () => null);
  const lastWeight = useState<number | null>("lastWeight", () => null);

  const caloriesForToday = useState<number | null>(
    "caloriesForToday",
    () => null
  );
  const calorieGoal = useState<number | null>("calorieGoal", () => 2000);

  const macrosForToday = useState<Macros | null>("macrosForToday", () => ({
    protein: 0,
    carbs: 0,
    fat: 0,
  }));

  function setWeight(v: number | null) {
    if (v != null) {
      lastWeight.value = weightForToday.value ?? lastWeight.value;
      weightForToday.value = v;
    } else {
      weightForToday.value = null;
    }
  }

  function setCalories(v: number | null) {
    caloriesForToday.value = v;
  }

  function setMacros(m: Macros) {
    macrosForToday.value = m;
  }

  return {
    weightForToday,
    lastWeight,
    setWeight,
    caloriesForToday,
    calorieGoal,
    setCalories,
    macrosForToday,
    setMacros,
    // convenience getters
    get caloriesForTodayValue() {
      return caloriesForToday.value;
    },
    get weightForTodayValue() {
      return weightForToday.value;
    },
  };
}
