/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    Telegram?: { WebApp: any }
  }
}

export const tg = window.Telegram?.WebApp
export const initData: string = tg?.initData ?? ''
export const startParam: string | undefined = tg?.initDataUnsafe?.start_param

function applyTheme() {
  if (tg) document.documentElement.dataset.theme = tg.colorScheme === 'dark' ? 'dark' : 'light'
}

export function initTelegram() {
  if (!tg) return
  tg.ready()
  tg.expand()
  applyTheme()
  tg.onEvent?.('themeChanged', applyTheme)
}

export function haptic(kind: 'success' | 'error' | 'tap') {
  const h = tg?.HapticFeedback
  if (!h) return
  if (kind === 'tap') h.impactOccurred('light')
  else h.notificationOccurred(kind)
}
