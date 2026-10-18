<script setup lang="ts">
import type { City } from '../types/api'
defineProps<{ cities: City[]; modelValue: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <div class="select-field">
    <label for="city-select">城市</label>
    <select id="city-select" :value="modelValue" :disabled="disabled"
      @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)">
      <option value="" disabled>请选择城市</option>
      <option v-for="city in cities" :key="city.id" :value="city.id">{{ city.name }}</option>
    </select>
  </div>
</template>
