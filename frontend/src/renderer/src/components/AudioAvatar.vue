<script setup lang="ts">
defineProps<{
  active: boolean
  speaking: boolean
  status: string
}>()
</script>

<template>
  <div
    class="audio-avatar"
    :class="{ 'is-active': active, 'is-speaking': speaking }"
    data-testid="audio-avatar-fallback"
    :aria-label="`音频模式数字人，${status}`"
  >
    <div class="audio-avatar__stage" aria-hidden="true">
      <span class="audio-avatar__orbit audio-avatar__orbit--outer" />
      <span class="audio-avatar__orbit audio-avatar__orbit--inner" />
      <span class="audio-avatar__signal audio-avatar__signal--left" />
      <span class="audio-avatar__signal audio-avatar__signal--right" />

      <svg class="audio-avatar__portrait" viewBox="0 0 220 260" role="presentation">
        <defs>
          <linearGradient id="avatar-hair" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#183b36" />
            <stop offset="0.55" stop-color="#0a211e" />
            <stop offset="1" stop-color="#071411" />
          </linearGradient>
          <linearGradient id="avatar-skin" x1="0.2" y1="0" x2="0.8" y2="1">
            <stop offset="0" stop-color="#f9d9c9" />
            <stop offset="0.6" stop-color="#eebfaf" />
            <stop offset="1" stop-color="#d99f92" />
          </linearGradient>
          <linearGradient id="avatar-suit" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#d8fff4" />
            <stop offset="0.45" stop-color="#6bd8bc" />
            <stop offset="1" stop-color="#1f806c" />
          </linearGradient>
          <radialGradient id="avatar-eye" cx="50%" cy="44%" r="60%">
            <stop offset="0" stop-color="#c9fff0" />
            <stop offset="0.35" stop-color="#4db89d" />
            <stop offset="1" stop-color="#071b17" />
          </radialGradient>
          <filter id="avatar-glow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <path
          class="audio-avatar__shoulders"
          d="M23 259c7-47 34-73 70-78h34c37 5 63 31 70 78Z"
          fill="url(#avatar-suit)"
        />
        <path d="m77 187 33 29 33-29 18 11-21 61H80l-21-61Z" fill="#ebfff9" opacity=".92" />
        <path d="m91 169 3 28 16 19 16-19 3-28Z" fill="url(#avatar-skin)" />

        <path
          d="M50 91c0-48 25-76 61-76 40 0 65 29 62 79l-8 60c-14 25-33 38-55 38-24 0-45-15-57-43Z"
          fill="url(#avatar-hair)"
        />
        <path
          d="M63 92c2-38 20-61 49-61 30 0 47 22 48 59l-6 49c-9 29-25 45-44 45-20 0-37-18-45-47Z"
          fill="url(#avatar-skin)"
        />
        <path
          d="M60 92c3-39 20-64 54-64 23 0 41 14 48 39-22-13-51-10-77 5-9 6-17 12-25 20Z"
          fill="url(#avatar-hair)"
        />
        <path d="M66 88c-2 27-1 51 8 73-18-14-24-40-19-69Z" fill="#0b2521" />
        <path d="M157 82c6 30 4 60-11 84 20-14 27-42 20-74Z" fill="#081d1a" />

        <g class="audio-avatar__eyes">
          <path d="M78 107c7-7 18-7 25 0-8-3-17-3-25 0Z" fill="#523d3a" />
          <path d="M117 107c7-7 18-7 25 0-8-3-17-3-25 0Z" fill="#523d3a" />
          <ellipse cx="91" cy="111" rx="6" ry="7" fill="url(#avatar-eye)" />
          <ellipse cx="129" cy="111" rx="6" ry="7" fill="url(#avatar-eye)" />
          <circle cx="93" cy="108" r="1.5" fill="#fff" />
          <circle cx="131" cy="108" r="1.5" fill="#fff" />
        </g>
        <path d="M108 113c-2 13-4 20-1 23 3 2 7 2 10 0" fill="none" stroke="#c78e83" />
        <path
          class="audio-avatar__mouth"
          d="M95 149c9 5 21 5 30 0-7 10-23 11-30 0Z"
          fill="#a94f57"
        />
        <path d="M97 149c8 2 18 2 26 0" fill="none" stroke="#ffd8d2" stroke-width="1.2" />

        <path
          class="audio-avatar__circuit"
          d="M150 56h24v20m-2 0h12m-25 87h22v-16"
          fill="none"
          stroke="#72e8c7"
          stroke-linecap="round"
          stroke-width="1.5"
          opacity=".72"
          filter="url(#avatar-glow)"
        />
        <circle cx="174" cy="76" r="3" fill="#8cffe0" filter="url(#avatar-glow)" />
        <circle cx="181" cy="147" r="3" fill="#8cffe0" filter="url(#avatar-glow)" />
      </svg>
    </div>

    <div class="audio-avatar__meta">
      <strong>AI 数字人</strong>
      <span>{{ status }}</span>
    </div>
  </div>
</template>

<style scoped lang="less">
.audio-avatar {
  position: absolute;
  z-index: 2;
  inset: 0;
  display: grid;
  place-items: center;
  overflow: hidden;
  color: #eafff9;
  background:
    radial-gradient(circle at 50% 38%, rgba(87, 222, 185, 0.24), transparent 36%),
    linear-gradient(160deg, #071714 0%, #020706 72%);
}

.audio-avatar::before {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(112, 225, 193, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(112, 225, 193, 0.035) 1px, transparent 1px);
  background-size: 22px 22px;
  content: '';
  mask-image: linear-gradient(to bottom, #000, transparent 88%);
}

.audio-avatar__stage {
  position: relative;
  width: min(74%, 280px);
  aspect-ratio: 1 / 1.08;
  display: grid;
  place-items: center;
  transform: translateY(-2%);
}

.audio-avatar__stage::after {
  position: absolute;
  right: 14%;
  bottom: 3%;
  left: 14%;
  height: 15%;
  border-radius: 50%;
  background: rgba(67, 223, 181, 0.2);
  filter: blur(16px);
  content: '';
}

.audio-avatar__portrait {
  position: relative;
  z-index: 2;
  width: 78%;
  height: 96%;
  overflow: visible;
  filter: drop-shadow(0 16px 24px rgba(0, 0, 0, 0.42));
  transform-origin: 50% 80%;
}

.audio-avatar__orbit {
  position: absolute;
  border: 1px solid rgba(112, 225, 193, 0.28);
  border-radius: 50%;
  box-shadow: 0 0 26px rgba(112, 225, 193, 0.06);
}

.audio-avatar__orbit--outer {
  width: 96%;
  height: 96%;
  border-style: dashed;
  animation: avatar-orbit 28s linear infinite;
}

.audio-avatar__orbit--inner {
  width: 76%;
  height: 76%;
  border-color: rgba(112, 225, 193, 0.18);
  animation: avatar-orbit 18s linear infinite reverse;
}

.audio-avatar__signal {
  position: absolute;
  top: 42%;
  width: 9%;
  height: 22%;
  border: solid rgba(112, 225, 193, 0.38);
  opacity: 0.45;
}

.audio-avatar__signal--left {
  left: -1%;
  border-width: 0 0 0 2px;
  border-radius: 50% 0 0 50%;
}

.audio-avatar__signal--right {
  right: -1%;
  border-width: 0 2px 0 0;
  border-radius: 0 50% 50% 0;
}

.audio-avatar__eyes {
  transform-box: fill-box;
  transform-origin: center;
  animation: avatar-blink 6.2s infinite;
}

.audio-avatar__meta {
  position: absolute;
  z-index: 4;
  bottom: 42px;
  display: grid;
  gap: 4px;
  min-width: 150px;
  padding: 9px 14px;
  border: 1px solid rgba(112, 225, 193, 0.34);
  border-radius: 9px;
  text-align: center;
  background: rgba(2, 12, 10, 0.84);
  backdrop-filter: blur(10px);
}

.audio-avatar__meta strong {
  font-size: 13px;
  letter-spacing: 0.06em;
}

.audio-avatar__meta span {
  color: #bfe3da;
  font-size: 11px;
  line-height: 1.4;
}

.audio-avatar.is-active .audio-avatar__orbit--inner {
  border-color: rgba(112, 225, 193, 0.42);
  box-shadow: 0 0 30px rgba(112, 225, 193, 0.13);
}

.audio-avatar.is-active .audio-avatar__signal {
  animation: avatar-signal 1.8s ease-in-out infinite;
}

.audio-avatar.is-speaking .audio-avatar__portrait {
  animation: avatar-speaking 1.15s ease-in-out infinite;
}

.audio-avatar.is-speaking .audio-avatar__mouth {
  transform-box: fill-box;
  transform-origin: center;
  animation: avatar-mouth 0.34s ease-in-out infinite alternate;
}

.audio-avatar.is-speaking .audio-avatar__orbit--outer {
  border-color: rgba(112, 225, 193, 0.64);
  box-shadow:
    0 0 36px rgba(112, 225, 193, 0.18),
    inset 0 0 24px rgba(112, 225, 193, 0.08);
}

@keyframes avatar-orbit {
  to {
    transform: rotate(360deg);
  }
}

@keyframes avatar-blink {
  0%,
  45%,
  49%,
  100% {
    transform: scaleY(1);
  }
  47% {
    transform: scaleY(0.08);
  }
}

@keyframes avatar-signal {
  0%,
  100% {
    opacity: 0.25;
    transform: scaleY(0.55);
  }
  50% {
    opacity: 0.85;
    transform: scaleY(1);
  }
}

@keyframes avatar-speaking {
  0%,
  100% {
    transform: translateY(0) rotate(-0.25deg);
  }
  50% {
    transform: translateY(-2px) rotate(0.25deg);
  }
}

@keyframes avatar-mouth {
  from {
    transform: scaleY(0.7);
  }
  to {
    transform: scaleY(1.35);
  }
}

@media (max-width: 620px) {
  .audio-avatar__stage {
    width: min(70%, 250px);
  }

  .audio-avatar__meta {
    bottom: 24px;
    min-width: 140px;
    padding: 8px 12px;
  }

  .audio-avatar__meta strong {
    font-size: 12px;
  }

  .audio-avatar__meta span {
    font-size: 10px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .audio-avatar *,
  .audio-avatar *::before,
  .audio-avatar *::after {
    animation: none !important;
  }
}
</style>
