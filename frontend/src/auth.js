import { ref } from 'vue'
export const account = ref(null)
export const sessionExpired = () => { account.value = null; window.dispatchEvent(new Event('qiongyu-session-expired')) }
