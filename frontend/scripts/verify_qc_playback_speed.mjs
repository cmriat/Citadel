import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

import { chromium } from 'playwright'

// Run:
//   VITE_API_HOST=127.0.0.1 VITE_API_PORT=8001 npm run dev
//   pixi run -- uvicorn backend.main:app --host 0.0.0.0 --port 8001
//   node scripts/verify_qc_playback_speed.mjs

const BASE_URL = process.env.QC_BASE_URL ?? 'http://127.0.0.1:5174/pipeline'
const DATASET_ROOT =
  process.env.QC_DATASET_ROOT ??
  '/pfs/data/zhangchaorong/code/Citadel/.sisyphus/tmp/qc_sample_dataset'
const EVIDENCE_DIR =
  process.env.QC_EVIDENCE_DIR ??
  '/pfs/data/zhangchaorong/code/Citadel/.sisyphus/evidence'

const sel = (testId) => `[data-testid="${testId}"]`

async function waitVideoReady(page, testId) {
  const s = sel(testId)
  await page.waitForSelector(s, { state: 'attached', timeout: 120000 })
  await page.waitForFunction(
    (selector) => {
      const el = document.querySelector(selector)
      return el && el.readyState >= 3
    },
    s,
    { timeout: 120000 }
  )
}

async function getPlaybackRate(page, testId) {
  return await page.$eval(sel(testId), (el) => el.playbackRate)
}

async function main() {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true })

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  })
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } })

  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' })

  await page.waitForSelector('[data-testid="pipeline-local-dir-input"] input', {
    timeout: 60000,
  })
  await page.fill('[data-testid="pipeline-local-dir-input"] input', DATASET_ROOT)
  await page.locator('[data-testid="pipeline-local-dir-input"] input').blur()

  await page.click(sel('pipeline-open-qc-button'))
  await page.waitForSelector(sel('qc-episode-episode_0001'), { timeout: 120000 })
  await page.screenshot({
    path: path.join(EVIDENCE_DIR, 'qc-open.png'),
    fullPage: true,
  })

  await page.click(sel('qc-episode-episode_0001'))
  await waitVideoReady(page, 'qc-video-cam_env')
  await waitVideoReady(page, 'qc-video-cam_left_wrist')
  await waitVideoReady(page, 'qc-video-cam_right_wrist')

  await page.click(sel('qc-rate-cam_env'))
  await page
    .locator('.el-dropdown-menu:visible')
    .getByText('2.0x', { exact: true })
    .click()

  await page.click(sel('qc-rate-cam_left_wrist'))
  await page
    .locator('.el-dropdown-menu:visible')
    .getByText('3.0x', { exact: true })
    .click()

  const ratesAfterSet = {
    cam_env: await getPlaybackRate(page, 'qc-video-cam_env'),
    cam_left_wrist: await getPlaybackRate(page, 'qc-video-cam_left_wrist'),
    cam_right_wrist: await getPlaybackRate(page, 'qc-video-cam_right_wrist'),
  }
  if (ratesAfterSet.cam_env !== 2) throw new Error(`cam_env expected 2, got ${ratesAfterSet.cam_env}`)
  if (ratesAfterSet.cam_left_wrist !== 3) throw new Error(`cam_left_wrist expected 3, got ${ratesAfterSet.cam_left_wrist}`)
  if (ratesAfterSet.cam_right_wrist !== 1) throw new Error(`cam_right_wrist expected 1, got ${ratesAfterSet.cam_right_wrist}`)

  await page.screenshot({
    path: path.join(EVIDENCE_DIR, 'qc-rates-set.png'),
    fullPage: true,
  })

  await page.click(sel('qc-episode-episode_0002'))
  await waitVideoReady(page, 'qc-video-cam_env')
  await waitVideoReady(page, 'qc-video-cam_left_wrist')
  await waitVideoReady(page, 'qc-video-cam_right_wrist')

  const ratesAfterSwitch = {
    cam_env: await getPlaybackRate(page, 'qc-video-cam_env'),
    cam_left_wrist: await getPlaybackRate(page, 'qc-video-cam_left_wrist'),
    cam_right_wrist: await getPlaybackRate(page, 'qc-video-cam_right_wrist'),
  }
  if (ratesAfterSwitch.cam_env !== 1) throw new Error(`cam_env reset expected 1, got ${ratesAfterSwitch.cam_env}`)
  if (ratesAfterSwitch.cam_left_wrist !== 1) throw new Error(`cam_left_wrist reset expected 1, got ${ratesAfterSwitch.cam_left_wrist}`)
  if (ratesAfterSwitch.cam_right_wrist !== 1) throw new Error(`cam_right_wrist reset expected 1, got ${ratesAfterSwitch.cam_right_wrist}`)

  await page.screenshot({
    path: path.join(EVIDENCE_DIR, 'qc-episode-switch-reset.png'),
    fullPage: true,
  })

  console.log(JSON.stringify({ ratesAfterSet, ratesAfterSwitch }, null, 2))
  await browser.close()
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
