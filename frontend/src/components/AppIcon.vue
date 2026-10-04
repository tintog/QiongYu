<!-- 内联图标集：统一 24×24 viewBox、currentColor 描边，避免引入图标库依赖 -->
<template>
  <svg
    :viewBox="'0 0 24 24'"
    fill="none"
    :stroke="color"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    :width="size"
    :height="size"
    aria-hidden="true"
  >
    <template v-for="(d, index) in paths" :key="index">
      <circle v-if="d.type === 'circle'" :cx="d.cx" :cy="d.cy" :r="d.r" :fill="d.fill || 'none'" />
      <path v-else :d="d.d || d" :fill="d.fill || 'none'" />
    </template>
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 16 },
  strokeWidth: { type: [Number, String], default: 1.7 },
  color: { type: String, default: 'currentColor' },
})

const ICONS = {
  // 导航
  globe: ['M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z', 'M2 12h20', 'M12 2c2.5 3 2.5 17 0 20-2.5-3-2.5-17 0-20Z'],
  layers: ['M12 3 3 8l9 5 9-5-9-5Z', 'm3 13 9 5 9-5', 'm3 17 9 5 9-5'],
  chart: ['M4 4v16h16', 'm7 15 3-4 3 3 4-6'],
  'chart-bar': ['M4 4v16h16', 'M8 16V11', 'M13 16V7', 'M18 16v-3'],
  target: [{ type: 'circle', cx: 12, cy: 12, r: 9 }, { type: 'circle', cx: 12, cy: 12, r: 5 }, { type: 'circle', cx: 12, cy: 12, r: 1.4, fill: 'currentColor' }],
  sliders: ['M4 6h10', 'M18 6h2', 'M4 12h4', 'M12 12h8', 'M4 18h12', 'M20 18h0', { type: 'circle', cx: 16, cy: 6, r: 2 }, { type: 'circle', cx: 10, cy: 12, r: 2 }, { type: 'circle', cx: 18, cy: 18, r: 2 }],
  bell: ['M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9', 'M10.5 21a1.9 1.9 0 0 0 3 0'],
  database: ['M12 3c4.4 0 8 1.1 8 2.5S16.4 8 12 8 4 6.9 4 5.5 7.6 3 12 3Z', 'M4 5.5v13C4 19.9 7.6 21 12 21s8-1.1 8-2.5v-13', 'M4 12c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5'],
  wind: ['M3 8h11a3 3 0 1 0-3-3', 'M3 16h15a3 3 0 1 1-3 3', 'M3 12h9'],
  thermo: ['M14 14.8V4a2 2 0 1 0-4 0v10.8a4 4 0 1 0 4 0Z', 'M12 9v6'],
  droplet: ['M12 3s6 6.4 6 10.4A6 6 0 0 1 6 13.4C6 9.4 12 3 12 3Z'],
  gauge: ['M12 14 16 9', 'M4 18a10 10 0 1 1 16 0', { type: 'circle', cx: 12, cy: 15, r: 2 }],
  eye: ['M2 12s3.8-6 10-6 10 6 10 6-3.8 6-10 6-10-6-10-6Z', { type: 'circle', cx: 12, cy: 12, r: 2.6 }],
  clock: [{ type: 'circle', cx: 12, cy: 12, r: 9 }, 'M12 7.5V12l3 2'],
  play: ['m8 5 11 7-11 7V5Z'],
  pause: ['M9 5v14', 'M15 5v14'],
  prev: ['m15 6-6 6 6 6'],
  next: ['m9 6 6 6-6 6'],
  refresh: ['M20 11A8 8 0 0 0 5.6 6.6L4 8', 'M4 4v4h4', 'M4 13a8 8 0 0 0 14.4 4.4L20 16', 'M20 20v-4h-4'],
  download: ['M12 3v12', 'm7 11 5 5 5-5', 'M4 19h16'],
  search: ['M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z', 'm16.5 16.5 3.5 3.5'],
  alert: ['M12 3 2.5 20h19L12 3Z', 'M12 9.5v4.5', 'M12 17.2v.3'],
  check: ['m4.5 12.5 5 5 10-11'],
  close: ['m6 6 12 12', 'm18 6-12 12'],
  info: [{ type: 'circle', cx: 12, cy: 12, r: 9 }, 'M12 11v5', 'M12 8.2v.3'],
  route: [{ type: 'circle', cx: 6, cy: 6, r: 2.5 }, { type: 'circle', cx: 18, cy: 18, r: 2.5 }, 'M8.5 6h6a3 3 0 0 1 3 3v6.5'],
  grid: ['M4 4h7v7H4V4Z', 'M13 4h7v7h-7V4Z', 'M4 13h7v7H4v-7Z', 'M13 13h7v7h-7v-7Z'],
  compare: ['M4 5h6v14H4V5Z', 'M14 5h6v14h-6V5Z', 'M10 12h4'],
  city: ['M4 21V9l6-4v16', 'M10 21V11h10v10', 'M13 14h1.5', 'M16.5 14H18', 'M13 17.5h1.5', 'M16.5 17.5H18'],
  locate: [{ type: 'circle', cx: 12, cy: 12, r: 8 }, 'M12 2v4', 'M12 18v4', 'M2 12h4', 'M18 12h4', { type: 'circle', cx: 12, cy: 12, r: 2 }],
  zoomIn: ['M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z', 'm16.5 16.5 3.5 3.5', 'M11 8.5v5', 'M8.5 11h5'],
  zoomOut: ['M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z', 'm16.5 16.5 3.5 3.5', 'M8.5 11h5'],
  server: ['M4 5h16v5H4V5Z', 'M4 14h16v5H4v-5Z', 'M7.5 7.5v.01', 'M7.5 16.5v.01'],
  shield: ['M12 3 5 6v6c0 4.4 3 7.6 7 9 4-1.4 7-4.6 7-9V6l-7-3Z', 'm9 12 2 2 4-4'],
  branch: [{ type: 'circle', cx: 6, cy: 6, r: 2.4 }, { type: 'circle', cx: 6, cy: 18, r: 2.4 }, { type: 'circle', cx: 18, cy: 12, r: 2.4 }, 'M6 8.4v7.2', 'M8.4 6h4a3 3 0 0 1 3 3v.6', 'M8.4 18h4a3 3 0 0 0 3-3v-.6'],
  sun: [{ type: 'circle', cx: 12, cy: 12, r: 4 }, 'M12 2v2', 'M12 20v2', 'M2 12h2', 'M20 12h2', 'm5 5 1.5 1.5', 'm17.5 17.5 1.5 1.5', 'm19 5-1.5 1.5', 'm6.5 17.5-1.5 1.5'],
  activity: ['M3 12h4l2.5-6 4 12 2.5-6h5'],
  compass: [{ type: 'circle', cx: 12, cy: 12, r: 9 }, 'm15.5 8.5-2 5-5 2 2-5 5-2Z'],
}

const paths = computed(() => {
  const value = ICONS[props.name]
  if (!value) return []
  return value.map((item) => (typeof item === 'string' ? { d: item } : item))
})
</script>
