<script setup lang="ts">
withDefaults(
  defineProps<{
    message: string
    role: string
    style?: string
  }>(),
  {}
)
</script>

<template>
  <div :class="['answer-message-container', role]" :style="style">
    <div class="answer-message-text">
      {{ message }}
    </div>
  </div>
</template>

<style scoped lang="less">
.answer-message-container {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 12px;
  color: #26244c;

  &.human {
    border: 1px solid rgba(214, 222, 219, 0.96);
    background: rgba(255, 255, 255, 0.94);
    // margin-left: 20px;
    margin-right: 0;
  }

  &.avatar {
    border: 1px solid #4e4195;
    background: #5b4ca8;
    color: #ffffff;
    box-shadow: 0 5px 14px rgba(67, 53, 137, 0.16);
    // margin-right: 20px;
  }
}
</style>
