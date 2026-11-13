export interface AdsgramAdResult {
  done: boolean
  description: string
  state: 'load' | 'render' | 'playing' | 'destroy'
  error: boolean
}

export interface AdsgramInitParams {
  blockId: string
  debug?: boolean
  debugBannerType?: 'RewardedVideo' | 'FullscreenMedia'
}

export interface AdsgramController {
  show: () => Promise<AdsgramAdResult>
  destroy?: () => void
}

declare global {
  interface Window {
    Adsgram?: {
      init: (params: AdsgramInitParams) => AdsgramController
    }
  }
}

/**
 * Triggers an Adsgram rewarded video ad.
 * Resolves to true if and only if the user watched the video to completion without skipping.
 */
export async function showRewardedAd(customBlockId?: string): Promise<boolean> {
  const blockId =
    customBlockId ||
    (typeof import.meta !== 'undefined' && import.meta.env?.VITE_ADSGRAM_BLOCK_ID) ||
    'int-9195'

  if (typeof window !== 'undefined' && window.Adsgram) {
    try {
      const adController = window.Adsgram.init({ blockId })
      const res = await adController.show()
      // According to Adsgram docs, res.done is true when video is watched to completion
      if (res && res.done === false) {
        throw new Error('You must watch the full ad without skipping to double your points!')
      }
      return true
    } catch (err) {
      console.warn('Adsgram ad was interrupted or closed early:', err)
      const msg =
        (err as { description?: string })?.description ||
        (err as Error)?.message ||
        'You must watch the full ad without skipping to double your points!'
      throw new Error(msg)
    }
  }

  // Fallback for local development outside Telegram
  if (import.meta.env.DEV) {
    console.info('[Adsgram] Development Mode: simulating rewarded ad playback...')
    await new Promise((resolve) => setTimeout(resolve, 1500))
    return true
  }

  throw new Error('Ad service could not be loaded. Please disable ad-blockers and try again.')
}

